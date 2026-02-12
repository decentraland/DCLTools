import bpy

class OBJECT_OT_rename_mesh_data(bpy.types.Operator):
    bl_idname = "object.rename_mesh_data"
    bl_label = "Rename Mesh Data to Object Name"
    bl_description = "Rename mesh data blocks to match their object names (e.g., 'Cube.001' becomes 'Cube.001')"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        renamed_count = 0
        skipped_count = 0
        
        # Process selected objects or all objects in the scene
        objects_to_process = bpy.context.selected_objects if bpy.context.selected_objects else list(bpy.data.objects)
        
        for obj in objects_to_process:
            if obj.type == 'MESH' and obj.data:
                old_name = obj.data.name
                new_name = obj.name
                
                # Only rename if the names are different
                if old_name != new_name:
                    try:
                        obj.data.name = new_name
                        renamed_count += 1
                        print(f"✓ Renamed: '{old_name}' → '{new_name}'")
                    except Exception as e:
                        print(f"✗ Failed to rename '{old_name}' → '{new_name}': {e}")
                        skipped_count += 1
                else:
                    skipped_count += 1
        
        # Report results
        if renamed_count > 0:
            self.report({'INFO'}, f"Renamed {renamed_count} mesh data block(s)")
            print(f"\n=== RENAME MESH DATA COMPLETE ===")
            print(f"Renamed: {renamed_count}")
            print(f"Skipped: {skipped_count}")
            print(f"Total processed: {renamed_count + skipped_count}")
        else:
            self.report({'INFO'}, f"No mesh data blocks needed renaming")
            print(f"\n=== RENAME MESH DATA COMPLETE ===")
            print(f"All mesh data blocks already match their object names")
        
        return {'FINISHED'}

