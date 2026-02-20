"""
Watchpoint Service - User-defined metric watchpoints for AI monitoring.
Stores watchpoints in a JSON file per property. READ/WRITE.

Watchpoint structure:
{
    "id": "wp_123",
    "metric": "occupancy_pct",
    "operator": "lt",        # lt, gt, eq
    "threshold": 90.0,
    "label": "Occupancy below 90%",
    "enabled": true,
    "created_at": "2026-02-14T12:00:00"
}
"""
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

WATCHPOINTS_PATH = Path(__file__).parent.parent / "db" / "data" / "watchpoints.json"

# Available metrics that can be watched
AVAILABLE_METRICS = {
    "occupancy_pct": {"label": "Occupancy %", "unit": "%", "direction": "higher_better"},
    "vacant_units": {"label": "Vacant Units", "unit": "units", "direction": "lower_better"},
    "delinquent_total": {"label": "Total Delinquent $", "unit": "$", "direction": "lower_better"},
    "delinquent_units": {"label": "Delinquent Units", "unit": "units", "direction": "lower_better"},
    "renewal_rate": {"label": "Renewal Rate %", "unit": "%", "direction": "higher_better"},
    "avg_rent": {"label": "Avg In-Place Rent", "unit": "$", "direction": "higher_better"},
    "loss_to_lease_pct": {"label": "Loss-to-Lease %", "unit": "%", "direction": "lower_better"},
    "atr": {"label": "ATR (Units)", "unit": "units", "direction": "lower_better"},
    "atr_pct": {"label": "ATR %", "unit": "%", "direction": "lower_better"},
    "aged_vacancy_90": {"label": "Aged Vacancy 90+ Days", "unit": "units", "direction": "lower_better"},
    "response_rate": {"label": "Review Response Rate %", "unit": "%", "direction": "higher_better"},
    "overall_rating": {"label": "Overall Rating", "unit": "stars", "direction": "higher_better"},
    "google_rating": {"label": "Google Rating", "unit": "stars", "direction": "higher_better"},
    "on_notice_units": {"label": "Units on Notice", "unit": "units", "direction": "lower_better"},
    "lead_to_lease": {"label": "Lead-to-Lease %", "unit": "%", "direction": "higher_better"},
}

OPERATORS = {
    "lt": "<",
    "gt": ">",
    "lte": "≤",
    "gte": "≥",
    "eq": "=",
}


def _load_watchpoints() -> Dict[str, List[dict]]:
    """Load all watchpoints keyed by property_id."""
    if WATCHPOINTS_PATH.exists():
        try:
            return json.loads(WATCHPOINTS_PATH.read_text())
        except Exception:
            return {}
    return {}


def _save_watchpoints(data: Dict[str, List[dict]]):
    """Save watchpoints to disk."""
    try:
        WATCHPOINTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        WATCHPOINTS_PATH.write_text(json.dumps(data, indent=2))
    except Exception as e:
        logger.error(f"[WATCHPOINTS] Failed to save: {e}")


def get_watchpoints(property_id: str) -> List[dict]:
    """Get all watchpoints for a property."""
    data = _load_watchpoints()
    return data.get(property_id, [])


def add_watchpoint(property_id: str, metric: str, operator: str, threshold: float, label: Optional[str] = None) -> dict:
    """Add a new watchpoint for a property."""
    if metric not in AVAILABLE_METRICS:
        raise ValueError(f"Unknown metric: {metric}. Available: {list(AVAILABLE_METRICS.keys())}")
    if operator not in OPERATORS:
        raise ValueError(f"Unknown operator: {operator}. Available: {list(OPERATORS.keys())}")

    meta = AVAILABLE_METRICS[metric]
    if not label:
        label = f"{meta['label']} {OPERATORS[operator]} {threshold}{meta['unit']}"

    wp = {
        "id": f"wp_{uuid.uuid4().hex[:8]}",
        "metric": metric,
        "operator": operator,
        "threshold": threshold,
        "label": label,
        "enabled": True,
        "created_at": datetime.now().isoformat(),
    }

    data = _load_watchpoints()
    data.setdefault(property_id, []).append(wp)
    _save_watchpoints(data)
    return wp


def remove_watchpoint(property_id: str, watchpoint_id: str) -> bool:
    """Remove a watchpoint by ID."""
    data = _load_watchpoints()
    wps = data.get(property_id, [])
    before = len(wps)
    data[property_id] = [w for w in wps if w["id"] != watchpoint_id]
    if len(data[property_id]) < before:
        _save_watchpoints(data)
        return True
    return False


def toggle_watchpoint(property_id: str, watchpoint_id: str) -> Optional[dict]:
    """Toggle a watchpoint's enabled state."""
    data = _load_watchpoints()
    for wp in data.get(property_id, []):
        if wp["id"] == watchpoint_id:
            wp["enabled"] = not wp["enabled"]
            _save_watchpoints(data)
            return wp
    return None


def evaluate_watchpoints(property_id: str, current_metrics: Dict[str, float]) -> List[dict]:
    """
    Evaluate watchpoints against current metric values.
    Returns list of watchpoints with their current status (triggered/ok).
    """
    wps = get_watchpoints(property_id)
    results = []

    for wp in wps:
        if not wp.get("enabled", True):
            results.append({**wp, "status": "disabled", "current_value": None})
            continue

        metric = wp["metric"]
        current = current_metrics.get(metric)

        if current is None:
            results.append({**wp, "status": "no_data", "current_value": None})
            continue

        op = wp["operator"]
        threshold = wp["threshold"]

        triggered = False
        if op == "lt" and current < threshold:
            triggered = True
        elif op == "gt" and current > threshold:
            triggered = True
        elif op == "lte" and current <= threshold:
            triggered = True
        elif op == "gte" and current >= threshold:
            triggered = True
        elif op == "eq" and current == threshold:
            triggered = True

        results.append({
            **wp,
            "status": "triggered" if triggered else "ok",
            "current_value": current,
        })

    return results


def format_watchpoints_for_ai(property_id: str, current_metrics: Dict[str, float]) -> str:
    """Format evaluated watchpoints as text for the AI insights prompt."""
    evaluated = evaluate_watchpoints(property_id, current_metrics)
    if not evaluated:
        return ""

    lines = ["\nCUSTOM WATCHPOINTS (user-defined alerts):"]
    for wp in evaluated:
        meta = AVAILABLE_METRICS.get(wp["metric"], {})
        status_icon = "🔴" if wp["status"] == "triggered" else "🟢" if wp["status"] == "ok" else "⚪"
        current_str = f" (current: {wp['current_value']}{meta.get('unit', '')})" if wp.get("current_value") is not None else ""
        lines.append(f"  {status_icon} {wp['label']}{current_str} — {wp['status'].upper()}")

    return "\n".join(lines)
