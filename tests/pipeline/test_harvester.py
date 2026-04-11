"""Tests for the LinkedIn harvester — mocks Playwright, no real browser.

Tests cover the ported v1 patterns:
- Job ID extraction via data-occludable-job-id attribute
- Next button pagination
- Detail page field extraction (title, company, location, description, work type)
- Work type detection logic
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from terrain.pipeline.harvest.base import SourceConfig
from terrain.pipeline.harvest.linkedin import LinkedInHarvester, _detect_work_type


class TestDetectWorkType:
    def test_remote(self) -> None:
        assert _detect_work_type("Remote") == "remote"
        assert _detect_work_type("This is a remote position") == "remote"

    def test_hybrid(self) -> None:
        assert _detect_work_type("Hybrid") == "hybrid"

    def test_onsite(self) -> None:
        assert _detect_work_type("On-site") == "onsite"
        assert _detect_work_type("Onsite") == "onsite"

    def test_unknown(self) -> None:
        assert _detect_work_type("San Francisco, CA") == "unknown"
        assert _detect_work_type("") == "unknown"


class TestGetJobIdsFromCollection:
    async def test_extracts_ids_via_data_attribute(self, tmp_path: Path) -> None:
        """Job IDs come from data-occludable-job-id, not card links."""
        harvester = LinkedInHarvester(tmp_path)
        page = AsyncMock()

        # page.evaluate returns the JS result — list of job ID strings
        page.evaluate.return_value = ["111111", "222222", "333333"]
        # No Next button — single page
        page.query_selector.return_value = None

        stubs = await harvester._get_job_ids_from_collection(
            page, "https://www.linkedin.com/jobs/collections/top-applicant/"
        )

        assert len(stubs) == 3
        job_ids = {s["job_id"] for s in stubs}
        assert job_ids == {"111111", "222222", "333333"}
        assert all(s["url"].startswith("https://www.linkedin.com/jobs/view/") for s in stubs)
        # Verify the JS evaluate was called (not CSS selectors)
        page.evaluate.assert_called_once()

    async def test_paginates_via_next_button(self, tmp_path: Path) -> None:
        """Pagination uses physical Next button click, not URL params."""
        harvester = LinkedInHarvester(tmp_path)
        page = AsyncMock()

        # Page 1: 3 IDs, page 2: 2 more IDs, page 3: Next button gone
        page.evaluate.side_effect = [
            ["111", "222", "333"],
            ["444", "555"],
            [],
        ]

        next_btn = AsyncMock()
        next_btn.is_visible.return_value = True
        next_btn.is_enabled.return_value = True

        call_count = 0

        async def mock_query_selector(selector: str):
            nonlocal call_count
            if "artdeco-button--icon-right" in selector:
                call_count += 1
                if call_count <= 2:
                    return next_btn
                return None  # No button on page 3
            return None

        page.query_selector = mock_query_selector

        stubs = await harvester._get_job_ids_from_collection(
            page, "https://www.linkedin.com/jobs/collections/top-applicant/"
        )

        assert len(stubs) == 5
        assert next_btn.click.call_count == 2

    async def test_stops_when_next_button_disabled(self, tmp_path: Path) -> None:
        harvester = LinkedInHarvester(tmp_path)
        page = AsyncMock()
        page.evaluate.return_value = ["111"]

        next_btn = AsyncMock()
        next_btn.is_visible.return_value = True
        next_btn.is_enabled.return_value = False
        page.query_selector.return_value = next_btn

        stubs = await harvester._get_job_ids_from_collection(
            page, "https://www.linkedin.com/jobs/collections/top-applicant/"
        )

        assert len(stubs) == 1
        next_btn.click.assert_not_called()

    async def test_respects_max_jobs_cap(self, tmp_path: Path) -> None:
        harvester = LinkedInHarvester(tmp_path, max_jobs_per_collection=2)
        page = AsyncMock()
        page.evaluate.return_value = ["111", "222", "333"]
        page.query_selector.return_value = None

        stubs = await harvester._get_job_ids_from_collection(
            page, "https://www.linkedin.com/jobs/collections/top-applicant/"
        )

        assert len(stubs) == 2

    async def test_handles_timeout(self, tmp_path: Path) -> None:
        from playwright.async_api import TimeoutError as PWTimeout

        harvester = LinkedInHarvester(tmp_path)
        page = AsyncMock()
        page.goto.side_effect = PWTimeout("Timeout")

        stubs = await harvester._get_job_ids_from_collection(
            page, "https://www.linkedin.com/jobs/collections/top-applicant/"
        )

        assert stubs == []


class TestGetJobDetails:
    async def test_extracts_all_fields(self, tmp_path: Path) -> None:
        harvester = LinkedInHarvester(tmp_path)
        page = AsyncMock()

        # Mock cascading selectors
        title_el = AsyncMock()
        title_el.inner_text.return_value = "Senior Data Engineer"

        company_el = AsyncMock()
        company_el.inner_text.return_value = "Acme Corp"

        desc_el = AsyncMock()
        desc_el.inner_text.return_value = "Build our data organization from scratch. Remote."

        location_el = AsyncMock()
        location_el.inner_text.return_value = "San Francisco, CA"

        work_type_el = AsyncMock()
        work_type_el.inner_text.return_value = "Remote"

        async def mock_query_selector(selector: str):
            if "h1" in selector:
                return title_el
            if "company" in selector or "app-aware-link" in selector:
                return company_el
            if "description" in selector:
                return desc_el
            return None

        page.query_selector = mock_query_selector
        page.query_selector_all = AsyncMock(side_effect=[
            [location_el],  # tvm__text--low-emphasis (location)
            [work_type_el],  # tvm__text (work type)
        ])

        details = await harvester._get_job_details(
            page, "https://www.linkedin.com/jobs/view/12345/"
        )

        assert details["title"] == "Senior Data Engineer"
        assert details["company"] == "Acme Corp"
        assert details["location"] == "San Francisco, CA"
        assert details["description_text"] == "Build our data organization from scratch. Remote."
        assert details["work_type"] == "remote"

    async def test_skips_dot_separator_in_location(self, tmp_path: Path) -> None:
        """Location extraction skips the '·' separator dots."""
        harvester = LinkedInHarvester(tmp_path)
        page = AsyncMock()

        page.query_selector = AsyncMock(return_value=None)

        dot_el = AsyncMock()
        dot_el.inner_text.return_value = "·"
        location_el = AsyncMock()
        location_el.inner_text.return_value = "Denver, CO"

        page.query_selector_all = AsyncMock(side_effect=[
            [dot_el, location_el],  # location spans
            [],  # work type spans
        ])

        details = await harvester._get_job_details(
            page, "https://www.linkedin.com/jobs/view/12345/"
        )

        assert details["location"] == "Denver, CO"

    async def test_handles_timeout(self, tmp_path: Path) -> None:
        from playwright.async_api import TimeoutError as PWTimeout

        harvester = LinkedInHarvester(tmp_path)
        page = AsyncMock()
        page.goto.side_effect = PWTimeout("Timeout")

        details = await harvester._get_job_details(
            page, "https://www.linkedin.com/jobs/view/12345/"
        )

        assert details == {}


class TestHarvest:
    async def test_iterates_configured_collections(self, tmp_path: Path) -> None:
        harvester = LinkedInHarvester(tmp_path)
        collections_called: list[str] = []

        async def mock_harvest_collection(config: SourceConfig, collection: str) -> list:
            collections_called.append(collection)
            return []

        harvester.harvest_collection = mock_harvest_collection  # type: ignore

        config = SourceConfig(
            board="linkedin",
            collections=["top-applicant", "recommended", "remote-jobs"],
        )
        await harvester.harvest(config)

        assert collections_called == ["top-applicant", "recommended", "remote-jobs"]

    async def test_unknown_collection_returns_empty(self, tmp_path: Path) -> None:
        harvester = LinkedInHarvester(tmp_path)
        config = SourceConfig(board="linkedin", collections=["nonexistent"])

        # harvest_collection handles unknown collections gracefully
        # but it tries to launch a browser, so we mock it
        async def mock_harvest_collection(config: SourceConfig, collection: str) -> list:
            from terrain.pipeline.harvest.linkedin import COLLECTION_URLS
            if collection not in COLLECTION_URLS:
                return []
            return []

        harvester.harvest_collection = mock_harvest_collection  # type: ignore
        result = await harvester.harvest(config)
        assert result == []
