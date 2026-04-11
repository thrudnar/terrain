"""Migration script — reads v1 SQLite database and writes to MongoDB.

Usage:
    python scripts/migrate_sqlite.py /path/to/v1/database.db

The script connects to MongoDB using the MONGO_URI environment variable
or the .anthropic_api_key file fallback pattern from Settings.
"""

import argparse
import asyncio
import hashlib
import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient

from terrain.config.settings import get_settings
from terrain.models.opportunity import (
    Application,
    ApplicationSource,
    ApplicationStatus,
    CoverLetter,
    GenerationMethod,
    Opportunity,
    PipelineState,
    Recommendation,
    ScoringResult,
    Source,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CANDIDATE_ID = "candidate_1"


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse a datetime string from SQLite, handling multiple formats."""
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _safe_recommendation(value: str | None) -> Recommendation:
    """Map legacy recommendation string to enum, with fallback."""
    if not value:
        return Recommendation.SKIP
    mapping = {
        "STRONG FIT": Recommendation.STRONG_FIT,
        "GOOD FIT": Recommendation.GOOD_FIT,
        "MARGINAL FIT": Recommendation.MARGINAL_FIT,
        "SKIP": Recommendation.SKIP,
    }
    return mapping.get(value.upper().strip(), Recommendation.SKIP)


def read_sqlite(db_path: Path) -> dict[str, list[dict]]:
    """Read all relevant tables from the v1 SQLite database."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    tables: dict[str, list[dict]] = {}

    for table_name in ["jobs", "job_scores", "applications", "interesting_companies"]:
        try:
            cursor = conn.execute(f"SELECT * FROM {table_name}")  # noqa: S608
            tables[table_name] = [dict(row) for row in cursor.fetchall()]
            logger.info("Read %d rows from %s", len(tables[table_name]), table_name)
        except sqlite3.OperationalError:
            logger.warning("Table %s not found, skipping", table_name)
            tables[table_name] = []

    conn.close()
    return tables


def build_opportunities(tables: dict[str, list[dict]]) -> list[Opportunity]:
    """Build Opportunity documents from SQLite rows."""
    # Index scores and applications by job key
    scores_by_key: dict[str, dict] = {}
    for score in tables.get("job_scores", []):
        key = f"{score.get('job_board', 'linkedin')}:{score.get('job_id', '')}"
        scores_by_key[key] = score

    apps_by_key: dict[str, dict] = {}
    for app in tables.get("applications", []):
        key = f"{app.get('job_board', 'linkedin')}:{app.get('job_id', '')}"
        apps_by_key[key] = app

    opportunities: list[Opportunity] = []

    for job in tables.get("jobs", []):
        board = job.get("job_board", "linkedin")
        job_id = str(job.get("job_id", ""))
        key = f"{board}:{job_id}"

        now = datetime.now(timezone.utc)
        created = _parse_datetime(job.get("created_at")) or now
        desc = job.get("description", "") or ""

        opp = Opportunity(
            candidate_id=CANDIDATE_ID,
            source=Source(
                board=board,
                board_job_id=job_id,
                collection=job.get("collection", "unknown"),
                url=job.get("url", f"https://linkedin.com/jobs/view/{job_id}"),
                first_seen=created,
                last_seen=created,
                posted_date=_parse_datetime(job.get("posted_date")),
            ),
            company=job.get("company", "Unknown"),
            title=job.get("title", "Unknown"),
            location=job.get("location"),
            description_text=desc,
            description_hash=f"sha256:{hashlib.sha256(desc.encode()).hexdigest()[:16]}",
            pipeline_state=PipelineState.HARVESTED,
            created_at=created,
            updated_at=now,
        )

        # Attach scoring if exists
        score = scores_by_key.get(key)
        if score:
            try:
                strengths_raw = score.get("strengths", "")
                gaps_raw = score.get("gaps", "")
                strengths = [s.strip() for s in strengths_raw.split("|") if s.strip()] if strengths_raw else []
                gaps = [g.strip() for g in gaps_raw.split("|") if g.strip()] if gaps_raw else []

                opp.scoring = ScoringResult(
                    prompt_version=score.get("prompt_version", "v1"),
                    model=score.get("model", "unknown"),
                    overall=int(score.get("overall_score", 0)),
                    skills=int(score.get("skills_score", 0)),
                    seniority=int(score.get("seniority_score", 0)),
                    work_type=int(score.get("work_type_score", 0)),
                    work_arrangement=score.get("work_arrangement"),
                    salary_range=score.get("salary_range"),
                    match_summary=score.get("match_summary", ""),
                    strengths=strengths,
                    gaps=gaps,
                    recommendation=_safe_recommendation(score.get("recommendation")),
                    reasoning=score.get("reasoning", ""),
                    scored_at=_parse_datetime(score.get("scored_at")) or now,
                )
                opp.pipeline_state = PipelineState.SCORED
            except Exception as e:
                logger.warning("Failed to parse score for %s: %s", key, e)

        # Attach application if exists
        app = apps_by_key.get(key)
        if app:
            opp.application = Application(
                status=ApplicationStatus.APPLIED,
                applied_date=_parse_datetime(app.get("applied_date")),
                source=ApplicationSource.HARVESTED,
            )
            opp.pipeline_state = PipelineState.APPLIED

            cover_content = app.get("cover_letter", "")
            if cover_content:
                opp.cover_letter = CoverLetter(
                    prompt_version=app.get("cover_letter_prompt_version", "v1"),
                    model=app.get("cover_letter_model", "unknown"),
                    content=cover_content,
                    generated_at=_parse_datetime(app.get("cover_letter_generated_at")) or now,
                    skill_used=app.get("skill_used"),
                    generation_method=GenerationMethod.REALTIME,
                )

        opportunities.append(opp)

    return opportunities


async def write_to_mongo(
    mongo_uri: str,
    opportunities: list[Opportunity],
    interesting_companies: list[dict],
) -> dict[str, int]:
    """Write migrated data to MongoDB. Returns counts."""
    client = AsyncIOMotorClient(mongo_uri)
    db = client.get_default_database()

    # Write opportunities
    opp_collection = db["opportunities"]
    if opportunities:
        docs = [opp.model_dump(by_alias=True, exclude={"id"}) for opp in opportunities]
        result = await opp_collection.insert_many(docs)
        opp_count = len(result.inserted_ids)
    else:
        opp_count = 0

    # Write interesting companies
    ic_collection = db["interesting_companies"]
    ic_count = 0
    for ic in interesting_companies:
        doc = {
            "candidate_id": CANDIDATE_ID,
            "company_name": ic.get("company_name", ic.get("company", "")),
            "interest_drivers": [],
            "apprehensions": [],
            "notes": ic.get("notes", ""),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        await ic_collection.insert_one(doc)
        ic_count += 1

    # Seed candidate document
    cand_collection = db["candidates"]
    existing = await cand_collection.find_one({"candidate_id": CANDIDATE_ID})
    if not existing:
        await cand_collection.insert_one({
            "candidate_id": CANDIDATE_ID,
            "name": "Candidate Name",
            "active_prompts": {"scoring": "v1", "cover_letter": "v1", "dedup": "v1"},
            "prompt_history": [],
            "schedules": {},
            "ai_routing": None,
        })

    client.close()

    return {
        "opportunities": opp_count,
        "interesting_companies": ic_count,
    }


def validate(tables: dict[str, list[dict]], counts: dict[str, int]) -> list[str]:
    """Validate migration results. Returns list of warnings."""
    warnings = []

    job_count = len(tables.get("jobs", []))
    if counts["opportunities"] != job_count:
        warnings.append(
            f"Job count mismatch: {job_count} in SQLite, {counts['opportunities']} in MongoDB"
        )

    ic_count = len(tables.get("interesting_companies", []))
    if counts["interesting_companies"] != ic_count:
        warnings.append(
            f"Interesting company count mismatch: {ic_count} in SQLite, "
            f"{counts['interesting_companies']} in MongoDB"
        )

    return warnings


async def main(db_path: Path) -> None:
    settings = get_settings()
    logger.info("Reading SQLite from %s", db_path)
    tables = read_sqlite(db_path)

    logger.info("Building opportunity documents...")
    opportunities = build_opportunities(tables)
    logger.info("Built %d opportunities", len(opportunities))

    scored = sum(1 for o in opportunities if o.scoring is not None)
    applied = sum(1 for o in opportunities if o.application is not None)
    with_cl = sum(1 for o in opportunities if o.cover_letter is not None)
    logger.info("  Scored: %d, Applied: %d, With cover letter: %d", scored, applied, with_cl)

    logger.info("Writing to MongoDB at %s", settings.mongo_uri)
    counts = await write_to_mongo(
        settings.mongo_uri,
        opportunities,
        tables.get("interesting_companies", []),
    )

    warnings = validate(tables, counts)
    if warnings:
        for w in warnings:
            logger.warning("VALIDATION: %s", w)
    else:
        logger.info("Validation passed — all counts match")

    logger.info("Migration complete: %s", counts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate v1 SQLite to MongoDB")
    parser.add_argument("db_path", type=Path, help="Path to the v1 SQLite database")
    args = parser.parse_args()

    if not args.db_path.exists():
        print(f"Error: {args.db_path} does not exist")
        sys.exit(1)

    asyncio.run(main(args.db_path))
