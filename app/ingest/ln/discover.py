"""LinkedIn URL discovery: extract URLs from GH/HF data."""
from __future__ import annotations

import logging

from app.ingest.bridge.storage import BridgeStorage
from app.ingest.ln.storage import LNStorage

log = logging.getLogger(__name__)


async def discover_linkedin_urls(
    bridge_storage: BridgeStorage,
    ln_storage: LNStorage,
) -> int:
    """Extract LinkedIn URLs from GH/HF data and populate ln_pending_urls.

    Returns count of URLs discovered.
    """
    urls = await bridge_storage.extract_linkedin_urls()
    if not urls:
        log.info("No LinkedIn URLs discovered")
        return 0

    count = await ln_storage.upsert_pending_urls(urls)
    log.info("Discovered %d LinkedIn URLs", count)
    return count
