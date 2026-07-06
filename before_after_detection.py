"""Before/After YOLO detection demo (Methodology: AI Detection stage).
Shows that YOLO detects the earthwork stage in each survey, and a change in the
detected class between BEFORE and AFTER = construction progress."""
import warnings, glob, os
warnings.filterwarnings("ignore")
import cv2
from collections import Counter
from ultralytics import YOLO

m = YOLO("models/best.pt")
IMGS = r"d:/temp/zapru/demo_images"
OUT = r"d:/temp/zapru/detection_results"
os.makedirs(OUT, exist_ok=True)


def first_img(layer):
    for e in ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"):
        g = sorted(glob.glob(os.path.join(IMGS, layer, e)))
        if g:
            return g[0]
    return None


def annotate(path):
    r = m(path, conf=0.25, imgsz=640, verbose=False)[0]
    dets = Counter(m.names[int(b.cls)] for b in (r.boxes or []))
    label = dets.most_common(1)[0][0] if dets else "None"
    img = r.plot()
    h, w = img.shape[:2]
    img = cv2.resize(img, (720, int(h * 720 / w)))
    return img, label


# Each cycle: (before layer-folder, after layer-folder)
CYCLES = [("SubBase", "ABC"), ("ABC", "PrimeCoat")]

for i, (b_layer, a_layer) in enumerate(CYCLES, 1):
    bimg, blabel = annotate(first_img(b_layer))
    aimg, alabel = annotate(first_img(a_layer))
    h = min(bimg.shape[0], aimg.shape[0])
    bimg, aimg = cv2.resize(bimg, (720, h)), cv2.resize(aimg, (720, h))
    bar = 70
    canvas = cv2.copyMakeBorder(cv2.hconcat([bimg, aimg]), bar, 40, 0, 0,
                                cv2.BORDER_CONSTANT, value=(30, 30, 30))
    cv2.putText(canvas, f"BEFORE: {blabel}", (20, 45),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
    cv2.putText(canvas, f"AFTER: {alabel}", (740, 45),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
    verdict = f"CHANGE: {blabel} -> {alabel}  ==> PROGRESS" if blabel != alabel else "NO CHANGE"
    cv2.putText(canvas, verdict, (20, canvas.shape[0] - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    out = os.path.join(OUT, f"before_after_cycle{i}.jpg")
    cv2.imwrite(out, canvas)
    print(f"Cycle {i}: {blabel} -> {alabel}  saved {out}")
