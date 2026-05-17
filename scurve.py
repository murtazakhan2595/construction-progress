"""
S-curve generation: planned vs actual cumulative cost over the project timeline.

The planned schedule comes from project_plan.json (supplied by the project
owner). If no explicit planned curve is given, a standard logistic S-curve
baseline is generated from the total budget and the number of periods.

The actual curve accumulates from completed volume analyses (see progress.py).
"""

import math

import matplotlib
matplotlib.use("Agg")  # headless backend - no display needed
import matplotlib.pyplot as plt


def generate_planned_curve(total_budget, num_periods):
    """Standard logistic (S-shaped) planned cumulative-cost curve.

    Returns a list of cumulative planned cost, one value per period, ending
    exactly at total_budget.
    """
    if num_periods <= 0:
        return []
    curve = []
    for i in range(1, num_periods + 1):
        x = (i / num_periods) * 12 - 6  # spread the logistic over -6..+6
        curve.append(total_budget * (1 / (1 + math.exp(-x))))
    scale = total_budget / curve[-1] if curve[-1] else 1
    return [round(v * scale, 2) for v in curve]


def build_scurve(planned_cumulative, actual_cumulative, period_labels=None):
    """Combine planned and actual cumulative cost into S-curve data.

    planned_cumulative - cumulative planned cost per period
    actual_cumulative  - cumulative actual cost per period (may be shorter:
                         the project is still in progress)

    Returns {"rows": [...], "summary": {...}}.
    """
    n = len(planned_cumulative)
    if period_labels is None or len(period_labels) != n:
        period_labels = [f"Period {i + 1}" for i in range(n)]

    rows = []
    for i in range(n):
        planned = planned_cumulative[i]
        actual = actual_cumulative[i] if i < len(actual_cumulative) else None
        variance = round(actual - planned, 2) if actual is not None else None
        rows.append({
            "period": period_labels[i],
            "planned": planned,
            "actual": actual,
            "variance": variance,
        })

    # Schedule status at the latest period that has actual data
    latest = None
    for row in rows:
        if row["actual"] is not None:
            latest = row

    summary = {}
    if latest:
        planned = latest["planned"] or 0
        actual = latest["actual"] or 0
        spi = round(actual / planned, 3) if planned else 0.0
        summary = {
            "latest_period": latest["period"],
            "planned_to_date": planned,
            "actual_to_date": actual,
            "variance": latest["variance"],
            "performance_index": spi,  # >1 ahead, <1 behind schedule
            "status": ("ahead of schedule" if spi > 1.02
                       else "behind schedule" if spi < 0.98
                       else "on schedule"),
        }
    return {"rows": rows, "summary": summary}


def render_scurve_png(scurve, output_path, currency="PKR"):
    """Render the S-curve to a PNG file. Returns output_path."""
    rows = scurve.get("rows", [])
    if not rows:
        return None

    labels = [r["period"] for r in rows]
    planned = [r["planned"] for r in rows]
    actual = [r["actual"] for r in rows]
    # Only plot the actual line up to the periods that have data
    actual_x = [i for i, v in enumerate(actual) if v is not None]
    actual_y = [actual[i] for i in actual_x]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(range(len(labels)), planned, "o-", color="#3498db",
            linewidth=2, label="Planned")
    if actual_y:
        ax.plot(actual_x, actual_y, "s-", color="#e67e22",
                linewidth=2, label="Actual")
    ax.set_title("Project S-Curve - Planned vs Actual")
    ax.set_xlabel("Period")
    ax.set_ylabel(f"Cumulative Cost ({currency})")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=110)
    plt.close(fig)
    return output_path
