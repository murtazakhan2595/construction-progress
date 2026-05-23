"""
Cost calculation - converts a measured volume plus YOLO road-layer detections
into a Bill of Quantities (BOQ).

Volume attribution
------------------
CloudCompare returns a single net volume for the whole site. When YOLO detects
one or more road layers, that volume is split across them in proportion to the
detection bounding-box areas. With no detections, the volume is reported as a
single "unclassified earthwork" line.

Quantity per billing unit
-------------------------
  m3  -> quantity = volume attributed to the layer
  m2  -> quantity = attributed volume / layer thickness   (surface area)
  Rft -> quantity = attributed volume                     (refine when length
                                                            data is available)
"""

from road_layers import ROAD_LAYERS, layer_name, layer_unit
from config_store import get_rates

DEFAULT_CLASS_ID = 0  # Common Cutting & Filling - used for unclassified earthwork


def _quantity_for_layer(class_id, volume_m3):
    """Convert an attributed volume into the layer's billing quantity."""
    item = ROAD_LAYERS.get(class_id, {})
    unit = item.get("unit", "m3")
    if unit == "m2":
        thickness = item.get("thickness_m")
        return volume_m3 / thickness if thickness else volume_m3
    return volume_m3


def build_boq(volume_m3, detected_layers=None, currency="PKR", rates=None):
    """Build a Bill of Quantities.

    volume_m3       - net volume in cubic metres (sign ignored; magnitude used)
    detected_layers - list of YOLO detection dicts ({class_id, bbox, ...});
                      detections whose class_id is not a known road layer
                      (e.g. from the generic COCO model) are ignored
    currency        - currency label for the BOQ (from project plan)
    rates           - {class_id: rate} override; defaults to the user-saved
                      rates from config_store

    Returns:
        {"items": [{layer, unit, quantity, rate, amount}, ...],
         "total_cost": float, "currency": str}
    """
    volume_m3 = abs(float(volume_m3 or 0.0))
    if rates is None:
        rates = get_rates()
    items = []

    # Sum detection bbox area per known road-layer class
    area_by_class = {}
    for det in (detected_layers or []):
        class_id = det.get("class_id")
        if class_id not in ROAD_LAYERS:
            continue
        bbox = det.get("bbox") or [0, 0, 0, 0]
        x1, y1, x2, y2 = bbox
        area = max(0, x2 - x1) * max(0, y2 - y1)
        area_by_class[class_id] = area_by_class.get(class_id, 0) + area

    if not area_by_class or sum(area_by_class.values()) == 0:
        # No road layer identified - report as unclassified earthwork
        rate = rates.get(DEFAULT_CLASS_ID, 0)
        items.append({
            "layer": "Earthwork (unclassified)",
            "unit": "m3",
            "quantity": round(volume_m3, 2),
            "rate": rate,
            "amount": round(volume_m3 * rate, 2),
        })
    else:
        total_area = sum(area_by_class.values())
        for class_id, area in sorted(area_by_class.items()):
            share = volume_m3 * (area / total_area)
            quantity = _quantity_for_layer(class_id, share)
            rate = rates.get(class_id, 0)
            items.append({
                "layer": layer_name(class_id),
                "unit": layer_unit(class_id),
                "quantity": round(quantity, 2),
                "rate": rate,
                "amount": round(quantity * rate, 2),
            })

    total_cost = round(sum(item["amount"] for item in items), 2)
    return {"items": items, "total_cost": total_cost, "currency": currency}
