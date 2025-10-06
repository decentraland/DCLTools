import bpy

class OBJECT_OT_simplify_colliders(bpy.types.Operator):
    bl_idname = "object.simplify_colliders"
    bl_label = "Simplify Colliders"
    bl_description = "Apply decimation modifier to reduce polygon count on collider objects"
    bl_options = {'REGISTER', 'UNDO'}

    ratio: bpy.props.FloatProperty(
        name="Decimation Ratio",
        description="Ratio of faces to keep (0.1 = 10% of original faces)",
        default=0.5,
        min=0.01,
        max=1.0,
    )

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

        for obj in objects:
            if obj.type != 'MESH' or not obj.name.endswith("_collider"):
                continue

            # Add decimation modifier
            decimate_mod = obj.modifiers.new(name="Decimate", type='DECIMATE')
            decimate_mod.ratio = self.ratio
            decimate_mod.use_collapse_triangulate = True
            
            # Apply the modifier
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_apply(modifier=decimate_mod.name)
            
            affected += 1

        self.report({'INFO'}, f"Simplified {affected} collider objects with ratio {self.ratio}")
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "ratio")
        layout.prop(self, "scope_selected")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
