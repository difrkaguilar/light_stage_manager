# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  difrkaguilar + Claude (Anthropic)
# LuxCore Stage Manager -- Shared constants

# Naming
LSM_PREFIX            = "LSM_"
LSM_COLLECTION_PREFIX = "LSM -- "

# Versioning
PRESET_SCHEMA_VERSION = 1
ADDON_DATA_VERSION    = 1
ADDON_ID              = "luxcore_stage_manager"

# Supported render engines
LUXCORE_ENGINE_ID = "LUXCORE"
CYCLES_ENGINE_ID  = "CYCLES"
EEVEE_ENGINE_ID   = "BLENDER_EEVEE_NEXT"   # Blender 4.2+
EEVEE_LEGACY_ID   = "BLENDER_EEVEE"        # Blender < 4.2

CYCLES_LIKE_ENGINES = frozenset({
    CYCLES_ENGINE_ID,
    EEVEE_ENGINE_ID,
    EEVEE_LEGACY_ID,
})

# ---------------------------------------------------------------------------
# Category definitions — single source of truth for the entire addon.
#
# Tuple layout: (id, display_name, description, blender_icon, enum_int)
#
# Rules:
#   - "ALL" must be first and have enum_int 0.
#   - enum_int values must be unique and stable (they are stored in .blend files).
#   - Adding a new category: append a new tuple and bump the enum_int.
#   - Never reuse an enum_int that was previously assigned.
#   - VALID_CATEGORIES and CATEGORY_ICONS are derived automatically;
#     do NOT define them manually anywhere else in the addon.
# ---------------------------------------------------------------------------

CATEGORY_DEFS: list = [
    ("ALL",          "All",           "Show all presets",                                  "LIGHTPROBE_VOLUME", 0),
    ("PORTRAIT",     "Portrait",      "Portrait lighting setups",                          "OUTLINER_OB_LIGHT", 1),
    ("PRODUCT",      "Product",       "Product photography setups",                        "CUBE",              2),
    ("ARCHITECTURE", "Architecture",  "Architectural visualization setups",                "HOME",              3),
    ("CREATIVE",     "Creative",      "Creative and artistic setups",                      "SHADERFX",          4),
    ("CINEMATIC",    "Cinematic",     "Film-inspired setups referencing real productions", "SEQUENCE",          5),
]

# Derived — do not edit manually
VALID_CATEGORIES: frozenset = frozenset(c[0] for c in CATEGORY_DEFS if c[0] != "ALL")
CATEGORY_ICONS:   dict      = {c[0]: c[3] for c in CATEGORY_DEFS}

VALID_LIGHT_TYPES  = frozenset({"AREA", "SPOT", "SUN", "POINT"})
VALID_AREA_SHAPES  = frozenset({"SQUARE", "RECTANGLE", "DISK", "ELLIPSE"})
VALID_LXC_ENGINES  = frozenset({"PATH", "BIDIR"})
VALID_ENV_TYPES    = frozenset({"sky2", "constant", "hdri"})

# Kelvin
KELVIN_MIN     = 1000.0
KELVIN_MAX     = 40000.0    # for Blender native color conversion
KELVIN_LXC_MAX = 12000.0    # BlendLuxCore hard property limit

# ---------------------------------------------------------------------------
# LuxCore gain normalisation
# ---------------------------------------------------------------------------
# Preset energies are in "photographic Watts" (design convention):
#   100 W  -> moderate fill   -> gain ~1.0  (AREA/SPOT)
#   500 W  -> bright key      -> gain ~5.0  (AREA/SPOT)
#    20 W  -> candle           -> gain ~2.0  (POINT, higher scale)
#     4 W  -> sun (BLC)        -> gain ~4.0  (SUN, 1:1 mapping)
LXC_AREA_GAIN_SCALE  = 0.01
LXC_SPOT_GAIN_SCALE  = 0.01
LXC_POINT_GAIN_SCALE = 0.10
LXC_SUN_GAIN_SCALE   = 1.00

# ---------------------------------------------------------------------------
# Cycles energy reference values (for UI display only)
# ---------------------------------------------------------------------------
# Blender 4.x AREA default spread angle (radians): math.pi = 180 degrees
# A tighter spread makes the light behave more like a focused softbox.
# We use 180 degrees (pi) = fully diffuse, matching LuxCore default behaviour.
import math
CYCLES_AREA_SPREAD_DEFAULT = math.pi   # 180 degrees, fully diffuse
