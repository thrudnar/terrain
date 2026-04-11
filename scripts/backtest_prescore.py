"""Backtest the pre-score filter against all scored opportunities in the database.

Runs each opportunity through the Ollama pre-filter and compares the
filter decision against the actual Sonnet scoring result.

Usage:
    python scripts/backtest_prescore.py
"""

import asyncio
import json
import logging
import sys
from collections import Counter
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

from terrain.pipeline.prescore import PreScoreFilter, PRESCORE_SYSTEM_PROMPT, PRESCORE_USER_TEMPLATE, DESCRIPTION_TRUNCATE
from terrain.providers.ai.ollama import OllamaProvider

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    # Connect to DB
    client = AsyncIOMotorClient("mongodb://localhost:27017/terrain")
    db = client.get_default_database()

    # Get all scored opportunities
    cursor = db.opportunities.find({"scoring": {"$ne": None}})
    opps = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        opps.append(doc)

    print(f"=== PRE-SCORE FILTER BACKTEST ===")
    print(f"Model: llama3.1:8b-instruct-q4_K_M (via Ollama)")
    print(f"Opportunities: {len(opps)}")
    print()

    # Initialize Ollama
    ollama = OllamaProvider("http://localhost:11434")

    results = []
    for i, opp in enumerate(opps):
        title = opp.get("title", "")
        company = opp.get("company", "")
        desc = opp.get("description_text", "")
        scoring = opp.get("scoring", {})
        overall = scoring.get("overall", 0)
        recommendation = scoring.get("recommendation", "?")

        # Truncate description
        excerpt = desc[:DESCRIPTION_TRUNCATE]
        if len(desc) > DESCRIPTION_TRUNCATE:
            last_space = excerpt.rfind(" ")
            if last_space > DESCRIPTION_TRUNCATE // 2:
                excerpt = excerpt[:last_space]
            excerpt += "..."

        user_prompt = PRESCORE_USER_TEMPLATE.format(
            title=title,
            company=company,
            description_excerpt=excerpt,
        )

        from terrain.providers.ai.base import CompletionRequest
        request = CompletionRequest(
            model="llama3.1:8b-instruct-q4_K_M",
            system_prompt=PRESCORE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.0,
            max_tokens=100,
        )

        try:
            response = await ollama.complete(request)
            text = response.content.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:])
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            data = json.loads(text)
            decision = data.get("decision", "score").lower().strip()
            reason = data.get("reason", "")
        except Exception as e:
            decision = "score"  # Default to score on error
            reason = f"parse error: {e}"

        results.append({
            "company": company,
            "title": title,
            "overall": overall,
            "recommendation": recommendation,
            "prescore_decision": decision,
            "prescore_reason": reason,
        })

        status = "SKIP" if decision == "skip" else "PASS"
        sys.stdout.write(f"\r  [{i+1}/{len(opps)}] {status} {overall:3d} {recommendation:14s} {company[:20]} — {title[:40]}")
        sys.stdout.flush()

    print("\n")

    # Analysis
    would_filter = [r for r in results if r["prescore_decision"] == "skip"]
    would_keep = [r for r in results if r["prescore_decision"] != "skip"]

    print(f"=== RESULTS ===")
    print(f"Would filter: {len(would_filter)} ({100*len(would_filter)/len(results):.1f}%)")
    print(f"Would keep:   {len(would_keep)} ({100*len(would_keep)/len(results):.1f}%)")
    print()

    # Filtered by actual tier
    print(f"=== FILTERED by actual Sonnet score tier ===")
    filtered_tiers = Counter(r["recommendation"] for r in would_filter)
    for tier in ["STRONG FIT", "GOOD FIT", "MARGINAL FIT", "SKIP"]:
        count = filtered_tiers.get(tier, 0)
        pct = 100 * count / len(would_filter) if would_filter else 0
        print(f"  {tier:14s} {count:3d} ({pct:4.1f}%)")

    print()
    print(f"=== KEPT by actual Sonnet score tier ===")
    kept_tiers = Counter(r["recommendation"] for r in would_keep)
    for tier in ["STRONG FIT", "GOOD FIT", "MARGINAL FIT", "SKIP"]:
        count = kept_tiers.get(tier, 0)
        pct = 100 * count / len(would_keep) if would_keep else 0
        print(f"  {tier:14s} {count:3d} ({pct:4.1f}%)")

    # THE CRITICAL CHECK
    good_filtered = [r for r in would_filter if r["recommendation"] in ("STRONG FIT", "GOOD FIT")]
    print()
    if good_filtered:
        print(f"!!! WARNING: {len(good_filtered)} STRONG/GOOD FIT would be pre-filtered !!!")
        print()
        for r in sorted(good_filtered, key=lambda x: x["overall"], reverse=True):
            print(f"  {r['overall']:3d} {r['recommendation']:12s}  {r['company']} — {r['title']}")
            print(f"      Reason: {r['prescore_reason']}")
            print()
    else:
        print("SAFE: No STRONG FIT or GOOD FIT would be pre-filtered.")

    # Score distribution of filtered
    if would_filter:
        filtered_scores = [r["overall"] for r in would_filter]
        print()
        print(f"=== FILTERED score range: {min(filtered_scores)}–{max(filtered_scores)}, median: {sorted(filtered_scores)[len(filtered_scores)//2]} ===")

    # Confusion matrix
    print()
    print(f"=== CONFUSION MATRIX (prescore vs Sonnet) ===")
    # True positive = prescore says skip AND Sonnet says SKIP/MARGINAL
    # False positive = prescore says skip AND Sonnet says STRONG/GOOD (BAD!)
    # True negative = prescore says score AND Sonnet says STRONG/GOOD
    # False negative = prescore says score AND Sonnet says SKIP (missed filter, costs money but harmless)
    tp = len([r for r in results if r["prescore_decision"] == "skip" and r["recommendation"] in ("SKIP", "MARGINAL FIT")])
    fp = len([r for r in results if r["prescore_decision"] == "skip" and r["recommendation"] in ("STRONG FIT", "GOOD FIT")])
    tn = len([r for r in results if r["prescore_decision"] != "skip" and r["recommendation"] in ("STRONG FIT", "GOOD FIT")])
    fn = len([r for r in results if r["prescore_decision"] != "skip" and r["recommendation"] in ("SKIP", "MARGINAL FIT")])

    print(f"  True positives  (correctly filtered):  {tp:3d}")
    print(f"  FALSE POSITIVES (wrongly filtered):    {fp:3d}  {'!!! DANGER' if fp > 0 else 'SAFE'}")
    print(f"  True negatives  (correctly kept):      {tn:3d}")
    print(f"  False negatives (missed, harmless):    {fn:3d}")
    if tp + fp > 0:
        print(f"  Precision: {100*tp/(tp+fp):.1f}% (of filtered, how many were actually bad)")
    if tp + fn > 0:
        print(f"  Recall:    {100*tp/(tp+fn):.1f}% (of actual bad, how many did we catch)")

    # Cost impact
    avg_cost = 4.508166 / 298
    savings = len(would_filter) * avg_cost
    print()
    print(f"=== COST IMPACT ===")
    print(f"Sonnet calls saved: {len(would_filter)}")
    print(f"Savings per run: ${savings:.2f}")
    print(f"Estimated cost after pre-filter: ${len(would_keep) * avg_cost:.2f}")

    await ollama.close()
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
