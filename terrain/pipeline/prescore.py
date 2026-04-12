"""Pre-score filter — lightweight AI assessment to skip obvious mismatches before full scoring.

Uses a cheap/local model (Ollama or Haiku) to make a binary "score" or "skip" decision
based on title + truncated description. Much cheaper than full scoring with Sonnet.

Configuration: enabled via candidate's filter_rules or a simple feature flag.
Prompt content lives in prompts/<candidate_id>/prescore/v1.md (gitignored, not in repo).
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional

from terrain.models.opportunity import Opportunity, PipelineState
from terrain.models.pipeline import PipelineStageEnum, StageResult
from terrain.providers.ai.base import AIProvider, CompletionRequest
from terrain.providers.db.base import CandidateRepository, OpportunityRepository

logger = logging.getLogger(__name__)

# Truncate descriptions to this length for the pre-filter prompt
DESCRIPTION_TRUNCATE = 600


class PreScoreFilter:
    """Lightweight AI pre-filter that screens opportunities before full scoring."""

    def __init__(
        self,
        opportunity_repo: OpportunityRepository,
        candidate_repo: CandidateRepository,
        ai_provider: AIProvider,
        prompts_dir: Path = Path("prompts"),
        enabled: bool = True,
    ) -> None:
        self._opp_repo = opportunity_repo
        self._cand_repo = candidate_repo
        self._ai = ai_provider
        self._prompts_dir = prompts_dir
        self.enabled = enabled

    def _load_prompt(self, candidate_id: str) -> tuple[str, str]:
        """Load prescore prompt file, return (system_prompt, user_template)."""
        prompt_path = self._prompts_dir / candidate_id / "prescore" / "v1.md"
        content = prompt_path.read_text()

        if "## User Prompt Template" in content:
            parts = content.split("## User Prompt Template", 1)
            system_prompt = parts[0].strip()
            user_template = parts[1].strip()
            if "## Notes" in user_template:
                user_template = user_template.split("## Notes")[0].strip()
        else:
            system_prompt = content
            user_template = "Title: {title}\nCompany: {company}\n\nDescription (excerpt):\n{description_excerpt}\n\nDecision:"

        return system_prompt, user_template

    def _truncate_description(self, text: str) -> str:
        """Truncate description to first N characters, breaking at a word boundary."""
        if len(text) <= DESCRIPTION_TRUNCATE:
            return text
        truncated = text[:DESCRIPTION_TRUNCATE]
        last_space = truncated.rfind(" ")
        if last_space > DESCRIPTION_TRUNCATE // 2:
            truncated = truncated[:last_space]
        return truncated + "..."

    def _parse_decision(self, content: str) -> tuple[str, str]:
        """Parse AI response into (decision, reason). Returns ('score', '') or ('skip', reason)."""
        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:])
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        try:
            data = json.loads(text)
            decision = data.get("decision", "score").lower().strip()
            reason = data.get("reason", "")
            if decision in ("skip", "filter"):
                return "skip", reason
            return "score", ""
        except (json.JSONDecodeError, AttributeError):
            # If parsing fails, default to "score" (don't filter on error)
            logger.warning("Failed to parse pre-score response: %s", text[:100])
            return "score", ""

    async def evaluate_one(self, opp: Opportunity, system_prompt: str, user_template: str) -> tuple[str, str]:
        """Evaluate a single opportunity. Returns (decision, reason)."""
        excerpt = self._truncate_description(opp.description_text)

        user_prompt = user_template.format(
            title=opp.title,
            company=opp.company,
            description_excerpt=excerpt,
        )

        request = CompletionRequest(
            model="llama3.1:8b-instruct-q4_K_M",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.0,
            max_tokens=100,
            metadata={"task": "prescore", "candidate_id": opp.candidate_id},
        )

        response = await self._ai.complete(request)
        return self._parse_decision(response.content)

    async def run(
        self, candidate_id: str, options: Optional[dict[str, object]] = None
    ) -> StageResult:
        """Run pre-score filter on all harvested opportunities."""
        start = time.monotonic()

        if not self.enabled:
            return StageResult(
                stage=PipelineStageEnum.DEDUP,  # Uses dedup stage enum as placeholder
                errors=["Pre-score filter is disabled"],
            )

        candidate = await self._cand_repo.get(candidate_id)
        if candidate is None:
            return StageResult(
                stage=PipelineStageEnum.DEDUP,
                items_error=1,
                errors=[f"Candidate {candidate_id} not found"],
            )

        system_prompt, user_template = self._load_prompt(candidate_id)

        from terrain.providers.db.base import OpportunityFilters
        filters = OpportunityFilters(pipeline_state=PipelineState.HARVESTED)
        harvested = await self._opp_repo.find_for_ui(candidate_id, filters)

        filtered_count = 0
        passed_count = 0
        errors: list[str] = []

        for opp in harvested:
            try:
                decision, reason = await self.evaluate_one(opp, system_prompt, user_template)
                if decision == "skip":
                    await self._opp_repo.update_pipeline_state(
                        candidate_id, opp.id or "", PipelineState.FILTERED
                    )
                    filtered_count += 1
                    logger.info("Pre-filtered %s — %s: %s", opp.id, opp.title, reason)
                else:
                    passed_count += 1
            except Exception as e:
                errors.append(f"Pre-score failed for {opp.id}: {e}")
                # On error, leave as harvested (will be scored normally)

        return StageResult(
            stage=PipelineStageEnum.DEDUP,
            items_processed=len(harvested),
            items_new=passed_count,
            items_error=len(errors),
            errors=errors,
            duration_seconds=time.monotonic() - start,
        )

    async def run_one(self, candidate_id: str, opportunity_id: str) -> StageResult:
        opp = await self._opp_repo.get(candidate_id, opportunity_id)
        if opp is None:
            return StageResult(
                stage=PipelineStageEnum.DEDUP,
                items_error=1,
                errors=[f"Opportunity {opportunity_id} not found"],
            )

        system_prompt, user_template = self._load_prompt(candidate_id)
        decision, reason = await self.evaluate_one(opp, system_prompt, user_template)
        return StageResult(
            stage=PipelineStageEnum.DEDUP,
            items_processed=1,
            items_new=1 if decision == "score" else 0,
        )
