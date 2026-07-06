"""Orthomosaic preview generation.

Downscales a (possibly multi-hundred-MB) orthophoto GeoTIFF to a
web-friendly JPG using a *decimated* read. Passing ``out_shape`` to
rasterio makes it read from the raster's internal overviews instead of the
full-resolution grid, so we never load the entire orthomosaic into memory.

Used by the volume pipeline to attach before/after orthomosaic previews to
the analysis report (served like the S-curve PNG via /result-file/<name>).
"""
import logging
import numpy as np


def generate_orthophoto_preview(tif_path, out_jpg_path, max_dim=2000, quality=85):
    """Write a downscaled RGB JPG preview of an orthophoto GeoTIFF.

    Returns True on success, False if deps are missing or conversion fails
    (callers treat the preview as optional and continue on False).
    """
    try:
        import rasterio
        from rasterio.enums import Resampling
        from PIL import Image
    except Exception as e:
        logging.warning(f"Orthophoto preview skipped (missing deps): {e}")
        return False

    try:
        with rasterio.open(tif_path) as ds:
            scale = max(ds.width, ds.height) / float(max_dim)
            if scale < 1:
                scale = 1.0
            out_w = max(1, int(round(ds.width / scale)))
            out_h = max(1, int(round(ds.height / scale)))
            bands = min(ds.count, 4)

            data = ds.read(
                indexes=list(range(1, bands + 1)),
                out_shape=(bands, out_h, out_w),
                resampling=Resampling.average,
            )  # shape: (bands, h, w)

            # Normalize non-8-bit rasters (e.g. float/uint16) to 0-255.
            if data.dtype != np.uint8:
                arr = data.astype("float32")
                mn, mx = float(np.nanmin(arr)), float(np.nanmax(arr))
                if mx > mn:
                    arr = (arr - mn) / (mx - mn) * 255.0
                data = np.nan_to_num(arr).astype("uint8")

            if bands >= 3:
                rgb = np.transpose(data[:3], (1, 2, 0))  # h, w, 3
                if bands >= 4:
                    # Composite over white using the alpha/mask band so
                    # nodata edges render clean instead of black.
                    alpha = data[3].astype("float32")[:, :, None] / 255.0
                    white = np.full_like(rgb, 255, dtype="float32")
                    rgb = (rgb.astype("float32") * alpha + white * (1 - alpha)).astype("uint8")
                img = Image.fromarray(rgb, "RGB")
            else:
                img = Image.fromarray(data[0], "L").convert("RGB")

            img.save(out_jpg_path, "JPEG", quality=quality, optimize=True)

        logging.info(f"Orthophoto preview written: {out_jpg_path} ({out_w}x{out_h})")
        return True
    except Exception as e:
        logging.error(f"Orthophoto preview failed for {tif_path}: {e}")
        return False
