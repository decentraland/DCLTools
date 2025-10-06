import bpy

class OBJECT_OT_strip_materials_from_colliders(bpy.types.Operator):
    bl_idname = "object.strip_materials_from_colliders"
    bl_label = "Strip Materials from Colliders"
    bl_description = "Remove all material slots from objects with '_collider' suffix"
    bl_options = {'REGISTER', 'UNDO'}

    scope_selected: bpy.props.BoolProperty(
        name="Only Selected",
        description="Affect only selected objects",
        default=False,
    )

    def execute(self, context):
        if bpy.context.mode != 'OBJECT':
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except Exception:
                pass

        objects = context.selected_objects if self.scope_selected else bpy.data.objects
        affected = 0
        slots_removed = 0

        for obj in objects:
            if obj.type != 'MESH' or not obj.name.endswith("_collider"):
                continue

            # Clear material slots
            count = len(obj.material_slots)
            if count > 0:
                for i in range(count - 1, -1, -1):
                    obj.active_material_index = i
                    bpy.ops.object.material_slot_remove()
                affected += 1
                slots_removed += count

        self.report({'INFO'}, f"Removed {slots_removed} material slots from {affected} *_collider meshes")
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "scope_selected")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
