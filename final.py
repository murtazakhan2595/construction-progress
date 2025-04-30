from flask import Flask, request, jsonify, render_template, send_from_directory
import os
import subprocess
import cv2
import uuid
import requests
import logging
from ultralytics import YOLO
import shutil

app = Flask(__name__)

# Directories
UPLOAD_FOLDER = "uploads"
RESULTS_FOLDER = "results"
DOWNLOAD_FOLDER = "downloaded_assets"
POINT_CLOUD_FOLDER = "point_clouds"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
os.makedirs(POINT_CLOUD_FOLDER, exist_ok=True)

# YOLOv8 Model
model = YOLO("yolov8n.pt")

# WebODM Configuration
WEBODM_URL = "http://127.0.0.1:8000/api"
WEBODM_AUTH = ("admin", "admin")
PROJECT_ID = 12  # Your project ID

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Mapping asset names to their correct download paths
SPECIAL_ASSETS = {
    "all.zip": "all.zip",
    "orthophoto.tif": "orthophoto.tif",
    "georeferenced_model.laz": "georeferenced_model.laz",
    "textured_model.zip": "textured_model.zip",
    "textured_model.glb": "textured_model.glb",
    "report.pdf": "report.pdf",
    "shots.geojson": "shots.geojson",
}

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/upload', methods=['POST'])
def upload():
    before_image = request.files.get('before_image')
    after_image = request.files.get('after_image')

    if not before_image or not after_image:
        return jsonify({"error": "Missing images"}), 400

    before_filename = f"before_{uuid.uuid4().hex}.jpg"
    after_filename = f"after_{uuid.uuid4().hex}.jpg"

    before_path = os.path.join(UPLOAD_FOLDER, before_filename)
    after_path = os.path.join(UPLOAD_FOLDER, after_filename)

    before_image.save(before_path)
    after_image.save(after_path)

    before_result_path = detect_objects(before_path, "before")
    after_result_path = detect_objects(after_path, "after")

    task_id = submit_task(PROJECT_ID, before_path, after_path)
    if not task_id:
        return jsonify({"error": "Failed to submit images to WebODM"}), 500

    return jsonify({
        "success": True,
        "task_id": task_id,
        "before_result": f"/results/{os.path.basename(before_result_path)}",
        "after_result": f"/results/{os.path.basename(after_result_path)}"
    })

@app.route('/check_webodm/<task_id>')
def check_webodm(task_id):
    response = requests.get(f"{WEBODM_URL}/projects/{PROJECT_ID}/tasks/{task_id}/", auth=WEBODM_AUTH)

    if response.status_code == 200:
        task_data = response.json()
        task_status = task_data.get("status")

        logging.info(f"WebODM Task Status: {task_status}")

        if task_status == 40:  # Completed
            downloaded_files = download_all_assets(PROJECT_ID, task_id)
            if downloaded_files:
                # Process point clouds if any
                laz_files = [f for f in downloaded_files if f.lower().endswith('.laz')]
                for laz_file in laz_files:
                    calculate_point_cloud_difference(laz_file)
                return jsonify({"status": "completed", "downloaded_assets": downloaded_files})
            return jsonify({"status": "failed", "error": "Asset download failed"})

        elif task_status in [30, 50]:  # Failed or Canceled
            return jsonify({"status": "failed", "error": "WebODM processing failed"})

    return jsonify({"status": "processing"})

def detect_objects(image_path, prefix):
    img = cv2.imread(image_path)
    results = model(img)

    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            label = result.names[int(box.cls[0])]
            confidence = box.conf[0] * 100
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(img, f"{label} {confidence:.1f}%", (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 255, 0), 3)

    processed_path = os.path.join(RESULTS_FOLDER, f"{prefix}_detected.jpg")
    cv2.imwrite(processed_path, img)
    return processed_path

@app.route('/results/<filename>')
def serve_results(filename):
    return send_from_directory(RESULTS_FOLDER, filename)

def submit_task(project_id, before_image, after_image):
    url = f"{WEBODM_URL}/projects/{project_id}/tasks/"

    with open(before_image, "rb") as before_file, open(after_image, "rb") as after_file:
        files = [
            ('images[]', ('before.jpg', before_file, 'image/jpeg')),
            ('images[]', ('after.jpg', after_file, 'image/jpeg'))
        ]
        response = requests.post(url, auth=WEBODM_AUTH, files=files)

    return response.json().get("id") if response.status_code == 201 else None

def download_all_assets(project_id, task_id):
    """Download ALL available assets for a WebODM task."""
    task_url = f"{WEBODM_URL}/projects/{project_id}/tasks/{task_id}/"
    session = requests.Session()
    session.auth = WEBODM_AUTH

    response = session.get(task_url)
    if response.status_code != 200:
        logging.error(f"❌ Failed to fetch task details (HTTP {response.status_code})")
        return None

    task_data = response.json()
    assets = task_data.get("available_assets", [])

    if not assets:
        logging.warning(f"⚠️ No downloadable assets found for task {task_id}")
        return None

    downloaded_files = []

    for asset_name in assets:
        if asset_name in SPECIAL_ASSETS:
            asset_url = f"{WEBODM_URL}/projects/{project_id}/tasks/{task_id}/download/{SPECIAL_ASSETS[asset_name]}"
        else:
            asset_url = f"{WEBODM_URL}/projects/{project_id}/tasks/{task_id}/assets/{asset_name}"

        save_path = os.path.join(DOWNLOAD_FOLDER, asset_name)

        # 💥 Ensure folder exists
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        logging.info(f"⬇️ Downloading: {asset_name}")

        asset_response = session.get(asset_url, stream=True)
        if asset_response.status_code == 200:
            with open(save_path, "wb") as f:
                for chunk in asset_response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            logging.info(f"✅ Downloaded: {asset_name}")
            downloaded_files.append(save_path)
        else:
            logging.error(f"❌ Failed to download {asset_name} (HTTP {asset_response.status_code})")

    return downloaded_files


def calculate_point_cloud_difference(file_path):
    """Compute volume using CloudCompare."""
    cloudcompare_path = "CloudCompare"  # Ensure CloudCompare is installed and available in PATH

    if not shutil.which(cloudcompare_path):
        logging.error("❌ CloudCompare not found in system path!")
        return None

    command = [
        cloudcompare_path,
        "-NO_TIMESTAMP",
        "-O", file_path,
        "-VOLUME",
        "-GRID_STEP", "0.5",  # 💥 Set a grid step size (you can adjust 0.5 meters or units)
        "-AUTO_SAVE", "OFF",
        "-SAVE_CLOUDS"
    ]

    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        logging.info("✅ Volume calculation successful.")
        print("STDOUT:\n", result.stdout)
        return result.stdout
    except subprocess.CalledProcessError as e:
        logging.error("❌ Error during CloudCompare execution.")
        print("STDERR:\n", e.stderr)
        return None

if __name__ == '__main__':
    app.run(debug=True)
