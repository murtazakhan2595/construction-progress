import warnings, glob, os
warnings.filterwarnings("ignore")
from collections import Counter
import cv2
from ultralytics import YOLO

MODEL = "models/best.pt"
SRC = r"d:/temp/zapru/yolo Check"
OUT = r"d:/temp/zapru/detection_results"
IMGSZ = 640
CONF = 0.25

os.makedirs(OUT, exist_ok=True)
m = YOLO(MODEL)

imgs = []
for e in ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"):
    imgs += glob.glob(os.path.join(SRC, e))
imgs = sorted(set(imgs))

summary = []
for p in imgs:
    r = m(p, conf=CONF, imgsz=IMGSZ, verbose=False)[0]
    dets = Counter(m.names[int(b.cls)] for b in (r.boxes or []))
    confs = [round(float(b.conf), 2) for b in (r.boxes or [])]
    name = os.path.splitext(os.path.basename(p))[0]
    annotated = r.plot()
    h, w = annotated.shape[:2]
    annotated = cv2.resize(annotated, (1600, int(h * 1600 / w)))
    cv2.imwrite(os.path.join(OUT, name + "_det.jpg"), annotated)
    summary.append((name, dict(dets), confs))

with open(os.path.join(OUT, "_SUMMARY.txt"), "w") as f:
    f.write(f"Detection check | model={MODEL} | imgsz={IMGSZ} | conf={CONF}\n" + "=" * 70 + "\n")
    for name, dets, confs in summary:
        f.write(f"{name:42} -> {dets}  confs={confs}\n")

print(f"Saved {len(summary)} annotated images + _SUMMARY.txt to {OUT}")
