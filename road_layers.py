"""
Road construction layers - canonical reference table.

Single source of truth used by:
  - YOLO road-layer detection (class IDs -> layer names)
  - Cost calculation (unit + rate per layer)

IMPORTANT
---------
1. These class IDs MUST match the trained YOLO model's class order exactly
   (from the Roboflow dataset data.yaml):
       class 0 = Aggregate Base Course
       class 1 = Asphalt
       class 2 = Sub Base
   If the model is ever retrained with a different class order, update this
   table to match or labels and costs will be attributed to the wrong layer.
2. The `rate` values below are PLACEHOLDERS. Replace them with the official
   unit rates from the project Bill of Quantities (BOQ) before final use.
3. `thickness_m` is the typical compacted layer thickness, used to convert a
   measured surface area into a volume when needed. None = not applicable.
"""

CURRENCY = "PKR"

# class_id -> {name, unit, rate, thickness_m}
ROAD_LAYERS = {
    0:  {"name": "Aggregate Base Course",    "unit": "m3",  "rate": 2500.0,  "thickness_m": 0.20},
    1:  {"name": "Asphalt",                  "unit": "m3",  "rate": 18500.0, "thickness_m": 0.05},
    2:  {"name": "Sub Base",                 "unit": "m3",  "rate": 1200.0,  "thickness_m": 0.15},
}

NUM_CLASSES = len(ROAD_LAYERS)


def layer_name(class_id):
    """Human-readable name for a class ID."""
    item = ROAD_LAYERS.get(class_id)
    return item["name"] if item else f"class_{class_id}"


def layer_unit(class_id):
    """Billing unit (m3, m2, Rft) for a class ID."""
    item = ROAD_LAYERS.get(class_id)
    return item["unit"] if item else ""


def layer_rate(class_id):
    """Unit rate for a class ID, in CURRENCY."""
    item = ROAD_LAYERS.get(class_id)
    return item["rate"] if item else 0.0


def layer_by_name(name):
    """Look up a layer definition by (case-insensitive) name; returns
    (class_id, definition) or (None, None)."""
    for cid, item in ROAD_LAYERS.items():
        if item["name"].lower() == str(name).lower():
            return cid, item
    return None, None
