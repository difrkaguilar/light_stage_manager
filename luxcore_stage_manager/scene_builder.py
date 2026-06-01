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

    # Gel tint: multiply the resolved color by the gel RGB.
    # Gel is read from the descriptor first (per-light override),
    # then from the scene property (global rig tint).
    gel_id = descriptor.get("gel")
    if gel_id is None:
        # Check scene-level gel property (set via the panel slider)
        try:
            import bpy as _bpy
            scene_gel = _bpy.context.scene.lsm_props.gel_preset
            if scene_gel and scene_gel != "none":
                gel_id = scene_gel
        except Exception:
            pass

    if gel_id and gel_id != "none":
        from .constants import GEL_COLORS
        gel_rgb = GEL_COLORS.get(gel_id)
        if gel_rgb:
            cur = light_data.color
            light_data.color = (
                cur[0] * gel_rgb[0],
                cur[1] * gel_rgb[1],
                cur[2] * gel_rgb[2],
            )
            log.debug("[LSM] Gel '%s' applied to %s", gel_id, obj_name)

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
    obj["lsm_role"]         = descriptor.get("role", "fill")
    obj["lsm_raw_energy"]   = float(raw_energy)       # unscaled preset value
    obj["lsm_base_energy"]  = float(actual_energy)    # scaled applied energy — live_update reference
    obj["lsm_luxcore_gain"] = float(gain_mult)        # luxcore_gain from descriptor
    obj["lsm_light_type"]   = light_type
    obj["lsm_preset_id"]    = descriptor.get("_preset_id", "")
    # Store original color/kelvin from preset for live adjustments.
    # Updates always start from these base values — never accumulate.
    if kelvin is not None:
        obj["lsm_kelvin"]     = float(kelvin)
        obj["lsm_base_color"] = kelvin_to_linear_rgb(float(kelvin))
    elif color_rgb is not None:
        obj["lsm_kelvin"]     = -1.0   # sentinel: RGB source, no kelvin
        obj["lsm_base_color"] = tuple(float(c) for c in color_rgb[:3])
    else:
        obj["lsm_kelvin"]     = -1.0
        obj["lsm_base_color"] = (1.0, 1.0, 1.0)

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

    # =========================================================================
    # GOBO PLANE — optional, SPOT lights only
    # =========================================================================
    # Must be created after the light object is linked and positioned so
    # _create_gobo_plane can read light_obj.matrix_world correctly.
    gobo_cfg = descriptor.get("gobo")
    if gobo_cfg and light_type == "SPOT":
        _create_gobo_plane(
            light_obj  = obj,
            gobo_cfg   = gobo_cfg,
            collection = collection,
            engine     = engine,
            scene_scale = scene_scale,
        )

    return obj


# ---------------------------------------------------------------------------
# Gobo plane helper
# ---------------------------------------------------------------------------

def _create_gobo_plane(light_obj, gobo_cfg: dict, collection,
                       engine: str, scene_scale: float) -> object:
    """Create a shadow-casting gobo plane in front of a SPOT light.

    The plane is a physical mesh that blocks some light rays, simulating
    a gobo (pattern projector) in front of the light. Users assign their
    own B&W texture to the material to control the shadow pattern.

    The material is set up so:
    - Cycles: Transparent BSDF controlled by image texture alpha + Alpha Clip
              shadow mode. The plane is invisible to camera rays.
    - LuxCore: Glass material with absorption texture — approximates the
               blocking effect. Invisible to camera via visibility settings.
    - EEVEE:   Same as Cycles setup; shadow quality depends on EEVEE settings.

    Args:
        light_obj:  The SPOT light Object the gobo belongs to.
        gobo_cfg:   Dict from the "gobo" key in the light descriptor.
                    Keys: size (float, metres), distance (float, metres from light),
                          texture ("checker"|"stripes"|"dots") for the placeholder.
        collection: Blender collection to link into.
        engine:     "LUXCORE"|"CYCLES"|"OTHER"
        scene_scale: Current scene scale multiplier.

    Returns:
        Created gobo Object, or None on failure.
    """
    import mathutils

    size      = float(gobo_cfg.get("size",     0.4)) * scene_scale
    distance  = float(gobo_cfg.get("distance", 0.3)) * scene_scale
    tex_type  = gobo_cfg.get("texture", "checker")
    plane_name = LSM_PREFIX + "Gobo_" + light_obj.name.replace(LSM_PREFIX, "", 1)

    try:
        # ---- Mesh: 1×1 plane scaled to size ---------------------------------
        mesh = bpy.data.meshes.new(plane_name)
        h    = size / 2.0
        verts = [(-h, -h, 0), (h, -h, 0), (h, h, 0), (-h, h, 0)]
        faces = [(0, 1, 2, 3)]
        mesh.from_pydata(verts, [], faces)
        mesh.update()

        plane_obj = bpy.data.objects.new(plane_name, mesh)
        collection.objects.link(plane_obj)

        # ---- Position: in front of the light along its -Z local axis --------
        fwd       = light_obj.matrix_world.to_3x3() @ mathutils.Vector((0.0, 0.0, -1.0))
        plane_obj.location = light_obj.location + fwd * distance
        plane_obj.rotation_euler = light_obj.rotation_euler.copy()

        # Store metadata
        plane_obj["lsm_role"]      = "gobo"
        plane_obj["lsm_preset_id"] = light_obj.get("lsm_preset_id", "")

        # ---- Material -------------------------------------------------------
        mat = bpy.data.materials.new(name=plane_name + "_Mat")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        # Output
        out  = nodes.new("ShaderNodeOutputMaterial")

        # Placeholder texture — procedural so no external file needed
        tex  = nodes.new("ShaderNodeTexChecker")   # replaced by user's own texture
        if tex_type == "stripes":
            tex  = nodes.new("ShaderNodeTexWave")
            tex.wave_type = "BANDS"
        elif tex_type == "dots":
            tex  = nodes.new("ShaderNodeTexVoronoi")
        tex.location = (-400, 100)

        coord = nodes.new("ShaderNodeTexCoord")
        coord.location = (-600, 100)
        links.new(coord.outputs["UV"], tex.inputs[0])

        # Mix: texture controls transparency
        mix  = nodes.new("ShaderNodeMixShader")
        mix.location = (-100, 0)

        transp = nodes.new("ShaderNodeBsdfTransparent")
        transp.location = (-300, 100)

        diffuse = nodes.new("ShaderNodeBsdfDiffuse")
        diffuse.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
        diffuse.location = (-300, -100)

        # Texture fac → mix (0 = transparent, 1 = opaque/black)
        tex_out = tex.outputs.get("Color") or tex.outputs[0]
        links.new(tex_out, mix.inputs["Fac"])
        links.new(transp.outputs["BSDF"],  mix.inputs[1])
        links.new(diffuse.outputs["BSDF"], mix.inputs[2])
        links.new(mix.outputs["Shader"],   out.inputs["Surface"])

        # Shadow mode: cast shadows based on alpha, invisible to camera
        mat.shadow_method       = "CLIP"   # Cycles / EEVEE
        mat.blend_method        = "CLIP"
        mat.alpha_threshold     = 0.5

        plane_obj.data.materials.append(mat)

        # Hide from camera (shadows only)
        plane_obj.visible_camera      = False
        plane_obj.visible_diffuse     = False
        plane_obj.visible_glossy      = False
        plane_obj.visible_transmission = False
        plane_obj.visible_shadow      = True    # only shadow rays see this plane

        # LuxCore: mark invisible to camera via luxcore visibility
        if engine == "LUXCORE":
            from .lxc_compat import apply_lxc_object_visibility
            apply_lxc_object_visibility(plane_obj, visible_to_camera=False)

        log.debug("[LSM] Gobo plane created: %r  size=%.3f  dist=%.3f  tex=%s",
                  plane_name, size, distance, tex_type)
        return plane_obj

    except Exception as exc:
        log.error("[LSM] _create_gobo_plane failed for %r: %s",
                  light_obj.name, exc)
        return None

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
    """Remove all LSM objects: lights, gobo planes, and target empties."""
    to_delete = [o for o in scene.objects
                 if o.name.startswith(LSM_PREFIX)
                 or o.name.startswith("LSM_Target_")]
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

def apply_live_adjustments(scene,
                           intensity_mult:  float = 1.0,
                           temp_offset:     float = 0.0,
                           gel_id:          str   = "none",
                           fill_ratio:      float = 1.0) -> int:
    """Apply intensity, temperature, gel and fill-ratio to in-scene LSM lights.

    This is the single function called by ALL live-update callbacks. It always
    starts from the stored base values (``lsm_raw_energy``, ``lsm_base_color``,
    ``lsm_kelvin``) so adjustments never accumulate across slider moves.

    Args:
        scene:          Target bpy.types.Scene.
        intensity_mult: Global energy multiplier.
        temp_offset:    Kelvin offset (applied only to lights with lsm_kelvin > 0).
        gel_id:         Named gel from GEL_COLORS, or "none".
        fill_ratio:     Fill-to-key ratio (applied after intensity).

    Returns:
        Number of lights updated.
    """
    from .constants import GEL_COLORS, KELVIN_MIN, KELVIN_MAX

    lsm_lights = [o for o in scene.objects
                  if o.name.startswith(LSM_PREFIX)
                  and o.type == "LIGHT"
                  and o.get("lsm_role") != "gobo"]

    if not lsm_lights:
        return 0

    # Gel multiplier
    gel_rgb = GEL_COLORS.get(gel_id) if gel_id and gel_id != "none" else None

    # Find key base energy for fill ratio (at intensity_mult=1.0)
    key_base_energy = None
    for obj in lsm_lights:
        if obj.get("lsm_role") == "key":
            key_base_energy = float(obj.get("lsm_base_energy",
                                            obj.get("lsm_raw_energy",
                                                    obj.data.energy)))
            break

    updated = 0
    for obj in lsm_lights:
        ld   = obj.data
        role = obj.get("lsm_role", "fill")

        # lsm_base_energy = actual energy at intensity_mult=1.0 (includes scene_scale²)
        # Falls back to lsm_raw_energy for lights created before this fix,
        # then to current ld.energy as last resort.
        base = float(obj.get("lsm_base_energy",
                              obj.get("lsm_raw_energy", ld.energy)))

        # --- Energy ---
        if role in ("fill", "rim") and key_base_energy is not None:
            ratio       = float(fill_ratio) if role == "fill" else float(fill_ratio) * 0.5
            scaled_key  = key_base_energy * max(0.0001, float(intensity_mult))
            base_energy = scaled_key * ratio
        else:
            base_energy = base * max(0.0001, float(intensity_mult))

        ld.energy = max(0.001, base_energy)

        # --- Color ---
        base_color = list(obj.get("lsm_base_color", (1.0, 1.0, 1.0)))
        stored_k   = float(obj.get("lsm_kelvin", -1.0))

        if stored_k > 0 and abs(temp_offset) > 0.5:
            adjusted_k = max(float(KELVIN_MIN),
                             min(float(KELVIN_MAX), stored_k + float(temp_offset)))
            base_color = list(kelvin_to_linear_rgb(adjusted_k))

        if gel_rgb:
            base_color = [
                base_color[0] * gel_rgb[0],
                base_color[1] * gel_rgb[1],
                base_color[2] * gel_rgb[2],
            ]

        ld.color = tuple(base_color)

        # --- LuxCore energy + color sync ---
        # LuxCore ignores ld.energy and ld.color in "artistic" unit mode.
        # We must push the values to lx.gain, lx.temperature, and lx.rgb_gain.
        try:
            from .lxc_compat import is_active_engine, _try_set
            from .constants import (LXC_AREA_GAIN_SCALE, LXC_SPOT_GAIN_SCALE,
                                    LXC_POINT_GAIN_SCALE, LXC_SUN_GAIN_SCALE,
                                    KELVIN_LXC_MAX)
            if is_active_engine(scene):
                lx = getattr(ld, "luxcore", None)
                if lx is not None:
                    # ---- Gain ----
                    _gs_map = {
                        "AREA":  LXC_AREA_GAIN_SCALE,
                        "SPOT":  LXC_SPOT_GAIN_SCALE,
                        "POINT": LXC_POINT_GAIN_SCALE,
                        "SUN":   LXC_SUN_GAIN_SCALE,
                    }
                    gs = _gs_map.get(ld.type, LXC_AREA_GAIN_SCALE)
                    lxc_gain_val = base_energy * gs * float(obj.get("lsm_luxcore_gain", 1.0))
                    _try_set(lx, "gain", lxc_gain_val)

                    # ---- Color / Temperature ----
                    if stored_k > 0:
                        # Kelvin source: update LuxCore temperature (not just ld.color)
                        lxc_k = max(float(KELVIN_MIN),
                                    min(float(KELVIN_LXC_MAX),
                                        stored_k + float(temp_offset)))
                        _try_set(lx, "temperature",           float(lxc_k))
                        _try_set(lx, "color_temperature",     int(lxc_k))
                        _try_set(lx, "color_mode",            "temperature")
                        _try_set(lx, "use_color_temperature", True)
                    else:
                        # RGB source: sync Blender color → LuxCore rgb_gain
                        _try_set(lx, "rgb_gain",              tuple(base_color))
                        _try_set(lx, "color_mode",            "color")
                        _try_set(lx, "use_color_temperature", False)
        except Exception:
            pass

        updated += 1

    return updated
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
