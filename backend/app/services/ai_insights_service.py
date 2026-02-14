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


INSIGHTS_PROMPT = """You are a senior multifamily asset manager with 15 years of experience. You think in terms of NOI impact, not platitudes. You are reviewing a property for an owner who already knows the basics — they can see their own dashboard. Your job is to surface what they'd MISS.

Produce EXACTLY this JSON (no markdown, no fences):

{"alerts":[{"severity":"high"|"medium"|"low","title":"Max 8 words","fact":"One sentence with specific numbers AND explicit time period (e.g. 'in L30', 'for Feb 2026').","risk":"Quantify the financial impact in $/month or $/year where possible.","action":"A specific, non-obvious action. Not 'monitor closely' or 'review trends'."}],"qna":[{"question":"...","answer":"2-3 sentences with numbers and explicit time periods."}]}

BANNED WORDS (never use these — replace with the exact timeframe from the data):
"recent", "recently", "lately", "currently", "current", "ongoing", "at this time", "as of now", "presently"

ANALYST RULES — this is what separates you from a junior:
1. CROSS-CORRELATE: If occupancy is low AND tours are low, that's a marketing/pricing problem. If occupancy is low but tours are high, that's a conversion problem. Say which.
2. QUANTIFY IN DOLLARS: "5 vacant units at $1,400/mo = $7,000/mo revenue gap" not "vacancy is concerning."
3. SKIP THE OBVIOUS: Never say "occupancy is X%" as an alert if it's already on the dashboard. Only flag it if it's anomalous (vs 94% benchmark) or combined with another signal.
4. BENCHMARK: Physical occupancy <93% is below market. Response rate <80% is below standard. Lead-to-lease <10% needs investigation. Delinquency >3% of gross rent is elevated.
5. FIND THE STORY: Connect 2-3 data points into a narrative. E.g., "High churn risk + expiring leases + negative trade-outs = potential revenue cliff in 60 days."
6. ACTIONS MUST BE SPECIFIC: "Offer $500 concession on 2BR units priced above $1,600" not "consider adjusting pricing." "Call the 5 residents with 90+ day delinquency balances" not "follow up on delinquencies."
7. EXPLICIT TIMEFRAMES: Never say "recent", "lately", "currently". Always state the exact period: "in the last 30 days", "for May 2026", "as of Feb 2026", "in the L30 leasing funnel". Match the timeframe labels from the data (L30 = last 30 days, CM = current month, etc.).
8. Generate 2-4 alerts (only real issues) and 3 Q&A pairs. Use ONLY provided numbers. No PII. No fabrication.

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
            max_tokens=1500,
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

        # Post-process: scrub banned vague timeframe words
        result = _scrub_vague_timeframes(result)

        _set_cached(property_id, result)
        logger.info(f"[AI-INSIGHTS] Generated {len(result['alerts'])} alerts, {len(result['qna'])} Q&A for {property_id}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"[AI-INSIGHTS] JSON parse error: {e}\nRaw: {raw[:500]}")
        return {"alerts": [], "qna": [], "error": "Failed to parse AI response"}
    except Exception as e:
        logger.error(f"[AI-INSIGHTS] Error: {e}")
        return {"alerts": [], "qna": [], "error": str(e)}


import re

_BANNED_REPLACEMENTS = [
    # Pattern → replacement (case-insensitive)
    (r'\brecent trade-outs\b', 'L30 trade-outs'),
    (r'\brecent leases\b', 'L30 leases'),
    (r'\brecent renewals\b', 'L30 renewals'),
    (r'\brecent months?\b', 'the last 30 days'),
    (r'\brecently\b', 'in the last 30 days'),
    (r'\brecent\b', 'L30'),
    (r'\blately\b', 'in the last 30 days'),
    (r'\bcurrently\b', 'as of this report'),
    (r'\bcurrent month\b', 'CM'),
    (r'\bcurrent\b', 'as of this report'),
    (r'\bongoing\b', 'as of this report'),
    (r'\bat this time\b', 'as of this report'),
    (r'\bas of now\b', 'as of this report'),
    (r'\bpresently\b', 'as of this report'),
]


def _scrub_vague_timeframes(result: dict) -> dict:
    """Replace banned vague timeframe words in all text fields."""
    def _scrub(text: str) -> str:
        for pattern, replacement in _BANNED_REPLACEMENTS:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text

    for alert in result.get("alerts", []):
        for key in ("title", "fact", "risk", "action"):
            if key in alert and isinstance(alert[key], str):
                alert[key] = _scrub(alert[key])
    for qa in result.get("qna", []):
        for key in ("question", "answer"):
            if key in qa and isinstance(qa[key], str):
                qa[key] = _scrub(qa[key])
    return result


def _build_data_summary(property_id: str, data: Dict[str, Any]) -> str:
    """Build a compact text summary of all property data for the AI prompt."""
    from datetime import datetime
    now = datetime.now()
    lines = [f"Property: {data.get('property_name', property_id)} ({property_id})",
             f"Report date: {now.strftime('%B %d, %Y')} | CM = {now.strftime('%B %Y')} | L30 = last 30 days | L7 = last 7 days"]

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

    # Trade-outs (filter to YTD to match dashboard view)
    tradeouts = data.get("tradeouts", {})
    all_tradeouts = tradeouts.get("tradeouts", [])
    if all_tradeouts:
        from datetime import datetime
        year_start = datetime(now.year, 1, 1) if 'now' in dir() else datetime(datetime.now().year, 1, 1)
        ytd = []
        for t in all_tradeouts:
            try:
                mid = t.get("move_in_date", "")
                d = datetime.strptime(mid, "%m/%d/%Y") if mid else None
                if d and d >= year_start:
                    ytd.append(t)
            except Exception:
                pass
        if ytd:
            avg_prior = sum(t.get("prior_rent", 0) for t in ytd) / len(ytd)
            avg_new = sum(t.get("new_rent", 0) for t in ytd) / len(ytd)
            avg_pct = sum(t.get("pct_change", 0) for t in ytd) / len(ytd)
            lines.append(f"\nTRADE-OUTS (YTD {now.year if 'now' in dir() else datetime.now().year}): {len(ytd)} trade-outs, "
                          f"avg prior ${avg_prior:,.0f} → new ${avg_new:,.0f} ({avg_pct:+.1f}%)")
        elif tradeouts.get("summary", {}).get("count", 0) > 0:
            s = tradeouts["summary"]
            lines.append(f"\nTRADE-OUTS (all-time, {s['count']} total): "
                          f"avg prior ${s.get('avg_prior_rent', 0):,.0f} → "
                          f"new ${s.get('avg_new_rent', 0):,.0f} ({s.get('avg_pct_change', 0):+.1f}%)")

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

    # Reputation / Reviews
    google_rev = data.get("google_reviews", {})
    apt_rev = data.get("apartments_reviews", {})
    if google_rev or apt_rev:
        parts = []
        if google_rev:
            parts.append(f"Google {google_rev.get('rating')}★ ({google_rev.get('review_count',0)} reviews, "
                         f"{google_rev.get('response_rate',0)}% responded, {google_rev.get('needs_response',0)} need reply)")
        if apt_rev:
            parts.append(f"Apartments.com {apt_rev.get('rating')}★ ({apt_rev.get('review_count',0)} reviews, "
                         f"{apt_rev.get('response_rate',0)}% responded, {apt_rev.get('needs_response',0)} need reply)")
        lines.append(f"\nREPUTATION: " + " | ".join(parts))

    # Custom watchpoints (WS8)
    watchpoint_text = data.get("watchpoint_summary", "")
    if watchpoint_text:
        lines.append(watchpoint_text)

    return "\n".join(lines)
