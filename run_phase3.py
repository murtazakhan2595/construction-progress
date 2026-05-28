"""
Phase 3 runner - submit the local Before/After drone sets straight to the
analyzer, skipping the Flask upload form. Used for the end-to-end pipeline
test on real drone data.

Usage:
    python run_phase3.py
    python run_phase3.py --before-task-id <uuid>           # skip BEFORE upload
    python run_phase3.py --before-task-id <uuid> --after-task-id <uuid>
"""

import argparse
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from finalV2 import ConstructionVolumeAnalyzer, task_status_store

BEFORE_DIR = r"d:\temp\zapru\Before"
AFTER_DIR = r"d:\temp\zapru\After"

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".tif", ".tiff")


def collect(folder):
    return sorted(
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.lower().endswith(IMAGE_EXTS)
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--before-task-id", default=None,
                        help="Resume an in-progress BEFORE WebODM task")
    parser.add_argument("--after-task-id", default=None,
                        help="Resume an in-progress AFTER WebODM task")
    parser.add_argument("--before-step", type=int, default=1,
                        help="Use every Nth BEFORE image (default 1 = all)")
    parser.add_argument("--after-step", type=int, default=1,
                        help="Use every Nth AFTER image (default 1 = all)")
    parser.add_argument("--before-limit", type=int, default=0,
                        help="Use only the first N (consecutive) BEFORE images")
    parser.add_argument("--after-limit", type=int, default=0,
                        help="Use only the first N (consecutive) AFTER images")
    args = parser.parse_args()

    before = collect(BEFORE_DIR)[::max(1, args.before_step)]
    after = collect(AFTER_DIR)[::max(1, args.after_step)]
    # Consecutive subset keeps image overlap intact (needed for photogrammetry)
    if args.before_limit:
        before = before[:args.before_limit]
    if args.after_limit:
        after = after[:args.after_limit]
    print(f"Before: {len(before)} images from {BEFORE_DIR}")
    print(f"After:  {len(after)} images from {AFTER_DIR}")
    if not before or not after:
        print("Image folders are empty - aborting.")
        return 1

    task_id = str(uuid.uuid4())
    print(f"Task ID: {task_id}")
    if args.before_task_id:
        print(f"Resuming BEFORE WebODM task {args.before_task_id}")
    if args.after_task_id:
        print(f"Resuming AFTER WebODM task {args.after_task_id}")
    print("Starting pipeline. WebODM photogrammetry typically takes "
          "30-90 minutes PER set (so plan for 1-3 hours total).")

    analyzer = ConstructionVolumeAnalyzer(task_id)
    ok = analyzer.process_construction_analysis(
        before, after, None,
        {"dem_resolution": 0.1, "mesh_resolution": "high",
         "volume_method": "dem_diff"},
        before_task_id=args.before_task_id,
        after_task_id=args.after_task_id,
    )

    print()
    print("Pipeline complete. success=", ok)
    status = task_status_store.get(task_id, {})
    print("Final status:", status.get("status"))
    print("Message:    ", status.get("message"))
    data = status.get("data") or {}
    if "volume_change" in data:
        print(f"Volume change: {data['volume_change']:.3f} m^3")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
