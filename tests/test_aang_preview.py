"""Tests for the Aang renderer preview payload and its wiring."""

import base64
import json
import os
import sys
from urllib.parse import parse_qs, urlparse

import pytest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
sys.path.insert(0, os.path.join(SRC_DIR, "ops"))

import aang_utils  # noqa: E402


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _decode_base64_param(url):
    params = parse_qs(urlparse(url).query)
    return [json.loads(base64.b64decode(value).decode("utf-8")) for value in params["base64"]]


class TestEntityDefinition:
    def test_wearable_entity_carries_category_and_representations(self):
        entity = aang_utils.build_entity_definition(
            "wearable_1.glb",
            "http://127.0.0.1:8000/wearable_1.glb",
            category="lower_body",
        )

        assert entity["data"]["category"] == "lower_body"
        assert len(entity["data"]["representations"]) == 2
        assert entity["emoteDataADR74"]["representations"] == []

        rep = entity["data"]["representations"][0]
        assert rep["mainFile"] == "wearable_1.glb"
        assert rep["contents"] == [{"key": "wearable_1.glb", "url": "http://127.0.0.1:8000/wearable_1.glb"}]
        assert rep["bodyShapes"] == [aang_utils.BODY_SHAPE_MALE]

    def test_wearable_main_file_is_listed_in_its_own_contents(self):
        # Representation.ForBodyShape drops any representation whose mainFile is
        # not present in both the representation contents and the entity content.
        entity = aang_utils.build_entity_definition("m.glb", "http://x/m.glb")
        for rep in entity["data"]["representations"]:
            assert rep["mainFile"] in [content["key"] for content in rep["contents"]]

    def test_emote_entity_leaves_data_category_empty(self):
        # RawActiveEntity.IsEmote is `string.IsNullOrEmpty(data.category)`.
        entity = aang_utils.build_entity_definition("emote_1.glb", "http://127.0.0.1:8000/emote_1.glb", is_emote=True)

        assert entity["data"]["category"] == ""
        assert entity["data"]["representations"] == []
        assert entity["emoteDataADR74"]["category"] == "emote"
        assert len(entity["emoteDataADR74"]["representations"]) == 2

    def test_emote_loop_flag_is_forwarded(self):
        entity = aang_utils.build_entity_definition("e.glb", "http://x/e.glb", is_emote=True, loop=True)
        assert entity["emoteDataADR74"]["loop"] is True

    def test_hides_are_applied_to_wearables_only(self):
        wearable = aang_utils.build_entity_definition("w.glb", "http://x/w.glb", hides=["hair", "facial_hair"])
        emote = aang_utils.build_entity_definition("e.glb", "http://x/e.glb", is_emote=True, hides=["hair"])

        assert wearable["data"]["hides"] == ["hair", "facial_hair"]
        assert emote["data"]["hides"] == []

    def test_overrides_are_carried_on_the_wearable(self):
        entity = aang_utils.build_entity_definition(
            "w.glb",
            "http://x/w.glb",
            hides=["hair"],
            replaces=["facial_hair"],
            removes_default_hiding=["hands"],
        )

        assert entity["data"]["hides"] == ["hair"]
        assert entity["data"]["replaces"] == ["facial_hair"]
        assert entity["data"]["removesDefaultHiding"] == ["hands"]

    def test_overrides_are_dropped_on_emotes(self):
        entity = aang_utils.build_entity_definition(
            "e.glb",
            "http://x/e.glb",
            is_emote=True,
            hides=["hair"],
            replaces=["facial_hair"],
            removes_default_hiding=["hands"],
        )

        assert entity["data"]["replaces"] == []
        assert entity["data"]["removesDefaultHiding"] == []

    def test_selection_order_does_not_change_the_payload(self):
        # Blender returns ENUM_FLAG values as an unordered set.
        a = aang_utils.build_entity_definition("w.glb", "http://x/w.glb", hides={"hair", "hat", "feet"})
        b = aang_utils.build_entity_definition("w.glb", "http://x/w.glb", hides={"feet", "hair", "hat"})
        assert a == b

    def test_both_data_blocks_always_exist(self):
        # JsonUtility dereferences `data` unconditionally, so it must never be missing.
        for is_emote in (False, True):
            entity = aang_utils.build_entity_definition("m.glb", "http://x/m.glb", is_emote=is_emote)
            assert "data" in entity
            assert "emoteDataADR74" in entity


class TestPreviewURL:
    def test_url_uses_builder_mode_and_round_trips_the_entity(self):
        entity = aang_utils.build_entity_definition("wearable_1.glb", "http://127.0.0.1:8000/wearable_1.glb")
        url = aang_utils.build_preview_url("https://renderer.example.com", [entity])

        params = parse_qs(urlparse(url).query)
        assert params["mode"] == ["builder"]
        assert params["bodyShape"] == [aang_utils.BODY_SHAPE_MALE]
        assert _decode_base64_param(url) == [entity]

    def test_base64_param_never_contains_raw_plus_or_slash(self):
        # UrlDecode turns a literal "+" into a space, which breaks FromBase64String.
        entity = aang_utils.build_entity_definition("w.glb", "http://127.0.0.1:8000/w.glb", name="~~~ ??? ///")
        raw_query = urlparse(aang_utils.build_preview_url("https://r.example.com", [entity])).query
        encoded = [part for part in raw_query.split("&") if part.startswith("base64=")][0]

        assert "+" not in encoded
        assert "/" not in encoded

    def test_encoded_payload_length_is_a_multiple_of_four(self):
        # AangConfiguration.AddBase64 rejects lengths that are 1 mod 4.
        entity = aang_utils.build_entity_definition("w.glb", "http://127.0.0.1:8000/w.glb")
        assert len(aang_utils.encode_entity(entity)) % 4 == 0

    def test_no_background_parameter_is_emitted(self):
        entity = aang_utils.build_entity_definition("w.glb", "http://x/w.glb")
        url = aang_utils.build_preview_url("https://r.example.com", [entity])
        assert "background" not in parse_qs(urlparse(url).query)

    def test_trailing_slash_and_existing_query_are_dropped(self):
        entity = aang_utils.build_entity_definition("w.glb", "http://x/w.glb")
        url = aang_utils.build_preview_url("https://r.example.com/?mode=marketplace", [entity])
        assert url.startswith("https://r.example.com?mode=builder")

    def test_bare_host_gets_an_https_scheme(self):
        entity = aang_utils.build_entity_definition("w.glb", "http://x/w.glb")
        url = aang_utils.build_preview_url("aang-renderer-abc123.vercel.app", [entity])
        assert url.startswith("https://aang-renderer-abc123.vercel.app?mode=builder")

    def test_local_renderer_keeps_its_scheme_and_port(self):
        entity = aang_utils.build_entity_definition("w.glb", "http://x/w.glb")
        url = aang_utils.build_preview_url("http://localhost:8080", [entity])
        assert url.startswith("http://localhost:8080?mode=builder")

    def test_empty_renderer_url_raises(self):
        entity = aang_utils.build_entity_definition("w.glb", "http://x/w.glb")
        with pytest.raises(ValueError):
            aang_utils.build_preview_url("   ", [entity])


class TestCategoryHelpers:
    def test_sorting_follows_the_declared_category_order(self):
        assert aang_utils.sort_categories({"feet", "upper_body", "hair"}) == ["upper_body", "feet", "hair"]

    def test_sorting_deduplicates_and_drops_blanks(self):
        assert aang_utils.sort_categories(["hair", "hair", "", None]) == ["hair"]

    def test_base_body_uses_its_own_order(self):
        assert aang_utils.sort_categories({"hands", "head"}, aang_utils.BASE_BODY_OVERRIDES) == ["head", "hands"]

    def test_unknown_values_sort_last_instead_of_raising(self):
        assert aang_utils.sort_categories({"hair", "zzz"}) == ["hair", "zzz"]

    def test_readable_labels_match_the_builder(self):
        assert aang_utils.readable_category("upper_body") == "Upper Body"
        assert aang_utils.readable_category("hands_wear") == "Hands Wear"


class TestRendererURLNormalization:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("aang-abc123.vercel.app", "https://aang-abc123.vercel.app"),
            ("https://aang-abc123.vercel.app/", "https://aang-abc123.vercel.app"),
            ("https://aang-abc123.vercel.app/?mode=marketplace", "https://aang-abc123.vercel.app"),
            ("  https://aang-abc123.vercel.app#top  ", "https://aang-abc123.vercel.app"),
            ("http://127.0.0.1:5500", "http://127.0.0.1:5500"),
            ("", ""),
            (None, ""),
        ],
    )
    def test_normalization(self, raw, expected):
        assert aang_utils.normalize_renderer_url(raw) == expected


class TestDefaultRendererURL:
    def test_default_is_set_and_absolute(self):
        assert aang_utils.DEFAULT_RENDERER_URL.startswith("https://")

    def test_default_survives_normalization_unchanged(self):
        assert aang_utils.normalize_renderer_url(aang_utils.DEFAULT_RENDERER_URL) == aang_utils.DEFAULT_RENDERER_URL

    def test_default_is_not_a_dead_project_alias(self):
        # aang-renderer.vercel.app is the repo homepage but has no deployment
        # aliased to it; only immutable per-deployment URLs stay reachable.
        assert aang_utils.DEFAULT_RENDERER_URL != "https://aang-renderer.vercel.app"

    def test_default_is_not_loopback(self):
        # The add-on's own server hosts the GLB, never the renderer itself.
        assert "127.0.0.1" not in aang_utils.DEFAULT_RENDERER_URL
        assert "localhost" not in aang_utils.DEFAULT_RENDERER_URL


class TestPreviewWiring:
    def test_modules_exist(self):
        assert os.path.isfile(os.path.join(SRC_DIR, "ops", "aang_utils.py"))
        assert os.path.isfile(os.path.join(SRC_DIR, "ops", "preview_aang.py"))

    def test_operators_are_imported_and_registered(self):
        init_src = _read(os.path.join(SRC_DIR, "__init__.py"))
        assert "OBJECT_OT_preview_in_aang," in init_src
        assert "OBJECT_OT_stop_aang_preview," in init_src
        assert "DCLToolsPreferences," in init_src

    def test_overrides_are_multi_select_flags(self):
        preview_src = _read(os.path.join(SRC_DIR, "ops", "preview_aang.py"))
        for prop in ("hides", "replaces", "base_body"):
            assert f"{prop}: bpy.props.EnumProperty" in preview_src
        assert preview_src.count('options={"ENUM_FLAG"}') == 3

    def test_draw_does_not_introspect_operator_rna(self):
        # In Blender 5.1 operator properties live on get_rna_type(), not on
        # self.bl_rna.properties — looking them up there raises KeyError.
        preview_src = _read(os.path.join(SRC_DIR, "ops", "preview_aang.py"))
        assert "bl_rna.properties" not in preview_src

    def test_background_input_is_gone(self):
        preview_src = _read(os.path.join(SRC_DIR, "ops", "preview_aang.py"))
        assert "background" not in preview_src

    def test_preview_buttons_are_drawn(self):
        init_src = _read(os.path.join(SRC_DIR, "__init__.py"))
        assert '"Preview Wearable"' in init_src
        assert '"Preview Emote"' in init_src

    def test_server_is_stopped_on_unregister(self):
        init_src = _read(os.path.join(SRC_DIR, "__init__.py"))
        unregister_src = init_src.split("def unregister():", 1)[1]
        assert "stop_preview_server()" in unregister_src

    def test_server_binds_to_loopback_only(self):
        preview_src = _read(os.path.join(SRC_DIR, "ops", "preview_aang.py"))
        assert '("127.0.0.1", 0)' in preview_src

    def test_readme_documents_the_preview(self):
        readme_src = _read(os.path.join(ROOT_DIR, "README.md"))
        assert "### Preview in Aang Renderer" in readme_src
