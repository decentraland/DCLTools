import bpy

class OBJECT_OT_make_avatar_editable(bpy.types.Operator):
    bl_idname = "object.make_avatar_editable"
    bl_label = "Make Avatar Editable"
    bl_description = "Convert linked avatar to local copy for manipulation and posing"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Find avatar collections
        avatar_collections = []
        for collection in bpy.data.collections:
            if "DCLAvatar_Shape" in collection.name:
                avatar_collections.append(collection)
        
        if not avatar_collections:
            self.report({'WARNING'}, "No avatar collections found. Please import avatars first.")
            return {'CANCELLED'}
        
        converted_objects = 0
        armatures_found = []
        
        for collection in avatar_collections:
            # Get all objects in the collection
            objects_to_convert = []
            for obj in collection.objects:
                if obj.library:  # If object is linked
                    objects_to_convert.append(obj)
            
            if not objects_to_convert:
                self.report({'INFO'}, f"Collection '{collection.name}' already contains local objects")
                continue
            
            # Convert linked objects to local copies
            for obj in objects_to_convert:
                try:
                    # Make local copy
                    obj.make_local()
                    converted_objects += 1
                    
                    # Store armatures for later mode switching
                    if obj.type == 'ARMATURE':
                        armatures_found.append(obj)
                    
                except Exception as e:
                    self.report({'WARNING'}, f"Could not convert '{obj.name}': {str(e)}")
        
        # Handle armature mode switching after all conversions
        if armatures_found:
            # Deselect all first
            bpy.ops.object.select_all(action='DESELECT')
            
            for armature in armatures_found:
                try:
                    # Select and activate armature
                    armature.select_set(True)
                    context.view_layer.objects.active = armature
                    
                    # Try to switch to Pose mode
                    bpy.ops.object.mode_set(mode='POSE')
                    self.report({'INFO'}, f"Armature '{armature.name}' is now editable in Pose mode")
                    
                except Exception as e:
                    # If Pose mode fails, ensure it's in Object mode
                    try:
                        bpy.ops.object.mode_set(mode='OBJECT')
                        self.report({'INFO'}, f"Armature '{armature.name}' is now editable in Object mode")
                    except:
                        self.report({'WARNING'}, f"Could not set mode for armature '{armature.name}': {str(e)}")
        
        if converted_objects > 0:
            self.report({'INFO'}, f"Successfully converted {converted_objects} linked objects to local copies")
            self.report({'INFO'}, "Avatars are now editable! Switch to Pose mode to manipulate bones.")
        else:
            self.report({'INFO'}, "No linked objects found to convert")
        
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        layout.label(text="This tool will convert linked avatars to local copies.")
        layout.separator()
        layout.label(text="After conversion:")
        layout.label(text="• Avatars become fully editable")
        layout.label(text="• You can pose and animate them")
        layout.label(text="• Switch to Pose mode to manipulate bones")
        layout.label(text="• Original blend files remain unchanged")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
