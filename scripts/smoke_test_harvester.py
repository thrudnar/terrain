"""Smoke test — harvest 2 jobs from page 1 and 2 jobs from page 2 of a LinkedIn collection.

Usage:
    python scripts/smoke_test_harvester.py

Requires: authenticated LinkedIn session at ~/.terrain/linkedin-profile/
"""

import asyncio
import json
import logging
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PWTimeout

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROFILE_DIR = Path.home() / "Dev" / "terrain" / "linkedin-profile"
COLLECTION_URL = "https://www.linkedin.com/jobs/collections/top-applicant/"

INITIAL_LOAD_WAIT = 4.0
PAGE_DELAY = 3.0
SCROLL_PAUSE = 2.0


async def run() -> None:
    if not PROFILE_DIR.exists():
        print(f"No browser profile at {PROFILE_DIR}")
        print("Run the LinkedIn session setup first (see docs/infrastructure/09-linkedin-session.md)")
        return

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=True,
            viewport={"width": 1280, "height": 1800},
        )
        page = await ctx.new_page()

        # === Page 1 ===
        print(f"\n{'='*60}")
        print(f"Loading collection: {COLLECTION_URL}")
        print(f"{'='*60}")

        try:
            await page.goto(COLLECTION_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(INITIAL_LOAD_WAIT)
        except PWTimeout:
            print("FAIL: Timeout loading collection page")
            await ctx.close()
            return

        # Check if we're logged in
        current_url = page.url
        if "/login" in current_url or "/authwall" in current_url:
            print(f"FAIL: Redirected to login ({current_url})")
            print("LinkedIn session has expired. Refresh it on Aldhani.")
            await ctx.close()
            return

        print(f"Page loaded: {current_url}")

        # Extract job IDs from page 1
        page1_ids = await page.evaluate("""
            () => [...new Set(
                [...document.querySelectorAll('[data-occludable-job-id]')]
                .map(el => el.getAttribute('data-occludable-job-id'))
                .filter(Boolean)
            )]
        """)
        print(f"\nPage 1: found {len(page1_ids)} job IDs")

        if not page1_ids:
            print("FAIL: No job IDs found on page 1")
            print("The data-occludable-job-id selector may have changed.")
            await ctx.close()
            return

        # Take first 2 from page 1
        page1_sample = page1_ids[:2]
        print(f"Sampling first 2: {page1_sample}")

        # === Paginate to page 2 ===
        print(f"\n{'='*60}")
        print("Clicking Next button...")
        print(f"{'='*60}")

        next_btn = await page.query_selector("button.artdeco-button--icon-right")
        if not next_btn:
            print("FAIL: No Next button found")
            print("The button.artdeco-button--icon-right selector may have changed.")
            await ctx.close()
            return

        is_visible = await next_btn.is_visible()
        is_enabled = await next_btn.is_enabled()
        print(f"Next button: visible={is_visible}, enabled={is_enabled}")

        if not is_visible or not is_enabled:
            print("FAIL: Next button not clickable")
            await ctx.close()
            return

        await next_btn.click()
        await asyncio.sleep(PAGE_DELAY)

        page2_ids = await page.evaluate("""
            () => [...new Set(
                [...document.querySelectorAll('[data-occludable-job-id]')]
                .map(el => el.getAttribute('data-occludable-job-id'))
                .filter(Boolean)
            )]
        """)
        # Page 2 IDs may overlap with page 1; find new ones
        new_on_page2 = [jid for jid in page2_ids if jid not in set(page1_ids)]
        print(f"\nPage 2: found {len(page2_ids)} total IDs, {len(new_on_page2)} new")

        if not new_on_page2:
            print("WARNING: No new IDs on page 2 (all duplicates of page 1)")
            page2_sample = page2_ids[:2]
        else:
            page2_sample = new_on_page2[:2]

        print(f"Sampling first 2 new: {page2_sample}")

        # === Fetch details for all 4 jobs ===
        all_job_ids = page1_sample + page2_sample
        results = []

        for i, job_id in enumerate(all_job_ids):
            source = "page 1" if i < 2 else "page 2"
            url = f"https://www.linkedin.com/jobs/view/{job_id}/"
            print(f"\n{'='*60}")
            print(f"Fetching job {i+1}/4 ({source}): {url}")
            print(f"{'='*60}")

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(SCROLL_PAUSE)
            except PWTimeout:
                print(f"  FAIL: Timeout loading {url}")
                results.append({"job_id": job_id, "source": source, "error": "timeout"})
                continue

            async def text(selector: str) -> str | None:
                el = await page.query_selector(selector)
                return (await el.inner_text()).strip() if el else None

            title = await text("h1.t-24, h1.jobs-unified-top-card__job-title, h1")
            company = await text(
                "a.app-aware-link[href*='linkedin.com/company'], "
                ".jobs-unified-top-card__company-name a, "
                ".job-details-jobs-unified-top-card__company-name a"
            )

            location = None
            for el in await page.query_selector_all("span.tvm__text--low-emphasis"):
                t = (await el.inner_text()).strip()
                if t and t != "·":
                    location = t
                    break

            desc_el = await page.query_selector(
                ".jobs-description__content, "
                ".job-details-jobs-unified-top-card__job-description"
            )
            description = (await desc_el.inner_text()).strip() if desc_el else None

            work_type = None
            for el in await page.query_selector_all("span.tvm__text"):
                t = (await el.inner_text()).strip()
                if any(k in t.lower() for k in ["remote", "hybrid", "on-site", "onsite"]):
                    work_type = t
                    break

            result = {
                "job_id": job_id,
                "source": source,
                "title": title,
                "company": company,
                "location": location,
                "work_type": work_type,
                "description_length": len(description) if description else 0,
            }
            results.append(result)

            print(f"  Title:       {title or 'NOT FOUND'}")
            print(f"  Company:     {company or 'NOT FOUND'}")
            print(f"  Location:    {location or 'NOT FOUND'}")
            print(f"  Work type:   {work_type or 'NOT FOUND'}")
            print(f"  Description: {len(description) if description else 0} chars")

            if not title:
                print("  WARNING: Title selector failed")
            if not company:
                print("  WARNING: Company selector failed")
            if not description:
                print("  WARNING: Description selector failed")

            await asyncio.sleep(PAGE_DELAY)

        await ctx.close()

    # === Summary ===
    print(f"\n{'='*60}")
    print("SMOKE TEST SUMMARY")
    print(f"{'='*60}")

    ok = 0
    for r in results:
        if r.get("error"):
            print(f"  FAIL: {r['job_id']} ({r['source']}) — {r['error']}")
        elif not r.get("title") or not r.get("description_length"):
            print(f"  PARTIAL: {r['job_id']} ({r['source']}) — {r.get('title', '?')} @ {r.get('company', '?')} (desc: {r.get('description_length', 0)} chars)")
        else:
            print(f"  OK: {r['job_id']} ({r['source']}) — {r['title']} @ {r['company']} (desc: {r['description_length']} chars)")
            ok += 1

    print(f"\nResult: {ok}/4 jobs fully extracted")
    if ok == 4:
        print("ALL SELECTORS WORKING")
    elif ok > 0:
        print("PARTIAL — some selectors may need updating")
    else:
        print("FAIL — selectors are broken")


if __name__ == "__main__":
    asyncio.run(run())
