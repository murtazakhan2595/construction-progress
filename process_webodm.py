import requests

WEBODM_URL = "http://127.0.0.1:8000"
PROJECT_ID = 12
USERNAME = "admin"
PASSWORD = "admin"

before_image_path = r"D:\construction_progress\uploads\Before.jpeg"
after_image_path = r"D:\construction_progress\uploads\After.jpeg"


url = f"{WEBODM_URL}/api/projects/{PROJECT_ID}/tasks/"
auth = (USERNAME, PASSWORD)

files = {
    "images": open(before_image_path, "rb"),
    "images": open(after_image_path, "rb"),
}

response = requests.post(url, files=files, auth=auth)

print(response.status_code, response.text)  # Debug output

if response.status_code == 201:
    print("Images submitted successfully!")
else:
    print("Failed to submit images to WebODM")
