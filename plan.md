# Construction Volume Analysis — Completion Plan

**Project:** Automating the Project Monitoring System for Roads, Highway, and
Infrastructure Projects using Machine Learning, AI, Web Application, and Digital
Twin Techniques (MS Thesis).

**Repo:** github.com/Rozi1/Contsruction_Volume_Analysis
**Canonical app:** `finalV2.py` (Flask)
**Last updated:** 2026-05-17

---

## 1. What this project does

A web application that measures construction earthwork progress from drone
imagery and reports it as volume and cost.

End-to-end intended flow:

1. User uploads **before** and **after** drone image sets via the web UI.
2. **WebODM** processes each set via photogrammetry → point cloud, mesh, DEM/DSM/DTM.
3. **CloudCompare** compares the before/after surfaces → cut/fill volume difference.
4. **YOLOv8** identifies which road construction layer is present (custom model — pending).
5. App applies **predefined unit rates** → converts volume into cost (work done).
6. App generates an **Excel report** and an **S-curve** (planned vs actual, time vs cost)
   showing how far actual progress deviates from the plan.

This matches the 5-stage methodology: Data Acquisition → Data Processing →
AI Detection → Volume & Cost Calculation → Web Application.

---

## 2. Current state (analysis findings)

### Built and present (in `finalV2.py`)
- Flask web UI (`templates/construction_volume.html`) — uploads, options, progress, results.
- WebODM integration — submit task, poll status, download point cloud + DSM/DTM.
- CloudCompare integration — mesh → DEM → volume difference (multiple fallback methods).
- Cut/fill volume calculation + JSON analysis report.

### Broken (confirmed from code + run logs)
- **WebODM "Invalid options" 400** — options payload rejected; pipeline never completed a run.
- **`/results` route collision** — `/results/<task_id>` and `/results/<filename>` both
  defined; Flask uses the first, so detected preview images return 404.
- **`/health` returns 500** — bug in the health endpoint.
- No `requirements.txt` — dependencies undocumented.

### Missing entirely (described by friend, not in code)
- **YOLO road-layer detection** — only generic YOLO runs; no custom-model support or
  class→layer mapping. (Model will be trained by friend ~next month.)
- **Cost module** — no rate table, no cost calculation.
- **Excel report** — only JSON exists.
- **S-curve** — planned-vs-actual progress/cost chart absent.

### Other notes
- Older iteration files (`final.py`, `work.py`, `working.py`, `app.py`, `appv2.py`,
  `myapp.py`, `running.py`, `test.py`, `testV2.py`, `dem.py`, `process_webodm.py`)
  are superseded — archived under `_archive/`.
- WebODM needs **many overlapping drone photos per survey**, not single images.
- WebODM (Docker) and CloudCompare (desktop) are both **free/open-source** and must be
  installed locally to run the project.

---

## 3. Inputs required from project owner (Rozi Khan)

| Input | Needed for | Status |
|-------|-----------|--------|
| Drone image sets (overlapping, before & after) | Phase 3 | Pending |
| GCP files (optional, improves accuracy) | Phase 3 | Pending |
| Trained YOLO road-layer model (`best.pt`) | Phase 4 | ~Next month |
| Unit rate list (Rs per unit per road layer) | Phase 5 | Pending |
| Project plan/schedule (planned cost or progress over time) | Phase 6 | Pending |

---

## 4. Phase-by-phase plan

Estimated total: ~31–54 hours of active work (~4–7 working days). Phase 3 is the
biggest unknown — the CloudCompare volume chain has never produced a verified result.

### Phase 0 — Consolidate codebase  *(no external dependency)* — DONE
- [x] Write this `plan.md`.
- [x] Archive superseded iteration files into `_archive/`.
- [x] Create `requirements.txt`.
- [x] Add a clean `README.md` with run instructions.
- [x] Add `.gitignore`.

### Phase 1 — Environment setup  *(no external dependency)* — DONE
- [x] Install CloudCompare (desktop) — `C:\Program Files\CloudCompare\CloudCompare.exe`.
- [x] Docker Desktop running.
- [x] Install and start WebODM (5 containers up at localhost:8000);
      admin/admin; **project ID = 1**.
- [x] Recreate a clean Python venv (3.12.6) from `requirements.txt`.
- [ ] Verify `/health` shows WebODM + CloudCompare both reachable (after Phase 2 fix).

### Phase 2 — Fix core bugs  *(needs Phase 1)* — DONE
- [x] Fix WebODM `submit_webodm_task` options payload ("Invalid options").
      Root cause: option `texturing-nadir-weight` removed from newer ODM versions.
      Fix = dropped it. Verified: test submission now returns HTTP 201.
- [x] Resolve the `/results` route collision — file route renamed to
      `/result-file/<filename>`; `upload()` updated to match.
- [x] Fix the `/health` 500 error — was environmental (services were down);
      now returns 200 with WebODM + CloudCompare + YOLO all green.
- [x] Detected-image serving fixed via the route rename above.
- [x] WebODM URL / project ID / auth now read from environment variables
      (defaults: localhost:8000, admin/admin, project 1).

### Phase 3 — Volume pipeline end-to-end  *(needs Phase 2 + drone images)*
- [ ] Submit a real before/after drone set to WebODM successfully.
- [ ] Confirm point cloud + DSM/DTM download correctly.
- [ ] Run CloudCompare mesh → DEM → volume; get a correct cut/fill number.
- [ ] Verify the volume result is plausible; tune grid step / parameters.
- [ ] Surface cut volume, fill volume, net volume in the results UI.

### Phase 4 — YOLO road-layer detection  *(model deferred ~1 month)* — DONE
- [x] Configurable model path via `YOLO_MODEL_PATH` env var (defaults to generic
      `yolov8n.pt`; point it at the trained `best.pt` when ready).
- [x] Class-ID → road-layer mapping table (`road_layers.py`, 12 classes).
- [x] `detect_objects` returns structured detections and labels boxes with
      road-layer names when the custom model is loaded.
- [x] Plug-in point ready: drop in `best.pt`, set `YOLO_MODEL_PATH`, done.
      The custom model must be trained with classes in `road_layers.py` ID order.

### Phase 5 — Cost module  *(needs rate list)* — DONE
- [x] Editable unit-rate table — in `road_layers.py` (rates are PLACEHOLDERS;
      replace with the official BOQ rates from the project owner).
- [x] `cost.py` — `build_boq()` computes cost = quantity × rate; splits the
      measured volume across detected layers by detection bbox area.
- [x] BOQ table rendered on the results page; included in the analysis report.

### Phase 6 — S-curve & Excel reporting  *(needs project plan)* — DONE
- [x] `project_plan.json` — owner-supplied planned schedule (budget, periods,
      optional explicit planned curve). Owner must fill with the real plan.
- [x] `scurve.py` — planned vs actual S-curve + deviation/performance index;
      renders a chart PNG via matplotlib. `progress.py` accumulates actuals.
- [x] `report_excel.py` — Excel export (Summary, BOQ, S-Curve sheets + line
      chart) via `openpyxl`; served at `/report-excel/<task_id>`.
- [x] Results page shows the S-curve chart and an Excel download button.

### Phase 7 — Integrate, test, hand over  *(needs all above)*
- [ ] Wire every module into a single results view.
- [ ] Full end-to-end test run.
- [ ] Finalize `README.md` and a short user guide.
- [ ] Package and hand over to project owner.

---

## 5. Progress log

- 2026-05-17 — Analysis complete; plan created; Phase 0 complete (codebase
  consolidated, dead files archived, `requirements.txt` / `README.md` / `.gitignore`
  added).
- 2026-05-17 — Phase 1 complete: venv 3.12 + deps, CloudCompare installed,
  WebODM running (Docker), project ID = 1.
- 2026-05-17 — Phase 2 complete: WebODM options bug fixed (verified 201),
  route collision fixed, /health green, config env-driven.
- 2026-05-17 — Project consolidated; git commits for Phases 0-2.
  Phase 3 BLOCKED on drone image sets from project owner.
- 2026-05-17 — Phase 4 complete: `road_layers.py` table added, YOLO model
  path configurable, structured detections.
- 2026-05-17 — Phase 5 complete: `cost.py` BOQ builder, cost wired into the
  analysis report, BOQ table on results page.
- 2026-05-17 — Phase 6 complete: `scurve.py` + `progress.py` + `project_plan.json`
  + `report_excel.py`; S-curve chart and Excel export wired into the app and UI.
- 2026-05-23 — Drone images received (Before: 85, After: 161; DJI Zenmuse L1).
  Added user-editable Settings UI (rate list + project plan) backed by
  `config_store.py` and `/api/rates`, `/api/plan` endpoints. Fixed generic-YOLO
  detection so it no longer falsely maps COCO class IDs to road layers.
  Next: Phase 3 end-to-end with the real images.
