# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  difrkaguilar + Claude (Anthropic)
# LuxCore Stage Manager -- UI Panels (English only)

from __future__ import annotations
import logging

import bpy
from bpy.types import Panel, UIList, PropertyGroup
from bpy.props import (
    StringProperty, IntProperty, FloatProperty,
    BoolProperty, EnumProperty, CollectionProperty,
)

from .presets_data import PRESETS, CATEGORIES
from .constants import LSM_PREFIX, LUXCORE_ENGINE_ID, CYCLES_ENGINE_ID, CATEGORY_ICONS

# CAT_ICONS is no longer defined here — use CATEGORY_ICONS from constants directly.
CAT_ICONS = CATEGORY_ICONS   # thin alias kept for any future local references

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _filtered_presets(category):
    return PRESETS if category == "ALL" else [p for p in PRESETS if p["category"] == category]

def _repopulate_items(props):
    filtered = _filtered_presets(props.active_category)
    props.preset_items.clear()
    for p in filtered:
        item = props.preset_items.add()
        item.name      = p["name"]
        item.preset_id = p["id"]


def _apply_preference_defaults(props) -> None:
    """Populate scene properties from addon preferences when available."""
    try:
        prefs = bpy.context.preferences.addons["luxcore_stage_manager"].preferences
    except Exception:
        return

    props.intensity_multiplier   = float(getattr(prefs, "default_intensity", 1.0))
    props.clear_existing         = bool(getattr(prefs, "default_clear_existing", True))
    props.auto_configure_luxcore = bool(getattr(prefs, "default_auto_configure", True))

# ---------------------------------------------------------------------------
# Update callbacks
# ---------------------------------------------------------------------------

def _cb_category_changed(self, context):
    _repopulate_items(self)
    self.list_index = 0
    filtered = _filtered_presets(self.active_category)
    self["active_preset_id"] = filtered[0]["id"] if filtered else ""

def _cb_index_changed(self, context):
    filtered = _filtered_presets(self.active_category)
    idx = self.list_index
    if 0 <= idx < len(filtered):
        self["active_preset_id"] = filtered[idx]["id"]

# ---------------------------------------------------------------------------
# Property groups
# ---------------------------------------------------------------------------

class LSM_PresetListItem(PropertyGroup):
    preset_id: StringProperty(name="Preset ID", default="")

class LSM_SceneProperties(PropertyGroup):

    active_category: EnumProperty(
        name="Category",
        # Single source of truth: constants.CATEGORY_DEFS → presets_data.CATEGORIES.
        # Adding a new category only requires editing constants.py.
        items=list(CATEGORIES),
        default="ALL",
        update=_cb_category_changed,
    )

    list_index: IntProperty(
        name="Selected Index", default=0, min=0, update=_cb_index_changed)

    active_preset_id: StringProperty(name="Active Preset ID", default="")

    preset_items: CollectionProperty(type=LSM_PresetListItem)

    intensity_multiplier: FloatProperty(
        name="Intensity",
        description="Global energy multiplier applied to all lights in the preset",
        default=1.0, min=0.01, max=20.0, soft_min=0.1, soft_max=5.0,
        step=10, precision=2,
    )
    temperature_offset: FloatProperty(
        name="Temp Offset (K)",
        description="Kelvin offset added to every color temperature in the preset",
        default=0.0, min=-5000.0, max=5000.0, soft_min=-1500.0, soft_max=1500.0,
        step=100, precision=0,
    )
    clear_existing: BoolProperty(
        name="Clear Existing LSM Lights",
        description="Remove current LSM_ lights before applying the new preset",
        default=True,
    )
    auto_configure_luxcore: BoolProperty(
        name="Auto-configure Render Settings",
        description="Apply render settings from the preset (samples, depth, denoiser)",
        default=True,
    )
    show_preview: BoolProperty(
        name="Show Preview",
        description="Display a preview thumbnail for the selected preset",
        default=True,
    )

    # --- Scale reference ---
    scale_reference: bpy.props.EnumProperty(
        name="Scale Reference",
        description=(
            "How to determine the rig scale and orbit centre.\n"
            "Presets are calibrated for a ~1 m object (Suzanne scale)"
        ),
        items=[
            ("ACTIVE", "Active Object",
             "Use the active object's bounding box (longest axis + centre).\n"
             "Recommended: select your hero object before applying"),
            ("SCENE",  "All Visible",
             "Use the union bounding box of all visible mesh objects.\n"
             "Useful when no single object is selected"),
            ("MANUAL", "Manual",
             "Enter the reference diagonal manually (metres).\n"
             "Useful for non-mesh rigs or known real-world dimensions"),
        ],
        default="ACTIVE",
    )
    manual_scale: bpy.props.FloatProperty(
        name="Scene Scale (m)",
        description=(
            "Reference diagonal in metres used when Scale Reference = Manual.\n"
            "1.0 = Suzanne  |  4.5 = typical car  |  0.05 = ring/coin"
        ),
        default=1.0, min=0.001, max=1000.0, soft_min=0.01, soft_max=50.0,
        step=10, precision=3,
        unit="LENGTH",
    )

# ---------------------------------------------------------------------------
# UIList
# ---------------------------------------------------------------------------

class LSM_UL_PresetList(UIList):
    bl_idname = "LSM_UL_PresetList"

    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index):
        from .presets_data import PRESETS_BY_ID
        preset   = PRESETS_BY_ID.get(item.preset_id)
        cat_icon = CAT_ICONS.get(preset.get("category",""), "LIGHT") if preset else "LIGHT"
        row = layout.row(align=True)
        row.label(text="", icon=cat_icon)
        row.label(text=item.name)

    def filter_items(self, context, data, propname):
        return [], []

# ---------------------------------------------------------------------------
# Engine indicator helper
# ---------------------------------------------------------------------------

def _draw_engine_indicator(layout, context):
    engine = context.scene.render.engine
    prefs = None
    try:
        prefs = bpy.context.preferences.addons["luxcore_stage_manager"].preferences
    except Exception:
        pass

    if engine == LUXCORE_ENGINE_ID:
        row = layout.row(align=True)
        row.label(text="Engine: LuxCore", icon="SHADING_RENDERED")
    elif engine == CYCLES_ENGINE_ID:
        row = layout.row(align=True)
        row.label(text="Engine: Cycles", icon="SHADING_RENDERED")
    elif engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        row = layout.row(align=True)
        row.label(text="Engine: EEVEE (basic support)", icon="SHADING_SOLID")
    else:
        box = layout.box()
        box.label(text="Engine: " + engine, icon="ERROR")
        box.label(text="Use LuxCore or Cycles for best results.")

    if (
        prefs is not None and
        getattr(prefs, "show_luxcore_warning", True) and
        engine != LUXCORE_ENGINE_ID
    ):
        box = layout.box()
        box.label(text="LuxCore is not the active render engine.", icon="INFO")
        box.label(text="Presets still work, but LuxCore-only settings are skipped.")
    layout.separator(factor=0.3)

# ---------------------------------------------------------------------------
# Panels
# ---------------------------------------------------------------------------

class LSM_PT_Main(Panel):
    bl_label       = "Light Stage Manager"
    bl_idname      = "LSM_PT_Main"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "LightStageManager"
    bl_order       = 0

    def draw_header(self, context):
        self.layout.label(text="", icon="OUTLINER_OB_LIGHT")

    def draw(self, context):
        try:
            self._draw_safe(context)
        except Exception as exc:
            log.error("LSM_PT_Main.draw: %s", exc)
            self.layout.label(text="UI error — see console", icon="ERROR")

    def _draw_safe(self, context):
        layout = self.layout
        props  = context.scene.lsm_props

        _draw_engine_indicator(layout, context)

        # Category filter
        layout.label(text="Category:", icon="FILTER")
        row = layout.row(align=True)
        row.scale_y = 1.1
        for cat_id, cat_label, _desc, cat_icon, _order in CATEGORIES:
            op = row.operator(
                "lsm.set_category",
                text="" if cat_id == "ALL" else cat_label,
                icon=cat_icon if cat_id == "ALL" else "NONE",
                depress=(props.active_category == cat_id),
            )
            op.category = cat_id

        layout.separator(factor=0.3)

        # Preset list (read-only draw)
        layout.template_list(
            "LSM_UL_PresetList", "",
            props, "preset_items",
            props, "list_index",
            rows=6, maxrows=10,
        )

        # Preview thumbnail
        if props.show_preview and props.active_preset_id:
            try:
                from .previews import get_icon_id
                icon_id = get_icon_id(props.active_preset_id)
                if icon_id:
                    prev_box = layout.box()
                    prev_box.template_icon(icon_value=icon_id, scale=9.0)
                else:
                    row = layout.row()
                    row.alignment = "CENTER"
                    row.label(text="Preview loading...", icon="TIME")
            except Exception as exc:
                log.debug("Preview draw failed: %s", exc)

        # Apply button — label reflects active engine
        layout.separator(factor=0.2)
        engine = context.scene.render.engine
        btn_labels = {
            LUXCORE_ENGINE_ID:     "Apply Preset  [LuxCore]",
            CYCLES_ENGINE_ID:      "Apply Preset  [Cycles]",
            "BLENDER_EEVEE_NEXT":  "Apply Preset  [EEVEE]",
            "BLENDER_EEVEE":       "Apply Preset  [EEVEE]",
        }
        btn_text = btn_labels.get(engine, "Apply Preset")
        row = layout.row(align=True)
        row.scale_y = 1.6
        op = row.operator("lsm.apply_preset", text=btn_text, icon="LIGHT")
        op.preset_id = props.active_preset_id or ""


class LSM_PT_PresetInfo(Panel):
    bl_label       = "Preset Info"
    bl_idname      = "LSM_PT_PresetInfo"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "LightStageManager"
    bl_parent_id   = "LSM_PT_Main"
    bl_options     = {"DEFAULT_CLOSED"}
    bl_order       = 1

    def draw(self, context):
        try:
            self._draw_safe(context)
        except Exception as exc:
            log.error("LSM_PT_PresetInfo.draw: %s", exc)

    def _draw_safe(self, context):
        layout = self.layout
        props  = context.scene.lsm_props
        from .presets_data import PRESETS_BY_ID
        preset = PRESETS_BY_ID.get(props.active_preset_id)
        if preset is None:
            layout.label(text="(Nothing selected)", icon="INFO")
            return

        box = layout.box()
        col = box.column(align=True)
        cat_icon = CAT_ICONS.get(preset.get("category",""), "LIGHT")
        col.label(text=preset.get("name",""), icon=cat_icon)
        col.separator(factor=0.3)

        desc = preset.get("description", "")
        line, max_w = "", 36
        for word in desc.split():
            if len(line) + len(word) + 1 > max_w:
                col.label(text=line)
                line = word
            else:
                line = (line + " " + word).strip()
        if line:
            col.label(text=line)

        col.separator(factor=0.3)
        lights = preset.get("lights", [])
        col.label(text="%d light%s" % (len(lights),"s" if len(lights)!=1 else ""),
                  icon="LIGHT")
        lxc = preset.get("luxcore_cfg", {})
        if lxc:
            col.label(text="Engine: %s  Depth: %d  Halt: %d spp" % (
                lxc.get("engine","PATH"),
                lxc.get("path_depth",8),
                lxc.get("halt_samples",256),
            ))
        env = preset.get("env_light")
        if env:
            col.label(text="Env: %s  gain=%.4f" % (
                env.get("type","?"), env.get("gain",0.0)))

        col.separator(factor=0.3)
        col.label(text="Compatible: LuxCore \u2713  Cycles \u2713  EEVEE \u2713",
                  icon="CHECKMARK")
        col.separator(factor=0.3)
        col.prop(props, "show_preview")


class LSM_PT_LightModifiers(Panel):
    bl_label       = "Light Modifiers"
    bl_idname      = "LSM_PT_LightModifiers"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "LightStageManager"
    bl_parent_id   = "LSM_PT_Main"
    bl_options     = {"DEFAULT_CLOSED"}
    bl_order       = 2

    def draw(self, context):
        try:
            from .operators import _compute_scale_and_origin
            layout = self.layout
            props  = context.scene.lsm_props

            # ---- Intensity & temperature ------------------------------------
            col = layout.column(align=True)
            col.label(text="Lighting Adjustments:", icon="LIGHT")
            col.prop(props, "intensity_multiplier", slider=True)
            col.prop(props, "temperature_offset",   slider=True)
            col.separator(factor=0.3)
            col.operator("lsm.reset_modifiers",
                         text="Reset to Defaults", icon="LOOP_BACK")

            layout.separator(factor=0.5)

            # ---- Scale reference -------------------------------------------
            box = layout.box()
            box.label(text="Scale & Target Reference:", icon="OBJECT_DATA")

            col2 = box.column(align=True)
            col2.prop(props, "scale_reference", text="")
            if props.scale_reference == "MANUAL":
                col2.prop(props, "manual_scale")

            # Live feedback: show what scale/origin will be used
            try:
                scale, origin = _compute_scale_and_origin(context)
                info_col = box.column(align=True)
                info_col.scale_y = 0.85
                info_col.label(
                    text="Scale: %.3f m  |  Origin: (%.1f, %.1f, %.1f)" % (
                        scale, origin.x, origin.y, origin.z),
                    icon="INFO")

                # Visual hint about energy scaling
                if abs(scale - 1.0) > 0.05:
                    energy_factor = scale ** 2
                    info_col.label(
                        text="Energy ×%.1f  |  Sizes ×%.2f" % (
                            energy_factor * props.intensity_multiplier, scale),
                        icon="DRIVER_TRANSFORM")
            except Exception:
                pass   # context not ready yet (e.g. during registration)

            layout.separator(factor=0.4)

            # ---- Apply options ---------------------------------------------
            col3 = layout.column(align=True)
            col3.label(text="Apply Options:")
            col3.prop(props, "clear_existing")
            col3.prop(props, "auto_configure_luxcore")

        except Exception as exc:
            log.error("LSM_PT_LightModifiers.draw: %s", exc)


class LSM_PT_SceneTools(Panel):
    bl_label       = "Scene Tools"
    bl_idname      = "LSM_PT_SceneTools"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "LightStageManager"
    bl_parent_id   = "LSM_PT_Main"
    bl_options     = {"DEFAULT_CLOSED"}
    bl_order       = 3

    def draw(self, context):
        try:
            layout = self.layout
            n = sum(1 for o in context.scene.objects
                    if o.name.startswith(LSM_PREFIX))
            if n > 0:
                box = layout.box()
                box.label(
                    text="%d LSM light%s in scene" % (n,"s" if n!=1 else ""),
                    icon="OUTLINER_OB_LIGHT")
                col = box.column(align=True)
                col.operator("lsm.select_lights", text="Select All",
                             icon="RESTRICT_SELECT_OFF")
                col.operator("lsm.remove_lights",  text="Remove All",
                             icon="TRASH")
                col.separator()
                col.operator("lsm.verify_active_preset",
                             text="Verify Active Preset", icon="CHECKMARK")
                col.operator("lsm.diagnose_lights",
                             text="Diagnose (Console)", icon="INFO")
            else:
                layout.label(text="No LSM lights in scene.", icon="INFO")
        except Exception as exc:
            log.error("LSM_PT_SceneTools.draw: %s", exc)


class LSM_PT_Previews(Panel):
    bl_label       = "Preview Thumbnails"
    bl_idname      = "LSM_PT_Previews"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "LightStageManager"
    bl_parent_id   = "LSM_PT_Main"
    bl_options     = {"DEFAULT_CLOSED"}
    bl_order       = 4

    def draw(self, context):
        try:
            self._draw_safe(context)
        except Exception as exc:
            log.error("LSM_PT_Previews.draw: %s", exc)

    def _draw_safe(self, context):
        import os
        from .previews import _previews_dir
        layout = self.layout
        pdir   = _previews_dir()

        existing = sum(
            1 for p in PRESETS
            if os.path.exists(os.path.join(pdir, p["id"] + ".png"))
        )
        total = len(PRESETS)

        col = layout.column(align=True)

        if existing == total:
            col.label(text="%d / %d rendered PNGs ready" % (existing, total),
                      icon="CHECKMARK")
        elif existing > 0:
            col.label(text="%d / %d PNGs rendered" % (existing, total),
                      icon="TIME")
        else:
            col.label(text="No rendered previews yet.", icon="INFO")
            col.label(text="Using diagram fallbacks.")

        col.separator()
        col.label(text="Render once after installation:", icon="RENDER_STILL")
        col.label(text="Blender renders Suzanne under each preset.")
        col.label(text="Runs headless in background (~3-8 min).")
        col.separator()

        row = col.row(align=True)
        op  = row.operator("lsm.render_previews",
                            text="Render All Previews", icon="RENDER_STILL")
        op.force_re_render = False

        row2 = col.row(align=True)
        op2  = row2.operator("lsm.render_previews",
                              text="Force Re-render", icon="FILE_REFRESH")
        op2.force_re_render = True


class LSM_PT_RenderProperties(Panel):
    bl_label       = "Light Stage Manager"
    bl_idname      = "LSM_PT_RenderProperties"
    bl_space_type  = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context     = "render"
    bl_options     = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(text="", icon="OUTLINER_OB_LIGHT")

    def draw(self, context):
        try:
            layout = self.layout
            props  = context.scene.lsm_props
            _draw_engine_indicator(layout, context)
            layout.label(text="Open N-panel > LightStageManager tab")
            layout.separator()
            layout.prop(props, "auto_configure_luxcore")
            layout.prop(props, "clear_existing")
        except Exception as exc:
            log.error("LSM_PT_RenderProperties.draw: %s", exc)


# ---------------------------------------------------------------------------
# App handlers & deferred init
# ---------------------------------------------------------------------------

def _on_load_post(filepath=""):
    try:
        for scene in bpy.data.scenes:
            if hasattr(scene, "lsm_props"):
                _apply_preference_defaults(scene.lsm_props)
                _repopulate_items(scene.lsm_props)
    except Exception as exc:
        log.warning("LSM load_post: %s", exc)


def _deferred_init():
    """Runs once via timer — bpy.data is fully accessible here."""
    try:
        for scene in bpy.data.scenes:
            if hasattr(scene, "lsm_props"):
                _apply_preference_defaults(scene.lsm_props)
                _repopulate_items(scene.lsm_props)
    except Exception as exc:
        log.warning("LSM deferred_init (scenes): %s", exc)

    try:
        from .previews import init_previews
        from .presets_data import PRESETS as ALL_PRESETS
        init_previews(ALL_PRESETS)
    except Exception as exc:
        log.warning("LSM deferred_init (previews): %s", exc)

    return None   # one-shot


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

PROPERTY_GROUPS = (LSM_PresetListItem, LSM_SceneProperties)
UILISTS         = (LSM_UL_PresetList,)
PANELS          = (
    LSM_PT_Main,
    LSM_PT_PresetInfo,
    LSM_PT_LightModifiers,
    LSM_PT_SceneTools,
    LSM_PT_Previews,
    LSM_PT_RenderProperties,
)


def register():
    for cls in PROPERTY_GROUPS:
        bpy.utils.register_class(cls)
    for cls in UILISTS:
        bpy.utils.register_class(cls)
    for cls in PANELS:
        bpy.utils.register_class(cls)

    bpy.types.Scene.lsm_props = bpy.props.PointerProperty(type=LSM_SceneProperties)

    if _on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load_post)

    bpy.app.timers.register(_deferred_init, first_interval=0.0)


def unregister():
    if _on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post)
    if bpy.app.timers.is_registered(_deferred_init):
        bpy.app.timers.unregister(_deferred_init)

    try:
        from .previews import free_previews
        free_previews()
    except Exception:
        pass

    if hasattr(bpy.types.Scene, "lsm_props"):
        del bpy.types.Scene.lsm_props

    for cls in reversed(PANELS):
        bpy.utils.unregister_class(cls)
    for cls in reversed(UILISTS):
        bpy.utils.unregister_class(cls)
    for cls in reversed(PROPERTY_GROUPS):
        bpy.utils.unregister_class(cls)
