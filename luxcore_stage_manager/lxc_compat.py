# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  difrkaguilar + Claude (Anthropic)
# LuxCore Stage Manager -- LuxCore API Compatibility Layer
# Verified against BlendLuxCore 2.10.x property structure.

from __future__ import annotations
import logging
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Version / availability detection
# ---------------------------------------------------------------------------

def get_luxcore_version():
    """Return BlendLuxCore version tuple, or None if not installed."""
    try:
        import BlendLuxCore  # type: ignore
        return tuple(BlendLuxCore.bl_info.get("version", ()))
    except ImportError:
        pass
    try:
        import bpy
        if bpy.context and "BlendLuxCore" in bpy.context.preferences.addons:
            return ()
    except Exception:
        pass
    return None


def is_available() -> bool:
    return get_luxcore_version() is not None


def is_active_engine(scene) -> bool:
    from .constants import LUXCORE_ENGINE_ID
    return scene.render.engine == LUXCORE_ENGINE_ID


# ---------------------------------------------------------------------------
# Core safe-setter — catches ALL Blender exceptions including RuntimeError
# ---------------------------------------------------------------------------

def _try_set(obj, attr: str, value) -> bool:
    """Set obj.attr = value. Catches every possible Blender exception.

    Blender raises RuntimeError (not TypeError) when an enum value is not
    found in the items list, or when a property is set in a restricted
    context. This was the silent failure in previous versions.
    """
    if obj is None:
        return False
    try:
        setattr(obj, attr, value)
        return True
    except Exception as exc:   # <-- catch ALL, not just (Attribute|Type|Value)Error
        log.debug("[LSM] _try_set %s.%s=%r failed: %s", type(obj).__name__, attr, repr(value), exc)
        return False


def _try_get(obj, attr: str, default=None):
    if obj is None:
        return default
    try:
        return getattr(obj, attr, default)
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Apply LuxCore properties to a light data-block
# Called AFTER the object is linked to the scene (avoids Blender 4.5 restriction)
# ---------------------------------------------------------------------------

def apply_lxc_light_props(light_data,
                           light_type:   str,
                           lxc_gain:     float,
                           kelvin:       int | None,
                           light_unit:   str = "artistic") -> None:
    """Apply all BlendLuxCore properties to a light data-block.

    Must be called AFTER bpy.data.objects.new() and collection.objects.link()
    so that the light data-block is fully registered in the scene graph.

    Property paths (BlendLuxCore 2.10.x):
        light.luxcore.light_unit        EnumProperty: "artistic"|"power"|"flux"|"candela"
        light.luxcore.gain              FloatProperty
        light.luxcore.color_mode        EnumProperty: "color"|"temperature"
        light.luxcore.temperature       FloatProperty (Kelvin, UI/export path)
    """
    lx = getattr(light_data, "luxcore", None)
    if lx is None:
        print("[LSM] WARNING: light.luxcore is None for %r — BlendLuxCore not active?" % light_data.name)
        return

    # Force LuxCore-native settings path so BlendLuxCore does not fall back to
    # its Cycles compatibility mode for newly created lights.
    _try_set(lx, "use_cycles_settings", False)

    # ---- 1. Unit: artistic (gain-based) ------------------------------------
    if _try_set(lx, "light_unit", light_unit):
        pass  # ok
    # Fallback: some BLC versions use 'unit' not 'light_unit'
    elif hasattr(lx, "unit"):
        _try_set(lx, "unit", light_unit)

    # ---- 2. Gain -----------------------------------------------------------
    ok_gain = _try_set(lx, "gain", float(lxc_gain))
    print("[LSM]   gain=%s -> %s" % (
        "%.4f" % lxc_gain,
        "OK (%.4f)" % _try_get(lx, "gain", -1) if ok_gain else "FAILED"
    ))

    # ---- 3. Color temperature ----------------------------------------------
    if kelvin is not None:
        from .constants import KELVIN_MIN, KELVIN_LXC_MAX
        k = int(max(KELVIN_MIN, min(KELVIN_LXC_MAX, float(kelvin))))

        # Start by clearing any RGB tint and writing the Kelvin value, then
        # re-apply mode and temperature again after compatibility aliases.
        _try_set(lx, "rgb_gain", (1.0, 1.0, 1.0))
        ok_temp = _try_set(lx, "temperature", float(k))
        ok_mode = _try_set(lx, "color_mode", "temperature")

        # Compatibility aliases seen across older addon generations.
        # Keep these in sync when present so UI, export, and diagnostics agree.
        _try_set(lx, "color_temperature", k)
        _try_set(lx, "use_color_temperature", True)

        # BLC < 2.9 fallback: use_color_temperature (bool)
        if not ok_mode:
            _try_set(lx, "use_color_temperature", True)
        if not ok_temp:
            _try_set(lx, "temperature", float(k))

        # Re-assert the modern values last in case any alias write or internal
        # update callback reset them to defaults.
        _try_set(lx, "color_mode", "temperature")
        _try_set(lx, "temperature", float(k))

        # Verify
        actual_mode = _try_get(lx, "color_mode", "?")
        actual_k    = _try_get(lx, "temperature", _try_get(lx, "color_temperature", "?"))
        print("[LSM]   color_mode=%r K=%s -> mode=%r K_actual=%s use_cycles=%s" % (
            "temperature", k, actual_mode, actual_k,
            _try_get(lx, "use_cycles_settings", "N/A")))
    else:
        # RGB color mode
        _try_set(lx, "rgb_gain", tuple(float(c) for c in light_data.color[:3]))
        ok = _try_set(lx, "color_mode", "color")
        if not ok:
            _try_set(lx, "use_color_temperature", False)
        else:
            _try_set(lx, "use_color_temperature", False)
        print("[LSM]   color_mode=color (RGB) use_cycles=%s" % (
            _try_get(lx, "use_cycles_settings", "N/A")))


def apply_lxc_object_visibility(obj, visible_to_camera: bool = False) -> None:
    """Set LuxCore object visibility flags.

    BlendLuxCore 2.10 object visibility path:
        obj.luxcore.visibility.camera   (BoolProperty, default=True)
    We set camera=False so light objects don't appear in the render image.
    """
    lx_obj = getattr(obj, "luxcore", None)
    if lx_obj is None:
        return

    # Try nested visibility group (BLC 2.9+)
    vis = getattr(lx_obj, "visibility", None)
    if vis is not None:
        _try_set(vis, "camera",     visible_to_camera)
        _try_set(vis, "indirect",   True)
        _try_set(vis, "shadowcatcher", False)
    else:
        # Older BLC flat layout
        _try_set(lx_obj, "visible_to_camera", visible_to_camera)


# ---------------------------------------------------------------------------
# Scene / World proxies (unchanged, they work correctly)
# ---------------------------------------------------------------------------

class LuxCoreSceneProxy:
    def __init__(self, scene) -> None:
        self._scene = scene
        self._lx    = getattr(scene, "luxcore", None)

    @property
    def available(self) -> bool:
        return self._lx is not None and is_active_engine(self._scene)

    def set_engine(self, engine: str) -> bool:
        from .constants import VALID_LXC_ENGINES
        if engine not in VALID_LXC_ENGINES:
            return False
        cfg = getattr(self._lx, "config", None)
        return _try_set(cfg, "engine", engine) if cfg else False

    def set_path_depth(self, depth: int) -> bool:
        cfg  = getattr(self._lx, "config", None)
        path = getattr(cfg,  "path",   None) if cfg  else None
        return _try_set(path, "depth", int(depth)) if path else False

    def set_halt_samples(self, samples: int) -> bool:
        cfg  = getattr(self._lx, "config", None)
        halt = getattr(cfg,  "halt",   None) if cfg  else None
        if halt is None:
            return False
        _try_set(halt, "enable",  True)
        return _try_set(halt, "samples", int(samples))

    def set_denoiser(self, enabled: bool) -> bool:
        dn = getattr(self._lx, "denoiser", None)
        return _try_set(dn, "enabled", bool(enabled)) if dn else False


class LuxCoreWorldProxy:
    def __init__(self, scene) -> None:
        self._scene = scene
        self._world = self._ensure_world()
        self._lx    = getattr(self._world, "luxcore", None) if self._world else None

    @property
    def available(self) -> bool:
        return self._lx is not None

    def _ensure_world(self):
        import bpy
        if self._scene.world is not None:
            return self._scene.world
        try:
            w = bpy.data.worlds.new("World")
            self._scene.world = w
            return w
        except Exception as exc:
            log.error("Could not create World: %s", exc)
            return None

    def configure_sky2(self, turbidity: float = 3.0, gain: float = 0.01) -> bool:
        ok1 = _try_set(self._lx, "light",        "SKY2")
        ok2 = _try_set(self._lx, "sun_sky_gain", float(gain))
        ok3 = _try_set(self._lx, "turbidity",    float(turbidity))
        return any((ok1, ok2, ok3))

    def configure_constant(self, color=(0.05, 0.05, 0.05), gain: float = 0.001) -> bool:
        ok1 = _try_set(self._lx, "light", "CONSTANT")
        ok2 = _try_set(self._lx, "color", tuple(float(c) for c in color))
        ok3 = _try_set(self._lx, "gain",  float(gain))
        return any((ok1, ok2, ok3))

    def configure_hdri(self, filepath: str, gain: float = 1.0,
                       rotation: float = 0.0, gamma: float = 1.0) -> bool:
        """Configure LuxCore INFINITE environment light from an image file.

        Args:
            filepath: Absolute path to the .hdr or .exr file.
            gain:     Overall brightness multiplier.
            rotation: Y-axis rotation in radians.
            gamma:    Image gamma (1.0 = linear, which .exr files already are).
        """
        import bpy

        if not filepath:
            log.warning("[LSM-LXC] configure_hdri: empty filepath")
            return False

        try:
            img = bpy.data.images.load(filepath, check_existing=True)
        except Exception as exc:
            log.error("[LSM-LXC] configure_hdri: could not load %r: %s", filepath, exc)
            return False

        ok1 = _try_set(self._lx, "light",    "INFINITE")
        ok2 = _try_set(self._lx, "image",    img)
        ok3 = _try_set(self._lx, "gain",     float(gain))
        ok4 = _try_set(self._lx, "rotation", float(rotation))
        ok5 = _try_set(self._lx, "gamma",    float(gamma))
        return any((ok1, ok2, ok3, ok4, ok5))
