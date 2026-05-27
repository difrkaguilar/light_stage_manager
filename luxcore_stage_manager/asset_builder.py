# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026  difrkaguilar + Claude (Anthropic)
# Light Stage Manager -- Asset Browser library generator

"""Generates (or regenerates) ``assets/LSM_Assets.blend``.

Each LSM preset becomes a ``bpy.types.World`` datablock marked as an asset:

    World.name            = preset["name"]
    World["lsm_preset_id"] = preset["id"]   ← custom property, used by the
                                               Apply-from-asset operator
    World.asset_data.description  = preset["description"]
    World.asset_data.catalog_id   = <uuid matching blender_assets.cats.txt>
    World.asset_data.tags         = [preset["category"], "LSM"]

The .blend file is saved next to ``blender_assets.cats.txt`` in the
``assets/`` sub-directory of the addon folder.  The user then registers
that directory as a Blender Asset Library once in their preferences.

This module is intentionally side-effect-free at import time so it can be
imported during addon registration without touching bpy.data.
"""

from __future__ import annotations
import logging
import os

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stable catalog UUIDs — must match blender_assets.cats.txt exactly.
# Generated deterministically (MD5 of "LSM_CAT_<ID>"); never change them.
# ---------------------------------------------------------------------------

_CATALOG_UUIDS: dict[str, str] = {
    "PORTRAIT":     "1a04b50b-22b0-b921-cdd9-441d6fe312af",
    "PRODUCT":      "57adc79d-57eb-28e8-dc3d-d983217eba36",
    "ARCHITECTURE": "0cc1e517-a50e-6587-7d8d-cb48099714f9",
    "CREATIVE":     "1dc5a3d6-2771-cf53-2c28-07f35f2c46b4",
    "CINEMATIC":    "8f7e54e8-576c-1898-c9e5-74c1e47eac91",
    # Fallback for unknown future categories → root LSM catalog
    "_DEFAULT":     "24742c73-4cd1-c3f0-1a98-71d94889ed5b",
}


def _assets_dir() -> str:
    """Return the absolute path to the addon's ``assets/`` directory."""
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), "assets")


def assets_blend_path() -> str:
    """Absolute path to the generated ``LSM_Assets.blend`` file."""
    return os.path.join(_assets_dir(), "LSM_Assets.blend")


def _make_tag_safe(text: str) -> str:
    """Blender asset tags have a 64-char limit; truncate if needed."""
    return text[:64]


# ---------------------------------------------------------------------------
# Category placeholder colors (RGBA 0-1) used when no PNG preview exists.
# These give each category a distinct visual identity in the Asset Browser.
# ---------------------------------------------------------------------------

_CAT_COLORS: dict[str, tuple] = {
    "PORTRAIT":     (0.12, 0.18, 0.35, 1.0),   # deep blue
    "PRODUCT":      (0.10, 0.28, 0.18, 1.0),   # dark green
    "ARCHITECTURE": (0.28, 0.20, 0.10, 1.0),   # warm brown
    "CREATIVE":     (0.30, 0.10, 0.30, 1.0),   # purple
    "CINEMATIC":    (0.22, 0.08, 0.08, 1.0),   # dark red
    "_DEFAULT":     (0.15, 0.15, 0.15, 1.0),   # neutral grey
}

_PREVIEW_SIZE = 128   # pixels — Blender's standard asset thumbnail resolution


def _assign_preview(world, preset_id: str, category: str) -> bool:
    """Load the PNG thumbnail for *preset_id* and assign it to *world*'s asset preview.

    If the PNG does not exist, generates a solid-color placeholder whose hue
    matches the category so the Asset Browser grid is not a sea of grey globes.

    Returns True if a preview was successfully assigned.
    """
    import bpy

    addon_dir    = os.path.dirname(os.path.realpath(__file__))
    preview_path = os.path.join(addon_dir, "previews", preset_id + ".png")
    px_size      = _PREVIEW_SIZE

    try:
        preview = world.preview_ensure()

        if os.path.isfile(preview_path):
            # --- Load rendered PNG -------------------------------------------
            img = bpy.data.images.load(preview_path, check_existing=False)
            img.gl_load()
            w, h = img.size
            if w > 0 and h > 0:
                preview.image_size = (w, h)
                preview.image_pixels_float[:] = img.pixels[:]
                bpy.data.images.remove(img)
                log.debug("[LSM-Asset] Preview loaded from PNG: %s", preview_path)
                return True
            bpy.data.images.remove(img)
            log.warning("[LSM-Asset] PNG has zero size: %s", preview_path)

        # --- Solid-color placeholder -----------------------------------------
        # Build a px_size × px_size RGBA pixel buffer in the category color.
        # A subtle vignette makes it look less flat.
        color     = _CAT_COLORS.get(category, _CAT_COLORS["_DEFAULT"])
        n_pixels  = px_size * px_size
        half      = px_size / 2.0
        pixels    = []
        for row in range(px_size):
            for col in range(px_size):
                # Radial vignette: darken toward edges
                dx = (col - half) / half
                dy = (row - half) / half
                vignette = max(0.0, 1.0 - (dx * dx + dy * dy) * 0.6)
                pixels += [
                    color[0] * vignette,
                    color[1] * vignette,
                    color[2] * vignette,
                    1.0,
                ]

        preview.image_size = (px_size, px_size)
        preview.image_pixels_float[:] = pixels
        log.debug("[LSM-Asset] Placeholder preview for %r (category=%s)", preset_id, category)
        return True

    except Exception as exc:
        log.warning("[LSM-Asset] _assign_preview failed for %r: %s", preset_id, exc)
        return False

def generate_asset_library(report_fn=None) -> tuple[bool, str]:
    """Create or overwrite ``LSM_Assets.blend`` with all current presets.

    Must be called from within a running Blender session (requires bpy.data).

    Args:
        report_fn: Optional callable(level: str, message: str) for UI feedback.
                   Level is one of "INFO", "WARNING", "ERROR".

    Returns:
        (success: bool, message: str)
    """
    import bpy
    from .presets_data import PRESETS

    def _report(level: str, msg: str) -> None:
        log.info("[LSM-Asset] %s: %s", level, msg)
        if report_fn is not None:
            report_fn(level, msg)

    output_path = assets_blend_path()
    os.makedirs(_assets_dir(), exist_ok=True)

    _report("INFO", "Generating LSM Asset Library — %d presets …" % len(PRESETS))

    # ---- 1. Build a temporary in-memory .blend with World assets ------------
    # We use a temporary scene approach: create worlds in bpy.data,
    # mark them as assets, save to disk, then remove them from bpy.data
    # so we don't pollute the user's current session.

    created_worlds: list = []

    try:
        for preset in PRESETS:
            pid      = preset["id"]
            pname    = preset["name"]
            pcategory = preset.get("category", "PORTRAIT")
            pdesc    = preset.get("description", "")

            # Avoid duplicates if regenerating in the same session
            existing = bpy.data.worlds.get(pname)
            if existing is not None:
                bpy.data.worlds.remove(existing, do_unlink=True)

            world = bpy.data.worlds.new(name=pname)

            # Store the preset ID as a custom property so the Apply operator
            # can look it up without parsing the name.
            world["lsm_preset_id"] = pid
            world["lsm_version"]   = 1   # schema version for future migrations

            # Mark as Blender asset
            world.asset_mark()
            ad = world.asset_data

            # Description (truncated to Blender's 255-char field limit)
            if pdesc:
                ad.description = pdesc[:255]

            # Catalog: map category → stable UUID
            cat_uuid = _CATALOG_UUIDS.get(pcategory, _CATALOG_UUIDS["_DEFAULT"])
            ad.catalog_id = cat_uuid

            # Tags: category name + "LSM" sentinel
            ad.tags.new(_make_tag_safe(pcategory), skip_if_exists=True)
            ad.tags.new("LSM", skip_if_exists=True)

            # Engine hint tag
            lxc_cfg = preset.get("luxcore_cfg", {})
            engine_tag = lxc_cfg.get("engine", "PATH")
            ad.tags.new(_make_tag_safe(engine_tag), skip_if_exists=True)

            # Light count tag (useful for filtering in production)
            n_lights = len(preset.get("lights", []))
            ad.tags.new(_make_tag_safe("%d lights" % n_lights), skip_if_exists=True)

            # Preview: PNG thumbnail or solid-color category placeholder
            _assign_preview(world, pid, pcategory)

            created_worlds.append(world)
            log.debug("[LSM-Asset] Created world asset: %r (catalog=%s)", pname, cat_uuid)

        # ---- 2. Write the .blend file -----------------------------------------
        # bpy.data.libraries.write() saves only the specified datablocks,
        # creating a minimal .blend file without the full scene.
        data_blocks = set(created_worlds)
        bpy.data.libraries.write(
            filepath    = output_path,
            datablocks  = data_blocks,
            fake_user   = False,   # assets don't need fake users
            compress    = True,
            path_remap  = "NONE",
        )

        n = len(created_worlds)
        msg = "Asset library written: %s  (%d assets)" % (output_path, n)
        _report("INFO", msg)
        return True, msg

    except Exception as exc:
        msg = "Asset library generation failed: %s" % exc
        log.exception("[LSM-Asset] %s", msg)
        _report("ERROR", msg)
        return False, msg

    finally:
        # ---- 3. Clean up — remove temporary worlds from current session ------
        # This is critical: we don't want 30 extra World datablocks
        # lingering in the user's .blend file after generation.
        for world in created_worlds:
            try:
                if world.name in bpy.data.worlds:
                    bpy.data.worlds.remove(world, do_unlink=True)
            except Exception as exc:
                log.warning("[LSM-Asset] Could not remove temp world %r: %s",
                            world.name, exc)


# ---------------------------------------------------------------------------
# Query helpers — used by panels and operators
# ---------------------------------------------------------------------------

def asset_library_exists() -> bool:
    """Return True if ``LSM_Assets.blend`` exists on disk."""
    return os.path.isfile(assets_blend_path())


def get_active_lsm_asset(context) -> str | None:
    """Return the preset ID of the currently active Asset Browser asset,
    or None if no LSM asset is selected.

    Compatible with Blender 4.0+ (bpy.context.asset).
    Falls back gracefully on older builds.
    """
    try:
        asset = getattr(context, "asset", None)
        if asset is None:
            return None

        # bpy.types.AssetRepresentation (4.0+)
        # The asset name matches World.name which matches preset["name"].
        # But we stored lsm_preset_id as a custom property — try that first.
        # Custom properties are accessible via asset.metadata in 4.1+.
        metadata = getattr(asset, "metadata", None)
        if metadata is not None:
            props = getattr(metadata, "properties", None)
            if props is not None and "lsm_preset_id" in props:
                return props["lsm_preset_id"]

        # Fallback: match by name against PRESETS_BY_ID
        from .presets_data import PRESETS_BY_ID
        asset_name = getattr(asset, "name", None)
        if asset_name:
            # Try exact name match
            for pid, preset in PRESETS_BY_ID.items():
                if preset["name"] == asset_name:
                    return pid

        return None

    except Exception as exc:
        log.debug("[LSM-Asset] get_active_lsm_asset: %s", exc)
        return None


def is_lsm_asset(context) -> bool:
    """Return True if the active Asset Browser asset is an LSM preset."""
    return get_active_lsm_asset(context) is not None
