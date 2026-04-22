"""Link rewriting for email click tracking."""

import re
import uuid


def rewrite_links(
    html: str, tracking_id: str, base_url: str
) -> tuple[str, dict[str, str]]:
    """Rewrite all <a href="..."> links to pass through the click tracker.

    Args:
        html: The email body HTML.
        tracking_id: Unique tracking identifier for this message.
        base_url: Base URL for the tracking server.

    Returns:
        Tuple of (modified HTML, link_map) where link_map maps
        link_id -> original_url for later resolution.
    """
    link_map: dict[str, str] = {}
    base = base_url.rstrip("/")

    def _replace_href(match: re.Match) -> str:
        original_url = match.group(1)

        # Skip mailto:, tel:, and anchor links
        if original_url.startswith(("mailto:", "tel:", "#", "{{")):
            return match.group(0)

        # Skip tracking/unsubscribe URLs (avoid double-rewriting)
        if "/t/" in original_url or "/c/" in original_url or "/unsub/" in original_url:
            return match.group(0)

        link_id = uuid.uuid4().hex[:12]
        link_map[link_id] = original_url
        tracked_url = f"{base}/c/{tracking_id}/{link_id}"
        return f'href="{tracked_url}"'

    pattern = r'href="([^"]+)"'
    rewritten = re.sub(pattern, _replace_href, html, flags=re.IGNORECASE)

    return rewritten, link_map
