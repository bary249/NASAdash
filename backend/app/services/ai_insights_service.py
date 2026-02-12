"""
AI Insights Service - Auto-generated red flags and pre-computed Q&A.
Uses Claude to analyze property data and produce actionable alerts.
READ-ONLY: Only analyzes data, no modifications.
"""
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional

from anthropic import Anthropic
from app.config import get_settings

logger = logging.getLogger(__name__)

# Simple in-memory cache (property_id -> {timestamp, data})
_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL = 3600  # 1 hour


def _get_cached(property_id: str) -> Optional[dict]:
    entry = _cache.get(property_id)
    if entry and (time.time() - entry["ts"]) < CACHE_TTL:
        return entry["data"]
    return None


def _set_cached(property_id: str, data: dict):
    _cache[property_id] = {"ts": time.time(), "data": data}


INSIGHTS_PROMPT = """You are an expert asset manager analyzing a multifamily property. Based on the data below, produce EXACTLY this JSON structure (no markdown, no code fences, just raw JSON):

{
  "alerts": [
    {
      "severity": "high" | "medium" | "low",
      "title": "Short alert title (max 8 words)",
      "fact": "One sentence with specific numbers from the data.",
      "risk": "One sentence explaining the financial/operational risk.",
      "action": "One sentence with a concrete recommended action."
    }
  ],
  "qna": [
    {
      "question": "A question an owner/manager would ask",
      "answer": "A concise answer with specific numbers from the data (2-3 sentences max)."
    }
  ]
}

RULES:
- Generate 2-4 alerts based on REAL issues in the data (not generic advice). Prioritize by severity.
- Generate 3 Q&A pairs covering: (1) a financial/occupancy question, (2) a leasing/pipeline question, (3) a risk/resident question.
- Use ONLY the numbers from the provided data. Never invent data.
- Never include resident names or PII.
- Keep each field concise. No paragraphs.
- If data is limited, generate fewer alerts but never fabricate.
- Output valid JSON only. No explanation text before or after.

PROPERTY DATA:
"""


async def generate_insights(property_id: str, property_data: Dict[str, Any]) -> dict:
    """Generate AI insights for a property. Returns cached if available."""
    cached = _get_cached(property_id)
    if cached:
        logger.debug(f"[AI-INSIGHTS] Cache hit for {property_id}")
        return cached

    settings = get_settings()
    if not settings.anthropic_api_key:
        return {"alerts": [], "qna": [], "error": "AI not configured"}

    client = Anthropic(api_key=settings.anthropic_api_key)

    # Build compact data summary for the prompt
    data_summary = _build_data_summary(property_id, property_data)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": INSIGHTS_PROMPT + data_summary
            }]
        )
        raw = response.content[0].text.strip()

        # Parse JSON (handle potential markdown wrapping)
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        result = json.loads(raw)

        # Validate structure
        if "alerts" not in result:
            result["alerts"] = []
        if "qna" not in result:
            result["qna"] = []

        _set_cached(property_id, result)
        logger.info(f"[AI-INSIGHTS] Generated {len(result['alerts'])} alerts, {len(result['qna'])} Q&A for {property_id}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"[AI-INSIGHTS] JSON parse error: {e}\nRaw: {raw[:500]}")
        return {"alerts": [], "qna": [], "error": "Failed to parse AI response"}
    except Exception as e:
        logger.error(f"[AI-INSIGHTS] Error: {e}")
        return {"alerts": [], "qna": [], "error": str(e)}


def _build_data_summary(property_id: str, data: Dict[str, Any]) -> str:
    """Build a compact text summary of all property data for the AI prompt."""
    lines = [f"Property: {data.get('property_name', property_id)} ({property_id})"]

    # Occupancy
    occ = data.get("occupancy", {})
    if occ:
        lines.append(f"\nOCCUPANCY: {occ.get('total_units', 0)} total units, "
                      f"{occ.get('occupied_units', 0)} occupied ({occ.get('physical_occupancy', 0)}%), "
                      f"{occ.get('vacant_units', 0)} vacant, "
                      f"{occ.get('leased_percentage', 0)}% leased, "
                      f"{occ.get('aged_vacancy_90_plus', 0)} aged 90+ days, "
                      f"{occ.get('notice_break_units', 0)} on notice")

    # Pricing
    pricing = data.get("pricing", {})
    if pricing:
        lines.append(f"\nPRICING: In-place ${pricing.get('total_in_place_rent', 0):,.0f}, "
                      f"Asking ${pricing.get('total_asking_rent', 0):,.0f}, "
                      f"{pricing.get('unit_count', 0)} unit types")

    # Delinquency
    delinq = data.get("delinquency", {})
    if delinq and delinq.get("total_delinquent", 0) > 0:
        lines.append(f"\nDELINQUENCY: ${delinq.get('total_delinquent', 0):,.0f} total delinquent, "
                      f"{delinq.get('delinquent_units', 0)} units, "
                      f"Current ${delinq.get('current', 0):,.0f}, "
                      f"30-day ${delinq.get('over_30', 0):,.0f}, "
                      f"60-day ${delinq.get('over_60', 0):,.0f}, "
                      f"90+ ${delinq.get('over_90', 0):,.0f}")

    # Expirations
    expirations = data.get("expirations", {})
    periods = expirations.get("periods", [])
    if periods:
        exp_parts = []
        for p in periods:
            exp_parts.append(f"{p['label']}: {p['expirations']} expiring, {p['renewals']} renewed ({p['renewal_pct']}%)")
        lines.append(f"\nLEASE EXPIRATIONS: " + "; ".join(exp_parts))

    # Funnel
    funnel = data.get("funnel", {})
    if funnel:
        lines.append(f"\nLEASING FUNNEL (L30): {funnel.get('leads', 0)} leads, "
                      f"{funnel.get('tours', 0)} tours, "
                      f"{funnel.get('applications', 0)} applications, "
                      f"{funnel.get('lease_signs', 0)} leases signed, "
                      f"Lead-to-lease {funnel.get('lead_to_lease_rate', 0)}%")

    # Trade-outs
    tradeouts = data.get("tradeouts", {})
    summary = tradeouts.get("summary", {})
    if summary and summary.get("count", 0) > 0:
        lines.append(f"\nTRADE-OUTS: {summary['count']} recent, "
                      f"avg prior ${summary.get('avg_prior_rent', 0):,.0f} → "
                      f"new ${summary.get('avg_new_rent', 0):,.0f} "
                      f"({summary.get('avg_pct_change', 0):+.1f}%)")

    # Loss to lease
    ltl = data.get("loss_to_lease", {})
    if ltl and ltl.get("data_available"):
        lines.append(f"\nLOSS TO LEASE: {ltl.get('loss_to_lease_pct', 0)}% "
                      f"(${ltl.get('total_loss_to_lease', 0):,.0f}/mo gap, "
                      f"${ltl.get('loss_per_unit', 0):,.0f}/unit)")

    # Risk scores
    risk = data.get("risk_scores", {})
    if risk and risk.get("total_scored", 0) > 0:
        churn = risk.get("churn", {})
        delinq_risk = risk.get("delinquency", {})
        lines.append(f"\nRISK SCORES: {risk.get('total_scored', 0)} residents scored, "
                      f"Churn: {churn.get('high_risk', 0)} high-risk / {churn.get('medium_risk', 0)} medium / {churn.get('low_risk', 0)} low, "
                      f"Delinquency: {delinq_risk.get('high_risk', 0)} high-risk / {delinq_risk.get('medium_risk', 0)} medium")

    # Shows
    shows = data.get("shows", {})
    if shows:
        lines.append(f"\nSHOWS (L7): {shows.get('total_shows', 0)} tours in last 7 days")

    return "\n".join(lines)
