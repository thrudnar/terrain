"""Scorer stage — scores opportunities against candidate profile using AI."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from terrain.models.opportunity import PipelineState, Recommendation, ScoringResult
from terrain.models.pipeline import PipelineStageEnum, StageResult
from terrain.providers.ai.base import AIProvider, CompletionRequest
from terrain.providers.db.base import CandidateRepository, OpportunityRepository


class Scorer:
    """Scores opportunities using AI provider with versioned prompts."""

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
        """Load and split prompt file into system prompt and user prompt template."""
        prompt_path = self._prompts_dir / candidate_id / "scoring" / f"{version}.md"
        content = prompt_path.read_text()

        # Split on "## User Prompt Template" heading
        if "## User Prompt Template" in content:
            parts = content.split("## User Prompt Template", 1)
            system_prompt = parts[0].strip()
            user_template = parts[1].strip()
            # Remove trailing notes section if present
            if "## Notes" in user_template:
                user_template = user_template.split("## Notes")[0].strip()
        else:
            system_prompt = content
            user_template = "{description_text}"

        return system_prompt, user_template

    def _parse_scoring_response(
        self, content: str, prompt_version: str, model: str
    ) -> ScoringResult:
        """Parse AI JSON response into ScoringResult."""
        # Strip markdown code fences if present
        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:])
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        data = json.loads(text)

        return ScoringResult(
            prompt_version=prompt_version,
            model=model,
            overall=int(data["overall"]),
            skills=int(data["skills"]),
            seniority=int(data["seniority"]),
            work_type=int(data["work_type"]),
            work_arrangement=data.get("work_arrangement"),
            salary_range=data.get("salary_range"),
            match_summary=data["match_summary"],
            strengths=data.get("strengths", []),
            gaps=data.get("gaps", []),
            recommendation=Recommendation(data["recommendation"]),
            reasoning=data.get("reasoning", ""),
            scored_at=datetime.now(timezone.utc),
        )

    async def run(
        self, candidate_id: str, options: Optional[dict[str, object]] = None
    ) -> StageResult:
        start = time.monotonic()
        errors: list[str] = []

        candidate = await self._cand_repo.get(candidate_id)
        if candidate is None:
            return StageResult(
                stage=PipelineStageEnum.SCORING,
                items_error=1,
                errors=[f"Candidate {candidate_id} not found"],
            )

        prompt_version = candidate.active_prompts.scoring
        if options and "prompt_version" in options:
            prompt_version = str(options["prompt_version"])

        model = "claude-sonnet-4-6"
        if candidate.ai_routing and candidate.ai_routing.scoring:
            model = candidate.ai_routing.scoring.model

        system_prompt, user_template = self._load_prompt(candidate_id, prompt_version)
        unscored = await self._opp_repo.find_unscored(candidate_id)

        scored = 0
        for opp in unscored:
            try:
                user_prompt = user_template.replace(
                    "{description_text}", opp.description_text
                )
                request = CompletionRequest(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    cache_control=True,
                    metadata={"task": "scoring", "candidate_id": candidate_id},
                )
                response = await self._ai.complete(request)
                scoring = self._parse_scoring_response(
                    response.content, prompt_version, model
                )
                await self._opp_repo.update_scoring(candidate_id, opp.id or "", scoring)
                await self._opp_repo.update_pipeline_state(
                    candidate_id, opp.id or "", PipelineState.SCORED
                )
                scored += 1
            except Exception as e:
                errors.append(f"Failed to score {opp.id}: {e}")

        return StageResult(
            stage=PipelineStageEnum.SCORING,
            items_processed=len(unscored),
            items_new=scored,
            items_error=len(errors),
            errors=errors,
            duration_seconds=time.monotonic() - start,
        )

    async def run_one(self, candidate_id: str, opportunity_id: str) -> StageResult:
        start = time.monotonic()

        candidate = await self._cand_repo.get(candidate_id)
        if candidate is None:
            return StageResult(
                stage=PipelineStageEnum.SCORING,
                items_error=1,
                errors=[f"Candidate {candidate_id} not found"],
            )

        opp = await self._opp_repo.get(candidate_id, opportunity_id)
        if opp is None:
            return StageResult(
                stage=PipelineStageEnum.SCORING,
                items_error=1,
                errors=[f"Opportunity {opportunity_id} not found"],
            )

        prompt_version = candidate.active_prompts.scoring
        model = "claude-sonnet-4-6"
        if candidate.ai_routing and candidate.ai_routing.scoring:
            model = candidate.ai_routing.scoring.model

        system_prompt, user_template = self._load_prompt(candidate_id, prompt_version)
        user_prompt = user_template.replace("{description_text}", opp.description_text)

        request = CompletionRequest(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            metadata={"task": "scoring", "candidate_id": candidate_id},
        )
        response = await self._ai.complete(request)
        scoring = self._parse_scoring_response(response.content, prompt_version, model)
        await self._opp_repo.update_scoring(candidate_id, opportunity_id, scoring)
        await self._opp_repo.update_pipeline_state(
            candidate_id, opportunity_id, PipelineState.SCORED
        )

        return StageResult(
            stage=PipelineStageEnum.SCORING,
            items_processed=1,
            items_new=1,
            duration_seconds=time.monotonic() - start,
        )
