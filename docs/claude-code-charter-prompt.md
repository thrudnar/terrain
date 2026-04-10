# Project Charter: terrAIn — Job Hunting Pipeline Re-Architecture

## What You're Building

**terrAIn** — a production-quality job hunting pipeline that automatically harvests job listings from multiple sources, scores them against a candidate's profile, and generates cover letters for strong matches. The system replaces a working but monolithic v1 prototype (SQLite, vanilla JS, scripts) with a properly architected application: MongoDB document store, clean service boundaries, dual AI providers (Anthropic API + local Ollama), scheduled pipeline automation, and a React frontend.

This application is built for a single candidate today but architecturally supports multiple candidates — each with their own sources, prompts, scoring criteria, and pipeline configuration.

## Context: What Came Before

There is a working v1 of this system at a separate path on the owner's machine. You do not need to modify or reference that code directly, but you should know what it does so you understand the requirements:

- **Harvester:** Playwright-based LinkedIn scraper that extracts job listings from collection pages and stores full descriptions. Currently scrapes 3 collections (top-applicant, recommended, remote-jobs) with pagination support. ~260 jobs harvested.
- **Scorer:** Calls Claude Haiku with a detailed system prompt (full career history, scoring dimensions, calibration anchors) to evaluate each job on a 0–100 scale across skills, seniority, work type, and overall fit. Produces structured JSON with scores, narrative summary, strengths/gaps, and a recommendation label (STRONG FIT / GOOD FIT / MARGINAL FIT / SKIP).
- **Application Workflow:** Starring a high-scoring job creates an application record and triggers async cover letter generation via Claude Sonnet with the voice-of-tim skill (Anthropic skills beta API).
- **UI:** FastAPI backend + 49KB vanilla JS single-page app. Views for jobs, scores, applications with filters, modals, inline editing.
- **Database:** SQLite with separate tables for jobs, job_scores, applications, score_prompts, cover_letter_prompts, interesting_companies.

The v1 system works but has no service boundaries, no scheduling, no batch processing, no deduplication, and a monolithic frontend. This re-arch addresses all of those.

---

## Architecture Overview

Read the full design document at `docs/design-recommendations.md` (included in this repo). What follows is the operational summary you need to build.

### Core Design Principle

**Every major component communicates through an explicitly defined interface (Python protocol or ABC).** This is a hard constraint. No module should directly import another module's internals or an external SDK. The interfaces serve three purposes simultaneously: independent development (parallel Claude Code sessions), testability (mock boundaries), and swappability (provider changes don't touch business logic). If you find yourself importing `pymongo` or `anthropic` outside the `providers/` package, that's a design violation.

### Data Model

MongoDB, single database called `terrain`. Core collections:

**`opportunities`** — one document per job opportunity per candidate. Starts lean at harvest, accumulates subdocuments as it progresses:
- Root fields: `candidate_id`, `company`, `title`, `location`, `work_type`, `description_text`, `description_hash`, `pipeline_state`, `archived`, timestamps
- `source`: board, board_job_id, collection, url, first_seen, last_seen, posted_date
- `dedup`: status (unique/duplicate/repost_unchanged/repost_evolved), parent_id, method, similarity_score
- `scoring`: prompt_version, model, overall/skills/seniority/work_type scores, work_arrangement, salary_range, match_summary, strengths[], gaps[], recommendation, reasoning
- `application`: status (new/applied/waiting/phone_screen/interview/offer/rejected/withdrawn/dead), applied_date, application_link, contact, resume_version, source
- `cover_letter`: prompt_version, model, content, generated_at, skill_used, generation_method
- `notes`: freeform markdown string
- `gmail_events`: array of {gmail_message_id, subject, received_at, characterization} — plumbing only, no Gmail integration built
- `errors`: array of {stage, occurred_at, run_id, error_type, message, retryable, resolved_at}
- `interesting_company_match`: boolean

Key indexes: `{candidate_id: 1, pipeline_state: 1}`, `{candidate_id: 1, company: 1, title: 1}` (dedup), `{candidate_id: 1, scoring.overall: -1}`, `{candidate_id: 1, source.board: 1, source.board_job_id: 1}` (unique)

**`candidates`** — profile and configuration per candidate:
- `candidate_id`, `name`
- `active_prompts`: {scoring: "v2", cover_letter: "v1", dedup: "v1"}
- `prompt_history`: array of activation/deactivation records
- `schedules`: {harvest_linkedin: "0 8,20 * * *", score_batch: "0 10,22 * * *", ...}
- `ai_routing`: per-task provider+model config
- `promotion_threshold`: {min_score: 75, interesting_company_boost: true}

**`interesting_companies`** — per candidate, rich fields: name, description, interest_drivers, apprehensions, interest_level, size, round, sector, culture, purpose_impact, evilness, tech_centric, up_or_out, why, who_i_know, careers_url

**`pipeline_runs`** — one document per pipeline execution: candidate_id, stage, source, started_at, completed_at, trigger (scheduled/manual), items_processed, items_new, items_duplicate, items_error, prompt_version, batch_id, cost_usd, error_log[], status (running/completed/failed)

**`api_usage`** — one document per AI call: provider, model, task, candidate_id, input_tokens, output_tokens, cached_tokens, cost_usd, pipeline_run_id, timestamp

### Prompt Management

Prompts are versioned markdown files in the repo:

```
prompts/
  candidate_1/
    scoring/
      v1.md
      v2.md
    cover-letter/
      v1.md
    dedup/
      v1.md
```

Each file contains the full prompt text (system prompt + user prompt template). Template variables use `{placeholders}`. The `candidates` collection tracks which version is active. Every opportunity document stamps the prompt version used to generate its scores and cover letter. This enables A/B comparison: run two versions against the same jobs, filter results by version in the UI.

Prompt files are the source of truth for content. MongoDB is the source of truth for activation metadata.

### Pipeline Stages

Five stages, each implementing:

```python
class PipelineStage(Protocol):
    async def run(self, candidate_id: str, options: dict) -> StageResult: ...
    async def run_one(self, candidate_id: str, opportunity_id: str) -> StageResult: ...
```

1. **Harvest** — scrapes job sources, creates opportunity documents with `pipeline_state: "harvested"`. Multi-source via adapter interface:
   ```python
   class HarvestSource(Protocol):
       async def harvest(self, config: SourceConfig) -> list[RawOpportunity]: ...
   ```
   Build LinkedIn adapter (port from v1 Playwright logic). Create stubs for Jobright and BuiltIn. Capture `posted_date` from job cards where available. Implement smarter harvest cap: paginate until N new jobs posted within last 3 weeks, not a blunt count.

2. **Dedup** (inline, runs immediately after harvest) — two paths:
   - **Fast path:** Exact match on `(candidate_id, company, title)` → DB lookup only
   - **Similarity path:** When company+title collision found, send both descriptions to AI provider (Ollama/Llama by default) for similarity assessment. Three-way classification: duplicate (high similarity + short time gap), repost_unchanged (high similarity + long time gap), repost_evolved (low similarity). Keeper selection priority: has applied application > has any application > already scored > better location score > earliest harvested. Cross-board aware.
   
   Must be its own module so dedup rules can evolve independently. Strip description boilerplate before comparison.

3. **Score** — evaluates opportunities against candidate profile:
   - **Scheduled:** Anthropic Batch API. Collect unscored opportunities, submit batch, poll for completion. System prompt gets `cache_control` for caching across the batch.
   - **One-off:** Messages API for single urgent opportunity.
   - Writes to `scoring` subdocument, stamps `prompt_version`, advances `pipeline_state` to `"scored"`.

4. **Promote** — rules-based threshold evaluation. Default: `scoring.overall >= candidate.promotion_threshold.min_score`. Optional `interesting_company_match` boost. Creates `application` subdocument with `status: "new"`.

5. **Cover Letter** — generates cover letters for promoted opportunities:
   - **Scheduled:** Anthropic Batch API for all promoted opportunities awaiting cover letters.
   - **One-off:** Messages API with voice-of-tim skill for urgent requests.
   - Fallback: if skills beta unavailable, standard API call without skill. Log which method was used.
   - Writes to `cover_letter` subdocument, stamps `prompt_version` and `skill_used`.

**Scheduler:** APScheduler, in-process. Loads cron schedules from `candidates` collection. Each run creates a `pipeline_runs` document. Pipeline dashboard reads this collection.

### AI Provider Abstraction

```python
class AIProvider(Protocol):
    async def complete(self, request: CompletionRequest) -> CompletionResponse: ...
    async def complete_batch(self, requests: list[CompletionRequest]) -> BatchHandle: ...
    async def poll_batch(self, handle: BatchHandle) -> BatchResult: ...
```

Two adapters:

**AnthropicAdapter** — Messages API (real-time), Batch API (bulk), skills beta (voice-of-tim), prompt caching. Centralized retry logic (exponential backoff on rate limits), usage logging to `api_usage` collection.

**OllamaAdapter** — wraps Ollama's OpenAI-compatible API at `http://localhost:11434`. Used for dedup similarity, field extraction, email classification. No batch mode (local inference is fast and free). `complete_batch` can iterate sequentially.

Routing is configured per-task in the candidate profile. Changing a task from Ollama to Anthropic (or vice versa) is a config change, not a code change.

Every AI call (both providers) logs to `api_usage`: provider, model, task, tokens, cost, run_id, timestamp.

### Database Abstraction

Repository pattern. Business logic never imports `pymongo`:

```python
class OpportunityRepository(Protocol):
    async def create(self, opportunity: Opportunity) -> str: ...
    async def find_unscored(self, candidate_id: str) -> list[Opportunity]: ...
    async def find_by_company_title(self, candidate_id: str, company: str, title: str) -> list[Opportunity]: ...
    async def update_scoring(self, opp_id: str, scoring: ScoringResult) -> None: ...
    async def update_application(self, opp_id: str, application: ApplicationUpdate) -> None: ...
    async def find_for_ui(self, candidate_id: str, filters: OpportunityFilters) -> list[Opportunity]: ...
    async def aggregate_by_pipeline_state(self, candidate_id: str) -> dict[str, int]: ...
    # ... etc
```

Similar repositories for Candidate, PipelineRun, ApiUsage, InterestingCompany.

Single `DatabaseClient` class owns the connection pool, provides repository instances. Connection URI from environment variable.

### Frontend

React 18+ with TypeScript. Stack: Tailwind CSS, Recharts (charts), React Router, Tanstack Query (data fetching).

**Two primary views:**

1. **Pipeline Dashboard** — harvest/scoring/cover-letter monitors (last run, items processed, errors, next scheduled), schedule overview with enable/disable, match distribution chart, cost summary by task type with trends, stage inventory counts (how many opportunities in each pipeline_state).

2. **Application Management** — opportunity list with filters (pipeline_state, recommendation tier, work_arrangement, company, date range), opportunity detail (job description, match assessment, cover letter editable/regenerable, status dropdown, freeform markdown notes with autosave, interesting company indicator, error indicator), A/B prompt comparison (select two versions, side-by-side results), interesting companies manager (CRUD with all rich fields).

**No team/roster/hiring views.** This is a focused job hunting tool.

### External Dependency: voice-of-tim

The cover letter generator uses Anthropic's skills beta API to invoke `voice-of-tim`, a personal writing style skill maintained outside this application. The Anthropic adapter passes `skills-2025-10-02` as a beta header. Fallback: standard API without skill if beta unavailable. The skill is not part of this repo and should not be built, maintained, or versioned here.

---

## Project Structure

```
terrain/
  api/                    ← FastAPI application
    routes/
      opportunities.py    ← CRUD, filters, detail
      pipeline.py         ← trigger runs, status, schedules
      candidates.py          ← config, active prompts
      health.py           ← GET /api/health
    main.py               ← app factory, middleware, lifespan
  pipeline/               ← Pipeline stages
    harvest/
      base.py             ← HarvestSource protocol
      linkedin.py         ← Playwright LinkedIn scraper
      jobright.py         ← stub
      builtin.py          ← stub
    dedup.py              ← exact + similarity dedup
    scorer.py             ← batch + one-off scoring
    promoter.py           ← threshold evaluation
    cover_letter.py       ← batch + one-off generation
    scheduler.py          ← APScheduler setup + run logging
  providers/              ← External service adapters
    ai/
      base.py             ← AIProvider protocol + data classes
      anthropic.py        ← Anthropic SDK wrapper
      ollama.py           ← Ollama API wrapper
    db/
      base.py             ← Repository protocols
      mongo.py            ← MongoDB implementations
      client.py           ← Connection pool + repository factory
  models/                 ← Pydantic models (shared across all packages)
    opportunity.py
    candidate.py
    pipeline.py
    api_usage.py
  config/
    settings.py           ← Pydantic Settings, env vars, AI routing
  prompts/
    candidate_1/
      scoring/
        v1.md
      cover-letter/
        v1.md
      dedup/
        v1.md
  docs/
    design-recommendations.md  ← Full architecture document
    infrastructure/             ← Owner dependency specs (generated)
  ui/
    src/
      components/
      views/
        Dashboard.tsx
        Applications.tsx
        ABComparison.tsx
        InterestingCompanies.tsx
      api/                ← typed API client
      App.tsx
    package.json
    vite.config.ts
    tailwind.config.js
  scripts/
    migrate_sqlite.py     ← SQLite → MongoDB migration
    seed_candidate.py        ← seed candidate_1 profile (if not migrating)
  tests/
    pipeline/
      test_scorer.py
      test_dedup.py
      test_harvester.py
      test_promoter.py
      test_cover_letter.py
      test_scheduler.py
    providers/
      test_anthropic.py
      test_ollama.py
      test_mongo.py
    api/
      test_opportunities.py
      test_pipeline.py
      test_candidates.py
    test_migration.py
    conftest.py           ← shared fixtures, mock factories
  docker-compose.yml      ← dev: MongoDB on localhost
  docker-compose.prod.yml ← prod: points to NAS
  pyproject.toml
  Makefile                ← dev, test, deploy commands
  .env.example
  CLAUDE.md               ← project instructions for Claude Code
  README.md
```

---

## Build Phases

### Phase 1: Foundation (sequential)

Build the contracts everything else depends on. This must be complete and stable before Phase 2.

1. Project skeleton — directory structure, `pyproject.toml`, `docker-compose.yml`, `.env.example`, Makefile, CLAUDE.md
2. Shared Pydantic models — Opportunity (with all subdocuments), Candidate, PipelineRun, ApiUsage, InterestingCompany, and all supporting types (ScoringResult, ApplicationUpdate, DedupResult, CompletionRequest, CompletionResponse, StageResult, etc.)
3. Interface definitions — protocols for AIProvider, all Repository classes, HarvestSource, PipelineStage
4. Configuration — Pydantic Settings, environment variable loading, AI routing config structure
5. Infrastructure dependency specs — generate `docs/infrastructure/` documents (see below)
6. Prompt file migration — port v1 scoring prompt content from the existing seed script and v1 cover letter prompt from the existing team inbox file into `prompts/candidate_1/` markdown files. These are content ports, not code copies.

### Phase 2: Services (parallelizable)

Each can be built and unit-tested independently against Phase 1 interfaces.

- MongoDB repositories (all collections) + connection management + index creation
- Anthropic adapter (Messages API, Batch API, skills beta, prompt caching, retry, usage logging)
- Ollama adapter (completion, response parsing, health check)
- LinkedIn harvester (Playwright, ported from v1 logic, new interface)
- Dedup module (exact match + AI similarity, keeper selection, cross-board logic)
- Scorer (batch + one-off, prompt file loading, result parsing)
- Promoter (threshold evaluation, interesting company boost)
- Cover letter generator (batch + one-off, skill fallback, prompt file loading)
- Scheduler (APScheduler, cron config from candidate profile, pipeline_runs logging)
- Migration script (SQLite reader → MongoDB writer → validation)
- React frontend scaffold (Vite + TypeScript + Tailwind + Router + Tanstack Query, component structure, API client types)

### Phase 3: Integration (sequential)

Wire services together, verify end-to-end:

1. FastAPI routes composing repositories and pipeline stages
2. Pipeline orchestration — scheduler triggers stages, stages use providers and repositories
3. Integration tests — real MongoDB (Docker), real Anthropic (small test set), real Ollama
4. End-to-end smoke test — harvest → dedup → score → promote → generate cover letter → verify fully populated opportunity document

### Phase 4: UI Implementation

- Pipeline dashboard (pipeline_runs + opportunity aggregations)
- Application management (list, detail, filters, notes, cover letter, status)
- A/B prompt comparison (version selector, side-by-side scoring results)
- Interesting companies manager (CRUD)

### Phase 5: Production deployment

- Owner completes infrastructure specs
- Run migration script
- Deploy to Mac Mini
- Verify health endpoint, run scheduled harvest, confirm full pipeline

---

## Infrastructure Dependency Specs

Generate these as the first deliverable in Phase 1. Each document goes in `docs/infrastructure/` and follows this format:

```markdown
# [Dependency Name]

## What this is
What you're setting up and why the application needs it.

## What "done" looks like
Testable acceptance criteria.

## What the application expects
Connection string format, environment variable name, ports, credentials format, version requirements.

## Setup guidance
Step-by-step for someone who may not be an expert in this technology.

## Verification
Command or script to confirm it's working.
```

**Critical principle: minimum viable infrastructure.** Each spec asks the owner to deliver only the floor — a running service with permissions for the application to manage itself. The owner does NOT create database schemas, collections, indexes, or application-level configuration. Examples:
- MongoDB: running instance, user with readWrite + dbAdmin on `terrain` database. Application creates everything else.
- Mac Mini: macOS with Python 3.11+ and SSH access. Application creates venv, installs deps, writes launchd plist.
- Ollama: installed with model pulled. Application configures the connection.

Generate specs for:
1. MongoDB on NAS (Docker container, persistent volume, network binding, auth)
2. Mac Mini Python environment (Python 3.11+, system or Homebrew)
3. Mac Mini application service (launchd plist, auto-restart, logging)
4. Ollama on Mac Mini (install, Llama 3.1 8B Q4 model)
5. Mac Mini networking (static IP or hostname, port access)
6. LinkedIn authenticated session (Playwright browser profile)
7. Anthropic API access (key, Batch API, rate tier)
8. Git repository (repo, clone on both machines, SSH keys)
9. Dev environment on MacBook (Docker Desktop + Mongo, Python venv, Node.js + npm)

---

## Testing Requirements

### Protocol

- After implementing any module, write unit tests before reporting work as complete
- Run relevant test suite after every meaningful change
- When modifying an interface, update both implementation tests and dependent module tests
- Integration tests run on demand — flag when a change warrants one
- Never report a task as complete with failing tests

### Unit tests

Use pytest. Mock at interface boundaries — AI provider mocks return predictable responses, repository mocks return fixture data. No external services needed for unit suite.

### Integration tests

Mark with `@pytest.mark.integration`. Run separately. Hit real services:
- Scorer + Anthropic API against known job description → verify scores in expected range
- Repository + MongoDB (Docker) → full CRUD on opportunity documents
- Ollama + dedup prompt → classification of known duplicate pair

### Prompt regression tests

Benchmark fixtures from v1 calibration anchors (jobs scored at 85, 80, 60, 50). Run against new prompt versions to verify calibration. Part of A/B workflow, not every build.

### API contract tests

Verify FastAPI endpoints return Pydantic response model shapes. Catches frontend/backend drift.

### Migration validation

Built into the migration script: document counts match source rows, no orphans, spot-check sample of fully populated opportunities.

---

## Application Logging

Structured JSON logging via Python `logging`. Development: stdout. Production: launchd captures to log files.

Log: pipeline stage start/complete with duration and counts, AI calls with model/tokens/latency, slow DB operations, scheduler events, errors with tracebacks.

`GET /api/health` returns: status, database connectivity, Ollama connectivity, scheduler state, last run timestamps, uptime.

---

## Environment Configuration

```
# .env.dev
MONGO_URI=mongodb://localhost:27017/terrain
OLLAMA_URL=http://localhost:11434
ANTHROPIC_API_KEY=sk-...
ENVIRONMENT=development
LOG_LEVEL=DEBUG

# .env.prod
MONGO_URI=mongodb://dbhost.local:27017/terrain
OLLAMA_URL=http://localhost:11434
ANTHROPIC_API_KEY=sk-...
ENVIRONMENT=production
LOG_LEVEL=INFO
```

Loaded via Pydantic Settings. `.env` files not committed. `.env.example` committed with placeholder values.

---

## Deployment

**Development (MacBook):** `docker compose up -d` (Mongo), `uvicorn terrain.api.main:app --reload`, `cd ui && npm run dev`

**Production (Mac Mini M1 + NAS):**
- App: native Python via launchd (auto-restart, boot start). 8GB RAM — no Docker overhead.
- Ollama: native via launchd, Llama 3.1 8B Q4 (~5GB). M1 Metal acceleration.
- MongoDB: Docker on NAS, persistent volume, LAN accessible.
- Deploy: `git pull && make restart` on Mac Mini.

---

## What's Deferred

Acknowledged but out of scope for initial build:

- **Gmail monitoring integration** — document fields plumbed (`gmail_events` array), no Gmail API connection
- **Jobright and BuiltIn harvesters** — interface built, stubs exist, only LinkedIn implemented
- **Mobile/PWA** — responsive React app, no dedicated mobile experience
- **Multi-candidate onboarding UI** — data model supports it, no UI for managing candidate profiles
- **Cost forecasting** — usage logging built, dashboard shows history, no predictions

---

## CLAUDE.md Directives

The CLAUDE.md file for this project should include these standing instructions:

```markdown
# terrAIn

## Architecture
This is a job hunting pipeline: harvest → dedup → score → promote → cover letter.
See docs/design-recommendations.md for full architecture.

## Hard Rules
- Every component communicates through interfaces defined in protocols.
  Never import pymongo, anthropic SDK, or ollama outside providers/.
- Never import one pipeline stage's internals from another.
- All database access goes through repository classes in providers/db/.
- All AI calls go through provider classes in providers/ai/.
- Every AI call logs to api_usage collection via the provider.
- Every opportunity document mutation stamps updated_at.
- candidate_id is required on every database query.

## Testing
- Write unit tests alongside implementation. Mock at interface boundaries.
- Run relevant tests after every change. Never report complete with failing tests.
- Mark integration tests with @pytest.mark.integration.

## Prompts
- Prompt content lives in prompts/ directory (filesystem is source of truth).
- Prompt activation metadata lives in candidates collection (MongoDB).
- Every scored/generated result stamps the prompt_version used.

## Style
- Python: async/await throughout. Type hints on all function signatures.
- Pydantic models for all data structures crossing boundaries.
- Structured JSON logging.
- FastAPI with explicit response models.
```
