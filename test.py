
from flask import Flask, request, jsonify, render_template, send_from_directory
import os
import subprocess
import cv2
import uuid
import requests
import time

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
RESULTS_FOLDER = "results"
POINT_CLOUD_FOLDER = "point_clouds"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)
os.makedirs(POINT_CLOUD_FOLDER, exist_ok=True)

from ultralytics import YOLO
model = YOLO("yolov8n.pt")

WEBODM_URL = "http://127.0.0.1:8000/api"
PROCESSING_NODE_URL = "http://webodm-node-odm-1:3000"
WEBODM_AUTH = ("admin", "admin")

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

    detect_objects(before_path)
    detect_objects(after_path)

    project_id = get_or_create_project("construction_analysis")
    if not project_id:
        return jsonify({"error": "Failed to retrieve or create WebODM project"}), 500

    task_id = submit_task(project_id, before_path, after_path)
    if not task_id:
        return jsonify({"error": "Failed to submit images to WebODM"}), 500

    if not poll_webodm_task(task_id):
        return jsonify({"error": "WebODM processing failed"}), 500

    before_pcd, after_pcd = download_and_extract_point_clouds(task_id)
    if not before_pcd or not after_pcd:
        return jsonify({"error": "Missing point cloud files"}), 500

    volume_change = calculate_volume_change(before_pcd, after_pcd)

    return jsonify({
        "success": True,
        "volume_change": volume_change,
        "before_result": f"/results/{os.path.basename(before_path)}",
        "after_result": f"/results/{os.path.basename(after_path)}"
    })

def detect_objects(image_path):
    results = model(image_path)
    output_path = os.path.join(RESULTS_FOLDER, os.path.basename(image_path))
    
    img = cv2.imread(image_path)
    for result in results:
        for box in result.boxes.xyxy:
            x1, y1, x2, y2 = map(int, box)
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)

    cv2.imwrite(output_path, img)

@app.route('/results/<filename>')
def serve_results(filename):
    return send_from_directory(RESULTS_FOLDER, filename)

def get_or_create_project(project_name):
    response = requests.get(f"{WEBODM_URL}/projects/", auth=WEBODM_AUTH)
    if response.status_code == 200:
        projects = response.json()
        for project in projects:
            if project["name"] == project_name:
                return project["id"]
    
    response = requests.post(
        f"{WEBODM_URL}/projects/", auth=WEBODM_AUTH, data={"name": project_name}
    )
    if response.status_code == 201:
        return response.json()["id"]
    
    return None

def submit_task(project_id, before_image, after_image):
    url = f"{WEBODM_URL}/projects/{project_id}/tasks/"
    
    with open(before_image, "rb") as before_file, open(after_image, "rb") as after_file:
        files = [
            ('images[]', ('before.jpg', before_file, 'image/jpeg')),
            ('images[]', ('after.jpg', after_file, 'image/jpeg'))
        ]

        response = requests.post(url, auth=WEBODM_AUTH, files=files)

    if response.status_code == 201:
        print("Task submitted successfully")
        return response.json().get("id")
    else:
        print(f"Error submitting task: {response.status_code}")
        print("Response text:", response.text)

    return None

def poll_webodm_task(task_id, max_wait=600):
    elapsed = 0
    while elapsed < max_wait:
        response = requests.get(f"{WEBODM_URL}/tasks/{task_id}/", auth=WEBODM_AUTH)
        if response.status_code == 200:
            task_status = response.json().get("status")
            print(f"Task Status: {task_status}")
            if task_status == "COMPLETED":
                return True
            elif task_status in ["FAILED", "CANCELED"]:
                return False
        
        time.sleep(10)
        elapsed += 10

    return False

def download_and_extract_point_clouds(task_id):
    """Download and extract point cloud files (.las, .ply) for the given task ID."""
    
    assets_url = f"{WEBODM_URL}/tasks/{task_id}/assets/"
    response = requests.get(assets_url, auth=WEBODM_AUTH)

    if response.status_code != 200:
        print("Error: Unable to retrieve assets list from WebODM")
        return None, None

    assets = response.json()
    os.makedirs(POINT_CLOUD_FOLDER, exist_ok=True)

    before_pcd, after_pcd = None, None

    for asset in assets:
        file_url = f"{WEBODM_URL}{asset['asset']}"
        file_name = os.path.basename(asset["asset"])
        local_path = os.path.join(POINT_CLOUD_FOLDER, file_name)

        if file_name.endswith(".las") or file_name.endswith(".ply"):
            print(f"Downloading: {file_name}")

            file_response = requests.get(file_url, auth=WEBODM_AUTH, stream=True)
            if file_response.status_code == 200:
                with open(local_path, "wb") as file:
                    for chunk in file_response.iter_content(chunk_size=8192):
                        file.write(chunk)
                print(f"Saved: {local_path}")

                if "before" in file_name.lower():
                    before_pcd = local_path
                elif "after" in file_name.lower():
                    after_pcd = local_path

    return before_pcd, after_pcd

def calculate_volume_change(before_pcd, after_pcd):
    if not before_pcd or not after_pcd:
        return None
    
    volume_result = subprocess.run([ 
        "CloudCompare", "-SILENT", "-O", before_pcd, "-O", after_pcd,
        "-C2C_DIST", "-SAVE_CLOUDS"
    ], capture_output=True, text=True)
    
    return volume_result.stdout

if __name__ == '__main__':
    app.run(debug=True)
