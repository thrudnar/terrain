"""Tests for the SQLite migration script — uses synthetic fixture data."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.migrate_sqlite import build_opportunities, read_sqlite, validate


def _create_test_db(db_path: Path) -> None:
    """Create a minimal v1 SQLite database with test data."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY,
            job_board TEXT,
            job_id TEXT,
            collection TEXT,
            url TEXT,
            company TEXT,
            title TEXT,
            location TEXT,
            description TEXT,
            posted_date TEXT,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE job_scores (
            id INTEGER PRIMARY KEY,
            job_board TEXT,
            job_id TEXT,
            overall_score INTEGER,
            skills_score INTEGER,
            seniority_score INTEGER,
            work_type_score INTEGER,
            work_arrangement TEXT,
            salary_range TEXT,
            match_summary TEXT,
            strengths TEXT,
            gaps TEXT,
            recommendation TEXT,
            reasoning TEXT,
            prompt_version TEXT,
            model TEXT,
            scored_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE applications (
            id INTEGER PRIMARY KEY,
            job_board TEXT,
            job_id TEXT,
            applied_date TEXT,
            cover_letter TEXT,
            cover_letter_prompt_version TEXT,
            cover_letter_model TEXT,
            cover_letter_generated_at TEXT,
            skill_used TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE interesting_companies (
            id INTEGER PRIMARY KEY,
            company_name TEXT,
            notes TEXT
        )
    """)

    # Insert test data
    conn.execute("""
        INSERT INTO jobs (job_board, job_id, collection, url, company, title, location, description, created_at)
        VALUES ('linkedin', '111', 'top-applicant', 'https://linkedin.com/jobs/view/111',
                'Acme Corp', 'Senior Data Engineer', 'Remote', 'Build our data org from scratch.', '2026-04-01 00:00:00')
    """)
    conn.execute("""
        INSERT INTO jobs (job_board, job_id, collection, url, company, title, location, description, created_at)
        VALUES ('linkedin', '222', 'recommended', 'https://linkedin.com/jobs/view/222',
                'Beta Inc', 'Analytics Manager', 'San Francisco', 'Lead analytics team.', '2026-04-02 00:00:00')
    """)

    conn.execute("""
        INSERT INTO job_scores (job_board, job_id, overall_score, skills_score, seniority_score, work_type_score,
                               work_arrangement, match_summary, strengths, gaps, recommendation, reasoning,
                               prompt_version, model, scored_at)
        VALUES ('linkedin', '111', 85, 85, 90, 90, 'Remote',
                'Strong match.', 'org-building | data platform', 'unfamiliar domain',
                'STRONG FIT', 'Clean fit.', 'v1', 'claude-sonnet-4-6', '2026-04-01 12:00:00')
    """)

    conn.execute("""
        INSERT INTO applications (job_board, job_id, applied_date, cover_letter,
                                 cover_letter_prompt_version, cover_letter_model, cover_letter_generated_at)
        VALUES ('linkedin', '111', '2026-04-02', 'The opportunity to build...',
                'v1', 'claude-sonnet-4-6', '2026-04-02 00:00:00')
    """)

    conn.execute("""
        INSERT INTO interesting_companies (company_name, notes)
        VALUES ('Acme Corp', 'Great culture, strong data team')
    """)

    conn.commit()
    conn.close()


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    _create_test_db(db_path)
    return db_path


class TestReadSqlite:
    def test_reads_all_tables(self, test_db: Path) -> None:
        tables = read_sqlite(test_db)
        assert len(tables["jobs"]) == 2
        assert len(tables["job_scores"]) == 1
        assert len(tables["applications"]) == 1
        assert len(tables["interesting_companies"]) == 1

    def test_handles_missing_table(self, tmp_path: Path) -> None:
        db_path = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY)")
        conn.close()

        tables = read_sqlite(db_path)
        assert len(tables["jobs"]) == 0
        assert len(tables["job_scores"]) == 0


class TestBuildOpportunities:
    def test_builds_from_jobs(self, test_db: Path) -> None:
        tables = read_sqlite(test_db)
        opps = build_opportunities(tables)

        assert len(opps) == 2

    def test_attaches_scoring(self, test_db: Path) -> None:
        tables = read_sqlite(test_db)
        opps = build_opportunities(tables)

        scored_opp = next(o for o in opps if o.source.board_job_id == "111")
        assert scored_opp.scoring is not None
        assert scored_opp.scoring.overall == 85
        assert scored_opp.scoring.strengths == ["org-building", "data platform"]

    def test_attaches_application_and_cover_letter(self, test_db: Path) -> None:
        tables = read_sqlite(test_db)
        opps = build_opportunities(tables)

        applied_opp = next(o for o in opps if o.source.board_job_id == "111")
        assert applied_opp.application is not None
        assert applied_opp.cover_letter is not None
        assert "opportunity" in applied_opp.cover_letter.content.lower()

    def test_unscored_stays_harvested(self, test_db: Path) -> None:
        tables = read_sqlite(test_db)
        opps = build_opportunities(tables)

        unscored = next(o for o in opps if o.source.board_job_id == "222")
        assert unscored.scoring is None
        assert unscored.pipeline_state.value == "harvested"

    def test_pipe_delimited_strengths(self, test_db: Path) -> None:
        tables = read_sqlite(test_db)
        opps = build_opportunities(tables)

        scored = next(o for o in opps if o.scoring is not None)
        assert scored.scoring.strengths == ["org-building", "data platform"]
        assert scored.scoring.gaps == ["unfamiliar domain"]


class TestValidate:
    def test_passes_on_match(self, test_db: Path) -> None:
        tables = read_sqlite(test_db)
        counts = {"opportunities": 2, "interesting_companies": 1}
        warnings = validate(tables, counts)
        assert warnings == []

    def test_warns_on_mismatch(self, test_db: Path) -> None:
        tables = read_sqlite(test_db)
        counts = {"opportunities": 1, "interesting_companies": 1}
        warnings = validate(tables, counts)
        assert len(warnings) == 1
        assert "mismatch" in warnings[0].lower()
