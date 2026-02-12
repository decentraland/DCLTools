import bpy
import os

class OBJECT_OT_custom_logo(bpy.types.Operator):
    bl_idname = "object.custom_logo"
    bl_label = "Decentraland Tools"
    bl_description = "Decentraland Tools - Custom Logo"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # This operator just shows the logo, no actual functionality
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        # Try to use a custom icon
        row = layout.row(align=True)
        row.label(text="", icon='MESH_GRID')  # Use grid icon as closest to landscape
        row.label(text="Decentraland Tools")
