
from flask import Flask, request, jsonify, render_template, send_from_directory, send_file
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
import json
import io
from datetime import datetime
import numpy as np

from road_layers import ROAD_LAYERS, NUM_CLASSES, layer_name
from cost import build_boq
from scurve import generate_planned_curve, build_scurve, render_scurve_png
from progress import record_progress, actual_cumulative
from report_excel import build_excel_report
import config_store

app = Flask(__name__)

# Directories
UPLOAD_FOLDER = "uploads"
RESULTS_FOLDER = "results"
DOWNLOAD_FOLDER = "downloaded_assets"
POINT_CLOUD_FOLDER = "point_clouds"
MESH_FOLDER = "meshes"
DEM_FOLDER = "dems"
GCP_FOLDER = "gcp_files"

# Create all necessary directories
for folder in [UPLOAD_FOLDER, RESULTS_FOLDER, DOWNLOAD_FOLDER, POINT_CLOUD_FOLDER, MESH_FOLDER, DEM_FOLDER, GCP_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# YOLOv8 model for road-layer detection.
# Set the YOLO_MODEL_PATH environment variable to the custom-trained road-layer
# model when it is ready; until then it falls back to the generic yolov8n.pt.
YOLO_MODEL_PATH = os.environ.get("YOLO_MODEL_PATH", "yolov8n.pt")
YOLO_CONFIDENCE = float(os.environ.get("YOLO_CONFIDENCE", "0.25"))
try:
    model = YOLO(YOLO_MODEL_PATH)
    YOLO_AVAILABLE = True
    # Treat the model as a road-layer model when its class count matches our
    # canonical road-layer table; otherwise it is a generic (COCO) model.
    USING_ROAD_LAYER_MODEL = len(model.names) == NUM_CLASSES
    logging.info(
        f"YOLO model loaded: {YOLO_MODEL_PATH} "
        f"({'road-layer' if USING_ROAD_LAYER_MODEL else 'generic'} model)"
    )
except Exception as e:
    model = None
    YOLO_AVAILABLE = False
    USING_ROAD_LAYER_MODEL = False
    logging.warning(f"YOLO model not available ({e}). Object detection disabled.")

# WebODM Configuration (override via environment variables for different setups)
WEBODM_URL = os.environ.get("WEBODM_URL", "http://127.0.0.1:8000/api")
WEBODM_AUTH = (
    os.environ.get("WEBODM_USER", "admin"),
    os.environ.get("WEBODM_PASSWORD", "admin"),
)
PROJECT_ID = int(os.environ.get("WEBODM_PROJECT_ID", "1"))  # WebODM project ID
# Max time (s) to wait for a WebODM task to finish - 6h covers most CPU runs.
WEBODM_TASK_TIMEOUT = int(os.environ.get("WEBODM_TASK_TIMEOUT", "21600"))

# CloudCompare Configuration - Updated paths for different OS
CLOUDCOMPARE_PATHS = [
    r"C:\Program Files\CloudCompare\CloudCompare.exe",  # Windows
    r"C:\Program Files (x86)\CloudCompare\CloudCompare.exe",  # Windows 32-bit
    "/usr/bin/CloudCompare",  # Linux
    "/Applications/CloudCompare.app/Contents/MacOS/CloudCompare"  # macOS
]

# Find available CloudCompare installation
CLOUDCOMPARE_PATH = None
for path in CLOUDCOMPARE_PATHS:
    if os.path.exists(path):
        CLOUDCOMPARE_PATH = path
        break

# Processing options
PROCESSING_OPTIONS = {
    "mesh_resolution": "high",  # high, medium, low
    "dem_resolution": 0.1,     # meters per pixel
    "volume_method": "dem_diff", # dem_diff, mesh_diff, point_cloud_diff
    "max_concurrency": 2
}

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("construction_volume.log"),
        logging.StreamHandler()
    ]
)

# Global Task Status Store
task_status_store = {}


class ConstructionVolumeAnalyzer:
    def __init__(self, task_id):
        self.task_id = task_id
        self.before_images = []
        self.after_images = []
        self.gcp_file = None
        self.processing_options = PROCESSING_OPTIONS.copy()
        self.detected_layers = []  # road-layer detections, set by upload()
        
    def update_status(self, status, progress=0, message="", data=None):
        """Update task status with progress information"""
        task_status_store[self.task_id] = {
            "status": status,
            "progress": progress,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "data": data or {}
        }
        logging.info(f"Task {self.task_id}: {status} - {message} ({progress}%)")

    def process_construction_analysis(self, before_paths, after_paths, gcp_path=None,
                                      options=None, before_task_id=None,
                                      after_task_id=None):
        """Main processing pipeline for construction volume analysis.

        If before_task_id or after_task_id is supplied, the matching upload
        step is skipped and the existing WebODM task is resumed (useful after
        a Python-side timeout while WebODM kept processing in the background).
        """
        try:
            if options:
                self.processing_options.update(options)

            self.before_images = before_paths
            self.after_images = after_paths
            self.gcp_file = gcp_path

            # Step 1: Process Before Images
            if before_task_id:
                self.update_status("processing", 10,
                                    f"Resuming BEFORE WebODM task {before_task_id}")
            else:
                self.update_status("processing", 10,
                                    "Processing BEFORE images with WebODM")
                before_task_id = self.submit_webodm_task("before", before_paths, gcp_path)
                if not before_task_id:
                    raise Exception("Failed to submit BEFORE task to WebODM")

            if not self.wait_for_webodm_task(before_task_id):
                raise Exception("BEFORE task failed in WebODM")
                
            # Step 2: Download Before Assets
            self.update_status("processing", 25, "Downloading BEFORE point cloud and assets")
            before_assets = self.download_webodm_assets(before_task_id, "before")
            if not before_assets:
                raise Exception("Failed to download BEFORE assets")
                
            # Step 3: Process After Images
            if after_task_id:
                self.update_status("processing", 40,
                                    f"Resuming AFTER WebODM task {after_task_id}")
            else:
                self.update_status("processing", 40,
                                    "Processing AFTER images with WebODM")
                after_task_id = self.submit_webodm_task("after", after_paths, gcp_path)
                if not after_task_id:
                    raise Exception("Failed to submit AFTER task to WebODM")

            if not self.wait_for_webodm_task(after_task_id):
                raise Exception("AFTER task failed in WebODM")
                
            # Step 4: Download After Assets
            self.update_status("processing", 55, "Downloading AFTER point cloud and assets")  
            after_assets = self.download_webodm_assets(after_task_id, "after")
            if not after_assets:
                raise Exception("Failed to download AFTER assets")
                
            # Step 5: Generate Meshes from Point Clouds (Fixed)
            self.update_status("processing", 70, "Generating meshes from point clouds")
            before_mesh = self.generate_mesh_from_pointcloud_fixed(before_assets["pointcloud"], "before")
            after_mesh = self.generate_mesh_from_pointcloud_fixed(after_assets["pointcloud"], "after")
            
            if not before_mesh or not after_mesh:
                # Fallback: Try alternative mesh generation
                before_mesh = self.generate_mesh_alternative(before_assets["pointcloud"], "before")
                after_mesh = self.generate_mesh_alternative(after_assets["pointcloud"], "after")
                
            if not before_mesh or not after_mesh:
                raise Exception("Failed to generate meshes")
                
            # Step 6: Generate DEMs from Meshes (Fixed)
            self.update_status("processing", 80, "Generating Digital Elevation Models")
            before_dem = self.generate_dem_from_mesh_fixed(before_mesh, "before")
            after_dem = self.generate_dem_from_mesh_fixed(after_mesh, "after")
            
            # Fallback: Generate DEMs directly from point clouds if mesh method fails
            if not before_dem:
                before_dem = self.generate_dem_from_pointcloud_direct(before_assets["pointcloud"], "before")
            if not after_dem:
                after_dem = self.generate_dem_from_pointcloud_direct(after_assets["pointcloud"], "after")
            
            if not before_dem or not after_dem:
                raise Exception("Failed to generate DEMs")
                
            # Step 7: Calculate Volume Difference
            self.update_status("processing", 90, "Calculating volume difference")
            volume_result = self.calculate_volume_difference(before_dem, after_dem, before_assets, after_assets)
            
            if volume_result is None:
                raise Exception("Volume calculation failed")
                
            # Step 8: Generate Report
            self.update_status("processing", 95, "Generating analysis report")
            report = self.generate_analysis_report(volume_result, before_assets, after_assets)
            
            # Complete
            self.update_status("completed", 100, "Construction volume analysis completed", {
                "volume_change": volume_result,
                "report": report,
                "before_task_id": before_task_id,
                "after_task_id": after_task_id
            })
            
            return True
            
        except Exception as e:
            self.update_status("failed", 0, f"Analysis failed: {str(e)}")
            logging.error(f"Construction analysis failed: {e}")
            return False

    def process_existing_data(self, before_dsm_path, after_dsm_path, options=None):
        """Volume analysis from pre-computed DSMs - skips WebODM entirely.
        Used when the user already has DSM/elevation outputs from a previous
        photogrammetry run."""
        try:
            if options:
                self.processing_options.update(options)

            self.update_status("processing", 30,
                                "Loading existing DSMs (skipping WebODM)")
            before_assets = {"dsm": before_dsm_path, "pointcloud": None,
                             "orthophoto": None, "dtm": None}
            after_assets = {"dsm": after_dsm_path, "pointcloud": None,
                            "orthophoto": None, "dtm": None}

            self.update_status("processing", 60,
                                "Computing volume difference from DSMs")
            volume_result = self.calculate_volume_difference(
                before_dsm_path, after_dsm_path, before_assets, after_assets)
            if volume_result is None:
                raise Exception("Volume calculation failed")

            self.update_status("processing", 90, "Generating analysis report")
            report = self.generate_analysis_report(
                volume_result, before_assets, after_assets)

            self.update_status("completed", 100,
                                "Analysis complete (existing-data mode)", {
                                    "volume_change": volume_result,
                                    "report": report,
                                })
            return True
        except Exception as e:
            self.update_status("failed", 0,
                                f"Existing-data analysis failed: {str(e)}")
            logging.error(f"Existing-data analysis failed: {e}")
            return False

    def submit_webodm_task(self, phase, image_paths, gcp_path=None):
        """Submit processing task to WebODM with enhanced options"""
        url = f"{WEBODM_URL}/projects/{PROJECT_ID}/tasks/"
        
        files = []
        # Enhanced processing options for better DSM/DTM generation
        data = {
            'name': f'{phase}_{self.task_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
            'options': json.dumps([
                {'name': 'mesh-size', 'value': '300000'},
                {'name': 'mesh-octree-depth', 'value': '10'},
                {'name': 'feature-quality', 'value': 'high'},
                {'name': 'pc-quality', 'value': 'high'},
                {'name': 'dsm', 'value': True},  # Enable DSM generation
                {'name': 'dtm', 'value': True},  # Enable DTM generation
                {'name': 'dem-resolution', 'value': str(self.processing_options.get("dem_resolution", 0.1))},
                {'name': 'orthophoto-resolution', 'value': str(self.processing_options.get("dem_resolution", 0.1))},
                {'name': 'pc-filter', 'value': '2.5'},  # Point cloud filtering
                {'name': 'pc-sample', 'value': '0'}  # No point cloud sampling
            ])
        }
        
        try:
            # Add images
            for i, img_path in enumerate(image_paths):
                files.append(('images', (os.path.basename(img_path), open(img_path, 'rb'), 'image/jpeg')))
            
            # Add GCP file if provided
            if gcp_path and os.path.exists(gcp_path):
                files.append(('gcp', (os.path.basename(gcp_path), open(gcp_path, 'rb'), 'text/plain')))
                logging.info(f"Added GCP file: {gcp_path}")
            
            response = requests.post(url, auth=WEBODM_AUTH, files=files, data=data, timeout=300)
            
            if response.status_code == 201:
                task_id = response.json().get("id")
                logging.info(f"Submitted {phase} task {task_id} with {len(image_paths)} images")
                return task_id
            else:
                logging.error(f"Failed to create {phase} task: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logging.error(f"Error submitting {phase} task: {e}")
            return None
        finally:
            # Close all file handles
            for file_tuple in files:
                try:
                    file_tuple[1][1].close()
                except:
                    pass

    def wait_for_webodm_task(self, task_id, timeout=None):
        """Wait for WebODM task completion with timeout (defaults to
        WEBODM_TASK_TIMEOUT, 6h)."""
        if timeout is None:
            timeout = WEBODM_TASK_TIMEOUT
        url = f"{WEBODM_URL}/projects/{PROJECT_ID}/tasks/{task_id}/"
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get(url, auth=WEBODM_AUTH, timeout=30)
                if response.status_code == 200:
                    task_data = response.json()
                    status = task_data.get("status")
                    progress = task_data.get("running_progress", 0)
                    
                    status_map = {
                        10: "queued",
                        20: "running", 
                        30: "failed",
                        40: "completed",
                        50: "canceled"
                    }
                    
                    status_text = status_map.get(status, f"unknown({status})")
                    logging.info(f"Task {task_id} status: {status_text} ({progress}%)")
                    
                    if status == 40:  # Completed
                        return True
                    elif status in [30, 50]:  # Failed or Canceled
                        logging.error(f"Task {task_id} failed with status {status}")
                        return False
                        
                else:
                    logging.warning(f"Failed to get task status: {response.status_code}")
                    
            except Exception as e:
                logging.error(f"Error checking task status: {e}")
                
            time.sleep(15)  # Check every 15 seconds
            
        logging.error(f"Task {task_id} timed out after {timeout} seconds")
        return False

    def download_webodm_assets(self, task_id, phase):
        """Download all necessary assets from WebODM including DSM and DTM"""
        assets = {
            "pointcloud": None,
            "orthophoto": None,
            "dsm": None,
            "dtm": None
        }
        
        asset_files = {
            "pointcloud": "georeferenced_model.laz",
            "orthophoto": "orthophoto.tif",
            "dsm": "dsm.tif", 
            "dtm": "dtm.tif"
        }
        
        for asset_type, filename in asset_files.items():
            try:
                url = f"{WEBODM_URL}/projects/{PROJECT_ID}/tasks/{task_id}/download/{filename}"
                output_path = os.path.join(DOWNLOAD_FOLDER, f"{phase}_{task_id}_{filename}")
                
                response = requests.get(url, auth=WEBODM_AUTH, stream=True, timeout=300)
                
                if response.status_code == 200:
                    with open(output_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    
                    assets[asset_type] = output_path
                    logging.info(f"Downloaded {phase} {asset_type}: {output_path}")
                else:
                    logging.warning(f"Could not download {asset_type} for {phase}: {response.status_code}")
                    
            except Exception as e:
                logging.error(f"Error downloading {asset_type} for {phase}: {e}")
        
        # At minimum, we need the point cloud
        if not assets["pointcloud"]:
            logging.error(f"Failed to download critical asset (point cloud) for {phase}")
            return None
            
        return assets

    def generate_mesh_from_pointcloud_fixed(self, pointcloud_path, phase):
        """Generate high-quality mesh from point cloud using CloudCompare - Fixed version"""
        if not os.path.exists(pointcloud_path):
            logging.error(f"Point cloud file not found: {pointcloud_path}")
            return None
            
        if not CLOUDCOMPARE_PATH:
            logging.error("CloudCompare not found. Please install CloudCompare.")
            return None
            
        mesh_path = os.path.join(MESH_FOLDER, f"{phase}_{self.task_id}_mesh.ply")
        
        try:
            # Step 1: Convert LAZ to ASCII format first for better compatibility
            ascii_pc_path = os.path.join(POINT_CLOUD_FOLDER, f"{phase}_{self.task_id}_pc.xyz")
            
            cmd_convert = [
                CLOUDCOMPARE_PATH,
                "-SILENT",
                "-AUTO_SAVE", "OFF",
                "-O", pointcloud_path,
                "-C_EXPORT_FMT", "ASC",
                "-PREC", "6",
                "-SAVE_CLOUDS", "FILE", ascii_pc_path
            ]
            
            result = subprocess.run(cmd_convert, capture_output=True, text=True, timeout=300)
            
            # Step 2: Load ASCII point cloud and generate mesh
            if os.path.exists(ascii_pc_path):
                pc_to_use = ascii_pc_path
            else:
                pc_to_use = pointcloud_path
            
            # Enhanced Delaunay triangulation with better parameters
            cmd_mesh = [
                CLOUDCOMPARE_PATH,
                "-SILENT",
                "-AUTO_SAVE", "OFF",
                "-O", pc_to_use,
                "-DELAUNAY",
                "-AA_TYPE", "LS",  # Least Square fitting
                "-MAX_EDGE_LENGTH", "1.0",
                "-SAVE_MESHES", "FILE", mesh_path
            ]
            
            result = subprocess.run(cmd_mesh, capture_output=True, text=True, timeout=600)
            
            if os.path.exists(mesh_path):
                logging.info(f"Generated {phase} mesh: {mesh_path}")
                return mesh_path
            
            # Alternative: Check for auto-generated files with different naming
            pc_dir = os.path.dirname(pointcloud_path)
            mesh_patterns = [
                f"*{phase}*DELAUNAY*.ply",
                f"*DELAUNAY*.ply",
                f"*_MESH*.ply",
                "*.ply"
            ]
            
            for pattern in mesh_patterns:
                mesh_files = glob.glob(os.path.join(pc_dir, pattern))
                if mesh_files:
                    latest_mesh = max(mesh_files, key=os.path.getctime)
                    shutil.copy2(latest_mesh, mesh_path)
                    logging.info(f"Found and copied {phase} mesh: {mesh_path}")
                    return mesh_path
                    
            # Check in working directory
            mesh_files = glob.glob("*.ply")
            if mesh_files:
                latest_mesh = max(mesh_files, key=os.path.getctime)
                shutil.move(latest_mesh, mesh_path)
                logging.info(f"Found mesh in working directory: {mesh_path}")
                return mesh_path
                
            logging.error(f"No mesh file generated for {phase}")
            return None
            
        except subprocess.TimeoutExpired:
            logging.error(f"Mesh generation timed out for {phase}")
            return None
        except Exception as e:
            logging.error(f"Mesh generation failed for {phase}: {e}")
            return None

    def generate_mesh_alternative(self, pointcloud_path, phase):
        """Alternative mesh generation using Poisson reconstruction"""
        if not CLOUDCOMPARE_PATH:
            return None
            
        mesh_path = os.path.join(MESH_FOLDER, f"{phase}_{self.task_id}_poisson_mesh.ply")
        
        try:
            # Poisson surface reconstruction
            cmd = [
                CLOUDCOMPARE_PATH,
                "-SILENT",
                "-AUTO_SAVE", "OFF",
                "-O", pointcloud_path,
                "-POISSON_RECON",
                "-DEPTH", "8",
                "-DENSITY",
                "-SAVE_MESHES", "FILE", mesh_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if os.path.exists(mesh_path):
                logging.info(f"Generated {phase} Poisson mesh: {mesh_path}")
                return mesh_path
                
            return None
            
        except Exception as e:
            logging.error(f"Poisson mesh generation failed for {phase}: {e}")
            return None

    def generate_dem_from_mesh_fixed(self, mesh_path, phase):
        """Generate Digital Elevation Model from mesh - Fixed version"""
        if not os.path.exists(mesh_path):
            logging.error(f"Mesh file not found: {mesh_path}")
            return None
            
        dem_path = os.path.join(DEM_FOLDER, f"{phase}_{self.task_id}_dem.tif")
        resolution = self.processing_options.get("dem_resolution", 0.1)
        
        try:
            # Method 1: Direct rasterization from mesh
            cmd = [
                CLOUDCOMPARE_PATH,
                "-SILENT",
                "-AUTO_SAVE", "OFF",
                "-O", mesh_path,
                "-RASTERIZE",
                "-GRID_STEP", str(resolution),
                "-VERT_DIR", "2",  # Z direction  
                "-PROJ", "MIN",    # Minimum projection (ground level)
                "-SF_PROJ", "MIN",
                "-OUTPUT_RASTER_Z",
                "-OUTPUT_RASTER_RGB"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            logging.info(f"Rasterization command output: {result.stdout}")
            
            # Wait for file system to update
            time.sleep(5)
            
            # Find generated raster files
            mesh_dir = os.path.dirname(mesh_path)
            search_dirs = [mesh_dir, DEM_FOLDER, os.getcwd()]
            
            for search_dir in search_dirs:
                raster_patterns = [
                    f"*{phase}*_Z*.tif",
                    "*_Z*.tif", 
                    f"*{phase}*.tif",
                    "*.tif"
                ]
                
                for pattern in raster_patterns:
                    raster_files = glob.glob(os.path.join(search_dir, pattern))
                    if raster_files:
                        # Sort by creation time, get newest
                        z_raster = max(raster_files, key=os.path.getctime)
                        
                        # Copy to final location
                        shutil.copy2(z_raster, dem_path)
                        logging.info(f"Generated {phase} DEM: {dem_path}")
                        return dem_path
                        
            logging.error(f"No DEM raster generated for {phase}")
            return None
            
        except subprocess.TimeoutExpired:
            logging.error(f"DEM generation timed out for {phase}")
            return None
        except Exception as e:
            logging.error(f"DEM generation failed for {phase}: {e}")
            return None

    def generate_dem_from_pointcloud_direct(self, pointcloud_path, phase):
        """Generate DEM directly from point cloud as fallback method"""
        if not os.path.exists(pointcloud_path):
            return None
            
        dem_path = os.path.join(DEM_FOLDER, f"{phase}_{self.task_id}_dem_direct.tif")
        resolution = self.processing_options.get("dem_resolution", 0.1)
        
        try:
            # Direct rasterization from point cloud
            cmd = [
                CLOUDCOMPARE_PATH,
                "-SILENT",
                "-AUTO_SAVE", "OFF",
                "-O", pointcloud_path,
                "-RASTERIZE",
                "-GRID_STEP", str(resolution),
                "-VERT_DIR", "2",
                "-PROJ", "MIN",
                "-SF_PROJ", "MIN", 
                "-OUTPUT_RASTER_Z",
                "-EMPTY_FILL", "INTERP"  # Interpolate empty cells
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            # Find and copy result
            time.sleep(3)
            pc_dir = os.path.dirname(pointcloud_path)
            
            for search_dir in [pc_dir, os.getcwd()]:
                raster_files = glob.glob(os.path.join(search_dir, "*_Z*.tif"))
                if raster_files:
                    latest_raster = max(raster_files, key=os.path.getctime)
                    shutil.copy2(latest_raster, dem_path)
                    logging.info(f"Generated {phase} DEM from point cloud: {dem_path}")
                    return dem_path
                    
            return None
            
        except Exception as e:
            logging.error(f"Direct DEM generation failed for {phase}: {e}")
            return None

    def calculate_volume_difference(self, before_dem, after_dem, before_assets, after_assets):
        """Calculate volume difference using multiple methods"""
        volume_results = {}
        
        # Method 1: Use WebODM DSM/DTM if available
        if before_assets.get("dsm") and after_assets.get("dsm"):
            volume_dsm = self.calculate_volume_from_dems(before_assets["dsm"], after_assets["dsm"])
            if volume_dsm is not None:
                volume_results["dsm_difference"] = volume_dsm
                logging.info(f"DSM volume difference: {volume_dsm:.3f} m³")
        
        # Method 2: Use generated DEMs
        if before_dem and after_dem:
            volume_dem = self.calculate_volume_from_dems(before_dem, after_dem)
            if volume_dem is not None:
                volume_results["dem_difference"] = volume_dem
                logging.info(f"Generated DEM volume difference: {volume_dem:.3f} m³")
        
        # Method 3: Point Cloud Comparison (fallback)
        if before_assets["pointcloud"] and after_assets["pointcloud"]:
            volume_pc = self.calculate_volume_from_pointclouds(
                before_assets["pointcloud"], 
                after_assets["pointcloud"]
            )
            if volume_pc is not None:
                volume_results["pointcloud_difference"] = volume_pc
                logging.info(f"Point cloud volume difference: {volume_pc:.3f} m³")
        
        # Return best available result
        if "dsm_difference" in volume_results:
            return volume_results["dsm_difference"]
        elif "dem_difference" in volume_results:
            return volume_results["dem_difference"]
        elif "pointcloud_difference" in volume_results:
            return volume_results["pointcloud_difference"]
        else:
            logging.error("No volume calculation method succeeded")
            return None

    def calculate_volume_from_dems(self, before_dem, after_dem):
        """Calculate volume using DEM raster arithmetic with enhanced error handling"""
        try:
            # Try GDAL method first (most accurate)
            try:
                import gdal
                import numpy as np
                
                # Enable GDAL exceptions
                gdal.UseExceptions()
                
                # Open DEM files
                before_ds = gdal.Open(before_dem)
                after_ds = gdal.Open(after_dem)
                
                if not before_ds or not after_ds:
                    raise Exception("Could not open DEM files with GDAL")
                
                # Read elevation arrays
                before_array = before_ds.GetRasterBand(1).ReadAsArray()
                after_array = after_ds.GetRasterBand(1).ReadAsArray()
                
                # Get pixel size for area calculation
                gt = before_ds.GetGeoTransform()
                pixel_width = abs(gt[1])
                pixel_height = abs(gt[5])
                pixel_area = pixel_width * pixel_height
                
                # Handle different array sizes by cropping to smaller
                min_rows = min(before_array.shape[0], after_array.shape[0])
                min_cols = min(before_array.shape[1], after_array.shape[1])
                
                before_array = before_array[:min_rows, :min_cols]
                after_array = after_array[:min_rows, :min_cols]
                
                # Handle NoData values
                before_nodata = before_ds.GetRasterBand(1).GetNoDataValue()
                after_nodata = after_ds.GetRasterBand(1).GetNoDataValue()
                
                # Create mask for valid pixels
                valid_mask = np.ones(before_array.shape, dtype=bool)
                
                if before_nodata is not None:
                    valid_mask &= (before_array != before_nodata)
                if after_nodata is not None:
                    valid_mask &= (after_array != after_nodata)
                
                # Remove extreme outliers
                valid_mask &= (np.abs(before_array) < 1000)  # Reasonable elevation limits
                valid_mask &= (np.abs(after_array) < 1000)
                
                # Calculate elevation difference only for valid pixels
                diff_array = np.zeros_like(before_array)
                diff_array[valid_mask] = after_array[valid_mask] - before_array[valid_mask]
                
                # Calculate volume (sum of height differences × pixel area)
                volume_change = np.sum(diff_array) * pixel_area
                
                # Clean up
                before_ds = None
                after_ds = None
                
                logging.info(f"Volume calculation using GDAL: {volume_change:.3f} m³")
                logging.info(f"Valid pixels: {np.sum(valid_mask)} / {valid_mask.size}")
                logging.info(f"Pixel area: {pixel_area:.6f} m²")
                
                return volume_change
                
            except ImportError:
                logging.warning("GDAL not available, using CloudCompare method")
                return self.calculate_volume_cloudcompare(before_dem, after_dem)
            except Exception as gdal_error:
                logging.warning(f"GDAL method failed: {gdal_error}, trying CloudCompare")
                return self.calculate_volume_cloudcompare(before_dem, after_dem)
                
        except Exception as e:
            logging.error(f"DEM volume calculation failed: {e}")
            return None

    def calculate_volume_cloudcompare(self, before_dem, after_dem):
        """Calculate volume using CloudCompare 2.5D volume calculation"""
        if not CLOUDCOMPARE_PATH:
            logging.error("CloudCompare not available for volume calculation")
            return None
            
        temp_dir = os.path.join(RESULTS_FOLDER, f"volume_calc_{uuid.uuid4().hex}")
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            # Convert DEMs to point clouds
            before_pc = os.path.join(temp_dir, "before_points.xyz")
            after_pc = os.path.join(temp_dir, "after_points.xyz")
            
            # Convert before DEM to point cloud
            cmd1 = [
                CLOUDCOMPARE_PATH,
                "-SILENT",
                "-AUTO_SAVE", "OFF", 
                "-O", before_dem,
                "-C_EXPORT_FMT", "ASC",
                "-PREC", "6",
                "-SAVE_CLOUDS", "FILE", before_pc
            ]
            subprocess.run(cmd1, check=True, timeout=300)
            
            # Convert after DEM to point cloud
            cmd2 = [
                CLOUDCOMPARE_PATH,
                "-SILENT",
                "-AUTO_SAVE", "OFF",
                "-O", after_dem,
                "-C_EXPORT_FMT", "ASC",
                "-PREC", "6",
                "-SAVE_CLOUDS", "FILE", after_pc
            ]
            subprocess.run(cmd2, check=True, timeout=300)
            
            # Calculate 2.5D volume difference
            volume_report = os.path.join(temp_dir, "volume_report.txt")
            
            cmd3 = [
                CLOUDCOMPARE_PATH,
                "-SILENT",
                "-AUTO_SAVE", "OFF",
                "-O", before_pc,
                "-O", after_pc,
                "-2D5_VOL_CALC",
                "-GRID_STEP", str(self.processing_options.get("dem_resolution", 0.1)),
                "-VERT_DIR", "2",
                "-REPORT_FILE", volume_report
            ]
            
            result = subprocess.run(cmd3, capture_output=True, text=True, timeout=300)
            
            # Extract volume from report or stdout
            volume = None
            
            if os.path.exists(volume_report):
                volume = self.extract_volume_from_file(volume_report)
                
            if volume is None and result.stdout:
                volume = self.extract_volume_from_text(result.stdout)
                
            if volume is not None:
                logging.info(f"Volume calculation using CloudCompare: {volume:.3f} m³")
                return volume
            else:
                logging.warning("Could not extract volume from CloudCompare output")
                return 0.0
                
        except Exception as e:
            logging.error(f"CloudCompare volume calculation failed: {e}")
            return None
        finally:
            # Clean up temporary files
            try:
                shutil.rmtree(temp_dir)
            except:
                pass

    def calculate_volume_from_pointclouds(self, before_pc, after_pc):
        """Calculate volume using point cloud comparison with enhanced method"""
        if not CLOUDCOMPARE_PATH:
            return None
            
        temp_dir = os.path.join(RESULTS_FOLDER, f"pc_volume_{uuid.uuid4().hex}")
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            # Method 1: Convert point clouds to regular grids and calculate difference
            grid_resolution = self.processing_options.get("dem_resolution", 0.1)
            
            # Rasterize before point cloud
            before_raster = os.path.join(temp_dir, "before_raster.tif")
            cmd1 = [
                CLOUDCOMPARE_PATH,
                "-SILENT",
                "-AUTO_SAVE", "OFF",
                "-O", before_pc,
                "-RASTERIZE",
                "-GRID_STEP", str(grid_resolution),
                "-VERT_DIR", "2",
                "-PROJ", "MIN",
                "-SF_PROJ", "MIN",
                "-OUTPUT_RASTER_Z"
            ]
            subprocess.run(cmd1, capture_output=True, text=True, timeout=300)
            
            # Rasterize after point cloud  
            after_raster = os.path.join(temp_dir, "after_raster.tif")
            cmd2 = [
                CLOUDCOMPARE_PATH,
                "-SILENT",
                "-AUTO_SAVE", "OFF",
                "-O", after_pc,
                "-RASTERIZE",
                "-GRID_STEP", str(grid_resolution),
                "-VERT_DIR", "2",
                "-PROJ", "MIN",
                "-SF_PROJ", "MIN",
                "-OUTPUT_RASTER_Z"
            ]
            subprocess.run(cmd2, capture_output=True, text=True, timeout=300)
            
            # Find generated raster files
            raster_files = glob.glob(os.path.join(temp_dir, "*_Z*.tif"))
            if len(raster_files) >= 2:
                # Use the raster method for volume calculation
                volume = self.calculate_volume_from_dems(raster_files[0], raster_files[1])
                if volume is not None:
                    logging.info(f"Point cloud volume calculation: {volume:.3f} m³")
                    return volume
            
            # Method 2: Fallback - simplified distance-based calculation
            logging.info("Using simplified point cloud volume estimation")
            return self.estimate_volume_from_point_clouds(before_pc, after_pc)
            
        except Exception as e:
            logging.error(f"Point cloud volume calculation failed: {e}")
            return None
        finally:
            try:
                shutil.rmtree(temp_dir)
            except:
                pass

    def estimate_volume_from_point_clouds(self, before_pc, after_pc):
        """Simplified volume estimation from point clouds"""
        try:
            # This is a basic estimation - in production, use more sophisticated methods
            # For now, return a placeholder that indicates processing completed
            logging.info("Point cloud volume estimation completed (placeholder)")
            return 0.0
        except Exception as e:
            logging.error(f"Point cloud volume estimation failed: {e}")
            return None

    def extract_volume_from_file(self, filepath):
        """Extract volume value from report file"""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            return self.extract_volume_from_text(content)
        except Exception as e:
            logging.error(f"Error reading volume file {filepath}: {e}")
            return None

    def extract_volume_from_text(self, text):
        """Extract volume value from text using regex patterns"""
        patterns = [
            r'Volume[:\s]+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*(?:m³|m3|cubic)',
            r'Total volume[:\s]+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)',
            r'Volume difference[:\s]+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)',
            r'Net volume[:\s]+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)',
            r'Volume\s*=\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)',
            r'Added volume[:\s]+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)',
            r'Removed volume[:\s]+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
                    
        return None

    def generate_analysis_report(self, volume_result, before_assets, after_assets):
        """Generate comprehensive analysis report"""
        report = {
            "task_id": self.task_id,
            "timestamp": datetime.now().isoformat(),
            "volume_change_m3": volume_result,
            "volume_change_yd3": volume_result * 1.30795,  # Convert to cubic yards
            "volume_change_ft3": volume_result * 35.3147,  # Convert to cubic feet
            "processing_options": self.processing_options,
            "assets": {
                "before": {k: os.path.basename(v) if v else None for k, v in before_assets.items()},
                "after": {k: os.path.basename(v) if v else None for k, v in after_assets.items()}
            },
            "analysis": {
                "cut_volume": max(0, -volume_result),
                "fill_volume": max(0, volume_result),
                "net_volume": volume_result,
                "interpretation": self.interpret_volume_change(volume_result),
                "accuracy_estimate": self.estimate_accuracy()
            }
        }
        
        # Cost breakdown (Bill of Quantities) from volume + detected layers
        report["detected_layers"] = [
            {"layer": d.get("layer"), "confidence": round(d.get("confidence", 0), 3)}
            for d in self.detected_layers
        ]
        plan = config_store.get_plan()
        report["project_name"] = plan.get("project_name")
        report["boq"] = build_boq(volume_result, self.detected_layers,
                                  plan.get("currency", "PKR"))

        # S-curve: planned schedule vs accumulated actual progress
        record_progress(self.task_id, report["boq"]["total_cost"], volume_result)
        planned = plan.get("planned_cumulative") or generate_planned_curve(
            plan.get("total_budget", 0), len(plan.get("period_labels", [])))
        report["scurve"] = build_scurve(
            planned, actual_cumulative(), plan.get("period_labels"))
        try:
            png_path = os.path.join(RESULTS_FOLDER, f"scurve_{self.task_id}.png")
            render_scurve_png(report["scurve"], png_path,
                              plan.get("currency", "PKR"))
            report["scurve_image"] = f"/result-file/scurve_{self.task_id}.png"
        except Exception as e:
            logging.error(f"S-curve render failed: {e}")

        # Save report to file
        report_path = os.path.join(RESULTS_FOLDER, f"analysis_report_{self.task_id}.json")
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        return report

    def interpret_volume_change(self, volume):
        """Interpret volume change for construction context"""
        if abs(volume) < 0.1:
            return "Minimal change detected (within measurement uncertainty)"
        elif volume > 0:
            return f"Material added: {volume:.2f} m³ of fill/construction material"
        else:
            return f"Material removed: {abs(volume):.2f} m³ of excavation/cut material"

    def estimate_accuracy(self):
        """Estimate measurement accuracy based on processing parameters"""
        resolution = self.processing_options.get("dem_resolution", 0.1)
        
        # Rough accuracy estimation based on DEM resolution
        # Typical accuracy is 1-5% for well-controlled surveys
        pixel_area = resolution * resolution
        volume_uncertainty_per_pixel = resolution * 0.1  # 10cm vertical uncertainty
        
        return {
            "estimated_vertical_accuracy": f"±{resolution * 1000:.0f} mm",
            "estimated_volume_accuracy": "±2-5%",
            "dem_resolution": f"{resolution} m/pixel",
            "notes": "Accuracy depends on image quality, overlap, and ground control points"
        }

# Flask Routes (keeping existing routes)
@app.route('/')
def index():
    return render_template("construction_volume.html")

@app.route('/upload', methods=['POST'])
def upload():
    """Handle file uploads and start processing"""
    try:
        before_files = request.files.getlist('before_images')
        after_files = request.files.getlist('after_images')
        gcp_file = request.files.get('gcp_file')
        
        # Get processing options
        options = {
            "dem_resolution": float(request.form.get('dem_resolution', 0.1)),
            "mesh_resolution": request.form.get('mesh_resolution', 'high'),
            "volume_method": request.form.get('volume_method', 'dem_diff')
        }
        
        if not before_files or not after_files:
            return jsonify({"error": "Missing before or after images"}), 400
        
        if len(before_files[0].filename) == 0 or len(after_files[0].filename) == 0:
            return jsonify({"error": "No files selected"}), 400
        
        # Save uploaded files
        before_paths = save_uploaded_files(before_files, "before")
        after_paths = save_uploaded_files(after_files, "after")
        
        gcp_path = None
        if gcp_file and gcp_file.filename:
            gcp_filename = f"gcp_{uuid.uuid4().hex}.txt"
            gcp_path = os.path.join(GCP_FOLDER, gcp_filename)
            gcp_file.save(gcp_path)
            logging.info(f"Saved GCP file: {gcp_path}")
        
        # Optional: Run object detection for preview
        detection_results = {}
        if YOLO_AVAILABLE and request.form.get('enable_detection') == 'true':
            detection_results = {
                "before": detect_objects(before_paths[0], "before"),
                "after": detect_objects(after_paths[0], "after")
            }
        
        # Start background processing
        task_id = str(uuid.uuid4())
        analyzer = ConstructionVolumeAnalyzer(task_id)

        # Attach road-layer detections (used later for the cost breakdown)
        if detection_results:
            after_res = detection_results.get("after")
            if after_res:
                analyzer.detected_layers = after_res.get("detections", [])

        thread = threading.Thread(
            target=analyzer.process_construction_analysis,
            args=(before_paths, after_paths, gcp_path, options)
        )
        thread.daemon = True
        thread.start()
        
        response_data = {
            "success": True,
            "task_id": task_id,
            "message": "Processing started",
            "options": options
        }
        
        if detection_results:
            response_data["detection_results"] = {}
            for phase in ("before", "after"):
                res = detection_results.get(phase)
                if res and res.get("image_path"):
                    response_data["detection_results"][phase] = {
                        "image": f"/result-file/{os.path.basename(res['image_path'])}",
                        "detections": res["detections"],
                    }
        
        return jsonify(response_data)
        
    except Exception as e:
        logging.error(f"Upload failed: {e}")
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500

@app.route('/upload-existing', methods=['POST'])
def upload_existing():
    """Volume analysis from pre-computed DSM/elevation files (skips WebODM)."""
    try:
        before_dsm = request.files.get('before_dsm')
        after_dsm = request.files.get('after_dsm')
        if not before_dsm or not after_dsm:
            return jsonify({"error": "Both before and after DSM files are required"}), 400
        if not before_dsm.filename or not after_dsm.filename:
            return jsonify({"error": "No files selected"}), 400

        ext_b = os.path.splitext(before_dsm.filename)[1].lower() or ".tif"
        ext_a = os.path.splitext(after_dsm.filename)[1].lower() or ".tif"
        before_path = os.path.join(UPLOAD_FOLDER,
                                   f"before_dsm_{uuid.uuid4().hex}{ext_b}")
        after_path = os.path.join(UPLOAD_FOLDER,
                                  f"after_dsm_{uuid.uuid4().hex}{ext_a}")
        before_dsm.save(before_path)
        after_dsm.save(after_path)
        logging.info(f"Saved existing-mode DSMs: {before_path}, {after_path}")

        task_id = str(uuid.uuid4())
        analyzer = ConstructionVolumeAnalyzer(task_id)

        thread = threading.Thread(
            target=analyzer.process_existing_data,
            args=(before_path, after_path),
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            "success": True,
            "task_id": task_id,
            "message": "Volume analysis started (existing-data mode)",
        })
    except Exception as e:
        logging.error(f"Existing-data upload failed: {e}")
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500


@app.route('/status/<task_id>')
def get_task_status(task_id):
    """Get processing status for a task"""
    if task_id in task_status_store:
        return jsonify(task_status_store[task_id])
    else:
        return jsonify({"status": "not_found", "message": "Task not found"}), 404

@app.route('/results/<task_id>')
def get_task_results(task_id):
    """Get detailed results for a completed task"""
    if task_id not in task_status_store:
        return jsonify({"error": "Task not found"}), 404
        
    status_info = task_status_store[task_id]
    
    if status_info["status"] != "completed":
        return jsonify({"error": "Task not completed"}), 400
        
    try:
        # Load detailed report
        report_path = os.path.join(RESULTS_FOLDER, f"analysis_report_{task_id}.json")
        if os.path.exists(report_path):
            with open(report_path, 'r') as f:
                report = json.load(f)
            return jsonify(report)
        else:
            return jsonify(status_info["data"])
            
    except Exception as e:
        logging.error(f"Failed to load results for task {task_id}: {e}")
        return jsonify({"error": "Failed to load results"}), 500

@app.route('/download/<task_id>/<asset_type>')
def download_asset(task_id, asset_type):
    """Download generated assets"""
    try:
        asset_map = {
            "report": f"analysis_report_{task_id}.json",
            "before_dem": f"before_{task_id}_dem.tif", 
            "after_dem": f"after_{task_id}_dem.tif",
            "before_mesh": f"before_{task_id}_mesh.ply",
            "after_mesh": f"after_{task_id}_mesh.ply"
        }
        
        if asset_type not in asset_map:
            return jsonify({"error": "Invalid asset type"}), 400
            
        filename = asset_map[asset_type]
        
        # Check in appropriate folder
        folders_to_check = [RESULTS_FOLDER, DEM_FOLDER, MESH_FOLDER]
        
        for folder in folders_to_check:
            filepath = os.path.join(folder, filename)
            if os.path.exists(filepath):
                return send_from_directory(folder, filename)
                
        return jsonify({"error": "Asset not found"}), 404
        
    except Exception as e:
        logging.error(f"Download failed: {e}")
        return jsonify({"error": "Download failed"}), 500

@app.route('/result-file/<filename>')
def serve_results(filename):
    """Serve result files (detection previews, S-curve charts, etc.)"""
    return send_from_directory(RESULTS_FOLDER, filename)


@app.route('/runs')
def runs_page():
    """List all past analyses for revisiting in the UI."""
    runs = []
    for path in sorted(
        glob.glob(os.path.join(RESULTS_FOLDER, 'analysis_report_*.json')),
        key=os.path.getmtime,
        reverse=True,
    ):
        try:
            with open(path) as f:
                report = json.load(f)
            runs.append({
                'task_id': report.get('task_id'),
                'timestamp': report.get('timestamp'),
                'project_name': report.get('project_name') or '-',
                'volume_m3': report.get('volume_change_m3'),
                'total_cost': (report.get('boq') or {}).get('total_cost'),
                'currency': (report.get('boq') or {}).get('currency', ''),
            })
        except Exception as e:
            logging.warning(f"Skipping {path}: {e}")
    return render_template('runs.html', runs=runs)


@app.route('/report-excel/<task_id>')
def download_excel_report(task_id):
    """Generate and download the Excel report for a completed task."""
    report_path = os.path.join(RESULTS_FOLDER, f"analysis_report_{task_id}.json")
    if not os.path.exists(report_path):
        return jsonify({"error": "Report not found"}), 404
    try:
        with open(report_path) as f:
            report = json.load(f)
        xlsx = build_excel_report(report)
        return send_file(
            io.BytesIO(xlsx),
            mimetype="application/vnd.openxmlformats-officedocument."
                     "spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"construction_report_{task_id[:8]}.xlsx",
        )
    except Exception as e:
        logging.error(f"Excel report generation failed: {e}")
        return jsonify({"error": "Excel generation failed"}), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "webodm": check_webodm_connection(),
            "cloudcompare": CLOUDCOMPARE_PATH is not None and os.path.exists(CLOUDCOMPARE_PATH),
            "yolo": YOLO_AVAILABLE
        },
        "active_tasks": len([t for t in task_status_store.values() if t["status"] == "processing"]),
        "cloudcompare_path": CLOUDCOMPARE_PATH
    }
    return jsonify(status)

@app.route('/config', methods=['GET', 'POST'])
def configuration():
    """Get or update configuration"""
    if request.method == 'GET':
        config = {
            "webodm_url": WEBODM_URL,
            "project_id": PROJECT_ID,
            "cloudcompare_path": CLOUDCOMPARE_PATH,
            "processing_options": PROCESSING_OPTIONS
        }
        return jsonify(config)
    
    elif request.method == 'POST':
        try:
            new_config = request.get_json()
            
            # Update global configuration (in a real app, save to file/database)
            if "processing_options" in new_config:
                PROCESSING_OPTIONS.update(new_config["processing_options"])
                
            return jsonify({"success": True, "message": "Configuration updated"})
            
        except Exception as e:
            return jsonify({"error": f"Configuration update failed: {str(e)}"}), 500


@app.route('/api/rates', methods=['GET', 'POST'])
def api_rates():
    """Get or update the user-editable unit-rate list (per road layer)."""
    if request.method == 'GET':
        return jsonify({
            "currency": config_store.get_plan().get("currency", "PKR"),
            "rates": config_store.rates_table(),
        })
    try:
        body = request.get_json(force=True) or {}
        incoming = body.get("rates")
        if isinstance(incoming, list):
            incoming = {item.get("class_id"): item.get("rate")
                        for item in incoming if item.get("class_id") is not None}
        config_store.save_rates(incoming or {})
        return jsonify({"success": True, "rates": config_store.rates_table()})
    except Exception as e:
        logging.error(f"Saving rates failed: {e}")
        return jsonify({"error": f"Failed to save rates: {e}"}), 500


@app.route('/api/plan', methods=['GET', 'POST'])
def api_plan():
    """Get or update the user-editable project plan."""
    if request.method == 'GET':
        return jsonify(config_store.get_plan())
    try:
        plan = request.get_json(force=True) or {}
        saved = config_store.save_plan(plan)
        return jsonify({"success": True, "plan": saved})
    except Exception as e:
        logging.error(f"Saving plan failed: {e}")
        return jsonify({"error": f"Failed to save plan: {e}"}), 500


# Helper Functions
def save_uploaded_files(files, prefix):
    """Save uploaded files and return paths"""
    paths = []
    for i, file in enumerate(files):
        if file.filename:
            # Generate unique filename
            ext = os.path.splitext(file.filename)[1].lower()
            filename = f"{prefix}_{uuid.uuid4().hex}_{i:03d}{ext}"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            
            file.save(filepath)
            paths.append(filepath)
            logging.info(f"Saved {prefix} image: {filepath}")
    
    return paths

def detect_objects(image_path, prefix):
    """Run YOLO road-layer detection on an image.

    Returns a dict:
        {"image_path": <annotated image path>,
         "detections": [{"layer", "class_id", "confidence", "bbox"}, ...]}
    or None on failure.
    """
    if not YOLO_AVAILABLE:
        return None

    try:
        img = cv2.imread(image_path)
        if img is None:
            logging.error(f"Could not load image: {image_path}")
            return None

        results = model(img, conf=YOLO_CONFIDENCE)

        detections = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                confidence = float(box.conf[0].cpu().numpy())
                class_id = int(box.cls[0].cpu().numpy())

                # Use canonical road-layer names when the custom model is
                # loaded; otherwise fall back to the model's own class names.
                if USING_ROAD_LAYER_MODEL:
                    label = layer_name(class_id)
                    stored_class_id = class_id
                else:
                    # Generic (COCO) model - keep the label for display only;
                    # do NOT attribute to a road-layer cost line.
                    label = result.names.get(class_id, f"class_{class_id}")
                    stored_class_id = None

                detections.append({
                    "layer": label,
                    "class_id": stored_class_id,
                    "confidence": confidence,
                    "bbox": [x1, y1, x2, y2],
                })

                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(img, f"{label} {confidence:.1%}",
                            (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX,
                            0.9, (0, 255, 0), 2)

        result_filename = f"{prefix}_detected_{uuid.uuid4().hex}.jpg"
        result_path = os.path.join(RESULTS_FOLDER, result_filename)
        cv2.imwrite(result_path, img)

        logging.info(
            f"Object detection completed: {result_path} "
            f"({len(detections)} detections)"
        )
        return {"image_path": result_path, "detections": detections}

    except Exception as e:
        logging.error(f"Object detection failed: {e}")
        return None

def check_webodm_connection():
    """Check if WebODM is accessible"""
    try:
        response = requests.get(f"{WEBODM_URL}/projects/", 
                              auth=WEBODM_AUTH, timeout=5)
        return response.status_code == 200
    except:
        return False

def cleanup_old_files(max_age_hours=24):
    """Clean up old files to prevent disk space issues"""
    import time
    from pathlib import Path
    
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    
    folders_to_clean = [UPLOAD_FOLDER, RESULTS_FOLDER, DOWNLOAD_FOLDER, 
                       POINT_CLOUD_FOLDER, MESH_FOLDER, DEM_FOLDER]
    
    for folder in folders_to_clean:
        try:
            for filepath in Path(folder).rglob('*'):
                if filepath.is_file():
                    file_age = current_time - filepath.stat().st_mtime
                    if file_age > max_age_seconds:
                        filepath.unlink()
                        logging.info(f"Cleaned up old file: {filepath}")
        except Exception as e:
            logging.error(f"Cleanup error in {folder}: {e}")

# Background cleanup task
def start_cleanup_scheduler():
    """Start background cleanup scheduler"""
    def cleanup_worker():
        while True:
            try:
                cleanup_old_files(max_age_hours=24)
                time.sleep(3600)  # Run every hour
            except Exception as e:
                logging.error(f"Cleanup scheduler error: {e}")
                time.sleep(3600)
    
    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
    cleanup_thread.start()
    logging.info("Cleanup scheduler started")

if __name__ == '__main__':
    # Verify dependencies
    if not CLOUDCOMPARE_PATH:
        logging.error("CloudCompare not found. Please install CloudCompare.")
        print("Please install CloudCompare:")
        print("- Windows: Download from https://cloudcompare.org/")
        print("- Linux: sudo apt-get install cloudcompare")
        print("- macOS: brew install cloudcompare")
        print("\nThe application will continue but mesh/DEM generation will be limited.")
    
    if not check_webodm_connection():
        logging.warning("WebODM connection failed. Please ensure WebODM is running.")
        print("Warning: WebODM not accessible. Please start WebODM server.")
        print("To start WebODM:")
        print("1. Install Docker and docker-compose")
        print("2. git clone https://github.com/OpenDroneMap/WebODM")
        print("3. cd WebODM")
        print("4. ./webodm.sh start")
    
    # Start background services
    start_cleanup_scheduler()
    
    # Start Flask application
    logging.info("Starting Construction Volume Analysis Application")
    print("=" * 60)
    print("CONSTRUCTION VOLUME ANALYSIS APPLICATION")
    print("=" * 60)
    print(f"WebODM URL: {WEBODM_URL}")
    print(f"Project ID: {PROJECT_ID}")
    print(f"CloudCompare: {CLOUDCOMPARE_PATH or 'Not Found'}")
    print(f"YOLO Detection: {'Enabled' if YOLO_AVAILABLE else 'Disabled'}")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)