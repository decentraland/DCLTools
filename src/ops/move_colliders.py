import bpy

from .collider_utils import is_collider


def _in_scene_hierarchy(scene, collection):
    """True when *collection* is reachable from the scene's root collection."""

    def walk(parent):
        for child in parent.children:
            if child is collection or walk(child):
                return True
        return False

    return collection is scene.collection or walk(scene.collection)


class OBJECT_OT_move_colliders_to_collection(bpy.types.Operator):
    bl_idname = "object.move_colliders_to_collection"
    bl_label = "Move to Collection"
    bl_description = (
        "Move every collider mesh into its own collection and optionally hide it, "
        "so collision geometry stops blocking the view. Hidden colliders are still exported"
    )
    bl_options = {"REGISTER", "UNDO"}

    collection_name: bpy.props.StringProperty(
        name="Collection",
        description="Collection that will hold the colliders (created if it does not exist)",
        default="Colliders",
    )

    hide_collection: bpy.props.BoolProperty(
        name="Hide in Viewport",
        description=(
            "Hide the collection so colliders stop obstructing the visual mesh. "
            "This does not affect export: the toolkit's glTF export includes hidden objects"
        ),
        default=True,
    )

    scope_selected: bpy.props.BoolProperty(
        name="Only Selected",
        description="Move only the selected collider meshes",
        default=False,
    )

    def execute(self, context):
        if context.mode != "OBJECT":
            try:
                bpy.ops.object.mode_set(mode="OBJECT")
            except Exception:
                pass

        source = context.selected_objects if self.scope_selected else bpy.data.objects
        colliders = [o for o in source if o.type == "MESH" and is_collider(o)]

        if not colliders:
            self.report({"WARNING"}, "No collider meshes found (expected '_collider' in the name)")
            return {"CANCELLED"}

        target = bpy.data.collections.get(self.collection_name)
        if target is None:
            target = bpy.data.collections.new(self.collection_name)
        if not _in_scene_hierarchy(context.scene, target):
            context.scene.collection.children.link(target)

        moved = 0
        already = 0
        for obj in colliders:
            if len(obj.users_collection) == 1 and obj.users_collection[0] is target:
                already += 1
                continue

            # Link to the target first so the object is never left in zero
            # collections, which would drop it out of the scene entirely.
            if obj.name not in target.objects:
                target.objects.link(obj)
            for coll in list(obj.users_collection):
                if coll is not target:
                    coll.objects.unlink(obj)
            moved += 1

        # Hiding is applied after the move so newly added objects are covered.
        target.hide_viewport = self.hide_collection

        parts = [f"Moved {moved} collider(s) to '{target.name}'"]
        if already:
            parts.append(f"{already} already there")
        if self.hide_collection:
            parts.append("collection hidden (still exported)")
        self.report({"INFO"}, ". ".join(parts) + ".")
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "collection_name")
        layout.prop(self, "hide_collection")
        layout.prop(self, "scope_selected")
        box = layout.box()
        box.scale_y = 0.8
        box.label(text="Matches meshes with '_collider' in the name.", icon="INFO")
        box.label(text="Hiding is viewport-only - export still includes them.")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=380)
