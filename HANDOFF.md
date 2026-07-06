# Handoff Document — Construction Volume Analysis Project

> This document is a complete context dump intended to be fed to a new AI chat
> so it can pick up exactly where the previous session left off. Read it
> top-to-bottom before doing anything; everything you need is here.

---

## 0. LATEST UPDATE — 2026-06-26 (custom YOLO model TRAINED)

The biggest open item (custom road-layer detector) is now **DONE**. The
Gemini-Vision alternative (old §11) is **abandoned** — not needed.

**Model:** `YOLO26s-seg` (instance segmentation, Ultralytics 8.4.78), trained
on the friend's (Engr. Zafar Khan's) RTX 3070 Ti Laptop GPU, 100 epochs (~22 min).

**Dataset:** Roboflow `engrs-workspace-bvswe / construction-progress-monitoring-ejrwd`,
version 3, exported in `yolo26` (segmentation) format. 422 images, 70/30 split
(295 train / 127 val), 3 classes.

**Classes (data.yaml order — DO NOT reorder):**
| ID | Name |
|----|------|
| 0 | Aggregate Base Course |
| 1 | Asphalt |
| 2 | Sub Base |

**Validation metrics (best.pt):**
| Class | Mask mAP50 | Mask mAP50-95 |
|-------|-----------|---------------|
| all | 0.961 | 0.847 |
| Aggregate Base Course | 0.978 | 0.899 |
| Asphalt | 0.990 | 0.952 |
| Sub Base | 0.913 | 0.689 |

Sub Base is the weakest (most instances, hardest to delineate) but usable.
Inference ~4–13 ms/image.

**Where it lives / how it loads:**
- Trained weights on Zafar's machine: `D:\Construction Progress Monitoring Yolo Trained\runs\segment\roadlayers\run1\weights\best.pt` (also backed up as `roadlayers_best.pt`).
- App expects it at `construction_progress\models\best.pt` — **auto-loaded** (no env var needed); falls back to generic YOLO if absent. `YOLO_MODEL_PATH` still overrides.

**Code changes made:**
- `road_layers.py` — collapsed from 12 layers to the 3 classes above (IDs match data.yaml). Rates are still PKR placeholders; replace with real BOQ.
- `finalV2.py` — `YOLO_MODEL_PATH` now defaults to `models\best.pt` when present.
- The app already auto-detects a road-layer model via `len(model.names) == NUM_CLASSES` (now 3), so detection flips to real layer names + BOQ attribution automatically.

**Training environment recipe (Zafar's machine, for reference):** Python 3.12
venv; `torch 2.6.0+cu124` (downloaded via resumable `curl` due to flaky net),
`torchvision 0.21.0+cu124`, `ultralytics 8.4.78`. Train cmd:
`yolo segment train model=yolo26s-seg.pt data=...\data.yaml epochs=100 imgsz=640 batch=-1 patience=20 device=0`.

**Current focus:** feed the freshly-generated DSMs (see §0.1) through the app's
volume → BOQ → S-curve pipeline, verify end-to-end, then hand over.

---

## 0.1 LATEST UPDATE — 2026-06-27 (WebODM DSMs generated on GPU)

All photogrammetry for the new dataset is DONE — produced on Zafar's RTX 3070 Ti.

### The real dataset structure (corrected)
The new survey is NOT one before/after pair. On Zafar's machine at
`D:\Master's Data\Masters Research Work\Drone Data\Data Simulation\` there are
**3 layer folders, each with Before + After**:

| Folder | Before (Jun 19) | After (Jun 24) |
|--------|-----------------|----------------|
| `Asphalt (SubBase)` | 46 | 45 |
| `Asphalt (ABC)` | 62 | 62 |
| `Asphalt (Prime Coat)` | 62 | 60 |

Filenames embed the date: **all "Before" = 20260619, all "After" = 20260624**.
So it's **one site, two flights, split into 3 sub-areas by layer** — i.e. **3
independent before→after volume measurements** over the same 5-day window, NOT a
cumulative time-chain (the dates contradict a SubBase→ABC→PrimeCoat sequence).
Same physical area confirmed within each pair. Images are huge: 12288×6912 (~55 MB each).

### WebODM on Windows — GPU is NOT supported via webodm.sh
`./webodm.sh --gpu` prints **"GPU support is not available for Windows"** and
silently falls back to CPU. The working approach (and what we used):
- Confirmed Docker GPU passthrough: `docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi` shows the card.
- Ran a **standalone GPU NodeODM** container:
  `docker run -d --gpus all --name nodeodm-gpu -p 40001:3000 opendronemap/nodeodm:gpu`
- Registered it in WebODM as a processing node → **node id 2**, `host.docker.internal:40001`, online.
- Submit tasks pinned to it: `processing_node=2, auto_processing_node=false`.
- CPU run took forever + OOM'd; GPU run = ~8 min each. ✅

### Environment (Zafar's machine)
- WebODM **3.2.6** cloned at `...\Data Simulation\WebODM` (path has spaces+apostrophe but worked). Started via `& "C:\Program Files\Git\bin\bash.exe" webodm.sh start`.
- `.wslconfig`: `memory=26GB`, `swap=24GB` (machine has 32 GB).
- WebODM project **"construction progress" = id 2**; admin/admin.
- ODM (node) version **3.5.6**.

### OOM lesson → memory-safe options (USE THESE for big images)
`pc-quality: high` OOM'd at 85% even at 24 GB on the 84 MP images. Working options:
`feature-quality: medium`, `pc-quality: medium`, `resize-to: 2048`,
`max-concurrency: 4`, `dsm: true`, `dtm: true`, `dem-resolution: 5`,
`orthophoto-resolution: 5` (resolutions are in **cm/px**; the old app value `0.1` was wrong units, though GSD-capped).

### Outputs
All 6 tasks COMPLETED on GPU. DSMs (+DTMs) downloaded to `dsm_outputs\` and
zipped as `dsm_outputs.zip` (~3 MB total — small because resize-to 2048 coarsened
GSD; valid GeoTIFFs). The 3 pairs for the volume step:
- `SubBase_Before_gpu_dsm.tif` ↔ `SubBase_After_dsm.tif`
- `ABC_Before_dsm.tif` ↔ `ABC_After_dsm.tif`
- `PrimeCoat_Before_dsm.tif` ↔ `PrimeCoat_After_dsm.tif`

### Helper scripts created on Zafar's machine (reusable)
- `submit_webodm.py <folder> <name> <project_id> <node_id>` — uploads w/ progress bar, memory-safe options, pins to GPU node.
- `webodm_status.py <pid> <task_id>` — polls one task.
- `status_all.py` — snapshot of all tasks in project 2.
- `download_dsm.py` — downloads dsm.tif+dtm.tif for every DONE task into `dsm_outputs\`.

### Next steps
1. Transfer `dsm_outputs.zip` + `best.pt` to the app machine (`d:\temp\zapru\...\construction_progress`); best.pt → `models\best.pt`.
2. Run each of the 3 before/after pairs through `process_existing_data` (or the UI "Use Existing 3D Data") → 3 volume deltas.
3. Verify YOLO detects the 3 layers + BOQ + S-curve + Excel.
4. Demo prep (3 saved runs → S-curve) and final handover to Zafar's machine.

---

## 0.2 LATEST UPDATE — 2026-06-28 (app integrated end-to-end + live-demo wiring)

The full pipeline now runs on the **operator's machine** (`d:\temp\zapru\...\construction_progress`)
end-to-end: YOLO detection + volume + BOQ + S-curve. Summary of everything done.

### Files now on the operator's machine
- `models\best.pt` — the trained YOLO26s-seg model (auto-loaded; 23 MB).
- `d:\temp\zapru\dsm_outputs\` — the 6 DSMs (3 before/after pairs) from WebODM.
- `d:\temp\zapru\yolo Check\` — detection sanity images (flat folder).
- `d:\temp\zapru\demo_images\{SubBase,ABC,PrimeCoat}\` — representative images per layer for detection.
- `d:\temp\zapru\detection_results\` — annotated detection outputs + before/after comparison images.

### Volume accuracy — Z-offset correction (IMPORTANT)
Raw volumes were ~100× too high (e.g. ABC 2036 m³ vs actual ~20). Root cause:
no GCPs → each before/after DSM is an independent reconstruction with an
arbitrary **vertical datum offset** (measured ~3.6 m on the ABC pair), summed
over the whole area. **Fix implemented** in `calculate_volume_from_dems`
(rasterio path): subtract the **median over-overlap elevation difference**
before integrating. Toggle via processing option `z_offset_correction`
(default True). Validated:
| Layer | Raw | Corrected | Actual |
|-------|-----|-----------|--------|
| ABC | 2036 m³ | 25.0 m³ | ~20 m³ ✓ |
| PrimeCoat | −3379 m³ | −0.6 m³ | ~0 (thin spray) ✓ |
| SubBase | 463 m³ | 6.5 m³ | (plausible, maybe low) |
Caveat: median-correction assumes some unchanged background; it can under-count
a uniform full-area lift. **Survey-grade volumes still need GCPs** (Min. 5 per
the methodology) — state this as a known limitation / future work.

### YOLO detection findings
- `detect_objects()` runs at the default **imgsz 640** — this is the right
  resolution (model trained on ~432 px Roboflow images). Higher imgsz hurt
  (0.98 conf at 640 → 0.29 at 1280).
- Strong on **training-style frames** (oblique road views, video frames):
  Asphalt 0.97–0.98, ABC 0.80–0.96, Sub Base 0.35–0.86.
- **Weak on raw 84 MP nadir frames** (the thesis _D.JPG sets) — a train/inference
  **domain gap**. To detect reliably on those, retrain with full-res frames added.
- First dataset Zafar sent had mislabeled folders; he sent a corrected set that
  detects cleanly. Detection ground-truth confirmed via `run_detection_check.py`.

### App code changes made
- `road_layers.py` — 3 classes (0=Aggregate Base Course, 1=Asphalt, 2=Sub Base).
- `finalV2.py`:
  - `YOLO_MODEL_PATH` auto-loads `models\best.pt`.
  - `calculate_volume_from_dems` — Z-offset (median) correction.
  - `submit_webodm_task` — now uses **memory-safe options** (feature-quality
    medium, pc-quality medium, resize-to 2048, max-concurrency 4, dsm/dtm,
    dem/ortho-resolution 5 cm) and **pins to a processing node** when
    `WEBODM_NODE_ID` is set (else auto). The old high-quality opts OOM'd on 84 MP.
  - New `WEBODM_NODE_ID` env var.
  - New helper `detect_layer_summary(image_paths, prefix, k=5)` — runs detection
    over k samples, returns the **dominant layer** (highest summed confidence).
  - `/upload` now runs `detect_layer_summary` on before & after sets, computes a
    **before→after change verdict** ("Sub Base → ABC: new layer detected —
    progress"), returns `detection_summary`, and attaches AFTER detections to the BOQ.
- `templates/construction_volume.html` — detection preview now shows the
  **dominant stage per phase + a change-verdict banner**.

### Helper / driver scripts (operator machine)
- `run_demo.py` — processes the 3 DSM pairs (detection + volume) → 3 reports in `/runs`.
- `before_after_detection.py` — generates side-by-side before/after detection
  comparison images (Methodology "AI Detection" demo).
- `run_detection_check.py` — runs detection on a folder, saves annotated images + summary.

### On Zafar's machine (WebODM host) — bring-up recap
- WebODM 3.2.6 at `...\Data Simulation\WebODM`; start: `& "C:\Program Files\Git\bin\bash.exe" webodm.sh start`.
- GPU NodeODM (Windows workaround — `webodm.sh --gpu` is NOT supported on Windows):
  `docker run -d --gpus all --name nodeodm-gpu -p 40001:3000 opendronemap/nodeodm:gpu`
  → registered as **processing node id 2** (`host.docker.internal:40001`).
  Restart later with `docker start nodeodm-gpu` (no re-pull).
- WebODM project **"construction progress" = id 2**; admin/admin.
- Submit scripts on that machine: `submit_webodm.py`, `webodm_status.py`, `status_all.py`, `download_dsm.py`.

### Live-demo architecture (target)
Choreography chosen: **A (pre-staged) + live-capable** — same code path.
- Upload before/after image sets → YOLO on samples returns instantly (the wow).
- Both sets submitted to the **GPU node** in the background (real photogrammetry,
  ~8 min/survey — too slow to wait for live, so show pre-staged DSM result and
  narrate "running live in the background"; if the panel insists, let it finish).
- When DSMs ready → volume (Z-corrected) → BOQ → S-curve.
- **Must run on Zafar's machine** (app + WebODM + GPU node co-located).
  Start with: `$env:WEBODM_PROJECT_ID="2"; $env:WEBODM_NODE_ID="2"; .\.venv\Scripts\python.exe finalV2.py`

### Status
- ✅ **App deployed to Zafar's machine** at `D:\ConstructionApp\Rozi Khan\construction_progress`.
  Runs on the reused training venv (`D:\Construction Progress Monitoring Yolo Trained\.venv`,
  CUDA torch) + `pip install flask rasterio openpyxl requests-toolbelt`.
- ✅ **Full live flow VERIFIED end-to-end on Zafar's machine (2026-06-28):**
  Start Fresh → upload before/after (SubBase) → YOLO detection preview → WebODM
  submitted to **GPU node (id 2)** → volume (Z-corrected) → BOQ → S-curve. Success.
  Launch: `cd` to the app dir, `$env:WEBODM_PROJECT_ID="2"; $env:WEBODM_NODE_ID="2"`,
  run with the training-venv python. Requires WebODM stack + `docker start nodeodm-gpu`.

### Remaining work
1. **Phase 2 visuals** (future, high wow) — the main outstanding item:
   orthomosaic JPEG preview, DSM heatmap, cut/fill heatmap overlay, Potree 3D
   point-cloud viewer. All build on WebODM outputs we already download.
2. **Detection domain gap** (known limitation, not a blocker) — model is strong
   on training-style frames, weak on raw 84 MP nadir frames. For crisp demo
   detection use training-style frames; long-term, retrain with full-res frames.
3. **GCP limitation** (thesis note) — survey-grade absolute volumes need GCPs
   (Min. 5 per methodology); Z-offset correction is the GCP-less best effort.

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
| ~~Trained YOLO road-layer model (`best.pt`)~~ | ✅ DONE 2026-06-26 | YOLO26s-seg, 3 classes, mAP50 0.96. See §0. Gemini alternative abandoned. |
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

- **YOLO is now LIVE** (as of 2026-06-26, §0) — the custom YOLO26s-seg model
  is trained and wired in. With `models\best.pt` present the app detects the
  3 real layers and attributes the BOQ to them. Without it, the old fallback
  still applies: generic COCO detections show but `class_id` is forced to
  `None`, so the BOQ shows one "Earthwork (unclassified)" line.
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
