# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  difrkaguilar + Claude (Anthropic)
# LuxCore Stage Manager -- Operators (English only)

from __future__ import annotations
import os
import sys
import json
import subprocess
import logging

import bpy
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty
from mathutils import Vector

from .presets_data import PRESETS, PRESETS_BY_ID
from .scene_builder import apply_preset, remove_lsm_lights
from .constants import (
    LSM_PREFIX,
    LXC_AREA_GAIN_SCALE, LXC_SPOT_GAIN_SCALE,
    LXC_POINT_GAIN_SCALE, LXC_SUN_GAIN_SCALE,
    KELVIN_MIN, KELVIN_LXC_MAX,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _addon_dir() -> str:
    return os.path.dirname(os.path.realpath(__file__))

def _previews_dir() -> str:
    return os.path.join(_addon_dir(), "previews")

def _renderer_script() -> str:
    return os.path.join(_addon_dir(), "preview_renderer.py")


_LXC_GAIN_SCALE = {
    "AREA":  LXC_AREA_GAIN_SCALE,
    "SPOT":  LXC_SPOT_GAIN_SCALE,
    "SUN":   LXC_SUN_GAIN_SCALE,
    "POINT": LXC_POINT_GAIN_SCALE,
}


def _expected_kelvin(descriptor: dict, temp_offset: float) -> int | None:
    kelvin = descriptor.get("kelvin")
    if kelvin is None:
        return None
    return int(max(KELVIN_MIN, min(KELVIN_LXC_MAX, float(kelvin) + float(temp_offset))))


def _expected_lxc_gain(descriptor: dict, intensity_mult: float) -> float:
    light_type    = descriptor.get("type", "AREA")
    raw_energy    = max(0.0, float(descriptor.get("energy", 100.0)))
    actual_energy = raw_energy * max(0.0001, float(intensity_mult))
    gain_mult     = max(0.0001, float(descriptor.get("luxcore_gain", 1.0)))
    gain_scale    = _LXC_GAIN_SCALE.get(light_type, LXC_AREA_GAIN_SCALE)
    return max(0.0001, actual_energy * gain_scale * gain_mult)


def _compute_scale_and_origin(context) -> tuple[float, Vector]:
    """Return (scene_scale, scene_origin) from the current scene state.

    Strategy (in order of priority):
      1. Active object with mesh data → longest bounding-box axis + BB centre.
      2. All visible mesh objects union → same.
      3. scene.unit_settings.scale_length as a bare hint (rare fallback).
      4. 1.0 / origin (0,0,0) — preset defaults, calibrated for Suzanne.

    The scale returned is the length of the longest axis of the reference
    bounding box in world space.  The origin is the centre of that box, so
    the rig orbits and aims at the actual object rather than the world axis.
    """
    props = getattr(context.scene, "lsm_props", None)
    if props is not None:
        ref_mode = getattr(props, "scale_reference", "ACTIVE")
        if ref_mode == "MANUAL":
            return float(props.manual_scale), Vector((0.0, 0.0, 0.0))

    def _bbox_from_objects(objects):
        """Return (min_corner, max_corner) in world space for a list of mesh objects."""
        world_verts = []
        for obj in objects:
            if obj.type != "MESH":
                continue
            for corner in obj.bound_box:          # 8 local corners
                world_verts.append(obj.matrix_world @ Vector(corner))
        if not world_verts:
            return None, None
        min_c = Vector((min(v.x for v in world_verts),
                        min(v.y for v in world_verts),
                        min(v.z for v in world_verts)))
        max_c = Vector((max(v.x for v in world_verts),
                        max(v.y for v in world_verts),
                        max(v.z for v in world_verts)))
        return min_c, max_c

    def _scale_and_origin_from_bbox(min_c, max_c):
        if min_c is None:
            return 1.0, Vector((0.0, 0.0, 0.0))
        dims   = max_c - min_c
        scale  = max(dims.x, dims.y, dims.z)
        origin = (min_c + max_c) / 2.0
        return max(0.001, scale), origin

    ref_mode = "ACTIVE"
    if props is not None:
        ref_mode = getattr(props, "scale_reference", "ACTIVE")

    if ref_mode == "ACTIVE":
        obj = context.active_object
        if obj and obj.type == "MESH":
            min_c, max_c = _bbox_from_objects([obj])
            return _scale_and_origin_from_bbox(min_c, max_c)
        # Active object exists but is not a mesh — fall through to SCENE
        log.debug("[LSM] scale_reference=ACTIVE but no mesh active, falling back to SCENE")

    if ref_mode in ("SCENE", "ACTIVE"):      # ACTIVE falls here when no mesh
        visible = [o for o in context.scene.objects
                   if o.type == "MESH" and not o.hide_viewport
                   and not o.name.startswith(LSM_PREFIX)]
        if visible:
            min_c, max_c = _bbox_from_objects(visible)
            return _scale_and_origin_from_bbox(min_c, max_c)

    # Last resort: unit scale as a bare hint, origin at world centre
    unit_scale = getattr(context.scene.unit_settings, "scale_length", 1.0)
    log.debug("[LSM] No reference mesh found; using unit_scale=%.4f", unit_scale)
    return float(unit_scale), Vector((0.0, 0.0, 0.0))


# ---------------------------------------------------------------------------
# LSM_OT_ApplyPreset
# ---------------------------------------------------------------------------

class LSM_OT_ApplyPreset(Operator):
    """Apply the selected preset: create lights and configure render settings"""
    bl_idname  = "lsm.apply_preset"
    bl_label   = "Apply Preset"
    bl_options = {"REGISTER", "UNDO"}

    preset_id: StringProperty(default="")

    @classmethod
    def poll(cls, context):
        return context.scene is not None

    def execute(self, context):
        props  = context.scene.lsm_props
        pid    = self.preset_id or props.active_preset_id
        if not pid:
            self.report({"WARNING"}, "LSM: No preset selected")
            return {"CANCELLED"}

        preset = PRESETS_BY_ID.get(pid)
        if preset is None:
            self.report({"ERROR"}, "LSM: Preset '%s' not found" % pid)
            return {"CANCELLED"}

        try:
            scene_scale, scene_origin = _compute_scale_and_origin(context)
            created = apply_preset(
                preset             = preset,
                scene              = context.scene,
                intensity_mult     = float(props.intensity_multiplier),
                temp_offset        = float(props.temperature_offset),
                clear_existing     = bool(props.clear_existing),
                configure_luxcore  = bool(props.auto_configure_luxcore),
                scene_scale        = scene_scale,
                scene_origin       = scene_origin,
            )
        except Exception as exc:
            log.exception("[LSM] apply_preset failed for %r", pid)
            self.report({"ERROR"}, "LSM: Error applying '%s': %s" % (
                preset.get("name", pid), exc))
            return {"CANCELLED"}

        n      = len(created)
        engine = context.scene.render.engine
        labels = {
            "LUXCORE":             "LuxCore",
            "CYCLES":              "Cycles",
            "BLENDER_EEVEE_NEXT":  "EEVEE",
            "BLENDER_EEVEE":       "EEVEE",
        }
        elabel = labels.get(engine, engine)

        self.report({"INFO"}, "LSM [%s]: '%s' applied — %d light%s" % (
            elabel, preset.get("name", pid), n, "s" if n != 1 else ""))
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# LSM_OT_SelectLSMLights
# ---------------------------------------------------------------------------

class LSM_OT_SelectLSMLights(Operator):
    """Select all lights created by LuxCore Stage Manager"""
    bl_idname = "lsm.select_lights"
    bl_label  = "Select LSM Lights"

    @classmethod
    def poll(cls, context):
        return (context.scene is not None and
                any(o.name.startswith(LSM_PREFIX) for o in context.scene.objects))

    def execute(self, context):
        try:
            bpy.ops.object.select_all(action="DESELECT")
            n = 0
            for obj in context.scene.objects:
                if not obj.name.startswith(LSM_PREFIX):
                    continue
                obj.select_set(True)
                n += 1
        except Exception as exc:
            self.report({"ERROR"}, "LSM: %s" % exc)
            return {"CANCELLED"}
        self.report({"INFO"}, "LSM: %d light%s selected" % (n, "s" if n != 1 else ""))
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# LSM_OT_RemoveLSMLights
# ---------------------------------------------------------------------------

class LSM_OT_RemoveLSMLights(Operator):
    """Remove all LSM_ lights from the active scene"""
    bl_idname  = "lsm.remove_lights"
    bl_label   = "Remove LSM Lights"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return (context.scene is not None and
                any(o.name.startswith(LSM_PREFIX) for o in context.scene.objects))

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        try:
            n = remove_lsm_lights(context.scene)
        except Exception as exc:
            self.report({"ERROR"}, "LSM: %s" % exc)
            return {"CANCELLED"}
        self.report({"INFO"}, "LSM: %d light%s removed" % (n, "s" if n != 1 else ""))
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# LSM_OT_ResetModifiers
# ---------------------------------------------------------------------------

class LSM_OT_ResetModifiers(Operator):
    """Reset intensity multiplier and temperature offset to defaults"""
    bl_idname = "lsm.reset_modifiers"
    bl_label  = "Reset Modifiers"

    def execute(self, context):
        try:
            p = context.scene.lsm_props
            try:
                prefs = bpy.context.preferences.addons["luxcore_stage_manager"].preferences
            except Exception:
                prefs = None

            p.intensity_multiplier = (
                float(getattr(prefs, "default_intensity", 1.0))
                if prefs is not None else 1.0
            )
            p.temperature_offset   = 0.0
            p.clear_existing = (
                bool(getattr(prefs, "default_clear_existing", True))
                if prefs is not None else True
            )
            p.auto_configure_luxcore = (
                bool(getattr(prefs, "default_auto_configure", True))
                if prefs is not None else True
            )
        except Exception as exc:
            self.report({"ERROR"}, "LSM: %s" % exc)
            return {"CANCELLED"}
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# LSM_OT_SetCategory
# ---------------------------------------------------------------------------

class LSM_OT_SetCategory(Operator):
    """Filter the preset list by category"""
    bl_idname = "lsm.set_category"
    bl_label  = "Set Category"

    category: StringProperty(default="ALL")

    def execute(self, context):
        try:
            context.scene.lsm_props.active_category = self.category
        except Exception as exc:
            self.report({"ERROR"}, "LSM: %s" % exc)
            return {"CANCELLED"}
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# LSM_OT_DiagnoseLights
# ---------------------------------------------------------------------------

class LSM_OT_DiagnoseLights(Operator):
    """Print LuxCore / Cycles property values of all LSM lights to the system console"""
    bl_idname = "lsm.diagnose_lights"
    bl_label  = "Diagnose LSM Lights (Console)"

    def execute(self, context):
        lsm_lights = [o for o in context.scene.objects
                      if o.name.startswith(LSM_PREFIX)]
        if not lsm_lights:
            self.report({"WARNING"}, "LSM: No LSM lights in scene")
            return {"CANCELLED"}

        engine  = context.scene.render.engine
        labels  = {
            "LUXCORE": "LuxCore", "CYCLES": "Cycles",
            "BLENDER_EEVEE_NEXT": "EEVEE", "BLENDER_EEVEE": "EEVEE",
        }
        elabel = labels.get(engine, engine)

        print()
        print("=" * 72)
        print("[LSM] DIAGNOSTIC REPORT — %d lights — Engine: %s (%s)" % (
            len(lsm_lights), elabel, engine))
        print("=" * 72)

        for obj in lsm_lights:
            ld      = obj.data
            lx_ld   = getattr(ld,  "luxcore",    None)
            lx_obj  = getattr(obj, "luxcore",    None)
            cyc_ld  = getattr(ld,  "cycles",     None)

            print()
            print("  OBJECT: %s" % obj.name)
            print("    Blender | type=%-6s energy=%.2f  color=(%.3f, %.3f, %.3f)" % (
                ld.type, ld.energy, ld.color[0], ld.color[1], ld.color[2]))

            if lx_ld is not None:
                gain   = getattr(lx_ld, "gain",              "N/A")
                cmode  = getattr(lx_ld, "color_mode",        "N/A")
                ktemp  = getattr(lx_ld, "temperature",
                                 getattr(lx_ld, "color_temperature", "N/A"))
                unit   = getattr(lx_ld, "light_unit",        "N/A")
                uctmp  = getattr(lx_ld, "use_color_temperature", "N/A")
                print("    LuxCore | gain=%-8s  unit=%-10s  color_mode=%-12s  K=%s  use_K=%s" % (
                    "%.4f" % gain if isinstance(gain, float) else str(gain),
                    str(unit), str(cmode), str(ktemp), str(uctmp)))
            else:
                print("    LuxCore | light.luxcore = NONE (BlendLuxCore not installed?)")

            if lx_obj is not None:
                vis = getattr(lx_obj, "visibility", None)
                if vis:
                    cam = getattr(vis, "camera", "N/A")
                    print("    ObjVis  | visibility.camera=%s" % cam)
                else:
                    cam = getattr(lx_obj, "visible_to_camera", "N/A")
                    print("    ObjVis  | visible_to_camera=%s" % cam)
            else:
                print("    ObjVis  | obj.luxcore = NONE")

            if cyc_ld is not None:
                mis  = getattr(cyc_ld, "use_multiple_importance", "N/A")
                boun = getattr(cyc_ld, "max_bounces", "N/A")
                print("    Cycles  | MIS=%s  max_bounces=%s" % (mis, boun))

        print()
        print("=" * 72)
        self.report({"INFO"},
                    "LSM: Diagnostic printed — Window > Toggle System Console")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# LSM_OT_VerifyActivePreset
# ---------------------------------------------------------------------------

class LSM_OT_VerifyActivePreset(Operator):
    """Verify current LSM lights against the active preset configuration"""
    bl_idname = "lsm.verify_active_preset"
    bl_label  = "Verify Active Preset (Console)"

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        if scene is None or scene.render.engine != "LUXCORE":
            return False
        props = getattr(scene, "lsm_props", None)
        return bool(props and props.active_preset_id)

    def execute(self, context):
        scene = context.scene
        props = scene.lsm_props
        preset = PRESETS_BY_ID.get(props.active_preset_id)
        if preset is None:
            self.report({"ERROR"}, "LSM: Active preset not found")
            return {"CANCELLED"}

        scene_lights = {
            obj.name: obj for obj in scene.objects
            if obj.name.startswith(LSM_PREFIX)
        }
        if not scene_lights:
            self.report({"WARNING"}, "LSM: No LSM lights in scene")
            return {"CANCELLED"}

        failures: list[str] = []

        print()
        print("=" * 72)
        print("[LSM] VERIFICATION REPORT — Preset: %s" % preset.get("name", props.active_preset_id))
        print("=" * 72)

        for desc in preset.get("lights", []):
            obj_name = LSM_PREFIX + desc.get("name", "Light")
            obj = scene_lights.get(obj_name)
            if obj is None:
                failures.append("%s missing from scene" % obj_name)
                print("  FAIL | %s | missing object" % obj_name)
                continue

            lx = getattr(obj.data, "luxcore", None)
            if lx is None:
                failures.append("%s has no light.luxcore data" % obj_name)
                print("  FAIL | %s | light.luxcore is missing" % obj_name)
                continue

            expected_gain = _expected_lxc_gain(desc, props.intensity_multiplier)
            actual_gain = getattr(lx, "gain", None)
            expected_kelvin = _expected_kelvin(desc, props.temperature_offset)
            actual_kelvin = getattr(lx, "temperature",
                                    getattr(lx, "color_temperature", None))
            actual_mode = getattr(lx, "color_mode", None)
            actual_unit = getattr(lx, "light_unit", getattr(lx, "unit", None))
            use_cycles_settings = getattr(lx, "use_cycles_settings", None)

            light_failures: list[str] = []
            if use_cycles_settings:
                light_failures.append("use_cycles_settings=%r expected False" % (use_cycles_settings,))
            if actual_unit != "artistic":
                light_failures.append("unit=%r expected 'artistic'" % (actual_unit,))

            if actual_gain is None or abs(float(actual_gain) - expected_gain) > 1e-4:
                light_failures.append("gain=%r expected %.4f" % (actual_gain, expected_gain))

            if expected_kelvin is not None:
                if actual_mode != "temperature":
                    light_failures.append("color_mode=%r expected 'temperature'" % (actual_mode,))
                if actual_kelvin is None or abs(float(actual_kelvin) - expected_kelvin) > 0.5:
                    light_failures.append("K=%r expected %d" % (actual_kelvin, expected_kelvin))
            elif actual_mode not in (None, "rgb", "color"):
                light_failures.append("color_mode=%r expected RGB path" % (actual_mode,))

            if light_failures:
                failures.append("%s: %s" % (obj_name, "; ".join(light_failures)))
                print("  FAIL | %s | %s" % (obj_name, "; ".join(light_failures)))
            else:
                if expected_kelvin is not None:
                    print("  OK   | %s | gain=%.4f mode=%s K=%s" % (
                        obj_name, float(actual_gain), actual_mode, actual_kelvin))
                else:
                    print("  OK   | %s | gain=%.4f mode=%s" % (
                        obj_name, float(actual_gain), actual_mode))

        extra = sorted(set(scene_lights.keys()) - {
            LSM_PREFIX + desc.get("name", "Light") for desc in preset.get("lights", [])
        })
        for obj_name in extra:
            failures.append("%s present in scene but not in active preset" % obj_name)
            print("  WARN | %s | extra LSM light not defined by active preset" % obj_name)

        print("-" * 72)
        print("[LSM] Verification checked %d expected lights, failures=%d" % (
            len(preset.get("lights", [])), len(failures)))
        print("=" * 72)

        if failures:
            self.report({"WARNING"}, "LSM: Verification found %d issue(s) — see console" % len(failures))
            return {"CANCELLED"}

        self.report({"INFO"}, "LSM: Verification passed for '%s'" % preset.get("name", props.active_preset_id))
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# LSM_OT_RenderPreviews
# ---------------------------------------------------------------------------

class LSM_OT_RenderPreviews(Operator):
    """Render 256x256 preview thumbnails for all presets using Suzanne.

Launches a headless Blender subprocess; takes 1-5 minutes depending on hardware.
Previews are saved to the addon's previews/ folder and persist across sessions."""
    bl_idname = "lsm.render_previews"
    bl_label  = "Render Preview Thumbnails"
    bl_options = {"REGISTER"}

    force_re_render: BoolProperty(
        name="Force Re-render",
        description="Re-render even if preview PNGs already exist",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(
            self, width=420, title="Render Preview Thumbnails",
        )

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        pdir = _previews_dir()
        existing = sum(
            1 for p in PRESETS
            if os.path.exists(os.path.join(pdir, p["id"] + ".png"))
        )
        col.label(text="This will launch a headless Blender instance.", icon="INFO")
        col.label(text="Each preset is rendered with Suzanne as subject.")
        col.label(text="Process takes approximately 2-8 minutes.")
        col.separator()
        col.label(text="Previews folder: .../%s" % os.path.basename(pdir))
        col.label(text="Existing PNGs: %d / %d" % (existing, len(PRESETS)))
        col.separator()
        col.prop(self, "force_re_render")

    def execute(self, context):
        pdir       = _previews_dir()
        script     = _renderer_script()
        blender_bin = getattr(bpy.app, "binary_path", sys.executable)

        # Validate
        if not os.path.exists(script):
            self.report({"ERROR"}, "LSM: preview_renderer.py not found in addon directory")
            return {"CANCELLED"}

        os.makedirs(pdir, exist_ok=True)

        # If force re-render, remove existing PNGs and sentinel
        if self.force_re_render:
            for p in PRESETS:
                png = os.path.join(pdir, p["id"] + ".png")
                if os.path.exists(png):
                    os.remove(png)
            sentinel = os.path.join(pdir, ".render_complete")
            if os.path.exists(sentinel):
                os.remove(sentinel)

        # Serialise preset light data to a temp JSON file
        # (only the fields the renderer needs: id, name, lights)
        import tempfile
        payload = []
        for p in PRESETS:
            payload.append({
                "id":     p["id"],
                "name":   p["name"],
                "lights": [
                    {
                        "name":     l.get("name"),
                        "type":     l.get("type"),
                        "location": list(l.get("location", [0,0,3])),
                        "target":   list(l.get("target")) if l.get("target") else None,
                        "energy":   l.get("energy"),
                        "kelvin":   l.get("kelvin"),
                        "color":    list(l.get("color")) if l.get("color") else None,
                        "size":     l.get("size"),
                        "size_y":   l.get("size_y"),
                        "shape":    l.get("shape"),
                        "spot_size": l.get("size") if l.get("type") == "SPOT" else None,
                        "spot_blend": l.get("spot_blend"),
                        "use_shadow": l.get("use_shadow", True),
                    }
                    for l in p.get("lights", [])
                ],
            })

        tmp_json = os.path.join(tempfile.gettempdir(), "lsm_preview_data.json")
        with open(tmp_json, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)

        # Launch headless Blender
        cmd = [
            blender_bin,
            "--background",
            "--python", script,
            "--",
            tmp_json,
            pdir,
        ]

        print("[LSM] Launching headless Blender: %s" % " ".join(cmd))

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            # Register a timer to poll process completion
            bpy.app.timers.register(
                lambda: _poll_render_process(proc, pdir, context),
                first_interval=2.0,
            )
            self.report({"INFO"},
                        "LSM: Preview render started — see System Console for progress")
        except Exception as exc:
            self.report({"ERROR"}, "LSM: Could not launch Blender: %s" % exc)
            return {"CANCELLED"}

        return {"FINISHED"}


def _poll_render_process(proc, pdir: str, context) -> float | None:
    """Timer callback: polls the headless Blender process.

    Returns a delay (float) to keep the timer running, or None to stop.
    """
    retcode = proc.poll()

    if retcode is None:
        # Still running — read any pending output
        try:
            for _ in range(20):
                line = proc.stdout.readline()
                if not line:
                    break
                print(line.rstrip())
        except Exception:
            pass
        return 3.0   # check again in 3 seconds

    # Process finished
    # Drain remaining output
    try:
        remaining, _ = proc.communicate(timeout=5)
        if remaining:
            for line in remaining.splitlines():
                print(line)
    except Exception:
        pass

    sentinel = os.path.join(pdir, ".render_complete")
    if os.path.exists(sentinel):
        print("[LSM] Preview render complete. Reloading thumbnails...")
        try:
            from .previews import reload_previews
            from .presets_data import PRESETS as ALL_PRESETS
            reload_previews(ALL_PRESETS)
            # Force UI redraw
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    area.tag_redraw()
        except Exception as exc:
            print("[LSM] Could not reload previews: %s" % exc)
    else:
        print("[LSM] WARNING: render process ended (code=%d) but sentinel not found." % retcode)

    return None   # stop timer


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

OPERATORS = (
    LSM_OT_ApplyPreset,
    LSM_OT_SelectLSMLights,
    LSM_OT_RemoveLSMLights,
    LSM_OT_ResetModifiers,
    LSM_OT_SetCategory,
    LSM_OT_DiagnoseLights,
    LSM_OT_VerifyActivePreset,
    LSM_OT_RenderPreviews,
)


def register():
    for cls in OPERATORS:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(OPERATORS):
        bpy.utils.unregister_class(cls)
