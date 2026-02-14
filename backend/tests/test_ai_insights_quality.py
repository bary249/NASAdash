"""
AI Insights Quality + Speed Benchmark
Compares models side-by-side on the same property data.

Run: python -m tests.test_ai_insights_quality
"""
import asyncio
import json
import time
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from anthropic import Anthropic
from app.config import get_settings
from app.services.ai_insights_service import INSIGHTS_PROMPT, _build_data_summary

MODELS = [
    ("claude-3-5-haiku-20241022", "Haiku 3.5"),
    ("claude-sonnet-4-20250514", "Sonnet 4"),
]

# Quality rubric — scored by Claude itself (meta-evaluation)
QUALITY_RUBRIC = """You are grading an AI-generated property analysis. Score each dimension 1-5.

DIMENSIONS:
1. **Specificity** (1-5): Does it use actual numbers from the data? Or vague language like "consider improving"?
2. **Dollar Impact** (1-5): Are risks quantified in $/month or $/year? Or just qualitative?
3. **Cross-correlation** (1-5): Does it connect 2+ data points into insights? Or treat each metric in isolation?
4. **Actionability** (1-5): Are actions specific enough to execute tomorrow? Or generic "review and adjust"?
5. **Non-obviousness** (1-5): Does it surface insights the owner wouldn't see from the dashboard alone?

Output ONLY this JSON:
{"specificity": N, "dollar_impact": N, "cross_correlation": N, "actionability": N, "non_obviousness": N, "total": N, "reasoning": "One sentence summary"}
"""


async def get_test_property_data() -> dict:
    """Gather real property data for testing."""
    from app.services import occupancy_service, pricing_service
    from app.models import Timeframe

    property_id = "parkside"
    property_data = {"property_id": property_id}

    try:
        occ = await occupancy_service.get_occupancy_metrics(property_id, Timeframe.CM)
        property_data["property_name"] = occ.property_name
        property_data["occupancy"] = occ.model_dump()
    except Exception:
        pass
    try:
        p = await pricing_service.get_unit_pricing(property_id)
        property_data["pricing"] = p.model_dump()
    except Exception:
        pass
    try:
        f = await occupancy_service.get_leasing_funnel(property_id, Timeframe.L30)
        property_data["funnel"] = f.model_dump()
    except Exception:
        pass
    try:
        property_data["expirations"] = await occupancy_service.get_lease_expirations(property_id)
    except Exception:
        pass
    try:
        property_data["tradeouts"] = await pricing_service.get_lease_tradeouts(property_id)
    except Exception:
        pass
    try:
        property_data["loss_to_lease"] = await pricing_service.get_loss_to_lease(property_id)
    except Exception:
        pass

    # Delinquency
    try:
        from app.db.schema import UNIFIED_DB_PATH
        import sqlite3
        conn = sqlite3.connect(UNIFIED_DB_PATH)
        c = conn.cursor()
        c.execute("""
            SELECT SUM(CASE WHEN total_delinquent > 0 THEN total_delinquent ELSE 0 END),
                   COUNT(CASE WHEN total_delinquent > 0 THEN 1 END),
                   SUM(CASE WHEN balance_0_30 > 0 THEN balance_0_30 ELSE 0 END),
                   SUM(CASE WHEN balance_31_60 > 0 THEN balance_31_60 ELSE 0 END),
                   SUM(CASE WHEN balance_over_90 > 0 THEN balance_over_90 ELSE 0 END)
            FROM unified_delinquency WHERE unified_property_id = ?
        """, (property_id,))
        row = c.fetchone()
        conn.close()
        if row and row[0]:
            property_data["delinquency"] = {
                "total_delinquent": row[0], "delinquent_units": row[1],
                "over_30": row[2], "over_60": row[3], "over_90": row[4],
            }
    except Exception:
        pass

    # Risk scores
    try:
        from app.db.schema import UNIFIED_DB_PATH
        import sqlite3
        conn = sqlite3.connect(UNIFIED_DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM unified_risk_scores WHERE unified_property_id = ?", (property_id,))
        row = c.fetchone()
        if row:
            cols = [d[0] for d in c.description]
            rd = dict(zip(cols, row))
            property_data["risk_scores"] = {
                "total_scored": rd.get("total_scored", 0),
                "churn": {"high_risk": rd.get("churn_high_risk", 0), "medium_risk": rd.get("churn_medium_risk", 0), "low_risk": rd.get("churn_low_risk", 0)},
                "delinquency": {"high_risk": rd.get("delinq_high_risk", 0), "medium_risk": rd.get("delinq_medium_risk", 0)},
            }
        conn.close()
    except Exception:
        pass

    # Reviews
    try:
        from app.services.google_reviews_service import get_property_reviews
        g = await get_property_reviews(property_id)
        if g and not g.get("error"):
            property_data["google_reviews"] = {"rating": g.get("rating"), "review_count": g.get("review_count", 0), "response_rate": g.get("response_rate", 0), "needs_response": g.get("needs_response", 0)}
    except Exception:
        pass
    try:
        from app.services.apartments_reviews_service import get_apartments_reviews
        a = get_apartments_reviews(property_id)
        if a and a.get("rating"):
            property_data["apartments_reviews"] = {"rating": a.get("rating"), "review_count": a.get("review_count", 0), "response_rate": a.get("response_rate", 0), "needs_response": a.get("needs_response", 0)}
    except Exception:
        pass

    return property_data


def run_model(client: Anthropic, model: str, data_summary: str) -> dict:
    """Run a single model and return timing + output."""
    t0 = time.time()
    try:
        response = client.messages.create(
            model=model,
            max_tokens=1500,
            messages=[{"role": "user", "content": INSIGHTS_PROMPT + data_summary}]
        )
        elapsed = time.time() - t0
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(raw)
        return {
            "model": model,
            "elapsed": round(elapsed, 2),
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "alerts": result.get("alerts", []),
            "qna": result.get("qna", []),
            "raw": raw,
        }
    except Exception as e:
        return {"model": model, "elapsed": round(time.time() - t0, 2), "error": str(e)}


def grade_output(client: Anthropic, data_summary: str, output: dict) -> dict:
    """Grade an AI output using the quality rubric."""
    try:
        resp = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=400,
            messages=[{"role": "user", "content": QUALITY_RUBRIC + f"\n\nPROPERTY DATA:\n{data_summary}\n\nAI OUTPUT:\n{output['raw']}"}]
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        # Extract first JSON object (grader sometimes appends explanation text)
        depth = 0
        start = raw.index("{")
        for i, ch in enumerate(raw[start:], start):
            if ch == "{": depth += 1
            elif ch == "}": depth -= 1
            if depth == 0:
                raw = raw[start:i+1]
                break
        result = json.loads(raw)
        # Auto-compute total if missing
        if "total" not in result or result["total"] == 0:
            dims = ["specificity", "dollar_impact", "cross_correlation", "actionability", "non_obviousness"]
            result["total"] = sum(result.get(d, 0) for d in dims)
        return result
    except Exception as e:
        return {"error": str(e), "total": 0}


async def main():
    settings = get_settings()
    if not settings.anthropic_api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        return

    client = Anthropic(api_key=settings.anthropic_api_key)

    print("=" * 60)
    print("AI INSIGHTS QUALITY + SPEED BENCHMARK")
    print("=" * 60)

    # Gather data
    print("\n1. Gathering property data...")
    property_data = await get_test_property_data()
    data_summary = _build_data_summary("parkside", property_data)
    print(f"   Data summary: {len(data_summary)} chars")
    print(f"   Sections: {[k for k in property_data.keys() if k not in ('property_id', 'property_name')]}")

    # Run each model
    results = []
    for model_id, label in MODELS:
        print(f"\n2. Running {label} ({model_id})...")
        result = run_model(client, model_id, data_summary)
        result["label"] = label
        results.append(result)
        if "error" in result:
            print(f"   ERROR: {result['error']}")
        else:
            print(f"   Time: {result['elapsed']}s | Tokens: {result['input_tokens']}→{result['output_tokens']}")
            print(f"   Alerts: {len(result['alerts'])} | Q&A: {len(result['qna'])}")
            for a in result["alerts"]:
                print(f"     [{a['severity']}] {a['title']}")

    # Grade each output
    print("\n3. Grading outputs...")
    for r in results:
        if "error" in r:
            r["grade"] = {"error": r["error"], "total": 0}
            continue
        print(f"   Grading {r['label']}...")
        r["grade"] = grade_output(client, data_summary, r)
        g = r["grade"]
        if "error" not in g:
            print(f"   Score: {g['total']}/25 | {g.get('reasoning', '')}")

    # Print comparison table
    print("\n" + "=" * 60)
    print("COMPARISON")
    print("=" * 60)
    print(f"{'Metric':<25} ", end="")
    for r in results:
        print(f"{'| ' + r['label']:<20}", end="")
    print()
    print("-" * 65)

    metrics = [
        ("Speed (seconds)", lambda r: f"{r.get('elapsed', '?')}s"),
        ("Input tokens", lambda r: str(r.get("input_tokens", "?"))),
        ("Output tokens", lambda r: str(r.get("output_tokens", "?"))),
        ("Alerts count", lambda r: str(len(r.get("alerts", [])))),
        ("Q&A count", lambda r: str(len(r.get("qna", [])))),
        ("Specificity", lambda r: str(r.get("grade", {}).get("specificity", "?")) + "/5"),
        ("Dollar Impact", lambda r: str(r.get("grade", {}).get("dollar_impact", "?")) + "/5"),
        ("Cross-correlation", lambda r: str(r.get("grade", {}).get("cross_correlation", "?")) + "/5"),
        ("Actionability", lambda r: str(r.get("grade", {}).get("actionability", "?")) + "/5"),
        ("Non-obviousness", lambda r: str(r.get("grade", {}).get("non_obviousness", "?")) + "/5"),
        ("TOTAL QUALITY", lambda r: str(r.get("grade", {}).get("total", "?")) + "/25"),
    ]

    for label, fn in metrics:
        print(f"{label:<25} ", end="")
        for r in results:
            print(f"{'| ' + fn(r):<20}", end="")
        print()

    # Recommendation
    print("\n" + "=" * 60)
    valid = [r for r in results if "error" not in r]
    if len(valid) == 2:
        fast = min(valid, key=lambda r: r["elapsed"])
        best = max(valid, key=lambda r: r.get("grade", {}).get("total", 0))
        speed_ratio = max(r["elapsed"] for r in valid) / min(r["elapsed"] for r in valid)
        quality_diff = best.get("grade", {}).get("total", 0) - min(r.get("grade", {}).get("total", 0) for r in valid)

        print(f"Speed winner:   {fast['label']} ({speed_ratio:.1f}x faster)")
        print(f"Quality winner: {best['label']} (+{quality_diff} points)")

        if best["label"] == fast["label"]:
            print(f"\nRECOMMENDATION: {best['label']} wins on both speed and quality.")
        elif quality_diff <= 2:
            print(f"\nRECOMMENDATION: Use {fast['label']} — quality difference is marginal ({quality_diff} pts) but {speed_ratio:.1f}x faster.")
        elif speed_ratio <= 1.5:
            print(f"\nRECOMMENDATION: Use {best['label']} — quality gain ({quality_diff} pts) is worth the modest speed cost ({speed_ratio:.1f}x).")
        else:
            print(f"\nTRADEOFF: {best['label']} is better quality (+{quality_diff}) but {fast['label']} is {speed_ratio:.1f}x faster. Your call.")

    # Save full results
    out_path = Path(__file__).parent / "ai_insights_benchmark.json"
    with open(out_path, "w") as f:
        # Strip raw output for readability
        save = []
        for r in results:
            s = {k: v for k, v in r.items() if k != "raw"}
            save.append(s)
        json.dump(save, f, indent=2)
    print(f"\nFull results saved to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
