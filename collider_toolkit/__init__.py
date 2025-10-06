bl_info = {
    "name": "Collider Toolkit",
    "author": "Your Name",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),
    "location": "3D Viewport > Sidebar (N) > Collider Toolkit",
    "description": "Collection of tools for collider mesh optimization and management",
    "category": "Object",
}

import bpy
from bpy.utils import register_class, unregister_class

from .ops.remove_uvs import OBJECT_OT_remove_uvs_from_colliders
from .ops.strip_materials import OBJECT_OT_strip_materials_from_colliders
from .ops.rename_add_suffix import OBJECT_OT_rename_add_collider_suffix
from .ops.simplify_colliders import OBJECT_OT_simplify_colliders
from .ops.cleanup_colliders import OBJECT_OT_cleanup_colliders

class VIEW3D_PT_collider_toolkit(bpy.types.Panel):
    bl_label = "Collider Toolkit"
    bl_idname = "VIEW3D_PT_collider_toolkit"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Collider Toolkit"

    def draw(self, context):
        layout = self.layout
        
        # UV Cleanup Section
        box = layout.box()
        row = box.row()
        row.prop(context.scene, "collider_toolkit_uv_expanded", text="UV Cleanup", icon='TRIA_DOWN' if context.scene.collider_toolkit_uv_expanded else 'TRIA_RIGHT', emboss=False)
        
        if context.scene.collider_toolkit_uv_expanded:
            col = box.column(align=True)
            col.operator(OBJECT_OT_remove_uvs_from_colliders.bl_idname, text="Remove UVs from Colliders", icon='UV')
            col.operator(OBJECT_OT_strip_materials_from_colliders.bl_idname, text="Strip Materials from Colliders", icon='MATERIAL')
        
        # Collider Management Section
        box = layout.box()
        row = box.row()
        row.prop(context.scene, "collider_toolkit_manage_expanded", text="Collider Management", icon='TRIA_DOWN' if context.scene.collider_toolkit_manage_expanded else 'TRIA_RIGHT', emboss=False)
        
        if context.scene.collider_toolkit_manage_expanded:
            col = box.column(align=True)
            col.operator(OBJECT_OT_rename_add_collider_suffix.bl_idname, text="Add _collider Suffix", icon='OUTLINER_OB_MESH')
            col.operator(OBJECT_OT_simplify_colliders.bl_idname, text="Simplify Colliders", icon='MOD_DECIM')
            col.operator(OBJECT_OT_cleanup_colliders.bl_idname, text="Cleanup Colliders", icon='BRUSH_DATA')

classes = (
    OBJECT_OT_remove_uvs_from_colliders,
    OBJECT_OT_strip_materials_from_colliders,
    OBJECT_OT_rename_add_collider_suffix,
    OBJECT_OT_simplify_colliders,
    OBJECT_OT_cleanup_colliders,
    VIEW3D_PT_collider_toolkit,
)

def register():
    # Register properties
    bpy.types.Scene.collider_toolkit_uv_expanded = bpy.props.BoolProperty(default=True)
    bpy.types.Scene.collider_toolkit_manage_expanded = bpy.props.BoolProperty(default=True)
    
    for cls in classes:
        register_class(cls)

def unregister():
    for cls in reversed(classes):
        unregister_class(cls)
    
    # Unregister properties
    del bpy.types.Scene.collider_toolkit_uv_expanded
    del bpy.types.Scene.collider_toolkit_manage_expanded

if __name__ == "__main__":
    register()
