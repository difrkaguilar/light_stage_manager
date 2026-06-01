# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  difrkaguilar + Claude (Anthropic)
# LuxCore Stage Manager -- Addon Preferences & Migration System

from __future__ import annotations
import logging
import bpy
from bpy.types import AddonPreferences
from bpy.props import IntProperty, FloatProperty, BoolProperty
from .constants import ADDON_ID, ADDON_DATA_VERSION

log = logging.getLogger(__name__)


def _get_addon_id() -> str:
    """Return the correct AddonPreferences bl_idname for this installation.

    - Legacy install (Edit > Preferences > Add-ons > Install):
        __package__ == "luxcore_stage_manager"  →  bl_idname = "light_stage_manager"
    - Extension install (Extensions browser):
        __package__ == "bl_ext.user_default.light_stage_manager"
        →  bl_idname = "bl_ext.user_default.light_stage_manager"

    Using __package__ from the package root is the only reliable cross-version approach.
    """
    pkg = __package__ or ""
    if pkg.startswith("bl_ext."):
        return pkg          # e.g. "bl_ext.user_default.light_stage_manager"
    return ADDON_ID         # legacy: "light_stage_manager"

def _migrate_v0_to_v1(prefs):
    log.info("[LSM] Migration v0->v1: baseline OK.")

MIGRATIONS = {0: _migrate_v0_to_v1}

def run_migrations(prefs):
    current = prefs.data_version
    while current < ADDON_DATA_VERSION:
        fn = MIGRATIONS.get(current)
        if fn is None:
            log.warning("[LSM] No migration v%d->v%d; skipping.", current, current + 1)
        else:
            try:
                fn(prefs)
            except Exception as exc:
                log.error("[LSM] Migration v%d failed: %s", current, exc)
                break
        current += 1
    if prefs.data_version != current:
        prefs.data_version = current


class LSM_AddonPreferences(AddonPreferences):
    """Persistent per-user preferences for Light Stage Manager."""
    bl_idname = _get_addon_id()

    data_version: IntProperty(name="Internal Data Version", default=0, min=0)

    default_intensity: FloatProperty(
        name="Default Intensity",
        description="Starting intensity multiplier when applying a preset",
        default=1.0, min=0.01, max=20.0, soft_min=0.1, soft_max=5.0,
    )
    default_clear_existing: BoolProperty(
        name="Clear Existing LSM Lights by Default", default=True,
    )
    default_auto_configure: BoolProperty(
        name="Auto-configure LuxCore by Default", default=True,
    )
    show_luxcore_warning: BoolProperty(
        name="Show Warning When LuxCore Is Not Active",
        description="Display a notice in the panel when LuxCore is not the active render engine",
        default=True,
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="Default values for new scenes:", icon="PREFERENCES")
        col = layout.column(align=True)
        col.prop(self, "default_intensity")
        col.prop(self, "default_clear_existing")
        col.prop(self, "default_auto_configure")
        layout.separator()
        layout.prop(self, "show_luxcore_warning")

        # ---- Asset Browser section -----------------------------------------
        layout.separator()
        asset_box = layout.box()
        asset_box.label(text="Asset Browser Integration:", icon="ASSET_MANAGER")

        from .asset_builder import asset_library_exists, assets_blend_path
        import os

        if asset_library_exists():
            asset_box.label(
                text="Library: %s" % assets_blend_path(),
                icon="CHECKMARK")
            row = asset_box.row(align=True)
            row.operator("lsm.generate_asset_library",
                         text="Regenerate", icon="FILE_REFRESH")
        else:
            asset_box.label(
                text="Library not generated yet.", icon="ERROR")
            row = asset_box.row(align=True)
            row.scale_y = 1.4
            row.operator("lsm.generate_asset_library",
                         text="Generate Asset Library", icon="ASSET_MANAGER")

        # Setup instructions
        guide = asset_box.column(align=True)
        guide.scale_y = 0.85
        guide.separator(factor=0.5)
        guide.label(text="One-time setup after generating:", icon="INFO")
        lib_path = os.path.dirname(assets_blend_path())
        guide.label(text="  Edit > Preferences > File Paths > Asset Libraries")
        guide.label(text="  Add (+) → Name: Light Stage Manager")
        guide.label(text="  Path: %s" % lib_path)
        guide.label(text="  Import method: Don't Import")

        layout.separator()
        box = layout.box()
        box.label(text="Diagnostic:", icon="INFO")
        try:
            from .lxc_compat import get_luxcore_version
            ver = get_luxcore_version()
            if ver is None:
                box.label(text="BlendLuxCore: NOT detected", icon="ERROR")
            elif ver:
                box.label(text="BlendLuxCore: v%s" % ".".join(str(v) for v in ver),
                          icon="CHECKMARK")
            else:
                box.label(text="BlendLuxCore: detected (version unknown)", icon="INFO")
        except Exception:
            box.label(text="BlendLuxCore: status unknown", icon="QUESTION")
        box.label(text="Data version: %d / %d" % (self.data_version, ADDON_DATA_VERSION))
        box.separator()
        box.label(text="Supported engines:", icon="SHADING_RENDERED")
        box.label(text="  ✓ LuxCore (BlendLuxCore 2.10.1+)")
        box.label(text="  ✓ Cycles (Blender 4.4+)")
        box.label(text="  ✓ EEVEE (basic support)")
