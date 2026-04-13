# TerrAIn

A job hunting pipeline I designed and built with Claude Code. TerrAIn harvests job listings from LinkedIn, deduplicates them, scores them against my candidate profile using Claude Sonnet, promotes strong matches, and drafts cover letters. Five pipeline stages, three provider adapters, a React/TypeScript frontend, and a FastAPI backend. 152 passing tests. Published at v0.8.

This is equal parts engineering exercise and working tool. I wanted to build an AI solution that is both effective and efficient, mixing open-source local models with frontier APIs, making deliberate cost and quality tradeoffs at each stage, and testing whether Claude Code can build a full-stack application against real architectural requirements delivered through a charter prompt.

---

## What It Does

TerrAIn automates the discovery and evaluation side of a job search: finding relevant roles, assessing fit, drafting application content, and tracking pipeline state. The goal is to surface the connections worth pursuing so I can spend my time on the conversations that matter.

---

## Architecture

I designed the architecture in a separate planning session (Opus Cowork), producing ~70KB of planning deliverables: an architecture document, a Claude Code charter prompt, a UI design system, and a Phase 4 UI prompt. Then I handed the charter prompt to Claude Code and built the application in a single continuous session across ~3 days.

### Pipeline

Five stages, each implemented as an independent service behind a Python Protocol interface:

| Stage | What it does | AI Provider |
|---|---|---|
| **Harvest** | Playwright-based LinkedIn scraper with persistent browser session. Extracts job listings using data-attribute selectors and button-click pagination. | — |
| **Dedup** | Exact match + AI similarity classification. Distinguishes duplicates from reposts from evolved listings. | Ollama (Llama 3.1 8B, local) |
| **Score** | Evaluates each listing against a 24KB calibrated scoring prompt. Returns a recommendation tier (STRONG / GOOD / MARGINAL / SKIP) with rationale. | Anthropic (Claude Sonnet) |
| **Promote** | Threshold evaluation with interesting-company boost. Routes strong matches for content generation. | — |
| **Cover Letter** | Generates tailored, near-ready cover letter drafts using the voice-of-tim skill for consistent voice and tone. | Anthropic (Claude Sonnet) |

### Provider Adapters

Three adapters, all behind Protocol interfaces so they're independently testable and swappable:

- **MongoDB** — motor async driver, 5 repository implementations, compound indexes on candidate_id + pipeline_state
- **Anthropic** — Messages API, Batch API (50% cost savings for scheduled runs), skills beta integration, prompt caching, per-call cost tracking
- **Ollama** — local LLM inference for classification tasks where cost matters more than reasoning depth

### Data Model

A single MongoDB document per opportunity that accumulates state as it moves through the pipeline. Scoring, application status, cover letter, and dedup results are subdocuments added progressively. This replaced the v1 relational schema (3 SQLite tables with foreign keys) because the data is document-shaped: a job listing grows richer over time, and forcing that into normalized tables created friction.

### Frontend

Dark-mode-first React/TypeScript UI built to a Linear-inspired design system I specified in DESIGN.md (thanks to [awesome-design-md](https://github.com/VoltAgent/awesome-design-md) for the foundation). Design token layer (all colors, typography, spacing as CSS custom properties consumed by Tailwind). 11 shared components, 5 views: Pipeline Dashboard, Opportunity List, Opportunity Detail, Interesting Companies, and Prompt Comparison.

### Scheduler

APScheduler with cron triggers and a master on/off toggle. When disabled, runs log as "skipped" rather than silently not running (preserving the audit trail). Manual triggers queue jobs identically to scheduled runs, returning a run ID immediately rather than blocking the HTTP response.

---

## Design Principles

**Interface-driven modularity.** Every component communicates through Python Protocols. Providers are swappable, pipeline stages are independently testable, and no stage imports another stage's internals. I specified this as the core architectural principle for three reasons: development independence, provider swappability, and operational clarity.

**Human judgment at the decision points that matter.** Scoring, routing, and first-draft generation are automated. Final application decisions, tone calibration, and outreach strategy remain mine.

**Persistent state, not session state.** The pipeline maintains full history across runs. No context is lost.

**Backtest before deploy.** Any filter or prompt change gets validated against existing scored data before activation. I established this after testing a pre-scoring filter that looked good on paper but killed 48 STRONG/GOOD FIT opportunities when backtested against real data.

---

## Cost Management

The Anthropic Batch API is implemented for scheduled runs at a 50% discount over synchronous calls. Ollama handles classification tasks (dedup similarity) locally at zero API cost. Per-call cost tracking logs every API interaction so spend is visible by pipeline stage.

I tested a pre-scoring filter using Ollama Llama 8B to reduce the volume reaching the frontier API. It filtered aggressively but killed too many real matches (48 false positives). Shelved with a documented tuning methodology. LinkedIn's own matching already removes the easy mismatches; what remains requires the full scoring prompt.

---

## Technology Stack

- **Backend**: Python, FastAPI, APScheduler
- **Frontend**: React, TypeScript, Vite, Tailwind, Tanstack Query, Recharts
- **Database**: MongoDB 7 (Docker, motor async driver)
- **AI**: Anthropic Claude API (Messages, Batch, skills beta, prompt caching), Ollama (Llama 3.1 8B)
- **Scraping**: Playwright (persistent browser context, LinkedIn)
- **Data Modeling**: Pydantic
- **Testing**: pytest (unit, integration against real Docker MongoDB, end-to-end smoke)
- **Infrastructure**: Two-machine home lab (MacBook dev, Mac Mini M1 prod), Docker Compose, SSH, launchd
- **Built with**: Claude Code (Opus)

---

## What Didn't Work

**Subagent parallelization failed.** I launched three Claude Code subagents to build provider adapters in parallel. All three hit permission walls. I built everything sequentially in the main conversation instead.

**Guessed LinkedIn selectors were completely wrong.** The initial harvester used CSS class-based selectors that looked plausible but didn't work. The v1 code used a fundamentally different approach (data attributes, JS evaluate, button-click pagination). I ported the working selectors from v1.

**Synchronous pipeline triggers timed out.** The initial "Run Harvest" button blocked the HTTP response for the entire harvest duration. I redesigned to background task execution with run ID polling.

**Pre-scoring filter was too aggressive.** The Ollama Llama 8B model filtered 78.5% of opportunities but killed 48 real matches. A lightweight model reading title + 600 characters can't replicate the judgment of the full 24KB scoring prompt. I documented the failure and the 6-step tuning methodology for future revisit.

---

## How I Built It

I designed the architecture in a separate planning session, then distilled it into a charter prompt: a standalone document containing everything Claude Code needed to build the application from scratch in a new repo. Claude Code built it from that prompt in a single continuous conversation across ~3 days. I directed the architecture decisions and handled problems as they came up (the selector failure, the synchronous trigger timeout, the pre-filter rejection). The implementation code is AI-generated; the architecture, the decisions, and the quality bar are mine.

The charter prompt approach was deliberate. I wanted to test whether Claude Code could build against real architectural requirements (typed interfaces, provider adapters, test coverage expectations, a design system spec) rather than evolving code through incremental prompting. The published repo is the answer to that question.

---

## Project Status

v0.8, published. The core pipeline works end-to-end. I'm iterating through tuning and functional feedback toward v1.

**Known follow-ups:** Batch API wiring for bulk scoring, run status reconciliation for orphaned records, multi-source harvesting (Jobright, BuiltIn), production deployment to the Mac Mini.

---

## Relationship to Other Projects

| Project | What it is |
|---|---|
| [Team Claude v1](https://github.com/thrudnar/team-claude-v1) | The original 10-agent team. Established orchestration patterns, surfaced the architectural coupling that this project resolves. |
| [Team Claude](https://github.com/thrudnar/team-claude) | Reorganized v1 to separate operational infrastructure from work products. The intermediate step. |

---

## Notes on Privacy

This repository contains code and architecture only. The job tracking database, candidate profile, scoring prompts, API credentials, and application content are excluded via `.gitignore`. No personal data is included.
