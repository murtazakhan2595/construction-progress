# import subprocess
# import os
# import glob
# import shutil
# import time

# def create_dem_from_mesh():
#     # Configuration
#     cloudcompare_path = r"C:\Program Files\CloudCompare\CloudCompare.exe"
#     mesh_file = r"C:\Users\RK\Desktop\My Data\construction_progress\downloaded_assets\d30a7f92-6c6b-43df-b388-6f877a75a6f9_georeferenced_model_2025-08-20_13h26_37_335.bin"
#     output_dem = r"C:\Users\RK\Desktop\My Data\construction_progress\downloaded_assets\output_dem.asc"
    
#     # Validate inputs
#     if not os.path.exists(cloudcompare_path):
#         print(f"❌ CloudCompare not found at: {cloudcompare_path}")
#         return False
        
#     if not os.path.exists(mesh_file):
#         print(f"❌ Mesh file not found at: {mesh_file}")
#         return False
    
#     # Get the directory for output files
#     mesh_dir = os.path.dirname(mesh_file)
    
#     # Count existing .asc files before processing
#     existing_asc_files = glob.glob(os.path.join(mesh_dir, "*.asc"))
#     existing_count = len(existing_asc_files)
    
#     try:
#         print("🔄 Starting DEM generation...")
        
#         # Try multiple approaches with different parameters
#         approaches = [
#             # Approach 1: Basic rasterization with larger grid step
#             [
#                 cloudcompare_path,
#                 "-SILENT",
#                 "-AUTO_SAVE", "OFF", 
#                 "-O", mesh_file,
#                 "-RASTERIZE",
#                 "-GRID_STEP", "1.0",    # Larger grid step
#                 "-VERT_DIR", "2",       # Z direction
#                 "-PROJ", "AVG",
#                 "-OUTPUT_RASTER_Z",
#                 "-C_EXPORT_FMT", "ASC", # Force ASCII format
#                 "-SAVE_MESHES", "FILE", os.path.join(mesh_dir, "temp_raster")
#             ],
#             # Approach 2: Convert mesh to point cloud first, then rasterize
#             [
#                 cloudcompare_path,
#                 "-SILENT",
#                 "-AUTO_SAVE", "OFF",
#                 "-O", mesh_file,
#                 "-SAMPLE_MESH", "DENSITY", "100000",  # Sample 100k points from mesh
#                 "-RASTERIZE", 
#                 "-GRID_STEP", "0.5",
#                 "-VERT_DIR", "2",
#                 "-PROJ", "AVG",
#                 "-OUTPUT_RASTER_Z"
#             ],
#             # Approach 3: Simple rasterization without extra parameters
#             [
#                 cloudcompare_path,
#                 "-SILENT",
#                 "-AUTO_SAVE", "OFF",
#                 "-O", mesh_file,
#                 "-RASTERIZE",
#                 "-GRID_STEP", "0.5",
#                 "-OUTPUT_RASTER_Z"
#             ]
#         ]
        
#         success = False
#         for i, cmd in enumerate(approaches, 1):
#             print(f"🔄 Trying approach {i}...")
#             try:
        
#                 result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=300)
                
#                 print(f"✅ Approach {i} - CloudCompare execution completed")
#                 if result.stdout:
#                     # Only print last few lines to avoid clutter
#                     stdout_lines = result.stdout.strip().split('\n')
#                     relevant_lines = [line for line in stdout_lines if 
#                                     any(keyword in line.lower() for keyword in 
#                                         ['rasterize', 'error', 'warning', 'mesh', 'vertices', 'faces'])]
#                     if relevant_lines:
#                         print("📋 Relevant output:")
#                         for line in relevant_lines[-5:]:  # Last 5 relevant lines
#                             print(f"  {line}")
                
#                 # Wait for file system to update
#                 time.sleep(3)
                
#                 # Check for various output file types
#                 possible_outputs = []
#                 for ext in ['*.asc', '*.tif', '*.tiff', '*.txt']:
#                     files = glob.glob(os.path.join(mesh_dir, ext))
#                     new_files = [f for f in files if f not in existing_asc_files and 
#                                os.path.getctime(f) > time.time() - 60]  # Created in last minute
#                     possible_outputs.extend(new_files)
                
#                 # Also check for files with mesh name prefix
#                 mesh_basename = os.path.splitext(os.path.basename(mesh_file))[0]
#                 pattern_files = glob.glob(os.path.join(mesh_dir, f"{mesh_basename}*"))
#                 new_pattern_files = [f for f in pattern_files if f != mesh_file and 
#                                    os.path.getctime(f) > time.time() - 60]
#                 possible_outputs.extend(new_pattern_files)
                
#                 if possible_outputs:
#                     # Get the most recent file
#                     latest_output = max(possible_outputs, key=os.path.getctime)
#                     print(f"📁 Found output file: {os.path.basename(latest_output)}")
                    
#                     # Handle different file types
#                     if latest_output.lower().endswith('.asc'):
#                         # Direct ASC file
#                         if os.path.exists(output_dem):
#                             os.remove(output_dem)
#                         shutil.move(latest_output, output_dem)
#                         success = True
#                     else:
#                         # Try to convert or rename
#                         target_path = output_dem
#                         if latest_output.lower().endswith(('.tif', '.tiff')):
#                             target_path = output_dem.replace('.asc', '.tif')
                        
#                         if os.path.exists(target_path):
#                             os.remove(target_path)
#                         shutil.move(latest_output, target_path)
#                         print(f"✅ Output file moved to: {target_path}")
#                         success = True
#                     break
                    
#             except subprocess.CalledProcessError as e:
#                 print(f"❌ Approach {i} failed with error code: {e.returncode}")
#                 if i == len(approaches):  # Last approach failed
#                     print("STDOUT:", e.stdout if e.stdout else "None")
#                     print("STDERR:", e.stderr if e.stderr else "None")
#                 continue
#             except Exception as e:
#                 print(f"❌ Approach {i} failed: {str(e)}")
#                 continue
        
#         if success:
#             final_output = output_dem if os.path.exists(output_dem) else output_dem.replace('.asc', '.tif')
#             if os.path.exists(final_output):
#                 file_size = os.path.getsize(final_output) / 1024 / 1024  # MB
#                 print(f"📊 DEM file size: {file_size:.2f} MB")
#                 return True
        
#         # If we get here, no approach worked
#         print("⚠️ All approaches failed to generate DEM file.")
        
#         # Enhanced debugging
#         print("\n🔍 Enhanced Debugging:")
#         print(f"Mesh info: 296,092 faces, 251,486 vertices")
        
#         # Check all files in directory
#         print("\n📂 All files in mesh directory (with timestamps):")
#         for file in os.listdir(mesh_dir):
#             filepath = os.path.join(mesh_dir, file)
#             if os.path.isfile(filepath):
#                 mtime = os.path.getmtime(filepath)
#                 size_mb = os.path.getsize(filepath) / 1024 / 1024
#                 print(f"  - {file} ({size_mb:.2f} MB, {time.ctime(mtime)})")
        
#         return False
            
#     except subprocess.TimeoutExpired:
#         print("❌ CloudCompare timed out (process took too long)")
#         return False
        
#     except subprocess.CalledProcessError as e:
#         print("❌ CloudCompare failed with error code:", e.returncode)
#         print("STDOUT:", e.stdout if e.stdout else "None")
#         print("STDERR:", e.stderr if e.stderr else "None")
#         return False
        
#     except Exception as e:
#         print(f"❌ Unexpected error: {str(e)}")
#         return False

# def validate_dem_file(dem_path):
#     """Validate the generated DEM file"""
#     if not os.path.exists(dem_path):
#         return False
        
#     try:
#         with open(dem_path, 'r') as f:
#             header = f.readline().strip()
#             if header.startswith('ncols') or header.startswith('NCOLS'):
#                 print("✅ DEM file appears to be valid ESRI ASCII Grid format")
#                 return True
#             else:
#                 print("⚠️ DEM file may not be in correct ASCII Grid format")
#                 return False
#     except Exception as e:
#         print(f"⚠️ Could not validate DEM file: {e}")
#         return False

# if __name__ == "__main__":
#     print("🚀 DEM Generation Tool")
#     print("=" * 50)
    
#     success = create_dem_from_mesh()
    
#     if success:
#         output_dem = r"C:\Users\RK\Desktop\My Data\construction_progress\downloaded_assets\output_dem.asc"
#         validate_dem_file(output_dem)
#         print("\n🎉 Process completed successfully!")
#     else:
#         print("\n💡 Troubleshooting tips:")
#         print("1. Ensure your mesh file is valid and contains 3D geometry")
#         print("2. Try increasing the GRID_STEP value (e.g., 0.5 or 1.0)")
#         print("3. Check if the mesh has proper Z-coordinates")
#         print("4. Verify CloudCompare installation and version compatibility")
import subprocess
import os
import glob
import shutil
import time

def create_dem_from_mesh(mesh_file_path, output_dem_path, cloudcompare_path=None, grid_step=0.5, sample_points=100000):
    """
    Generate Digital Elevation Model (DEM) from mesh file using CloudCompare
    
    Args:
        mesh_file_path (str): Path to input mesh file (.bin, .ply, .obj, etc.)
        output_dem_path (str): Path for output DEM file (.tif or .asc)
        cloudcompare_path (str): Path to CloudCompare executable (optional)
        grid_step (float): Raster grid resolution in meters (default: 0.5)
        sample_points (int): Number of points to sample from mesh (default: 100000)
    
    Returns:
        tuple: (success: bool, output_file: str or None, error_message: str or None)
    """
    
    # Default CloudCompare path
    if cloudcompare_path is None:
        cloudcompare_path = r"C:\Program Files\CloudCompare\CloudCompare.exe"
    
    # Validate inputs
    if not os.path.exists(cloudcompare_path):
        return False, None, f"CloudCompare not found at: {cloudcompare_path}"
        
    if not os.path.exists(mesh_file_path):
        return False, None, f"Mesh file not found at: {mesh_file_path}"
    
    mesh_dir = os.path.dirname(mesh_file_path)
    
    # Get existing files to detect new outputs
    existing_files = set(os.listdir(mesh_dir))
    
    try:
        # CloudCompare command: Sample mesh to points, then rasterize
        cmd = [
            cloudcompare_path,
            "-SILENT",
            "-AUTO_SAVE", "OFF",
            "-O", mesh_file_path,
            "-SAMPLE_MESH", "DENSITY", str(sample_points),
            "-RASTERIZE", 
            "-GRID_STEP", str(grid_step),
            "-VERT_DIR", "2",  # Z direction
            "-PROJ", "AVG",
            "-OUTPUT_RASTER_Z"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=300)
        
        # Wait for file system to update
        time.sleep(2)
        
        # Find newly created files
        current_files = set(os.listdir(mesh_dir))
        new_files = current_files - existing_files
        
        # Look for raster files
        raster_files = [f for f in new_files if f.lower().endswith(('.tif', '.tiff', '.asc'))]
        
        if raster_files:
            # Get the raster file (should be only one)
            source_file = os.path.join(mesh_dir, raster_files[0])
            
            # Move to desired output location
            if os.path.exists(output_dem_path):
                os.remove(output_dem_path)
            
            shutil.move(source_file, output_dem_path)
            
            return True, output_dem_path, None
        else:
            return False, None, "No raster file was generated by CloudCompare"
            
    except subprocess.TimeoutExpired:
        return False, None, "CloudCompare process timed out"
        
    except subprocess.CalledProcessError as e:
        error_msg = f"CloudCompare failed with error code {e.returncode}"
        if e.stderr:
            error_msg += f": {e.stderr}"
        return False, None, error_msg
        
    except Exception as e:
        return False, None, f"Unexpected error: {str(e)}"

# Example usage function (can be removed if not needed)
def example_usage():
    """Example of how to use the create_dem_from_mesh function"""
    
    mesh_file = r"C:\Users\RK\Desktop\My Data\construction_progress\downloaded_assets\d30a7f92-6c6b-43df-b388-6f877a75a6f9_georeferenced_model_2025-08-20_13h26_37_335.bin"
    output_dem = r"C:\Users\RK\Desktop\My Data\construction_progress\downloaded_assets\output_dem..tif"
    
    success, output_file, error = create_dem_from_mesh(
        mesh_file_path=mesh_file,
        output_dem_path=output_dem,
        grid_step=0.5,
        sample_points=100000
    )
    
    if success:
        print(f"✅ DEM created successfully: {output_file}")
        file_size_mb = os.path.getsize(output_file) / 1024 / 1024
        print(f"File size: {file_size_mb:.2f} MB")
    else:
        print(f"❌ DEM generation failed: {error}")

if __name__ == "__main__":
    example_usage()