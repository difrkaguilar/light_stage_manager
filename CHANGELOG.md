# Changelog

All notable changes to **Light Stage Manager** are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).  
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [3.5.0] — 2026-05-31

Viewport overlay, per-light control panel, solo mode, live-update callbacks,
bake intensity, per-light Kelvin editing, target empties, and LuxCore ray
visibility. All modifier sliders (Intensity, Temp Offset, Gel, Fill Ratio)
now update the rig in real time without re-applying the preset.

### Added — Viewport Overlay (`overlay.py`)
- GPU draw handler registered with `SpaceView3D.draw_handler_add`
  (`POST_PIXEL`) draws coloured contour outlines around every visible
  LSM light in the 3D Viewport:
  - AREA: 4-corner rectangle
  - SPOT: 16-segment circle at 1.5 m cone depth
  - SUN: direction arrow (origin → tip)
  - POINT: 12-segment view-aligned circle
- Colour-coded by role: key=yellow · fill=blue · rim=green · env=purple ·
  gobo=orange · target=grey
- `blf` text labels (short name) rendered near each contour with drop shadow
- Enabled/disabled via `lsm_props.show_overlay` (`BoolProperty`) — stored
  as `scene["lsm_overlay_enabled"]` scene custom property
- Toggle exposed as eye icon in the **Scene Lights** panel header

### Added — Scene Lights Inline Panel (`LSM_PT_SceneLightsInline`)
- New collapsible **Scene Lights** panel (N-panel order 40) lists every
  LSM light in the scene grouped by role (key → fill → rim → env)
- Per-light primary row: visibility toggle · role dot icon · energy slider
  (`ld.energy`) · color swatch (`ld.color`) · Solo button
- Per-light secondary row (0.75× height): **D** diffuse toggle · **S**
  specular toggle · **K** Kelvin popup button · **T** target toggle
- **Bake Intensity** alert banner when `abs(intensity_multiplier - 1.0) > 0.001`
- **Exit Solo** alert banner while Solo mode is active
- Panel hidden automatically when no LSM lights are in scene (`poll`)

### Added — Solo Mode
- `LSM_OT_SoloLight` (`lsm.solo_light`): saves current viewport/render
  visibility of all LSM lights into `bpy.app.driver_namespace` keyed by
  `lsm_solo_visibility_stack`, then hides all except the target light
- `LSM_OT_SoloToggle` (`lsm.solo_toggle`): while in Solo mode, toggle
  an additional light on or off without exiting Solo
- `LSM_OT_ExitSolo` (`lsm.exit_solo`): pops the visibility stack and
  restores every light to its pre-Solo state; removes `lsm_solo_active`
  from the scene
- `scene["lsm_solo_active"]` tracks the currently soloed light name for
  panel button highlight

### Added — Live Update System
- `LSM_OT_LiveUpdate` (`lsm.live_update`): new unified operator called
  by all four property `update=` callbacks
- `apply_live_adjustments(scene, intensity_mult, temp_offset, gel_id,
  fill_ratio)` in `scene_builder.py`: replaces `apply_fill_ratio()`.
  Always starts from `lsm_base_energy` / `lsm_base_color` / `lsm_kelvin`
  stored at creation time — adjustments never accumulate across slider moves
- `intensity_multiplier`, `temperature_offset`, `gel_preset`, `fill_ratio`
  all have `update=lambda self, ctx: bpy.ops.lsm.live_update()` — changes
  are immediate, no manual "Apply" step needed after preset is loaded
- LuxCore gain and RGB sync inside `apply_live_adjustments()`: only
  `luxcore.gain` and `luxcore.rgb_gain` are written per drag event — avoids
  creating new `ConstFloatTexture3` objects on every call
- New custom properties stored on each light object at creation time:
  - `lsm_base_energy` — actual scaled energy at `intensity_mult = 1.0`
  - `lsm_kelvin` — original preset Kelvin (−1.0 sentinel for RGB lights)
  - `lsm_base_color` — original resolved RGB (3-tuple)
  - `lsm_luxcore_gain` — `luxcore_gain` value from the preset descriptor

### Added — Bake Intensity
- `LSM_OT_BakeIntensity` (`lsm.bake_intensity`): writes the current
  `ld.energy` (which already reflects the multiplier) into `lsm_raw_energy`
  and `lsm_base_energy` per light, then resets `intensity_multiplier` to 1.0
- `poll`: enabled only when `|intensity_multiplier − 1.0| > 0.001` and
  LSM lights exist
- Prevents multiplier stacking when re-applying or saving a preset after
  global exposure has been adjusted

### Added — Per-Light Editing Operators
- `LSM_OT_SetLightDiffuse` (`lsm.set_light_diffuse`): toggles diffuse
  contribution. Blender 4.x: `diffuse_factor` (float); older: `use_diffuse`
  (bool). Stores result in `obj["lsm_use_diffuse"]`. Updates LuxCore ray
  visibility via `set_lxc_light_ray_visibility()`
- `LSM_OT_SetLightSpecular` (`lsm.set_light_specular`): same for specular
  (`specular_factor` / `use_specular`). Stores in `obj["lsm_use_specular"]`
- `LSM_OT_SetLightKelvin` (`lsm.set_light_kelvin`): popup with Kelvin
  slider (1000–12 000 K). Updates `lsm_kelvin` and `lsm_base_color` on the
  object, then calls `lsm.live_update` so gel and global offset are applied
  on top of the new base temperature. `invoke` pre-fills from stored Kelvin
- `LSM_OT_ToggleLightTarget` (`lsm.toggle_light_target`): creates a
  `LSM_Target_<Name>` Empty (PLAIN_AXES, 0.15 m) at the light's current
  aim point (location + forward × 2 m) and adds a `TRACK_TO` constraint
  (`-Z → target`, `up_axis = Y`). Re-invoking removes the constraint and
  the Empty. `obj["lsm_has_target"]` tracks state for panel button depress

### Added — LuxCore Ray Visibility
- `set_lxc_light_ray_visibility(light_obj, diffuse, specular)` in
  `lxc_compat.py`: toggles `indirect_diffuse_enable` and
  `indirect_specular_enable` via BLC 2.10 nested `visibility` group
  (with shorter `diffuse`/`specular` alias fallback and flat-layout
  fallback for older BLC)

### Changed
- `apply_fill_ratio()` removed from `scene_builder.py`; replaced by
  `apply_live_adjustments()` which handles fill ratio as one parameter
- `LSM_OT_AdjustFillRatio` kept for backward compatibility only — its
  `execute()` now delegates to `bpy.ops.lsm.live_update()` and is
  marked `INTERNAL` in `bl_options`
- `remove_lsm_lights()` now also removes `LSM_Target_*` Empty objects
  (created by `LSM_OT_ToggleLightTarget`)
- `apply_lxc_light_props()` in `lxc_compat.py`: three debug `print()`
  calls removed and replaced with `log.debug()` to keep the console clean
- `apply_lxc_object_visibility()` docstring simplified; object-visibility
  and ray-visibility concerns separated into distinct functions
- `LSM_SceneProperties.intensity_multiplier` description updated:
  "in the preset" → "in the scene" (applies live to existing lights)
- `LSM_SceneProperties.temperature_offset` description expanded to note
  that RGB-only lights are not affected
- `LSM_SceneProperties.gel_preset` description simplified
- `panels.py`: `import CATEGORIES` added from `presets_data`; `log`
  logger initialised at module level
- `LSM_OT_SavePresetFromScene`: removed dangling `save_op.preset_name = ""`
  that caused `AttributeError: 'NoneType' has no attribute 'preset_name'`
  in some Blender versions

### Fixed
- Intensity/gel/temp-offset sliders had no real-time effect on lights
  already in scene — all three were missing `update=` callbacks. Fixed
  by routing through `lsm.live_update`
- LuxCore live updates were creating a new `ConstFloatTexture3` node on
  every slider drag event. Fixed by writing only `gain` and `rgb_gain`
  directly rather than calling `apply_lxc_light_props()` in the hot path
- Fill ratio for rim lights was computed relative to key energy at `1.0`
  regardless of scene scale. Fixed: rim ratio now tracks the scaled key
  energy via `lsm_base_energy`

---

## [3.4.0] — 2026-05-28

The largest release to date. Introduces a full cinematic preset library, a gel
colour system, scale-aware lighting, fill-ratio control, user preset persistence,
Asset Browser integration, and Blender Extensions Platform compatibility.

### Added — Presets
- **4 new CINEMATIC presets** bringing the cinematic category to 8 total:
  - `cin_kubrick` — Kubrick Overhead Hard: surgical SPOT from directly above,
    1:25 fill ratio, cold blue rim. Near-zero ambient
  - `cin_zsigmond_cold` — Zsigmond Cold Exterior: weak winter SUN at 4800 K +
    flat overcast sky dome at 8500 K. No artificial fill — sky IS the fill
  - `cin_lubezki_window` — Lubezki Continuous Window: single AREA source
    (3.5 × 3 m wall window). All fill comes from global illumination. The most
    minimal setup in the collection. BIDIR + 1200 samples
  - `cin_fincher` — Fincher Controlled: hard SPOT with physical **gobo plane**
    for projected shadow patterns. 1:43 key-to-fill ratio. Assign your own B&W
    texture to `LSM_Gobo_Key_Precise_Mat` to project patterns
- **Automotive Studio Rig** added to PRODUCT category: matched vertical strip
  lights for bodywork curvature, overhead panel, front key, cyclorama ground fill
- Total preset count: **34** (8 CINEMATIC · 9 PRODUCT · 8 PORTRAIT ·
  5 ARCHITECTURE · 4 CREATIVE)

### Added — Gobo System
- `_create_gobo_plane()` in `scene_builder.py`: physical shadow-casting mesh
  plane created in front of SPOT lights when descriptor contains `"gobo"` key
- Material with `ShaderNodeTexChecker` placeholder, `MixShader` transparency
  controlled by texture, `shadow_method = "CLIP"`, invisible to camera
  (`visible_camera = False`, `visible_shadow = True`)
- LuxCore: plane marked invisible via `apply_lxc_object_visibility()`
- Preset descriptors accept optional `"gobo": {"size", "distance", "texture"}`

### Added — Gel Colour System
- `GEL_PRESETS` in `constants.py` — 20 named cinematographic colour gels,
  single source of truth. Families:
  - **Tungsten/warm**: Tungsten Warm · Amber Deep · Straw
  - **Daylight/cool**: CTB Full · CTB Half · Sky Blue · Ice Blue
  - **Cinematic palettes**: Fincher Green · Kubrick Cold · Lubezki Warm ·
    WKW Amber · WKW Neon Green · BR2049 Orange · BR2049 Blue
  - **Special effects**: Lavender · Rose · Plus Green · Minus Green · Fire/Explosion
- `GEL_COLORS` and `GEL_ENUM_ITEMS` derived automatically — no manual duplication
- `gel_preset` `EnumProperty` in `LSM_SceneProperties` — global rig tint
- Per-light `"gel"` key in descriptors overrides global gel
- Gel applied as RGB multiplier after kelvin/color resolution in `create_light()`
- UI: gel selector in Light Modifiers panel between Temp Offset and Fill Ratio

### Added — Scale-Aware Lighting
- `_compute_scale_and_origin(context)` in `operators.py`: computes reference
  scale and orbit centre from active object bounding box (world space),
  all visible meshes, or manual input
- `scene_scale` and `scene_origin` parameters added to `create_light()` and
  `apply_preset()`
- Position scaling: `location_world = (preset.location × scale) + origin`
- Energy scaling: `scale²` for AREA/SPOT/POINT (inverse-square law);
  linear for SUN (parallel rays, distance-independent)
- Light size scaling: linear (`size`, `size_y`, `shadow_soft_size`)
- `scale_reference` EnumProperty: **Active Object** · **All Visible** · **Manual**
- `manual_scale` FloatProperty with `unit="LENGTH"` for explicit override
- Live feedback in Light Modifiers panel: shows computed scale, origin, and
  resulting energy/size multipliers before applying

### Added — Fill Ratio Control
- `fill_ratio` FloatProperty in `LSM_SceneProperties` (0.0–2.0)
- `apply_fill_ratio()` in `scene_builder.py`: operates on in-scene LSM lights
  without re-applying the preset. Key light energy unchanged; fill lights
  scaled by ratio; rim lights at half the fill ratio
- `LSM_OT_AdjustFillRatio` operator — called by `update=` callback, supports UNDO
- Ratio readout in panel: `8:1 (key:fill)` format
- Panel shows fill slider only when both key and fill roles are present in scene
- Light role metadata (`lsm_role`: key/fill/rim/gobo) stored as custom property
  on each light object at creation time

### Added — User Preset Persistence
- `user_presets.json` in addon directory for user-created presets
- `reload_user_presets()` in `presets_data.py`: hot-reloads without restart.
  `PRESETS` converted to mutable list; `PRESETS_BY_ID` updated in place
- `_serialize_light()` in `operators.py`: reverse-engineers scene lights back
  to normalised preset schema (reverses scale, recovers aim from matrix)
- `LSM_OT_SavePresetFromScene`: dialog with name, category, description.
  Pre-fills from active preset. Validates before saving. Replaces on same name
- `LSM_OT_DeleteUserPreset`: confirmation dialog, removes from JSON, hot-reloads
- UIList: user presets marked with `★` prefix and `SOLO_ON` icon
- Scene Tools panel: **Save Rig as Preset** always visible (when LSM lights exist),
  **Delete Selected** enabled only when active preset is user-created
- User presets loaded automatically at addon startup

### Added — Asset Browser Integration
- `asset_builder.py`: generates `assets/LSM_Assets.blend` with one
  `bpy.types.World` asset per preset
- Each World carries: `lsm_preset_id` custom property, description, stable
  `catalog_id` UUID, category and engine tags
- `_assign_preview()`: loads PNG from `previews/<id>.png` into
  `world.preview_ensure()` pixel buffer; falls back to solid-color vignette
  placeholder per category if PNG absent
- `blender_assets.cats.txt` with stable deterministic UUIDs (MD5 of category
  name) — colon-separated format as required by Blender
- `LSM_OT_GenerateAssetLibrary`: one-click library generation from Preferences
- `LSM_OT_ApplyFromAsset`: reads `context.asset`, resolves preset ID,
  delegates to full scale-aware apply pipeline. Syncs N-panel selection
- `LSM_PT_AssetBrowser` panel (`FILE_BROWSER / TOOL_PROPS`): shows preset
  metadata, light summary, Apply button, and quick Intensity/Scale controls
- Preferences: Asset Library section with generation button, status indicator,
  and 4-step setup guide

### Added — Blender Extensions Platform
- `blender_manifest.toml` at addon root — schema 1.0.0, Blender 4.2+ minimum,
  GPL-3.0-or-later, stable id `light_stage_manager`, `files` permission declared
- Separate distribution zip (`_extension.zip`) with files at root (no subfolder)
  for submission to `extensions.blender.org`
- Legacy `_v3_4_0.zip` (subfolder structure) retained for `Install from Disk`
  and Blender 4.1 compatibility

### Added — HDRI Support
- `"hdri"` added to `VALID_ENV_TYPES`
- `resolve_hdri_path(name)` in `cycles_compat.py`: searches
  `bpy.context.preferences.studio_lights` for WORLD-type lights by name
  (case-insensitive, with or without extension)
- `list_blender_hdris()`: returns all available Blender built-in HDRIs
- `apply_cycles_sky()` extended: `type = "hdri"` branch builds
  `ShaderNodeTexEnvironment → ShaderNodeMapping → ShaderNodeBackground` node tree
  with rotation support. Falls back to sky2 if file not found
- `LuxCoreWorldProxy.configure_hdri()`: sets `world.luxcore.light = "INFINITE"`,
  loads image with `check_existing=True`, applies gain/rotation/gamma
- Scene builder dispatches `hdri` type for both LuxCore and Cycles paths
- Preset schema: `"env_light": {"type": "hdri", "name": "forest.exr", "gain": 0.8}`

### Added — Thumbnails
- 34 PNG thumbnails (256 × 256) bundled in `previews/` — no render step required
- 4 procedurally generated placeholders for new CINEMATIC presets evoke each
  film style (radial bloom + vignette + category palette, pure stdlib)

### Changed
- `constants.py` is now the **single source of truth** for all categories:
  `CATEGORY_DEFS` drives `VALID_CATEGORIES`, `CATEGORY_ICONS`, the panel
  `EnumProperty`, and the asset catalog UUIDs. One edit propagates everywhere
- `CINEMATIC` category added (`"SEQUENCE"` icon, enum int 5)
- `PRESETS` list in `presets_data.py` converted from tuple to mutable list
  to support hot-reload of user presets
- `CATEGORIES` in `presets_data.py` is now an alias to `constants.CATEGORY_DEFS`
  (same object in memory) — no duplication
- `panels.py` `CAT_ICONS` replaced by alias to `constants.CATEGORY_ICONS`
- `active_category` EnumProperty now built from `list(CATEGORIES)` — no
  hardcoded items
- Light modifiers panel restructured: scale reference block with live feedback
  added between temperature controls and apply options
- `apply_preset()` log message includes scale and origin values
- `bl_info` description updated to reflect 34 presets and Asset Browser support
- README fully rewritten: artist-first structure, editorial preset descriptions,
  engine support table, architecture reference, contributing guide

### Fixed
- `candlelight` preset: `Candle_Main` (gain 8.0) and `Candle_2` (gain 6.0) were
  near-black in Cycles — fixed with `cycles_energy: 140.0` and `90.0` respectively
- `blender_assets.cats.txt` separator was `\t` (tab) — corrected to `:` (colon)
  as required by Blender. Previously caused all assets to appear under "Unassigned"
- `blender_manifest.toml` used `[author]` TOML section — corrected to flat
  `maintainer` string. Previously caused "missing maintainer" install failure
- `blender_manifest.toml` tag `"Rendering"` not in Blender Extensions vocabulary —
  replaced with valid tags `"Lighting"` and `"Compositing"`

---

## [3.3.0] — 2026-05 (internal)

Architecture cleanup sprint. Eliminated category definition duplication across
three modules and introduced the dual-calibration system for cross-engine energy.

### Added
- `CATEGORY_DEFS` in `constants.py` as authoritative category list (id, name,
  description, icon, enum_int). `VALID_CATEGORIES` and `CATEGORY_ICONS` derived
  automatically
- `cycles_energy` optional field in light descriptors (**Opción B**
  dual-calibration): overrides energy for Cycles/EEVEE path only. LuxCore
  continues using `energy × luxcore_gain`. Resolves systematic under-exposure
  of high-gain POINT lights in Cycles
- Phase 2b in `create_light()` applies `cycles_energy` override with correct
  `scene_scale²` factor

### Changed
- `CATEGORIES` in `presets_data.py` replaced with alias to `constants.CATEGORY_DEFS`
- `CATEGORY_ICONS` in `presets_data.py` removed — now imported from `constants`
- `LSM_SceneProperties.active_category` EnumProperty items now built from
  `list(CATEGORIES)` — no hardcoded strings
- `panels.py` local `CAT_ICONS` dict removed, replaced with import from `constants`

### Fixed
- `panels.py` `active_category` EnumProperty missing `"CINEMATIC"` entry causing
  `bpy_struct: item.attr = val: enum "CINEMATIC" not found` error on preset apply

---

## [3.2.0] — 2026-05 (internal)

First cinematic preset batch and scale-aware rig foundation.

### Added
- **4 CINEMATIC presets** (initial batch):
  - `cin_deakins_window` — Roger Deakins interior: 2.8 × 2 m window key,
    sky bounce, soft rear rim. BIDIR engine
  - `cin_wkw_amber_night` — Wong Kar-wai: amber POINT practical (gain 10.0),
    neon-green AREA accent, red wall bounce. BIDIR
  - `cin_br2049` — Blade Runner 2049: cold blue sky, orange neon strip,
    electric blue rim. PATH
  - `cin_a24_golden` — A24 Golden Naturalism: SUN at 3200 K, sky fill at
    10 000 K, ground bounce. BIDIR + 1000 samples
- `CINEMATIC` added to `VALID_CATEGORIES` and `CATEGORIES` enum
- `SEQUENCE` icon assigned to CINEMATIC category

### Architecture notes
- `cycles_energy` field identified as needed for WKW practical lights;
  implemented in v3.3.0 as Opción B

---

## [3.1.0] — 2026-04 (internal)

RNA-based property introspection, two-layer global persistence, and inline preset
editing operators.

### Added
- `_walk_rna()` for RNA-based property discovery — replaces hardcoded property
  lists in save/apply flows
- Two-layer global persistence: `bpy.app.driver_namespace` (session) +
  `user_presets.json` (disk)
- Global push/pull operators for cross-project preset access
- Inline preset editing operators (edit name, description, category in UIList)
- `lsm_props.preset_type` property: Preview / Production mode toggle

### Fixed
- Pyluxcore validator incorrectly running on RNA-mapped keys during save/apply —
  moved to external JSON import path only. This was the critical bug causing
  preset application to have no visible effect on render parameters

---

## [3.0.0] — 2026-03

Full rewrite introducing modular architecture, multi-engine support, and the
current scene_builder pipeline.

### Added
- `scene_builder.py`: two-phase light creation pipeline
  - Phase 1: Blender-native properties (all engines)
  - Phase 2a: LuxCore-specific properties via typed proxy classes
  - Phase 2b: Cycles/EEVEE properties
- `lxc_compat.py`: LuxCore API isolation with dual BLC 2.9 / 2.10 support
  - `LuxCoreLightProxy` and `LuxCoreWorldProxy` typed classes
  - `_try_set()` / `_try_get()` defensive attribute accessors
  - BLC 2.10 `color_mode` enum tried first; BLC 2.9 `use_color_temperature`
    bool as fallback
  - `apply_lxc_object_visibility()`: `visibility.camera = False` to prevent
    light geometry appearing in renders
  - `light_unit` forced to `"artistic"` before gain assignment
- `cycles_compat.py`: Cycles/EEVEE layer
  - `apply_cycles_sky()`: `sky2` → Nishita node tree; `constant` → Background
  - `CyclesSceneProxy.apply_from_lxc_cfg()`: translates LuxCore engine
    config (samples, depth, denoiser) to Cycles equivalents
  - `apply_cycles_area_spread()` for spread angle on AREA lights
- `presets_data.py`: validated preset schema with `validate_preset()`
- `constants.py`: single-file config (prefixes, engine IDs, gain scales,
  Kelvin limits, valid type sets)
- `preferences.py`: `AddonPreferences` with versioned migration system
  (`ADDON_DATA_VERSION`, `data_version` property, `_migrate()` method)
- `previews.py`: two-tier preview system — PNG loader with procedural
  diagram fallback
- `preview_renderer.py`: standalone headless Blender script for thumbnail
  batch rendering using Cycles + Suzanne reference mesh
- `LSM_` naming prefix and `LSM — <PresetName>` collection ownership for all
  created objects
- `detect_engine()` helper: maps `scene.render.engine` to internal enum

### Changed
- Replaced monolithic `__init__.py` structure with dedicated modules
- All `draw()` methods made passive (read-only) — mutations via `update=`
  callbacks only
- No `bpy.data` access during `register()` — prevents `_RestrictData` errors
  on Blender 4.4+

---

## [2.0.0] — 2026-02

Six-bug rewrite addressing critical blocking issues found in v1 production testing.

### Fixed — Critical
- `LSM_PresetListItem` double-registered as `PropertyGroup` — caused
  `ValueError: bpy_struct "…" registration error` on startup
- Missing `bl_context = 'render'` on render properties panel — panel never
  appeared in Properties editor
- Missing `preset_type` property (Preview / Production) — all presets applied
  with hardcoded PATH settings regardless of intended quality level
- `PRESETS_BY_ID` built before `PRESETS` list was fully populated — first
  preset in list was always missing from lookup
- `apply_preset()` called `bpy.ops.object.select_all()` inside a loop causing
  context errors when multiple lights were created
- LuxCore gain applied before `light_unit` was set — caused silent EV coupling
  failures where gain had no effect

### Added
- 14 built-in presets (8 PORTRAIT · 6 PRODUCT) replacing the 4 placeholder rigs
- Filterable UIList with category tabs
- Full operator coverage: Apply, Select, Remove, Reset, SetCategory, Diagnose,
  VerifyActive, RenderPreviews
- `preview_ensure()` integration for UIList thumbnail display

---

## [1.0.0] — 2026-01

Initial release. Proof of concept for LuxCore-aware lighting presets in Blender.

### Added
- `bl_info` addon scaffold targeting Blender 4.4 + BlendLuxCore 2.10
- 4 placeholder lighting presets: Three-Point, Rembrandt, High Key, Product
- Basic `EnumProperty` category filter (PORTRAIT, PRODUCT)
- Single `LSM_OT_ApplyPreset` operator creating lights via `bpy.ops.object.light_add()`
- Manual `luxcore.gain` and `luxcore.light_unit` assignment (no proxy layer)
- N-panel tab registration in 3D Viewport

---

*Light Stage Manager is developed by difrkaguilar.*  
*Issues and contributions: https://github.com/difrkaguilar/light_stage_manager*
