"""
Custom icon loading for Decentraland Tools.

Uses bpy.utils.previews to load PNG icons from the icons/ folder.
Icons are accessed via get_icon(name) which returns the icon_id
for use with icon_value= in Blender UI layouts.
"""

import bpy
import os

preview_collections = {}

ICON_DIR = os.path.join(os.path.dirname(__file__), "icons")

# Map of icon names to filenames
# Tabler Icons (MIT license) - https://tabler.io/icons - color #ff8800
ICONS = {
    "DCL_LOGO": "dcl_logo.png",
    # Scene Creation
    "GRID_DOTS": "grid-dots.png",          # Create Parcels
    "RULER": "ruler-2.png",                # Scene Limitations
    "SHIELD_CHECK": "shield-check.png",    # Scene Validator
    # Export
    "BULB": "bulb.png",                    # Export Lights
    "PACKAGE_EXPORT": "package-export.png", # Export glTF
    # Avatars
    "FRIENDS": "friends.png",              # Avatar Shapes
    "SHIRT_SPORT": "shirt-sport.png",      # Wearable Limits
    # Converter
    "BONE": "bone.png",                    # Particle to Armature
    # Materials & Textures
    "REPLACE": "replace.png",              # Replace Materials
    "ERASER": "eraser.png",                # Clean Unused Materials
    "IMAGE_IN_PICTURE": "image-in-picture.png",  # Resize Textures
    "PHOTO_CHECK": "photo-check.png",      # Validate Textures
    "FLIP_VERTICAL": "flip-vertical.png",  # Backface Culling
    # CleanUp
    "TRASH_X": "trash-x.png",             # Remove Empty Objects
    "TRANSFORM": "transform.png",          # Apply Transforms
    "FORMS": "forms.png",                  # Rename Mesh Data
    "PHOTO_EDIT": "photo-edit.png",        # Rename Textures
    "EDIT": "edit.png",                    # Batch Rename Objects
    # LOD
    "CUBE_SPARK": "cube-spark.png",        # LOD Generator
    # Viewer
    "EYE_DOTTED": "eye-dotted.png",        # Toggle Display Mode
    # Colliders
    "TAG": "tag.png",                      # Add Suffix
    "MAP_OFF": "map-off.png",              # Remove UVs
    "SPHERE_OFF": "sphere-off.png",        # Strip Materials
    "POLYGON": "polygon.png",              # Simplify
    # Documentation
    "BOOK": "book.png",                    # Documentation
    "BOOK_2": "book-2.png",               # Limits Guide
    "FILE_DESC": "file-description.png",   # Asset Guide
}


def register():
    """Load all custom icons into a preview collection."""
    icons = bpy.utils.previews.new()
    for name, filename in ICONS.items():
        filepath = os.path.join(ICON_DIR, filename)
        if os.path.exists(filepath):
            icons.load(name, filepath, 'IMAGE')
    preview_collections["dcl"] = icons


def unregister():
    """Remove all preview collections."""
    for pcoll in preview_collections.values():
        bpy.utils.previews.remove(pcoll)
    preview_collections.clear()


def get_icon(name):
    """Return the icon_id for a custom icon, or 0 if not found."""
    pcoll = preview_collections.get("dcl")
    if pcoll and name in pcoll:
        return pcoll[name].icon_id
    return 0
