"""Payload helpers for the Builder Live Preview bridge.

The Builder's ``/live-preview`` page connects to a tiny local HTTP server
exposed by this add-on: ``GET /state`` returns the JSON metadata built here and
``GET /model.glb`` returns the latest export. The page polls ``/state`` and
re-fetches the model whenever ``version`` moves, then hot-swaps it on the
avatar without reloading. Everything in this module is plain Python so it can
be exercised without Blender.
"""

import json

DEFAULT_BUILDER_URL = "https://builder.decentraland.org"
LIVE_PREVIEW_PATH = "/live-preview"

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


def normalize_builder_url(raw):
    """Turn whatever was pasted into a usable Builder origin.

    Accepts a bare host ("builder.decentraland.zone"), a full URL, and URLs
    that still carry a path, query or fragment.
    """
    value = (raw or "").strip()
    if not value:
        return ""

    if "://" not in value:
        value = f"https://{value.lstrip('/')}"

    return value.split("?", 1)[0].split("#", 1)[0].rstrip("/")


def live_preview_url(base_url):
    """The Builder page to open for a given deployment."""
    root = normalize_builder_url(base_url)
    if not root:
        raise ValueError("Builder URL is empty")
    return f"{root}{LIVE_PREVIEW_PATH}"


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
