# Quickstart

Get the Construction Volume Analysis app running in 5 steps. See `README.md`
for details and `plan.md` for the full project status.

## You will install

| Tool | Why | Where |
|------|-----|-------|
| Python 3.10+ | runs the app | python.org |
| Docker Desktop | runs WebODM | docker.com/products/docker-desktop |
| CloudCompare | volume from 3D surfaces | cloudcompare.org |

All three are free.

## 1. Get the code

```bash
git clone https://github.com/murtazakhan2595/construction-progress.git
cd construction-progress
```

## 2. Python environment

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 3. WebODM (in a separate folder, one time only)

```bash
git clone https://github.com/OpenDroneMap/WebODM ../WebODM
cd ../WebODM
./webodm.sh start
```

Open http://localhost:8000 in a browser, set the admin password to `admin`
(or anything - just match it in step 5), and create a project. Note its
project ID (visible in the URL, usually `1`).

## 4. Run the app

```bash
cd ../construction-progress
python finalV2.py
```

App opens at **http://localhost:5000**.

## 5. Configure (one time, via the web UI)

At the top of the page, expand **⚙️ Project Plan & Rate List**:

- **Project Plan** - set name, currency, total budget, period labels (months),
  then click *Save Plan*.
- **Rate List** - edit the 12 road-layer unit rates, then click *Save Rates*.

If your WebODM credentials or project ID differ from the defaults, set
environment variables before running the app:

```
set WEBODM_URL=http://localhost:8000/api
set WEBODM_USER=admin
set WEBODM_PASSWORD=admin
set WEBODM_PROJECT_ID=1
set YOLO_MODEL_PATH=path\to\best.pt        (when the trained model is ready)
```

## 6. Use it

1. Upload **Before** and **After** drone image sets (many overlapping aerial
   photos each; raw JPEGs from the drone are fine).
2. Optional: tick *Enable object detection preview*.
3. Click **Start Analysis**.
4. WebODM photogrammetry runs (30-90 min per set on CPU); the page polls and
   shows progress.
5. When it completes you see volume change, Bill of Quantities, S-curve, and
   buttons to download the JSON report and the Excel report.

## Notes

- The trained road-layer YOLO model is pending. Until you set
  `YOLO_MODEL_PATH`, detections show generic COCO labels but the BOQ
  collapses to a single "Earthwork (unclassified)" line.
- GCP files are optional: the DJI Zenmuse L1 RTK GPS in EXIF is already
  accurate enough for relative volume measurement.
- WebODM and CloudCompare can both run on the same machine as the app, or
  the app can point at a remote WebODM via `WEBODM_URL`.
