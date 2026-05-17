"""
Project progress log - accumulates the actual cost of each completed volume
analysis so the S-curve can plot a real "actual" cumulative line.

Each completed drone survey is treated as one reporting period: the Nth
completed survey supplies the actual value for period N.
"""

import json
import os
from datetime import datetime

PROGRESS_FILE = os.path.join("results", "progress_log.json")


def load_progress():
    """Return the list of recorded survey results (oldest first)."""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE) as f:
                return json.load(f)
        except Exception:
            return []
    return []


def record_progress(task_id, cost, volume_m3):
    """Append a completed survey's result to the progress log."""
    log = load_progress()
    log.append({
        "task_id": task_id,
        "date": datetime.now().isoformat(),
        "cost": round(float(cost or 0.0), 2),
        "volume_m3": round(float(volume_m3 or 0.0), 2),
    })
    os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
    with open(PROGRESS_FILE, "w") as f:
        json.dump(log, f, indent=2)
    return log


def actual_cumulative():
    """Running cumulative actual cost, one value per completed survey."""
    cumulative, total = [], 0.0
    for entry in load_progress():
        total += entry.get("cost", 0.0)
        cumulative.append(round(total, 2))
    return cumulative
