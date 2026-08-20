"""Payload helpers for the Aang renderer preview.

The Aang renderer (https://github.com/decentraland/aang-renderer) loads custom
content in ``builder`` mode through a ``base64`` query parameter. That parameter
is *not* the model: it is a base64 encoded entity definition whose
``representations[].contents[]`` entries point at the model files by URL, the
same shape the Builder sends. Everything in this module is plain Python so it
can be exercised without Blender.
"""

import base64
import json
from urllib.parse import quote

BODY_SHAPE_MALE = "urn:decentraland:off-chain:base-avatars:BaseMale"
BODY_SHAPE_FEMALE = "urn:decentraland:off-chain:base-avatars:BaseFemale"
BODY_SHAPES = (BODY_SHAPE_MALE, BODY_SHAPE_FEMALE)

# Wearable categories accepted by the renderer (Runtime.Wearables.WearableCategories).
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

# "Base body" overrides in the Builder's Overrides section. Listing "hands" cancels
# the implicit hands-hiding that upper bodies get by default (AvatarUtils.ShouldHideHands),
# and "head" does the same for the skin category's implicit hides.
BASE_BODY_OVERRIDES = ("head", "hands")

# Emotes bundled with the renderer, used as the idle animation for wearable previews.
BUILTIN_EMOTES = (
    "idle",
    "clap",
    "dab",
    "dance",
    "fashion",
    "fashion-2",
    "fashion-3",
    "fashion-4",
    "love",
    "money",
    "fist-pump",
    "head-explode",
)

PREVIEW_ENTITY_ID = "urn:decentraland:off-chain:dcl-tools:blender-preview"

# Fallback renderer deployment, used when the add-on preferences are empty.
# The aang-renderer CI only publishes per-PR Vercel *preview* deployments and has no
# production job, so there is no stable domain to point at: the project's own
# aang-renderer.vercel.app alias serves a 404, and the per-branch aliases die with
# their branch. Immutable per-deployment URLs do survive, so this pins the newest
# one known good (PR #78, 2026-08-17). Replace it with a fresher deployment URL from
# any aang-renderer PR comment, or override it in the add-on preferences.
DEFAULT_RENDERER_URL = "https://aang-renderer-ps7qn5uwr-decentraland1.vercel.app"


def normalize_renderer_url(raw):
    """Turn whatever was pasted into a usable renderer origin.

    Accepts a bare host ("aang-abc123.vercel.app"), a full URL, and URLs that
    still carry a path, query or fragment — Vercel preview links are usually
    copied straight out of a PR comment.
    """
    value = (raw or "").strip()
    if not value:
        return ""

    if "://" not in value:
        value = f"https://{value.lstrip('/')}"

    return value.split("?", 1)[0].split("#", 1)[0].rstrip("/")


def readable_category(name):
    """ "upper_body" -> "Upper Body", matching the Builder's labels."""
    return name.replace("_", " ").title()


def sort_categories(values, order=WEARABLE_CATEGORIES):
    """Deduplicate and order a category selection so the same picks build the same URL.

    Blender hands ENUM_FLAG properties back as an unordered set.
    """
    rank = {name: index for index, name in enumerate(order)}
    return sorted({value for value in values if value}, key=lambda value: (rank.get(value, len(order)), value))


def _representation(body_shape, main_file, file_url):
    return {
        "bodyShapes": [body_shape],
        "mainFile": main_file,
        "contents": [{"key": main_file, "url": file_url}],
        "overrideHides": [],
        "overrideReplaces": [],
    }


def build_entity_definition(
    main_file,
    file_url,
    *,
    name="Blender Preview",
    category="upper_body",
    is_emote=False,
    loop=False,
    hides=(),
    replaces=(),
    removes_default_hiding=(),
    body_shapes=BODY_SHAPES,
    entity_id=PREVIEW_ENTITY_ID,
):
    """Build the entity definition the renderer decodes from the ``base64`` parameter.

    ``RawActiveEntity`` treats an empty ``data.category`` as "this is an emote",
    so both ``data`` and ``emoteDataADR74`` are always present and only one of
    them carries a category and representations.
    """
    representations = [_representation(shape, main_file, file_url) for shape in body_shapes]

    wearable_data = {
        "category": "" if is_emote else category,
        "hides": [] if is_emote else sort_categories(hides),
        "replaces": [] if is_emote else sort_categories(replaces),
        "removesDefaultHiding": [] if is_emote else sort_categories(removes_default_hiding, BASE_BODY_OVERRIDES),
        "representations": [] if is_emote else representations,
        "loop": False,
    }
    emote_data = {
        "category": "emote" if is_emote else "",
        "hides": [],
        "replaces": [],
        "removesDefaultHiding": [],
        "representations": representations if is_emote else [],
        "loop": bool(loop) if is_emote else False,
    }

    return {
        "id": entity_id,
        "thumbnail": "",
        "i18n": [{"code": "en", "text": name}],
        "data": wearable_data,
        "emoteDataADR74": emote_data,
    }


def encode_entity(entity):
    """Base64 encode an entity definition the way ``AangConfiguration.AddBase64`` expects.

    Standard (not URL-safe) base64, because the renderer decodes it with
    ``Convert.FromBase64String``. Callers must percent-encode the result before
    putting it in a query string.
    """
    payload = json.dumps(entity, separators=(",", ":"), sort_keys=False)
    return base64.b64encode(payload.encode("utf-8")).decode("ascii")


def build_preview_url(
    base_url,
    entities,
    *,
    body_shape=BODY_SHAPE_MALE,
    background="",
    emote="",
    projection="",
):
    """Assemble the renderer URL for one or more entity definitions."""
    root = normalize_renderer_url(base_url)
    if not root:
        raise ValueError("Renderer URL is empty")

    params = ["mode=builder", f"bodyShape={quote(body_shape, safe='')}"]

    if emote:
        params.append(f"emote={quote(emote, safe='')}")
    if projection:
        params.append(f"projection={quote(projection, safe='')}")

    hexcolor = (background or "").strip().lstrip("#")
    if hexcolor:
        params.append(f"background={quote(hexcolor, safe='')}")

    for entity in entities:
        # safe="" also escapes "+" and "/", which UrlDecode would otherwise turn
        # into a space and a path separator.
        params.append(f"base64={quote(encode_entity(entity), safe='')}")

    return f"{root}?{'&'.join(params)}"
