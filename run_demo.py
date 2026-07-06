"""Demo driver: for each layer, run YOLO detection on representative images +
compute volume from the before/after DSM pair, producing a full analysis report
(volume + BOQ-by-layer + S-curve) that shows up in the app's /runs page."""
import warnings, glob, os, uuid
warnings.filterwarnings("ignore")
from finalV2 import ConstructionVolumeAnalyzer, detect_objects

DSM = r"d:/temp/zapru/dsm_outputs"
IMGS = r"d:/temp/zapru/demo_images"

LAYERS = [
    ("SubBase",   f"{DSM}/SubBase_Before_gpu_dsm.tif", f"{DSM}/SubBase_After_dsm.tif"),
    ("ABC",       f"{DSM}/ABC_Before_dsm.tif",         f"{DSM}/ABC_After_dsm.tif"),
    ("PrimeCoat", f"{DSM}/PrimeCoat_Before_dsm.tif",   f"{DSM}/PrimeCoat_After_dsm.tif"),
]

for name, before, after in LAYERS:
    analyzer = ConstructionVolumeAnalyzer(str(uuid.uuid4()))
    folder = os.path.join(IMGS, name)
    dets = []
    imgs = []
    for e in ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"):
        imgs += glob.glob(os.path.join(folder, e))
    for img in sorted(set(imgs))[:5]:
        res = detect_objects(img, "after")
        if res:
            dets += res["detections"]
    analyzer.detected_layers = dets
    ok = analyzer.process_existing_data(before, after)
    labels = sorted({d["layer"] for d in dets})
    print(f"{name:10} ok={ok}  detected={labels}  task={analyzer.task_id}")

print("\nDone. Start the app and open http://localhost:5000/runs to view all 3 analyses.")
