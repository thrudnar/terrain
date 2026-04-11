"""Dedup stage — identifies duplicate opportunities via exact match and AI similarity."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from terrain.models.opportunity import DedupMethod, DedupResult, DedupStatus, PipelineState
from terrain.models.pipeline import PipelineStageEnum, StageResult
from terrain.providers.ai.base import AIProvider, CompletionRequest
from terrain.providers.db.base import CandidateRepository, OpportunityRepository


class Dedup:
    """Deduplicates opportunities using exact match and AI similarity comparison."""

    def __init__(
        self,
        opportunity_repo: OpportunityRepository,
        candidate_repo: CandidateRepository,
        ai_provider: AIProvider,
        prompts_dir: Path = Path("prompts"),
    ) -> None:
        self._opp_repo = opportunity_repo
        self._cand_repo = candidate_repo
        self._ai = ai_provider
        self._prompts_dir = prompts_dir

    def _load_prompt(self, candidate_id: str, version: str) -> tuple[str, str]:
        """Load dedup prompt file, split into system and user template."""
        prompt_path = self._prompts_dir / candidate_id / "dedup" / f"{version}.md"
        content = prompt_path.read_text()

        if "## Job A" in content:
            parts = content.split("## Job A", 1)
            system_prompt = parts[0].strip()
            user_template = "## Job A" + parts[1].strip()
        else:
            system_prompt = content
            user_template = "## Job A (existing)\n\n{description_a}\n\n## Job B (new)\n\n{description_b}"

        return system_prompt, user_template

    def _parse_similarity_response(self, content: str) -> tuple[DedupStatus, float]:
        """Parse AI response into dedup status and similarity score."""
        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:])
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        data = json.loads(text)
        classification = data["classification"]
        similarity = float(data.get("similarity_score", 0.0))

        status_map = {
            "duplicate": DedupStatus.DUPLICATE,
            "repost_unchanged": DedupStatus.REPOST_UNCHANGED,
            "repost_evolved": DedupStatus.REPOST_EVOLVED,
        }
        status = status_map.get(classification, DedupStatus.UNIQUE)
        return status, similarity

    async def _check_similarity(
        self,
        candidate_id: str,
        existing_desc: str,
        new_desc: str,
        prompt_version: str,
        model: str,
    ) -> tuple[DedupStatus, float]:
        """Use AI to compare two job descriptions for similarity."""
        system_prompt, user_template = self._load_prompt(candidate_id, prompt_version)
        user_prompt = user_template.replace("{description_a}", existing_desc).replace(
            "{description_b}", new_desc
        )

        request = CompletionRequest(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            metadata={"task": "dedup", "candidate_id": candidate_id},
        )
        response = await self._ai.complete(request)
        return self._parse_similarity_response(response.content)

    async def run(
        self, candidate_id: str, options: Optional[dict[str, object]] = None
    ) -> StageResult:
        start = time.monotonic()
        errors: list[str] = []

        candidate = await self._cand_repo.get(candidate_id)
        if candidate is None:
            return StageResult(
                stage=PipelineStageEnum.DEDUP,
                items_error=1,
                errors=[f"Candidate {candidate_id} not found"],
            )

        prompt_version = candidate.active_prompts.dedup
        model = "llama3.1:8b-q4"
        if candidate.ai_routing and candidate.ai_routing.dedup_similarity:
            model = candidate.ai_routing.dedup_similarity.model

        from terrain.providers.db.base import OpportunityFilters

        filters = OpportunityFilters(pipeline_state=PipelineState.HARVESTED)
        harvested = await self._opp_repo.find_for_ui(candidate_id, filters)

        duplicates = 0
        unique = 0

        for opp in harvested:
            if opp.dedup is not None:
                continue

            try:
                # Fast path: exact match on company + title
                matches = await self._opp_repo.find_by_company_title(
                    candidate_id, opp.company, opp.title
                )
                # Exclude self from matches
                existing = [m for m in matches if m.id != opp.id and m.dedup is None or (m.dedup and m.dedup.status != DedupStatus.DUPLICATE)]

                if not existing:
                    dedup_result = DedupResult(
                        status=DedupStatus.UNIQUE,
                        checked_at=datetime.now(timezone.utc),
                        method=DedupMethod.EXACT,
                    )
                    await self._opp_repo.update_dedup(
                        candidate_id, opp.id or "", dedup_result
                    )
                    unique += 1
                    continue

                # Similarity path: AI comparison with the first existing match
                keeper = existing[0]
                status, score = await self._check_similarity(
                    candidate_id,
                    keeper.description_text,
                    opp.description_text,
                    prompt_version,
                    model,
                )

                if status in (DedupStatus.DUPLICATE, DedupStatus.REPOST_UNCHANGED):
                    dedup_result = DedupResult(
                        status=status,
                        parent_id=keeper.id,
                        checked_at=datetime.now(timezone.utc),
                        method=DedupMethod.SIMILARITY,
                        similarity_score=score,
                    )
                    duplicates += 1
                else:
                    # repost_evolved or unique — treat as new opportunity
                    dedup_result = DedupResult(
                        status=status,
                        checked_at=datetime.now(timezone.utc),
                        method=DedupMethod.SIMILARITY,
                        similarity_score=score,
                    )
                    unique += 1

                await self._opp_repo.update_dedup(candidate_id, opp.id or "", dedup_result)

            except Exception as e:
                errors.append(f"Dedup failed for {opp.id}: {e}")

        return StageResult(
            stage=PipelineStageEnum.DEDUP,
            items_processed=len(harvested),
            items_new=unique,
            items_error=len(errors),
            errors=errors,
            duration_seconds=time.monotonic() - start,
        )

    async def run_one(self, candidate_id: str, opportunity_id: str) -> StageResult:
        start = time.monotonic()

        candidate = await self._cand_repo.get(candidate_id)
        if candidate is None:
            return StageResult(
                stage=PipelineStageEnum.DEDUP,
                items_error=1,
                errors=[f"Candidate {candidate_id} not found"],
            )

        opp = await self._opp_repo.get(candidate_id, opportunity_id)
        if opp is None:
            return StageResult(
                stage=PipelineStageEnum.DEDUP,
                items_error=1,
                errors=[f"Opportunity {opportunity_id} not found"],
            )

        prompt_version = candidate.active_prompts.dedup
        model = "llama3.1:8b-q4"
        if candidate.ai_routing and candidate.ai_routing.dedup_similarity:
            model = candidate.ai_routing.dedup_similarity.model

        matches = await self._opp_repo.find_by_company_title(
            candidate_id, opp.company, opp.title
        )
        existing = [m for m in matches if m.id != opp.id]

        if not existing:
            dedup_result = DedupResult(
                status=DedupStatus.UNIQUE,
                checked_at=datetime.now(timezone.utc),
                method=DedupMethod.EXACT,
            )
        else:
            keeper = existing[0]
            status, score = await self._check_similarity(
                candidate_id,
                keeper.description_text,
                opp.description_text,
                prompt_version,
                model,
            )
            dedup_result = DedupResult(
                status=status,
                parent_id=keeper.id if status in (DedupStatus.DUPLICATE, DedupStatus.REPOST_UNCHANGED) else None,
                checked_at=datetime.now(timezone.utc),
                method=DedupMethod.SIMILARITY,
                similarity_score=score,
            )

        await self._opp_repo.update_dedup(candidate_id, opportunity_id, dedup_result)

        return StageResult(
            stage=PipelineStageEnum.DEDUP,
            items_processed=1,
            items_new=1 if dedup_result.status != DedupStatus.DUPLICATE else 0,
            duration_seconds=time.monotonic() - start,
        )
