import bpy


class OBJECT_OT_clean_unused_materials(bpy.types.Operator):
    bl_idname = "object.clean_unused_materials"
    bl_label = "Clean Unused Materials"
    bl_description = "Remove materials that are not assigned to any object in the scene"
    bl_options = {'REGISTER', 'UNDO'}

    include_fake_user: bpy.props.BoolProperty(
        name="Include Fake User Materials",
        description="Also remove materials that only have a fake user (no real usage)",
        default=False,
    )

    def get_unused_materials(self):
        """Find materials with zero real users."""
        unused = []
        for mat in bpy.data.materials:
            # Check if material is actually used by any object
            real_users = mat.users
            if mat.use_fake_user:
                real_users -= 1
            if real_users <= 0:
                unused.append(mat)
        return unused

    def execute(self, context):
        unused_materials = self.get_unused_materials()

        if not self.include_fake_user:
            # Only remove materials with zero users (no fake user either)
            to_remove = [mat for mat in unused_materials if not mat.use_fake_user]
        else:
            to_remove = unused_materials

        if not to_remove:
            self.report({'INFO'}, "No unused materials found")
            return {'FINISHED'}

        removed_count = 0
        removed_names = []
        for mat in to_remove:
            removed_names.append(mat.name)
            bpy.data.materials.remove(mat)
            removed_count += 1

        self.report({'INFO'}, f"Removed {removed_count} unused material(s): {', '.join(removed_names)}")
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout

        unused = self.get_unused_materials()
        fake_only = [mat for mat in unused if mat.use_fake_user]
        no_users = [mat for mat in unused if not mat.use_fake_user]

        layout.label(text=f"Found {len(unused)} unused material(s):", icon='INFO')

        if no_users:
            box = layout.box()
            box.label(text=f"{len(no_users)} with zero users (will be removed):", icon='ERROR')
            for mat in no_users[:20]:
                box.label(text=f"  {mat.name}")
            if len(no_users) > 20:
                box.label(text=f"  ... and {len(no_users) - 20} more")

        if fake_only:
            box = layout.box()
            box.label(text=f"{len(fake_only)} with fake user only:", icon='WARNING')
            for mat in fake_only[:10]:
                box.label(text=f"  {mat.name}")
            if len(fake_only) > 10:
                box.label(text=f"  ... and {len(fake_only) - 10} more")

        layout.separator()
        layout.prop(self, "include_fake_user")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)
