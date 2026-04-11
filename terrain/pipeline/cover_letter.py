"""Cover letter stage — generates cover letters using AI with voice-of-tim skill."""

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from terrain.models.opportunity import CoverLetter, GenerationMethod, PipelineState
from terrain.models.pipeline import PipelineStageEnum, StageResult
from terrain.providers.ai.base import AIProvider, CompletionRequest
from terrain.providers.db.base import CandidateRepository, OpportunityRepository


class CoverLetterGenerator:
    """Generates cover letters using AI provider with versioned prompts and voice-of-tim skill."""

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
        """Load cover letter prompt file, split into system and user template."""
        prompt_path = self._prompts_dir / candidate_id / "cover-letter" / f"{version}.md"
        content = prompt_path.read_text()

        if "## User Prompt Template" in content:
            parts = content.split("## User Prompt Template", 1)
            system_prompt = parts[0].strip()
            user_template = parts[1].strip()
            if "## Notes" in user_template:
                user_template = user_template.split("## Notes")[0].strip()
        else:
            system_prompt = content
            user_template = (
                "Company: {company}\nTitle: {title}\n\n{description_text}\n\n"
                "Match: {match_summary}\nStrengths: {strengths}"
            )

        return system_prompt, user_template

    def _fill_template(
        self,
        template: str,
        company: str,
        title: str,
        description_text: str,
        match_summary: str,
        strengths: list[str],
    ) -> str:
        """Substitute template variables with opportunity data."""
        result = template.replace("{company}", company)
        result = result.replace("{title}", title)
        result = result.replace("{description_text}", description_text)
        result = result.replace("{match_summary}", match_summary)
        result = result.replace("{strengths}", ", ".join(strengths))
        return result

    async def _generate_one(
        self,
        candidate_id: str,
        opp_id: str,
        system_prompt: str,
        user_prompt: str,
        model: str,
        skill: Optional[str],
        prompt_version: str,
        method: GenerationMethod,
    ) -> CoverLetter:
        """Generate a single cover letter, with skill fallback."""
        request = CompletionRequest(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            skill=skill,
            metadata={"task": "cover_letter", "candidate_id": candidate_id},
        )

        skill_used = skill
        try:
            response = await self._ai.complete(request)
        except Exception:
            if skill:
                # Fallback: retry without skill
                request_no_skill = CompletionRequest(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    skill=None,
                    metadata={"task": "cover_letter", "candidate_id": candidate_id},
                )
                response = await self._ai.complete(request_no_skill)
                skill_used = None
            else:
                raise

        return CoverLetter(
            prompt_version=prompt_version,
            model=model,
            content=response.content,
            generated_at=datetime.now(timezone.utc),
            skill_used=skill_used,
            generation_method=method,
        )

    async def run(
        self, candidate_id: str, options: Optional[dict[str, object]] = None
    ) -> StageResult:
        start = time.monotonic()
        errors: list[str] = []

        candidate = await self._cand_repo.get(candidate_id)
        if candidate is None:
            return StageResult(
                stage=PipelineStageEnum.COVER_LETTER,
                items_error=1,
                errors=[f"Candidate {candidate_id} not found"],
            )

        prompt_version = candidate.active_prompts.cover_letter
        model = "claude-sonnet-4-6"
        skill: Optional[str] = None
        if candidate.ai_routing and candidate.ai_routing.cover_letter:
            model = candidate.ai_routing.cover_letter.model
            skill = candidate.ai_routing.cover_letter.skill

        system_prompt, user_template = self._load_prompt(candidate_id, prompt_version)
        awaiting = await self._opp_repo.find_awaiting_cover_letter(candidate_id)

        generated = 0
        for opp in awaiting:
            try:
                match_summary = ""
                strengths: list[str] = []
                if opp.scoring:
                    match_summary = opp.scoring.match_summary
                    strengths = opp.scoring.strengths

                user_prompt = self._fill_template(
                    user_template,
                    opp.company,
                    opp.title,
                    opp.description_text,
                    match_summary,
                    strengths,
                )

                cover_letter = await self._generate_one(
                    candidate_id,
                    opp.id or "",
                    system_prompt,
                    user_prompt,
                    model,
                    skill,
                    prompt_version,
                    GenerationMethod.BATCH,
                )
                await self._opp_repo.update_cover_letter(
                    candidate_id, opp.id or "", cover_letter
                )
                generated += 1
            except Exception as e:
                errors.append(f"Cover letter failed for {opp.id}: {e}")

        return StageResult(
            stage=PipelineStageEnum.COVER_LETTER,
            items_processed=len(awaiting),
            items_new=generated,
            items_error=len(errors),
            errors=errors,
            duration_seconds=time.monotonic() - start,
        )

    async def run_one(self, candidate_id: str, opportunity_id: str) -> StageResult:
        start = time.monotonic()

        candidate = await self._cand_repo.get(candidate_id)
        if candidate is None:
            return StageResult(
                stage=PipelineStageEnum.COVER_LETTER,
                items_error=1,
                errors=[f"Candidate {candidate_id} not found"],
            )

        opp = await self._opp_repo.get(candidate_id, opportunity_id)
        if opp is None:
            return StageResult(
                stage=PipelineStageEnum.COVER_LETTER,
                items_error=1,
                errors=[f"Opportunity {opportunity_id} not found"],
            )

        prompt_version = candidate.active_prompts.cover_letter
        model = "claude-sonnet-4-6"
        skill: Optional[str] = None
        if candidate.ai_routing and candidate.ai_routing.cover_letter:
            model = candidate.ai_routing.cover_letter.model
            skill = candidate.ai_routing.cover_letter.skill

        system_prompt, user_template = self._load_prompt(candidate_id, prompt_version)

        match_summary = ""
        strengths: list[str] = []
        if opp.scoring:
            match_summary = opp.scoring.match_summary
            strengths = opp.scoring.strengths

        user_prompt = self._fill_template(
            user_template,
            opp.company,
            opp.title,
            opp.description_text,
            match_summary,
            strengths,
        )

        cover_letter = await self._generate_one(
            candidate_id,
            opportunity_id,
            system_prompt,
            user_prompt,
            model,
            skill,
            prompt_version,
            GenerationMethod.REALTIME,
        )
        await self._opp_repo.update_cover_letter(candidate_id, opportunity_id, cover_letter)

        return StageResult(
            stage=PipelineStageEnum.COVER_LETTER,
            items_processed=1,
            items_new=1,
            duration_seconds=time.monotonic() - start,
        )
