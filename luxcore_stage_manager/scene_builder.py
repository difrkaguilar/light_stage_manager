# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  difrkaguilar + Claude (Anthropic)
# LuxCore Stage Manager -- Scene Builder
#
# Engine-aware: detects active render engine at apply time and
# routes to LuxCore or Cycles property application accordingly.
# ONE preset definition drives both engines.
#
# Architecture:
#   Phase 1 (all engines): Blender-native props (energy, size, color, shape)
#   Phase 2a (LuxCore):   apply_lxc_light_props() + apply_lxc_object_visibility()
#   Phase 2b (Cycles):    apply_cycles_light_props() (spread, MIS, bounces)

from __future__ import annotations
import math
import logging

import bpy
from mathutils import Vector

from .constants import (
    LSM_PREFIX, LSM_COLLECTION_PREFIX,
    KELVIN_MIN, KELVIN_MAX,
    LXC_AREA_GAIN_SCALE, LXC_SPOT_GAIN_SCALE,
    LXC_POINT_GAIN_SCALE, LXC_SUN_GAIN_SCALE,
    LUXCORE_ENGINE_ID, CYCLES_LIKE_ENGINES,
)
from .lxc_compat import (
    apply_lxc_light_props,
    apply_lxc_object_visibility,
    LuxCoreSceneProxy,
    LuxCoreWorldProxy,
    is_active_engine as lxc_is_active,
)
from .cycles_compat import (
    apply_cycles_light_props,
    apply_cycles_sky,
    reset_cycles_world,
    CyclesSceneProxy,
    is_cycles_like,
)

log = logging.getLogger(__name__)

_GAIN_SCALE = {
    "AREA":  LXC_AREA_GAIN_SCALE,
    "SPOT":  LXC_SPOT_GAIN_SCALE,
    "SUN":   LXC_SUN_GAIN_SCALE,
    "POINT": LXC_POINT_GAIN_SCALE,
}


# ---------------------------------------------------------------------------
# Engine detection
# ---------------------------------------------------------------------------

def detect_engine(scene) -> str:
    """Return 'LUXCORE', 'CYCLES', or 'OTHER' for the active render engine."""
    eng = scene.render.engine
    if eng == LUXCORE_ENGINE_ID:
        return "LUXCORE"
    if eng in CYCLES_LIKE_ENGINES:
        return "CYCLES"
    return "OTHER"


# ---------------------------------------------------------------------------
# Kelvin -> linear RGB
# ---------------------------------------------------------------------------

def kelvin_to_linear_rgb(temperature: float) -> tuple:
    temp = max(KELVIN_MIN, min(KELVIN_MAX, float(temperature))) / 100.0
    red   = (1.0 if temp <= 66
             else max(0.0, min(1.0, 329.698727446*((temp-60.0)**-0.1332047592)/255.0)))
    green = (max(0.0, min(1.0, (99.4708025861*math.log(max(1.0,temp-10.0))-161.1195681661)/255.0))
             if temp <= 66
             else max(0.0, min(1.0, 288.1221695283*((temp-60.0)**-0.0755148492)/255.0)))
    blue  = (1.0 if temp >= 66 else 0.0 if temp <= 19
             else max(0.0, min(1.0, (138.5177312231*math.log(temp-10.0)-305.0447927307)/255.0)))
    def lin(c):
        return c/12.92 if c <= 0.04045 else ((c+0.055)/1.055)**2.4
    return (lin(red), lin(green), lin(blue))


# ---------------------------------------------------------------------------
# Collection helper
# ---------------------------------------------------------------------------

def get_or_create_collection(name: str, parent=None):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        p = parent if parent is not None else bpy.context.scene.collection
        if name not in [c.name for c in p.children]:
            p.children.link(col)
    return col


def _look_at(obj, target: Vector) -> None:
    direction = target - obj.location
    if direction.length < 1e-6:
        return
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


# ---------------------------------------------------------------------------
# Single light creation
# ---------------------------------------------------------------------------

def create_light(descriptor:    dict,
                 collection,
                 engine:        str,
                 intensity_mult: float = 1.0,
                 temp_offset:   float = 0.0,
                 scene_scale:   float = 1.0,
                 scene_origin          = None):
    """Create one light from a preset descriptor for the given engine.

    Scale & targeting model
    -----------------------
    Presets are authored at scene_scale=1.0 (a ~1 m reference object, e.g.
    Suzanne).  When the target object is larger or smaller the rig must adapt:

    * Positions  : scaled linearly then offset by scene_origin.
                   light_world = (preset_location * scene_scale) + scene_origin
    * Light sizes: scaled linearly (AREA size/size_y, SPOT radius, POINT softness)
    * Energy     : scaled by scene_scale² for AREA / SPOT / POINT
                   (inverse-square law: doubling distance needs 4× power).
                   SUN energy scales linearly (parallel rays, distance-independent).
    * Targets    : preset target Vectors are treated as *offsets from origin*
                   after scaling, so the rig always aims at the object, not
                   the global axis:
                   aim_world = (preset_target * scene_scale) + scene_origin

    cycles_energy descriptor key (Opción B dual-calibration)
    ---------------------------------------------------------
    If present, overrides ``energy`` for the Cycles/EEVEE path only.
    LuxCore continues to use ``energy`` × ``luxcore_gain`` as before.
    The cycles_energy value is also scaled by scene_scale².

    Returns:
        Created bpy.types.Object, or None on failure.
    """
    if scene_origin is None:
        scene_origin = Vector((0.0, 0.0, 0.0))
    else:
        scene_origin = Vector(scene_origin)
    scene_scale = max(0.001, float(scene_scale))

    light_type    = descriptor.get("type", "AREA")
    obj_name      = LSM_PREFIX + descriptor.get("name", "Light")
    raw_energy    = max(0.0, float(descriptor.get("energy", 100.0)))
    gain_mult     = max(0.0001, float(descriptor.get("luxcore_gain", 1.0)))
    kelvin        = descriptor.get("kelvin")
    color_rgb     = descriptor.get("color")

    # Energy scaling:  AREA/SPOT/POINT obey inverse-square → scale²
    #                  SUN is a directional source → scale linearly
    energy_scale  = (scene_scale ** 2) if light_type != "SUN" else scene_scale
    actual_energy = raw_energy * max(0.0001, float(intensity_mult)) * energy_scale

    print("[LSM] Creating %s | engine=%s type=%s energy=%.1fW" % (
        obj_name, engine, light_type, actual_energy))

    # =========================================================================
    # PHASE 1: Blender-native properties (shared by all engines)
    # =========================================================================
    try:
        light_data = bpy.data.lights.new(name=obj_name, type=light_type)
    except Exception as exc:
        log.error("[LSM] Failed to create light data %r: %s", obj_name, exc)
        return None

    light_data.energy     = actual_energy
    light_data.use_shadow = bool(descriptor.get("use_shadow", True))

    # Geometry
    if light_type == "AREA":
        shape = descriptor.get("shape", "RECTANGLE")
        light_data.shape  = shape
        light_data.size   = float(descriptor.get("size",  1.0)) * scene_scale
        if shape in ("RECTANGLE", "ELLIPSE"):
            light_data.size_y = float(descriptor.get(
                "size_y", descriptor.get("size", 1.0))) * scene_scale

    elif light_type == "SPOT":
        light_data.spot_size  = float(descriptor.get("size",       math.radians(30)))
        light_data.spot_blend = float(descriptor.get("spot_blend", 0.15))
        # spot_size is an angle — not scaled — but soft shadow radius is spatial
        light_data.shadow_soft_size = float(descriptor.get(
            "shadow_soft_size", 0.0)) * scene_scale

    elif light_type == "SUN":
        light_data.angle = float(descriptor.get("size", 0.009))
        # SUN angle is angular diameter of the disc — no spatial scaling

    elif light_type == "POINT":
        light_data.shadow_soft_size = float(descriptor.get("size", 0.05)) * scene_scale

    # Color (linear RGB via Kelvin conversion — used as native Blender color
    # AND as reference for LuxCore when color_mode is not "temperature")
    adjusted_k = None
    if kelvin is not None:
        adjusted_k = max(KELVIN_MIN, float(kelvin) + float(temp_offset))
        light_data.color = kelvin_to_linear_rgb(adjusted_k)
    elif color_rgb is not None:
        light_data.color = tuple(float(c) for c in color_rgb[:3])
    else:
        light_data.color = (1.0, 1.0, 1.0)

    # =========================================================================
    # PHASE 2: Link object to scene — REQUIRED before setting LuxCore props
    # =========================================================================
    try:
        obj = bpy.data.objects.new(name=obj_name, object_data=light_data)
        collection.objects.link(obj)
    except Exception as exc:
        log.error("[LSM] Failed to link object %r: %s", obj_name, exc)
        bpy.data.lights.remove(light_data)
        return None

    obj.location = Vector(descriptor.get("location", (0.0, 0.0, 3.0))) * scene_scale + scene_origin
    target = descriptor.get("target")
    if target is not None and light_type != "POINT":
        aim_world = Vector(target) * scene_scale + scene_origin
        _look_at(obj, aim_world)

    # Store metadata as custom properties for round-trip serialisation and
    # for the fill-ratio operator to identify light roles without name parsing.
    obj["lsm_role"]         = descriptor.get("role", "fill")   # "key"|"fill"|"rim"|"env"
    obj["lsm_raw_energy"]   = float(raw_energy)                 # preset value at scale=1
    obj["lsm_light_type"]   = light_type
    obj["lsm_preset_id"]    = descriptor.get("_preset_id", "")  # injected by apply_preset

    # =========================================================================
    # PHASE 2a: LuxCore-specific properties (only when LuxCore is active)
    # =========================================================================
    if engine == "LUXCORE":
        gain_scale = _GAIN_SCALE.get(light_type, LXC_AREA_GAIN_SCALE)
        lxc_gain   = max(0.0001, actual_energy * gain_scale * gain_mult)
        kelvin_int = int(adjusted_k) if adjusted_k is not None else None

        apply_lxc_light_props(
            light_data = light_data,
            light_type = light_type,
            lxc_gain   = lxc_gain,
            kelvin     = kelvin_int,
            light_unit = "artistic",
        )
        # Prevent light geometry from appearing as visible object in render
        apply_lxc_object_visibility(obj, visible_to_camera=False)

    # =========================================================================
    # PHASE 2b: Cycles-specific properties (only when Cycles/EEVEE is active)
    # =========================================================================
    elif engine == "CYCLES":
        # Opción B — dual-calibration: if the preset specifies a separate
        # Cycles energy value, apply it now (after link, before MIS/spread).
        # This handles lights whose luxcore_gain has no Cycles equivalent
        # (e.g. POINT practicals with luxcore_gain >> 1.0).
        cycles_energy_raw = descriptor.get("cycles_energy")
        if cycles_energy_raw is not None:
            cycles_actual = (max(0.0, float(cycles_energy_raw))
                             * max(0.0001, float(intensity_mult))
                             * energy_scale)
            light_data.energy = cycles_actual
            log.debug("[LSM-CYC] cycles_energy override: %.1fW → %.1fW (×%.3f mult ×%.3f scale²)",
                      float(cycles_energy_raw), cycles_actual, intensity_mult, energy_scale)

        apply_cycles_light_props(
            light_data  = light_data,
            light_type  = light_type,
            use_mis     = True,
            max_bounces = 1024,
        )
        # Note: Cycles does not need visible_to_camera suppression —
        # Cycles light objects are never visible as meshes in the render.

    return obj


# ---------------------------------------------------------------------------
# Scene management
# ---------------------------------------------------------------------------

def _remove_empty_lsm_collections(scene) -> None:
    """Remove empty LSM collections left behind after deleting generated lights."""
    parent_links = [scene.collection]
    parent_links.extend(bpy.data.collections)

    for col in list(bpy.data.collections):
        if not col.name.startswith(LSM_COLLECTION_PREFIX):
            continue
        if col.objects or col.children:
            continue

        for parent in parent_links:
            try:
                if col.name in parent.children:
                    parent.children.unlink(col)
            except Exception:
                continue

        try:
            bpy.data.collections.remove(col)
        except Exception as exc:
            log.warning("[LSM] Could not remove empty collection %r: %s", col.name, exc)


def remove_lsm_lights(scene) -> int:
    to_delete = [o for o in scene.objects if o.name.startswith(LSM_PREFIX)]
    for obj in to_delete:
        try:
            for col in list(obj.users_collection):
                col.objects.unlink(obj)
            bpy.data.objects.remove(obj, do_unlink=True)
        except Exception as exc:
            log.warning("[LSM] Could not remove %r: %s", obj.name, exc)
    _remove_empty_lsm_collections(scene)
    return len(to_delete)


# ---------------------------------------------------------------------------
# Full preset application — engine-aware entry point
# ---------------------------------------------------------------------------

def apply_fill_ratio(scene, fill_ratio: float, intensity_mult: float = 1.0) -> int:
    """Adjust fill and rim light energies relative to the key light in the scene.

    This operates on LSM_ lights **already in the scene** without re-applying
    the preset.  The key light's energy is left unchanged; fill and rim lights
    are scaled so their energy equals:

        fill_energy = key_energy × fill_ratio

    Args:
        scene:         Target bpy.types.Scene
        fill_ratio:    Target fill-to-key ratio (0.0 = dark fill, 1.0 = equal)
        intensity_mult: Current global intensity multiplier (from lsm_props)

    Returns:
        Number of lights whose energy was updated.
    """
    # Find the key light to use as reference
    key_obj   = None
    key_energy = None
    lsm_lights = [o for o in scene.objects
                  if o.name.startswith(LSM_PREFIX) and o.type == "LIGHT"]

    for obj in lsm_lights:
        if obj.get("lsm_role") == "key":
            key_obj    = obj
            key_energy = obj.data.energy
            break

    if key_obj is None or key_energy is None or key_energy <= 0:
        log.debug("[LSM] apply_fill_ratio: no key light found")
        return 0

    updated = 0
    for obj in lsm_lights:
        role = obj.get("lsm_role", "fill")
        if role in ("fill", "rim"):
            # rim lights get half the fill ratio — they're meant to be subtle
            ratio = fill_ratio if role == "fill" else fill_ratio * 0.5
            new_energy = key_energy * ratio
            obj.data.energy = max(0.001, new_energy)
            updated += 1
            log.debug("[LSM] fill_ratio: %s (%s) → %.1fW", obj.name, role, new_energy)

    return updated


def apply_preset(preset:            dict,
                 scene,
                 intensity_mult:    float = 1.0,
                 temp_offset:       float = 0.0,
                 clear_existing:    bool  = True,
                 configure_luxcore: bool  = True,
                 scene_scale:       float = 1.0,
                 scene_origin             = None) -> list:
    """Apply a preset to the scene, adapting to the active render engine.

    Args:
        preset:            Preset dict from presets_data.PRESETS
        scene:             Target bpy.types.Scene
        intensity_mult:    Global energy multiplier (preserves inter-light ratios)
        temp_offset:       Kelvin offset for all color temperatures
        clear_existing:    Remove existing LSM_ lights before applying
        configure_luxcore: Apply render settings (samples, depth, denoiser).
                           Works for both LuxCore AND Cycles.
        scene_scale:       Reference size of the target object in metres.
                           1.0 = preset defaults (calibrated for ~1 m objects).
                           Computed by the operator from the active/visible
                           object bounding box; can also be set manually.
        scene_origin:      World-space pivot point the rig orbits and aims at.
                           Typically the centre of the active object's bounding
                           box. Defaults to Vector((0,0,0)).

    Returns:
        List of created light Objects.
    """
    if scene_origin is None:
        scene_origin = Vector((0.0, 0.0, 0.0))

    engine = detect_engine(scene)

    print("[LSM] ═══ Applying: '%s' │ Engine: %s │ Lights: %d │ "
          "intensity=%.2f  scale=%.3f  origin=(%.2f,%.2f,%.2f)  K_offset=%+.0f ═══" % (
        preset.get("name", "?"), engine,
        len(preset.get("lights", [])),
        intensity_mult, scene_scale,
        scene_origin.x, scene_origin.y, scene_origin.z,
        temp_offset,
    ))

    if clear_existing:
        remove_lsm_lights(scene)

    col_name   = LSM_COLLECTION_PREFIX + preset.get("name", "Preset")
    collection = get_or_create_collection(col_name, parent=scene.collection)

    created = []
    preset_id = preset.get("id", "")

    # Default role assignment when not explicit in preset descriptor:
    # light[0] → key, light[1] → fill, light[2] → rim, rest → fill
    # Presets can override with an explicit "role" field on any light.
    _DEFAULT_ROLES = ("key", "fill", "rim")

    for i, desc in enumerate(preset.get("lights", [])):
        if "role" not in desc:
            desc = dict(desc, role=_DEFAULT_ROLES[i] if i < 3 else "fill")
        desc_with_id = dict(desc, _preset_id=preset_id)
        obj = create_light(
            descriptor     = desc_with_id,
            collection     = collection,
            engine         = engine,
            intensity_mult = intensity_mult,
            temp_offset    = temp_offset,
            scene_scale    = scene_scale,
            scene_origin   = scene_origin,
        )
        if obj is not None:
            created.append(obj)

    print("[LSM] ═══ Done: %d/%d lights ═══" % (
        len(created), len(preset.get("lights", []))))

    # ---- Environment / render config ----------------------------------------
    if configure_luxcore:
        env_cfg = preset.get("env_light")
        lxc_cfg = preset.get("luxcore_cfg", {})

        if engine == "LUXCORE":
            if env_cfg:
                wp = LuxCoreWorldProxy(scene)
                if wp.available:
                    t = env_cfg.get("type", "sky2")
                    if t == "sky2":
                        wp.configure_sky2(
                            turbidity=env_cfg.get("turbidity", 3.0),
                            gain=env_cfg.get("gain", 0.01),
                        )
                    elif t == "constant":
                        wp.configure_constant(
                            color=env_cfg.get("color", (0.05, 0.05, 0.05)),
                            gain=env_cfg.get("gain", 0.001),
                        )
                    elif t == "hdri":
                        from .cycles_compat import resolve_hdri_path
                        hdri_name = env_cfg.get("name", "")
                        filepath  = resolve_hdri_path(hdri_name) if hdri_name else None
                        if filepath:
                            wp.configure_hdri(
                                filepath = filepath,
                                gain     = env_cfg.get("gain",     1.0),
                                rotation = env_cfg.get("rotation", 0.0),
                                gamma    = env_cfg.get("gamma",    1.0),
                            )
                        else:
                            log.warning("[LSM] HDRI %r not found — LuxCore fallback to SKY2",
                                        hdri_name)
                            wp.configure_sky2(turbidity=4.0, gain=env_cfg.get("gain", 0.01))
            if lxc_cfg:
                sp = LuxCoreSceneProxy(scene)
                if sp.available:
                    sp.set_engine(lxc_cfg.get("engine", "PATH"))
                    sp.set_path_depth(lxc_cfg.get("path_depth", 8))
                    sp.set_halt_samples(lxc_cfg.get("halt_samples", 256))
                    sp.set_denoiser(lxc_cfg.get("denoiser", True))

        elif engine == "CYCLES":
            if env_cfg:
                apply_cycles_sky(scene, env_cfg)
            else:
                reset_cycles_world(scene)
            if lxc_cfg:
                sp = CyclesSceneProxy(scene)
                sp.apply_from_lxc_cfg(lxc_cfg)

    return created
