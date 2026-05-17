"""
Road construction layers - canonical reference table.

Single source of truth used by:
  - YOLO road-layer detection (class IDs -> layer names)
  - Cost calculation (unit + rate per layer)

IMPORTANT
---------
1. The custom YOLO model MUST be trained with classes in this exact ID order
   (class 0 = Common Cutting & Filling, class 1 = Sub Base Course, ...).
2. The `rate` values below are PLACEHOLDERS. Replace them with the official
   unit rates from the project Bill of Quantities (BOQ) before final use.
3. `thickness_m` is the typical compacted layer thickness, used to convert a
   measured surface area into a volume when needed. None = not applicable.
"""

CURRENCY = "PKR"

# class_id -> {name, unit, rate, thickness_m}
ROAD_LAYERS = {
    0:  {"name": "Common Cutting & Filling", "unit": "m3",  "rate": 450.0,   "thickness_m": 0.30},
    1:  {"name": "Sub Base Course",          "unit": "m3",  "rate": 1200.0,  "thickness_m": 0.15},
    2:  {"name": "Aggregate Base Course",    "unit": "m3",  "rate": 2500.0,  "thickness_m": 0.20},
    3:  {"name": "Prime Coat",               "unit": "m2",  "rate": 85.0,    "thickness_m": None},
    4:  {"name": "Tack Coat",                "unit": "m2",  "rate": 45.0,    "thickness_m": None},
    5:  {"name": "Asphalt Wearing Course",   "unit": "m3",  "rate": 18500.0, "thickness_m": 0.05},
    6:  {"name": "Asphalt Binder Course",    "unit": "m3",  "rate": 16000.0, "thickness_m": 0.07},
    7:  {"name": "Allied Kerb Stone",        "unit": "Rft", "rate": 950.0,   "thickness_m": None},
    8:  {"name": "Tuff Paver",               "unit": "m2",  "rate": 1800.0,  "thickness_m": 0.06},
    9:  {"name": "RCC Drainage Works",       "unit": "m3",  "rate": 22000.0, "thickness_m": 0.25},
    10: {"name": "Earth Filling",            "unit": "m3",  "rate": 380.0,   "thickness_m": 0.30},
    11: {"name": "Compaction Works",         "unit": "m2",  "rate": 120.0,   "thickness_m": None},
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
