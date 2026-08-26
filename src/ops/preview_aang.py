"""Preview the current wearable or emote in the Decentraland Aang renderer.

The renderer runs in the browser and fetches its models over HTTP, so a preview
means three things: export the selection to a GLB, serve that GLB from a
short-lived local HTTP server, and open the renderer with a base64 entity
definition pointing back at it.

The server binds to 127.0.0.1 on an OS-assigned port and only ever serves the
temporary export folder. It stays up so repeated previews reuse the same tab
origin, and is torn down when the add-on is unregistered.
"""

import functools
import os
import shutil
import tempfile
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import bpy

from .aang_utils import (
    BASE_BODY_OVERRIDES,
    BODY_SHAPE_FEMALE,
    BODY_SHAPE_MALE,
    BUILTIN_EMOTES,
    DEFAULT_RENDERER_URL,
    WEARABLE_CATEGORIES,
    build_entity_definition,
    build_preview_url,
    normalize_renderer_url,
    readable_category,
    sort_categories,
)
from .emote_utils import find_avatar_armature

# ---------------------------------------------------------------------------
# Local file server
# ---------------------------------------------------------------------------


class _PreviewRequestHandler(SimpleHTTPRequestHandler):
    """Static handler with CORS enabled so the hosted renderer may fetch the GLB."""

    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".glb": "model/gltf-binary",
        ".gltf": "model/gltf+json",
    }

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_OPTIONS(self):  # noqa: N802 — http.server naming
        self.send_response(204)
        self.end_headers()

    def log_message(self, fmt, *args):
        # Silence per-request logging; Blender's console is not a web server log.
        pass


class _PreviewServer:
    """Threaded HTTP server over a temporary directory."""

    def __init__(self):
        self._httpd = None
        self._thread = None
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

        self.directory = tempfile.mkdtemp(prefix="dcl_aang_preview_")
        handler = functools.partial(_PreviewRequestHandler, directory=self.directory)
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._httpd.daemon_threads = True
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="dcl-aang-preview", daemon=True)
        self._thread.start()
        return self.directory

    def url_for(self, filename):
        return f"http://127.0.0.1:{self.port}/{filename}"

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
        self.directory = None


_server = _PreviewServer()


def stop_preview_server():
    """Shut the preview server down. Called from the add-on's unregister()."""
    _server.stop()


# ---------------------------------------------------------------------------
# Helpers
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


def _next_export_name(directory, prefix, extension=".glb"):
    """Unique filename so a reload never hits a cached model."""
    index = 1
    while True:
        candidate = f"{prefix}_{index}{extension}"
        if not os.path.exists(os.path.join(directory, candidate)):
            return candidate
        index += 1


def _flag_items(names, description):
    """Build ENUM_FLAG items with explicit bit values, so several can be picked at once."""
    return [
        (name, readable_category(name), description.format(name=readable_category(name)), "NONE", 1 << index)
        for index, name in enumerate(names)
    ]


def _selection_label(values, order=WEARABLE_CATEGORIES):
    """Summarise a multi-select for its dropdown button, like the Builder does."""
    chosen = sort_categories(values, order)
    if not chosen:
        return "Select an option"
    return ", ".join(readable_category(name) for name in chosen)


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


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------


class OBJECT_OT_preview_in_aang(bpy.types.Operator):
    bl_idname = "object.preview_in_aang"
    bl_label = "Preview in Renderer"
    bl_description = "Export the current wearable or emote and preview it on an avatar in the Aang renderer"
    bl_options = {"REGISTER"}

    renderer_url: bpy.props.StringProperty(
        name="Renderer URL",
        description=(
            "Aang renderer deployment to open, e.g. a Vercel preview URL from an aang-renderer PR. "
            "A bare host works too. Saved to the add-on preferences"
        ),
        default=DEFAULT_RENDERER_URL,
    )

    content_type: bpy.props.EnumProperty(
        name="Preview",
        description="What to send to the renderer",
        items=[
            ("AUTO", "Auto", "Emote if the avatar armature has an action, wearable otherwise"),
            ("WEARABLE", "Wearable", "Export the model and equip it on the avatar"),
            ("EMOTE", "Emote", "Export the animation and play it on the avatar"),
        ],
        default="AUTO",
    )

    category: bpy.props.EnumProperty(
        name="Category",
        description="Wearable category (which avatar slot the model occupies)",
        items=[(cat, cat.replace("_", " ").title(), f"Preview as a {cat} wearable") for cat in WEARABLE_CATEGORIES],
        default="upper_body",
    )

    hides: bpy.props.EnumProperty(
        name="Hides",
        description="Categories this wearable hides on the avatar",
        items=_flag_items(WEARABLE_CATEGORIES, "Hide {name}"),
        options={"ENUM_FLAG"},
        default=set(),
    )

    replaces: bpy.props.EnumProperty(
        name="Replaces",
        description="Categories this wearable replaces. The renderer folds these into the hiding list",
        items=_flag_items(WEARABLE_CATEGORIES, "Replace {name}"),
        options={"ENUM_FLAG"},
        default=set(),
    )

    base_body: bpy.props.EnumProperty(
        name="Base body",
        description=(
            "Default hiding to switch back on. Picking Hands keeps the avatar's hands visible under an "
            "upper body, which would otherwise hide them"
        ),
        items=_flag_items(BASE_BODY_OVERRIDES, "Keep {name} visible"),
        options={"ENUM_FLAG"},
        default=set(),
    )

    body_shape: bpy.props.EnumProperty(
        name="Body Shape",
        description="Which avatar to render the preview on",
        items=[
            ("MALE", "Male", "Render on BaseMale"),
            ("FEMALE", "Female", "Render on BaseFemale"),
        ],
        default="MALE",
    )

    base_emote: bpy.props.EnumProperty(
        name="Idle Emote",
        description="Animation the avatar plays while showing a wearable",
        items=[(name, name.replace("-", " ").title(), f"Play the {name} emote") for name in BUILTIN_EMOTES],
        default="idle",
    )

    emote_loop: bpy.props.BoolProperty(
        name="Loop",
        description="Loop the exported emote in the renderer",
        default=False,
    )

    selected_only: bpy.props.BoolProperty(
        name="Selected Only",
        description="Export only the selected objects. Remember to include the armature for skinned wearables",
        default=False,
    )

    def invoke(self, context, event):
        prefs = get_addon_preferences(context)
        saved = getattr(prefs, "aang_renderer_url", "") if prefs else ""
        self.renderer_url = saved or DEFAULT_RENDERER_URL
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):
        layout = self.layout

        layout.prop(self, "renderer_url")
        if not self.renderer_url.strip():
            layout.label(text="Paste an Aang renderer URL (a Vercel preview link works).", icon="ERROR")
        layout.separator()

        layout.prop(self, "content_type")
        resolved = self.content_type if self.content_type != "AUTO" else _detect_content_type(context)

        if resolved == "WEARABLE":
            layout.label(text="Basics")
            basics = layout.box()
            basics.prop(self, "category")
            basics.prop(self, "base_emote")
            basics.prop(self, "selected_only")

            layout.label(text="Overrides")
            overrides = layout.box()
            self._draw_override(overrides, "base_body", "Base body", BASE_BODY_OVERRIDES)
            self._draw_override(overrides, "hides", "Hides")
            self._draw_override(overrides, "replaces", "Replaces")
        else:
            layout.prop(self, "emote_loop")
            layout.label(text="Uses the Emote Settings frame range.", icon="INFO")

        layout.prop(self, "body_shape")

    def _draw_override(self, layout, prop_name, label, order=WEARABLE_CATEGORIES):
        """One Builder-style row: a label and a dropdown that toggles several categories."""
        split = layout.split(factor=0.35)
        split.label(text=label)
        split.prop_menu_enum(self, prop_name, text=_selection_label(getattr(self, prop_name), order))

    def execute(self, context):
        renderer_url = normalize_renderer_url(self.renderer_url)
        if not renderer_url:
            self.report({"ERROR"}, "Set the Aang renderer URL first (Preferences > Add-ons > Decentraland Tools).")
            return {"CANCELLED"}

        prefs = get_addon_preferences(context)
        if prefs and prefs.aang_renderer_url != renderer_url:
            prefs.aang_renderer_url = renderer_url

        content_type = self.content_type if self.content_type != "AUTO" else _detect_content_type(context)
        is_emote = content_type == "EMOTE"

        try:
            directory = _server.start()
        except OSError as exc:
            self.report({"ERROR"}, f"Could not start the local preview server: {exc}")
            return {"CANCELLED"}

        filename = _next_export_name(directory, "emote" if is_emote else "wearable")
        out_path = os.path.join(directory, filename)

        if is_emote:
            # Reuses the emote exporter so validation, frame range and prop
            # armatures behave exactly like a normal emote export.
            result = bpy.ops.object.export_emote_glb(filepath=out_path)
            if "FINISHED" not in result:
                return {"CANCELLED"}
        else:
            error = _export_wearable_glb(out_path, self.selected_only)
            if error:
                self.report({"ERROR"}, f"Export failed: {error}")
                return {"CANCELLED"}

        if not os.path.isfile(out_path):
            self.report({"ERROR"}, "Export produced no file.")
            return {"CANCELLED"}

        entity = build_entity_definition(
            filename,
            _server.url_for(filename),
            name=bpy.path.display_name_from_filepath(bpy.data.filepath) or "Blender Preview",
            category=self.category,
            is_emote=is_emote,
            loop=self.emote_loop,
            hides=self.hides,
            replaces=self.replaces,
            removes_default_hiding=self.base_body,
        )

        url = build_preview_url(
            renderer_url,
            [entity],
            body_shape=BODY_SHAPE_FEMALE if self.body_shape == "FEMALE" else BODY_SHAPE_MALE,
            emote="" if is_emote else self.base_emote,
        )

        try:
            webbrowser.open(url)
        except Exception as exc:
            self.report({"ERROR"}, f"Could not open the browser: {exc}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Serving {filename} on port {_server.port} — opening the renderer.")
        return {"FINISHED"}


class OBJECT_OT_stop_aang_preview(bpy.types.Operator):
    bl_idname = "object.stop_aang_preview"
    bl_label = "Stop Preview Server"
    bl_description = "Stop the local server that hosts preview models and delete the exported files"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return _server.running

    def execute(self, context):
        stop_preview_server()
        self.report({"INFO"}, "Preview server stopped.")
        return {"FINISHED"}
