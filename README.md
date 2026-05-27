# Light Stage Manager

> **30 cinematic lighting presets for Blender — LuxCore · Cycles · EEVEE**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Blender](https://img.shields.io/badge/Blender-4.1%2B-orange.svg)](https://www.blender.org)
[![LuxCore](https://img.shields.io/badge/BlendLuxCore-2.10.1%2B-green.svg)](https://github.com/LuxCoreRender/BlendLuxCore)
[![Version](https://img.shields.io/badge/version-3.4.0-informational.svg)](https://github.com/difrkaguilar/light-stage-manager/releases)

---

Stop placing lights by hand. Select a lighting direction, click **Apply** — done.

Light Stage Manager gives you 30 professional lighting setups that adapt automatically
to your render engine, your object size, and your scene. Portrait rigs, product studio
setups, architectural daylight, creative moods, and film-inspired cinematic looks —
all calibrated for LuxCore, Cycles and EEVEE with a single click.

---

## Presets

### 🎬 Cinematic (4)
Film-inspired setups referencing real production pipelines.

| Preset | Key references | Lights |
|---|---|---|
| **Deakins — Window Natural** | Roger Deakins interior style. Motivated single window, huge soft key, sky bounce fill, subtle rim. No obvious rig | 3 |
| **Wong Kar-wai — Amber Night** | Warm practical dominant, neon accent, saturated coloured bounce. High emotional contrast | 3 |
| **Blade Runner 2049** | Cold blue ambient, high-energy orange neon, electric blue rim. Near-zero fill, extreme colour contrast | 3 |
| **A24 — Golden Naturalism** | Late afternoon sun as sole motivated key, cool sky fill, ground bounce. No artificial sources | 3 |

### 🧑 Portrait (8)
Classic and contemporary portrait rigs. Each setup matches a specific photographic intent.

| Preset | Description |
|---|---|
| **Rembrandt Classic** | Triangle shadow on far cheek. Key 45° lateral-up, soft fill, rear rim |
| **Butterfly / Paramount** | Classic Hollywood glamour. Front-above key creates butterfly nose shadow |
| **Loop Lighting** | Key at 30-45°. Small nose shadow. Most versatile commercial portrait setup |
| **Split Lighting** | 90° side key. Half face lit, half in shadow. High contrast |
| **Clamshell Beauty** | Top key + chin reflector. Eliminates under-eye shadows. Beauty / fashion |
| **Broad Lighting** | Key on camera-facing side. Widening, three-dimensional look |
| **Short Lighting** | Key on far side. Slimming effect, common in masculine portraiture |
| **Film Noir** | Single hard top spot. Extreme contrast, long shadows |

### 📦 Product (9)
Studio setups for product, e-commerce and automotive photography.

| Preset | Description |
|---|---|
| **Automotive Studio Rig** | Vertical strip lights reveal bodywork curvature. Overhead panel + front key + ground fill simulate white cyclorama |
| **Product Classic 45°** | 45° front key, soft fill, separation backlight. Most used commercial setup |
| **Product Clamshell** | Symmetric top/bottom. Jewelry and cosmetics |
| **Tabletop Sweep** | Large side softbox + bounce fill. Professional e-commerce |
| **Infinity White** | High-key infinite white background. Catalogue / e-commerce |
| **Backlit / Translucent** | Strong backlight for bottles and translucent products |
| **Studio Three-Point Pro** | Front-side key, soft fill, top accent |
| **Jewelry Macro Sparkle** | Multiple small hard sources for gemstone sparkle. High caustic depth |
| **Cosmetic Gradient Beauty** | Enveloping front light for perfumery and cosmetics |

### 🏛️ Architecture (5)
Interior and exterior lighting for architectural visualization.

| Preset | Description |
|---|---|
| **Interior Daylight** | Sun + sky area + interior fill. Natural side window light |
| **Interior Night Artificial** | Warm pendants + cool accent. Intimate atmosphere |
| **Exterior Golden Hour** | Low warm sun + cool sky fill. Long shadows |
| **Exterior Overcast** | Diffuse overcast sky. No hard shadows. Clean arch-viz |
| **Window Natural Minimal** | Single window as sole source. Minimalist photorealism |

### 🎨 Creative (4)
Atmospheric and editorial setups for stylized rendering.

| Preset | Description |
|---|---|
| **Moody Drama** | Hard front-side spot, no fill. Deep shadows and dark atmosphere |
| **High Key Ethereal** | No visible shadows. Cold wrap softboxes. Fashion / conceptual |
| **Neon RGB Atmosphere** | Blue key, orange fill, cyan rim. Cyberpunk / editorial |
| **Candlelight Atmosphere** | Very warm point sources + minimal bounce. Deep darkness |

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
After applying, two sliders let you fine-tune the whole rig without touching individual lights:

| Control | Effect |
|---|---|
| **Intensity** | Multiplies all light energies proportionally — ratios between lights are preserved |
| **Temp Offset (K)** | Shifts all colour temperatures. +500 K = warmer overall. Does not affect RGB lights |
| **Fill Ratio** | Adjusts in-scene fill and rim energy relative to the key light without re-applying the preset |

`Fill Ratio` is live: `1.0` keeps fill equal to key, `0.5` gives a classic 2:1 ratio,
and `0.0` removes fill for a more dramatic look. Rim lights track at half the fill ratio.

### User presets
You can turn any rig already in the scene into a reusable preset:

1. Apply or build a lighting rig with `LSM_` lights
2. Open **Scene Tools**
3. Click **Save Rig as Preset**
4. Choose name, category and description

User presets are stored in `user_presets.json`, reloaded automatically on startup, and
shown in the preset list with a star marker so they stand out from built-in presets.

### Asset Browser integration
All 30 presets are available directly from Blender's **Asset Browser** with full preview
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

The addon generates an `LSM_Assets.blend` library containing one **World** asset per preset,
with stable catalog IDs, description metadata, category tags, engine tags and light-count tags.

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
├── constants.py           Single source of truth: CATEGORY_DEFS, engine IDs,
│                          gain scales, Kelvin limits. All other modules derive
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
├── presets_data.py        30 preset dicts + validate_preset() + CATEGORIES alias
│                          (authoritative data lives in constants.CATEGORY_DEFS)
├── previews.py            Two-tier preview: PNG loader → procedural diagram fallback
├── preview_renderer.py    Standalone headless Blender script for thumbnail rendering
├── user_presets.json      Generated on demand when the user saves custom presets
├── assets/
│   ├── LSM_Assets.blend          Generated by the addon (not in repo)
│   └── blender_assets.cats.txt   Catalog with stable UUIDs for Asset Browser
└── previews/
    ├── README.txt
    ├── rembrandt.png             256×256 rendered thumbnails — 30 PNGs included in repo
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
