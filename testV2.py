import os
import requests
import logging

# Configuration
WEBODM_URL = "http://127.0.0.1:8000/api"  # Change if different
WEBODM_AUTH = ("admin", "admin")  # Your WebODM username/password
PROJECT_ID = 12  # Set your project ID here
TASK_ID = "7134b0b9-c303-404c-8cdf-1fbddcc1fed7"     # Set your task ID here
DOWNLOAD_FOLDER = "downloaded_assets"

os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

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

def download_webodm_assets(project_id, task_id):
    """Automate the downloading of all assets for a WebODM task."""
    task_url = f"{WEBODM_URL}/projects/{project_id}/tasks/{task_id}/"
    session = requests.Session()
    session.auth = WEBODM_AUTH

    # Step 1: Get task details
    response = session.get(task_url)
    if response.status_code != 200:
        logging.error(f"❌ Failed to fetch task details (HTTP {response.status_code})")
        return

    task_data = response.json()
    assets = task_data.get("available_assets", [])

    if not assets:
        logging.warning(f"⚠️ No downloadable assets found for task {task_id}")
        return

    logging.info(f"✅ Found {len(assets)} assets to download.")

    # Step 2: Download each asset
    for asset_name in assets:
        # Use correct download endpoint
        if asset_name in SPECIAL_ASSETS:
            asset_url = f"{WEBODM_URL}/projects/{project_id}/tasks/{task_id}/download/{SPECIAL_ASSETS[asset_name]}"
        else:
            # fallback for normal assets like cameras.json
            asset_url = f"{WEBODM_URL}/projects/{project_id}/tasks/{task_id}/assets/{asset_name}"

        save_path = os.path.join(DOWNLOAD_FOLDER, asset_name)

        logging.info(f"⬇️ Downloading: {asset_name}")

        asset_response = session.get(asset_url, stream=True)
        if asset_response.status_code == 200:
            with open(save_path, "wb") as f:
                for chunk in asset_response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            logging.info(f"✅ Downloaded: {asset_name}")
        else:
            logging.error(f"❌ Failed to download {asset_name} (HTTP {asset_response.status_code})")

if __name__ == "__main__":
    download_webodm_assets(PROJECT_ID, TASK_ID)
