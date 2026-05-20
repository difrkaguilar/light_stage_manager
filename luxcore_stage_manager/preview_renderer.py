#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  difrkaguilar + Claude (Anthropic)
# Light Stage Manager -- Headless Preview Renderer v2
#
# Invoked by the main Blender instance as a subprocess:
#   blender --background --python preview_renderer.py -- <json_path> <output_dir>
#
# Renders 256x256 PNG per preset.
# Suzanne: front-facing, SubSurf 3, warm material.
# Camera: front-facing, 85mm lens.
# Exposure: auto-compensated per preset to avoid blown-out / underexposed frames.
# World: dark neutral (no sky) -- lights define the look.

import sys, os, json, math

try:
    sep  = sys.argv.index("--")
    args = sys.argv[sep + 1:]
except ValueError:
    print("[LSM-RENDERER] ERROR: No arguments after --")
    sys.exit(1)

if len(args) < 2:
    print("[LSM-RENDERER] ERROR: Expected <json_path> <output_dir>")
    sys.exit(1)

JSON_PATH  = args[0]
OUTPUT_DIR = args[1]

with open(JSON_PATH, "r", encoding="utf-8") as fh:
    PRESETS = json.load(fh)

os.makedirs(OUTPUT_DIR, exist_ok=True)

import bpy
from mathutils import Vector

# ---------------------------------------------------------------------------
# Kelvin -> linear RGB
# ---------------------------------------------------------------------------

def kelvin_to_linear_rgb(k):
    t = max(1000.0, min(12000.0, float(k))) / 100.0
    r = (1.0 if t <= 66 else
         max(0.0, min(1.0, 329.698727446 * ((t - 60) ** -0.1332047592) / 255.0)))
    g = (max(0.0, min(1.0, (99.4708 * math.log(max(1.0, t - 10)) - 161.1196) / 255.0))
         if t <= 66 else
         max(0.0, min(1.0, 288.1222 * ((t - 60) ** -0.0755) / 255.0)))
    b = (1.0 if t >= 66 else 0.0 if t <= 19 else
         max(0.0, min(1.0, (138.5177 * math.log(t - 10) - 305.0448) / 255.0)))
    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (lin(r), lin(g), lin(b))


def look_at(obj, target):
    d = target - obj.location
    if d.length > 1e-6:
        obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


# ---------------------------------------------------------------------------
# Scene setup
# ---------------------------------------------------------------------------

def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    for mat in list(bpy.data.materials):
        if mat.users == 0:
            bpy.data.materials.remove(mat)


def add_suzanne():
    """Monkey head front-facing (-Y toward camera), SubSurf 3, warm material."""
    # In Blender, Suzanne faces -Y by default.
    # Camera is at Y=-N, so no rotation needed for a direct front view.
    bpy.ops.mesh.primitive_monkey_add(
        size=1.0,
        location=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0),
    )
    obj = bpy.context.active_object
    obj.name = "Suzanne_LSM"

    # Smooth shading
    bpy.ops.object.shade_smooth()

    # Subdivision Surface level 3
    mod = obj.modifiers.new("SubSurf", "SUBSURF")
    mod.levels         = 3
    mod.render_levels  = 3
    mod.subdivision_type = "CATMULL_CLARK"

    # Warm off-white Principled BSDF material
    mat = bpy.data.materials.new("Suzanne_Mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.72, 0.62, 0.54, 1.0)
        bsdf.inputs["Roughness"].default_value  = 0.42
        try:
            bsdf.inputs["Specular IOR Level"].default_value = 0.28
        except Exception:
            try:
                bsdf.inputs["Specular"].default_value = 0.28
            except Exception:
                pass
    obj.data.materials.append(mat)
    return obj


def add_floor():
    """Neutral grey floor."""
    bpy.ops.mesh.primitive_plane_add(size=14.0, location=(0.0, 0.0, -0.52))
    obj = bpy.context.active_object
    obj.name = "Floor_LSM"
    mat = bpy.data.materials.new("Floor_Mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.18, 0.18, 0.18, 1.0)
        bsdf.inputs["Roughness"].default_value  = 0.88
    obj.data.materials.append(mat)
    return obj


def setup_camera(scene):
    """Front-facing camera: X=0, Y=-3.8, Z=0.6, aimed just above origin. 85mm lens."""
    bpy.ops.object.camera_add(location=(0.0, -3.8, 0.6))
    cam = bpy.context.active_object
    cam.name = "Preview_Cam"
    look_at(cam, Vector((0.0, 0.0, 0.05)))
    cam.data.lens       = 85.0
    cam.data.clip_start = 0.1
    cam.data.clip_end   = 100.0
    scene.camera = cam
    return cam


def configure_render(scene, size=256):
    """Cycles render settings for clean, fast thumbnails."""
    scene.render.engine               = "CYCLES"
    scene.render.resolution_x         = size
    scene.render.resolution_y         = size
    scene.render.resolution_percentage = 100
    scene.render.film_transparent     = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode  = "RGB"
    scene.render.image_settings.color_depth = "8"

    cyc = scene.cycles
    cyc.samples               = 128
    cyc.use_denoising         = True
    cyc.denoiser              = "OPENIMAGEDENOISE"
    cyc.use_adaptive_sampling = True
    cyc.adaptive_threshold    = 0.02
    cyc.device                = "CPU"

    # Color management: AgX (Blender 4.x) avoids clipping highlights
    cm = scene.view_settings
    for vt in ("AgX", "Filmic", "Standard"):
        try:
            cm.view_transform = vt
            break
        except Exception:
            continue
    cm.look   = "None"
    cm.gamma  = 1.0


def setup_world(scene):
    """Dark near-black world. Lights define the scene exclusively."""
    world = scene.world
    if world is None:
        world = bpy.data.worlds.new("LSM_World")
        scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value    = (0.02, 0.02, 0.025, 1.0)
        bg.inputs["Strength"].default_value = 0.0   # no ambient contribution


# ---------------------------------------------------------------------------
# Per-preset exposure compensation
# ---------------------------------------------------------------------------

_EV_REFERENCE_W = 700.0   # 700 W total → EV 0  (typical 3-light portrait)

def compute_exposure(lights):
    """EV compensation: -log2(total_W / reference). Clamped [-5, +3.5]."""
    total = sum(float(l.get("energy") or 100) for l in lights)
    if total <= 0:
        return 0.0
    ev = -math.log2(total / _EV_REFERENCE_W)
    return max(-5.0, min(3.5, ev))


# ---------------------------------------------------------------------------
# Light creation
# ---------------------------------------------------------------------------

def create_lights(lights_data, scene):
    created = []
    for light in lights_data:
        ltype  = light.get("type") or "AREA"
        lname  = "PRV_" + (light.get("name") or "Light")
        energy = float(light.get("energy") or 100.0)

        try:
            ld = bpy.data.lights.new(name=lname, type=ltype)
        except Exception as exc:
            print("[LSM-RENDERER]   Light creation failed: %s" % exc)
            continue

        ld.energy = energy

        if ltype == "AREA":
            shape = light.get("shape") or "RECTANGLE"
            ld.shape = shape
            ld.size  = float(light.get("size") or 1.0)
            if shape in ("RECTANGLE", "ELLIPSE"):
                ld.size_y = float(light.get("size_y") or light.get("size") or 1.0)
        elif ltype == "SPOT":
            ld.spot_size  = float(light.get("size") or math.radians(30))
            ld.spot_blend = float(light.get("spot_blend") or 0.15)
        elif ltype == "SUN":
            ld.angle = float(light.get("size") or 0.009)
        elif ltype == "POINT":
            ld.shadow_soft_size = float(light.get("size") or 0.05)

        kelvin    = light.get("kelvin")
        color_rgb = light.get("color")
        if kelvin is not None:
            ld.color = kelvin_to_linear_rgb(float(kelvin))
        elif color_rgb and any(v is not None for v in (color_rgb or [])):
            ld.color = tuple(float(v or 0.0) for v in color_rgb[:3])
        else:
            ld.color = (1.0, 1.0, 1.0)

        obj = bpy.data.objects.new(name=lname, object_data=ld)
        scene.collection.objects.link(obj)

        loc = light.get("location") or [0.0, 0.0, 3.0]
        obj.location = Vector(loc)

        tgt = light.get("target")
        if tgt is not None and ltype != "POINT":
            look_at(obj, Vector(tgt))

        created.append(obj)
    return created


def remove_lights(objects):
    for obj in objects:
        try:
            data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.lights.remove(data)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

print()
print("[LSM-RENDERER] ========================================")
print("[LSM-RENDERER]  Light Stage Manager - Preview Renderer")
print("[LSM-RENDERER]  Presets: %d  Output: %s" % (len(PRESETS), OUTPUT_DIR))
print("[LSM-RENDERER] ========================================")

scene = bpy.context.scene
clear_scene()
add_suzanne()
add_floor()
setup_camera(scene)
configure_render(scene, size=256)
setup_world(scene)

rendered = 0
skipped  = 0
failed   = 0

for idx, preset in enumerate(PRESETS):
    pid    = preset.get("id") or ""
    name   = preset.get("name") or pid
    lights = preset.get("lights") or []
    outpng = os.path.join(OUTPUT_DIR, pid + ".png")

    if os.path.exists(outpng):
        print("[LSM-RENDERER] [%02d/%02d] SKIP  %s" % (idx+1, len(PRESETS), pid))
        skipped += 1
        continue

    # Per-preset exposure compensation
    ev       = compute_exposure(lights)
    total_w  = sum(float(l.get("energy") or 100) for l in lights)
    scene.view_settings.exposure = ev

    print("[LSM-RENDERER] [%02d/%02d] RENDER %-28s | %d lights | %.0fW | EV%+.1f" % (
        idx+1, len(PRESETS), name, len(lights), total_w, ev))

    light_objs = create_lights(lights, scene)
    scene.render.filepath = outpng

    try:
        bpy.ops.render.render(write_still=True)
        rendered += 1
    except Exception as exc:
        print("[LSM-RENDERER]         ERROR: %s" % exc)
        failed += 1
    finally:
        remove_lights(light_objs)
        # Reset exposure for next preset
        scene.view_settings.exposure = 0.0

print()
print("[LSM-RENDERER] ========================================")
print("[LSM-RENDERER]  Done: rendered=%d  skipped=%d  failed=%d" % (
    rendered, skipped, failed))
print("[LSM-RENDERER] ========================================")

sentinel = os.path.join(OUTPUT_DIR, ".render_complete")
with open(sentinel, "w") as fh:
    fh.write("rendered=%d skipped=%d failed=%d\n" % (rendered, skipped, failed))
