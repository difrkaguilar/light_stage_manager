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
log = logging.getLogger(__name__)
_modules_loaded = False


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
    import bpy
    from . import preferences, operators, panels
    from .preferences import LSM_AddonPreferences
    from .overlay import register_overlay

    bpy.utils.register_class(LSM_AddonPreferences)
    operators.register()
    panels.register()
    register_overlay()

    bpy.app.timers.register(_deferred_migrations, first_interval=0.0)

    _modules_loaded = True
    print("[Light Stage Manager] v3.5.0 registered"
          " — 34 presets, LuxCore + Cycles, 20 gels, Blender 4.1+, Asset Browser ready")


def unregister():
    global _modules_loaded
    if not _modules_loaded:
        return
    import bpy
    from . import operators, panels
    from .preferences import LSM_AddonPreferences
    from .overlay import unregister_overlay

    if bpy.app.timers.is_registered(_deferred_migrations):
        bpy.app.timers.unregister(_deferred_migrations)

    unregister_overlay()
    panels.unregister()
    operators.unregister()
    bpy.utils.unregister_class(LSM_AddonPreferences)

    _modules_loaded = False
    print("[Light Stage Manager] v3.5.0 unregistered.")


if __name__ == "__main__":
    register()
