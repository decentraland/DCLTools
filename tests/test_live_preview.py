"""Tests for the Builder Live Preview bridge payload and its wiring."""

import json
import os
import sys

import pytest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
sys.path.insert(0, os.path.join(SRC_DIR, "ops"))

import bridge_utils  # noqa: E402


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class TestStatePayload:
    def test_wearable_payload_round_trips(self):
        state = json.loads(bridge_utils.build_state_payload(version=3, is_emote=False, name="Hat", category="hat"))
        assert state == {"version": 3, "type": "wearable", "name": "Hat", "category": "hat"}

    def test_emote_payload_drops_the_wearable_category(self):
        # The Builder page decides "is emote" from type, and an emote's category
        # comes from its own dropdown there.
        state = json.loads(bridge_utils.build_state_payload(version=1, is_emote=True, name="Wave", category="hat"))
        assert state["type"] == "emote"
        assert state["category"] == ""

    def test_version_is_always_an_int(self):
        state = json.loads(bridge_utils.build_state_payload(version="7", is_emote=False, name="x"))
        assert state["version"] == 7

    def test_name_falls_back_when_the_file_is_unsaved(self):
        state = json.loads(bridge_utils.build_state_payload(version=1, is_emote=False, name=""))
        assert state["name"] == "Blender Preview"


class TestBuilderURL:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("builder.decentraland.zone", "https://builder.decentraland.zone"),
            ("https://builder.decentraland.org/", "https://builder.decentraland.org"),
            ("https://builder.decentraland.org/?tab=x", "https://builder.decentraland.org"),
            ("  https://builder.decentraland.org#top  ", "https://builder.decentraland.org"),
            ("http://localhost:3000", "http://localhost:3000"),
            ("", ""),
            (None, ""),
        ],
    )
    def test_normalization(self, raw, expected):
        assert bridge_utils.normalize_builder_url(raw) == expected

    def test_live_preview_url_appends_the_page_path(self):
        assert bridge_utils.live_preview_url("http://localhost:3000/") == "http://localhost:3000/live-preview"

    def test_empty_builder_url_raises(self):
        with pytest.raises(ValueError):
            bridge_utils.live_preview_url("   ")

    def test_default_is_the_production_builder(self):
        assert bridge_utils.DEFAULT_BUILDER_URL == "https://builder.decentraland.org"


class TestReadableCategory:
    def test_labels_match_the_builder(self):
        assert bridge_utils.readable_category("upper_body") == "Upper Body"
        assert bridge_utils.readable_category("hands_wear") == "Hands Wear"


class TestWiring:
    def test_the_aang_modules_are_gone(self):
        assert not os.path.isfile(os.path.join(SRC_DIR, "ops", "aang_utils.py"))
        assert not os.path.isfile(os.path.join(SRC_DIR, "ops", "preview_aang.py"))

    def test_operators_are_imported_and_registered(self):
        init_src = _read(os.path.join(SRC_DIR, "__init__.py"))
        assert "OBJECT_OT_preview_in_builder," in init_src
        assert "OBJECT_OT_stop_live_preview," in init_src

    def test_preview_buttons_are_drawn(self):
        init_src = _read(os.path.join(SRC_DIR, "__init__.py"))
        assert '"Preview Wearable"' in init_src
        assert '"Preview Emote"' in init_src

    def test_bridge_is_stopped_on_unregister(self):
        init_src = _read(os.path.join(SRC_DIR, "__init__.py"))
        unregister_src = init_src.split("def unregister():", 1)[1]
        assert "stop_live_preview()" in unregister_src

    def test_server_binds_to_loopback_only(self):
        live_src = _read(os.path.join(SRC_DIR, "ops", "live_preview.py"))
        assert '("127.0.0.1", 0)' in live_src

    def test_bridge_serves_the_expected_endpoints(self):
        live_src = _read(os.path.join(SRC_DIR, "ops", "live_preview.py"))
        assert '"/state"' in live_src
        assert 'MODEL_FILE = "model.glb"' in live_src

    def test_exports_are_swapped_in_atomically(self):
        # The Builder may fetch /model.glb at any moment; a half-written file
        # must never be visible at the served path.
        live_src = _read(os.path.join(SRC_DIR, "ops", "live_preview.py"))
        assert "os.replace(" in live_src

    def test_handlers_survive_undo_but_not_file_loads(self):
        # persistent keeps handlers alive across undo pushes; the explicit
        # load_pre hook is what ends the session when another file opens.
        live_src = _read(os.path.join(SRC_DIR, "ops", "live_preview.py"))
        assert live_src.count("@persistent") == 3
        assert "load_pre" in live_src

    def test_refresh_is_debounced(self):
        live_src = _read(os.path.join(SRC_DIR, "ops", "live_preview.py"))
        assert "DEBOUNCE_SECONDS" in live_src

    def test_readme_documents_the_live_preview(self):
        readme_src = _read(os.path.join(ROOT_DIR, "README.md"))
        assert "### Live Preview in the Builder" in readme_src
