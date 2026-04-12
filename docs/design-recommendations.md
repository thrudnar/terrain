# terrAIn — Re-Architecture Design Recommendations

## 0. Core Design Principle: Interface-Driven Modularity

Every major component in this architecture communicates through an explicitly defined interface (Python protocol or ABC). This is the single most important architectural decision, and it serves three purposes simultaneously:

**Independent development.** Each module can be built and modified in isolation. A developer (human or Claude Code) working on the scorer only needs the `AIProvider` interface and the `OpportunityRepository` interface — not the Anthropic SDK internals or MongoDB query syntax. This means multiple Claude Code sessions can work in parallel on different modules without conflict, both during initial build and for any future development.

**Testability.** The interfaces are the mock boundaries. Unit tests for any module replace its dependencies with mock implementations of the interfaces. No external services needed for the full unit test suite.

**Swappability.** The AI provider can be Anthropic or Ollama. The database can be MongoDB or a future alternative. The harvester can be LinkedIn or Jobright. The business logic doesn't change when an external dependency changes — only the adapter behind the interface.

These three properties are not separate goals — they're the same property observed from different angles. If a module can be tested with a mock, it can be developed independently. If it can be developed independently, its dependencies are swappable. This principle should be treated as a hard constraint on all implementation work: if a module directly imports another module's internals or an external SDK, that's a design violation.

**Development phasing implication:** The interfaces and shared data models must be built first, as a foundation. Once stable, all implementation work behind those interfaces can proceed in parallel.

---

## 1. Data Model: The Opportunity Document

### Recommendation: Single MongoDB document per opportunity, per candidate

The current schema splits a job's lifecycle across three tables (`jobs`, `job_scores`, `applications`) with foreign keys stitching them together. This made sense when the system was exploratory, but the pipeline is fundamentally linear: a job enters, gets enriched, and either progresses or doesn't. The re-arch collapses this into a single document that grows as it moves through stages.

```json
{
  "_id": "ObjectId",
  "candidate_id": "candidate_1",
  "source": {
    "board": "linkedin",
    "board_job_id": "1234567890",
    "collection": "top-applicant",
    "url": "https://linkedin.com/jobs/view/{board_job_id}",
    "first_seen": "2026-04-01T00:00:00Z",
    "last_seen": "2026-04-08T00:00:00Z",
    "posted_date": "2026-03-28T00:00:00Z"
  },
  "company": "Acme Corp",
  "title": "Senior Data Engineer",
  "location": "San Francisco, CA",
  "work_type": "hybrid",
  "description_text": "...",
  "description_hash": "sha256:...",

  "dedup": {
    "status": "unique | duplicate | repost_unchanged | repost_evolved",
    "parent_id": "ObjectId (ref to keeper, if duplicate)",
    "checked_at": "2026-04-01T00:00:00Z",
    "method": "exact | similarity",
    "similarity_score": 0.94
  },

  "scoring": {
    "prompt_version": "v2",
    "model": "claude-haiku-4-5-20251001",
    "overall": 82,
    "skills": 85,
    "seniority": 80,
    "work_type": 90,
    "work_arrangement": "Hybrid",
    "salary_range": "$180K–$220K",
    "match_summary": "...",
    "strengths": ["..."],
    "gaps": ["..."],
    "recommendation": "STRONG FIT",
    "reasoning": "...",
    "scored_at": "2026-04-02T00:00:00Z"
  },

  "application": {
    "status": "new | applied | waiting | phone_screen | interview | offer | rejected | withdrawn | dead",
    "applied_date": "2026-04-03T00:00:00Z",
    "application_link": "https://...",
    "contact": "...",
    "resume_version": "v1",
    "source": "harvested | manual"
  },

  "cover_letter": {
    "prompt_version": "v1",
    "model": "claude-sonnet-4-6",
    "content": "...",
    "generated_at": "2026-04-03T00:00:00Z",
    "skill_used": "voice-of-tim",
    "generation_method": "batch | realtime"
  },

  "notes": "Free-form markdown. Recruiter call 4/5: discussed team size...",

  "gmail_events": [
    {
      "gmail_message_id": "...",
      "subject": "Interview Scheduling",
      "received_at": "2026-04-05T00:00:00Z",
      "characterization": "interview_request"
    }
  ],

  "interesting_company_match": true,

  "pipeline_state": "harvested | scored | applied | active | closed",
  "archived": false,
  "created_at": "2026-04-01T00:00:00Z",
  "updated_at": "2026-04-08T00:00:00Z"
}
```

### Why this works

- **Pipeline progression is natural.** An opportunity starts with `source` + `company` + `title` + `description_text`. The `scoring` subdocument appears after scoring runs. The `application` subdocument appears when you star it. The `cover_letter` subdocument arrives after generation. `notes` grows as you interact. Each stage adds to the document rather than joining across tables.

- **Candidate isolation is built in.** Every query includes `candidate_id`. Indexes are compound: `{ candidate_id: 1, pipeline_state: 1 }`, `{ candidate_id: 1, company: 1, title: 1 }` for dedup, etc.

- **Prompt traceability is embedded.** `scoring.prompt_version` and `cover_letter.prompt_version` are stamped at generation time. A/B comparison is a query: "show me all opportunities scored with v2 vs v3 for candidate_1."

- **Freeform data is first-class.** `notes`, `description_text`, `cover_letter.content`, `match_summary` — these are large text fields that sit comfortably in a document store without the awkwardness of TEXT columns in SQL.

### Supporting collections

```
opportunities          — the core document above
candidates             — candidate profiles, active prompt versions, source configs
interesting_companies  — per-candidate, with rich fields (interest drivers, apprehensions, etc.)
pipeline_runs          — log of each harvest/scoring/cover-letter batch run
api_usage              — cost tracking per API call (model, tokens, cost, run_id)
```

---

## 2. Prompt Management: Filesystem + Metadata

### Recommendation: Prompts as versioned files in the repo, metadata in MongoDB

**Directory structure:**
```
prompts/
  candidate_1/
    scoring/
      v1.md
      v2.md
    cover-letter/
      v1.md
      v2.md
    dedup/
      v1.md
  candidate_2/
    ...
```

**Each prompt file** contains the full prompt text — system prompt, user prompt template, and any instructions. Markdown format for readability. Template variables use `{placeholders}`.

**MongoDB `candidates` collection** tracks which version is active:
```json
{
  "candidate_id": "candidate_1",
  "name": "Candidate Name",
  "active_prompts": {
    "scoring": "v2",
    "cover_letter": "v1",
    "dedup": "v1"
  },
  "prompt_history": [
    { "type": "scoring", "version": "v1", "activated": "2026-03-15", "deactivated": "2026-04-01" },
    { "type": "scoring", "version": "v2", "activated": "2026-04-01", "deactivated": null }
  ]
}
```

**Why filesystem:**
- Claude Code can read, edit, and diff prompt files directly — this is your primary development tool
- Git history provides version archaeology (why did v2 change? check the commit)
- Prompts are inspectable without running the app or querying a database
- The numbered version files are explicit and immutable — v1.md doesn't change after promotion

**A/B comparison workflow:**
1. Create `v3.md` in the scoring directory
2. Run scorer with `--prompt-version v3` against a test set (or the full corpus)
3. UI shows results filterable by prompt version: v2 results vs v3 results side-by-side
4. Promote v3 to active in the candidate config when satisfied

---

## 3. Pipeline Architecture: Stages, Scheduler, and Batch

### Recommendation: In-app scheduler with stage-based pipeline, Batch API for bulk runs

**Pipeline stages (in order):**

```
HARVEST → DEDUP → SCORE → PROMOTE → GENERATE COVER LETTER
```

Each stage is a Python module with a clean interface:

```python
class PipelineStage:
    async def run(self, candidate_id: str, options: dict) -> StageResult:
        """Execute this stage for a candidate. Returns result summary."""
        ...

    async def run_one(self, candidate_id: str, opportunity_id: str) -> StageResult:
        """Execute for a single opportunity (urgent one-off)."""
        ...
```

### Harvest stage
- Runs on schedule (configurable per candidate, per source)
- Multi-source: LinkedIn now, Jobright and BuiltIn architected as source adapters
- Each source adapter implements a common interface:
  ```python
  class HarvestSource:
      async def harvest(self, config: SourceConfig) -> list[RawOpportunity]:
          ...
  ```
- Stores new opportunities with `pipeline_state: "harvested"`
- Captures `posted_date` from job cards where available

### Dedup stage (inline with harvest)
- Runs immediately after harvest, before opportunities enter the scoring queue
- **Fast path:** Exact match on `(candidate_id, company, title)` — pure DB lookup, no AI
- **Similarity path:** When company+title collision is found, invoke Llama (via Ollama) for description comparison. Three-way classification: duplicate / repost-unchanged / repost-evolved
- Keeper selection follows the priority hierarchy from the existing design
- Cross-board aware: the compound index on `(candidate_id, company, title)` catches the same role posted on LinkedIn and Jobright

### Score stage
- **Scheduled runs:** Anthropic Batch API. Collect all unscored opportunities for a candidate, submit as a batch, poll for completion. 50% cost savings.
- **One-off:** Messages API for a single urgent opportunity.
- Prompt caching: system prompt gets `cache_control` — stays cached across the entire batch since it's identical for every request in a run.
- Results written to `scoring` subdocument with `prompt_version` stamped.
- Opportunities advance to `pipeline_state: "scored"`.

### Promote stage
- Rules-based threshold evaluation (configurable per candidate)
- Default: `scoring.overall >= 75` → auto-promote to cover letter queue
- Could also factor in `interesting_company_match` as a boost
- Promotion creates the `application` subdocument with `status: "new"`

### Cover letter stage
- **Scheduled runs:** Batch API for all promoted opportunities awaiting cover letters
- **One-off:** Messages API with voice-of-tim skill for urgent requests
- Writes to `cover_letter` subdocument with `prompt_version` and `skill_used` stamped
- Fallback: if skills beta unavailable, standard API call (current pattern, preserved)

### Scheduler
- **APScheduler** (Python, in-process) — mature, lightweight, supports cron-like schedules
- Schedule configuration per candidate, stored in the `candidates` collection:
  ```json
  {
    "schedules": {
      "harvest_linkedin": "0 8,20 * * *",
      "harvest_jobright": "0 9 * * *",
      "score_batch": "0 10,22 * * *",
      "cover_letter_batch": "0 11 * * *"
    }
  }
  ```
- Pipeline monitoring: each run creates a `pipeline_runs` document logging start time, stage, items processed, errors, duration, cost
- The UI dashboard reads `pipeline_runs` to show schedules, throughput, and batch status

---

## 4. AI Provider Abstraction

### Recommendation: Unified interface with provider adapters for Anthropic and Ollama

```python
class AIProvider:
    """Common interface for all AI operations."""

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send a prompt, get a response."""
        ...

    async def complete_batch(self, requests: list[CompletionRequest]) -> BatchHandle:
        """Submit a batch of requests. Returns a handle for polling."""
        ...

    async def poll_batch(self, handle: BatchHandle) -> BatchResult:
        """Check batch status and retrieve results."""
        ...
```

**Two adapters:**

1. **AnthropicAdapter** — wraps the Anthropic SDK. Handles Messages API (real-time), Batch API (bulk), skills beta (voice-of-tim), prompt caching (`cache_control`). Centralized retry logic, rate limiting, and usage logging.

2. **OllamaAdapter** — wraps Ollama's OpenAI-compatible local API. Used for dedup similarity and other classification tasks. No batch mode needed (local inference is fast and free). If the task outgrows Llama 8B, flip the config to route through AnthropicAdapter instead — zero code changes.

**Configuration per task:**
```json
{
  "ai_routing": {
    "scoring": { "provider": "anthropic", "model": "claude-haiku-4-5-20251001" },
    "cover_letter": { "provider": "anthropic", "model": "claude-sonnet-4-6", "skill": "voice-of-tim" },
    "dedup_similarity": { "provider": "ollama", "model": "llama3.1:8b-q4" },
    "email_classification": { "provider": "ollama", "model": "llama3.1:8b-q4" }
  }
}
```

**Usage logging:** Every AI call (both providers) logs to the `api_usage` collection:
```json
{
  "provider": "anthropic",
  "model": "claude-haiku-4-5-20251001",
  "task": "scoring",
  "candidate_id": "candidate_1",
  "input_tokens": 4200,
  "output_tokens": 800,
  "cached_tokens": 3800,
  "cost_usd": 0.0012,
  "pipeline_run_id": "...",
  "timestamp": "2026-04-08T10:00:00Z"
}
```

---

## 5. Database Abstraction

### Recommendation: Repository pattern isolating MongoDB specifics

```python
class OpportunityRepository:
    """All opportunity data access goes through here."""

    async def find_unscored(self, candidate_id: str) -> list[Opportunity]:
        ...

    async def find_by_company_title(self, candidate_id: str, company: str, title: str) -> list[Opportunity]:
        ...

    async def update_scoring(self, opp_id: str, scoring: ScoringResult) -> None:
        ...

    async def find_for_ui(self, candidate_id: str, filters: OpportunityFilters) -> list[Opportunity]:
        ...
```

**Why:** The business logic (pipeline stages, UI endpoints) never imports `pymongo` or constructs queries directly. If you ever need to swap Mongo for something else, or mock the data layer for testing, the surface area is contained.

**Connection management:** A single `DatabaseClient` class owns the connection pool, handles reconnection, and provides repository instances. Configuration (host, port, database name) comes from environment variables — different values for dev (localhost Docker) vs prod (NAS).

---

## 6. Service Boundaries for Claude Code Development

### Recommendation: Package-per-service in a monorepo

```
terrain/
  api/                  ← FastAPI app (UI backend)
    routes/
      opportunities.py
      pipeline.py
      candidates.py
    main.py
  pipeline/             ← Pipeline stages
    harvest/
      base.py           ← HarvestSource interface
      linkedin.py
      jobright.py        (stub)
      builtin.py         (stub)
    dedup.py
    scorer.py
    promoter.py
    cover_letter.py
    scheduler.py
  providers/            ← External service adapters
    ai/
      base.py           ← AIProvider interface
      anthropic.py
      ollama.py
    db/
      base.py           ← Repository interfaces
      mongo.py          ← MongoDB implementation
  models/               ← Shared data models (Pydantic)
    opportunity.py
    candidate.py
    pipeline.py
  config/               ← Environment-aware configuration
    settings.py
  prompts/              ← Prompt files (filesystem)
    candidate_1/
      scoring/
      cover-letter/
      dedup/
  ui/                   ← React frontend
    src/
      components/
      views/
      api/              ← API client
    package.json
  scripts/              ← Migration, seed data, utilities
    migrate_sqlite.py
  tests/
    pipeline/
    providers/
    api/
  docker-compose.yml    ← Dev environment (Mongo)
  docker-compose.prod.yml
  requirements.txt
  README.md
```

### Why this structure matters for Claude Code

Each top-level package is a **coherent unit of work** you can hand to Claude Code:

- "Work on the LinkedIn harvester" → scope is `pipeline/harvest/linkedin.py` + `providers/` + `models/` + `tests/pipeline/`
- "Improve the scoring prompt" → scope is `prompts/candidate_1/scoring/` + `pipeline/scorer.py`
- "Add a new API endpoint for pipeline monitoring" → scope is `api/routes/pipeline.py` + `models/pipeline.py`
- "Build the A/B comparison view" → scope is `ui/src/views/` + `api/routes/`

The interfaces between packages are explicit Python protocols/ABCs. A developer (human or AI) working on one package knows exactly what contract they need to satisfy without understanding the internals of another.

---

## 7. Frontend: React SPA

### Recommendation: React with a component library, two primary views

**Stack:**
- React 18+ with TypeScript
- Tailwind CSS for styling (utility-first, fast to iterate, demo-quality output)
- Recharts for pipeline monitoring charts
- React Router for view navigation
- Tanstack Query (React Query) for API data fetching and caching

**Two primary experiences:**

### Pipeline Dashboard
- **Harvest monitor:** Last run time, jobs harvested (by source), next scheduled run, error count
- **Scoring monitor:** Batch status, jobs scored, match distribution (chart: how many STRONG/GOOD/MARGINAL/SKIP), prompt version in use
- **Cover letter monitor:** Batch status, letters generated, pending queue depth
- **Schedule overview:** All scheduled jobs with next-run times, enable/disable toggles
- **Cost summary:** Spend by task type, trend over time (from `api_usage` collection)

### Application Management
- **Opportunity list** with filters: pipeline state, recommendation tier, work arrangement, company, date range
- **Opportunity detail view:**
  - Job description (collapsible)
  - Match assessment with scores and narrative
  - Cover letter (editable, regenerable)
  - Status dropdown for pipeline state
  - Freeform notes field (markdown, autosaves)
  - Gmail events timeline (when plumbed)
  - Interesting company indicator
- **A/B prompt comparison:** Select two prompt versions, view scoring results side-by-side for the same opportunities
- **Interesting companies manager:** Add, edit, view entries with all rich fields

### No team views
The team/roster/hiring/tasks views from the current UI are excluded entirely. This is a focused job hunting tool.

---

## 8. Infrastructure & Deployment

### Development environment (MacBook)
- **Code:** Local repo, Claude Code as primary development tool
- **Database:** MongoDB in Docker Desktop (`docker-compose.yml` — starts Mongo on `localhost:27017`)
- **Ollama:** Not needed on MacBook for dev — mock the AI provider interface for dedup tests, or install Ollama locally if you want to test inference
- **App:** Run FastAPI directly (`uvicorn terrain.api.main:app --reload`)
- **Frontend:** Vite dev server with hot reload (`npm run dev`)

### Production environment

**Application server runs:**
- The Python application (API + scheduler + pipeline workers) — managed by `launchd` (native macOS process manager, auto-restarts on crash, starts on boot)
- Ollama as a persistent service (also via `launchd`) — Llama 3.1 8B Q4 loaded and ready
- Nginx as a reverse proxy (optional, for clean URL routing between API and static frontend assets)

**Database server runs:**
- MongoDB in Docker — persistent storage, accessible on the LAN at a fixed IP/hostname

**Why launchd over Docker for the app:** Running the Python app natively (no container overhead) and Ollama natively (needs direct access to Metal/GPU for Apple Silicon acceleration) is more memory-efficient. Docker would add overhead for no real benefit — the app isn't complex enough to need container isolation from itself.

**Why Docker for Mongo on the database server:** Docker support is already available, Mongo's official image is well-maintained, and isolating the database on dedicated storage hardware is the right separation.

### Deployment workflow

**Recommended: Git-based with a simple pull-and-restart pattern.**

1. Development happens on the dev machine, committed to a Git repo
2. Production server has the repo cloned
3. Deploy: `ssh prod && cd terrain && git pull && make restart`
4. `make restart` triggers `launchctl` to restart the app service

**Why not rsync:** Git gives you rollback, history, and the confidence that what's running in prod is exactly a committed state. rsync can drift.

**Why not full CI/CD:** This is a single-user system on a private network. A multi-stage pipeline with build servers would be overengineering. The `git pull && make restart` pattern is honest, reliable, and fast.

### Environment configuration

The application reads config from environment variables (via Pydantic Settings). See `.env.example` for the variable names and defaults. The `.env` files are NOT committed to the repo — they live on each machine.

---

## 9. Local AI: Ollama + Llama

### Recommendation: Ollama as a persistent service for classification tasks

**Model:** Llama 3.1 8B Instruct, Q4_K_M quantization (~5GB RAM)

**Tasks routed to local Llama:**

| Task | Input | Output | Why local |
|------|-------|--------|-----------|
| Dedup similarity | Two job descriptions (trimmed) | Score 0–1 + classification | High volume at harvest time, binary-ish judgment, no cost per call |
| Field extraction | Raw job HTML | Structured fields (posted_date, salary, location) | Pattern recognition, not reasoning |
| Gmail classification | Email subject + snippet | Category label | Simple classification, latency doesn't matter |

**Tasks that stay on Anthropic:**

| Task | Why Anthropic |
|------|--------------|
| Match scoring | Nuanced judgment against full career profile, calibrated prompts |
| Cover letter generation | Quality is everything, voice-of-tim skill integration |

**Ollama setup on the application server:**
```bash
# Install (one-time)
curl -fsSL https://ollama.com/install.sh | sh

# Pull model (one-time)
ollama pull llama3.1:8b-instruct-q4_K_M

# Runs as a service automatically after install
# API available at http://localhost:11434
```

**The escape hatch:** If any Llama-powered task underperforms, change one config line to route it through the Anthropic adapter. The task's prompt file and logic don't change — only the provider config:
```json
"dedup_similarity": { "provider": "anthropic", "model": "claude-haiku-4-5-20251001" }
```

---

## 10. Migration Strategy

### Recommendation: One-time Python script, run before go-live

`scripts/migrate_sqlite.py` reads the existing SQLite database and writes to MongoDB:

1. **For each row in `jobs`:** Create an opportunity document with `source`, `company`, `title`, `description_text`, and basic fields populated.
2. **For each row in `job_scores`:** Find the matching opportunity by `job_board + job_id`, populate the `scoring` subdocument. Stamp `scoring.prompt_version` from the score record.
3. **For each row in `applications`:** Find the matching opportunity, populate the `application` and `cover_letter` subdocuments.
4. **`interesting_companies`:** Migrate to its own collection, keyed by `candidate_id`.
5. **`score_prompts` and `cover_letter_prompts`:** Content migrates to prompt files on disk (`prompts/candidate_1/scoring/v1.md`, etc.). Activation metadata goes into the `candidates` collection.
6. **Validation pass:** Count documents, verify no orphaned scores or applications, spot-check a few opportunities end-to-end.

All migrated data gets `candidate_id: "candidate_1"`.

---

## 11. Pipeline Runs & Error Tracking (Addendum)

### Pipeline Runs collection

Each scheduled or manual pipeline execution creates a run document:

```json
{
  "candidate_id": "candidate_1",
  "stage": "harvest | dedup | scoring | promotion | cover_letter",
  "source": "linkedin (harvest only)",
  "started_at": "2026-04-08T08:00:00Z",
  "completed_at": "2026-04-08T08:03:42Z",
  "trigger": "scheduled | manual",
  "items_processed": 47,
  "items_new": 12,
  "items_duplicate": 3,
  "items_error": 0,
  "prompt_version": "v2 (scoring/cover letter stages)",
  "batch_id": "Anthropic batch ID (if applicable)",
  "cost_usd": 0.0042,
  "error_log": [],
  "status": "completed | failed | running"
}
```

The pipeline dashboard reads this collection to show: last run times per stage, throughput trends, error rates, cost per run, and next scheduled execution. An aggregation on the `opportunities` collection grouped by `pipeline_state` provides the current inventory view — how many opportunities are in each stage right now.

### Error tracking on opportunity documents

When a pipeline stage fails for a specific opportunity, the error is recorded directly on the document:

```json
{
  "errors": [
    {
      "stage": "scoring",
      "occurred_at": "2026-04-08T10:02:15Z",
      "run_id": "ObjectId (ref to pipeline_runs)",
      "error_type": "rate_limit | api_error | parse_error | timeout | validation",
      "message": "JSON parse failed: model returned markdown-wrapped response",
      "retryable": true,
      "resolved_at": null
    }
  ]
}
```

This gives immediate visibility on any individual opportunity — the UI can surface an error indicator without log diving. The `retryable` flag lets the pipeline auto-retry on the next scheduled run. `resolved_at` gets stamped when a subsequent run succeeds, preserving the error history while showing current health.

The pipeline dashboard aggregates error states across opportunities for a health summary: "3 opportunities stuck in error state, 2 retryable."

---

## 12. Testing Strategy

### Principle: Test as you build, not after

Claude Code writes and runs tests alongside implementation — every module ships with its test suite. Tests are a first-class deliverable, not a verification step bolted on at the end.

### Testing layers

**Unit tests** — one test file per module, using pytest. The AI provider and database repository interfaces are the primary mock boundaries. Tests for pipeline stages (scorer, dedup, harvester logic) use mock providers that return predictable responses. Tests for API routes use mock repositories. No external services needed to run the full unit suite.

```
tests/
  pipeline/
    test_scorer.py        ← mock AI provider, verify score parsing and document updates
    test_dedup.py         ← mock AI provider, verify classification logic
    test_harvester.py     ← mock HTTP responses, verify field extraction
    test_promoter.py      ← verify threshold logic against sample opportunities
    test_cover_letter.py  ← mock AI provider, verify document updates and fallback
    test_scheduler.py     ← verify schedule config loading and stage dispatch
  providers/
    test_anthropic.py     ← verify request formatting, retry logic, usage logging
    test_ollama.py        ← verify request formatting, response parsing
    test_mongo.py         ← verify query construction, document mapping
  api/
    test_opportunities.py ← verify route responses, filters, error handling
    test_pipeline.py      ← verify run triggers, status reporting
    test_candidates.py       ← verify config endpoints
  test_migration.py       ← verify SQLite-to-Mongo data integrity
```

**Integration tests** (marked, run separately) — these hit real external services and verify end-to-end behavior:
- Scorer + Anthropic API against a known job description → scores in expected range
- Repository + MongoDB (Docker container) → full CRUD cycle on opportunity documents
- Ollama + dedup prompt → classification of a known duplicate pair
- API + MongoDB → full request/response cycle through the real stack

**Prompt regression tests** — a fixed set of benchmark opportunities with expected score ranges. When a new prompt version is created, run it against the benchmarks and verify calibration hasn't drifted. The existing four calibration anchors (85, 80, 60, 50) from v1 become formal test fixtures. These run as part of the A/B comparison workflow — not on every build, but on every prompt change.

**API contract tests** — verify that API endpoints return the JSON shapes the React frontend depends on. These catch frontend/backend drift early. Pydantic response models serve double duty here: they're both the API's output specification and the test's expected schema.

**Migration validation** — the migration script includes a verification pass: document counts match source row counts, no orphaned scores or applications, spot-check a sample of fully-populated opportunity documents end-to-end.

### Claude Code testing protocol

The CLAUDE.md for the new project should include this directive:

- After implementing any module, write unit tests before reporting the work as complete
- Run the relevant test suite after every meaningful change
- When modifying an interface (AI provider, repository, API route), update both the implementation tests and any dependent module tests
- Integration tests run on demand, not automatically — flag when a change warrants an integration test run
- Never report a task as complete with failing tests

---

## 13. External Dependency: voice-of-tim Skill

The cover letter generator depends on Anthropic's skills beta API to invoke the `voice-of-tim` skill, which governs the candidate's writing voice and style. This skill is maintained outside the application — it's a personal style resource used across Claude products (claude.ai, Claude Code, Cowork, API).

**How it's accessed:** The Anthropic adapter passes `skills-2025-10-02` as a beta header and includes the skill identifier in the API call. The skill shapes *how* the cover letter sounds; the prompt file shapes *what* it says.

**Fallback:** If the skills beta is unavailable (API change, deprecation, network issue), the cover letter generator falls back to the standard Messages API without the skill. This produces a functional but less voice-calibrated cover letter. The fallback is logged on the opportunity document (`cover_letter.skill_used: null`).

**Design implication:** The AI provider interface needs to support optional skill parameters on completion requests. The Anthropic adapter handles the beta header; the Ollama adapter ignores skill parameters (local models don't support skills). This keeps the skill integration contained in the adapter layer.

**Not in scope:** Building, maintaining, or versioning the voice-of-tim skill itself. It lives outside this repo.

---

## 14. Application Logging & Health

### Recommendation: Structured logging with Python's logging module, health endpoint

**Application logs:** All components use Python's standard `logging` module with structured JSON output. In development, logs go to stdout. In production, `launchd` captures stdout/stderr to log files automatically (configurable in the plist). Log level is configurable via environment variable (`LOG_LEVEL=INFO` in prod, `DEBUG` in dev).

**What gets logged:**
- Pipeline stage start/complete with duration and item counts
- AI provider calls with model, token counts, and latency (complements the `api_usage` collection for real-time debugging)
- Database operations that take longer than a threshold
- Scheduler events (job triggered, skipped, failed)
- Errors with full tracebacks

**Health endpoint:** `GET /api/health` returns a quick status check:
```json
{
  "status": "healthy",
  "database": "connected",
  "ollama": "connected | unavailable",
  "scheduler": "running",
  "last_harvest": "2026-04-08T08:00:00Z",
  "last_score_run": "2026-04-08T10:00:00Z",
  "uptime_seconds": 86400
}
```

This gives you a single URL to hit to verify the production system is alive and connected to its dependencies. It also provides a foundation for any future monitoring or alerting.

---

## 15. Development Phasing

### Build order: Foundation → Services → Integration → UI

The architecture is designed for parallel development, but the foundation must be built first. Here's the sequenced plan:

### Phase 1: Foundation (sequential, single Claude Code session)

This phase establishes the contracts everything else depends on. Must be complete and stable before Phase 2 begins.

1. **Project skeleton** — directory structure, `pyproject.toml` / `requirements.txt`, `docker-compose.yml`, `.env.example`, CLAUDE.md
2. **Shared data models** — Pydantic models for Opportunity, Candidate, PipelineRun, ApiUsage, and all subdocuments (Scoring, Application, CoverLetter, Dedup, etc.)
3. **Interface definitions** — Python protocols/ABCs for AIProvider, OpportunityRepository, CandidateRepository, PipelineRunRepository, HarvestSource, PipelineStage
4. **Configuration** — Pydantic Settings loading from environment variables, AI routing config, scheduler config
5. **Infrastructure dependency specs** — generate the `docs/infrastructure/` spec documents for owner delivery
6. **Prompt file migration** — port v1 scoring and cover letter prompt content from SQLite seed scripts to `prompts/candidate_1/` markdown files

### Phase 2: Services (parallelizable, multiple Claude Code sessions)

Each of these can be built and tested independently against the interfaces from Phase 1.

- **MongoDB adapter** — repository implementations, connection management, index creation
- **Anthropic adapter** — Messages API, Batch API, skills beta, prompt caching, retry logic, usage logging
- **Ollama adapter** — completion requests, response parsing, connection health check
- **LinkedIn harvester** — ported from v1, adapted to new interfaces and opportunity model
- **Dedup stage** — exact match + similarity classification logic
- **Scorer stage** — batch and one-off modes, prompt file loading, result parsing
- **Promoter stage** — threshold evaluation, configurable per candidate
- **Cover letter stage** — batch and one-off modes, skill fallback, prompt file loading
- **Scheduler** — APScheduler setup, cron config loading from candidate profile, run logging
- **Migration script** — SQLite reader, MongoDB writer, validation pass
- **React frontend scaffold** — project setup, routing, API client, component structure

### Phase 3: Integration (sequential, single Claude Code session)

Wire the services together and verify end-to-end:

1. **API routes** — FastAPI endpoints that compose repositories and pipeline stages
2. **Pipeline orchestration** — scheduler triggers stages, stages call providers and repositories
3. **Integration tests** — real MongoDB, real Anthropic API (small test set), real Ollama
4. **End-to-end smoke test** — harvest one job, dedup it, score it, promote it, generate a cover letter, verify the opportunity document is fully populated

### Phase 4: UI (can begin during Phase 2, integrates in Phase 3)

- **Pipeline dashboard** — reads pipeline_runs and opportunity aggregations
- **Application management** — opportunity list, detail view, filters, notes, cover letter display
- **A/B comparison view** — prompt version selector, side-by-side results
- **Interesting companies manager** — CRUD interface

### Phase 5: Production deployment

- Owner completes infrastructure dependency specs (database server, application server, Ollama)
- Run migration script against production MongoDB
- Deploy application to production server
- Verify health endpoint, run scheduled harvest, confirm full pipeline

---

## 16. What's Deferred (Intentionally)

These items are acknowledged in the requirements but explicitly out of scope for the initial re-arch build:

- **Gmail monitoring integration** — schema plumbing included (fields in opportunity document, `gmail_events` array), but no Gmail API connection or email processing logic
- **Jobright and BuiltIn harvesters** — source adapter interface is built, stubs exist, but only LinkedIn is implemented
- **Mobile/PWA** — React app is responsive enough to use on a phone browser, but no dedicated mobile experience
- **Multi-candidate onboarding UI** — the data model supports multiple candidates, but there's no UI for creating/managing candidate profiles. Candidate_1 is seeded by the migration script.
- **Cost forecasting** — usage logging is built, dashboard shows historical spend, but no predictive modeling
