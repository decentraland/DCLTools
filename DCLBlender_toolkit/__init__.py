bl_info = {
    "name": "Decentraland Tools",
    "author": "Your Name",
    "version": (1, 1, 0),
    "blender": (2, 80, 0),
    "location": "3D Viewport > Sidebar (N) > Decentraland Tools",
    "description": "Collection of tools for Decentraland asset creation and optimization (Blender 2.80 - 5.0+)",
    "category": "Object",
}

# Logo files: 
# - assets/dcl-logo-mono.svg (original)
# - assets/dcl-logo-new.svg (new landscape design)

import bpy
from bpy.utils import register_class, unregister_class

from .ops.remove_uvs import OBJECT_OT_remove_uvs_from_colliders
from .ops.strip_materials import OBJECT_OT_strip_materials_from_colliders
from .ops.rename_add_suffix import OBJECT_OT_rename_add_collider_suffix
from .ops.simplify_colliders import OBJECT_OT_simplify_colliders
from .ops.cleanup_colliders import OBJECT_OT_cleanup_colliders
from .ops.export_lights import OBJECT_OT_export_lights
from .ops.create_parcels import OBJECT_OT_create_parcels
from .ops.rename_textures import OBJECT_OT_rename_textures
from .ops.enable_backface_culling import OBJECT_OT_enable_backface_culling
from .ops.link_avatar_wearables import OBJECT_OT_link_avatar_wearables
from .ops.scene_limitations import OBJECT_OT_scene_limitations
from .ops.documentation import OBJECT_OT_open_documentation, OBJECT_OT_scene_limits_guide, OBJECT_OT_asset_guidelines
from .ops.remove_empty_objects import OBJECT_OT_remove_empty_objects
from .ops.toggle_display_mode import OBJECT_OT_toggle_display_mode
from .ops.particle_to_armature import OBJECT_OT_particles_to_armature_converter
from .ops.resize_textures import OBJECT_OT_resize_textures
from .ops.apply_transforms import OBJECT_OT_apply_transforms
from .ops.avatar_limitations import OBJECT_OT_avatar_limitations
from .ops.rename_mesh_data import OBJECT_OT_rename_mesh_data
from .ops.replace_materials import (
    MaterialListItem,
    OBJECT_OT_replace_materials,
    OBJECT_OT_add_source_material_to_list,
    OBJECT_OT_remove_source_material_from_list,
)

def load_custom_icon():
    """Load custom Decentraland logo as Blender icon"""
    # Use a tool-type icon that represents the add-on's functionality
    return 'TOOL_SETTINGS'

class VIEW3D_PT_dcl_tools(bpy.types.Panel):
    bl_label = "Decentraland Tools"
    bl_idname = "VIEW3D_PT_dcl_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Decentraland Tools"

    def draw(self, context):
        layout = self.layout
        
        # Header with tool icon
        row = layout.row(align=True)
        # Use a tool-type icon that represents the add-on's functionality
        row.label(text="", icon='TOOL_SETTINGS')  # Tool settings icon
        row.label(text="Decentraland Tools")
        
        # Scene Creation Section
        box = layout.box()
        row = box.row()
        row.prop(context.scene, "dcl_tools_scene_expanded", text="Scene Creation", icon='TRIA_DOWN' if context.scene.dcl_tools_scene_expanded else 'TRIA_RIGHT', emboss=False)
        
        if context.scene.dcl_tools_scene_expanded:
            col = box.column(align=True)
            col.operator(OBJECT_OT_create_parcels.bl_idname, text="Create Parcels", icon='MESH_PLANE')
            col.operator(OBJECT_OT_scene_limitations.bl_idname, text="Scene Limitations Calculator", icon='INFO')
        
        # Export Section
        box = layout.box()
        row = box.row()
        row.prop(context.scene, "dcl_tools_export_expanded", text="Export", icon='TRIA_DOWN' if context.scene.dcl_tools_export_expanded else 'TRIA_RIGHT', emboss=False)
        
        if context.scene.dcl_tools_export_expanded:
            col = box.column(align=True)
            col.operator(OBJECT_OT_export_lights.bl_idname, text="Export Lights (EXPERIMENTAL)", icon='LIGHT_DATA')
        
        # Avatars Section
        box = layout.box()
        row = box.row()
        row.prop(context.scene, "dcl_tools_avatars_expanded", text="Avatars", icon='TRIA_DOWN' if context.scene.dcl_tools_avatars_expanded else 'TRIA_RIGHT', emboss=False)
        
        if context.scene.dcl_tools_avatars_expanded:
            col = box.column(align=True)
            col.operator(OBJECT_OT_link_avatar_wearables.bl_idname, text="Avatar Shapes", icon='ARMATURE_DATA')
            col.operator(OBJECT_OT_avatar_limitations.bl_idname, text="Avatar Limitations Calculator", icon='INFO')
        
        # Converter Section
        box = layout.box()
        row = box.row()
        row.prop(context.scene, "dcl_tools_converter_expanded", text="Converter", icon='TRIA_DOWN' if context.scene.dcl_tools_converter_expanded else 'TRIA_RIGHT', emboss=False)
        
        if context.scene.dcl_tools_converter_expanded:
            col = box.column(align=True)
            col.operator(OBJECT_OT_particles_to_armature_converter.bl_idname, text="Particle to Armature", icon='PARTICLES')
        
        # Materials & Textures Section
        box = layout.box()
        row = box.row()
        row.prop(context.scene, "dcl_tools_materials_expanded", text="Materials & Textures", icon='TRIA_DOWN' if context.scene.dcl_tools_materials_expanded else 'TRIA_RIGHT', emboss=False)
        
        if context.scene.dcl_tools_materials_expanded:
            col = box.column(align=True)
            col.operator(OBJECT_OT_replace_materials.bl_idname, text="Replace Materials", icon='MATERIAL_DATA')
            col.operator(OBJECT_OT_resize_textures.bl_idname, text="Resize Textures", icon='IMAGE_DATA')
            col.operator(OBJECT_OT_enable_backface_culling.bl_idname, text="Enable Backface Culling", icon='MESH_CUBE')
        
        # CleanUp Section
        box = layout.box()
        row = box.row()
        row.prop(context.scene, "dcl_tools_cleanup_expanded", text="CleanUp", icon='TRIA_DOWN' if context.scene.dcl_tools_cleanup_expanded else 'TRIA_RIGHT', emboss=False)
        
        if context.scene.dcl_tools_cleanup_expanded:
            col = box.column(align=True)
            col.operator(OBJECT_OT_remove_empty_objects.bl_idname, text="Remove Empty Objects", icon='X')
            col.operator(OBJECT_OT_apply_transforms.bl_idname, text="Apply Transforms", icon='SNAP_ON')
            col.operator(OBJECT_OT_rename_mesh_data.bl_idname, text="Rename Mesh Data to Object Name", icon='MESH_DATA')
            col.operator(OBJECT_OT_rename_textures.bl_idname, text="Rename Textures by Material", icon='TEXTURE')
        
        # Viewer Section
        box = layout.box()
        row = box.row()
        row.prop(context.scene, "dcl_tools_viewer_expanded", text="Viewer", icon='TRIA_DOWN' if context.scene.dcl_tools_viewer_expanded else 'TRIA_RIGHT', emboss=False)
        
        if context.scene.dcl_tools_viewer_expanded:
            col = box.column(align=True)
            col.operator(OBJECT_OT_toggle_display_mode.bl_idname, text="Toggle Display Mode", icon='RESTRICT_VIEW_OFF')
        
        # Collider Management Section
        box = layout.box()
        row = box.row()
        row.prop(context.scene, "dcl_tools_manage_expanded", text="Collider Management", icon='TRIA_DOWN' if context.scene.dcl_tools_manage_expanded else 'TRIA_RIGHT', emboss=False)
        
        if context.scene.dcl_tools_manage_expanded:
            col = box.column(align=True)
            col.operator(OBJECT_OT_rename_add_collider_suffix.bl_idname, text="Add _collider Suffix", icon='OUTLINER_OB_MESH')
            col.operator(OBJECT_OT_remove_uvs_from_colliders.bl_idname, text="Remove UVs from Colliders", icon='UV')
            col.operator(OBJECT_OT_strip_materials_from_colliders.bl_idname, text="Strip Materials from Colliders", icon='MATERIAL')
            col.operator(OBJECT_OT_simplify_colliders.bl_idname, text="Simplify Colliders", icon='MOD_DECIM')
        
        # Documentation Section
        box = layout.box()
        row = box.row()
        row.prop(context.scene, "dcl_tools_docs_expanded", text="Documentation", icon='TRIA_DOWN' if context.scene.dcl_tools_docs_expanded else 'TRIA_RIGHT', emboss=False)
        
        if context.scene.dcl_tools_docs_expanded:
            col = box.column(align=True)
            col.operator(OBJECT_OT_open_documentation.bl_idname, text="Open Documentation", icon='HELP')
            col.operator(OBJECT_OT_scene_limits_guide.bl_idname, text="Scene Limits Guide", icon='INFO')
            col.operator(OBJECT_OT_asset_guidelines.bl_idname, text="Asset Guidelines", icon='FILE_TEXT')

classes = (
    MaterialListItem,
    OBJECT_OT_remove_uvs_from_colliders,
    OBJECT_OT_strip_materials_from_colliders,
    OBJECT_OT_rename_add_collider_suffix,
    OBJECT_OT_simplify_colliders,
    OBJECT_OT_cleanup_colliders,
    OBJECT_OT_remove_empty_objects,
    OBJECT_OT_toggle_display_mode,
    OBJECT_OT_export_lights,
    OBJECT_OT_create_parcels,
    OBJECT_OT_rename_textures,
    OBJECT_OT_resize_textures,
    OBJECT_OT_enable_backface_culling,
    OBJECT_OT_link_avatar_wearables,
    OBJECT_OT_particles_to_armature_converter,
    OBJECT_OT_scene_limitations,
    OBJECT_OT_apply_transforms,
    OBJECT_OT_avatar_limitations,
    OBJECT_OT_rename_mesh_data,
    OBJECT_OT_replace_materials,
    OBJECT_OT_add_source_material_to_list,
    OBJECT_OT_remove_source_material_from_list,
    OBJECT_OT_open_documentation,
    OBJECT_OT_scene_limits_guide,
    OBJECT_OT_asset_guidelines,
    VIEW3D_PT_dcl_tools,
)

def register():
    # Register properties
    bpy.types.Scene.dcl_tools_scene_expanded = bpy.props.BoolProperty(default=True)
    bpy.types.Scene.dcl_tools_export_expanded = bpy.props.BoolProperty(default=True)
    bpy.types.Scene.dcl_tools_avatars_expanded = bpy.props.BoolProperty(default=True)
    bpy.types.Scene.dcl_tools_converter_expanded = bpy.props.BoolProperty(default=True)
    bpy.types.Scene.dcl_tools_materials_expanded = bpy.props.BoolProperty(default=True)
    bpy.types.Scene.dcl_tools_cleanup_expanded = bpy.props.BoolProperty(default=True)
    bpy.types.Scene.dcl_tools_viewer_expanded = bpy.props.BoolProperty(default=True)
    bpy.types.Scene.dcl_tools_manage_expanded = bpy.props.BoolProperty(default=True)
    bpy.types.Scene.dcl_tools_docs_expanded = bpy.props.BoolProperty(default=True)
    
    # Particle System Converter properties
    bpy.types.Scene.ps_converter_out_collection = bpy.props.StringProperty(
        name="Output Collection",
        description="Collection name for converted armature and objects",
        default="ParticleArmature_Output"
    )
    bpy.types.Scene.ps_converter_start_frame = bpy.props.IntProperty(
        name="Start Frame",
        description="Start frame for animation conversion",
        default=1,
        min=1
    )
    bpy.types.Scene.ps_converter_end_frame = bpy.props.IntProperty(
        name="End Frame",
        description="End frame for animation conversion",
        default=250,
        min=1
    )
    
    # Replace Materials operator properties
    bpy.types.WindowManager.replace_materials_add = bpy.props.StringProperty(
        name="Replace Materials Add",
        description="Temporary property for adding materials to replacement list",
        default="",
    )
    bpy.types.WindowManager.replace_materials_remove = bpy.props.IntProperty(
        name="Replace Materials Remove",
        description="Temporary property for removing materials from replacement list",
        default=-1,
    )
    
    # Load custom icon
    load_custom_icon()
    
    for cls in classes:
        register_class(cls)

def unregister():
    for cls in reversed(classes):
        unregister_class(cls)
    
    # Unregister properties
    del bpy.types.Scene.dcl_tools_scene_expanded
    del bpy.types.Scene.dcl_tools_export_expanded
    del bpy.types.Scene.dcl_tools_avatars_expanded
    del bpy.types.Scene.dcl_tools_converter_expanded
    del bpy.types.Scene.dcl_tools_materials_expanded
    del bpy.types.Scene.dcl_tools_cleanup_expanded
    del bpy.types.Scene.dcl_tools_viewer_expanded
    del bpy.types.Scene.dcl_tools_manage_expanded
    del bpy.types.Scene.dcl_tools_docs_expanded
    
    # Unregister Particle System Converter properties
    del bpy.types.Scene.ps_converter_out_collection
    del bpy.types.Scene.ps_converter_start_frame
    del bpy.types.Scene.ps_converter_end_frame
    
    # Unregister Replace Materials properties
    if hasattr(bpy.types.WindowManager, 'replace_materials_add'):
        del bpy.types.WindowManager.replace_materials_add
    if hasattr(bpy.types.WindowManager, 'replace_materials_remove'):
        del bpy.types.WindowManager.replace_materials_remove

if __name__ == "__main__":
    register()