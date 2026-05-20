# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  difrkaguilar + Claude (Anthropic)
# LuxCore Stage Manager -- Cycles Compatibility Layer
#
# Applies Cycles-specific and Blender-native light settings.
# Symmetric to lxc_compat.py: same function signature contract,
# no BlendLuxCore dependency whatsoever.
#
# Supported engines: CYCLES, BLENDER_EEVEE_NEXT, BLENDER_EEVEE

from __future__ import annotations
import math
import logging
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Safe setter (same pattern as lxc_compat._try_set)
# ---------------------------------------------------------------------------

def _try_set(obj, attr: str, value) -> bool:
    if obj is None:
        return False
    try:
        setattr(obj, attr, value)
        return True
    except Exception as exc:
        log.debug("[LSM-CYC] _try_set %s.%s=%r: %s",
                  type(obj).__name__, attr, repr(value), exc)
        return False


def _try_get(obj, attr: str, default=None):
    try:
        return getattr(obj, attr, default)
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Engine detection helpers
# ---------------------------------------------------------------------------

def is_cycles(scene) -> bool:
    from .constants import CYCLES_ENGINE_ID
    return scene.render.engine == CYCLES_ENGINE_ID


def is_cycles_like(scene) -> bool:
    """True for Cycles AND EEVEE (both use Blender-native light energy)."""
    from .constants import CYCLES_LIKE_ENGINES
    return scene.render.engine in CYCLES_LIKE_ENGINES


def get_engine_label(scene) -> str:
    """Human-readable engine name for UI display."""
    engine = scene.render.engine
    labels = {
        "CYCLES":              "Cycles",
        "BLENDER_EEVEE_NEXT":  "EEVEE",
        "BLENDER_EEVEE":       "EEVEE (Legacy)",
        "LUXCORE":             "LuxCore",
    }
    return labels.get(engine, engine)


# ---------------------------------------------------------------------------
# Cycles-specific light properties
# ---------------------------------------------------------------------------

def apply_cycles_light_props(light_data,
                              light_type:   str,
                              use_mis:      bool = True,
                              max_bounces:  int  = 1024) -> None:
    """Apply Cycles-specific settings to a light data-block.

    Args:
        light_data:   bpy.types.Light
        light_type:   "AREA"|"SPOT"|"SUN"|"POINT"
        use_mis:      Multiple Importance Sampling (True = better quality)
        max_bounces:  Cycles light path bounce limit

    Cycles properties live at light_data.cycles.* (a CyclesLightSettings group).
    They are safe to set even when Cycles is not the active engine — Blender
    stores them regardless and uses them when Cycles is activated.
    """
    cyc = getattr(light_data, "cycles", None)
    if cyc is None:
        # Cycles not installed (unlikely, but safe guard)
        return

    _try_set(cyc, "use_multiple_importance", use_mis)
    _try_set(cyc, "max_bounces",             int(max_bounces))

    # AREA lights: in Blender 4.x the 'spread' property controls
    # how directional the light is (pi = 180° = fully diffuse softbox).
    if light_type == "AREA":
        if hasattr(light_data, "spread"):
            # Use full spread (pi) for soft, wrap-around light matching
            # LuxCore's default behaviour for area lights.
            _try_set(light_data, "spread", math.pi)


def apply_cycles_area_spread(light_data, spread_radians: float = math.pi) -> None:
    """Set the Cycles AREA light spread angle (Blender 4.x only)."""
    if hasattr(light_data, "spread"):
        _try_set(light_data, "spread", float(spread_radians))


# ---------------------------------------------------------------------------
# Cycles world / sky (for architecture presets with env_light)
# ---------------------------------------------------------------------------

def reset_cycles_world(scene,
                       color=(0.05, 0.05, 0.05),
                       strength: float = 0.0) -> None:
    """Restore a neutral Cycles world for presets without env_light.

    This prevents architecture/creative environment settings from leaking into
    portrait/product presets that are meant to rely on their light rig alone.
    """
    import bpy

    world = scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        scene.world = world

    world.use_nodes = True
    node_tree = world.node_tree
    if node_tree is None:
        return

    node_tree.nodes.clear()

    try:
        bg_node  = node_tree.nodes.new("ShaderNodeBackground")
        out_node = node_tree.nodes.new("ShaderNodeOutputWorld")

        bg_node.inputs["Color"].default_value    = (*[float(c) for c in color], 1.0)
        bg_node.inputs["Strength"].default_value = float(strength)
        node_tree.links.new(bg_node.outputs["Background"], out_node.inputs["Surface"])
    except Exception as exc:
        log.warning("[LSM-CYC] Could not reset neutral world: %s", exc)


def apply_cycles_sky(scene, env_cfg: dict) -> None:
    """Configure the Cycles sky/world when env_light is defined in a preset.

    Supports: sky2 (Nishita sky) and constant (flat ambient) modes.
    Falls back gracefully if the World node tree is not available.
    """
    import bpy

    world = scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        scene.world = world

    world.use_nodes = True
    node_tree = world.node_tree
    if node_tree is None:
        return

    # Clear existing nodes
    node_tree.nodes.clear()

    env_type = env_cfg.get("type", "sky2")
    gain     = float(env_cfg.get("gain", 0.01))

    if env_type == "sky2":
        # Nishita sky approximation
        turbidity = float(env_cfg.get("turbidity", 3.0))
        try:
            bg_node  = node_tree.nodes.new("ShaderNodeBackground")
            sky_node = node_tree.nodes.new("ShaderNodeTexSky")
            out_node = node_tree.nodes.new("ShaderNodeOutputWorld")

            sky_node.sky_type  = "NISHITA"
            sky_node.turbidity = min(10.0, max(1.0, turbidity))

            bg_node.inputs["Strength"].default_value = min(0.9, gain * 20.0)
            node_tree.links.new(sky_node.outputs["Color"],   bg_node.inputs["Color"])
            node_tree.links.new(bg_node.outputs["Background"], out_node.inputs["Surface"])
        except Exception as exc:
            log.warning("[LSM-CYC] Could not set Nishita sky: %s", exc)

    elif env_type == "constant":
        color = env_cfg.get("color", (0.05, 0.05, 0.05))
        try:
            bg_node  = node_tree.nodes.new("ShaderNodeBackground")
            out_node = node_tree.nodes.new("ShaderNodeOutputWorld")

            bg_node.inputs["Color"].default_value    = (*[float(c) for c in color], 1.0)
            bg_node.inputs["Strength"].default_value = min(0.5, gain * 80.0)
            node_tree.links.new(bg_node.outputs["Background"], out_node.inputs["Surface"])
        except Exception as exc:
            log.warning("[LSM-CYC] Could not set constant sky: %s", exc)


# ---------------------------------------------------------------------------
# Cycles render config (mirrors LuxCoreSceneProxy interface)
# ---------------------------------------------------------------------------

class CyclesSceneProxy:
    """Applies Cycles render settings from preset's luxcore_cfg block.

    The preset stores LuxCore terminology; this class translates it
    to Cycles equivalents so the same preset dict drives both engines.

    Mapping:
        path_depth   → cycles.max_bounces (total)
        halt_samples → cycles.samples
        denoiser     → cycles.use_denoiser (Blender 4.x)
        engine PATH  → cycles.progressive = 'PATH'
        engine BIDIR → cycles.progressive = 'PATH'  (BIDIR has no Cycles equiv)
    """

    def __init__(self, scene) -> None:
        self._scene  = scene
        self._cycles = getattr(scene, "cycles", None)
        self._rd     = scene.render

    @property
    def available(self) -> bool:
        return self._cycles is not None

    def apply_from_lxc_cfg(self, lxc_cfg: dict) -> None:
        """Translate LuxCore config dict to Cycles render settings."""
        if not self.available:
            return

        path_depth   = int(lxc_cfg.get("path_depth",   8))
        halt_samples = int(lxc_cfg.get("halt_samples", 256))
        denoiser     = bool(lxc_cfg.get("denoiser",    True))

        # Samples
        _try_set(self._cycles, "samples",     halt_samples)
        _try_set(self._cycles, "use_adaptive_sampling", True)

        # Bounces — Cycles splits total bounces into per-type max
        # We set a reasonable total and let the others be clamped automatically
        _try_set(self._cycles, "max_bounces",          path_depth)
        _try_set(self._cycles, "diffuse_bounces",      min(path_depth, 4))
        _try_set(self._cycles, "glossy_bounces",       min(path_depth, 4))
        _try_set(self._cycles, "transmission_bounces", min(path_depth, 8))
        _try_set(self._cycles, "volume_bounces",       min(path_depth, 2))

        # Denoiser (Blender 4.x: render.use_compositor_denoise or cycles.use_denoiser)
        if hasattr(self._cycles, "use_denoiser"):
            _try_set(self._cycles, "use_denoiser", denoiser)
        if denoiser:
            _try_set(self._cycles, "denoiser", "OPENIMAGEDENOISE")

        log.debug("[LSM-CYC] Applied Cycles config: samples=%d depth=%d denoiser=%s",
                  halt_samples, path_depth, denoiser)
