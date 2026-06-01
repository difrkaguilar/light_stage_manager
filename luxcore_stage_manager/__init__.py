# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  difrkaguilar + Claude (Anthropic)
# Light Stage Manager -- Entry point

bl_info = {
    "name":        "Light Stage Manager",
    "author":      "difrkaguilar + Claude",
    "version":     (3, 5, 0),
    "blender":     (4, 1, 0),
    "location":    "3D Viewport > N-panel > LightStageManager  |  Asset Browser",
    "description": "34 cinematic lighting presets for LuxCore, Cycles and EEVEE. Asset Browser ready.",
    "warning":     "Full LuxCore support requires BlendLuxCore 2.10.1+",
    "doc_url":     "",
    "tracker_url": "",
    "category":    "Lighting",
}
# Note: blender_manifest.toml provides richer metadata for the
# Blender Extensions Platform (Blender 4.2+). bl_info is kept for
# backwards compatibility with Blender 4.1 and older addon installers.

import logging
import bpy

log = logging.getLogger(__name__)
_modules_loaded = False


# ---------------------------------------------------------------------------
# LuxCore per-light energy sync
# Fires when any Light data changes (e.g. per-light energy slider in Scene
# Lights panel), keeping lx.gain in sync with ld.energy for LSM lights.
# ---------------------------------------------------------------------------

@bpy.app.handlers.persistent
def _lsm_lxc_energy_sync(scene, depsgraph):
    """Sync LuxCore gain/color for LSM lights when energy or color changes directly."""
    if not scene or scene.render.engine != "LUXCORE":
        return
    if not any(isinstance(upd.id, bpy.types.Light) for upd in depsgraph.updates):
        return
    try:
        from .constants import (LSM_PREFIX,
                                LXC_AREA_GAIN_SCALE, LXC_SPOT_GAIN_SCALE,
                                LXC_POINT_GAIN_SCALE, LXC_SUN_GAIN_SCALE)
        from .lxc_compat import _try_set
        _gs = {"AREA":  LXC_AREA_GAIN_SCALE, "SPOT":  LXC_SPOT_GAIN_SCALE,
               "SUN":   LXC_SUN_GAIN_SCALE,  "POINT": LXC_POINT_GAIN_SCALE}
        for obj in scene.objects:
            if not (obj.name.startswith(LSM_PREFIX) and obj.type == "LIGHT"):
                continue
            ld = obj.data
            lx = getattr(ld, "luxcore", None)
            if lx is None:
                continue
            gs = _gs.get(ld.type, LXC_AREA_GAIN_SCALE)
            _try_set(lx, "gain", ld.energy * gs * float(obj.get("lsm_luxcore_gain", 1.0)))
            # RGB-sourced lights: sync color swatch → lx.rgb_gain
            if float(obj.get("lsm_kelvin", -1.0)) <= 0:
                _try_set(lx, "rgb_gain", tuple(float(c) for c in ld.color[:3]))
    except Exception as exc:
        log.debug("[LSM] LXC energy sync: %s", exc)


def _deferred_migrations():
    """Deferred: bpy.context.preferences accessible via timer (not during register)."""
    import bpy
    try:
        entry = bpy.context.preferences.addons.get("luxcore_stage_manager")
        if entry is not None:
            from .preferences import run_migrations
            run_migrations(entry.preferences)
    except Exception as exc:
        log.error("[LSM] Deferred migration failed: %s", exc)
    return None   # one-shot


def register():
    global _modules_loaded
    from . import preferences, operators, panels
    from .preferences import LSM_AddonPreferences
    from .overlay import register_overlay

    bpy.utils.register_class(LSM_AddonPreferences)
    operators.register()
    panels.register()
    register_overlay()

    bpy.app.timers.register(_deferred_migrations, first_interval=0.0)

    if _lsm_lxc_energy_sync not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_lsm_lxc_energy_sync)

    _modules_loaded = True
    print("[Light Stage Manager] v3.5.0 registered"
          " — 34 presets, LuxCore + Cycles, 20 gels, Blender 4.1+, Asset Browser ready")


def unregister():
    global _modules_loaded
    if not _modules_loaded:
        return
    from . import operators, panels
    from .preferences import LSM_AddonPreferences
    from .overlay import unregister_overlay

    if bpy.app.timers.is_registered(_deferred_migrations):
        bpy.app.timers.unregister(_deferred_migrations)

    if _lsm_lxc_energy_sync in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_lsm_lxc_energy_sync)

    unregister_overlay()
    panels.unregister()
    operators.unregister()
    bpy.utils.unregister_class(LSM_AddonPreferences)

    _modules_loaded = False
    print("[Light Stage Manager] v3.5.0 unregistered.")


if __name__ == "__main__":
    register()
