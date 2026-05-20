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

# Valid values
VALID_LIGHT_TYPES  = frozenset({"AREA", "SPOT", "SUN", "POINT"})
VALID_CATEGORIES   = frozenset({"PORTRAIT", "PRODUCT", "ARCHITECTURE", "CREATIVE"})
VALID_AREA_SHAPES  = frozenset({"SQUARE", "RECTANGLE", "DISK", "ELLIPSE"})
VALID_LXC_ENGINES  = frozenset({"PATH", "BIDIR"})
VALID_ENV_TYPES    = frozenset({"sky2", "constant"})

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
