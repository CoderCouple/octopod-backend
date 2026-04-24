"""Tiered identity resolution: multi-signal scoring to merge duplicate developer_profile rows.

Blocking strategy avoids O(n²) — only compares profiles that share a potential signal.
Score = max(signal_weights).  ≥0.7 auto-merge, 0.4–0.7 review queue, <0.4 skip.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

log = logging.getLogger(__name__)

# ---- Signal weights ----

SIGNAL_WEIGHTS: dict[str, float] = {
    "hf_github_exact": 1.0,
    "email_exact": 0.9,
    "twitter_exact": 0.85,
    "website_crossref": 0.8,
    "linkedin_url_match": 0.75,
    "avatar_gravatar_match": 0.7,
    "name_location_exact": 0.6,
    "name_company_fuzzy": 0.55,
    "name_fuzzy_alone": 0.3,
}

AUTO_MERGE_THRESHOLD = 0.7
REVIEW_THRESHOLD = 0.4
NAME_BLOCK_CAP = 50


@dataclass
class ResolverStats:
    total_candidates: int = 0
    auto_merged: int = 0
    queued_for_review: int = 0
    skipped: int = 0
    errors: int = 0


@dataclass
class ProfileData:
    dp_id: str
    github_username: str | None = None
    huggingface_username: str | None = None
    email_hint: str | None = None
    display_name: str | None = None
    location: str | None = None
    company: str | None = None
    avatar_url: str | None = None
    website: str | None = None
    created_at: datetime | None = None
    # From gh_users
    gh_email: str | None = None
    gh_twitter: str | None = None
    gh_website: str | None = None
    gh_avatar: str | None = None
    gh_name: str | None = None
    gh_location: str | None = None
    gh_company: str | None = None
    # From hf_users
    hf_github_username: str | None = None
    hf_twitter: str | None = None
    hf_website: str | None = None
    hf_fullname: str | None = None
    hf_linkedin: str | None = None
    # From ln_pending_urls
    linkedin_url: str | None = None


@dataclass
class SignalMatch:
    signal: str
    weight: float
    detail: str = ""


@dataclass
class CandidatePair:
    source_id: str
    target_id: str
    score: float
    signals: list[dict[str, Any]] = field(default_factory=list)


class IdentityResolver:
    """Multi-signal identity resolver for developer profiles."""

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def run(
        self, since_hours: int = 24, full_scan: bool = False
    ) -> ResolverStats:
        stats = ResolverStats()

        profiles = await self._load_profiles(since_hours, full_scan)
        if len(profiles) < 2:
            log.info("[resolver] Only %d profiles, nothing to resolve", len(profiles))
            return stats

        log.info("[resolver] Loaded %d profiles for resolution", len(profiles))

        # Build blocks
        blocks = self._build_blocks(profiles)
        log.info("[resolver] Built %d blocks", len(blocks))

        # Score pairs within blocks
        seen_pairs: set[tuple[str, str]] = set()
        candidates: list[CandidatePair] = []

        for block in blocks:
            for i, p1 in enumerate(block):
                for p2 in block[i + 1 :]:
                    pair_key = _canonical_pair(p1.dp_id, p2.dp_id)
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    signals = self._score_pair(p1, p2)
                    if not signals:
                        continue

                    score = max(s.weight for s in signals)
                    if score < REVIEW_THRESHOLD:
                        stats.skipped += 1
                        continue

                    # Canonical ordering: older = target, newer = source
                    source_id, target_id = pair_key
                    candidates.append(CandidatePair(
                        source_id=source_id,
                        target_id=target_id,
                        score=score,
                        signals=[
                            {"signal": s.signal, "weight": s.weight, "detail": s.detail}
                            for s in signals
                        ],
                    ))

        log.info("[resolver] Found %d candidate pairs", len(candidates))
        stats.total_candidates = len(candidates)

        # Triage and persist
        for candidate in candidates:
            try:
                await self._triage_candidate(candidate, stats)
            except Exception:
                log.exception("[resolver] Error processing candidate %s→%s",
                              candidate.source_id, candidate.target_id)
                stats.errors += 1

        log.info(
            "[resolver] Done: %d auto-merged, %d queued, %d skipped, %d errors",
            stats.auto_merged, stats.queued_for_review, stats.skipped, stats.errors,
        )
        return stats

    # ---- Data loading ----

    async def _load_profiles(
        self, since_hours: int, full_scan: bool
    ) -> list[ProfileData]:
        where = "" if full_scan else (
            "WHERE dp.is_deleted = FALSE "
            "AND dp.created_at > NOW() - make_interval(hours => $1)"
        )
        params: list[Any] = [] if full_scan else [since_hours]

        # If full scan, we still exclude deleted ones
        if full_scan:
            where = "WHERE dp.is_deleted = FALSE AND (dp.merged_into_id IS NULL)"

        query = f"""
            SELECT
                dp.id AS dp_id,
                dp.github_username,
                dp.huggingface_username,
                dp.email_hint,
                dp.display_name,
                dp.location,
                dp.company,
                dp.avatar_url,
                dp.website,
                dp.created_at,
                gh.email AS gh_email,
                gh.twitter AS gh_twitter,
                gh.website_url AS gh_website,
                gh.avatar_url AS gh_avatar,
                gh.name AS gh_name,
                gh.location AS gh_location,
                gh.company AS gh_company,
                hf.github_username AS hf_github_username,
                hf.twitter AS hf_twitter,
                hf.website_url AS hf_website,
                hf.fullname AS hf_fullname,
                hf.linkedin AS hf_linkedin,
                lp.linkedin_url AS linkedin_url
            FROM developer_profile dp
            LEFT JOIN gh_users gh ON gh.login = dp.github_username
            LEFT JOIN hf_users hf ON hf.username = dp.huggingface_username
            LEFT JOIN ln_pending_urls lp
                ON (lp.source_platform = 'github' AND lp.source_username = dp.github_username)
                OR (lp.source_platform = 'huggingface' AND lp.source_username = dp.huggingface_username)
            {where}
        """

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        profiles_map: dict[str, ProfileData] = {}
        for row in rows:
            dp_id = row["dp_id"]
            if dp_id in profiles_map:
                # Merge linkedin_url from additional join rows
                if row["linkedin_url"] and not profiles_map[dp_id].linkedin_url:
                    profiles_map[dp_id].linkedin_url = row["linkedin_url"]
                continue
            profiles_map[dp_id] = ProfileData(
                dp_id=dp_id,
                github_username=row["github_username"],
                huggingface_username=row["huggingface_username"],
                email_hint=row["email_hint"],
                display_name=row["display_name"],
                location=row["location"],
                company=row["company"],
                avatar_url=row["avatar_url"],
                website=row["website"],
                created_at=row["created_at"],
                gh_email=row["gh_email"],
                gh_twitter=row["gh_twitter"],
                gh_website=row["gh_website"],
                gh_avatar=row["gh_avatar"],
                gh_name=row["gh_name"],
                gh_location=row["gh_location"],
                gh_company=row["gh_company"],
                hf_github_username=row["hf_github_username"],
                hf_twitter=row["hf_twitter"],
                hf_website=row["hf_website"],
                hf_fullname=row["hf_fullname"],
                hf_linkedin=row["hf_linkedin"],
                linkedin_url=row["linkedin_url"],
            )
        return list(profiles_map.values())

    # ---- Blocking ----

    def _build_blocks(self, profiles: list[ProfileData]) -> list[list[ProfileData]]:
        blocks: list[list[ProfileData]] = []
        index: dict[str, list[ProfileData]] = {}

        def add_to_block(key: str, profile: ProfileData) -> None:
            if not key:
                return
            index.setdefault(key, []).append(profile)

        for p in profiles:
            # Email block
            for email in _get_emails(p):
                add_to_block(f"email:{email}", p)

            # Cross-ref block: HF user claims a GH username
            if p.hf_github_username:
                add_to_block(f"gh_crossref:{p.hf_github_username.lower()}", p)
            if p.github_username:
                add_to_block(f"gh_crossref:{p.github_username.lower()}", p)

            # Twitter handle block
            twitter = _normalize_twitter(p.gh_twitter) or _normalize_twitter(p.hf_twitter)
            if twitter:
                add_to_block(f"twitter:{twitter}", p)

            # Name block (normalized)
            name = _normalize_name(p)
            if name:
                add_to_block(f"name:{name}", p)

            # LinkedIn URL block
            ln_url = p.linkedin_url or p.hf_linkedin
            if ln_url:
                add_to_block(f"linkedin:{ln_url.lower().rstrip('/')}", p)

        for key, members in index.items():
            if len(members) < 2:
                continue
            # Cap name blocks to avoid large comparisons
            if key.startswith("name:") and len(members) > NAME_BLOCK_CAP:
                continue
            # Deduplicate profiles within the same block
            seen_ids: set[str] = set()
            unique: list[ProfileData] = []
            for m in members:
                if m.dp_id not in seen_ids:
                    seen_ids.add(m.dp_id)
                    unique.append(m)
            if len(unique) >= 2:
                blocks.append(unique)

        return blocks

    # ---- Scoring ----

    def _score_pair(self, p1: ProfileData, p2: ProfileData) -> list[SignalMatch]:
        signals: list[SignalMatch] = []

        # hf_github_exact: HF user reports a GH login that matches the other profile
        if p1.hf_github_username and p2.github_username:
            if p1.hf_github_username.lower() == p2.github_username.lower():
                signals.append(SignalMatch(
                    "hf_github_exact", SIGNAL_WEIGHTS["hf_github_exact"],
                    f"HF({p1.huggingface_username}) → GH({p2.github_username})",
                ))
        if p2.hf_github_username and p1.github_username:
            if p2.hf_github_username.lower() == p1.github_username.lower():
                signals.append(SignalMatch(
                    "hf_github_exact", SIGNAL_WEIGHTS["hf_github_exact"],
                    f"HF({p2.huggingface_username}) → GH({p1.github_username})",
                ))

        # email_exact
        emails1 = _get_emails(p1)
        emails2 = _get_emails(p2)
        common_emails = emails1 & emails2
        if common_emails:
            signals.append(SignalMatch(
                "email_exact", SIGNAL_WEIGHTS["email_exact"],
                f"shared email: {next(iter(common_emails))}",
            ))

        # twitter_exact
        tw1 = _normalize_twitter(p1.gh_twitter) or _normalize_twitter(p1.hf_twitter)
        tw2 = _normalize_twitter(p2.gh_twitter) or _normalize_twitter(p2.hf_twitter)
        if tw1 and tw2 and tw1 == tw2:
            signals.append(SignalMatch(
                "twitter_exact", SIGNAL_WEIGHTS["twitter_exact"],
                f"shared twitter: @{tw1}",
            ))

        # website_crossref: GH website contains huggingface.co/{user} or vice versa
        if _website_crossref(p1, p2):
            signals.append(SignalMatch(
                "website_crossref", SIGNAL_WEIGHTS["website_crossref"],
                "website cross-references other platform profile",
            ))

        # linkedin_url_match
        ln1 = _normalize_linkedin(p1.linkedin_url) or _normalize_linkedin(p1.hf_linkedin)
        ln2 = _normalize_linkedin(p2.linkedin_url) or _normalize_linkedin(p2.hf_linkedin)
        if ln1 and ln2 and ln1 == ln2:
            signals.append(SignalMatch(
                "linkedin_url_match", SIGNAL_WEIGHTS["linkedin_url_match"],
                f"shared LinkedIn: {ln1}",
            ))

        # avatar_gravatar_match
        grav1 = _gravatar_hash(p1)
        grav2 = _gravatar_hash(p2)
        if grav1 and grav2 and grav1 == grav2:
            signals.append(SignalMatch(
                "avatar_gravatar_match", SIGNAL_WEIGHTS["avatar_gravatar_match"],
                f"shared Gravatar hash: {grav1[:8]}...",
            ))

        # Name-based signals
        name1 = _normalize_name(p1)
        name2 = _normalize_name(p2)
        if name1 and name2:
            jw = _jaro_winkler(name1, name2)
            loc1 = _normalize_location(p1)
            loc2 = _normalize_location(p2)
            comp1 = _normalize_company(p1)
            comp2 = _normalize_company(p2)

            if name1 == name2 and loc1 and loc2 and loc1 == loc2:
                signals.append(SignalMatch(
                    "name_location_exact", SIGNAL_WEIGHTS["name_location_exact"],
                    f"name={name1}, location={loc1}",
                ))
            elif jw >= 0.9 and comp1 and comp2 and comp1 == comp2:
                signals.append(SignalMatch(
                    "name_company_fuzzy", SIGNAL_WEIGHTS["name_company_fuzzy"],
                    f"jw={jw:.3f}, company={comp1}",
                ))
            elif jw >= 0.9:
                signals.append(SignalMatch(
                    "name_fuzzy_alone", SIGNAL_WEIGHTS["name_fuzzy_alone"],
                    f"jw={jw:.3f}, no corroboration",
                ))

        return signals

    # ---- Triage ----

    async def _triage_candidate(
        self, candidate: CandidatePair, stats: ResolverStats
    ) -> None:
        status = "approved" if candidate.score >= AUTO_MERGE_THRESHOLD else "pending"

        async with self._pool.acquire() as conn:
            # Check if pair already exists
            existing = await conn.fetchrow(
                "SELECT id, status FROM merge_candidate "
                "WHERE source_profile_id = $1 AND target_profile_id = $2",
                candidate.source_id, candidate.target_id,
            )
            if existing:
                if existing["status"] in ("merged", "rejected"):
                    stats.skipped += 1
                    return
                # Update score/signals if better
                await conn.execute(
                    "UPDATE merge_candidate SET "
                    "confidence_score = GREATEST(confidence_score, $2), "
                    "signals = $3, status = $4, updated_at = NOW() "
                    "WHERE id = $1",
                    existing["id"],
                    candidate.score,
                    json.dumps(candidate.signals),
                    status,
                )
            else:
                mc_id = f"mc_{uuid.uuid4()}"
                await conn.execute(
                    "INSERT INTO merge_candidate "
                    "(id, source_profile_id, target_profile_id, confidence_score, "
                    "signals, status, created_at, updated_at) "
                    "VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW())",
                    mc_id,
                    candidate.source_id,
                    candidate.target_id,
                    candidate.score,
                    json.dumps(candidate.signals),
                    status,
                )

        if status == "approved":
            from .storage import BridgeStorage

            storage = BridgeStorage.__new__(BridgeStorage)
            storage._pool = self._pool
            try:
                await storage.merge_profiles(candidate.source_id, candidate.target_id)
                stats.auto_merged += 1
            except Exception:
                log.exception(
                    "[resolver] Auto-merge failed for %s → %s",
                    candidate.source_id, candidate.target_id,
                )
                # Downgrade to pending for manual review
                async with self._pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE merge_candidate SET status = 'pending', updated_at = NOW() "
                        "WHERE source_profile_id = $1 AND target_profile_id = $2",
                        candidate.source_id, candidate.target_id,
                    )
                stats.queued_for_review += 1
        else:
            stats.queued_for_review += 1


# ---- Helper functions ----


def _canonical_pair(id1: str, id2: str) -> tuple[str, str]:
    """Return (newer_id=source, older_id=target) — newer gets merged into older."""
    return (max(id1, id2), min(id1, id2))


def _get_emails(p: ProfileData) -> set[str]:
    emails: set[str] = set()
    for e in [p.gh_email, p.email_hint]:
        if e and "@" in e:
            normalized = e.strip().lower()
            if not normalized.endswith("@users.noreply.github.com"):
                emails.add(normalized)
    return emails


def _normalize_twitter(handle: str | None) -> str | None:
    if not handle:
        return None
    cleaned = handle.strip().lower().lstrip("@")
    if cleaned.startswith("https://"):
        match = re.search(r"(?:twitter|x)\.com/(\w+)", cleaned)
        if match:
            cleaned = match.group(1)
    return cleaned if cleaned else None


def _normalize_linkedin(url: str | None) -> str | None:
    if not url:
        return None
    match = re.search(r"linkedin\.com/in/([\w-]+)", url, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    return None


def _normalize_name(p: ProfileData) -> str | None:
    """Normalize display name: lowercase, strip diacritics, collapse whitespace."""
    name = p.display_name or p.gh_name or p.hf_fullname
    if not name:
        return None
    # Strip diacritics
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(c for c in nfkd if not unicodedata.combining(c))
    cleaned = re.sub(r"\s+", " ", ascii_name.strip().lower())
    return cleaned if len(cleaned) >= 3 else None


def _normalize_location(p: ProfileData) -> str | None:
    loc = p.location or p.gh_location
    if not loc:
        return None
    return re.sub(r"\s+", " ", loc.strip().lower())


def _normalize_company(p: ProfileData) -> str | None:
    comp = p.company or p.gh_company
    if not comp:
        return None
    cleaned = comp.strip().lower().lstrip("@")
    return re.sub(r"\s+", " ", cleaned)


def _website_crossref(p1: ProfileData, p2: ProfileData) -> bool:
    """Check if one profile's website references the other's platform handle."""
    sites1 = [s for s in [p1.gh_website, p1.website, p1.hf_website] if s]
    sites2 = [s for s in [p2.gh_website, p2.website, p2.hf_website] if s]

    for site in sites1:
        site_lower = site.lower()
        if p2.huggingface_username and f"huggingface.co/{p2.huggingface_username.lower()}" in site_lower:
            return True
        if p2.github_username and f"github.com/{p2.github_username.lower()}" in site_lower:
            return True

    for site in sites2:
        site_lower = site.lower()
        if p1.huggingface_username and f"huggingface.co/{p1.huggingface_username.lower()}" in site_lower:
            return True
        if p1.github_username and f"github.com/{p1.github_username.lower()}" in site_lower:
            return True

    return False


def _gravatar_hash(p: ProfileData) -> str | None:
    """Extract Gravatar hash from avatar URL if present."""
    avatar = p.gh_avatar or p.avatar_url
    if not avatar:
        return None
    match = re.search(r"gravatar\.com/avatar/([a-f0-9]+)", avatar.lower())
    if not match:
        return None
    h = match.group(1)
    # Skip default/placeholder hashes
    if h in ("00000000000000000000000000000000", "d41d8cd98f00b204e9800998ecf8427e"):
        return None
    return h


def _jaro_winkler(s1: str, s2: str, p: float = 0.1) -> float:
    """Jaro-Winkler similarity. Pure Python, no dependencies."""
    if s1 == s2:
        return 1.0

    len1, len2 = len(s1), len(s2)
    if len1 == 0 or len2 == 0:
        return 0.0

    match_distance = max(len1, len2) // 2 - 1
    if match_distance < 0:
        match_distance = 0

    s1_matches = [False] * len1
    s2_matches = [False] * len2

    matches = 0
    transpositions = 0

    for i in range(len1):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len2)
        for j in range(start, end):
            if s2_matches[j] or s1[i] != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    k = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1

    jaro = (
        matches / len1 + matches / len2 + (matches - transpositions / 2) / matches
    ) / 3

    # Winkler modification: boost for common prefix (up to 4 chars)
    prefix = 0
    for i in range(min(4, len1, len2)):
        if s1[i] == s2[i]:
            prefix += 1
        else:
            break

    return jaro + prefix * p * (1 - jaro)
