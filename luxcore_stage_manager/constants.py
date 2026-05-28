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

# ---------------------------------------------------------------------------
# Gel presets — named colour vocabulary for cinematographic lighting.
#
# Each entry: (id, display_name, description, (R, G, B) linear)
#
# Rules:
#   - Colors are in linear (scene-linear) space, not sRGB.
#   - "None" id is the neutral entry (no gel applied).
#   - Adding a new gel: append a tuple, nothing else needs editing.
#   - IDs are stable — used in user presets serialisation.
# ---------------------------------------------------------------------------

GEL_PRESETS: list = [
    # id                  display name              description                          R      G      B
    ("none",              "No Gel",                 "No colour correction",              1.000, 1.000, 1.000),
    # ---- Tungsten / warm ----
    ("tungsten_warm",     "Tungsten Warm",          "Classic incandescent lamp orange",  1.000, 0.420, 0.080),
    ("amber_deep",        "Amber Deep",             "Deep amber — campfire, sunset",     1.000, 0.280, 0.030),
    ("straw",             "Straw",                  "Pale straw — practicals, oldfilm",  1.000, 0.780, 0.320),
    # ---- Daylight / cool ----
    ("ctb_full",          "CTB Full",               "Full colour temp blue — 3200→5600K",0.380, 0.580, 1.000),
    ("ctb_half",          "CTB Half",               "½ CTB — subtle cool correction",   0.620, 0.780, 1.000),
    ("sky_blue",          "Sky Blue",               "Open sky fill, exterior shadows",   0.300, 0.500, 1.000),
    ("ice_blue",          "Ice Blue",               "Cold winter, clinical, sci-fi",     0.200, 0.380, 1.000),
    # ---- Cinematic palettes ----
    ("fincher_green",     "Fincher Green",          "Desaturated sickly green — Seven, Zodiac",
                                                                                         0.340, 0.720, 0.340),
    ("kubrick_cold",      "Kubrick Cold",           "Institutional cold-white overhead", 0.700, 0.800, 1.000),
    ("lubezki_warm",      "Lubezki Warm",           "Diffuse window gold — The Revenant",0.980, 0.860, 0.680),
    ("wkw_amber",         "WKW Amber",              "Wong Kar-wai deep amber practical", 1.000, 0.380, 0.080),
    ("wkw_neon_green",    "WKW Neon Green",         "Wong Kar-wai cyan-green neon",      0.100, 0.800, 0.550),
    ("br2049_orange",     "BR2049 Orange",          "Blade Runner 2049 neon accent",     1.000, 0.300, 0.040),
    ("br2049_blue",       "BR2049 Blue",            "Blade Runner 2049 cold ambient",    0.080, 0.180, 0.550),
    # ---- Special effects ----
    ("lavender",          "Lavender",               "Soft purple fill — fantasy, beauty",0.680, 0.480, 1.000),
    ("rose",              "Rose",                   "Warm-pink beauty fill",             1.000, 0.480, 0.580),
    ("plus_green",        "Plus Green",             "Fluorescent correction / horror",   0.300, 1.000, 0.300),
    ("minus_green",       "Minus Green",            "Minus green / magenta correction",  1.000, 0.200, 0.600),
    ("fire_orange",       "Fire / Explosion",       "Practical fire, explosion effect",  1.000, 0.200, 0.020),
]

# Fast lookup: id → (R, G, B)   — tuple layout: (id, name, desc, R, G, B)
GEL_COLORS: dict = {g[0]: (g[3], g[4], g[5]) for g in GEL_PRESETS}

# EnumProperty items format: (id, display_name, description)
GEL_ENUM_ITEMS: list = [(g[0], g[1], g[2]) for g in GEL_PRESETS]

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
