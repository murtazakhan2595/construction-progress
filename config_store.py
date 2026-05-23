"""
Configuration store - persisted user-editable settings.

  rates.json         user-editable unit rates per road layer (Rs per unit)
  project_plan.json  user-editable project plan (name, budget, schedule)

Rates and the plan are edited from the Settings panel in the web UI and
loaded by the cost / S-curve modules at analysis time.
"""

import json
import os

from road_layers import ROAD_LAYERS

RATES_FILE = "rates.json"
PLAN_FILE = "project_plan.json"


# ----- Rates ---------------------------------------------------------------

def _defaults_rates():
    """Default rate per class ID, taken from the canonical road-layer table."""
    return {cid: float(item["rate"]) for cid, item in ROAD_LAYERS.items()}


def get_rates():
    """Return {class_id: rate} - user-edited rates with sensible fallbacks."""
    rates = _defaults_rates()
    if os.path.exists(RATES_FILE):
        try:
            with open(RATES_FILE) as f:
                stored = json.load(f)
            for k, v in stored.items():
                try:
                    rates[int(k)] = float(v)
                except (TypeError, ValueError):
                    pass
        except Exception:
            pass
    return rates


def save_rates(rates):
    """Persist {class_id: rate}. Accepts dict with int or str keys."""
    payload = {}
    for k, v in (rates or {}).items():
        try:
            payload[str(int(k))] = float(v)
        except (TypeError, ValueError):
            continue
    with open(RATES_FILE, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


def rates_table():
    """Rate list enriched with layer name + unit, for the settings UI."""
    rates = get_rates()
    return [
        {
            "class_id": cid,
            "name": item["name"],
            "unit": item["unit"],
            "rate": rates.get(cid, item["rate"]),
        }
        for cid, item in ROAD_LAYERS.items()
    ]


# ----- Project plan --------------------------------------------------------

PLAN_DEFAULTS = {
    "project_name": "Road Construction Project",
    "currency": "PKR",
    "total_budget": 0,
    "period_labels": [],
    "planned_cumulative": [],
}


def get_plan():
    """Return the project plan with all required keys populated."""
    plan = {}
    if os.path.exists(PLAN_FILE):
        try:
            with open(PLAN_FILE) as f:
                plan = json.load(f)
        except Exception:
            plan = {}
    out = dict(PLAN_DEFAULTS)
    out.update({k: v for k, v in plan.items() if k in PLAN_DEFAULTS})
    return out


def save_plan(plan):
    """Persist the project plan after coercing fields to expected types."""
    payload = dict(PLAN_DEFAULTS)
    if isinstance(plan, dict):
        for k, v in plan.items():
            if k in PLAN_DEFAULTS:
                payload[k] = v
    try:
        payload["total_budget"] = float(payload.get("total_budget") or 0)
    except (TypeError, ValueError):
        payload["total_budget"] = 0
    if not isinstance(payload.get("period_labels"), list):
        payload["period_labels"] = []
    if not isinstance(payload.get("planned_cumulative"), list):
        payload["planned_cumulative"] = []
    with open(PLAN_FILE, "w") as f:
        json.dump(payload, f, indent=2)
    return payload
