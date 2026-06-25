# Handoff Document — Construction Volume Analysis Project

> This document is a complete context dump intended to be fed to a new AI chat
> so it can pick up exactly where the previous session left off. Read it
> top-to-bottom before doing anything; everything you need is here.

---

## 1. Who & what

**Project owner:** Rozi Khan (MS thesis student). His thesis title:
*"Automating the Project Monitoring System for Roads, Highway, and
Infrastructure Projects using Machine Learning, AI, Web Application, and
Digital Twin Techniques."*

**Operator (the user you're talking to):** Ahmed Murtaza
(`murtazakhan2595@gmail.com`). He is helping his friend Rozi complete this
project. The user is **not the thesis owner** — he is the developer assisting.
Plan to hand the running app + repo back to Rozi.

**Project:** A web app that takes before/after drone imagery of a road
construction site → runs photogrammetry → computes earthwork volume → applies
unit rates to produce a Bill of Quantities → tracks progress against a planned
S-curve → exports an Excel report. Currency is PKR (Pakistani Rupees).

---

## 2. Where everything lives

### Local workspace (Windows 11 Pro, 40 GB RAM laptop)

```
d:/temp/zapru/
├── 15 Jun 2026 Data Capture/   # 81 drone images, NEW (~3.8 GB)
├── After/                       # 161 drone images, Dec 29 2025 (1.4 GB)
├── Before/                      # 85 drone images, Dec 25 2025 (705 MB)
├── Rozi Khan/
│   └── construction_progress/   # THE PROJECT (git repo + .venv)
└── WebODM/                      # WebODM clone (Docker stack)
```

The "Rozi Khan/construction_progress" nesting is cosmetic — VSCode held a
file lock and we couldn't flatten it. Functionally harmless.

### GitHub

- **origin** (user's repo, push here): `https://github.com/murtazakhan2595/construction-progress.git`
- **upstream** (friend's original): `https://github.com/Rozi1/Contsruction_Volume_Analysis.git`
- Branch: `main`
- Last commits cover Phases 0–7 + Settings UI + geo-aware volume calc + pipeline streamline + sample demo data

### Environment

| Component | Version / Path |
|---|---|
| Python | 3.12.6 (venv at `.venv/`) |
| Docker | 29.2.1 (Docker Desktop on Windows) |
| WebODM | latest cloned at `d:/temp/zapru/WebODM/` |
| CloudCompare | 2.13.2 (`C:\Program Files\CloudCompare\CloudCompare.exe`) |
| WSL2 memory | **28 GB** (bumped from default 16 GB — this matters, see §7) |
| Git Bash | available; PowerShell also used |
| Shell habit | tools talk Git Bash POSIX or PowerShell, not cmd |

`.wslconfig` at `C:\Users\Murtaza\.wslconfig`:
```ini
[wsl2]
memory=28GB
swap=16GB
processors=6
[boot]
command="hwclock -s"
```

---

## 3. The pipeline — how it works end-to-end

```
1. UPLOAD          User opens http://localhost:5000, picks mode:
                   • "Start Fresh"  → upload before/after drone images
                   • "Use Existing" → upload pre-computed before/after DSMs
                          │
2. PHOTOGRAMMETRY  WebODM (Docker, :8000) turns each image set into a 3D
   (WebODM)        model: point cloud (.laz), DSM (.tif), DTM, orthophoto
                          │
3. DOWNLOAD        App pulls the DSMs (skips re-download if already on disk)
                          │
4. VOLUME          Geo-aware rasterio calc: aligns before/after DSMs by real
                   world coords, reprojects onto a common grid capped at
                   2500×2500 (memory-safe), differences the overlap →
                   net / cut / fill volume (m³)
                          │
5. DETECTION       YOLOv8 labels road layers on the images
   (YOLO)          (generic COCO model for now; custom road-layer model
                    pluggable via YOLO_MODEL_PATH env var)
                          │
6. COST            volume × unit rate per detected layer → Bill of Quantities
                          │
7. S-CURVE         Planned (from project_plan.json) vs Actual (accumulated
                   surveys via progress.py), with deviation + performance index
                          │
8. REPORT          JSON report + S-curve PNG + downloadable Excel workbook;
                   every run saved & viewable at /runs and /?task=<id>
```

---

## 4. Files & their roles

### Backend code

| File | Role |
|---|---|
| `finalV2.py` | Flask app + `ConstructionVolumeAnalyzer` (the whole pipeline). Big file, ~1500 lines. |
| `road_layers.py` | 12 canonical road-layer definitions (name, unit, rate, thickness). Class IDs 0–11. |
| `cost.py` | `build_boq()` — splits volume across detected layers by detection bbox area, applies rates. |
| `scurve.py` | Planned-vs-actual S-curve math + matplotlib chart renderer. |
| `progress.py` | Reads/writes `results/progress_log.json` (accumulates actual cost across surveys). |
| `report_excel.py` | Excel export (Summary + BOQ + S-Curve sheets with embedded line chart). |
| `config_store.py` | Reads/writes user-editable rates + project plan; falls back to road_layers defaults. |
| `run_phase3.py` | CLI harness for headless pipeline runs. Supports `--before-task-id`/`--after-task-id` to resume, `--before-limit`/`--after-limit` for consecutive subsets, `--before-step`/`--after-step` for every-Nth subsets. |

### Frontend

| File | Role |
|---|---|
| `templates/construction_volume.html` | Main UI: Settings panel (rates + project plan), mode selector (Fresh / Existing 3D Data), upload form, progress bar, results section, BOQ table, S-curve image, Excel & JSON download buttons. |
| `templates/runs.html` | Past Analyses listing (`/runs`). |

### Config

| File | What |
|---|---|
| `project_plan.json` | Project plan (tracked in git). Currently: "N-25 Highway - Lahore-Multan Section (Phase 1)", 50M PKR, 12 months, explicit S-curve baseline. Editable from Settings panel. |
| `rates.json` | User-edited rates per class ID (gitignored — user data). Created by Settings panel. Falls back to `road_layers.py` defaults when missing. |
| `requirements.txt` | flask, requests, ultralytics, opencv-python, numpy, openpyxl, matplotlib (rasterio installed manually but not yet in requirements.txt — add it). |
| `.gitignore` | venv, __pycache__, *.log, uploads/ results/ dems/ meshes/ point_clouds/ downloaded_assets/* excluded, rates.json excluded. |
| `Methodology.pdf` | Friend's methodology diagram. Single page. |
| `processing_node detailts.json` | WebODM/ODM valid options reference. |

### Docs

| File | Purpose |
|---|---|
| `plan.md` | The 8-phase completion plan with status. |
| `README.md` | App overview + setup. |
| `QUICKSTART.md` | 5-step setup for the friend. |
| `YOLO_TRAINING_GUIDE.md` | (legacy from original repo) covers YOLO training. |
| `HANDOFF.md` | this document. |
| `_archive/` | Superseded earlier iterations of the friend's code. |

### Runtime data (gitignored)

| Folder | Contents |
|---|---|
| `uploads/` | User-uploaded images / DSMs |
| `downloaded_assets/` | WebODM-downloaded files (point clouds, DSM, DTM, orthophoto) |
| `results/` | Analysis JSON reports, S-curve PNGs, progress_log.json |
| `dems/`, `meshes/`, `point_clouds/`, `gcp_files/` | Intermediate, mostly unused now (we bypass mesh) |

### What's on disk right now (data we have)

```
downloaded_assets/before_566d273e-98c7-4bae-981a-f855d00685a1_dsm.tif        564 MB
downloaded_assets/before_566d273e-98c7-4bae-981a-f855d00685a1_dtm.tif        587 MB
downloaded_assets/before_566d273e-98c7-4bae-981a-f855d00685a1_orthophoto.tif 110 MB
downloaded_assets/before_566d273e-98c7-4bae-981a-f855d00685a1_georeferenced_model.laz  76 MB

downloaded_assets/after_2af8b20e-867e-4273-b0a6-1f11c54ba02f_dsm.tif         156 MB
downloaded_assets/after_2af8b20e-867e-4273-b0a6-1f11c54ba02f_dtm.tif         182 MB
downloaded_assets/after_2af8b20e-867e-4273-b0a6-1f11c54ba02f_orthophoto.tif  348 MB
downloaded_assets/after_2af8b20e-867e-4273-b0a6-1f11c54ba02f_georeferenced_model.laz   24 MB
```

- BEFORE: WebODM task `566d273e-98c7-4bae-981a-f855d00685a1` — full 85 images, completed.
- AFTER: WebODM task `2af8b20e-867e-4273-b0a6-1f11c54ba02f` — **subset of 20 consecutive images** (not the full 161). This is why we keep saying "small patch" — it covers a sub-region of the site.

---

## 5. Environment variables the app understands

| Var | Default | What |
|---|---|---|
| `WEBODM_URL` | `http://127.0.0.1:8000/api` | WebODM API base |
| `WEBODM_USER` | `admin` | WebODM auth |
| `WEBODM_PASSWORD` | `admin` | WebODM auth |
| `WEBODM_PROJECT_ID` | `1` | WebODM project ID |
| `WEBODM_TASK_TIMEOUT` | `21600` (6 h) | Max seconds to wait for a WebODM task |
| `YOLO_MODEL_PATH` | `yolov8n.pt` | Path to YOLO weights — set this to `best.pt` when trained model arrives |
| `YOLO_CONFIDENCE` | `0.25` | Detection confidence threshold |
| `ENABLE_AUTO_CLEANUP` | `0` (off) | Set to `1` to auto-delete old files |
| `CLEANUP_MAX_AGE_HOURS` | `720` (30 days) | Used only if ENABLE_AUTO_CLEANUP=1 |

---

## 6. Key URLs & commands

### URLs (when app + WebODM running)

| URL | What |
|---|---|
| `http://localhost:5000/` | Main UI |
| `http://localhost:5000/?task=<task_id>` | View a specific past analysis |
| `http://localhost:5000/runs` | List of past analyses |
| `http://localhost:5000/health` | JSON health probe |
| `http://localhost:5000/api/rates` | GET/POST rate list |
| `http://localhost:5000/api/plan` | GET/POST project plan |
| `http://localhost:5000/report-excel/<task_id>` | Excel download |
| `http://localhost:5000/result-file/<filename>` | Serve detection previews + S-curve PNGs |
| `http://localhost:8000/` | WebODM dashboard (`admin` / `admin`) |
| `http://localhost:8000/api/projects/1/tasks/` | WebODM task list |

### Commands

```bash
# Start the app (from project folder)
./.venv/Scripts/python.exe finalV2.py

# Start WebODM
cd ../../WebODM && ./webodm.sh start

# Stop WebODM (frees ~5+ GB of WSL memory)
cd ../../WebODM && ./webodm.sh stop

# Headless pipeline run
./.venv/Scripts/python.exe run_phase3.py                                # full 85 + 161
./.venv/Scripts/python.exe run_phase3.py --after-limit 20               # consecutive subset
./.venv/Scripts/python.exe run_phase3.py \
   --before-task-id 566d273e-98c7-4bae-981a-f855d00685a1 \
   --after-task-id 2af8b20e-867e-4273-b0a6-1f11c54ba02f                # resume existing tasks

# Pure-DSM run (no WebODM, ~1 min)
./.venv/Scripts/python.exe -c "
import uuid
from finalV2 import ConstructionVolumeAnalyzer
a = ConstructionVolumeAnalyzer(str(uuid.uuid4()))
a.process_existing_data(
    'downloaded_assets/before_566d273e-98c7-4bae-981a-f855d00685a1_dsm.tif',
    'downloaded_assets/after_2af8b20e-867e-4273-b0a6-1f11c54ba02f_dsm.tif')
"
```

---

## 7. Where we got stuck & how we got past it (so you don't repeat)

The last several days were spent unblocking the AFTER pipeline. Critical scars
the next AI should know about:

### 7.1 WebODM "Invalid options" 400 (fixed long ago)
- Cause: option `texturing-nadir-weight` was removed from newer ODM versions.
- Fix: removed that line from `submit_webodm_task`'s options payload. Verified
  with submission HTTP 201.

### 7.2 Route collision `/results/<task_id>` vs `/results/<filename>` (fixed)
- File-serving route renamed to `/result-file/<filename>`; `upload()` returns
  the new URL. Detection previews now load.

### 7.3 `/health` 500 (was environmental)
- Earlier returned 500 because WebODM/CloudCompare weren't installed yet. Now
  green when all services up.

### 7.4 WebODM crashing under load
- **Root cause: WSL2 memory was capped at 16 GB** in `.wslconfig`. WebODM
  meshing/texturing peaks above that on real image sets, OOM-kills the worker,
  Docker engine goes unresponsive.
- **Fix: bumped to 28 GB + 6 CPUs.** Verified: docker info → 27.4 GB,
  6 CPUs.
- **Still keep in mind:** if you run the FULL 161-image AFTER, even 28 GB may
  be tight. Best to do that on the friend's bigger machine.

### 7.5 Disk filled (Docker `docker_data.vhdx` ballooned to 120 GB)
- WebODM intermediate files are huge (~10–30 GB per task).
- Recovered by `docker system prune -f` (~15 GB reclaimed without losing the
  BEFORE task) and freeing C: drive space outside the vhdx. The vhdx grows
  dynamically up to ~166 GB now (46.9 GB free on C:).
- For a clean slate later: delete `C:\Users\Murtaza\AppData\Local\Docker\wsl\disk\docker_data.vhdx`
  after quitting Docker Desktop → reclaims all 120 GB. But this **wipes
  WebODM's DB** — BEFORE task ID will be gone. We have the BEFORE DSM saved
  on disk independently so we can still use "Use Existing 3D Data" mode.

### 7.6 5 every-40th images → "Cannot process dataset" (sampling bug, fixed)
- Sampling every-Nth image destroys overlap; ODM can't reconstruct.
- Fix: use **consecutive** images (`--after-limit N`) so frame-to-frame
  overlap is preserved.

### 7.7 "Failed to generate meshes" — the **big** fix
- The original code generated mesh from point cloud via CloudCompare DELAUNAY,
  then DEM from mesh, then volume. The mesh step kept failing.
- **Realization:** WebODM already produces DSM `.tif` files. We don't need
  the mesh detour at all — feed DSMs straight to volume.
- **Fix:** rewrote step 5 of `process_construction_analysis` to call
  `calculate_volume_from_dems(before_assets["dsm"], after_assets["dsm"])`
  directly. CloudCompare DEM-from-pointcloud kept only as fallback if a DSM
  is missing.
- The mesh/DEM-from-mesh methods are now **dead code** but I left them in
  place (~180 lines). Can be removed for cleanliness.

### 7.8 Volume math was geographically wrong (fixed)
- Initial rasterio code did a naive pixel-by-pixel subtraction. That only
  works if both DSMs share the exact same extent + grid (which they don't
  when AFTER covers a subregion of BEFORE).
- **Fix:** rewrote `calculate_volume_from_dems` to be geo-aware:
  - Computes overlap bounding box in world coords
  - Reprojects both DSMs onto a common grid capped at 2500×2500 (memory-safe)
  - Differences only the overlap; sums (a-b)·cell_area for volume
- Validated: identical DSMs → 0.0 m³. Real before/after → +14,899 m³ fill.

### 7.9 Auto-cleanup scheduler deleted our data (fixed)
- Original code ran `cleanup_old_files(max_age_hours=24)` on app start AND
  every hour. Silently deleted any file in `downloaded_assets/`, `results/`,
  etc. older than 24 h.
- It wiped the BEFORE DSM on an app restart. Re-downloaded fine.
- **Fix:** scheduler is now opt-in via `ENABLE_AUTO_CLEANUP=1`, default age
  bumped to 720 h. Off by default — won't bite the friend.

### 7.10 `np` UnboundLocalError inside `calculate_volume_from_dems` (fixed)
- The original GDAL fallback inside the function did `import numpy as np`,
  which made `np` function-local. Our new rasterio code earlier in the same
  function then couldn't access `np` (UnboundLocalError before assignment).
- **Fix:** use a local alias `import numpy as np_` in the rasterio block.

---

## 8. The real demo data currently in `/runs`

A real volume analysis is saved and visible right now (subject to whatever the
user has run since). Stable example values:

| Field | Value |
|---|---|
| Project | "N-25 Highway - Lahore-Multan Section (Phase 1)" |
| Net volume | +14,899.12 m³ (fill) |
| Cut / Fill | 0 / 14,899 m³ |
| BOQ total | PKR 6,704,603 |
| S-curve status | "ahead of schedule", PI 1.117 |
| Planned to date | PKR 6,000,000 (Month 1) |
| Actual to date | PKR 6,704,603 (Month 1) |

This is one survey: BEFORE = full 85-image WebODM task,
AFTER = 20-image consecutive subset (covers a small subregion).

---

## 9. What's done ✅

- Full environment (Docker, WebODM, CloudCompare, Python venv) on user's
  laptop.
- **Pipeline runs end-to-end in one shot** (with WebODM running) — verified.
- Geo-aware, memory-safe volume calc using rasterio.
- **Settings UI** — collapsible panel at top of the page with two cards:
  Project Plan (name, currency, total budget, period labels) and Rate List
  (all 12 layers, editable). Persisted via `/api/rates` and `/api/plan` →
  `rates.json` and `project_plan.json`.
- **"Use Existing 3D Data" mode** — upload pre-computed before/after DSM .tif
  files and skip WebODM entirely (~1 min runs). Backed by
  `/upload-existing` + `ConstructionVolumeAnalyzer.process_existing_data`.
- **Past-runs view** — `/runs` lists every `analysis_report_*.json`; click
  through to `/?task=<id>` to view a past run inline.
- BOQ, S-curve PNG, Excel export (Summary + BOQ + S-Curve sheets + embedded
  line chart), JSON report.
- Resume completed WebODM tasks via `--before-task-id`/`--after-task-id`;
  skip-existing-download.
- WSL memory fix + Docker prune for disk recovery.
- Sample demo data (N-25 highway, realistic PKR plan + rates).
- Auto-cleanup defused.
- All committed and pushed to GitHub.

---

## 10. What's pending ⏳

| Item | Owner | Notes |
|---|---|---|
| Trained YOLO road-layer model (`best.pt`) | Friend (Rozi), ~next month | Until then BOQ collapses to "Earthwork (unclassified)". Drop in via `YOLO_MODEL_PATH`. **User is now considering Gemini Vision as a faster alternative — see §11.** |
| Real unit rates | Friend | Placeholders are realistic PKR; editable in Settings. |
| Real project plan | Friend | Sample "N-25 Highway" plan in place; editable in Settings. |
| Full 161-image AFTER run | Us, on friend's beefier machine | We have a 20-image subset. Friend has GPU + more RAM. |
| Full end-to-end on friend's machine | Next session | User got remote desktop access — wants to do this. |
| 15 Jun 2026 third survey (81 images) | Need clarification from friend | Friend just shared this set. Likely a third time-point for surveying (not training). |
| Final docs polish + handover packaging | Us | Mostly done; QUICKSTART exists. |
| Orthomosaic display in UI | Discussed, not implemented | Would convert orthophoto.tif → JPG preview and show before/after side-by-side on results page. |
| Dead-code cleanup (mesh methods) | Optional | ~180 lines of unused mesh/DEM-from-mesh code, kept for safety. |

---

## 11. Open questions / decisions in flight

### YOLO training vs Gemini Vision (last live discussion)

User asked if Gemini could replace training a YOLO model. We agreed Gemini
is a great fit for his situation because:

- **No annotation work** — friend hasn't started, would take days/weeks
- **No GPU/training time**
- **Gemini 2.5 Flash** (or 2.0 Flash) is fast, cheap (~$0.01–0.05 / image),
  supports image input + JSON output + bounding boxes
- Plugs in by replacing only `detect_objects()` — downstream BOQ/S-curve
  unchanged

**Status:** waiting for user to grab a free API key from
[aistudio.google.com](https://aistudio.google.com/app/apikey) so I can wire
it up. Plan: add `gemini_detector.py` that wraps the Gemini call with a
structured prompt; branch in `detect_objects()` to use Gemini when
`GEMINI_API_KEY` is set, fall back to YOLO otherwise; map Gemini's text
layer names → our 12 class IDs via fuzzy match on `road_layers.py`.

If you, the next AI, get a Gemini key from the user — implement this.

### 15 Jun 2026 third survey

81 high-res images (~3.8 GB), DJI `_D.JPG` (different/larger sensor than the
Zenmuse L1 Dec sets — 43 MB JPEGs vs 8 MB). Likely meant as a **third
time-point for surveying**, not as training data. **Ask the friend** before
processing. If yes — run through WebODM (BEST on his machine) → two volume
deltas (Dec25→Dec29 and Dec29→Jun15) → S-curve with multiple actual points
(much better demo).

### Friend's machine setup (next concrete task user wants)

User has **remote desktop access** to friend's machine (GPU, more RAM, more
disk). Plan to:

1. Install Docker Desktop, CloudCompare, Python on friend's machine
2. Clone the repo, create venv, install requirements (add rasterio)
3. Start WebODM, create project, set admin/admin
4. If NVIDIA GPU: enable WebODM's GPU node for 5–10× faster photogrammetry
5. Run full BEFORE + AFTER + (if applicable) Jun 15 third survey
6. Verify result in the UI
7. Final docs polish; confirm friend can run solo from QUICKSTART.md

---

## 12. Honest limitations / caveats for the next AI

- **YOLO is decorative until a road-layer model arrives** — generic COCO
  detections show but `class_id` is forced to `None` in
  `detect_objects()`, so the BOQ shows one "Earthwork (unclassified)" line
  at the default rate. This is intentional — it prevents falsely mapping
  COCO class 7 ("truck") to road-layer class 7 ("Allied Kerb Stone").
- **Current volume is a 20-image patch**, not the full site. The full
  161-image AFTER WebODM run kept crashing this laptop (we fixed the
  underlying issues but never re-ran the full set). Friend's machine is the
  right place for that.
- **The S-curve has one real actual point.** With a third survey
  (15 Jun 2026), it would show three points and look much more compelling.
- **Several road-layer classes look identical from a drone** (asphalt
  wearing vs binder, sub-base vs aggregate base, prime vs tack coat). No
  detector — YOLO, Gemini, or human — can reliably distinguish them from
  aerial imagery. We recommended a merged 7-class scheme as a fallback
  (Earthwork / Granular Base / Bituminous Coat / Asphalt / Kerb Stone /
  Tuff Paver / RCC Drainage).
- **WebODM on Windows is fragile.** Beyond the WSL memory bump, it has a
  history of running out of disk inside the vhdx, going unresponsive after
  Docker hiccups, etc. The friend's machine (likely Linux + GPU) will be
  more reliable.

---

## 13. Conversational tone the user expects

- Direct, honest, no fluff
- Tells them when something is broken or risky before doing it
- Uses tables and structure, not big paragraphs
- Explains *why* he made a choice, not just *what*
- Mentions exact file paths and line numbers when relevant
- Confirms destructive actions (deletes, force pushes) before doing them
- Per-phase git commits with Co-Authored-By: Claude

User is comfortable with technical content and wants you to lead, not
hand-hold. He's running low on patience for cycles — get to the point and act.

---

## 14. Immediate next actions (suggested order)

When user resumes:

1. **Ask:** is the Jun 15 capture for surveying (3rd time-point) or YOLO
   training data? — confirms approach
2. **Ask:** has he gotten a Gemini API key? If yes → wire up Gemini detector
3. **Move execution to friend's machine** (he has remote desktop)
   - Install Docker, CloudCompare, Python; clone repo; venv; deps
   - Start WebODM; create project; admin/admin
   - Add `rasterio` to requirements.txt (currently missing — installed manually)
   - Run full BEFORE + AFTER (+ Jun 15 if applicable)
   - Verify in UI
4. **Polish & handover**
   - Add orthomosaic display to the results page (described in §10)
   - Strip the dead mesh methods (~180 lines) if user wants
   - Update README / QUICKSTART with the Gemini env var if wired
   - Confirm friend can launch app + run a survey from QUICKSTART.md alone

---

## 15. One-paragraph elevator pitch (for context)

A Flask web app that ingests before/after drone images of a road construction
site, runs WebODM photogrammetry in Docker, computes a real cut/fill volume
from the resulting Digital Surface Models using a memory-safe geo-aware
rasterio calculation, applies user-editable PKR unit rates per road layer to
produce a Bill of Quantities, tracks progress against a planned S-curve, and
exports the whole result as an Excel workbook. YOLO road-layer detection is
wired in but the custom model isn't trained yet — we're considering Gemini
Vision as a faster alternative. Demo-ready today with a 20-image subset
showing +14,899 m³ fill / PKR 6,704,603 / "ahead of schedule"; full-site run
and final handover happen on the friend's beefier machine via remote desktop
in the next session.

---

*End of handoff. Read all 15 sections before doing anything. When you reply
to the user, lead — don't ask "what do you want to do?" — propose the next
concrete action from §14.*
