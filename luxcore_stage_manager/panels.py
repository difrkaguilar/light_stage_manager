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
from .constants import (
    LSM_PREFIX, LUXCORE_ENGINE_ID, CYCLES_ENGINE_ID,
    CATEGORY_ICONS, GEL_ENUM_ITEMS,
)
# Solo state key — shared with operators.py via bpy.app.driver_namespace
_SOLO_VISIBILITY_KEY = "lsm_solo_visibility_stack"

# CAT_ICONS is no longer defined here — use CATEGORY_ICONS from constants directly.
CAT_ICONS = CATEGORY_ICONS   # thin alias kept for any future local references

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Custom role-dot icons — solid coloured circles generated in memory
# ---------------------------------------------------------------------------

_role_pcoll = None

_ROLE_DOT_COLORS = {
    "key":  (1.00, 0.85, 0.00),   # yellow
    "fill": (0.20, 0.55, 1.00),   # blue
    "rim":  (0.15, 0.90, 0.45),   # green
    "env":  (0.70, 0.30, 1.00),   # purple
}


def _build_circle_pixels(r, g, b, size=32):
    cx = cy = size / 2.0
    radius = size / 2.0 - 1.5
    pixels = []
    for y in range(size):
        for x in range(size):
            dx = x - cx + 0.5
            dy = y - cy + 0.5
            dist = (dx * dx + dy * dy) ** 0.5
            if dist <= radius - 0.5:
                a = 1.0
            elif dist <= radius + 0.5:
                a = radius + 0.5 - dist
            else:
                a = 0.0
            pixels.extend([r, g, b, a])
    return pixels


def _init_role_icons():
    global _role_pcoll
    import bpy.utils.previews
    if _role_pcoll is not None:
        return
    _role_pcoll = bpy.utils.previews.new()
    size = 32
    for role, (r, g, b) in _ROLE_DOT_COLORS.items():
        thumb = _role_pcoll.new(role)
        thumb.image_size = [size, size]
        thumb.image_pixels_float = _build_circle_pixels(r, g, b, size)


def _free_role_icons():
    global _role_pcoll
    if _role_pcoll is not None:
        import bpy.utils.previews
        bpy.utils.previews.remove(_role_pcoll)
        _role_pcoll = None


def _get_role_icon_id(role: str) -> int:
    if _role_pcoll is None:
        return 0
    thumb = _role_pcoll.get(role)
    return thumb.icon_id if thumb else 0


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
        description="Global energy multiplier applied to all lights in the scene",
        default=1.0, min=0.01, max=20.0, soft_min=0.1, soft_max=5.0,
        step=10, precision=2,
        update=lambda self, ctx: bpy.ops.lsm.live_update(),
    )
    temperature_offset: FloatProperty(
        name="Temp Offset (K)",
        description=(
            "Kelvin offset applied to all lights that have a colour temperature.\n"
            "RGB-only lights (e.g. neon accents) are not affected.\n"
            "Updates in real time."
        ),
        default=0.0, min=-5000.0, max=5000.0, soft_min=-1500.0, soft_max=1500.0,
        step=100, precision=0,
        update=lambda self, ctx: bpy.ops.lsm.live_update(),
    )

    gel_preset: bpy.props.EnumProperty(
        name="Gel",
        description=(
            "Named colour gel multiplied over all light colours.\n"
            "Works with both kelvin and RGB sources. Updates in real time."
        ),
        items=GEL_ENUM_ITEMS,
        default="none",
        update=lambda self, ctx: bpy.ops.lsm.live_update(),
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

    # --- Fill ratio ---
    fill_ratio: bpy.props.FloatProperty(
        name="Fill Ratio",
        description=(
            "Fill-to-key energy ratio.\n"
            "1.0 = flat (fill equals key)\n"
            "0.5 = 2:1 ratio, standard portrait\n"
            "0.0 = no fill, maximum drama\n"
            "Rim lights track at half the fill ratio. Updates in real time."
        ),
        default=1.0, min=0.0, max=2.0, soft_min=0.0, soft_max=1.0,
        step=5, precision=2,
        update=lambda self, ctx: bpy.ops.lsm.live_update(),
    )

    show_overlay: bpy.props.BoolProperty(
        name="Light Contours",
        description=(
            "Show coloured contour overlays in the 3D viewport for all LSM lights.\n"
            "Key = yellow  ·  Fill = blue  ·  Rim = green  ·  Env = purple"
        ),
        default=True,
        update=lambda self, ctx: ctx.scene.__setitem__(
            "lsm_overlay_enabled", self.show_overlay),
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
        if preset is None:
            layout.label(text=item.preset_id, icon="ERROR")
            return

        is_user  = preset.get("is_user", False)
        cat_icon = CAT_ICONS.get(preset.get("category", ""), "LIGHT")

        row = layout.row(align=True)
        # Category icon — for user presets swap to a star to distinguish them
        row.label(text="", icon="SOLO_ON" if is_user else cat_icon)
        # Name — append ★ suffix for user presets so they're scannable in a long list
        name = preset.get("name", item.preset_id)
        row.label(text=("★ " + name) if is_user else name)

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

            # Gel selector
            col.separator(factor=0.3)
            gel_row = col.row(align=True)
            gel_row.prop(props, "gel_preset", text="Gel", icon="COLORSET_13_VEC")
            if props.gel_preset != "none":
                # Show a coloured dot to preview the gel tint
                from .constants import GEL_COLORS
                gc = GEL_COLORS.get(props.gel_preset, (1, 1, 1))
                # Blender can't draw arbitrary color swatches in a row easily,
                # so we show the gel name as a label with the icon as hint
                gel_row.label(text="", icon="MATFLUID")

            # Fill ratio — only shown when LSM lights are in the scene
            lsm_lights = [o for o in context.scene.objects
                          if o.name.startswith(LSM_PREFIX) and o.type == "LIGHT"]
            has_key  = any(o.get("lsm_role") == "key"  for o in lsm_lights)
            has_fill = any(o.get("lsm_role") in ("fill","rim") for o in lsm_lights)

            if has_key and has_fill:
                col.separator(factor=0.4)
                fill_col = col.column(align=True)
                fill_col.prop(props, "fill_ratio", slider=True)
                # Ratio readout
                ratio = props.fill_ratio
                if ratio > 0.001:
                    ratio_str = "%.0f:1 (key:fill)" % (1.0 / ratio) if ratio < 1.0 else "1:%.0f (flat)" % ratio
                else:
                    ratio_str = "No fill  (maximum drama)"
                fill_col.scale_y = 0.8
                fill_col.label(text=ratio_str, icon="DRIVER_TRANSFORM")

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
            props  = context.scene.lsm_props
            n = sum(1 for o in context.scene.objects
                    if o.name.startswith(LSM_PREFIX))
            if n > 0:
                box = layout.box()
                box.label(
                    text="%d LSM light%s in scene" % (n, "s" if n != 1 else ""),
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

            # ---- Save preset ------------------------------------------------
            layout.separator(factor=0.4)
            save_box = layout.box()
            save_box.label(text="User Presets:", icon="BOOKMARKS")

            save_col = save_box.column(align=True)
            save_row = save_col.row(align=True)
            save_row.scale_y = 1.3
            save_row.operator(
                "lsm.save_preset_from_scene",
                text="Save Rig as Preset",
                icon="ADD",
            )

            # Delete button — only enabled when a user preset is selected
            from .presets_data import PRESETS_BY_ID
            active_preset = PRESETS_BY_ID.get(
                getattr(props, "active_preset_id", ""), {})
            is_user = active_preset.get("is_user", False)

            del_row = save_col.row(align=True)
            del_row.enabled = is_user
            del_op = del_row.operator(
                "lsm.delete_user_preset",
                text="Delete Selected" if is_user else "Delete (select user preset)",
                icon="REMOVE",
            )
            del_op.preset_id = props.active_preset_id if is_user else ""

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

# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class LSM_PT_SceneLightsInline(bpy.types.Panel):
    """Inline control panel for all LSM lights currently in the scene.

    Lists lights grouped by role (key / fill / rim / other) with per-light
    energy slider, color swatch, visibility toggle, and Solo button.
    Shows Bake Intensity when multiplier != 1.0.
    """
    bl_label       = "Scene Lights"
    bl_idname      = "LSM_PT_SceneLightsInline"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "LightStageManager"
    bl_order       = 40
    bl_options     = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        props = getattr(context.scene, "lsm_props", None)
        if props:
            self.layout.prop(props, "show_overlay", text="",
                             icon="HIDE_OFF" if props.show_overlay else "HIDE_ON")

    @classmethod
    def poll(cls, context):
        return any(o.name.startswith(LSM_PREFIX) and o.type == "LIGHT"
                   for o in context.scene.objects)

    def draw(self, context):
        try:
            layout = self.layout
            scene  = context.scene
            props  = scene.lsm_props
            in_solo = _SOLO_VISIBILITY_KEY in bpy.app.driver_namespace
            solo_target = scene.get("lsm_solo_active", "")

            lsm_lights = [o for o in scene.objects
                          if o.name.startswith(LSM_PREFIX)
                          and o.type == "LIGHT"
                          and o.get("lsm_role") != "gobo"]

            # --- Bake Intensity banner ---
            if abs(props.intensity_multiplier - 1.0) > 0.001:
                bake_row = layout.row()
                bake_row.alert = True
                bake_row.operator("lsm.bake_intensity",
                                  text="Bake Intensity ×%.2f → 1.0" % props.intensity_multiplier,
                                  icon="IMPORT")

            # --- Exit Solo banner ---
            if in_solo:
                exit_row = layout.row()
                exit_row.alert = True
                exit_row.operator("lsm.exit_solo",
                                  text="Exit Solo — restore all lights",
                                  icon="SOLO_OFF")

            layout.separator(factor=0.3)

            # Group by role
            role_order  = ["key", "fill", "rim", "env", "fill"]
            role_labels = {"key": "Key", "fill": "Fill", "rim": "Rim",
                           "env": "Env", None: "Other"}
            seen_roles  = {}
            for obj in lsm_lights:
                r = obj.get("lsm_role", "fill")
                seen_roles.setdefault(r, []).append(obj)

            role_priority = ["key", "fill", "rim", "env"]
            sorted_roles  = sorted(seen_roles.keys(),
                                   key=lambda r: role_priority.index(r)
                                   if r in role_priority else 99)

            for role in sorted_roles:
                objs = seen_roles[role]
                role_header = layout.row()
                role_header.label(text=role_labels.get(role, role.capitalize()),
                                  icon="LIGHT")

                for obj in objs:
                    ld        = obj.data
                    is_solo   = (obj.name == solo_target)
                    is_hidden = obj.hide_viewport
                    has_target = bool(obj.get("lsm_has_target", False))

                    # --- Primary row ---
                    row = layout.row(align=True)
                    row.active = not is_hidden

                    # Visibility toggle
                    vis_icon = "HIDE_OFF" if not is_hidden else "HIDE_ON"
                    row.prop(obj, "hide_viewport",
                             text="", icon=vis_icon, emboss=False)

                    # Role colour dot — solid circle generated from overlay colours
                    icon_id = _get_role_icon_id(role)
                    if icon_id:
                        row.label(text="", icon_value=icon_id)
                    else:
                        row.label(text="", icon="COLORSET_01_VEC")

                    # Light name (shortened)
                    short_name = obj.name.replace(LSM_PREFIX, "", 1)
                    row.label(text=short_name)

                    # Energy slider
                    row.prop(ld, "energy", text="", slider=False)

                    # Color picker
                    row.prop(ld, "color", text="")

                    # Solo button
                    solo_op = row.operator(
                        "lsm.solo_toggle" if (in_solo and not is_solo) else "lsm.solo_light",
                        text="",
                        icon="SOLO_ON" if is_solo else "RADIOBUT_OFF",
                        depress=is_solo,
                    )
                    solo_op.light_name = obj.name

                    # --- Secondary row: D/S toggles + Kelvin + Target ---
                    sub = layout.row(align=True)
                    sub.scale_y = 0.75
                    sub.active  = not is_hidden

                    # Diffuse toggle — Blender 4.x: diffuse_factor; older: use_diffuse
                    use_d = (getattr(ld, "diffuse_factor",  None) or 0) > 0.5 \
                            if hasattr(ld, "diffuse_factor") \
                            else getattr(ld, "use_diffuse", True)
                    diff_op  = sub.operator(
                        "lsm.set_light_diffuse",
                        text="D", depress=use_d,
                        icon="BLANK1",
                    )
                    diff_op.light_name = obj.name
                    diff_op.value      = not use_d

                    # Specular toggle
                    use_s = (getattr(ld, "specular_factor", None) or 0) > 0.5 \
                            if hasattr(ld, "specular_factor") \
                            else getattr(ld, "use_specular", True)
                    spec_op  = sub.operator(
                        "lsm.set_light_specular",
                        text="S", depress=use_s,
                        icon="BLANK1",
                    )
                    spec_op.light_name = obj.name
                    spec_op.value      = not use_s

                    sub.separator(factor=0.5)

                    # Kelvin temperature button
                    stored_k = float(obj.get("lsm_kelvin", -1.0))
                    k_label  = "%.0fK" % stored_k if stored_k > 0 else "RGB"
                    k_op     = sub.operator(
                        "lsm.set_light_kelvin",
                        text=k_label,
                        icon="LIGHT_SUN",
                    )
                    k_op.light_name = obj.name
                    k_op.kelvin     = max(1000.0, stored_k) if stored_k > 0 else 5600.0

                    sub.separator(factor=0.5)

                    # Target Empty toggle
                    target_icon = "EMPTY_AXIS" if has_target else "EMPTY_DATA"
                    tgt_op = sub.operator(
                        "lsm.toggle_light_target",
                        text="",
                        icon=target_icon,
                        depress=has_target,
                    )
                    tgt_op.light_name = obj.name

                layout.separator(factor=0.2)

        except Exception as exc:
            log.error("LSM_PT_SceneLightsInline.draw: %s", exc)


class LSM_PT_AssetBrowser(bpy.types.Panel):
    """Panel shown in the Asset Browser sidebar when an LSM asset is active.

    Displays preset metadata and provides a one-click Apply button that
    delegates to the full scale-aware, engine-aware apply pipeline.
    """
    bl_label       = "Light Stage Manager"
    bl_idname      = "LSM_PT_AssetBrowser"
    bl_space_type  = "FILE_BROWSER"
    bl_region_type = "TOOL_PROPS"
    bl_category    = "LSM"

    @classmethod
    def poll(cls, context):
        # Only show when the file browser is in Asset Browser mode
        # and an LSM asset is selected
        if not hasattr(context, "asset"):
            return False
        from .asset_builder import is_lsm_asset
        return is_lsm_asset(context)

    def draw(self, context):
        try:
            from .asset_builder import get_active_lsm_asset
            from .presets_data import PRESETS_BY_ID

            layout = self.layout
            pid    = get_active_lsm_asset(context)
            preset = PRESETS_BY_ID.get(pid) if pid else None

            if preset is None:
                layout.label(text="Unknown LSM preset", icon="ERROR")
                return

            # --- Preset identity ---
            col = layout.column(align=True)
            col.label(text=preset["name"], icon="LIGHT_SUN")
            cat  = preset.get("category", "")
            desc = preset.get("description", "")
            if cat:
                col.label(text="Category: %s" % cat.capitalize(),
                          icon=CAT_ICONS.get(cat, "LIGHT"))

            # --- Description (word-wrapped via label rows) ---
            if desc:
                layout.separator(factor=0.3)
                box = layout.box()
                box.scale_y = 0.8
                # Split at sentence boundaries for readability
                for sentence in desc.replace("\n", " ").split(". "):
                    sentence = sentence.strip()
                    if sentence:
                        box.label(text=sentence + ("." if not sentence.endswith(".") else ""))

            # --- Light summary ---
            lights     = preset.get("lights", [])
            lxc_cfg    = preset.get("luxcore_cfg", {})
            eng_hint   = lxc_cfg.get("engine", "PATH")
            n_lights   = len(lights)
            light_types = {}
            for l in lights:
                t = l.get("type", "AREA")
                light_types[t] = light_types.get(t, 0) + 1
            summary = "  ".join("%d× %s" % (v, k) for k, v in light_types.items())

            layout.separator(factor=0.3)
            info = layout.column(align=True)
            info.scale_y = 0.85
            info.label(text="%d lights: %s" % (n_lights, summary), icon="LIGHT")
            info.label(text="Engine: %s" % eng_hint, icon="RENDER_STILL")

            # --- Apply button ---
            layout.separator(factor=0.6)
            row = layout.row()
            row.scale_y = 1.6
            row.operator("lsm.apply_from_asset",
                         text="Apply Preset", icon="LIGHT_SUN")

            # --- Scene props shortcut ---
            scene = context.scene
            if scene and hasattr(scene, "lsm_props"):
                props = scene.lsm_props
                layout.separator(factor=0.3)
                sub = layout.column(align=True)
                sub.label(text="Quick adjustments:", icon="TOOL_SETTINGS")
                sub.prop(props, "intensity_multiplier", slider=True)
                sub.prop(props, "scale_reference",      text="Scale")
                if props.scale_reference == "MANUAL":
                    sub.prop(props, "manual_scale")

        except Exception as exc:
            log.error("LSM_PT_AssetBrowser.draw: %s", exc)


PROPERTY_GROUPS = (LSM_PresetListItem, LSM_SceneProperties)
UILISTS         = (LSM_UL_PresetList,)
PANELS = (
    LSM_PT_Main,
    LSM_PT_PresetInfo,
    LSM_PT_LightModifiers,
    LSM_PT_SceneLightsInline,
    LSM_PT_SceneTools,
    LSM_PT_Previews,
    LSM_PT_RenderProperties,
    LSM_PT_AssetBrowser,
)


def register():
    _init_role_icons()

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
    _free_role_icons()

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
