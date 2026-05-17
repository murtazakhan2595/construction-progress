from flask import Flask, request, jsonify, render_template, send_from_directory
import os
import subprocess
import cv2
import uuid
import requests
import logging
from ultralytics import YOLO

app = Flask(__name__)

# Directories
UPLOAD_FOLDER = "uploads"
RESULTS_FOLDER = "results"
POINT_CLOUD_FOLDER = "point_clouds"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)
os.makedirs(POINT_CLOUD_FOLDER, exist_ok=True)

# YOLOv8 Model for Object Detection
model = YOLO("yolov8n.pt")

# WebODM Configuration
WEBODM_URL = "http://127.0.0.1:8000/api"
WEBODM_AUTH = ("admin", "admin")
PROJECT_ID = 12  # Replace with your actual WebODM project ID

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/upload', methods=['POST'])
def upload():
    """Handles image upload, object detection, and WebODM processing."""
    
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
    """Check if WebODM processing is complete and download assets if done."""
    
    response = requests.get(f"{WEBODM_URL}/projects/{PROJECT_ID}/tasks/{task_id}/", auth=WEBODM_AUTH)

    if response.status_code == 200:
        task_data = response.json()
        task_status = task_data.get("status")

        logging.info(f"WebODM Task Status: {task_status}")

        if task_status == 40:  # ✅ Status 40 means COMPLETED
            downloaded_files = download_assets(PROJECT_ID, task_id)
            
            if downloaded_files:
                return jsonify({"status": "completed", "downloaded_assets": list(downloaded_files.keys())})
            
            return jsonify({"status": "failed", "error": "Asset download failed"})

        elif task_status in [30, 50]:  # FAILED or CANCELED
            return jsonify({"status": "failed", "error": "WebODM processing failed"})

    return jsonify({"status": "processing"})

def detect_objects(image_path, prefix):
    """Run YOLOv8 object detection and save results."""
    
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
    """Submit images for WebODM processing."""
    
    url = f"{WEBODM_URL}/projects/{project_id}/tasks/"
    
    with open(before_image, "rb") as before_file, open(after_image, "rb") as after_file:
        files = [('images[]', ('before.jpg', before_file, 'image/jpeg')),
                 ('images[]', ('after.jpg', after_file, 'image/jpeg'))]
        response = requests.post(url, auth=WEBODM_AUTH, files=files)

    return response.json().get("id") if response.status_code == 201 else None

# def download_assets(project_id, task_id):
#     """Fetch and download available assets from WebODM, including all.zip."""
    
#     # ✅ Fetch task details to get available assets
#     task_url = f"{WEBODM_URL}/projects/{project_id}/tasks/{task_id}/"
#     response = requests.get(task_url, auth=WEBODM_AUTH)

#     if response.status_code != 200:
#         logging.error(f"❌ Failed to fetch task details for {task_id} (HTTP {response.status_code})")
#         return None

#     task_data = response.json()
#     available_assets = task_data.get("available_assets", [])

#     if not available_assets:
#         logging.error(f"❌ No assets available for task {task_id}")
#         return None

#     os.makedirs(POINT_CLOUD_FOLDER, exist_ok=True)
#     downloaded_files = {}

#     # ✅ Use requests.Session() for authentication persistence
#     session = requests.Session()
#     session.auth = WEBODM_AUTH

#     for asset_name in available_assets:
#         asset_download_url = f"{WEBODM_URL}/projects/{project_id}/tasks/{task_id}/assets/{asset_name}"
#         save_path = os.path.join(POINT_CLOUD_FOLDER, asset_name)

#         logging.info(f"📥 Downloading {asset_name} from {asset_download_url}...")

#         # ✅ Allow redirects to ensure proper downloading
#         response = session.get(asset_download_url, stream=True, allow_redirects=True)

#         if response.status_code == 200:
#             with open(save_path, "wb") as file:
#                 for chunk in response.iter_content(chunk_size=8192):
#                     file.write(chunk)
#             logging.info(f"✅ Successfully downloaded {asset_name} to {save_path}")
#             downloaded_files[asset_name] = save_path
#         else:
#             logging.warning(f"⚠️ Skipping {asset_name} - Not found (HTTP {response.status_code})")

#     return downloaded_files if downloaded_files else None
def download_assets(project_id, task_id):
    """Download assets from WebODM Processing Node."""

    PROCESSING_NODE_URL = "http://172.18.0.6:3000"  # Use the correct Docker container IP

    task_url = f"{WEBODM_URL}/projects/{project_id}/tasks/{task_id}/"
    response = requests.get(task_url, auth=WEBODM_AUTH)

    if response.status_code != 200:
        logging.error(f"❌ Failed to fetch task details for {task_id} (HTTP {response.status_code})")
        return None

    task_data = response.json()
    available_assets = task_data.get("available_assets", [])

    if not available_assets:
        logging.error(f"❌ No assets available for task {task_id}")
        return None

    os.makedirs(POINT_CLOUD_FOLDER, exist_ok=True)
    downloaded_files = {}

    session = requests.Session()
    session.auth = WEBODM_AUTH

    for asset_name in available_assets:
        asset_download_url = f"{PROCESSING_NODE_URL}/data/{task_id}/{asset_name}"
        save_path = os.path.join(POINT_CLOUD_FOLDER, asset_name)

        logging.info(f"📥 Downloading {asset_name} from {asset_download_url}...")

        try:
            response = session.get(asset_download_url, stream=True, allow_redirects=True)

            if response.status_code == 200:
                with open(save_path, "wb") as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)
                logging.info(f"✅ Successfully downloaded {asset_name} to {save_path}")
                downloaded_files[asset_name] = save_path
            else:
                logging.warning(f"⚠️ Skipping {asset_name} - Not found (HTTP {response.status_code})")

        except requests.exceptions.ConnectionError as e:
            logging.error(f"❌ Connection error while downloading {asset_name}: {e}")
            return None

    return downloaded_files if downloaded_files else None


if __name__ == '__main__':
    app.run(debug=True)
