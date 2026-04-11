"""Pre-score filter — lightweight AI assessment to skip obvious mismatches before full scoring.

Uses a cheap/local model (Ollama or Haiku) to make a binary "score" or "skip" decision
based on title + truncated description. Much cheaper than full scoring with Sonnet.

Configuration: enabled via candidate's filter_rules or a simple feature flag.
"""

import json
import logging
import time
from typing import Optional

from terrain.models.opportunity import Opportunity, PipelineState
from terrain.models.pipeline import PipelineStageEnum, StageResult
from terrain.providers.ai.base import AIProvider, CompletionRequest
from terrain.providers.db.base import CandidateRepository, OpportunityRepository

logger = logging.getLogger(__name__)

# Truncate descriptions to this length for the pre-filter prompt
DESCRIPTION_TRUNCATE = 600

PRESCORE_SYSTEM_PROMPT = """You are screening job listings for a senior data executive. Your job is to make a fast binary decision: is this worth a detailed evaluation, or is it an obvious mismatch?

THE CANDIDATE:
- Target level: Director, Sr. Director, VP in data engineering, analytics, data platform, or data/AI infrastructure
- Target function: Data leadership and org-building, NOT hands-on IC work
- Industries: FinTech, Telehealth, Ecommerce preferred, but open to others if the mandate fits
- Geography: US remote strongly preferred
- NOT a fit for: product management, software engineering, DevOps/SRE, cybersecurity, sales, or domain-specialist roles requiring expertise in clinical trials, credit risk, ERP finance, mobile attribution, or gaming

SKIP if any of these are true:
- The role is an individual contributor position (building models, writing code daily, hands-on engineering)
- The role is in the wrong function (product, engineering, security, sales, marketing)
- The role requires deep domain expertise the candidate lacks (VBC healthcare, biopharma, credit risk, ERP systems)
- The role is a combined CIO/CTO scope where IT infrastructure management is a core responsibility
- The role is below Director level (manager, analyst, associate, specialist)
- The role is at a staffing/recruiting firm

SCORE if:
- Data leadership at Director+ level with org-building or platform mandate
- Even if the domain is unfamiliar, if the hire is for leadership ability not domain expertise

Respond with ONLY a JSON object: {"decision": "score"} or {"decision": "skip", "reason": "<one sentence>"}"""

PRESCORE_USER_TEMPLATE = """Title: {title}
Company: {company}

Description (excerpt):
{description_excerpt}

Decision:"""


class PreScoreFilter:
    """Lightweight AI pre-filter that screens opportunities before full scoring."""

    def __init__(
        self,
        opportunity_repo: OpportunityRepository,
        candidate_repo: CandidateRepository,
        ai_provider: AIProvider,
        enabled: bool = True,
    ) -> None:
        self._opp_repo = opportunity_repo
        self._cand_repo = candidate_repo
        self._ai = ai_provider
        self.enabled = enabled

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

    async def evaluate_one(self, opp: Opportunity) -> tuple[str, str]:
        """Evaluate a single opportunity. Returns (decision, reason)."""
        excerpt = self._truncate_description(opp.description_text)

        user_prompt = PRESCORE_USER_TEMPLATE.format(
            title=opp.title,
            company=opp.company,
            description_excerpt=excerpt,
        )

        request = CompletionRequest(
            model="llama3.1:8b-instruct-q4_K_M",
            system_prompt=PRESCORE_SYSTEM_PROMPT,
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

        from terrain.providers.db.base import OpportunityFilters
        filters = OpportunityFilters(pipeline_state=PipelineState.HARVESTED)
        harvested = await self._opp_repo.find_for_ui(candidate_id, filters)

        filtered_count = 0
        passed_count = 0
        errors: list[str] = []

        for opp in harvested:
            try:
                decision, reason = await self.evaluate_one(opp)
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

        decision, reason = await self.evaluate_one(opp)
        return StageResult(
            stage=PipelineStageEnum.DEDUP,
            items_processed=1,
            items_new=1 if decision == "score" else 0,
        )
