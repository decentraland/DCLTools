"""Payload helpers for the Builder Live Preview bridge.

The Builder's ``/live-preview`` page connects to a tiny local HTTP server
exposed by this add-on: ``GET /state`` returns the JSON metadata built here and
``GET /model.glb`` returns the latest export. The page polls ``/state`` and
re-fetches the model whenever ``version`` moves, then hot-swaps it on the
avatar without reloading. Everything in this module is plain Python so it can
be exercised without Blender.
"""

import json
from urllib.parse import quote

DEFAULT_PREVIEWER_URL = "https://decentraland.org/builder/live-preview"

# Wearable categories accepted by the Builder (WearableCategory in @dcl/schemas).
WEARABLE_CATEGORIES = (
    "upper_body",
    "lower_body",
    "hands_wear",
    "feet",
    "hat",
    "helmet",
    "top_head",
    "tiara",
    "mask",
    "eyewear",
    "earring",
    "hair",
    "facial_hair",
    "eyes",
    "eyebrows",
    "mouth",
    "skin",
    "body_shape",
)


def normalize_previewer_url(raw):
    """Turn whatever was pasted into a usable previewer page URL.

    Accepts a bare host, a full URL, and URLs that still carry a query or
    fragment. The path is kept: the value is the page itself.
    """
    value = (raw or "").strip()
    if not value:
        return ""

    if "://" not in value:
        value = f"https://{value.lstrip('/')}"

    return value.split("?", 1)[0].split("#", 1)[0].rstrip("/")


def live_preview_url(page_url, bridge_url=""):
    """The previewer page to open.

    ``bridge_url`` is handed over as the ``bridge`` query param so the page
    connects to the local bridge without the user pasting anything.
    """
    url = normalize_previewer_url(page_url)
    if not url:
        raise ValueError("Previewer URL is empty")
    if bridge_url:
        url += f"?bridge={quote(bridge_url, safe='')}"
    return url


# Body-mesh collections created by Import DCL Rig. Meshes in them are only a
# problem for full-scene exports: an explicit selection of them is a
# deliberate body_shape/skin wearable.
REFERENCE_AVATAR_COLLECTIONS = frozenset({"Avatar_ShapeA", "Avatar_ShapeB"})


def wearable_export_error(objects, *, selected_only):
    """Why exporting ``objects`` would show a broken wearable preview, or None.

    ``objects`` describes everything the GLB export would include, as
    ``(object_type, collection_names)`` pairs. An explicit selection is
    trusted beyond being non-empty and containing a mesh; only full-scene
    exports are checked for content that cannot belong to a wearable.
    """
    objects = list(objects)

    if not objects:
        return (
            "nothing is selected — select the wearable mesh"
            if selected_only
            else "the scene has no exportable objects"
        )

    if not any(obj_type == "MESH" for obj_type, _ in objects):
        return (
            "the selection contains no meshes and nothing is bound to the selected armature — select the wearable mesh"
            if selected_only
            else "the scene contains no meshes"
        )

    if selected_only:
        return None

    hint = 'enable "Selected Only" and select the wearable mesh'

    if any(
        REFERENCE_AVATAR_COLLECTIONS.intersection(colls) for obj_type, colls in objects if obj_type == "MESH"
    ):
        return f"the export would include the reference avatar's body — {hint}"

    armature_count = sum(1 for obj_type, _ in objects if obj_type == "ARMATURE")
    if armature_count > 1:
        return f"the export would include {armature_count} armatures, but a wearable uses at most one — {hint}"

    return None


def readable_category(name):
    """ "upper_body" -> "Upper Body", matching the Builder's labels."""
    return name.replace("_", " ").title()


def build_state_payload(*, version, is_emote, name, category=""):
    """The ``/state`` body. The Builder treats a changed ``version`` as "re-fetch the model"."""
    return json.dumps(
        {
            "version": int(version),
            "type": "emote" if is_emote else "wearable",
            "name": name or "Blender Preview",
            "category": "" if is_emote else category,
        },
        separators=(",", ":"),
    )
