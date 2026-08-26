"""Live preview of the current wearable or emote in the Builder.

Previewing means three things: export the selection to a GLB, serve it from a
short-lived local bridge, and open the Builder's ``/live-preview`` page, which
polls the bridge and hot-swaps the model on a live avatar:

    GET /state      -> {"version", "type", "name", "category"}
    GET /model.glb  -> the latest export

Category, overrides, body shape and emote playback are all chosen on the
Builder page; the add-on only exports and serves. Refresh is always live:
saving the .blend re-exports immediately, scene edits re-export after a quiet
period, and each re-export bumps ``version`` so the page picks it up on its
next poll. The bridge binds to 127.0.0.1 on an OS-assigned port and is torn
down on Stop Live Preview or when the add-on is unregistered.
"""

import os
import shutil
import tempfile
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import bpy
from bpy.app.handlers import persistent

from .bridge_utils import (
    DEFAULT_BUILDER_URL,
    WEARABLE_CATEGORIES,
    build_state_payload,
    live_preview_url,
    normalize_builder_url,
    readable_category,
)
from .emote_utils import find_avatar_armature

MODEL_FILE = "model.glb"

# Re-export only once the scene has been quiet for this long, so dragging a
# vertex or scrubbing a slider does not export on every mouse move.
DEBOUNCE_SECONDS = 1.5
# The refresh itself dirties the depsgraph (the emote exporter toggles
# visibility and scrubs frames); ignore updates this close after one or the
# session would loop forever.
_POST_REFRESH_GRACE = 0.75
_TIMER_INTERVAL = 0.5


# ---------------------------------------------------------------------------
# Bridge server
# ---------------------------------------------------------------------------


class _BridgeRequestHandler(BaseHTTPRequestHandler):
    """Serves /state and /model.glb with CORS enabled so the Builder page may fetch them."""

    def _send(self, code, content_type, body):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):  # noqa: N802 — http.server naming
        self._send(204, "text/plain", b"")

    def do_GET(self):  # noqa: N802 — http.server naming
        path = self.path.split("?", 1)[0]
        state, model_path = _server.snapshot()
        if path == "/state" and state:
            self._send(200, "application/json", state.encode("utf-8"))
        elif path == f"/{MODEL_FILE}" and model_path and os.path.isfile(model_path):
            with open(model_path, "rb") as f:
                self._send(200, "model/gltf-binary", f.read())
        else:
            self._send(404, "text/plain", b"not found")

    def log_message(self, fmt, *args):
        # Silence per-request logging; Blender's console is not a web server log.
        pass


class _BridgeServer:
    """Threaded HTTP server over a temporary export directory."""

    def __init__(self):
        self._httpd = None
        self._thread = None
        self._lock = threading.Lock()
        self._state = ""
        self.directory = None

    @property
    def running(self):
        return self._httpd is not None

    @property
    def port(self):
        return self._httpd.server_address[1] if self._httpd else None

    def start(self):
        if self.running:
            return self.directory

        self.directory = tempfile.mkdtemp(prefix="dcl_live_preview_")
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), _BridgeRequestHandler)
        self._httpd.daemon_threads = True
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="dcl-live-preview", daemon=True)
        self._thread.start()
        return self.directory

    def publish(self, state_payload):
        with self._lock:
            self._state = state_payload

    def snapshot(self):
        """Read by the server thread; the state payload and model path move together."""
        with self._lock:
            model_path = os.path.join(self.directory, MODEL_FILE) if self.directory else None
            return self._state, model_path

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._thread:
            self._thread.join(timeout=5)
        if self.directory and os.path.isdir(self.directory):
            shutil.rmtree(self.directory, ignore_errors=True)

        self._httpd = None
        self._thread = None
        self._state = ""
        self.directory = None


_server = _BridgeServer()


# ---------------------------------------------------------------------------
# Live session: re-export on save or scene changes and bump the version
# ---------------------------------------------------------------------------


class _LiveSession:
    def __init__(self):
        self.export = None
        self.is_emote = False
        self.name = ""
        self.category = ""
        self.dirty_at = None
        self.exporting = False
        self.last_refresh = 0.0

    @property
    def active(self):
        return self.export is not None


_session = _LiveSession()
# Monotonic across session restarts, so a page that is already polling always
# sees a change when a new preview starts.
_version = 0


def _publish_state():
    _server.publish(
        build_state_payload(
            version=_version,
            is_emote=_session.is_emote,
            name=_session.name,
            category=_session.category,
        )
    )


def start_live_session(export_callback, *, is_emote, name, category=""):
    """Begin streaming to the Builder.

    ``export_callback`` re-exports the GLB in place and returns an error string,
    or None on success. It runs on the main thread, from a save handler or a
    timer.
    """
    global _version
    stop_live_session()
    _session.export = export_callback
    _session.is_emote = is_emote
    _session.name = name
    _session.category = category
    _version += 1
    _publish_state()
    _install_handlers()


def stop_live_session():
    _session.export = None
    _session.dirty_at = None
    _remove_handlers()


def stop_live_preview():
    """Tear the bridge down. Called from the add-on's unregister()."""
    stop_live_session()
    _server.stop()


def _refresh():
    global _version
    _session.exporting = True
    try:
        error = _session.export()
    except Exception as exc:
        error = str(exc)
    finally:
        _session.exporting = False
        _session.last_refresh = time.monotonic()

    if error:
        print(f"DCL live preview: refresh skipped — {error}")
        return
    _version += 1
    _publish_state()


def _is_relevant(update):
    """Ignore updates that cannot change the exported GLB, like selection."""
    data = update.id
    if isinstance(data, bpy.types.Object):
        return update.is_updated_geometry or update.is_updated_transform
    return isinstance(
        data,
        (
            bpy.types.Mesh,
            bpy.types.Curve,
            bpy.types.Armature,
            bpy.types.Material,
            bpy.types.Image,
            bpy.types.Action,
            bpy.types.NodeTree,
        ),
    )


@persistent
def _on_save_post(*_args):
    if _session.active:
        _session.dirty_at = None
        _refresh()


@persistent
def _on_load_pre(*_args):
    # The session belongs to the file it was started from.
    stop_live_session()


@persistent
def _on_depsgraph_update(scene, depsgraph):
    if not _session.active or _session.exporting:
        return
    if time.monotonic() - _session.last_refresh < _POST_REFRESH_GRACE:
        return
    screen = getattr(bpy.context, "screen", None)
    if screen and screen.is_animation_playing:
        return
    if any(_is_relevant(update) for update in depsgraph.updates):
        _session.dirty_at = time.monotonic()


def _timer():
    if not _session.active:
        return None
    if _session.dirty_at is not None and time.monotonic() - _session.dirty_at >= DEBOUNCE_SECONDS:
        _session.dirty_at = None
        _refresh()
    return _TIMER_INTERVAL


def _install_handlers():
    handlers = bpy.app.handlers
    if _on_save_post not in handlers.save_post:
        handlers.save_post.append(_on_save_post)
    if _on_depsgraph_update not in handlers.depsgraph_update_post:
        handlers.depsgraph_update_post.append(_on_depsgraph_update)
    if _on_load_pre not in handlers.load_pre:
        handlers.load_pre.append(_on_load_pre)
    if not bpy.app.timers.is_registered(_timer):
        bpy.app.timers.register(_timer, first_interval=_TIMER_INTERVAL)


def _remove_handlers():
    handlers = bpy.app.handlers
    for collection, fn in (
        (handlers.save_post, _on_save_post),
        (handlers.depsgraph_update_post, _on_depsgraph_update),
        (handlers.load_pre, _on_load_pre),
    ):
        if fn in collection:
            collection.remove(fn)
    if bpy.app.timers.is_registered(_timer):
        bpy.app.timers.unregister(_timer)


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------


def _addon_package():
    """Root add-on package name, from either an extension or a legacy install."""
    return __package__.rsplit(".", 1)[0] if "." in __package__ else __package__


def get_addon_preferences(context):
    addon = context.preferences.addons.get(_addon_package())
    return addon.preferences if addon else None


def _detect_content_type(context):
    """Emote if an avatar armature carries an action, wearable otherwise."""
    armature = find_avatar_armature(context)
    if armature and armature.animation_data and armature.animation_data.action:
        return "EMOTE"
    return "WEARABLE"


def _export_wearable_glb(out_path, selected_only):
    """Export the wearable to GLB, degrading gracefully on older exporters."""
    kwargs_sets = [
        {
            "filepath": out_path,
            "export_format": "GLB",
            "use_selection": selected_only,
            "export_apply": True,
            "export_animations": False,
            "export_cameras": False,
            "export_lights": False,
        },
        {
            "filepath": out_path,
            "export_format": "GLB",
            "use_selection": selected_only,
            "export_apply": True,
        },
        {
            "filepath": out_path,
            "export_format": "GLB",
        },
    ]

    last_error = None
    for kwargs in kwargs_sets:
        try:
            bpy.ops.export_scene.gltf(**kwargs)
            return None
        except Exception as exc:
            last_error = exc
    return last_error


def _make_exporter(directory, is_emote, selected_only):
    """A callback that re-exports into the served folder.

    Exports land in a scratch file first and are swapped in with os.replace, so
    the Builder never fetches a half-written model.
    """
    model_path = os.path.join(directory, MODEL_FILE)
    scratch_path = os.path.join(directory, f"next_{MODEL_FILE}")

    def _export():
        if is_emote:
            # Reuses the emote exporter so validation, frame range and prop
            # armatures behave exactly like a normal emote export.
            result = bpy.ops.object.export_emote_glb(filepath=scratch_path)
            if "FINISHED" not in result:
                return "emote export cancelled (check validation)"
        else:
            error = _export_wearable_glb(scratch_path, selected_only)
            if error:
                return str(error)
        if not os.path.isfile(scratch_path):
            return "export produced no file"
        os.replace(scratch_path, model_path)
        return None

    return _export


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------


class OBJECT_OT_preview_in_builder(bpy.types.Operator):
    bl_idname = "object.preview_in_builder"
    bl_label = "Live Preview in Builder"
    bl_description = (
        "Export the current wearable or emote and stream it to the Builder's Live Preview page, "
        "re-exporting whenever the scene changes or the file is saved"
    )
    bl_options = {"REGISTER"}

    builder_url: bpy.props.StringProperty(
        name="Builder URL",
        description=(
            "Builder deployment whose Live Preview page to open. A locally served Builder "
            "(http://localhost:3000) works too. Saved to the add-on preferences"
        ),
        default=DEFAULT_BUILDER_URL,
    )

    content_type: bpy.props.EnumProperty(
        name="Preview",
        description="What to stream to the Builder",
        items=[
            ("AUTO", "Auto", "Emote if the avatar armature has an action, wearable otherwise"),
            ("WEARABLE", "Wearable", "Export the model and equip it on the avatar"),
            ("EMOTE", "Emote", "Export the animation and play it on the avatar"),
        ],
        default="AUTO",
    )

    category: bpy.props.EnumProperty(
        name="Category",
        description="Wearable category the Builder page starts with (changeable there)",
        items=[(cat, readable_category(cat), f"Preview as a {cat} wearable") for cat in WEARABLE_CATEGORIES],
        default="upper_body",
    )

    selected_only: bpy.props.BoolProperty(
        name="Selected Only",
        description="Export only the selected objects. Remember to include the armature for skinned wearables",
        default=False,
    )

    def invoke(self, context, event):
        prefs = get_addon_preferences(context)
        saved = getattr(prefs, "builder_url", "") if prefs else ""
        self.builder_url = saved or DEFAULT_BUILDER_URL
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):
        layout = self.layout

        layout.prop(self, "builder_url")
        layout.separator()

        layout.prop(self, "content_type")
        resolved = self.content_type if self.content_type != "AUTO" else _detect_content_type(context)

        if resolved == "WEARABLE":
            layout.prop(self, "category")
            layout.prop(self, "selected_only")
        else:
            layout.label(text="Uses the Emote Settings frame range.", icon="INFO")
        layout.label(text="Overrides, body shape and playback live on the Builder page.", icon="INFO")

    def execute(self, context):
        builder_url = normalize_builder_url(self.builder_url)
        if not builder_url:
            self.report({"ERROR"}, "Set the Builder URL first (Preferences > Add-ons > Decentraland Tools).")
            return {"CANCELLED"}

        prefs = get_addon_preferences(context)
        if prefs and prefs.builder_url != builder_url:
            prefs.builder_url = builder_url

        content_type = self.content_type if self.content_type != "AUTO" else _detect_content_type(context)
        is_emote = content_type == "EMOTE"

        try:
            directory = _server.start()
        except OSError as exc:
            self.report({"ERROR"}, f"Could not start the local bridge: {exc}")
            return {"CANCELLED"}

        export = _make_exporter(directory, is_emote, self.selected_only)
        error = export()
        if error:
            self.report({"ERROR"}, f"Export failed: {error}")
            return {"CANCELLED"}

        start_live_session(
            export,
            is_emote=is_emote,
            name=bpy.path.display_name_from_filepath(bpy.data.filepath) or "Blender Preview",
            category=self.category,
        )

        try:
            webbrowser.open(live_preview_url(builder_url))
        except Exception as exc:
            self.report({"ERROR"}, f"Could not open the browser: {exc}")
            return {"CANCELLED"}

        bridge_url = f"http://127.0.0.1:{_server.port}"
        # The Builder page can't discover the OS-assigned port, so hand the
        # address over via the clipboard for its Bridge URL field.
        context.window_manager.clipboard = bridge_url
        self.report(
            {"INFO"},
            f"Bridge on {bridge_url} (copied to clipboard) — paste it into the Builder page's Bridge URL field.",
        )
        return {"FINISHED"}


class OBJECT_OT_stop_live_preview(bpy.types.Operator):
    bl_idname = "object.stop_live_preview"
    bl_label = "Stop Live Preview"
    bl_description = "Stop the local bridge that streams exports to the Builder and delete the exported files"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return _server.running

    def execute(self, context):
        stop_live_preview()
        self.report({"INFO"}, "Live preview stopped.")
        return {"FINISHED"}
