"""Road-layer YOLO detection on an orthophoto (orthomosaic).

Renders a web-size RGB image of the (possibly huge) orthophoto via a decimated
read — compositing the alpha/nodata band over white so the survey edges are
clean — then runs the trained road-layer model on it. Returns the dominant
layer + detections and writes an annotated JPG for the results page.

This replaces the old sample-frame detection: it runs on the true stitched
output that represents the whole image set, which is what the operator sees.
"""
import logging
from collections import Counter
import numpy as np


def _ortho_rgb(tif_path, max_dim=2048):
    import rasterio
    from rasterio.enums import Resampling
    with rasterio.open(tif_path) as ds:
        scale = max(ds.width, ds.height) / float(max_dim)
        if scale < 1:
            scale = 1.0
        ow, oh = max(1, int(ds.width / scale)), max(1, int(ds.height / scale))
        b = min(ds.count, 4)
        data = ds.read(indexes=list(range(1, b + 1)),
                       out_shape=(b, oh, ow), resampling=Resampling.average)
    if data.dtype != np.uint8:
        a = data.astype("float32")
        mn, mx = float(np.nanmin(a)), float(np.nanmax(a))
        if mx > mn:
            a = (a - mn) / (mx - mn) * 255
        data = np.nan_to_num(a).astype("uint8")
    rgb = np.transpose(data[:3], (1, 2, 0))
    if data.shape[0] >= 4:
        al = data[3].astype("float32")[:, :, None] / 255.0
        rgb = (rgb.astype("float32") * al + 255 * (1 - al)).astype("uint8")
    return np.ascontiguousarray(rgb)


def detect_orthophoto(tif_path, model, out_jpg_path, conf=0.25, imgsz=1536, max_dim=2048):
    """Run the model on an orthophoto GeoTIFF.

    Returns {"dominant": <layer|None>, "detections": [{layer, class_id,
    confidence}], "scores": {layer: conf_sum}} and writes an annotated JPG to
    out_jpg_path. Returns None on failure (callers treat detection as optional).
    """
    try:
        from PIL import Image
        rgb = _ortho_rgb(tif_path, max_dim)
        # model expects BGR (cv2 convention); pass a contiguous reversed copy.
        r = model(np.ascontiguousarray(rgb[:, :, ::-1]),
                  conf=conf, imgsz=imgsz, verbose=False)[0]

        dets, score = [], Counter()
        for box in (r.boxes or []):
            cid = int(box.cls)
            name = model.names[cid] if cid in model.names else str(cid)
            cf = float(box.conf)
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
            dets.append({"layer": name, "class_id": cid,
                         "confidence": round(cf, 3), "bbox": [x1, y1, x2, y2]})
            score[name] += cf

        ann = r.plot(line_width=3, font_size=20)  # BGR
        Image.fromarray(ann[:, :, ::-1]).save(out_jpg_path, "JPEG", quality=88)

        dominant = score.most_common(1)[0][0] if score else None
        logging.info(f"Ortho detection {tif_path}: dominant={dominant} "
                     f"({len(dets)} boxes)")
        return {"dominant": dominant, "detections": dets, "scores": dict(score)}
    except Exception as e:
        logging.error(f"Orthophoto detection failed for {tif_path}: {e}")
        return None
