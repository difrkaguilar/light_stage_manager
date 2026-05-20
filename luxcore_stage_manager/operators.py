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

from .presets_data import PRESETS, PRESETS_BY_ID
from .scene_builder import apply_preset, remove_lsm_lights
from .constants import LSM_PREFIX

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

def _blender_executable() -> str:
    return sys.executable   # bpy.app.binary_path would be ideal but may not exist
                            # sys.executable inside Blender IS the blender binary


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
            created = apply_preset(
                preset            = preset,
                scene             = context.scene,
                intensity_mult    = float(props.intensity_multiplier),
                temp_offset       = float(props.temperature_offset),
                clear_existing    = bool(props.clear_existing),
                configure_luxcore = bool(props.auto_configure_luxcore),
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
            n = sum(1 for o in context.scene.objects
                    if o.name.startswith(LSM_PREFIX) and not o.select_set(True))
            # select_set returns None, so count differently
            n = sum(1 for o in context.scene.objects if o.name.startswith(LSM_PREFIX))
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
            p.intensity_multiplier = 1.0
            p.temperature_offset   = 0.0
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
                ktemp  = getattr(lx_ld, "color_temperature", "N/A")
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
    LSM_OT_RenderPreviews,
)


def register():
    for cls in OPERATORS:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(OPERATORS):
        bpy.utils.unregister_class(cls)
