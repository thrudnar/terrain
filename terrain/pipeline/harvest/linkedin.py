"""LinkedIn harvester — scrapes job listings using Playwright with persistent session.

Ported from v1 harvester (Job Listing Harvester/harvester/harvest.py).
Key patterns preserved:
- Job IDs extracted via data-occludable-job-id DOM attribute (reliable)
- Pagination via physical "Next" button, not URL params or infinite scroll
- Timing: 4s initial load, 2s scroll pause, 3s page delay (tuned for rate limiting)
- Detail page selectors: cascading fallbacks for title, company, location, description
"""

import asyncio
import logging
import re
from pathlib import Path
from typing import Optional

from playwright.async_api import Page, async_playwright, TimeoutError as PWTimeout

from terrain.pipeline.harvest.base import HarvestSource, RawOpportunity, SourceConfig

logger = logging.getLogger(__name__)

# Timing constants (tuned to avoid LinkedIn rate limiting)
INITIAL_LOAD_WAIT = 4.0
SCROLL_PAUSE = 2.0
PAGE_DELAY = 3.0
MAX_JOBS_PER_COLLECTION = 100

COLLECTION_URLS = {
    "top-applicant": "https://www.linkedin.com/jobs/collections/top-applicant/",
    "recommended": "https://www.linkedin.com/jobs/collections/recommended/",
    "remote-jobs": "https://www.linkedin.com/jobs/collections/remote-jobs/",
}


def _detect_work_type(text: str) -> str:
    """Detect work arrangement from text content."""
    t = (text or "").lower()
    if "remote" in t:
        return "remote"
    if "hybrid" in t:
        return "hybrid"
    if "on-site" in t or "onsite" in t:
        return "onsite"
    return "unknown"


class LinkedInHarvester:
    """Scrapes LinkedIn job collections using a persistent browser profile.

    Uses the data-occludable-job-id attribute to extract job IDs (reliable),
    then navigates to each job detail page to extract structured fields.
    """

    def __init__(
        self,
        profile_dir: Path,
        max_jobs_per_collection: int = MAX_JOBS_PER_COLLECTION,
    ) -> None:
        self._profile_dir = profile_dir
        self._max_jobs = max_jobs_per_collection

    async def _get_job_ids_from_collection(
        self, page: Page, url: str
    ) -> list[dict[str, str]]:
        """Load a collection page and paginate via Next button to collect job IDs."""
        logger.info("Loading collection: %s", url)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(INITIAL_LOAD_WAIT)
        except PWTimeout:
            logger.warning("Timeout loading %s — skipping", url)
            return []

        seen_ids: set[str] = set()
        page_num = 1

        while True:
            # Extract job IDs via the reliable data-occludable-job-id attribute
            current_ids = await page.evaluate("""
                () => [...new Set(
                    [...document.querySelectorAll('[data-occludable-job-id]')]
                    .map(el => el.getAttribute('data-occludable-job-id'))
                    .filter(Boolean)
                )]
            """)
            seen_ids.update(current_ids)
            logger.info(
                "Page %d: %d IDs (%d total)", page_num, len(current_ids), len(seen_ids)
            )

            if len(seen_ids) >= self._max_jobs:
                logger.info("Reached cap of %d", self._max_jobs)
                break

            # Paginate via physical Next button (not URL params or infinite scroll)
            next_btn = await page.query_selector("button.artdeco-button--icon-right")
            if not next_btn:
                logger.info("No Next button — end of list")
                break
            if not await next_btn.is_visible() or not await next_btn.is_enabled():
                logger.info("Next button disabled — end of list")
                break

            await next_btn.click()
            await asyncio.sleep(PAGE_DELAY)
            page_num += 1

        result_ids = list(seen_ids)[: self._max_jobs]
        logger.info("Collected %d job IDs across %d page(s)", len(result_ids), page_num)

        return [
            {
                "job_id": jid,
                "url": f"https://www.linkedin.com/jobs/view/{jid}/",
            }
            for jid in result_ids
        ]

    async def _get_job_details(self, page: Page, job_url: str) -> dict[str, Optional[str]]:
        """Fetch a job detail page and extract structured fields."""
        try:
            await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(SCROLL_PAUSE)
        except PWTimeout:
            logger.warning("Timeout on %s", job_url)
            return {}

        async def text(selector: str) -> Optional[str]:
            el = await page.query_selector(selector)
            return (await el.inner_text()).strip() if el else None

        # Title — cascading selectors
        title = await text(
            "h1.t-24, h1.jobs-unified-top-card__job-title, h1"
        )

        # Company — cascading selectors
        company = await text(
            "a.app-aware-link[href*='linkedin.com/company'], "
            ".jobs-unified-top-card__company-name a, "
            ".job-details-jobs-unified-top-card__company-name a"
        )

        # Location — first tvm__text--low-emphasis that isn't a separator dot
        location = None
        for el in await page.query_selector_all("span.tvm__text--low-emphasis"):
            t = (await el.inner_text()).strip()
            if t and t != "·":
                location = t
                break

        # Description
        description = await text(
            ".jobs-description__content, "
            ".job-details-jobs-unified-top-card__job-description"
        )

        # Work type — check tvm__text spans first, fall back to description
        work_type_raw = ""
        for el in await page.query_selector_all("span.tvm__text"):
            t = (await el.inner_text()).strip()
            if any(k in t.lower() for k in ["remote", "hybrid", "on-site", "onsite"]):
                work_type_raw = t
                break
        work_type = _detect_work_type(work_type_raw or description or "")

        return {
            "title": title,
            "company": company,
            "location": location,
            "work_type": work_type,
            "description_text": description,
        }

    async def harvest_collection(
        self, config: SourceConfig, collection: str
    ) -> list[RawOpportunity]:
        """Scrape a single LinkedIn job collection."""
        base_url = COLLECTION_URLS.get(collection)
        if not base_url:
            logger.warning("Unknown collection: %s", collection)
            return []

        opportunities: list[RawOpportunity] = []

        async with async_playwright() as p:
            ctx = await p.chromium.launch_persistent_context(
                str(self._profile_dir),
                headless=True,
                viewport={"width": 1280, "height": 1800},
            )
            page = await ctx.new_page()

            # Collect job IDs from collection pages
            job_stubs = await self._get_job_ids_from_collection(page, base_url)

            # Fetch details for each job
            for stub in job_stubs:
                logger.info("Fetching: %s", stub["url"])
                details = await self._get_job_details(page, stub["url"])
                await asyncio.sleep(PAGE_DELAY)

                if not details.get("description_text"):
                    logger.warning("No description for %s — skipping", stub["job_id"])
                    continue

                opp = RawOpportunity(
                    board="linkedin",
                    board_job_id=stub["job_id"],
                    collection=collection,
                    url=stub["url"],
                    company=details.get("company") or "Unknown",
                    title=details.get("title") or "Unknown",
                    location=details.get("location"),
                    work_type=details.get("work_type"),
                    description_text=details["description_text"],
                )
                opportunities.append(opp)

            await ctx.close()

        logger.info("Harvested %d jobs from %s", len(opportunities), collection)
        return opportunities

    async def harvest(self, config: SourceConfig) -> list[RawOpportunity]:
        """Scrape all configured LinkedIn collections."""
        all_opportunities: list[RawOpportunity] = []
        for collection in config.collections:
            opps = await self.harvest_collection(config, collection)
            all_opportunities.extend(opps)
        return all_opportunities
