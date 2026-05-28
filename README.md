# Light Stage Manager

> **34 cinematic lighting presets for Blender — LuxCore · Cycles · EEVEE**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Blender](https://img.shields.io/badge/Blender-4.1%2B-orange.svg)](https://www.blender.org)
[![LuxCore](https://img.shields.io/badge/BlendLuxCore-2.10.1%2B-green.svg)](https://github.com/LuxCoreRender/BlendLuxCore)
[![Version](https://img.shields.io/badge/version-3.4.0-informational.svg)](https://github.com/difrkaguilar/light-stage-manager/releases)

---

Stop placing lights by hand. Select a lighting direction, click **Apply** — done.

Light Stage Manager gives you 34 professional lighting setups that adapt automatically
to your render engine, your object size, and your scene. Portrait rigs, product studio
setups, architectural daylight, creative moods, and film-inspired cinematic looks —
all calibrated for LuxCore, Cycles and EEVEE with a single click.

---

## Presets

### 🎬 Cinematic (8)
Film-inspired setups that reference specific cinematographers and productions.
Each one has a deliberate intention — not just "looks good" but "looks like *this*".

| Preset | Mood & intent |
|---|---|
| **Deakins — Window Natural** | A single motivated window. The room breathes. Nothing screams "lighting rig". This is what Deakins spent 40 years perfecting: light that looks like it was already there |
| **Wong Kar-wai — Amber Night** | A practical lamp fights against neon and painted-wall bounce. The scene is emotionally saturated before anything happens. Warm amber dominant, green accent, red fill |
| **Blade Runner 2049** | Cold blue ambient from an overcast dystopian sky versus a narrow orange neon stripe. Extreme contrast ratio. The colour temperature war is the composition |
| **A24 — Golden Naturalism** | Late afternoon sun at 3200K, open sky at 10 000K as the counter-key, ground bounce for warmth from below. No rig visible. Relies on global illumination for cohesion — apply with BIDIR |
| **Kubrick — Overhead Hard** | Surgical overhead SPOT at near-zero fill ratio. The skull shadows are the point. Ghost fill at 1:25 ratio just prevents total crush. Cold blue rim for minimal separation |
| **Zsigmond — Cold Exterior** | Vilmos Zsigmond's winter palette from The Deer Hunter. Flat overcast grey-blue sky as the dominant source, weak cool sun at low angle. No artificial fill — the sky *is* the fill |
| **Lubezki — Continuous Window** | One light. One enormous wall-sized window. All fill comes from GI bounce. The most committed single-source setup in the collection. Works best on high-sample BIDIR renders |
| **Fincher — Controlled** | Precise SPOT with a gobo plane for projected shadow patterns. 1:43 key-to-fill ratio — almost no fill, almost total control. Assign your own B&W texture to the gobo plane material |

### 🧑 Portrait (8)
Classic and contemporary portrait rigs. Each one solves a specific photographic problem.

| Preset | When to use it |
|---|---|
| **Rembrandt Classic** | The triangle of light on the far cheek. Commercially useful for anyone who looks better with a slight mystery to them |
| **Butterfly / Paramount** | Front-above key for the classic Hollywood look. Eliminates under-chin shadows. The go-to for beauty work |
| **Loop Lighting** | Key at 30-45°. Small nose shadow. The most versatile commercial portrait setup — works for almost any face shape |
| **Split Lighting** | 90° side key, half the face in shadow. High drama, high contrast. Strong for editorial |
| **Clamshell Beauty** | Top key + chin reflector. Kills under-eye shadows completely. Fashion and beauty industry standard |
| **Broad Lighting** | Key on the camera-facing side. Widening and three-dimensional — works against conventional wisdom |
| **Short Lighting** | Key on the far side. Slimming. Traditionally masculine portraiture |
| **Film Noir** | Single hard top spot with no fill. Long shadows, high contrast. The shadows tell the story |

### 📦 Product (9)
Studio setups for product, e-commerce, and automotive. Built around specular control.

| Preset | What it solves |
|---|---|
| **Automotive Studio Rig** | Matched vertical strip lights reveal bodywork curvature. The strip specular *is* the design language of the car. Overhead + front key + cyclorama ground fill |
| **Product Classic 45°** | The most reliable commercial setup. 45° front key, soft fill, separation backlight |
| **Product Clamshell** | Symmetric top/bottom wrap for jewelry and cosmetics where shadows are unwanted |
| **Tabletop Sweep** | Large side softbox + bounce fill for e-commerce. Clean, directional, scalable |
| **Infinity White** | High-key infinite white. Catalogue standard. Everything needs to render on white eventually |
| **Backlit / Translucent** | Strong backlight for bottles, glasses, anything that reveals its material when lit from behind |
| **Studio Three-Point Pro** | The reliable workhorse. Front-side key, soft fill, top accent. Never wrong |
| **Jewelry Macro Sparkle** | Multiple small hard sources that make gemstones fire. Caustics-heavy — needs BIDIR |
| **Cosmetic Gradient Beauty** | Enveloping front light for packaging and perfumery. The product glows without a visible source |

### 🏛️ Architecture (5)
Interior and exterior lighting for architectural visualization and spatial rendering.

| Preset | Character |
|---|---|
| **Interior Daylight** | Sun + sky area + interior fill. Side window as the spatial anchor |
| **Interior Night Artificial** | Warm pendants + cool accent. The room feels inhabited |
| **Exterior Golden Hour** | Low warm sun, long shadows, cool sky counter-key |
| **Exterior Overcast** | Flat diffuse overcast. No hard shadows, clean surfaces. The architect's preferred light |
| **Window Natural Minimal** | One window as the only source. Spatial clarity through restraint |

### 🎨 Creative (4)
Atmospheric and editorial setups for anything that doesn't want to look like a product shot.

| Preset | Character |
|---|---|
| **Moody Drama** | Hard front-side spot with no fill. Deep shadows. The light has opinions |
| **High Key Ethereal** | No visible shadows. Cold wrap softboxes. Exists somewhere between beauty and concept |
| **Neon RGB Atmosphere** | Blue key, orange fill, cyan rim. Cyberpunk without apology |
| **Candlelight Atmosphere** | Very warm point practicals + minimal bounce. The darkness matters as much as the light |

---

## How it works

### One-click apply
1. Open the N-panel in the 3D Viewport (`N`) → **LightStageManager** tab
2. Select a preset — the thumbnail and info panel update immediately
3. Click **Apply Preset** — lights are created, named and configured for your active engine

All lights land in a collection called `LSM — <Preset Name>`. All objects are prefixed `LSM_`
so they never pollute your Outliner.

### Scale-aware — works for any object size
Presets are calibrated for a ~1 m reference object. When you apply a preset, the addon
reads the **active object's bounding box** and scales all light positions, sizes and energies
automatically. The same Rembrandt setup that works for Suzanne also works for a ring, an
automobile, or an architectural facade.

```
Light Modifiers → Scale Reference:
  Active Object   → bounding box of selected mesh (recommended)
  All Visible     → union bounding box of all visible meshes
  Manual          → enter the reference size in metres directly
```

The panel shows the computed scale and the resulting energy multiplier before you apply,
so you always know what will happen.

### Global adjustments
After applying, three controls let you fine-tune the whole rig without touching individual lights:

| Control | Effect |
|---|---|
| **Intensity** | Multiplies all light energies proportionally — ratios between lights are preserved |
| **Temp Offset (K)** | Shifts all colour temperatures. +500 K = warmer overall. Does not affect RGB lights |
| **Gel** | Applies a named cinematographic colour gel to all lights. Multiplies over the resolved colour — works with both kelvin and RGB sources |

**20 named gels included:**

| Category | Gels |
|---|---|
| Tungsten / Warm | Tungsten Warm · Amber Deep · Straw |
| Daylight / Cool | CTB Full · CTB Half · Sky Blue · Ice Blue |
| Cinematic palettes | Fincher Green · Kubrick Cold · Lubezki Warm · WKW Amber · WKW Neon Green · BR2049 Orange · BR2049 Blue |
| Special effects | Lavender · Rose · Plus Green · Minus Green · Fire / Explosion |

Gels can also be applied per-light via a `"gel"` key in a preset descriptor, which takes priority over the global gel selector.

### Asset Browser integration
All 34 presets are available directly from Blender's **Asset Browser** with full preview
thumbnails and category filtering — no N-panel required.

**One-time setup:**
1. **Edit → Preferences → Add-ons → Light Stage Manager → Generate Asset Library**
2. **Edit → Preferences → File Paths → Asset Libraries → `+`**
   - Name: `Light Stage Manager`
   - Path: `<addon_folder>/assets/`
   - Import method: `Don't Import`
3. Open the Asset Browser, select `Light Stage Manager` from the library dropdown

After setup, click any preset in the Asset Browser — the sidebar panel shows the preset
details and a one-click **Apply Preset** button.

---

## Render engine support

| Engine | Support level | Notes |
|---|---|---|
| **LuxCore (BlendLuxCore 2.10.1+)** | ✅ Full | `gain`, `light_unit`, `color_mode`, `color_temperature`, visibility, engine config |
| **Cycles (Blender 4.1+)** | ✅ Full | Physical Watts, MIS, spread, sky node tree, render samples/bounces/denoiser |
| **EEVEE Next (Blender 4.2+)** | ✅ Good | Energy, colour, shadows |
| **EEVEE Legacy** | ⚠️ Basic | Energy and colour only |

The same preset definition drives all engines — no manual adjustment required when
switching between LuxCore and Cycles.

### LuxCore-specific calibration
- `light_unit` forced to `"artistic"` before gain is set (prevents silent EV coupling failures)
- BLC 2.10 API (`color_mode` enum) tried first; BLC 2.9 (`use_color_temperature` bool) as fallback
- `obj.luxcore.visibility.camera = False` prevents light geometry appearing in renders
- BIDIR engine assigned automatically for presets that need it (interiors, practicals)

### Dual-energy calibration (Opción B)
Point lights with high LuxCore `gain` (e.g. candlelight, WKW practicals) carry a separate
`cycles_energy` value. LuxCore uses `energy × gain`; Cycles uses `cycles_energy` directly.
This prevents practicals from rendering near-black in Cycles.

### Gels and gobos
- **20 named gels** are available globally from the panel and per-light through the `"gel"` descriptor key.
- SPOT lights can define a `"gobo"` descriptor that creates a shadow-casting plane for projected pattern work, used by presets such as **Fincher — Controlled**.

---

## Installation

### From ZIP (recommended)
1. Download `light_stage_manager_v3.4.0.zip` from the [Releases](../../releases) page
2. **Edit → Preferences → Add-ons → Install...** → select the `.zip`
3. Enable **Lighting: Light Stage Manager**
4. The **LightStageManager** tab appears in the 3D Viewport N-panel

### From source
```bash
git clone https://github.com/difrkaguilar/light-stage-manager.git

# Linux / macOS
cp -r light-stage-manager/luxcore_stage_manager \
      ~/.config/blender/4.1/scripts/addons/

# Windows (PowerShell)
Copy-Item -Recurse light-stage-manager\luxcore_stage_manager `
          "$env:APPDATA\Blender Foundation\Blender\4.1\scripts\addons\"
```

### Requirements
| Component | Minimum | Notes |
|---|---|---|
| Blender | **4.1.0** | Python 3.10+ bundled |
| BlendLuxCore | **2.10.1+** | Optional — Cycles works without it |

---

## Architecture

```
luxcore_stage_manager/
├── __init__.py            Entry point, bl_info (v3.4.0), register/unregister
├── blender_manifest.toml  Blender Extensions Platform metadata (Blender 4.2+)
├── constants.py           Single source of truth: CATEGORY_DEFS, engine IDs,
│                          gel presets, gain scales, Kelvin limits. All other modules derive
│                          from here — no hardcoded category strings elsewhere.
├── lxc_compat.py          LuxCore API isolation — dual BLC 2.9/2.10 support,
│                          LuxCoreLightProxy + LuxCoreWorldProxy typed classes
├── cycles_compat.py       Cycles/EEVEE layer — sky node tree, spread, render
│                          config translation from LuxCore preset metadata
├── scene_builder.py       Scale-aware, engine-aware two-phase light creation.
│                          Phase 1: Blender-native (all engines).
│                          Phase 2a: LuxCore props. Phase 2b: Cycles props.
│                          Positions, sizes and energies scaled by scene_scale.
├── operators.py           ApplyPreset, ApplyFromAsset, GenerateAssetLibrary,
│                          SelectLSMLights, RemoveLSMLights, ResetModifiers,
│                          SetCategory, Diagnose, RenderPreviews
├── panels.py              Passive UI — draw() read-only, mutations via update=.
│                          Includes LSM_PT_AssetBrowser (FILE_BROWSER space).
├── preferences.py         AddonPreferences, versioned migration system,
│                          Asset Library generation button and setup guide
├── asset_builder.py       Generates LSM_Assets.blend with World assets.
│                          Stable catalog UUIDs, PNG thumbnails, color placeholders.
├── presets_data.py        34 preset dicts + validate_preset() + CATEGORIES alias
│                          (authoritative data lives in constants.CATEGORY_DEFS)
├── previews.py            Two-tier preview: PNG loader → procedural diagram fallback
├── preview_renderer.py    Standalone headless Blender script for thumbnail rendering
├── assets/
│   ├── LSM_Assets.blend          Generated by the addon (not in repo)
│   └── blender_assets.cats.txt   Catalog with stable UUIDs for Asset Browser
└── previews/
    ├── README.txt
    ├── rembrandt.png             256×256 rendered thumbnails — 34 PNGs included
    └── ...                       (Cycles render of Suzanne under each preset)
```

### Design principles
- **Single source of truth**: `constants.CATEGORY_DEFS` drives `VALID_CATEGORIES`,
  `CATEGORY_ICONS`, the `EnumProperty` in panels, and the asset catalog — one edit
  propagates everywhere.
- **Engine isolation**: LuxCore API calls are confined to `lxc_compat.py`. The rest
  of the addon never touches `.luxcore.*` attributes directly.
- **Scale invariance**: all preset coordinates are authored at `scene_scale = 1.0`
  (Suzanne). At apply time the operator computes the active object's bounding box
  and scales positions linearly, light sizes linearly, and energies by `scale²`
  (inverse-square law). SUN lights scale linearly (parallel rays, distance-independent).
- **Passive UI**: `draw()` methods are read-only. All state mutations go through
  `update=` callbacks. No `bpy.data` access during `register()` — prevents
  `_RestrictData` crashes on modern Blender builds.
- **Defensive execution**: every `draw()` and `execute()` is wrapped in `try/except`.
  A broken preset or LuxCore API change never crashes the UI.

---

## Contributing

1. Fork the repository and create a feature branch
2. Keep LuxCore API calls inside `lxc_compat.py` only
3. New presets go in `presets_data.py` following the existing schema
4. New categories: add a single tuple to `constants.CATEGORY_DEFS` — nothing else needs editing
5. Call `validate_preset(your_preset)` and confirm it returns `[]`
6. Open a pull request with a description and a render or screenshot

### Adding a preset (quick reference)
```python
{
    "id":          "my_preset",          # snake_case, unique
    "name":        "My Preset Name",     # displayed in UI and Asset Browser
    "category":    "PORTRAIT",           # must be in constants.VALID_CATEGORIES
    "description": "What and when.",
    "lights": [
        {
            "name":         "Key",
            "type":         "AREA",      # AREA | SPOT | SUN | POINT
            "location":     (2.5, -2.0, 2.2),
            "target":       (0.0, 0.0, 0.85),
            "energy":       500.0,       # Watts at scene_scale=1.0
            "kelvin":       5600,        # None → use "color" (R,G,B) instead
            # "cycles_energy": 500.0,    # only needed if luxcore_gain > ~2.0
            "size":         1.2,
            "size_y":       1.8,         # AREA RECTANGLE only
            "shape":        "RECTANGLE",
            "use_shadow":   True,
            "luxcore_gain": 1.0,
        },
    ],
    "env_light": None,                   # or {"type": "sky2", ...} / {"type": "constant", ...}
    "luxcore_cfg": {
        "engine": "PATH", "path_depth": 8, "halt_samples": 256, "denoiser": True,
    },
}
```

### Adding a category
Edit one line in `constants.py`:
```python
CATEGORY_DEFS: list = [
    ...
    ("MY_CAT", "My Category", "Description", "ICON_NAME", 6),  # ← append here
]
```
`VALID_CATEGORIES`, `CATEGORY_ICONS`, the panel `EnumProperty`, and the asset
catalog UUID mapping all update automatically.

---

## License

**Light Stage Manager** is free software released under the
**GNU General Public License v3.0 or later**.

```
Light Stage Manager
Copyright (C) 2026  difrkaguilar + Claude (Anthropic)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
```

See [LICENSE](LICENSE) for the full license text.

---

## Acknowledgements

- [Blender Foundation](https://www.blender.org) — open-source DCC and Python API
- [LuxCore Render](https://luxcorerender.org) and the [BlendLuxCore](https://github.com/LuxCoreRender/BlendLuxCore) team
- The Blender community for documentation, best practices and feedback
