"""
Shared helpers for identifying Decentraland collider geometry.

Decentraland treats meshes whose name carries the "_collider" suffix as
collision geometry: the engine uses them for physics and never renders them.
Tools have to agree on what counts as a collider - and, just as importantly,
keep colliders out of anything that touches visuals (material merging, atlas
baking, UVs), because collision meshes are not drawn.
"""

COLLIDER_SUFFIX = "_collider"


def is_collider(obj):
    """True when *obj* is collider geometry, directly or by inheritance.

    Matches the convention used across the toolkit: the name *contains*
    "_collider" rather than ending with it, so Blender's ".001" duplicate
    suffixes still match. Children of a collider count as collision geometry
    too.
    """
    if obj is None:
        return False
    if COLLIDER_SUFFIX in obj.name:
        return True
    parent = obj.parent
    while parent is not None:
        if COLLIDER_SUFFIX in parent.name:
            return True
        parent = parent.parent
    return False
