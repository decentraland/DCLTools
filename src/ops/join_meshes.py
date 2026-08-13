"""
Join meshes that already share a material, to cut draw calls.

Merging materials removes *material* draw calls, but every object still ships
as its own glTF node/primitive - a scene of 475 tiny props is 475 draw calls
even when they all use one material. This tool joins objects that can safely
become a single mesh.

What "safely" means is most of the work. Joining is destructive and Blender's
join operator has two sharp edges that silently damage a scene:

  * modifiers on the non-active objects are DROPPED, not applied, so a mirrored
    or array-ed object loses the geometry it was generating;
  * objects sharing mesh data (linked duplicates) get their geometry copied per
    instance, which inflates the file and kills GPU instancing.

So the tool excludes anything risky by default and reports exactly what it
skipped and why, rather than quietly producing a broken scene.

Grouping is deliberately conservative: objects only join when they agree on
material set, UV layer set, parent, collection and spatial cell. UV layers
matter because Blender merges them by name - joining a 'UVMap' object with a
'UVChannel_1' object yields two half-empty layers and broken texturing.
"""

import math

import bpy

from .collider_utils import is_collider

# 16-bit index buffers top out here; past it exporters switch to 32-bit indices,
# which costs memory and upsets some engines.
VERTEX_BUDGET = 65535

# One Decentraland parcel. Joining a whole scene into one mesh collapses the
# bounding box so frustum culling stops working; cells keep culling granularity.
DEFAULT_CELL_SIZE = 16.0


def _instance_source_collections():
    """Collections used as collection-instances, plus everything nested inside.

    Their contents *define* the instance, so joining inside one rewrites every
    placement of it at once.
    """
    stack = [obj.instance_collection for obj in bpy.data.objects if obj.instance_collection is not None]
    seen = set()
    while stack:
        coll = stack.pop()
        if coll is None or coll.name in seen:
            continue
        seen.add(coll.name)
        stack.extend(coll.children)
    return seen


def _signature(obj):
    """Material + UV identity that two objects must share to be joinable."""
    materials = tuple(slot.material.name if slot.material else "" for slot in obj.material_slots)
    uvs = tuple(layer.name for layer in obj.data.uv_layers)
    return materials, uvs


def _skip_reason(obj, opts, instance_sources):
    """Why *obj* must not be joined, or None when it is safe to join."""
    if obj.type != "MESH" or obj.data is None:
        return "not a mesh"
    if len(obj.data.vertices) == 0:
        return "empty mesh"
    if is_collider(obj) and not opts["join_colliders"]:
        return "collider"
    if opts["preserve_instances"] and obj.data.users > 1:
        return "shared mesh data (instanced)"
    if any(coll.name in instance_sources for coll in obj.users_collection):
        return "inside a collection instance"
    if obj.data.shape_keys is not None:
        return "has shape keys"
    if obj.animation_data is not None and obj.animation_data.action is not None:
        return "animated"
    if any(mod.type == "ARMATURE" for mod in obj.modifiers) or (obj.parent and obj.parent.type == "ARMATURE"):
        return "bound to armature"
    if obj.modifiers and not opts["apply_modifiers"]:
        # Joining would discard these outright - see module docstring.
        return "has modifiers"
    matrix = obj.matrix_world
    if matrix.determinant() < 0:
        # Join bakes the transform but not the winding order, so the result
        # would render inside-out.
        return "negative scale"
    return None


def _group_key(obj, opts):
    materials, uvs = _signature(obj)
    parent = obj.parent.name if obj.parent else ""
    collection = ""
    if opts["respect_collections"] and obj.users_collection:
        collection = obj.users_collection[0].name
    cell = ()
    if opts["cell_size"] > 0.0:
        t = obj.matrix_world.translation
        cell = (
            math.floor(t.x / opts["cell_size"]),
            math.floor(t.y / opts["cell_size"]),
        )
    return (is_collider(obj), parent, collection, materials, uvs) + cell


def plan_joins(objects, opts):
    """Return (batches, skipped) without touching the scene.

    ``batches`` is a list of object lists, each at least two objects that can be
    joined into one mesh. ``skipped`` maps a reason to how many objects hit it.
    """
    instance_sources = _instance_source_collections()

    groups = {}
    skipped = {}
    for obj in objects:
        reason = _skip_reason(obj, opts, instance_sources)
        if reason is not None:
            skipped[reason] = skipped.get(reason, 0) + 1
            continue
        groups.setdefault(_group_key(obj, opts), []).append(obj)

    batches = []
    for members in groups.values():
        if len(members) < 2:
            continue
        # Split so no single result blows the 16-bit index budget.
        current, total = [], 0
        for obj in members:
            count = len(obj.data.vertices)
            if current and total + count > VERTEX_BUDGET:
                if len(current) > 1:
                    batches.append(current)
                current, total = [obj], count
            else:
                current.append(obj)
                total += count
        if len(current) > 1:
            batches.append(current)
    return batches, skipped


class _Visibility:
    """Temporarily reveal everything: hidden objects cannot be selected/joined."""

    def __init__(self, context):
        self.context = context
        self.collections = []
        self.layers = []
        self.objects = []

    def __enter__(self):
        for coll in bpy.data.collections:
            self.collections.append((coll, coll.hide_viewport))
            coll.hide_viewport = False

        def walk(layer):
            self.layers.append((layer, layer.exclude, layer.hide_viewport))
            layer.exclude = False
            layer.hide_viewport = False
            for child in layer.children:
                walk(child)

        walk(self.context.view_layer.layer_collection)

        for obj in bpy.data.objects:
            self.objects.append((obj, obj.hide_viewport))
            obj.hide_viewport = False
            try:
                obj.hide_set(False)
            except RuntimeError:
                pass
        return self

    def __exit__(self, *exc):
        # Objects consumed by a join are gone, so every restore is guarded.
        for obj, hidden in self.objects:
            try:
                obj.hide_viewport = hidden
            except ReferenceError:
                pass
        for layer, exclude, hidden in self.layers:
            try:
                layer.exclude = exclude
                layer.hide_viewport = hidden
            except ReferenceError:
                pass
        for coll, hidden in self.collections:
            try:
                coll.hide_viewport = hidden
            except ReferenceError:
                pass
        return False


class OBJECT_OT_join_meshes(bpy.types.Operator):
    bl_idname = "object.join_meshes"
    bl_label = "Join Meshes"
    bl_description = (
        "Join meshes that share a material into single objects to cut draw calls. "
        "Instances, animated, modifier-driven and collider geometry are protected"
    )
    bl_options = {"REGISTER", "UNDO"}

    scope_selected: bpy.props.BoolProperty(
        name="Only Selected",
        description="Join only the selected objects (otherwise every mesh in the scene)",
        default=False,
    )

    cell_size: bpy.props.FloatProperty(
        name="Cell Size (m)",
        description=(
            "Only join objects within the same square cell, so the scene keeps "
            "enough separate meshes for frustum culling. 16m is one parcel. "
            "Set 0 to ignore position and join as much as possible"
        ),
        default=DEFAULT_CELL_SIZE,
        min=0.0,
        max=256.0,
    )

    respect_collections: bpy.props.BoolProperty(
        name="Keep Collections Apart",
        description="Never join objects that live in different collections",
        default=True,
    )

    join_colliders: bpy.props.BoolProperty(
        name="Join Colliders",
        description=("Also join collider meshes with each other. Colliders are always kept apart from visual geometry"),
        default=True,
    )

    preserve_instances: bpy.props.BoolProperty(
        name="Preserve Instances",
        description=(
            "Skip objects that share mesh data. Joining them copies the geometry "
            "once per instance and defeats GPU instancing"
        ),
        default=True,
    )

    apply_modifiers: bpy.props.BoolProperty(
        name="Apply Modifiers",
        description=(
            "Apply modifiers before joining. Without this, objects carrying "
            "modifiers are skipped - joining would discard their modifiers and "
            "silently lose the geometry those were generating"
        ),
        default=False,
    )

    def _options(self):
        return {
            "cell_size": self.cell_size,
            "respect_collections": self.respect_collections,
            "join_colliders": self.join_colliders,
            "preserve_instances": self.preserve_instances,
            "apply_modifiers": self.apply_modifiers,
        }

    def _candidates(self, context):
        source = context.selected_objects if self.scope_selected else bpy.data.objects
        return [obj for obj in source if obj.type == "MESH" and obj.data is not None]

    def execute(self, context):
        if context.mode != "OBJECT":
            try:
                bpy.ops.object.mode_set(mode="OBJECT")
            except Exception:
                pass

        candidates = self._candidates(context)
        if not candidates:
            self.report({"ERROR"}, "No mesh objects to process")
            return {"CANCELLED"}

        batches, skipped = plan_joins(candidates, self._options())
        if not batches:
            self.report({"WARNING"}, "Nothing to join - no two objects share material, UVs, collection and cell")
            return {"CANCELLED"}

        joined_from = 0
        results = 0
        failures = 0

        with _Visibility(context):
            view_objects = context.view_layer.objects
            for batch in batches:
                members = [obj for obj in batch if obj.name in view_objects]
                if len(members) < 2:
                    continue

                if self.apply_modifiers:
                    for obj in members:
                        if not obj.modifiers:
                            continue
                        bpy.ops.object.select_all(action="DESELECT")
                        obj.select_set(True)
                        view_objects.active = obj
                        try:
                            bpy.ops.object.convert(target="MESH")
                        except RuntimeError:
                            pass

                bpy.ops.object.select_all(action="DESELECT")
                for obj in members:
                    obj.select_set(True)
                view_objects.active = members[0]
                try:
                    bpy.ops.object.join()
                    joined_from += len(members)
                    results += 1
                except RuntimeError:
                    failures += 1

            bpy.ops.object.select_all(action="DESELECT")

        saved = joined_from - results
        msg = f"Joined {joined_from} objects into {results} mesh(es), {saved} fewer draw calls."
        if skipped:
            top = sorted(skipped.items(), key=lambda kv: -kv[1])[:3]
            detail = ", ".join(f"{count} {reason}" for reason, count in top)
            msg += f" Skipped {sum(skipped.values())}: {detail}."
        if failures:
            msg += f" {failures} group(s) failed to join."
        self.report({"INFO"}, msg)
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "cell_size")
        layout.prop(self, "respect_collections")
        layout.prop(self, "join_colliders")
        layout.prop(self, "preserve_instances")
        layout.prop(self, "apply_modifiers")
        layout.prop(self, "scope_selected")

        candidates = self._candidates(context)
        batches, skipped = plan_joins(candidates, self._options())
        joined_from = sum(len(b) for b in batches)
        remaining = len(candidates) - joined_from + len(batches)

        layout.separator()
        box = layout.box()
        box.label(text="Preview", icon="INFO")
        col = box.column(align=True)
        col.label(text=f"{len(candidates)} mesh objects  ->  {remaining} after joining")
        col.label(text=f"{joined_from} objects merge into {len(batches)} mesh(es)")

        if skipped:
            box = layout.box()
            box.label(text=f"Protected from joining: {sum(skipped.values())}", icon="CHECKMARK")
            col = box.column(align=True)
            for reason, count in sorted(skipped.items(), key=lambda kv: -kv[1])[:6]:
                col.label(text=f"    {count} x {reason}")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=460)
