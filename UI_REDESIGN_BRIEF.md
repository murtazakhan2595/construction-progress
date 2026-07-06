# UI Redesign Brief — Construction Volume Analysis

> **Purpose of this document.** Hand this to a UI-generation tool (e.g. Claude
> as a designer, v0, Lovable, or a fresh Claude Code session) to produce a
> modern **HTML + Tailwind CSS + JavaScript/TypeScript** front end that is a
> drop-in replacement for the current UI. It fully specifies every screen,
> component, state, and — critically — the **exact backend API contract** the
> new UI must speak to, so it plugs into the existing Flask app with **zero
> backend changes**.
>
> Read it top to bottom. Everything the designer needs is here; they do **not**
> need to see the Python.

---

## 0. TL;DR for the designer

- Build a **single-page web app** (plus one secondary "Past Analyses" list
  page) for a drone-photogrammetry → earthwork-volume → cost → progress tool.
- Stack: **HTML + Tailwind CSS + vanilla JS or TypeScript**. No React required,
  but React/Vue is acceptable *if* the final output can be served as static
  files the Flask app renders. Simplest path: one `construction_volume.html`
  and one `runs.html`, Tailwind via CDN or a compiled stylesheet.
- The current UI works but looks like a 2016 gradient template. Goal: **clean,
  professional, engineering-SaaS aesthetic** — think Linear / Vercel / a modern
  GIS dashboard. Data-dense but calm.
- **Do not invent new API endpoints or change request/response shapes.** They
  are frozen (see §6). You may freely restructure layout, styling, and
  client-side JS.

---

## 1. What the product does (context for good design)

A civil-engineering web app for **road/highway construction monitoring**. A
site engineer uploads **before** and **after** drone imagery (or pre-computed 3D
elevation models) of a construction site. The app:

1. Runs photogrammetry (WebODM) to build 3D surface models.
2. Computes the **earthwork volume change** (cut/fill in m³) between the two.
3. Runs a **YOLO AI model** to detect the road layer/stage in the images
   (Sub Base → Aggregate Base Course → Asphalt).
4. Multiplies volume × unit rates → a **Bill of Quantities (BOQ)** in **PKR
   (Pakistani Rupees)**.
5. Tracks progress against a planned **S-curve** (planned vs actual spend).
6. Exports an **Excel report**.

**Users:** civil engineers / site surveyors / a thesis examiner panel. They are
technical but not web-savvy. Clarity and trust matter more than flashiness.
Currency is **PKR**. Units are **metric (m³)** primary, with cubic yards/feet as
secondary.

**Two usage modes** the UI must support (a toggle):
- **Start Fresh** — upload raw before/after drone *images*; full photogrammetry
  pipeline runs (takes minutes to hours).
- **Use Existing 3D Data** — upload pre-computed before/after **DSM `.tif`**
  files; skips photogrammetry, results in ~1 minute.

---

## 2. Current UI inventory (what exists today — the baseline to replace)

The existing front end is two Jinja templates. Here is every element, so
nothing is lost in the redesign.

### 2.1 Main page (`/`)
- **Header** — title "🏗️ Construction Volume Analysis", subtitle, and a link to
  "📋 Past Analyses" (`/runs`).
- **Collapsible Settings panel** ("⚙️ Project Plan & Rate List") containing two
  cards:
  - **Project Plan card** — inputs: Project Name, Currency (default PKR), Total
    Budget (number), Period Labels (comma-separated, e.g. "Month 1, Month 2").
    A **Save Plan** button + inline save status.
  - **Rate List card** — a table of road layers (# / Road Layer / Unit / Rate),
    where **Rate is an editable number input** per row. A **Save Rates** button
    + inline status.
- **Mode selector** — two selectable cards: "Start Fresh" and "Use Existing 3D
  Data" (radio behavior; selected card highlighted).
- **Upload area** (depends on mode):
  - *Fresh mode:* two drag-and-drop file dropzones side by side — **Before
    Images** and **After Images** (multiple image files each). Shows a list of
    picked filenames. Dropzone turns green/active when files present.
  - *Existing mode:* two dropzones — **Before DSM** and **After DSM** (single
    `.tif`/`.tiff` each). Shows filename + size.
- **Ground Control Points** dropzone (optional, fresh mode only) — single
  `.txt`/`.csv`.
- **Processing Options** panel (fresh mode only): DEM Resolution (number,
  m/pixel), Mesh Quality (select: high/medium/low), Volume Calculation Method
  (select: DEM Difference / Mesh Comparison / Point Cloud Comparison), and an
  "Enable object detection preview" checkbox.
- **Action buttons** — "🚀 Start Analysis" (primary) and "🔄 Reset".
- **Progress section** (hidden until running) — a percent progress bar, a
  percent label, and a status message string. Polls the backend every 2s.
- **AI Detection preview** (hidden until available) — a verdict banner + two
  side-by-side annotated images (Before / After) each labeled with the detected
  dominant layer.
- **Results section** (hidden until complete):
  - A grid of **result cards**: Volume Change (m³ + yd³), Material Removed (cut),
    Material Added (fill), Interpretation text, Processing Time / Task ID.
  - **Bill of Quantities table** — Road Layer / Quantity / Unit / Rate / Amount,
    with a TOTAL footer row.
  - **S-Curve** — a status line (status + performance index) and a rendered PNG
    chart image.
  - Buttons: "📊 Excel Report", "📥 Download Report" (JSON), "🗂️ View Assets".
- **Error banner** area.

### 2.2 Past Analyses page (`/runs`)
A table listing prior runs: Project / Date / Volume (m³) / Total Cost / Task ID
/ a "View →" link (goes to `/?task=<id>` which reloads the main page in
read-only results mode). Empty state when there are no runs.

### 2.3 What's wrong with it today (design pain points to fix)
- Purple gradient background + heavy drop shadows = dated, "template-y".
- Emoji used as primary iconography — replace with a real icon set (Lucide,
  Heroicons, or Phosphor).
- Everything is one long scroll with weak visual hierarchy; the important number
  (volume change / cost) doesn't stand out.
- Settings, upload, options, results all compete for attention. Needs clear
  **step-based flow** (or clearly separated zones).
- No loading skeletons, no empty states beyond `/runs`, no toasts.
- Not truly responsive beyond a couple of media queries.
- Detection preview and results are visually disconnected.

---

## 3. Design goals & direction

| Goal | Detail |
|---|---|
| **Aesthetic** | Modern engineering-SaaS. Neutral base (white / slate-50), one confident accent (a professional blue or teal), generous whitespace, subtle borders over heavy shadows. Rounded-lg corners, not pill-everything. |
| **Hierarchy** | The **volume change** and **BOQ total** are the hero numbers. Make them unmissable. |
| **Flow** | Present the work as a clear sequence: **Configure → Upload → Process → Results**. A stepper or clearly delineated sections. |
| **Trust** | This is a measurement tool for a thesis/engineering audience. Precise typography, aligned numbers (tabular figures), clear units, no gimmicks. |
| **Icons** | Use a real icon library (Lucide preferred). No emoji in the final UI. |
| **Typography** | A clean sans (Inter / Geist / system-ui). Tabular numbers for all metrics and tables. |
| **Dark mode** | Nice-to-have, not required. If included, must be a toggle and not break chart/image legibility. |
| **Responsive** | Must work on a laptop (primary) and degrade gracefully to tablet. Mobile is low priority but shouldn't break. |
| **Accessibility** | Proper labels on inputs, focus states, sufficient contrast, keyboard-operable dropzones. |

**Explicitly keep** (functionality parity — do not drop these):
mode toggle, both upload flows, GCP upload, processing options, settings panel
(plan + editable rates), progress polling, detection preview, all result cards,
BOQ table, S-curve image, Excel/JSON/assets download, past-runs view, read-only
mode via `?task=<id>`, health-check warning banner.

---

## 4. Screen-by-screen spec for the new UI

### 4.1 App shell
- Top nav bar: product name/logo (left), links: **New Analysis** (`/`),
  **Past Analyses** (`/runs`) (right). Optional: a small health indicator dot
  (green/amber) driven by `/health` (see §6.8).
- Content max-width ~1200px, centered, comfortable padding.

### 4.2 Section A — Project configuration (Settings)
Collapsible or a dedicated panel. Two cards:
- **Project Plan**: Project Name, Currency, Total Budget, Period Labels. Save
  button with inline "Saved ✓" / error feedback (data via `/api/plan`).
- **Rate List**: editable table of road layers with a numeric Rate input per
  row. Save button + feedback (data via `/api/rates`).

Design it so a first-time user understands these are *defaults that drive the
cost math*. Consider a short helper line.

### 4.3 Section B — Data input
- **Mode toggle**: segmented control or two selectable cards — *Start Fresh* vs
  *Use Existing 3D Data*. Explain the tradeoff (slow full pipeline vs fast
  DSM-only) in a subline.
- **Dropzones** (drag-and-drop + click-to-browse):
  - Fresh: Before Images / After Images (multi-file, images). Show a compact
    scrollable file list with count and a way to clear.
  - Existing: Before DSM / After DSM (single `.tif`). Show filename + size.
  - GCP (fresh only): single optional file.
- **Processing Options** (fresh only): DEM Resolution (number), Mesh Quality
  (select), Volume Method (select), Enable detection preview (toggle/checkbox).
- **Primary CTA**: "Start Analysis" (disabled until required files present),
  plus a "Reset" secondary.

Validation: if required files are missing, show an inline error (don't submit).

### 4.4 Section C — Processing state
When a run starts, reveal a processing panel:
- Progress bar bound to the polled `progress` (0–100).
- The polled `message` string as a status line (e.g. "Running photogrammetry…").
- Consider step indicators (Upload → Photogrammetry → Volume → Detection → Cost
  → S-curve) that light up as progress crosses thresholds — but the backend only
  gives a single %+message, so keep step mapping cosmetic/optional.
- If detection preview data arrives with the upload response, show the
  **AI Detection** block immediately (before full completion): verdict banner +
  Before/After annotated images with layer labels.

### 4.5 Section D — Results
Revealed on completion (or immediately in `?task=` read-only mode):
- **Hero metrics row**: Volume Change (m³, with yd³ secondary), Cut (Material
  Removed), Fill (Material Added), and Interpretation. Make Volume Change the
  largest.
- **Meta**: timestamp, short task id, project name.
- **Bill of Quantities** table: Road Layer / Quantity / Unit / Rate (currency) /
  Amount (currency) + TOTAL row. Right-align and use tabular numbers.
- **S-Curve** card: status + performance index line, then the PNG chart image
  (`scurve_image` URL). Just render the image; the backend produces it.
- **AI Detection** block (if present): verdict banner + two annotated images.
- **Actions**: Excel Report, Download Report (JSON), View Assets (a small modal
  or dropdown listing downloadable asset links — see §6.6).

### 4.6 Past Analyses (`/runs`)
Modern table or card list: Project, Date, Volume (m³), Total Cost (currency),
Task ID (mono, truncated), View action → `/?task=<id>`. Include a clean empty
state and a "New Analysis" CTA.

---

## 5. States to design (don't forget these)
- **Empty / initial** (no files chosen).
- **Files selected** (dropzone active, file list populated).
- **Submitting / uploading**.
- **Processing** (progress bar + message; long-running).
- **Detection-preview-ready** (partial results while still processing).
- **Completed** (full results).
- **Failed** (error banner with the backend message; form re-enabled).
- **Read-only past run** (loaded from `?task=<id>`; hide the upload form or show
  results-only).
- **Health warning** (WebODM/CloudCompare down → dismissible warning banner).
- **Save feedback** for plan/rates (idle / saving / saved / error).

---

## 6. THE API CONTRACT (frozen — build the JS against exactly this)

The new UI is client-side JS talking to an existing Flask backend. **These
endpoints, payloads, and field names must not change.** All paths are relative
to the app origin (same host).

### 6.1 `GET /health`
Returns:
```json
{
  "status": "healthy",
  "timestamp": "2026-06-28T12:00:00",
  "services": { "webodm": true, "cloudcompare": true, "yolo": true },
  "active_tasks": 0,
  "cloudcompare_path": "C:\\...\\CloudCompare.exe"
}
```
On load, if `services.webodm` is false → show a warning banner ("WebODM service
not available…"). Same for `services.cloudcompare`.

### 6.2 `GET /api/plan`  /  `POST /api/plan`
GET returns the project plan:
```json
{
  "project_name": "N-25 Highway - Lahore-Multan Section (Phase 1)",
  "currency": "PKR",
  "total_budget": 50000000,
  "period_labels": ["Month 1", "Month 2", "..."],
  "planned_cumulative": [ ... ]
}
```
POST body (JSON) to save:
```json
{
  "project_name": "…",
  "currency": "PKR",
  "total_budget": 50000000,
  "period_labels": ["Month 1", "Month 2"],
  "planned_cumulative": []
}
```
POST returns `{ "success": true, "plan": { ...saved plan... } }` or
`{ "error": "…" }`.

### 6.3 `GET /api/rates`  /  `POST /api/rates`
GET returns:
```json
{
  "currency": "PKR",
  "rates": [
    { "class_id": 0, "name": "Aggregate Base Course", "unit": "m3", "rate": 2500.0 },
    { "class_id": 1, "name": "Asphalt",               "unit": "m3", "rate": 18500.0 },
    { "class_id": 2, "name": "Sub Base",              "unit": "m3", "rate": 1200.0 }
  ]
}
```
POST body to save (only class_id + rate needed):
```json
{ "rates": [ { "class_id": 0, "rate": 2500 }, { "class_id": 1, "rate": 18500 } ] }
```
POST returns `{ "success": true, "rates": [ ...full table... ] }` or `{ "error": "…" }`.
> Note: the rate list is **dynamic** — render whatever rows the GET returns
> (currently 3 road layers, but don't hardcode 3).

### 6.4 `POST /upload`  (Start Fresh mode — multipart/form-data)
Form fields:
- `before_images` — multiple image files (repeat the field per file).
- `after_images` — multiple image files.
- `gcp_file` — optional single file.
- `dem_resolution` — string/number (e.g. "0.1").
- `mesh_resolution` — "high" | "medium" | "low".
- `volume_method` — "dem_diff" | "mesh_diff" | "point_cloud_diff".
- `enable_detection` — "true" | "false" (string).

Success response:
```json
{
  "success": true,
  "task_id": "uuid-string",
  "message": "Processing started",
  "options": { "dem_resolution": 0.1, "mesh_resolution": "medium", "volume_method": "dem_diff" },
  "detection_results": {
    "before": { "image": "/result-file/xxx.jpg", "dominant": "Sub Base", "detections": [ ... ] },
    "after":  { "image": "/result-file/yyy.jpg", "dominant": "Aggregate Base Course", "detections": [ ... ] }
  },
  "detection_summary": {
    "before_layer": "Sub Base",
    "after_layer": "Aggregate Base Course",
    "changed": true,
    "verdict": "Sub Base → Aggregate Base Course: new layer detected — progress confirmed"
  }
}
```
`detection_results` / `detection_summary` are **only present** when
`enable_detection=true` and the model is available; handle their absence.
Error response: `{ "error": "…" }` with HTTP 4xx/5xx.

After a successful response, take `task_id` and begin **status polling** (§6.7).

### 6.5 `POST /upload-existing`  (Use Existing 3D Data — multipart/form-data)
Form fields:
- `before_dsm` — single `.tif`/`.tiff`.
- `after_dsm` — single `.tif`/`.tiff`.

Success: `{ "success": true, "task_id": "uuid", "message": "Volume analysis started (existing-data mode)" }`.
Error: `{ "error": "…" }`. Then poll status (§6.7).

### 6.6 Downloads / assets
- `GET /report-excel/<task_id>` → triggers an `.xlsx` file download (navigate to
  it / window.location).
- `GET /download/<task_id>/report` → JSON report blob (offer as file download).
- `GET /download/<task_id>/<asset_type>` where asset_type ∈
  `report | before_dem | after_dem | before_mesh | after_mesh`. "View Assets"
  should present these as links (some may 404 if that asset wasn't produced —
  that's acceptable).
- `GET /result-file/<filename>` → serves images (detection previews, S-curve
  PNG). You never construct these paths yourself; use the URLs the API returns
  (`detection_results.*.image`, `scurve_image`).

### 6.7 `GET /status/<task_id>`  (poll every ~2s)
Returns:
```json
{ "status": "processing", "progress": 45, "message": "Calculating volume…", "data": null }
```
- `status` ∈ `processing | completed | failed | not_found`.
- On `completed` → stop polling, call `GET /results/<task_id>`.
- On `failed` → stop polling, show `message` as the error.

### 6.8 `GET /results/<task_id>`  (the full report — also used by `?task=`)
Returns the analysis report JSON. **This is the shape the Results UI binds to:**
```json
{
  "task_id": "uuid",
  "timestamp": "2026-06-28T12:34:56",
  "project_name": "N-25 Highway - Lahore-Multan Section (Phase 1)",
  "volume_change_m3": 14899.12,
  "volume_change_yd3": 19487.6,
  "volume_change_ft3": 526180.0,
  "analysis": {
    "cut_volume": 0,
    "fill_volume": 14899.12,
    "net_volume": 14899.12,
    "interpretation": "Material added: 14899.12 m³ of fill/construction material",
    "accuracy_estimate": {
      "estimated_vertical_accuracy": "±100 mm",
      "estimated_volume_accuracy": "±2-5%",
      "dem_resolution": "0.1 m/pixel",
      "notes": "Accuracy depends on image quality, overlap, and ground control points"
    }
  },
  "detected_layers": [ { "layer": "Aggregate Base Course", "confidence": 0.86 } ],
  "boq": {
    "currency": "PKR",
    "total_cost": 6704603,
    "items": [
      { "layer": "Aggregate Base Course", "quantity": 14899.12, "unit": "m3", "rate": 2500, "amount": 6704603 }
    ]
  },
  "scurve": {
    "summary": { "status": "ahead of schedule", "performance_index": 1.117 },
    "planned_cumulative": [ ... ],
    "actual_cumulative": [ ... ],
    "period_labels": [ "Month 1", "..." ]
  },
  "scurve_image": "/result-file/scurve_<task_id>.png"
}
```
Binding notes:
- Hero number: `volume_change_m3` (show `volume_change_yd3` as secondary).
- Cut / Fill: `analysis.cut_volume` / `analysis.fill_volume` (only show a card if
  > 0, matching current behavior — or show both always if cleaner).
- Interpretation: `analysis.interpretation`.
- BOQ table rows: `boq.items[]` → layer / quantity / unit / rate / amount;
  footer TOTAL = `boq.total_cost`; currency = `boq.currency`.
- S-curve: show `scurve.summary.status` + `scurve.summary.performance_index`,
  then render the `scurve_image` URL as an `<img>`.
- `scurve_image` may be absent if rendering failed → hide the chart gracefully.
- Any field may be missing on older/edge reports → guard every access.

### 6.9 `GET /runs`  (server-rendered page)
Returns an HTML page (Jinja). The redesign should provide a **`runs.html`
template** that Flask renders with a `runs` list, each item:
`{ task_id, timestamp, project_name, volume_m3, total_cost, currency }`.
Use Jinja loop (`{% for r in runs %}`) — see §7 for the integration constraint.

---

## 7. Integration constraints (so it drops into the Flask app)

The backend serves two templates from a `templates/` folder:
- `construction_volume.html` — the main SPA (served at `/`).
- `runs.html` — the past-analyses list (served at `/runs`, Jinja-rendered with a
  `runs` variable).

**Deliverable expectations for the designer:**
1. Prefer **self-contained HTML files** (Tailwind via CDN `<script>` is fine for
   a first pass; a compiled Tailwind build is better for production). If you use
   a build step, also provide the compiled output so it can be dropped in
   without a toolchain.
2. `runs.html` must keep a **Jinja `{% for r in runs %}`** loop over the fields
   in §6.9 (or the redesign can fetch a JSON endpoint instead — but that
   endpoint doesn't exist yet, so **the Jinja approach is the safe default**).
3. The main page must support deep-link **`/?task=<id>`**: on load, read the
   `task` query param and, if present, immediately fetch `/results/<id>` and
   render results in read-only mode (no upload needed).
4. All API calls are **same-origin relative paths** — no CORS, no base URL.
5. Don't add a backend framework dependency. Plain fetch() calls only.
6. Keep `localStorage` persistence of the processing options (nice-to-have; the
   current UI remembers dem_resolution / mesh_resolution / volume_method /
   enable_detection).

---

## 8. Content / copy reference
- App name: **Construction Volume Analysis** (subtitle: "Earthwork & road-layer
  progress monitoring from drone photogrammetry").
- Currency label: **PKR** (but read `currency` from the API, don't hardcode).
- Road layers (current model, but render dynamically from `/api/rates`):
  Aggregate Base Course, Asphalt, Sub Base.
- Mode labels: **Start Fresh** ("Raw drone images → photogrammetry → volume") /
  **Use Existing 3D Data** ("Pre-computed DSM .tif → straight to volume").
- Verdict banner examples: "Sub Base → Aggregate Base Course: new layer detected
  — progress confirmed" (positive/green) vs "Asphalt: same stage — no new layer
  detected" (neutral).

---

## 9. Deliverables checklist (what to return to me)
- [ ] `construction_volume.html` — full redesigned main page (Tailwind + JS),
      wired to every endpoint in §6, all states in §5.
- [ ] `runs.html` — redesigned past-analyses page (Jinja loop preserved).
- [ ] Any compiled CSS/JS assets if a build step was used.
- [ ] A short note on how assets are referenced (CDN vs local) so I can place
      them in the Flask `templates/`(and `static/`) folders.
- [ ] Confirmation that no API path, field name, form-field name, or query-param
      contract from §6/§7 was changed.

---

## 10. Out of scope (do NOT do these)
- No backend/Python changes. No new endpoints. No auth. No database.
- Don't change the units, currency logic, or the S-curve computation (the PNG is
  produced server-side — just display it).
- Don't remove any existing capability listed in §3 "Explicitly keep".
- Don't rename form fields (`before_images`, `after_images`, `gcp_file`,
  `before_dsm`, `after_dsm`, `dem_resolution`, `mesh_resolution`,
  `volume_method`, `enable_detection`).

---

*When the redesigned files come back, hand them to me (Claude Code) and I'll drop
them into `Rozi Khan/construction_progress/templates/`, reconcile any field
mismatches, and verify against the running Flask app.*
