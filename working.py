from flask import Flask, request, jsonify, render_template, send_from_directory
import os
import subprocess
import cv2
import uuid
import requests

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

    before_result_path = detect_objects(before_path, "before")
    after_result_path = detect_objects(after_path, "after")

    project_id = get_or_create_project("construction_analysis")
    if not project_id:
        return jsonify({"error": "Failed to retrieve or create WebODM project"}), 500

    task_id = submit_task(project_id, before_path, after_path)
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
    response = requests.get(f"{WEBODM_URL}/tasks/{task_id}/", auth=WEBODM_AUTH)
    if response.status_code == 200:
        task_status = response.json().get("status")

        if task_status == "COMPLETED":
            before_pcd, after_pcd = download_and_extract_point_clouds(task_id)
            if before_pcd and after_pcd:
                volume_change = calculate_volume_change(before_pcd, after_pcd)
                return jsonify({
                    "status": "completed",
                    "volume_change": volume_change
                })
            return jsonify({"status": "failed", "error": "Point cloud extraction failed"})

        elif task_status in ["FAILED", "CANCELED"]:
            return jsonify({"status": "failed"})

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
                        cv2.FONT_HERSHEY_SIMPLEX, 2.5, (0, 255, 0), 3)

    processed_path = os.path.join(RESULTS_FOLDER, f"{prefix}_detected.jpg")
    cv2.imwrite(processed_path, img)
    return processed_path

@app.route('/results/<filename>')
def serve_results(filename):
    return send_from_directory(RESULTS_FOLDER, filename)

def get_or_create_project(project_name):
    response = requests.get(f"{WEBODM_URL}/projects/", auth=WEBODM_AUTH)
    if response.status_code == 200:
        for project in response.json():
            if project["name"] == project_name:
                return project["id"]

    response = requests.post(f"{WEBODM_URL}/projects/", auth=WEBODM_AUTH, data={"name": project_name})
    return response.json()["id"] if response.status_code == 201 else None

def submit_task(project_id, before_image, after_image):
    url = f"{WEBODM_URL}/projects/{project_id}/tasks/"
    
    with open(before_image, "rb") as before_file, open(after_image, "rb") as after_file:
        files = [('images[]', ('before.jpg', before_file, 'image/jpeg')),
                 ('images[]', ('after.jpg', after_file, 'image/jpeg'))]
        response = requests.post(url, auth=WEBODM_AUTH, files=files)

    return response.json().get("id") if response.status_code == 201 else None

def download_and_extract_point_clouds(task_id):
    assets_url = f"{WEBODM_URL}/tasks/{task_id}/assets/"
    response = requests.get(assets_url, auth=WEBODM_AUTH)

    if response.status_code != 200:
        return None, None

    before_pcd, after_pcd = None, None
    for asset in response.json():
        file_url = f"{WEBODM_URL}{asset['asset']}"
        file_name = os.path.basename(asset["asset"])
        local_path = os.path.join(POINT_CLOUD_FOLDER, file_name)

        if file_name.endswith((".las", ".ply")):
            file_response = requests.get(file_url, auth=WEBODM_AUTH, stream=True)
            if file_response.status_code == 200:
                with open(local_path, "wb") as file:
                    for chunk in file_response.iter_content(chunk_size=8192):
                        file.write(chunk)

                if "before" in file_name.lower():
                    before_pcd = local_path
                elif "after" in file_name.lower():
                    after_pcd = local_path

    return before_pcd, after_pcd

def calculate_volume_change(before_pcd, after_pcd):
    result = subprocess.run(["CloudCompare", "-SILENT", "-O", before_pcd, "-O", after_pcd,
                             "-C2C_DIST", "-SAVE_CLOUDS"], capture_output=True, text=True)
    return result.stdout

if __name__ == '__main__':
    app.run(debug=True)