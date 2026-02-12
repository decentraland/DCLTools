"""
Blender version compatibility utilities.
Supports Blender 2.80 through 5.0+.
"""
import bpy

# Blender version tuple (major, minor, patch)
bl_version = bpy.app.version


def is_blender_50_or_newer():
    """Check if running Blender 5.0 or newer."""
    return bl_version >= (5, 0, 0)
