import bpy
import os
import json

class OBJECT_OT_export_lights(bpy.types.Operator):
    bl_idname = "object.export_lights"
    bl_label = "Export Lights (EXPERIMENTAL)"
    bl_description = "Export lights from LightsEXPORT collection to JSON file"
    bl_options = {'REGISTER', 'UNDO'}


    export_folder: bpy.props.StringProperty(
        name="Export Folder",
        description="Folder name to export lights JSON file (will be created in Desktop)",
        default="lights_export",
    )

    collection_name: bpy.props.StringProperty(
        name="Collection Name",
        description="Name of the collection containing lights",
        default="LightsEXPORT",
    )

    def get_lights_collection_data(self, collection):
        objs_data = []
        
        for ob in collection.objects:
            if ob.type != "LIGHT":
                continue
            
            print(f"\nlight object: {ob}, {ob.name}\ndata: {ob.data}\ntype: {ob.type}")
            
            matrix_world = ob.matrix_world.copy()
            blender_pos = matrix_world.to_translation()
            sdk_pos = {}
            sdk_pos['x'] = -blender_pos.x
            sdk_pos['y'] = blender_pos.z
            sdk_pos['z'] = -blender_pos.y
            
            color = ob.data.color
            sdk_color = {}
            sdk_color['r'] = color.r
            sdk_color['g'] = color.g
            sdk_color['b'] = color.b
            
            intensity = ob.data.energy * 100
            range_val = getattr(ob.data, 'range', 10)
            if not range_val:
                range_val = 10
            
            ob_data = {}
            ob_data['name'] = ob.name
            ob_data['position'] = sdk_pos
            ob_data['color'] = sdk_color
            ob_data['intensity'] = intensity
            ob_data['range'] = range_val
            
            objs_data.append(ob_data)
            print(f"   * {ob_data}")
        
        return objs_data

    def execute(self, context):
        print("=== Starting Light Export Script ===")
        
        depsgraph = bpy.context.evaluated_depsgraph_get()
        depsgraph.update()
        
        for ob in bpy.context.selected_objects:
            ob.select_set(False)
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.view_layer.objects.active = None

        print(f"Looking for collection: {self.collection_name}")
        
        if self.collection_name not in bpy.data.collections:
            self.report({'ERROR'}, f"Collection '{self.collection_name}' not found!")
            return {'CANCELLED'}

        master_collection = bpy.data.collections[self.collection_name]
        lights_in_master = [obj for obj in master_collection.objects if obj.type == "LIGHT"]
        sub_collections = master_collection.children
        
        print(f"Lights in master collection: {len(lights_in_master)}")
        print(f"Child collections: {len(sub_collections)}")
        
        lights_data = {}
        
        if lights_in_master:
            print(f"Processing lights directly in '{self.collection_name}' collection")
            light_data = self.get_lights_collection_data(master_collection)
            if light_data:
                lights_data[self.collection_name] = light_data
                print(f"Found {len(light_data)} lights in master collection")
        
        for collection in sub_collections:
            print(f'Processing child collection: {collection.name}')
            light_data = self.get_lights_collection_data(collection)
            
            if light_data:
                lights_data[collection.name] = light_data
                print(f"Found {len(light_data)} lights in child collection")
            else:
                print(f"No lights found in child collection: {collection.name}")
        
        if not lights_data:
            self.report({'WARNING'}, "No light data found to export!")
            return {'CANCELLED'}
        
        print(f"Total lights found: {sum(len(lights) for lights in lights_data.values())}")
        
        lights_json = json.dumps(lights_data, indent=4)
        
        # Use blend file directory with user-specified folder name
        if bpy.data.filepath:
            # Blend file is saved - use its directory
            blend_dir = os.path.dirname(bpy.data.filepath)
            export_path = os.path.join(blend_dir, self.export_folder)
            print(f"Using blend file directory: {blend_dir}")
        else:
            # Blend file not saved - fallback to Desktop
            home_dir = os.path.expanduser("~")
            export_path = os.path.join(home_dir, "Desktop", self.export_folder)
            print(f"Blend file not saved, using Desktop: {home_dir}")
        
        print(f"User specified folder: '{self.export_folder}'")
        print(f"Using export path: {export_path}")
        
        # Create the directory
        try:
            os.makedirs(export_path, exist_ok=True)
            print(f"Directory created/verified: {export_path}")
        except Exception as e:
            print(f"Error creating directory: {e}")
            # Last resort - use current working directory with user folder name
            export_path = os.path.join(os.getcwd(), self.export_folder)
            os.makedirs(export_path, exist_ok=True)
            print(f"Using current directory: {export_path}")
        
        output_file = os.path.join(export_path, master_collection.name + ".json")
        print(f"Writing to: {output_file}")
        
        try:
            with open(output_file, "w") as f:
                f.write(lights_json)
            print(f"SUCCESS: Lights data exported to: {output_file}")
            self.report({'INFO'}, f"Lights exported to: {output_file}")
        except Exception as e:
            print(f"ERROR writing file: {e}")
            self.report({'ERROR'}, f"Error writing file: {e}")
            return {'CANCELLED'}
        
        print("=== Script Finished ===")
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "export_folder")
        layout.prop(self, "collection_name")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
