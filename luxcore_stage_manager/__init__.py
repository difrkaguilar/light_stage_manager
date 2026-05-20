# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  difrkaguilar + Claude (Anthropic)
# Light Stage Manager -- Entry point

bl_info = {
    "name":        "Light Stage Manager",
    "author":      "difrkaguilar + Claude",
    "version":     (3, 1, 0),
    "blender":     (4, 4, 0),
    "location":    "3D Viewport > N-panel > LightStageManager",
    "description": "25 professional lighting presets for LuxCore and Cycles renderers",
    "warning":     "Full LuxCore support requires BlendLuxCore 2.10.1+",
    "doc_url":     "",
    "tracker_url": "",
    "category":    "Lighting",
}

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

    bpy.utils.register_class(LSM_AddonPreferences)
    operators.register()
    panels.register()

    bpy.app.timers.register(_deferred_migrations, first_interval=0.0)

    _modules_loaded = True
    print("[Light Stage Manager] v3.1.0 registered"
          " — 25 presets, LuxCore + Cycles, Blender 4.4+")


def unregister():
    global _modules_loaded
    if not _modules_loaded:
        return
    import bpy
    from . import operators, panels
    from .preferences import LSM_AddonPreferences

    if bpy.app.timers.is_registered(_deferred_migrations):
        bpy.app.timers.unregister(_deferred_migrations)

    panels.unregister()
    operators.unregister()
    bpy.utils.unregister_class(LSM_AddonPreferences)

    _modules_loaded = False
    print("[Light Stage Manager] v3.1.0 unregistered.")


if __name__ == "__main__":
    register()
