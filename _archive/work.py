from flask import Flask, request, jsonify, render_template, send_from_directory
import os
import subprocess
import uuid
import requests
import logging
from ultralytics import YOLO
import cv2
import shutil
import time
import threading
import re
import glob
app = Flask(__name__)

# Directories
UPLOAD_FOLDER = "uploads"
RESULTS_FOLDER = "results"
DOWNLOAD_FOLDER = "downloaded_assets"
POINT_CLOUD_FOLDER = "point_clouds"

for folder in [UPLOAD_FOLDER, RESULTS_FOLDER, DOWNLOAD_FOLDER, POINT_CLOUD_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# YOLOv8 Model
model = YOLO("yolov8n.pt")

# WebODM Configuration
WEBODM_URL = "http://127.0.0.1:8000/api"
WEBODM_AUTH = ("admin", "admin")
PROJECT_ID = 12  # Adjust to your WebODM project ID

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Global Task Status Store
task_status_store = {}

@app.route('/')
def index():
    return render_template("design.html")

@app.route('/upload', methods=['POST'])
def upload():
    before_files = request.files.getlist('before_images')
    after_files = request.files.getlist('after_images')

    if not before_files or not after_files:
        return jsonify({"error": "Missing before or after images"}), 400

    before_paths = save_images(before_files, "before")
    after_paths = save_images(after_files, "after")

    before_result = detect_objects(before_paths[0], "before")
    after_result = detect_objects(after_paths[0], "after")

    task_id = str(uuid.uuid4())
    threading.Thread(target=volume_pipeline, args=(task_id, before_paths, after_paths)).start()

    return jsonify({
        "success": True,
        "task_id": task_id,
        "before_result": f"/results/{os.path.basename(before_result)}",
        "after_result": f"/results/{os.path.basename(after_result)}"
    })


def extract_volume_from_txt(filepath):
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
        for line in lines:
            if line.startswith("Volume:"):
                return float(line.split(":")[1].strip())
    except Exception as e:
        print(f"Error extracting volume: {e}")
    return None

@app.route('/check_webodm/<task_id>')
def check_webodm(task_id):
    try:
        # Find latest VolumeCalculationReport file in downloaded_assets
        files = sorted(
            glob.glob('downloaded_assets/VolumeCalculationReport_*.txt'),
            key=os.path.getmtime,
            reverse=True
        )
        if not files:
            return jsonify({'status': 'processing'})

        latest_file = files[0]
        volume_change = extract_volume_from_txt(latest_file)

        return jsonify({
            'status': 'completed',
            'volume_change': f"{volume_change:.2f} m³" if volume_change else "N/A"
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    
@app.route('/results/<filename>')
def serve_results(filename):
    return send_from_directory(RESULTS_FOLDER, filename)

def save_images(files, prefix):
    paths = []
    for file in files:
        filename = f"{prefix}_{uuid.uuid4().hex}.jpg"
        path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(path)
        paths.append(path)
    return paths

def detect_objects(image_path, prefix):
    img = cv2.imread(image_path)
    results = model(img)
    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            label = result.names[int(box.cls[0])]
            conf = box.conf[0] * 100
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(img, f"{label} {conf:.1f}%", (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    result_path = os.path.join(RESULTS_FOLDER, f"{prefix}_detected.jpg")
    cv2.imwrite(result_path, img)
    return result_path

def volume_pipeline(task_id, before_paths, after_paths):
    task_status_store[task_id] = {"status": "processing"}
    logging.info("Submitting BEFORE task")
    before_task_id = submit_webodm_task(PROJECT_ID, before_paths)
    if not before_task_id or not wait_for_webodm_task(PROJECT_ID, before_task_id):
        task_status_store[task_id] = {"status": "failed"}
        return

    before_laz = download_asset(PROJECT_ID, before_task_id, "georeferenced_model.laz")
    if not before_laz:
        task_status_store[task_id] = {"status": "failed"}
        return

    time.sleep(5)

    logging.info("Submitting AFTER task")
    after_task_id = submit_webodm_task(PROJECT_ID, after_paths)
    if not after_task_id or not wait_for_webodm_task(PROJECT_ID, after_task_id):
        task_status_store[task_id] = {"status": "failed"}
        return

    after_laz = download_asset(PROJECT_ID, after_task_id, "georeferenced_model.laz")
    if not after_laz:
        task_status_store[task_id] = {"status": "failed"}
        return

    logging.info("Computing volume difference")
    volume = compute_volume(before_laz, after_laz)

    if volume is not None:
        task_status_store[task_id] = {
            "status": "completed",
            "volume_change": round(volume, 2)
        }
    else:
        task_status_store[task_id] = {"status": "failed"}

def submit_webodm_task(project_id, image_paths):
    url = f"{WEBODM_URL}/projects/{project_id}/tasks/"
    files = []
    try:
        for p in image_paths:
            files.append(('images[]', (os.path.basename(p), open(p, 'rb'), 'image/jpeg')))
        response = requests.post(url, auth=WEBODM_AUTH, files=files)
        if response.status_code == 201:
            task_id = response.json().get("id")
            logging.info(f"Submitted task {task_id} with {len(image_paths)} images.")
            return task_id
        else:
            logging.error(f"Failed to create task: {response.status_code} {response.text}")
            return None
    finally:
        for _, file_tuple in files:
            file_tuple[1].close()

def wait_for_webodm_task(project_id, task_id):
    url = f"{WEBODM_URL}/projects/{project_id}/tasks/{task_id}/"
    while True:
        res = requests.get(url, auth=WEBODM_AUTH)
        if res.status_code == 200:
            status = res.json().get("status")
            logging.info(f"Task {task_id} status: {status}")
            if status == 40:  # Completed
                return True
            elif status in [30, 50]:  # Failed or Canceled
                return False
        time.sleep(10)

def download_asset(project_id, task_id, asset_name):
    url = f"{WEBODM_URL}/projects/{project_id}/tasks/{task_id}/download/{asset_name}"
    path = os.path.join(DOWNLOAD_FOLDER, f"{task_id}_{asset_name}")
    r = requests.get(url, auth=WEBODM_AUTH, stream=True)
    if r.status_code == 200:
        with open(path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return path
    else:
        logging.error(f"Failed to download asset: {r.status_code} {r.text}")
    return None

def compute_volume(before_file, after_file):
    cloudcompare_path = "CloudCompare"  # Or full path
    output_txt = os.path.join(RESULTS_FOLDER, f"volume_{uuid.uuid4().hex}.txt")

    if not shutil.which(cloudcompare_path):
        logging.error("CloudCompare not found in system PATH.")
        return None

    # command = [
    #     cloudcompare_path,
    #     "-AUTO_SAVE", "OFF",
    #     "-O", before_file,
    #     "-O", after_file,
    #     "-ICP",  # Optional: aligns the two clouds
    #     "-VOLUME",
    #     "-GRID_STEP", "0.05",
    #     "-VERT_DIR", "2",
    #     "-LOG_FILE", output_txt
    # ]
    command = [
        cloudcompare_path,
        "-AUTO_SAVE", "OFF",
        "-O", before_file,
        "-O", after_file,
        "-ICP",  # Comment this out if clouds already aligned
        "-VOLUME",
        "-GRID_STEP", "0.05",
        "-VERT_DIR", "2",  # Usually Z is vertical axis; confirm your data
        "-LOG_FILE", output_txt,
        "-NO_TIMESTAMP"  # Cleaner log output for parsing
    ]
    try:
        logging.info(f"Running CloudCompare command: {' '.join(command)}")
        subprocess.run(command, check=True)

        if os.path.exists(output_txt):
            with open(output_txt, "r") as f:
                for line in f:
                    if "Volume =" in line or "Total volume =" in line:
                        volume = line.split('=')[-1].strip().split(' ')[0]
                        return float(volume)
    except subprocess.CalledProcessError as e:
        logging.error(f"CloudCompare execution failed: {e}")
    except Exception as ex:
        logging.error(f"Unexpected error: {ex}")

    return None

if __name__ == '__main__':
    app.run(debug=True)
