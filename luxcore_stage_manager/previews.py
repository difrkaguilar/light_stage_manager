# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  difrkaguilar + Claude (Anthropic)
# LuxCore Stage Manager -- Preview Management
#
# Two-tier preview system:
#   Tier 1: Rendered PNGs from headless Blender (preview_renderer.py)
#            Loaded from addon/previews/<preset_id>.png
#   Tier 2: Procedural top-down light-rig diagram (fallback while rendering)

from __future__ import annotations
import os
import math
import logging
log = logging.getLogger(__name__)

_preview_collections: dict = {}
SIZE = 128

# Path to the previews folder inside the addon directory
def _previews_dir() -> str:
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), "previews")

def _png_path(preset_id: str) -> str:
    return os.path.join(_previews_dir(), preset_id + ".png")

def all_pngs_exist(presets: list) -> bool:
    return all(os.path.exists(_png_path(p["id"])) for p in presets)

def rendering_complete() -> bool:
    return os.path.exists(os.path.join(_previews_dir(), ".render_complete"))


# ---------------------------------------------------------------------------
# Tier-2 fallback: procedural diagram generator
# ---------------------------------------------------------------------------

def _kelvin_to_srgb(k: float) -> tuple:
    k = max(1000.0, min(12000.0, k))
    t = (k - 1000.0) / 11000.0
    if t < 0.25:
        r, g, b = 1.0, 0.3 + t*1.8, t*0.8
    elif t < 0.5:
        f = (t-0.25)/0.25; r, g, b = 1.0, 0.75+f*0.2, 0.2+f*0.7
    elif t < 0.75:
        f = (t-0.5)/0.25;  r, g, b = 1.0-f*0.25, 0.95, 0.9+f*0.1
    else:
        f = (t-0.75)/0.25; r, g, b = 0.75-f*0.2, 0.9-f*0.05, 1.0
    return (min(1.0,r), min(1.0,g), min(1.0,b))

def _c01(v): return max(0.0, min(1.0, v))

def _fill_circle(buf, cx, cy, r, rgb, alpha=1.0):
    for dy in range(-r, r+1):
        y = cy+dy
        if not (0 <= y < SIZE): continue
        for dx in range(-r, r+1):
            if dx*dx+dy*dy > r*r: continue
            x = cx+dx
            if not (0 <= x < SIZE): continue
            idx=(y*SIZE+x)*4
            a=alpha; ia=1.0-a
            buf[idx]=_c01(rgb[0]*a+buf[idx]*ia)
            buf[idx+1]=_c01(rgb[1]*a+buf[idx+1]*ia)
            buf[idx+2]=_c01(rgb[2]*a+buf[idx+2]*ia)
            buf[idx+3]=_c01(buf[idx+3]+a*(1.0-buf[idx+3]))

def _draw_ring(buf, cx, cy, r, thick, rgb, alpha=1.0):
    ri=max(0,r-thick)
    for dy in range(-r,r+1):
        y=cy+dy
        if not (0<=y<SIZE): continue
        for dx in range(-r,r+1):
            d2=dx*dx+dy*dy
            if d2>r*r or d2<ri*ri: continue
            x=cx+dx
            if not (0<=x<SIZE): continue
            idx=(y*SIZE+x)*4
            a=alpha; ia=1.0-a
            buf[idx]=_c01(rgb[0]*a+buf[idx]*ia)
            buf[idx+1]=_c01(rgb[1]*a+buf[idx+1]*ia)
            buf[idx+2]=_c01(rgb[2]*a+buf[idx+2]*ia)
            buf[idx+3]=_c01(buf[idx+3]+a)

def _draw_line(buf, x0,y0,x1,y1, rgb, alpha=0.5):
    dx=abs(x1-x0); dy=abs(y1-y0)
    sx=1 if x0<x1 else -1; sy=1 if y0<y1 else -1
    err=dx-dy
    while True:
        if 0<=x0<SIZE and 0<=y0<SIZE:
            idx=(y0*SIZE+x0)*4
            buf[idx]=_c01(rgb[0]*alpha+buf[idx]*(1-alpha))
            buf[idx+1]=_c01(rgb[1]*alpha+buf[idx+1]*(1-alpha))
            buf[idx+2]=_c01(rgb[2]*alpha+buf[idx+2]*(1-alpha))
            buf[idx+3]=_c01(buf[idx+3]+alpha)
        if x0==x1 and y0==y1: break
        e2=2*err
        if e2>-dy: err-=dy; x0+=sx
        if e2<dx:  err+=dx; y0+=sy

WORLD_RANGE=6.0
def _w2p(wx,wy):
    half=SIZE//2; scale=(SIZE-20)/2.0/WORLD_RANGE
    return int(half+wx*scale), int(half-wy*scale)

def _generate_diagram(preset: dict) -> list:
    buf=[0.0]*(SIZE*SIZE*4)
    bg=(0.055,0.055,0.09)
    for i in range(SIZE*SIZE):
        idx=i*4; buf[idx]=bg[0]; buf[idx+1]=bg[1]; buf[idx+2]=bg[2]; buf[idx+3]=1.0
    cx=cy=SIZE//2
    gc=(0.12,0.12,0.18)
    for x in range(SIZE):
        idx=(cy*SIZE+x)*4; buf[idx]=gc[0]; buf[idx+1]=gc[1]; buf[idx+2]=gc[2]
    for y in range(SIZE):
        idx=(y*SIZE+cx)*4; buf[idx]=gc[0]; buf[idx+1]=gc[1]; buf[idx+2]=gc[2]
    _fill_circle(buf,cx,cy,7,(0.95,0.95,0.95))
    _fill_circle(buf,cx,cy,4,(0.6,0.6,0.6))
    cpx,cpy=_w2p(0.0,-5.0); cc=(0.45,0.75,1.0)
    for row in range(6):
        for col in range(-row,row+1):
            x=cpx+col; y=cpy-(5-row)
            if 0<=x<SIZE and 0<=y<SIZE:
                idx=(y*SIZE+x)*4; buf[idx]=cc[0]; buf[idx+1]=cc[1]; buf[idx+2]=cc[2]; buf[idx+3]=0.85
    _fill_circle(buf,cpx,cpy,3,cc,alpha=0.7)
    _draw_line(buf,cpx,cpy,cx,cy,(0.3,0.5,0.7),alpha=0.3)
    lights=preset.get("lights",[])
    max_e=max((float(l.get("energy",100)) for l in lights),default=100.0)
    for light in lights:
        loc=light.get("location",(0.0,0.0,3.0))
        px,py=_w2p(float(loc[0]),float(loc[1]))
        energy=float(light.get("energy",100.0))
        ltype=light.get("type","AREA")
        kelvin=light.get("kelvin"); color_rgb=light.get("color")
        lc=(_kelvin_to_srgb(kelvin) if kelvin is not None
            else tuple(min(1.0,max(0.0,float(c))) for c in color_rgb[:3])
            if color_rgb else (1.0,1.0,0.9))
        r=max(4,min(18,int(4+(energy/max_e)*12)))
        _draw_line(buf,px,py,cx,cy,lc,alpha=0.2)
        if ltype=="AREA":
            _fill_circle(buf,px,py,r,lc,alpha=0.85)
            _fill_circle(buf,px,py,max(2,r//3),(1.0,1.0,1.0),alpha=0.6)
        elif ltype=="SPOT":
            _fill_circle(buf,px,py,r,lc,alpha=0.75)
            _fill_circle(buf,px,py,max(2,r//2),(1.0,1.0,1.0),alpha=0.7)
        elif ltype=="SUN":
            _draw_ring(buf,px,py,r+4,3,lc,alpha=0.5)
            _fill_circle(buf,px,py,r,lc,alpha=0.8)
            for ad in range(0,360,45):
                ang=math.radians(ad)
                x1=int(px+(r+2)*math.cos(ang)); y1=int(py+(r+2)*math.sin(ang))
                x2=int(px+(r+8)*math.cos(ang)); y2=int(py+(r+8)*math.sin(ang))
                _draw_line(buf,x1,y1,x2,y2,lc,alpha=0.7)
        elif ltype=="POINT":
            _fill_circle(buf,px,py,r,lc,alpha=0.5)
            _fill_circle(buf,px,py,max(2,r//3),(1.0,1.0,1.0),alpha=0.7)
    return buf


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_previews(presets: list) -> None:
    """Load PNG previews if available; fall back to procedural diagrams.

    Called from a bpy.app.timers callback after registration so that
    bpy.utils.previews is accessible.
    """
    import bpy

    if "main" in _preview_collections:
        return

    try:
        pcoll = bpy.utils.previews.new()
    except Exception as exc:
        log.error("[LSM] Could not create preview collection: %s", exc)
        return

    pdir = _previews_dir()
    loaded_png = 0
    loaded_diag = 0

    for preset in presets:
        pid = preset.get("id", "")
        if not pid:
            continue

        png = _png_path(pid)
        if os.path.exists(png):
            try:
                pcoll.load(pid, png, "IMAGE")
                loaded_png += 1
                continue
            except Exception as exc:
                log.warning("[LSM] Could not load PNG for %r: %s", pid, exc)

        # Fallback: procedural diagram
        try:
            pixels  = _generate_diagram(preset)
            preview = pcoll.new(pid)
            preview.image_size         = (SIZE, SIZE)
            preview.image_pixels_float = pixels
            loaded_diag += 1
        except Exception as exc:
            log.warning("[LSM] Could not generate diagram for %r: %s", pid, exc)

    _preview_collections["main"] = pcoll
    log.info("[LSM] Previews: %d PNG, %d diagrams", loaded_png, loaded_diag)
    print("[LSM] Previews: %d PNG loaded, %d diagrams generated" % (loaded_png, loaded_diag))


def reload_previews(presets: list) -> None:
    """Force re-initialisation of the preview collection (called after render)."""
    free_previews()
    init_previews(presets)


def get_icon_id(preset_id: str) -> int:
    pcoll = _preview_collections.get("main")
    if pcoll is None:
        return 0
    preview = pcoll.get(preset_id)
    return preview.icon_id if preview else 0


def free_previews() -> None:
    import bpy
    pcoll = _preview_collections.pop("main", None)
    if pcoll is not None:
        try:
            bpy.utils.previews.remove(pcoll)
        except Exception as exc:
            log.warning("[LSM] Could not free preview collection: %s", exc)
