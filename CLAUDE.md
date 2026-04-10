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
