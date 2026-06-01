# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  difrkaguilar + Claude (Anthropic)
# Light Stage Manager -- Viewport overlay (light contours + labels)

"""Viewport draw handler for LSM light visualisation.

Draws coloured contour outlines around AREA lights and point indicators
for SPOT/SUN/POINT lights, colour-coded by role:
    key  → yellow  (1.0, 0.85, 0.0)
    fill → blue    (0.2, 0.55, 1.0)
    rim  → green   (0.15, 0.9, 0.45)
    env  → purple  (0.7, 0.3, 1.0)
    other→ grey    (0.6, 0.6, 0.6)

The overlay is drawn with `SpaceView3D.draw_handler_add` and uses the
`gpu` + `gpu_extras.batch` modules available in Blender 4.x.

Registration / unregistration is called from `__init__.py`.
"""

from __future__ import annotations
import logging
import math

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Role → colour mapping (linear RGB, alpha)
# ---------------------------------------------------------------------------

_ROLE_COLORS: dict[str, tuple] = {
    "key":   (1.00, 0.85, 0.00, 0.90),
    "fill":  (0.20, 0.55, 1.00, 0.85),
    "rim":   (0.15, 0.90, 0.45, 0.85),
    "env":   (0.70, 0.30, 1.00, 0.80),
    "gobo":  (0.90, 0.30, 0.10, 0.60),
    "target":(0.80, 0.80, 0.80, 0.50),
}
_DEFAULT_COLOR = (0.60, 0.60, 0.60, 0.70)

# Thickness of the outline in pixels
_LINE_WIDTH = 1.5

# ---------------------------------------------------------------------------
# Module-level handler handle (returned by draw_handler_add)
# ---------------------------------------------------------------------------

_handle = None


# ---------------------------------------------------------------------------
# Core drawing function
# ---------------------------------------------------------------------------

def _draw_callback():
    """Draw callback registered with SpaceView3D — called every viewport redraw."""
    import bpy
    import gpu
    from gpu_extras.batch import batch_for_shader
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    from mathutils import Vector, Matrix

    context = bpy.context
    if context is None:
        return

    # Check overlay enabled flag (set by the panel toggle)
    if not context.scene.get("lsm_overlay_enabled", True):
        return

    lsm_lights = [o for o in context.scene.objects
                  if o.name.startswith("LSM_") and o.type == "LIGHT"
                  and not o.hide_viewport]

    if not lsm_lights:
        return

    region    = context.region
    rv3d      = context.region_data
    if region is None or rv3d is None:
        return

    shader = gpu.shader.from_builtin("UNIFORM_COLOR")

    gpu.state.line_width_set(_LINE_WIDTH)
    gpu.state.blend_set("ALPHA")
    gpu.state.depth_test_set("NONE")

    # Load font for labels
    try:
        import blf
        font_id    = 0
        font_size  = 14
        has_blf    = True
    except ImportError:
        has_blf = False

    for obj in lsm_lights:
        role  = obj.get("lsm_role", "fill")
        color = _ROLE_COLORS.get(role, _DEFAULT_COLOR)
        ld    = obj.data

        pts_2d = _get_contour_2d(obj, region, rv3d)
        if not pts_2d:
            continue

        # Contour outline
        loop  = pts_2d + [pts_2d[0]]
        batch = batch_for_shader(shader, "LINE_STRIP", {"pos": loop})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)

        # Label: light short name near the first contour point
        if has_blf and pts_2d:
            # Pick a label position: slightly above the first point
            lx_pos = pts_2d[0][0] + 4
            ly_pos = pts_2d[0][1] + 4
            short_name = obj.name.replace("LSM_", "", 1)

            # Draw a slightly darker shadow for legibility
            blf.size(font_id, font_size)
            blf.color(font_id, 0.0, 0.0, 0.0, 0.8)
            blf.position(font_id, lx_pos + 1, ly_pos - 1, 0)
            blf.draw(font_id, short_name)

            # Draw label in role color (bright)
            r, g, b, a = color
            blf.color(font_id, min(1.0, r * 1.4), min(1.0, g * 1.4), min(1.0, b * 1.4), 1.0)
            blf.position(font_id, lx_pos, ly_pos, 0)
            blf.draw(font_id, short_name)

    # Reset state
    gpu.state.line_width_set(1.0)
    gpu.state.blend_set("NONE")
    gpu.state.depth_test_set("LESS_EQUAL")


def _get_contour_2d(obj, region, rv3d) -> list:
    """Return a list of 2D screen-space points forming the light contour.

    For AREA:  4 corners of the rectangle/square.
    For SPOT:  circle approximation of the cone footprint at aim distance.
    For SUN:   small direction arrow indicator.
    For POINT: small circle around the location.
    """
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    from mathutils import Vector, Matrix

    ld   = obj.data
    ltype = ld.type
    mw   = obj.matrix_world

    def to_2d(v3):
        p = location_3d_to_region_2d(region, rv3d, v3)
        return list(p) if p else None

    if ltype == "AREA":
        sx = ld.size   / 2.0
        sy = (getattr(ld, "size_y", ld.size) if ld.shape in ("RECTANGLE","ELLIPSE")
              else ld.size) / 2.0
        corners_local = [
            Vector((-sx, -sy, 0)), Vector(( sx, -sy, 0)),
            Vector(( sx,  sy, 0)), Vector((-sx,  sy, 0)),
        ]
        pts = [to_2d(mw @ c) for c in corners_local]
        return [p for p in pts if p is not None]

    elif ltype == "SPOT":
        # Draw a circle at the cone edge at some distance ahead
        angle  = ld.spot_size / 2.0
        dist   = 1.5   # metres ahead along -Z
        radius = math.tan(angle) * dist
        n_seg  = 16
        center_local = Vector((0.0, 0.0, -dist))
        pts = []
        for i in range(n_seg):
            a  = 2.0 * math.pi * i / n_seg
            lv = Vector((math.cos(a) * radius,
                         math.sin(a) * radius,
                         -dist))
            p  = to_2d(mw @ lv)
            if p:
                pts.append(p)
        return pts

    elif ltype == "SUN":
        # Arrow: center + direction line
        origin  = to_2d(mw.translation)
        tip_pt  = to_2d(mw @ Vector((0.0, 0.0, -1.5)))
        if origin and tip_pt:
            return [origin, tip_pt]
        return []

    elif ltype == "POINT":
        # Small circle around the point
        radius = 0.25
        n_seg  = 12
        loc    = mw.translation
        # Build circle in view-aligned plane
        right = Vector(rv3d.view_matrix[0][:3]).normalized() * radius
        up    = Vector(rv3d.view_matrix[1][:3]).normalized() * radius
        pts   = []
        for i in range(n_seg):
            a   = 2.0 * math.pi * i / n_seg
            v3  = loc + right * math.cos(a) + up * math.sin(a)
            p   = to_2d(v3)
            if p:
                pts.append(p)
        return pts

    return []


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_overlay():
    """Register the draw handler. Call from addon register()."""
    global _handle
    if _handle is not None:
        return   # already registered

    import bpy
    try:
        _handle = bpy.types.SpaceView3D.draw_handler_add(
            _draw_callback, (), "WINDOW", "POST_PIXEL"
        )
        log.debug("[LSM] Viewport overlay registered")
    except Exception as exc:
        log.warning("[LSM] Could not register viewport overlay: %s", exc)


def unregister_overlay():
    """Remove the draw handler. Call from addon unregister()."""
    global _handle
    if _handle is None:
        return

    import bpy
    try:
        bpy.types.SpaceView3D.draw_handler_remove(_handle, "WINDOW")
        _handle = None
        log.debug("[LSM] Viewport overlay unregistered")
    except Exception as exc:
        log.warning("[LSM] Could not unregister viewport overlay: %s", exc)
