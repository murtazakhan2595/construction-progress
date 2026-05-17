# Construction Volume Analysis

Web application that measures construction earthwork progress from drone imagery
and reports it as volume and cost. MS Thesis project — see `plan.md` for the full
completion plan and current status.

## What it does

Upload **before** and **after** drone image sets → the app runs photogrammetry
(WebODM), compares the 3D surfaces (CloudCompare) to compute cut/fill volume,
identifies road layers (YOLOv8), applies unit rates for cost, and produces an
Excel report with an S-curve (planned vs actual progress).

## Requirements

This app depends on two free, open-source tools that must be installed and running:

| Tool | Purpose | Install |
|------|---------|---------|
| **WebODM** | Photogrammetry (images → point cloud / DEM) | Docker — https://opendronemap.org |
| **CloudCompare** | Volume difference from 3D surfaces | https://cloudcompare.org |

Plus Python 3.9+ and the packages in `requirements.txt`.

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Start WebODM (separate terminal, requires Docker)
#    git clone https://github.com/OpenDroneMap/WebODM
#    cd WebODM && ./webodm.sh start

# 4. Install CloudCompare from cloudcompare.org

# 5. Run the app
python finalV2.py
```

The app starts at http://localhost:5000

## Configuration

Edit the top of `finalV2.py`:

- `WEBODM_URL`, `WEBODM_AUTH`, `PROJECT_ID` — your WebODM instance and project
- `CLOUDCOMPARE_PATHS` — CloudCompare executable location

## Project files

| Path | Description |
|------|-------------|
| `finalV2.py` | Main Flask application |
| `templates/construction_volume.html` | Web UI |
| `requirements.txt` | Python dependencies |
| `plan.md` | Completion plan and status |
| `_archive/` | Superseded earlier code iterations |
| `uploads/`, `results/`, `dems/`, `meshes/`, `point_clouds/` | Working data folders |

## Status

Under active completion — see `plan.md`. The photogrammetry/volume pipeline is
built but being debugged; cost, Excel export, and S-curve modules are in progress.
