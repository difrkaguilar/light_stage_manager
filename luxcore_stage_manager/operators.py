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

from .presets_data import PRESETS, PRESETS_BY_ID, CATEGORIES
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


class LSM_OT_AdjustFillRatio(Operator):
    """Apply the current fill_ratio to in-scene LSM lights.

    Called automatically by the fill_ratio property update callback.
    Can also be invoked manually via F3 search.
    """
    bl_idname  = "lsm.adjust_fill_ratio"
    bl_label   = "Adjust Fill Ratio"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return any(o.name.startswith(LSM_PREFIX) and o.type == "LIGHT"
                   for o in context.scene.objects)

    def execute(self, context):
        from .scene_builder import apply_fill_ratio
        props = context.scene.lsm_props
        n = apply_fill_ratio(
            scene          = context.scene,
            fill_ratio     = float(props.fill_ratio),
            intensity_mult = float(props.intensity_multiplier),
        )
        if n == 0:
            self.report({"INFO"}, "LSM: No fill/rim lights found — key light required")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# LSM_OT_SavePresetFromScene
# ---------------------------------------------------------------------------

def _user_presets_path() -> str:
    import os
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), "user_presets.json")


def load_user_presets() -> list:
    """Load user presets from disk. Returns [] if file absent or corrupt."""
    import json, os
    path = _user_presets_path()
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except Exception as exc:
        log.warning("[LSM] load_user_presets: %s", exc)
        return []


def save_user_presets(presets: list) -> bool:
    """Persist user presets list to disk. Returns True on success."""
    import json
    try:
        with open(_user_presets_path(), "w", encoding="utf-8") as fh:
            json.dump(presets, fh, indent=2, ensure_ascii=False)
        return True
    except Exception as exc:
        log.error("[LSM] save_user_presets: %s", exc)
        return False


def _serialize_light(obj, scene_origin, scene_scale: float) -> dict | None:
    """Convert a scene light Object back to a normalised LSM descriptor dict."""
    from mathutils import Vector
    if obj.type != "LIGHT":
        return None
    ld         = obj.data
    light_type = ld.type
    origin     = Vector(scene_origin)
    raw_loc    = Vector(obj.location) - origin
    energy_scale = (scene_scale ** 2) if light_type != "SUN" else scene_scale
    raw_energy   = ld.energy / max(0.001, energy_scale)

    desc: dict = {
        "name":         obj.name.replace(LSM_PREFIX, "", 1),
        "type":         light_type,
        "location":     tuple(round(v / max(0.001, scene_scale), 4) for v in raw_loc),
        "target":       None,
        "energy":       round(raw_energy, 2),
        "kelvin":       None,
        "color":        tuple(round(c, 4) for c in ld.color[:3]),
        "use_shadow":   ld.use_shadow,
        "luxcore_gain": 1.0,
        "role":         obj.get("lsm_role", "fill"),
    }
    if light_type == "AREA":
        desc["shape"]  = ld.shape
        desc["size"]   = round(ld.size / scene_scale, 4)
        desc["size_y"] = round(getattr(ld, "size_y", ld.size) / scene_scale, 4)
    elif light_type == "SPOT":
        desc["size"]       = round(ld.spot_size, 4)
        desc["spot_blend"] = round(ld.spot_blend, 4)
    elif light_type == "SUN":
        desc["size"] = round(ld.angle, 4)
    elif light_type == "POINT":
        desc["size"] = round(ld.shadow_soft_size / scene_scale, 4)
    # Recover aim from rotation
    if light_type != "POINT":
        fwd = obj.matrix_world.to_3x3() @ Vector((0.0, 0.0, -1.0))
        aim = Vector(obj.location) + fwd
        aim_n = (aim - origin) / max(0.001, scene_scale)
        desc["target"] = tuple(round(v, 4) for v in aim_n)
    return desc


# ---------------------------------------------------------------------------
# LSM_OT_SetLightDiffuse / SetLightSpecular / SetLightKelvin / ToggleLightTarget
# ---------------------------------------------------------------------------

def _get_diffuse(light_data) -> bool:
    """Return current diffuse-enabled state regardless of Blender version."""
    v = getattr(light_data, "diffuse_factor", None)
    if v is not None:
        return v > 0.5
    return bool(getattr(light_data, "use_diffuse", True))


def _get_specular(light_data) -> bool:
    """Return current specular-enabled state regardless of Blender version."""
    v = getattr(light_data, "specular_factor", None)
    if v is not None:
        return v > 0.5
    return bool(getattr(light_data, "use_specular", True))

class LSM_OT_SetLightDiffuse(Operator):
    """Toggle diffuse contribution for one LSM light (Blender 4.x: diffuse_factor)."""
    bl_idname  = "lsm.set_light_diffuse"
    bl_label   = "Toggle Diffuse"
    bl_options = {"REGISTER", "UNDO"}

    light_name: bpy.props.StringProperty()
    value:      bpy.props.BoolProperty(default=True)

    def execute(self, context):
        obj = context.scene.objects.get(self.light_name)
        if obj is None or obj.type != "LIGHT":
            return {"CANCELLED"}
        ld = obj.data
        # Blender 4.x uses diffuse_factor (float); older used use_diffuse (bool)
        try:
            ld.diffuse_factor = 1.0 if self.value else 0.0
        except AttributeError:
            try:
                ld.use_diffuse = self.value
            except AttributeError:
                pass
        from .lxc_compat import set_lxc_light_ray_visibility
        spec_val = _get_specular(ld)
        set_lxc_light_ray_visibility(obj, diffuse=self.value, specular=spec_val)
        obj["lsm_use_diffuse"] = self.value
        return {"FINISHED"}


class LSM_OT_SetLightSpecular(Operator):
    """Toggle specular contribution for one LSM light (Blender 4.x: specular_factor)."""
    bl_idname  = "lsm.set_light_specular"
    bl_label   = "Toggle Specular"
    bl_options = {"REGISTER", "UNDO"}

    light_name: bpy.props.StringProperty()
    value:      bpy.props.BoolProperty(default=True)

    def execute(self, context):
        obj = context.scene.objects.get(self.light_name)
        if obj is None or obj.type != "LIGHT":
            return {"CANCELLED"}
        ld = obj.data
        try:
            ld.specular_factor = 1.0 if self.value else 0.0
        except AttributeError:
            try:
                ld.use_specular = self.value
            except AttributeError:
                pass
        from .lxc_compat import set_lxc_light_ray_visibility
        diff_val = _get_diffuse(ld)
        set_lxc_light_ray_visibility(obj, diffuse=diff_val, specular=self.value)
        obj["lsm_use_specular"] = self.value
        return {"FINISHED"}


class LSM_OT_SetLightKelvin(Operator):
    """Set the colour temperature of one LSM light in Kelvin.

    Updates lsm_kelvin and lsm_base_color then calls live_update so gel
    and global temp offset are applied on top of the new base colour.
    """
    bl_idname  = "lsm.set_light_kelvin"
    bl_label   = "Set Light Temperature"
    bl_options = {"REGISTER", "UNDO"}

    light_name: bpy.props.StringProperty()
    kelvin:     bpy.props.FloatProperty(
        name="Kelvin", default=5600.0,
        min=1000.0, max=12000.0, step=100, precision=0)

    def execute(self, context):
        from .scene_builder import kelvin_to_linear_rgb
        from .constants import KELVIN_MIN, KELVIN_MAX
        obj = context.scene.objects.get(self.light_name)
        if obj is None or obj.type != "LIGHT":
            return {"CANCELLED"}
        k = max(float(KELVIN_MIN), min(float(KELVIN_MAX), float(self.kelvin)))
        obj["lsm_kelvin"]     = k
        obj["lsm_base_color"] = kelvin_to_linear_rgb(k)
        bpy.ops.lsm.live_update()
        return {"FINISHED"}

    def invoke(self, context, event):
        obj = context.scene.objects.get(self.light_name)
        if obj:
            stored_k = float(obj.get("lsm_kelvin", 5600.0))
            if stored_k > 0:
                self.kelvin = stored_k
        return context.window_manager.invoke_props_popup(self, event)

    def draw(self, context):
        self.layout.prop(self, "kelvin", slider=True)


class LSM_OT_ToggleLightTarget(Operator):
    """Create or remove a target Empty for an LSM light.

    When created: adds LSM_Target_<Name> Empty at the light's current aim
    point and a TRACK_TO constraint (-Z → target). Move the Empty to
    interactively reorient the light.

    When removed: deletes the constraint and the Empty.
    """
    bl_idname  = "lsm.toggle_light_target"
    bl_label   = "Toggle Light Target"
    bl_options = {"REGISTER", "UNDO"}

    light_name: bpy.props.StringProperty()
    _TARGET_PREFIX = "LSM_Target_"

    def execute(self, context):
        obj = context.scene.objects.get(self.light_name)
        if obj is None or obj.type != "LIGHT":
            return {"CANCELLED"}
        short       = obj.name.replace(LSM_PREFIX, "", 1)
        target_name = self._TARGET_PREFIX + short
        existing    = context.scene.objects.get(target_name)
        if existing:
            self._remove_target(obj, existing)
        else:
            self._create_target(obj, target_name, context)
        return {"FINISHED"}

    def _create_target(self, light_obj, target_name, context):
        from mathutils import Vector
        fwd    = light_obj.matrix_world.to_3x3() @ Vector((0.0, 0.0, -1.0))
        aim_pt = Vector(light_obj.location) + fwd * 2.0

        empty                    = bpy.data.objects.new(target_name, None)
        empty.empty_display_type = "PLAIN_AXES"
        empty.empty_display_size = 0.15
        empty.location           = aim_pt
        empty["lsm_role"]        = "target"
        empty["lsm_for_light"]   = light_obj.name
        empty["lsm_preset_id"]   = light_obj.get("lsm_preset_id", "")

        for col in light_obj.users_collection:
            col.objects.link(empty); break
        else:
            context.scene.collection.objects.link(empty)

        ct            = light_obj.constraints.new("TRACK_TO")
        ct.name       = "LSM_TrackTo"
        ct.target     = empty
        ct.track_axis = "TRACK_NEGATIVE_Z"
        ct.up_axis    = "UP_Y"

        light_obj["lsm_has_target"] = True
        log.debug("[LSM] Target created: %r", target_name)

    def _remove_target(self, light_obj, empty):
        ct = light_obj.constraints.get("LSM_TrackTo")
        if ct:
            light_obj.constraints.remove(ct)
        bpy.data.objects.remove(empty, do_unlink=True)
        light_obj["lsm_has_target"] = False
        log.debug("[LSM] Target removed for %r", light_obj.name)


class LSM_OT_LiveUpdate(Operator):
    """Apply all live adjustments (intensity, temperature, gel, fill ratio)
    to in-scene LSM lights. Called automatically by property update callbacks.
    """
    bl_idname  = "lsm.live_update"
    bl_label   = "LSM Live Update"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        return any(o.name.startswith(LSM_PREFIX) and o.type == "LIGHT"
                   for o in context.scene.objects)

    def execute(self, context):
        from .scene_builder import apply_live_adjustments
        props = context.scene.lsm_props
        apply_live_adjustments(
            scene          = context.scene,
            intensity_mult = float(props.intensity_multiplier),
            temp_offset    = float(props.temperature_offset),
            gel_id         = props.gel_preset,
            fill_ratio     = float(props.fill_ratio),
        )
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# LSM_OT_SoloLight / LSM_OT_ExitSolo
# ---------------------------------------------------------------------------

_SOLO_VISIBILITY_KEY = "lsm_solo_visibility_stack"


class LSM_OT_SoloLight(Operator):
    """Temporarily hide all other LSM lights so this one can be evaluated alone.

    Saves the current visibility state of all LSM lights so it can be restored
    exactly on exit. While in Solo mode additional lights can be toggled on.
    """
    bl_idname  = "lsm.solo_light"
    bl_label   = "Solo Light"
    bl_options = {"REGISTER", "UNDO"}

    light_name: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        return any(o.name.startswith(LSM_PREFIX) and o.type == "LIGHT"
                   for o in context.scene.objects)

    def execute(self, context):
        import json
        scene = context.scene
        lsm_lights = [o for o in scene.objects
                      if o.name.startswith(LSM_PREFIX) and o.type == "LIGHT"]

        # Save current visibility state if not already in Solo mode
        if _SOLO_VISIBILITY_KEY not in bpy.app.driver_namespace:
            state = {o.name: (o.hide_viewport, o.hide_render)
                     for o in lsm_lights}
            bpy.app.driver_namespace[_SOLO_VISIBILITY_KEY] = state
            log.debug("[LSM] Solo: saved state for %d lights", len(state))

        # Hide all except the target
        for obj in lsm_lights:
            is_target = (obj.name == self.light_name)
            obj.hide_viewport = not is_target
            obj.hide_render   = not is_target

        # Store which light is soloed on the scene for the panel to read
        scene["lsm_solo_active"] = self.light_name
        return {"FINISHED"}


class LSM_OT_SoloToggle(Operator):
    """While in Solo mode, toggle an additional light on or off."""
    bl_idname  = "lsm.solo_toggle"
    bl_label   = "Toggle in Solo"
    bl_options = {"REGISTER", "UNDO"}

    light_name: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        return _SOLO_VISIBILITY_KEY in bpy.app.driver_namespace

    def execute(self, context):
        obj = context.scene.objects.get(self.light_name)
        if obj:
            obj.hide_viewport = not obj.hide_viewport
            obj.hide_render   = obj.hide_viewport
        return {"FINISHED"}


class LSM_OT_ExitSolo(Operator):
    """Exit Solo mode and restore previous light visibility."""
    bl_idname  = "lsm.exit_solo"
    bl_label   = "Exit Solo"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _SOLO_VISIBILITY_KEY in bpy.app.driver_namespace

    def execute(self, context):
        state = bpy.app.driver_namespace.pop(_SOLO_VISIBILITY_KEY, {})
        for name, (hide_vp, hide_rnd) in state.items():
            obj = context.scene.objects.get(name)
            if obj:
                obj.hide_viewport = hide_vp
                obj.hide_render   = hide_rnd

        context.scene.pop("lsm_solo_active", None)
        log.debug("[LSM] Solo: restored %d lights", len(state))
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# LSM_OT_BakeIntensity
# ---------------------------------------------------------------------------

class LSM_OT_BakeIntensity(Operator):
    """Bake the current intensity multiplier into individual light energies.

    Writes the current scaled energy values into each LSM light's data and
    resets ``intensity_multiplier`` to 1.0. Also updates ``lsm_raw_energy``
    so subsequent adjustments start from the baked values.

    Use this when you want to fine-tune individual lights after setting the
    overall exposure — prevents the multiplier from stacking on re-apply.
    """
    bl_idname  = "lsm.bake_intensity"
    bl_label   = "Bake Intensity"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        props = getattr(context.scene, "lsm_props", None)
        if props is None:
            return False
        return (abs(props.intensity_multiplier - 1.0) > 0.001 and
                any(o.name.startswith(LSM_PREFIX) and o.type == "LIGHT"
                    for o in context.scene.objects))

    def execute(self, context):
        scene = context.scene
        props = scene.lsm_props
        mult  = float(props.intensity_multiplier)

        n = 0
        for obj in scene.objects:
            if not (obj.name.startswith(LSM_PREFIX) and obj.type == "LIGHT"):
                continue
            # Bake current energy (already scaled by live_update) into raw
            obj["lsm_raw_energy"] = obj.data.energy   # already at mult×raw
            n += 1

        # Reset multiplier — raw values now carry the baked energy
        props.intensity_multiplier = 1.0
        self.report({"INFO"}, "LSM: Baked intensity into %d lights (×%.2f)" % (n, mult))
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# LSM_OT_AdjustFillRatio — kept for backward compatibility, delegates to LiveUpdate
# ---------------------------------------------------------------------------

class LSM_OT_AdjustFillRatio(Operator):
    """Kept for backward compatibility. Delegates to lsm.live_update."""
    bl_idname  = "lsm.adjust_fill_ratio"
    bl_label   = "Adjust Fill Ratio"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        return any(o.name.startswith(LSM_PREFIX) and o.type == "LIGHT"
                   for o in context.scene.objects)

    def execute(self, context):
        bpy.ops.lsm.live_update()
        return {"FINISHED"}


class LSM_OT_SavePresetFromScene(Operator):
    """Save the current LSM light rig as a user preset."""
    bl_idname  = "lsm.save_preset_from_scene"
    bl_label   = "Save Rig as Preset"
    bl_options = {"REGISTER"}

    preset_name: bpy.props.StringProperty(
        name="Name", default="My Preset")
    preset_category: bpy.props.EnumProperty(
        name="Category", items=list(CATEGORIES)[1:], default="CREATIVE")
    preset_description: bpy.props.StringProperty(
        name="Description", default="")

    @classmethod
    def poll(cls, context):
        return any(o.name.startswith(LSM_PREFIX) and o.type == "LIGHT"
                   for o in context.scene.objects)

    def invoke(self, context, event):
        props = getattr(context.scene, "lsm_props", None)
        if props and props.active_preset_id:
            from .presets_data import PRESETS_BY_ID
            p = PRESETS_BY_ID.get(props.active_preset_id)
            if p:
                self.preset_name     = p["name"] + " (custom)"
                self.preset_category = p.get("category", "CREATIVE")
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "preset_name")
        layout.prop(self, "preset_category")
        layout.prop(self, "preset_description")
        lsm_lights = [o for o in context.scene.objects
                      if o.name.startswith(LSM_PREFIX) and o.type == "LIGHT"]
        if lsm_lights:
            box = layout.box()
            box.scale_y = 0.8
            box.label(text="%d lights will be saved:" % len(lsm_lights), icon="LIGHT")
            for obj in lsm_lights[:8]:
                box.label(text="  %s  [%s]  %.0fW" % (
                    obj.name, obj.get("lsm_role","?"), obj.data.energy))

    def execute(self, context):
        import time
        lsm_lights = [o for o in context.scene.objects
                      if o.name.startswith(LSM_PREFIX) and o.type == "LIGHT"]
        if not lsm_lights:
            self.report({"WARNING"}, "LSM: No LSM lights in scene")
            return {"CANCELLED"}

        scene_scale, scene_origin = _compute_scale_and_origin(context)
        light_descs = [d for d in
                       (_serialize_light(o, scene_origin, scene_scale) for o in lsm_lights)
                       if d is not None]
        if not light_descs:
            self.report({"ERROR"}, "LSM: Could not serialise any lights")
            return {"CANCELLED"}

        safe = self.preset_name.lower()
        for ch in " /\\()[]{}": safe = safe.replace(ch, "_")
        pid = "user_%s_%s" % (safe[:24], str(int(time.time()))[-5:])

        new_preset = {
            "id":          pid,
            "name":        self.preset_name.strip() or "User Preset",
            "category":    self.preset_category,
            "description": self.preset_description.strip(),
            "is_user":     True,
            "lights":      light_descs,
            "env_light":   None,
            "luxcore_cfg": {"engine":"PATH","path_depth":8,"halt_samples":256,"denoiser":True},
        }

        from .presets_data import validate_preset
        errs = validate_preset(new_preset)
        if errs:
            self.report({"ERROR"}, "LSM: Validation — %s" % "; ".join(errs))
            return {"CANCELLED"}

        user_presets = load_user_presets()
        user_presets = [p for p in user_presets if p.get("name") != new_preset["name"]]
        user_presets.append(new_preset)

        if not save_user_presets(user_presets):
            self.report({"ERROR"}, "LSM: Could not write user_presets.json")
            return {"CANCELLED"}

        try:
            from .presets_data import reload_user_presets
            reload_user_presets()
        except Exception:
            pass

        self.report({"INFO"}, "LSM: '%s' saved (%d lights)" % (
            new_preset["name"], len(light_descs)))
        return {"FINISHED"}


class LSM_OT_DeleteUserPreset(Operator):
    """Delete the selected user preset (confirmation required)."""
    bl_idname  = "lsm.delete_user_preset"
    bl_label   = "Delete User Preset"
    bl_options = {"REGISTER"}

    preset_id: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        props = getattr(context.scene, "lsm_props", None)
        if props is None:
            return False
        from .presets_data import PRESETS_BY_ID
        return PRESETS_BY_ID.get(props.active_preset_id, {}).get("is_user", False)

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        from .presets_data import reload_user_presets
        pid = self.preset_id or getattr(
            context.scene.lsm_props, "active_preset_id", "")
        if not pid:
            self.report({"WARNING"}, "LSM: No preset selected"); return {"CANCELLED"}
        presets = [p for p in load_user_presets() if p.get("id") != pid]
        save_user_presets(presets)
        reload_user_presets()
        self.report({"INFO"}, "LSM: User preset deleted")
        return {"FINISHED"}


class LSM_OT_GenerateAssetLibrary(Operator):
    """Generate (or regenerate) the LSM_Assets.blend file for the Asset Browser.

    Creates one World asset per preset with full metadata (description,
    catalog UUID, tags).  The assets/ directory can then be registered as
    an Asset Library in Blender Preferences > File Paths > Asset Libraries.
    """
    bl_idname  = "lsm.generate_asset_library"
    bl_label   = "Generate Asset Library"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return context is not None

    def execute(self, context):
        from .asset_builder import generate_asset_library, assets_blend_path
        import os

        def _report(level, msg):
            lvl_map = {"INFO": "INFO", "WARNING": "WARNING", "ERROR": "ERROR"}
            self.report({lvl_map.get(level, "INFO")}, "LSM: " + msg)

        success, message = generate_asset_library(report_fn=_report)

        if success:
            # Prompt the user with the path they need to register
            path = os.path.dirname(assets_blend_path())
            self.report({"INFO"},
                        "LSM: Library ready. Register this folder as an Asset Library: %s" % path)
            return {"FINISHED"}
        else:
            return {"CANCELLED"}


# ---------------------------------------------------------------------------
# LSM_OT_ApplyFromAsset
# ---------------------------------------------------------------------------

class LSM_OT_ApplyFromAsset(Operator):
    """Apply the LSM preset that is currently selected in the Asset Browser.

    The operator reads ``context.asset`` (Blender 4.0+), resolves the preset
    ID from the World's custom property or by name matching, then delegates
    to the standard Apply pipeline (scale-aware, engine-aware).
    """
    bl_idname  = "lsm.apply_from_asset"
    bl_label   = "Apply from Asset Browser"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        from .asset_builder import is_lsm_asset
        return is_lsm_asset(context)

    def execute(self, context):
        from .asset_builder import get_active_lsm_asset

        pid = get_active_lsm_asset(context)
        if not pid:
            self.report({"WARNING"}, "LSM: No LSM asset selected in Asset Browser")
            return {"CANCELLED"}

        preset = PRESETS_BY_ID.get(pid)
        if preset is None:
            self.report({"ERROR"},
                        "LSM: Preset '%s' not found — regenerate the Asset Library" % pid)
            return {"CANCELLED"}

        # Sync the N-panel selection so the user sees the active preset there too
        props = getattr(context.scene, "lsm_props", None)
        if props is not None:
            props.active_preset_id = pid
            # Also sync the category filter so the preset is visible in the list
            cat = preset.get("category", "ALL")
            if props.active_category not in ("ALL", cat):
                props.active_category = "ALL"

        # Delegate to the standard apply pipeline
        try:
            scene_scale, scene_origin = _compute_scale_and_origin(context)
            created = apply_preset(
                preset             = preset,
                scene              = context.scene,
                intensity_mult     = float(props.intensity_multiplier) if props else 1.0,
                temp_offset        = float(props.temperature_offset)   if props else 0.0,
                clear_existing     = bool(props.clear_existing)        if props else True,
                configure_luxcore  = bool(props.auto_configure_luxcore) if props else True,
                scene_scale        = scene_scale,
                scene_origin       = scene_origin,
            )
        except Exception as exc:
            log.exception("[LSM] apply_from_asset failed for %r", pid)
            self.report({"ERROR"}, "LSM: Error applying '%s': %s" % (
                preset.get("name", pid), exc))
            return {"CANCELLED"}

        n = len(created)
        self.report({"INFO"}, "LSM: '%s' applied from Asset Browser — %d light%s" % (
            preset.get("name", pid), n, "s" if n != 1 else ""))
        return {"FINISHED"}


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
    LSM_OT_SetLightDiffuse,
    LSM_OT_SetLightSpecular,
    LSM_OT_SetLightKelvin,
    LSM_OT_ToggleLightTarget,
    LSM_OT_LiveUpdate,
    LSM_OT_SoloLight,
    LSM_OT_SoloToggle,
    LSM_OT_ExitSolo,
    LSM_OT_BakeIntensity,
    LSM_OT_AdjustFillRatio,
    LSM_OT_SavePresetFromScene,
    LSM_OT_DeleteUserPreset,
    LSM_OT_GenerateAssetLibrary,
    LSM_OT_ApplyFromAsset,
)


def register():
    for cls in OPERATORS:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(OPERATORS):
        bpy.utils.unregister_class(cls)
