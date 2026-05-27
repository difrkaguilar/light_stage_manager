# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  difrkaguilar + Claude (Anthropic)
# LuxCore Stage Manager -- Preset Definitions v2
#
# FIX: SCHEMA-01, SCHEMA-02, SCHEMA-03
#
# SCHEMA_VERSION must be incremented when the preset dict layout changes.
# validate_preset() enforces the contract at load time for any external JSON.

from __future__ import annotations
import math
from .constants import (
    PRESET_SCHEMA_VERSION,
    VALID_LIGHT_TYPES, VALID_CATEGORIES, VALID_AREA_SHAPES,
    VALID_LXC_ENGINES, VALID_ENV_TYPES, KELVIN_MIN, KELVIN_MAX,
    CATEGORY_DEFS, CATEGORY_ICONS,
)

# ---------------------------------------------------------------------------
# Schema definition
# ---------------------------------------------------------------------------

REQUIRED_PRESET_KEYS  = frozenset({"id", "name", "category", "description", "lights"})
REQUIRED_LIGHT_KEYS   = frozenset({"name", "type", "location", "energy"})

def validate_preset(data: dict) -> list[str]:
    """Validate a preset dict against the current schema.

    Returns a list of error strings.  An empty list means the preset is valid.
    Designed to be called on user-imported JSON presets; built-in presets are
    considered pre-validated by the test suite.

    Args:
        data: Preset dictionary to validate.

    Returns:
        List of human-readable error strings (empty = valid).
    """
    errs: list[str] = []
    pid = data.get("id", "<unknown>")

    # Required top-level keys
    missing = REQUIRED_PRESET_KEYS - set(data.keys())
    if missing:
        errs.append("[%s] Missing required keys: %s" % (pid, sorted(missing)))

    # Category
    cat = data.get("category")
    if cat and cat not in VALID_CATEGORIES:
        errs.append("[%s] Invalid category %r. Valid: %s" % (pid, cat, sorted(VALID_CATEGORIES)))

    # Lights list
    lights = data.get("lights")
    if not isinstance(lights, list) or len(lights) == 0:
        errs.append("[%s] 'lights' must be a non-empty list" % pid)
    else:
        for i, light in enumerate(lights):
            lname = light.get("name", "#%d" % i)
            lmissing = REQUIRED_LIGHT_KEYS - set(light.keys())
            if lmissing:
                errs.append("[%s] Light %r missing keys: %s" % (pid, lname, sorted(lmissing)))
            ltype = light.get("type")
            if ltype and ltype not in VALID_LIGHT_TYPES:
                errs.append("[%s] Light %r invalid type %r" % (pid, lname, ltype))
            shape = light.get("shape")
            if shape and shape not in VALID_AREA_SHAPES:
                errs.append("[%s] Light %r invalid shape %r" % (pid, lname, shape))
            kelvin = light.get("kelvin")
            if kelvin is not None and not (KELVIN_MIN <= float(kelvin) <= KELVIN_MAX):
                errs.append("[%s] Light %r kelvin %s out of range [%s, %s]" % (
                    pid, lname, kelvin, KELVIN_MIN, KELVIN_MAX))
            energy = light.get("energy")
            if energy is not None and float(energy) < 0:
                errs.append("[%s] Light %r energy must be >= 0" % (pid, lname))

    # LuxCore config (optional)
    lx_cfg = data.get("luxcore_cfg")
    if lx_cfg:
        engine = lx_cfg.get("engine")
        if engine and engine not in VALID_LXC_ENGINES:
            errs.append("[%s] luxcore_cfg engine %r invalid. Valid: %s" % (
                pid, engine, sorted(VALID_LXC_ENGINES)))
        depth = lx_cfg.get("path_depth")
        if depth is not None and int(depth) < 1:
            errs.append("[%s] luxcore_cfg path_depth must be >= 1" % pid)
        halts = lx_cfg.get("halt_samples")
        if halts is not None and int(halts) < 1:
            errs.append("[%s] luxcore_cfg halt_samples must be >= 1" % pid)

    # Env light (optional)
    env = data.get("env_light")
    if env is not None:
        etype = env.get("type")
        if etype and etype not in VALID_ENV_TYPES:
            errs.append("[%s] env_light type %r invalid. Valid: %s" % (
                pid, etype, sorted(VALID_ENV_TYPES)))
        gain = env.get("gain")
        if gain is not None and float(gain) < 0:
            errs.append("[%s] env_light gain must be >= 0" % pid)

    return errs



# ---------------------------------------------------------------------------
# Preset structure reference:
#   id           : unique snake_case identifier
#   name         : display name
#   category     : PORTRAIT | PRODUCT | ARCHITECTURE | CREATIVE
#   description  : short description shown in UI
#   lights       : list of light descriptors (see below)
#   env_light    : None or {"type":"sky2"|"constant", ...}
#   luxcore_cfg  : optional overrides for scene LuxCore config
#
# Light descriptor keys:
#   name         : object name (prefix LSM_ is added automatically)
#   type         : AREA | SPOT | SUN | POINT
#   location     : (x, y, z) world coords
#   target       : (x, y, z) point the light aims at (None = no constraint)
#   energy       : Blender energy (Watts for AREA/SPOT, strength for SUN)
#   color        : (r, g, b) linear  — used when kelvin is None
#   kelvin       : color temperature in K (overrides color if set)
#   size         : AREA width / SPOT spot_size in radians
#   size_y       : AREA height (defaults to size)
#   shape        : AREA shape: SQUARE|RECTANGLE|DISK|ELLIPSE
#   spot_blend   : SPOT blend factor [0..1]
#   use_shadow   : bool
#   luxcore_gain : LuxCore gain multiplier (on top of energy)
# ---------------------------------------------------------------------------

PRESETS = [

    # =========================================================================
    # PORTRAIT
    # =========================================================================

    {
        "id": "rembrandt",
        "name": "Rembrandt Classic",
        "category": "PORTRAIT",
        "description": (
            "The most iconic portrait setup. "
            "Rembrandt triangle on the far cheek. "
            "Key 45° lateral-up, soft fill, rear rim."
        ),
        "lights": [
            {
                "name": "Key",
                "type": "AREA",
                "location": (2.5, -2.0, 2.2),
                "target": (0.0, 0.0, 0.85),
                "energy": 500.0,
                "kelvin": 5600,
                "size": 1.2,
                "size_y": 1.8,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Fill",
                "type": "AREA",
                "location": (-2.2, -2.5, 1.0),
                "target": (0.0, 0.0, 0.8),
                "energy": 120.0,
                "kelvin": 6500,
                "size": 2.0,
                "size_y": 2.4,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Rim",
                "type": "AREA",
                "location": (-0.5, 2.8, 2.5),
                "target": (0.0, 0.0, 1.0),
                "energy": 320.0,
                "kelvin": 6200,
                "size": 0.8,
                "size_y": 1.5,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
        ],
        "env_light": None,
        "luxcore_cfg": {"engine": "PATH", "path_depth": 8, "halt_samples": 256, "denoiser": True},
    },

    {
        "id": "butterfly",
        "name": "Butterfly / Paramount",
        "category": "PORTRAIT",
        "description": (
            "Classic Hollywood glamour setup. Front-above key "
            "creates the butterfly nose shadow. Fashion and beauty."
        ),
        "lights": [
            {
                "name": "Key",
                "type": "AREA",
                "location": (0.0, -2.5, 2.8),
                "target": (0.0, 0.0, 0.9),
                "energy": 600.0,
                "kelvin": 5500,
                "size": 1.5,
                "size_y": 1.0,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Fill_Reflector",
                "type": "AREA",
                "location": (0.0, -1.5, -0.5),
                "target": (0.0, 0.0, 0.6),
                "energy": 150.0,
                "kelvin": 5500,
                "size": 1.8,
                "size_y": 1.0,
                "shape": "RECTANGLE",
                "use_shadow": False,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Rim_Left",
                "type": "AREA",
                "location": (-2.0, 2.0, 2.0),
                "target": (0.0, 0.0, 1.0),
                "energy": 200.0,
                "kelvin": 6000,
                "size": 0.6,
                "size_y": 1.2,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Rim_Right",
                "type": "AREA",
                "location": (2.0, 2.0, 2.0),
                "target": (0.0, 0.0, 1.0),
                "energy": 200.0,
                "kelvin": 6000,
                "size": 0.6,
                "size_y": 1.2,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
        ],
        "env_light": None,
        "luxcore_cfg": {"engine": "PATH", "path_depth": 8, "halt_samples": 256, "denoiser": True},
    },

    {
        "id": "loop",
        "name": "Loop Lighting",
        "category": "PORTRAIT",
        "description": (
            "Loop lighting: key at 30-45° creates a small "
            "nose shadow. Most versatile commercial portrait setup."
        ),
        "lights": [
            {
                "name": "Key",
                "type": "AREA",
                "location": (2.0, -2.5, 1.8),
                "target": (0.0, 0.0, 0.85),
                "energy": 450.0,
                "kelvin": 5600,
                "size": 1.3,
                "size_y": 2.0,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Fill",
                "type": "AREA",
                "location": (-1.8, -2.2, 1.0),
                "target": (0.0, 0.0, 0.8),
                "energy": 180.0,
                "kelvin": 6200,
                "size": 2.2,
                "size_y": 2.2,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Hair",
                "type": "SPOT",
                "location": (0.0, 0.5, 3.0),
                "target": (0.0, 0.0, 1.5),
                "energy": 200.0,
                "kelvin": 5800,
                "size": math.radians(25),
                "spot_blend": 0.2,
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
        ],
        "env_light": None,
        "luxcore_cfg": {"engine": "PATH", "path_depth": 8, "halt_samples": 256, "denoiser": True},
    },

    {
        "id": "split",
        "name": "Split Lighting",
        "category": "PORTRAIT",
        "description": (
            "Direct side key (90°): half face lit, half in shadow. "
            "Dramatic, high-contrast. Ideal for strong characters."
        ),
        "lights": [
            {
                "name": "Key",
                "type": "AREA",
                "location": (3.5, 0.0, 1.6),
                "target": (0.0, 0.0, 0.85),
                "energy": 550.0,
                "kelvin": 5200,
                "size": 1.0,
                "size_y": 2.0,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Rim",
                "type": "AREA",
                "location": (-1.5, 2.5, 2.0),
                "target": (0.0, 0.0, 1.0),
                "energy": 180.0,
                "kelvin": 6500,
                "size": 0.8,
                "size_y": 1.5,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
        ],
        "env_light": None,
        "luxcore_cfg": {"engine": "PATH", "path_depth": 6, "halt_samples": 200, "denoiser": True},
    },

    {
        "id": "clamshell",
        "name": "Clamshell Beauty",
        "category": "PORTRAIT",
        "description": (
            "Top key plus chin reflector fill. "
            "Eliminates under-eye shadows. Beauty and fashion."
        ),
        "lights": [
            {
                "name": "Key_Top",
                "type": "AREA",
                "location": (0.0, -2.0, 2.5),
                "target": (0.0, 0.0, 0.9),
                "energy": 500.0,
                "kelvin": 5500,
                "size": 2.0,
                "size_y": 1.0,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Fill_Bottom",
                "type": "AREA",
                "location": (0.0, -1.2, -0.3),
                "target": (0.0, 0.0, 0.7),
                "energy": 250.0,
                "kelvin": 5500,
                "size": 1.5,
                "size_y": 0.8,
                "shape": "RECTANGLE",
                "use_shadow": False,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Rim_Left",
                "type": "AREA",
                "location": (-2.5, 1.5, 1.8),
                "target": (0.0, 0.0, 1.0),
                "energy": 150.0,
                "kelvin": 6000,
                "size": 0.5,
                "size_y": 1.5,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Rim_Right",
                "type": "AREA",
                "location": (2.5, 1.5, 1.8),
                "target": (0.0, 0.0, 1.0),
                "energy": 150.0,
                "kelvin": 6000,
                "size": 0.5,
                "size_y": 1.5,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
        ],
        "env_light": None,
        "luxcore_cfg": {"engine": "PATH", "path_depth": 8, "halt_samples": 300, "denoiser": True},
    },

    {
        "id": "broad",
        "name": "Broad Lighting",
        "category": "PORTRAIT",
        "description": (
            "Key illuminates the wider (camera-facing) side of the face. "
            "Widening effect. Three-dimensional and friendly look."
        ),
        "lights": [
            {
                "name": "Key",
                "type": "AREA",
                "location": (-2.2, -1.8, 1.6),
                "target": (0.0, 0.0, 0.85),
                "energy": 480.0,
                "kelvin": 5600,
                "size": 1.4,
                "size_y": 2.0,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Fill",
                "type": "AREA",
                "location": (2.0, -2.5, 1.2),
                "target": (0.0, 0.0, 0.8),
                "energy": 140.0,
                "kelvin": 6200,
                "size": 2.0,
                "size_y": 2.0,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Background",
                "type": "AREA",
                "location": (0.0, 3.0, 0.0),
                "target": (0.0, 5.0, 0.0),
                "energy": 100.0,
                "kelvin": 5600,
                "size": 3.0,
                "size_y": 3.0,
                "shape": "RECTANGLE",
                "use_shadow": False,
                "luxcore_gain": 1.0,
            },
        ],
        "env_light": None,
        "luxcore_cfg": {"engine": "PATH", "path_depth": 8, "halt_samples": 256, "denoiser": True},
    },

    {
        "id": "short",
        "name": "Short Lighting",
        "category": "PORTRAIT",
        "description": (
            "Key illuminates the narrow (far) side of the face. "
            "Slimming effect. Common in masculine portraiture."
        ),
        "lights": [
            {
                "name": "Key",
                "type": "AREA",
                "location": (2.2, -1.8, 1.6),
                "target": (0.0, 0.0, 0.85),
                "energy": 480.0,
                "kelvin": 5600,
                "size": 1.4,
                "size_y": 2.0,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Fill",
                "type": "AREA",
                "location": (-2.0, -2.5, 1.2),
                "target": (0.0, 0.0, 0.8),
                "energy": 140.0,
                "kelvin": 6200,
                "size": 2.0,
                "size_y": 2.0,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Hair",
                "type": "SPOT",
                "location": (-0.5, 0.5, 3.2),
                "target": (0.0, 0.0, 1.6),
                "energy": 250.0,
                "kelvin": 5800,
                "size": math.radians(22),
                "spot_blend": 0.18,
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
        ],
        "env_light": None,
        "luxcore_cfg": {"engine": "PATH", "path_depth": 8, "halt_samples": 256, "denoiser": True},
    },

    {
        "id": "film_noir",
        "name": "Film Noir",
        "category": "PORTRAIT",
        "description": (
            "Dramatic top-down single hard spot with low fill. "
            "Extreme contrast, long shadows. Classic film noir."
        ),
        "lights": [
            {
                "name": "Top_Spot",
                "type": "SPOT",
                "location": (0.3, -0.5, 3.5),
                "target": (0.0, 0.0, 0.9),
                "energy": 800.0,
                "kelvin": 4200,
                "size": math.radians(20),
                "spot_blend": 0.05,
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Ground_Bounce",
                "type": "AREA",
                "location": (0.0, -0.5, -0.8),
                "target": (0.0, 0.0, 0.5),
                "energy": 60.0,
                "kelvin": 3800,
                "size": 3.0,
                "size_y": 2.0,
                "shape": "RECTANGLE",
                "use_shadow": False,
                "luxcore_gain": 1.0,
            },
        ],
        "env_light": None,
        "luxcore_cfg": {"engine": "PATH", "path_depth": 6, "halt_samples": 200, "denoiser": True},
    },

    # =========================================================================
    # PRODUCT
    # =========================================================================

    {
        "id": "product_45",
        "name": "Product Classic 45°",
        "category": "PRODUCT",
        "description": (
            "The most widely used product photography setup. "
            "45° front key, soft opposite fill, separation backlight."
        ),
        "lights": [
            {
                "name": "Key",
                "type": "AREA",
                "location": (2.0, -2.0, 2.0),
                "target": (0.0, 0.0, 0.3),
                "energy": 400.0,
                "kelvin": 5500,
                "size": 1.5,
                "size_y": 1.5,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Fill",
                "type": "AREA",
                "location": (-2.5, -1.5, 1.0),
                "target": (0.0, 0.0, 0.3),
                "energy": 120.0,
                "kelvin": 5800,
                "size": 2.5,
                "size_y": 2.5,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Backlight",
                "type": "AREA",
                "location": (0.0, 3.0, 1.5),
                "target": (0.0, 0.0, 0.3),
                "energy": 250.0,
                "kelvin": 6000,
                "size": 1.0,
                "size_y": 1.5,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
        ],
        "env_light": None,
        "luxcore_cfg": {"engine": "PATH", "path_depth": 10, "halt_samples": 512, "denoiser": True},
    },

    {
        "id": "clamshell_product",
        "name": "Product Clamshell",
        "category": "PRODUCT",
        "description": (
            "Symmetric top and bottom for jewelry and cosmetics. "
            "Even illumination that reveals surface detail and texture."
        ),
        "lights": [
            {
                "name": "Top",
                "type": "AREA",
                "location": (0.0, -0.5, 2.5),
                "target": (0.0, 0.0, 0.0),
                "energy": 450.0,
                "kelvin": 5500,
                "size": 2.0,
                "size_y": 2.0,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Bottom",
                "type": "AREA",
                "location": (0.0, -0.5, -2.0),
                "target": (0.0, 0.0, 0.0),
                "energy": 280.0,
                "kelvin": 5500,
                "size": 2.0,
                "size_y": 2.0,
                "shape": "RECTANGLE",
                "use_shadow": False,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Side_Left",
                "type": "AREA",
                "location": (-2.5, -0.5, 0.5),
                "target": (0.0, 0.0, 0.2),
                "energy": 100.0,
                "kelvin": 5800,
                "size": 0.5,
                "size_y": 1.5,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Side_Right",
                "type": "AREA",
                "location": (2.5, -0.5, 0.5),
                "target": (0.0, 0.0, 0.2),
                "energy": 100.0,
                "kelvin": 5800,
                "size": 0.5,
                "size_y": 1.5,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
        ],
        "env_light": None,
        "luxcore_cfg": {"engine": "PATH", "path_depth": 12, "halt_samples": 512, "denoiser": True},
    },

    {
        "id": "tabletop_sweep",
        "name": "Tabletop Sweep",
        "category": "PRODUCT",
        "description": (
            "Tabletop with seamless sweep background. "
            "Large side softbox, bounce fill. Professional e-commerce."
        ),
        "lights": [
            {
                "name": "Main_Softbox",
                "type": "AREA",
                "location": (3.0, -1.0, 2.0),
                "target": (0.0, 0.0, 0.2),
                "energy": 380.0,
                "kelvin": 5600,
                "size": 2.5,
                "size_y": 2.5,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Fill_Bounce",
                "type": "AREA",
                "location": (-2.8, -1.0, 1.5),
                "target": (0.0, 0.0, 0.2),
                "energy": 110.0,
                "kelvin": 5800,
                "size": 2.0,
                "size_y": 2.0,
                "shape": "RECTANGLE",
                "use_shadow": False,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Top_Fill",
                "type": "AREA",
                "location": (0.0, 0.0, 3.5),
                "target": (0.0, 0.0, 0.0),
                "energy": 80.0,
                "kelvin": 6200,
                "size": 3.0,
                "size_y": 3.0,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
        ],
        "env_light": None,
        "luxcore_cfg": {"engine": "PATH", "path_depth": 10, "halt_samples": 400, "denoiser": True},
    },

    {
        "id": "infinity_white",
        "name": "Infinity White",
        "category": "PRODUCT",
        "description": (
            "High-key with infinite white background. "
            "Multiple wrap lights to eliminate shadows. "
            "Catalogues and e-commerce."
        ),
        "lights": [
            {
                "name": "Top_Main",
                "type": "AREA",
                "location": (0.0, 0.0, 3.0),
                "target": (0.0, 0.0, 0.0),
                "energy": 400.0,
                "kelvin": 6500,
                "size": 4.0,
                "size_y": 4.0,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Front",
                "type": "AREA",
                "location": (0.0, -3.0, 1.0),
                "target": (0.0, 0.0, 0.2),
                "energy": 300.0,
                "kelvin": 6500,
                "size": 3.0,
                "size_y": 2.5,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Back",
                "type": "AREA",
                "location": (0.0, 3.0, 1.0),
                "target": (0.0, 0.0, 0.0),
                "energy": 350.0,
                "kelvin": 6500,
                "size": 3.0,
                "size_y": 2.5,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Left",
                "type": "AREA",
                "location": (-3.0, 0.0, 1.0),
                "target": (0.0, 0.0, 0.2),
                "energy": 280.0,
                "kelvin": 6500,
                "size": 3.0,
                "size_y": 2.5,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Right",
                "type": "AREA",
                "location": (3.0, 0.0, 1.0),
                "target": (0.0, 0.0, 0.2),
                "energy": 280.0,
                "kelvin": 6500,
                "size": 3.0,
                "size_y": 2.5,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
        ],
        "env_light": None,
        "luxcore_cfg": {"engine": "PATH", "path_depth": 6, "halt_samples": 300, "denoiser": True},
    },

    {
        "id": "backlit_product",
        "name": "Backlit / Translucent",
        "category": "PRODUCT",
        "description": (
            "Strong backlight for bottles, jars and translucent products. "
            "Side rim lights for separation. Minimal front fill."
        ),
        "lights": [
            {
                "name": "Back_Main",
                "type": "AREA",
                "location": (0.0, 3.5, 0.5),
                "target": (0.0, 0.0, 0.3),
                "energy": 700.0,
                "kelvin": 6500,
                "size": 2.0,
                "size_y": 2.0,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Rim_Left",
                "type": "AREA",
                "location": (-2.5, 2.0, 1.0),
                "target": (0.0, 0.0, 0.3),
                "energy": 350.0,
                "kelvin": 6200,
                "size": 0.5,
                "size_y": 1.8,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Rim_Right",
                "type": "AREA",
                "location": (2.5, 2.0, 1.0),
                "target": (0.0, 0.0, 0.3),
                "energy": 350.0,
                "kelvin": 6200,
                "size": 0.5,
                "size_y": 1.8,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Front_Fill",
                "type": "AREA",
                "location": (0.0, -3.0, 1.0),
                "target": (0.0, 0.0, 0.3),
                "energy": 80.0,
                "kelvin": 5800,
                "size": 2.0,
                "size_y": 2.0,
                "shape": "RECTANGLE",
                "use_shadow": False,
                "luxcore_gain": 1.0,
            },
        ],
        "env_light": None,
        "luxcore_cfg": {"engine": "PATH", "path_depth": 14, "halt_samples": 600, "denoiser": True},
    },

    {
        "id": "studio_3light",
        "name": "Studio Three-Point Pro",
        "category": "PRODUCT",
        "description": (
            "Three professional softboxes: front-side key, "
            "soft opposite fill, and top accent. "
            "Versatile setup for any product."
        ),
        "lights": [
            {
                "name": "Key_Softbox",
                "type": "AREA",
                "location": (2.5, -2.5, 1.8),
                "target": (0.0, 0.0, 0.25),
                "energy": 420.0,
                "kelvin": 5500,
                "size": 2.0,
                "size_y": 2.0,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Fill_Softbox",
                "type": "AREA",
                "location": (-2.0, -2.0, 1.2),
                "target": (0.0, 0.0, 0.25),
                "energy": 160.0,
                "kelvin": 5700,
                "size": 2.5,
                "size_y": 2.5,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Top_Accent",
                "type": "AREA",
                "location": (0.5, 0.0, 3.5),
                "target": (0.0, 0.0, 0.0),
                "energy": 200.0,
                "kelvin": 5800,
                "size": 1.5,
                "size_y": 1.5,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
        ],
        "env_light": None,
        "luxcore_cfg": {"engine": "PATH", "path_depth": 10, "halt_samples": 400, "denoiser": True},
    },

    {
        "id": "jewelry_sparkle",
        "name": "Jewelry Macro Sparkle",
        "category": "PRODUCT",
        "description": (
            "Precision lighting for jewelry. "
            "Multiple small hard sources to create sparkle. "
            "High path depth for caustics."
        ),
        "lights": [
            {
                "name": "Key_Top",
                "type": "SPOT",
                "location": (0.0, -0.5, 1.5),
                "target": (0.0, 0.0, 0.0),
                "energy": 300.0,
                "kelvin": 6000,
                "size": math.radians(15),
                "spot_blend": 0.05,
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Accent_1",
                "type": "SPOT",
                "location": (0.8, -0.8, 1.2),
                "target": (0.0, 0.0, 0.0),
                "energy": 180.0,
                "kelvin": 5800,
                "size": math.radians(12),
                "spot_blend": 0.05,
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Accent_2",
                "type": "SPOT",
                "location": (-0.8, -0.8, 1.2),
                "target": (0.0, 0.0, 0.0),
                "energy": 180.0,
                "kelvin": 5800,
                "size": math.radians(12),
                "spot_blend": 0.05,
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Diffuse_Fill",
                "type": "AREA",
                "location": (0.0, -2.0, 0.5),
                "target": (0.0, 0.0, 0.0),
                "energy": 80.0,
                "kelvin": 5600,
                "size": 2.0,
                "size_y": 2.0,
                "shape": "RECTANGLE",
                "use_shadow": False,
                "luxcore_gain": 1.0,
            },
        ],
        "env_light": None,
        "luxcore_cfg": {"engine": "PATH", "path_depth": 16, "halt_samples": 1024, "denoiser": True},
    },

    {
        "id": "cosmetic_gradient",
        "name": "Cosmetic Gradient Beauty",
        "category": "PRODUCT",
        "description": (
            "Smooth gradient for cosmetics and perfumery. "
            "Enveloping front light with subtle rear accent. "
            "Faithful, gradual colors."
        ),
        "lights": [
            {
                "name": "Wrap_Front",
                "type": "AREA",
                "location": (0.0, -2.5, 1.0),
                "target": (0.0, 0.0, 0.3),
                "energy": 350.0,
                "kelvin": 5500,
                "size": 4.0,
                "size_y": 3.0,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Top_Soft",
                "type": "AREA",
                "location": (0.0, -0.5, 2.8),
                "target": (0.0, 0.0, 0.0),
                "energy": 200.0,
                "kelvin": 5500,
                "size": 3.0,
                "size_y": 3.0,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Back_Glow",
                "type": "AREA",
                "location": (0.0, 2.5, 1.5),
                "target": (0.0, 0.0, 0.3),
                "energy": 150.0,
                "kelvin": 6500,
                "size": 1.5,
                "size_y": 2.0,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
        ],
        "env_light": None,
        "luxcore_cfg": {"engine": "PATH", "path_depth": 10, "halt_samples": 512, "denoiser": True},
    },

    # =========================================================================
    # ARCHITECTURE
    # =========================================================================

    {
        "id": "interior_day",
        "name": "Interior Daylight",
        "category": "ARCHITECTURE",
        "description": (
            "Natural daylight entering through a side window. "
            "Sun + sky area for diffuse exterior light. "
            "Soft interior fill."
        ),
        "lights": [
            {
                "name": "Sun",
                "type": "SUN",
                "location": (5.0, -3.0, 8.0),
                "target": (0.0, 0.0, 0.0),
                "energy": 3.5,
                "kelvin": 5800,
                "size": 0.1,
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Sky_Diffuse",
                "type": "AREA",
                "location": (4.0, 0.0, 2.0),
                "target": (0.0, 0.0, 1.0),
                "energy": 150.0,
                "kelvin": 10000,
                "size": 3.0,
                "size_y": 3.0,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Interior_Fill",
                "type": "AREA",
                "location": (-4.0, 0.0, 2.0),
                "target": (0.0, 0.0, 1.0),
                "energy": 40.0,
                "kelvin": 6500,
                "size": 3.0,
                "size_y": 3.0,
                "shape": "RECTANGLE",
                "use_shadow": False,
                "luxcore_gain": 1.0,
            },
        ],
        "env_light": {"type": "sky2", "turbidity": 3.0, "gain": 0.015},
        "luxcore_cfg": {"engine": "PATH", "path_depth": 10, "halt_samples": 512, "denoiser": True},
    },

    {
        "id": "interior_night",
        "name": "Interior Night Artificial",
        "category": "ARCHITECTURE",
        "description": (
            "Artificial night interior lighting. "
            "Warm main sources, cool accent. "
            "Intimate and welcoming atmosphere."
        ),
        "lights": [
            {
                "name": "Pendant_1",
                "type": "POINT",
                "location": (0.0, 0.0, 2.5),
                "target": None,
                "energy": 400.0,
                "kelvin": 2700,
                "size": 0.05,
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Pendant_2",
                "type": "POINT",
                "location": (-2.0, 1.5, 2.5),
                "target": None,
                "energy": 300.0,
                "kelvin": 2700,
                "size": 0.05,
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Ambient_Warm",
                "type": "AREA",
                "location": (0.0, 0.0, 3.0),
                "target": (0.0, 0.0, 0.0),
                "energy": 60.0,
                "kelvin": 3200,
                "size": 4.0,
                "size_y": 4.0,
                "shape": "RECTANGLE",
                "use_shadow": False,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Accent_Cold",
                "type": "SPOT",
                "location": (3.0, -2.0, 2.8),
                "target": (1.5, 0.0, 0.0),
                "energy": 200.0,
                "kelvin": 5000,
                "size": math.radians(30),
                "spot_blend": 0.3,
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
        ],
        "env_light": {"type": "constant", "gain": 0.001, "color": (0.02, 0.03, 0.06)},
        "luxcore_cfg": {"engine": "BIDIR", "path_depth": 12, "halt_samples": 512, "denoiser": True},
    },

    {
        "id": "exterior_golden",
        "name": "Exterior Golden Hour",
        "category": "ARCHITECTURE",
        "description": (
            "Golden hour: low warm sun from the horizon. "
            "Cool sky fill as contrast. "
            "Long shadows and photographic warmth."
        ),
        "lights": [
            {
                "name": "Sun_Golden",
                "type": "SUN",
                "location": (8.0, -2.0, 1.5),
                "target": (0.0, 0.0, 0.0),
                "energy": 4.5,
                "kelvin": 2850,
                "size": 0.15,
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Sky_Fill",
                "type": "AREA",
                "location": (0.0, 0.0, 8.0),
                "target": (0.0, 0.0, 0.0),
                "energy": 80.0,
                "kelvin": 12000,
                "size": 10.0,
                "size_y": 10.0,
                "shape": "RECTANGLE",
                "use_shadow": False,
                "luxcore_gain": 1.0,
            },
        ],
        "env_light": {"type": "sky2", "turbidity": 5.0, "gain": 0.02},
        "luxcore_cfg": {"engine": "PATH", "path_depth": 10, "halt_samples": 400, "denoiser": True},
    },

    {
        "id": "exterior_overcast",
        "name": "Exterior Overcast",
        "category": "ARCHITECTURE",
        "description": (
            "Overcast sky: diffuse light with no hard shadows. "
            "Perfect for architectural visualization without lighting distractions."
        ),
        "lights": [
            {
                "name": "Sky_Dome",
                "type": "AREA",
                "location": (0.0, 0.0, 6.0),
                "target": (0.0, 0.0, 0.0),
                "energy": 250.0,
                "kelvin": 7000,
                "size": 12.0,
                "size_y": 12.0,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Front_Ambient",
                "type": "AREA",
                "location": (0.0, -6.0, 3.0),
                "target": (0.0, 0.0, 1.0),
                "energy": 80.0,
                "kelvin": 7500,
                "size": 8.0,
                "size_y": 6.0,
                "shape": "RECTANGLE",
                "use_shadow": False,
                "luxcore_gain": 1.0,
            },
        ],
        "env_light": {"type": "sky2", "turbidity": 8.0, "gain": 0.025},
        "luxcore_cfg": {"engine": "PATH", "path_depth": 8, "halt_samples": 350, "denoiser": True},
    },

    {
        "id": "window_minimal",
        "name": "Window Natural Minimal",
        "category": "ARCHITECTURE",
        "description": (
            "A single window as the only light source. "
            "Minimalist and photorealistic. "
            "Ideal for interior room renders."
        ),
        "lights": [
            {
                "name": "Window",
                "type": "AREA",
                "location": (4.5, 0.0, 1.8),
                "target": (0.0, 0.0, 1.0),
                "energy": 600.0,
                "kelvin": 6500,
                "size": 1.5,
                "size_y": 2.2,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Ambient_Bounce",
                "type": "AREA",
                "location": (0.0, 0.0, 4.0),
                "target": (0.0, 0.0, 0.0),
                "energy": 25.0,
                "kelvin": 6500,
                "size": 6.0,
                "size_y": 6.0,
                "shape": "RECTANGLE",
                "use_shadow": False,
                "luxcore_gain": 1.0,
            },
        ],
        "env_light": None,
        "luxcore_cfg": {"engine": "BIDIR", "path_depth": 12, "halt_samples": 512, "denoiser": True},
    },

    # =========================================================================
    # CREATIVE
    # =========================================================================

    {
        "id": "moody_drama",
        "name": "Moody Drama",
        "category": "CREATIVE",
        "description": (
            "High dramatic contrast. Hard front-side key, "
            "no intentional fill. Deep shadows, dark atmosphere."
        ),
        "lights": [
            {
                "name": "Key_Hard",
                "type": "SPOT",
                "location": (3.0, -1.5, 2.8),
                "target": (0.0, 0.0, 0.8),
                "energy": 700.0,
                "kelvin": 4500,
                "size": math.radians(18),
                "spot_blend": 0.05,
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Rim_Cold",
                "type": "AREA",
                "location": (-2.0, 2.5, 2.0),
                "target": (0.0, 0.0, 1.0),
                "energy": 180.0,
                "kelvin": 8000,
                "size": 0.6,
                "size_y": 1.8,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
        ],
        "env_light": {"type": "constant", "gain": 0.0005, "color": (0.01, 0.01, 0.015)},
        "luxcore_cfg": {"engine": "PATH", "path_depth": 8, "halt_samples": 300, "denoiser": True},
    },

    {
        "id": "high_key",
        "name": "High Key Ethereal",
        "category": "CREATIVE",
        "description": (
            "No visible shadows, bright and ethereal light. "
            "Multiple cold-temperature wrap softboxes. "
            "Fashion, conceptual."
        ),
        "lights": [
            {
                "name": "Wrap_Front",
                "type": "AREA",
                "location": (0.0, -3.0, 1.5),
                "target": (0.0, 0.0, 0.8),
                "energy": 500.0,
                "kelvin": 6500,
                "size": 5.0,
                "size_y": 4.0,
                "shape": "RECTANGLE",
                "use_shadow": False,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Wrap_Left",
                "type": "AREA",
                "location": (-3.0, -1.0, 1.5),
                "target": (0.0, 0.0, 0.8),
                "energy": 350.0,
                "kelvin": 6500,
                "size": 4.0,
                "size_y": 4.0,
                "shape": "RECTANGLE",
                "use_shadow": False,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Wrap_Right",
                "type": "AREA",
                "location": (3.0, -1.0, 1.5),
                "target": (0.0, 0.0, 0.8),
                "energy": 350.0,
                "kelvin": 6500,
                "size": 4.0,
                "size_y": 4.0,
                "shape": "RECTANGLE",
                "use_shadow": False,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Top",
                "type": "AREA",
                "location": (0.0, 0.0, 3.5),
                "target": (0.0, 0.0, 0.0),
                "energy": 400.0,
                "kelvin": 6500,
                "size": 4.0,
                "size_y": 4.0,
                "shape": "RECTANGLE",
                "use_shadow": False,
                "luxcore_gain": 1.0,
            },
        ],
        "env_light": {"type": "constant", "gain": 0.05, "color": (1.0, 1.0, 1.0)},
        "luxcore_cfg": {"engine": "PATH", "path_depth": 6, "halt_samples": 200, "denoiser": True},
    },

    {
        "id": "neon_rgb",
        "name": "Neon RGB Atmosphere",
        "category": "CREATIVE",
        "description": (
            "RGB accent lights. Cool blue key, warm orange fill, "
            "green-cyan rim. Cyberpunk / editorial."
        ),
        "lights": [
            {
                "name": "Key_Blue",
                "type": "AREA",
                "location": (2.0, -2.5, 1.8),
                "target": (0.0, 0.0, 0.8),
                "energy": 450.0,
                "kelvin": None,
                "color": (0.2, 0.4, 1.0),
                "size": 1.0,
                "size_y": 2.0,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Fill_Orange",
                "type": "AREA",
                "location": (-2.0, -2.0, 1.0),
                "target": (0.0, 0.0, 0.8),
                "energy": 280.0,
                "kelvin": None,
                "color": (1.0, 0.35, 0.05),
                "size": 1.8,
                "size_y": 1.8,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Rim_Cyan",
                "type": "AREA",
                "location": (-0.5, 3.0, 2.0),
                "target": (0.0, 0.0, 1.0),
                "energy": 350.0,
                "kelvin": None,
                "color": (0.1, 1.0, 0.7),
                "size": 0.5,
                "size_y": 2.0,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            {
                "name": "Ground_Purple",
                "type": "AREA",
                "location": (0.0, 0.0, -1.0),
                "target": (0.0, 0.0, 0.5),
                "energy": 120.0,
                "kelvin": None,
                "color": (0.5, 0.1, 0.8),
                "size": 4.0,
                "size_y": 4.0,
                "shape": "RECTANGLE",
                "use_shadow": False,
                "luxcore_gain": 1.0,
            },
        ],
        "env_light": {"type": "constant", "gain": 0.001, "color": (0.02, 0.01, 0.05)},
        "luxcore_cfg": {"engine": "PATH", "path_depth": 8, "halt_samples": 350, "denoiser": True},
    },

    {
        "id": "candlelight",
        "name": "Candlelight Atmosphere",
        "category": "CREATIVE",
        "description": (
            "Candlelight warmth. Point sources at very warm temperature "
            "with minimal bounce fill. Deep darkness."
        ),
        "lights": [
            {
                "name": "Candle_Main",
                "type": "POINT",
                "location": (0.5, -0.3, 0.2),
                "target": None,
                "energy": 20.0,          # LuxCore: 20 × 0.10 × 8.0 = 16.0 gain
                "cycles_energy": 140.0,  # Cycles: direct Watts compensating absent gain
                "kelvin": 1850,
                "size": 0.02,
                "use_shadow": True,
                "luxcore_gain": 8.0,
            },
            {
                "name": "Candle_2",
                "type": "POINT",
                "location": (-0.4, 0.5, 0.15),
                "target": None,
                "energy": 15.0,          # LuxCore: 15 × 0.10 × 6.0 = 9.0 gain
                "cycles_energy": 90.0,   # Cycles: proportional to Candle_Main
                "kelvin": 1900,
                "size": 0.02,
                "use_shadow": True,
                "luxcore_gain": 6.0,
            },
            {
                "name": "Bounce_Warm",
                "type": "AREA",
                "location": (0.0, -2.0, 0.5),
                "target": (0.0, 0.0, 0.5),
                "energy": 8.0,
                "kelvin": 2200,
                "size": 3.0,
                "size_y": 2.0,
                "shape": "RECTANGLE",
                "use_shadow": False,
                "luxcore_gain": 1.0,
            },
        ],
        "env_light": {"type": "constant", "gain": 0.0002, "color": (0.03, 0.015, 0.005)},
        "luxcore_cfg": {"engine": "BIDIR", "path_depth": 10, "halt_samples": 600, "denoiser": True},
    },

    # =========================================================================
    # PRODUCT — automotive
    # =========================================================================

    {
        "id": "automotive_studio",
        "name": "Automotive Studio Rig",
        "category": "PRODUCT",
        "description": (
            "Professional car photography rig. "
            "Matched vertical strip lights reveal bodywork curvature. "
            "Overhead panel + front key + ground fill simulate white cyclorama."
        ),
        "lights": [
            # Long vertical strip: specular streak along driver's side
            {
                "name": "Strip_Left",
                "type": "AREA",
                "location": (-4.5, 0.0, 1.5),
                "target": (0.0, 0.0, 0.8),
                "energy": 600.0,
                "kelvin": 5500,
                "size": 0.25,
                "size_y": 5.0,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            # Long vertical strip: specular streak along passenger side
            {
                "name": "Strip_Right",
                "type": "AREA",
                "location": (4.5, 0.0, 1.5),
                "target": (0.0, 0.0, 0.8),
                "energy": 600.0,
                "kelvin": 5500,
                "size": 0.25,
                "size_y": 5.0,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            # Overhead softbox: top-plane fill, hood/roof gradients
            {
                "name": "Overhead_Panel",
                "type": "AREA",
                "location": (0.0, -1.0, 5.5),
                "target": (0.0, 0.0, 0.0),
                "energy": 350.0,
                "kelvin": 5800,
                "size": 4.0,
                "size_y": 3.0,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            # Front key: grille, headlights, front fascia
            {
                "name": "Front_Key",
                "type": "AREA",
                "location": (0.0, -5.0, 2.0),
                "target": (0.0, 0.0, 0.5),
                "energy": 200.0,
                "kelvin": 5600,
                "size": 3.0,
                "size_y": 2.0,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            # Ground fill: cyclorama floor bounce, undercar detail
            {
                "name": "Ground_Fill",
                "type": "AREA",
                "location": (0.0, 0.0, -1.5),
                "target": (0.0, 0.0, 1.0),
                "energy": 80.0,
                "kelvin": 5500,
                "size": 6.0,
                "size_y": 6.0,
                "shape": "RECTANGLE",
                "use_shadow": False,
                "luxcore_gain": 1.0,
            },
        ],
        # White cyclorama ambient: fills crevices, keeps specular clean
        "env_light": {"type": "constant", "gain": 0.003, "color": (1.0, 1.0, 1.0)},
        "luxcore_cfg": {"engine": "PATH", "path_depth": 12, "halt_samples": 600, "denoiser": True},
    },

    # =========================================================================
    # CINEMATIC
    # =========================================================================

    {
        "id": "cin_deakins_window",
        "name": "Deakins — Window Natural",
        "category": "CINEMATIC",
        "description": (
            "Roger Deakins interior style. "
            "Motivated single window key, very large and soft. "
            "Sky bounce fill, subtle rear rim. Naturalistic, no obvious rig."
        ),
        "lights": [
            # Large window substitute: the sole motivated source
            {
                "name": "Window_Key",
                "type": "AREA",
                "location": (-3.5, -1.0, 1.8),
                "target": (0.0, 0.0, 0.9),
                "energy": 280.0,
                "kelvin": 5200,
                "size": 2.8,
                "size_y": 2.0,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            # Ceiling sky bounce: indirect fill from opposite side, very low ratio
            {
                "name": "Sky_Bounce",
                "type": "AREA",
                "location": (0.0, 0.0, 4.5),
                "target": (0.0, 0.0, 0.0),
                "energy": 35.0,
                "kelvin": 7500,
                "size": 5.0,
                "size_y": 5.0,
                "shape": "RECTANGLE",
                "use_shadow": False,
                "luxcore_gain": 1.0,
            },
            # Rear soft rim: separates subject from background, barely readable
            {
                "name": "Rim_Soft",
                "type": "AREA",
                "location": (1.5, 3.0, 2.0),
                "target": (0.0, 0.0, 1.0),
                "energy": 60.0,
                "kelvin": 5800,
                "size": 1.2,
                "size_y": 2.5,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
        ],
        "env_light": {"type": "sky2", "turbidity": 3.5, "gain": 0.008},
        # BIDIR: essential for correct interior fill from a single window source
        "luxcore_cfg": {"engine": "BIDIR", "path_depth": 12, "halt_samples": 800, "denoiser": True},
    },

    {
        "id": "cin_wkw_amber_night",
        "name": "Wong Kar-wai — Amber Night",
        "category": "CINEMATIC",
        "description": (
            "Wong Kar-wai / Christopher Doyle palette. "
            "Warm practical as dominant source, neon accent, "
            "saturated coloured bounce. High emotional contrast."
        ),
        "lights": [
            # Practical lamp: the only 'real' light source in the space
            # cycles_energy is higher because luxcore_gain has no Cycles equivalent
            {
                "name": "Practical_Main",
                "type": "POINT",
                "location": (0.8, -0.5, 0.9),
                "target": None,
                "energy": 25.0,           # LuxCore: 25 × 0.10 × 10.0 = 25.0 gain
                "cycles_energy": 180.0,   # Cycles: direct Watts, no gain system
                "kelvin": None,
                "color": (1.0, 0.38, 0.08),   # amber profundo
                "size": 0.05,
                "use_shadow": True,
                "luxcore_gain": 10.0,
            },
            # Neon strip behind subject: green-cyan, typical of WKW Hong Kong streets
            {
                "name": "Neon_Back",
                "type": "AREA",
                "location": (0.0, 3.5, 1.2),
                "target": (0.0, 0.0, 0.9),
                "energy": 90.0,
                "kelvin": None,
                "color": (0.1, 0.80, 0.55),   # verde-cyan neón
                "size": 0.15,
                "size_y": 1.8,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            # Saturated wall bounce: deep red, as if reflecting off a red-painted wall
            {
                "name": "Wall_Bounce",
                "type": "AREA",
                "location": (-2.5, 0.5, 1.5),
                "target": (0.0, 0.0, 0.8),
                "energy": 45.0,
                "kelvin": None,
                "color": (0.9, 0.25, 0.15),   # rojo sangre
                "size": 2.0,
                "size_y": 2.5,
                "shape": "RECTANGLE",
                "use_shadow": False,
                "luxcore_gain": 1.0,
            },
        ],
        # Deep night ambient: barely perceptible warm-black
        "env_light": {"type": "constant", "gain": 0.0003, "color": (0.08, 0.04, 0.02)},
        # BIDIR: POINT practicals in dark scenes cause fireflies in PATH
        "luxcore_cfg": {"engine": "BIDIR", "path_depth": 12, "halt_samples": 700, "denoiser": True},
    },

    {
        "id": "cin_br2049",
        "name": "Blade Runner 2049",
        "category": "CINEMATIC",
        "description": (
            "Deakins / BR2049 palette. "
            "Cold blue ambient from above, high-energy orange neon accent, "
            "electric blue rim. Near-zero fill ratio. Extreme colour contrast."
        ),
        "lights": [
            # Overcast dystopian sky: cold blue, diffuse, dominant ambient
            {
                "name": "Sky_Cold",
                "type": "AREA",
                "location": (0.0, 0.0, 5.0),
                "target": (0.0, 0.0, 0.0),
                "energy": 80.0,
                "kelvin": None,
                "color": (0.08, 0.18, 0.55),   # azul oscuro
                "size": 6.0,
                "size_y": 6.0,
                "shape": "RECTANGLE",
                "use_shadow": False,
                "luxcore_gain": 1.0,
            },
            # Orange neon: the signature warm accent, punchy and narrow
            {
                "name": "Neon_Orange",
                "type": "AREA",
                "location": (3.0, 1.5, 0.8),
                "target": (0.0, 0.0, 0.5),
                "energy": 320.0,
                "kelvin": None,
                "color": (1.0, 0.30, 0.04),   # naranja neón
                "size": 0.2,
                "size_y": 2.5,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.5,
            },
            # Electric blue rim: hard separation, reinforces the cold atmosphere
            {
                "name": "Rim_Electric",
                "type": "AREA",
                "location": (-1.0, 3.0, 2.5),
                "target": (0.0, 0.0, 1.2),
                "energy": 200.0,
                "kelvin": None,
                "color": (0.15, 0.45, 1.0),   # azul eléctrico
                "size": 0.4,
                "size_y": 2.0,
                "shape": "RECTANGLE",
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
        ],
        # Near-black blue: the void between neon sources
        "env_light": {"type": "constant", "gain": 0.0002, "color": (0.04, 0.08, 0.20)},
        "luxcore_cfg": {"engine": "PATH", "path_depth": 10, "halt_samples": 500, "denoiser": True},
    },

    {
        "id": "cin_a24_golden",
        "name": "A24 — Golden Naturalism",
        "category": "CINEMATIC",
        "description": (
            "A24 available-light philosophy. "
            "Low warm sun as sole motivated key, cool sky fill as contrast, "
            "ground bounce for underside warmth. "
            "No obvious rig. Relies on global illumination for cohesion."
        ),
        "lights": [
            # Late afternoon sun: low angle, very warm, single motivated source
            {
                "name": "Sun_Late",
                "type": "SUN",
                "location": (6.0, -2.0, 1.8),
                "target": (0.0, 0.0, 0.0),
                "energy": 3.2,
                "kelvin": 3200,   # deepest golden-hour warmth
                "size": 0.08,
                "use_shadow": True,
                "luxcore_gain": 1.0,
            },
            # Open sky fill: large, cool, low energy — the natural counter-key
            {
                "name": "Sky_Soft",
                "type": "AREA",
                "location": (0.0, -1.0, 7.0),
                "target": (0.0, 0.0, 0.5),
                "energy": 60.0,
                "kelvin": 10000,   # sky blue (within LuxCore 12 000 K cap)
                "size": 8.0,
                "size_y": 8.0,
                "shape": "RECTANGLE",
                "use_shadow": False,
                "luxcore_gain": 1.0,
            },
            # Ground bounce: warm earth tone from below, subtle detail in shadows
            {
                "name": "Ground_Bounce",
                "type": "AREA",
                "location": (0.0, 0.0, -0.5),
                "target": (0.0, 0.0, 1.5),
                "energy": 25.0,
                "kelvin": 3800,
                "size": 5.0,
                "size_y": 5.0,
                "shape": "RECTANGLE",
                "use_shadow": False,
                "luxcore_gain": 1.0,
            },
        ],
        "env_light": {"type": "sky2", "turbidity": 2.5, "gain": 0.015},
        # BIDIR + high samples: A24 naturalism is born from global illumination
        "luxcore_cfg": {"engine": "BIDIR", "path_depth": 14, "halt_samples": 1000, "denoiser": True},
    },
]

# ---------------------------------------------------------------------------
# Category metadata for UI
# ---------------------------------------------------------------------------
# CATEGORY_DEFS and CATEGORY_ICONS are the authoritative definitions,
# living in constants.py. CATEGORIES is kept as an alias so existing
# code that does `from .presets_data import CATEGORIES` keeps working.

CATEGORIES = CATEGORY_DEFS

# Build lookup dict for fast access
PRESETS_BY_ID: dict = {p["id"]: p for p in PRESETS}


# ---------------------------------------------------------------------------
# User preset hot-reload
# ---------------------------------------------------------------------------

def reload_user_presets() -> int:
    """Load user_presets.json and merge into the live PRESETS / PRESETS_BY_ID.

    Called after save or delete operations so the UIList reflects changes
    immediately without restarting Blender.

    Returns the number of user presets loaded.
    """
    import os, json

    path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "user_presets.json")

    # Remove any previously loaded user presets from the live collections
    for pid in [p["id"] for p in PRESETS if p.get("is_user")]:
        PRESETS_BY_ID.pop(pid, None)
    PRESETS[:] = [p for p in PRESETS if not p.get("is_user")]

    if not os.path.isfile(path):
        return 0

    try:
        with open(path, "r", encoding="utf-8") as fh:
            user_list = json.load(fh)
        if not isinstance(user_list, list):
            return 0
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("[LSM] reload_user_presets: %s", exc)
        return 0

    loaded = 0
    for p in user_list:
        errs = validate_preset(p)
        if not errs:
            PRESETS.append(p)
            PRESETS_BY_ID[p["id"]] = p
            loaded += 1

    return loaded


# Load user presets at import time (addon startup)
reload_user_presets()