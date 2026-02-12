import bpy
import bmesh

class OBJECT_OT_create_parcels(bpy.types.Operator):
    bl_idname = "object.create_parcels"
    bl_label = "Create Parcels"
    bl_description = "Create a grid of Decentraland parcels with customizable dimensions"
    bl_options = {'REGISTER', 'UNDO'}

    parcels_x: bpy.props.IntProperty(
        name="Parcels X",
        description="Number of parcels in X direction",
        default=2,
        min=1,
        max=20,
    )

    parcels_y: bpy.props.IntProperty(
        name="Parcels Y", 
        description="Number of parcels in Y direction",
        default=2,
        min=1,
        max=20,
    )



    def execute(self, context):
        # Fixed parcel size for Decentraland
        parcel_size = 16.0
        
        # Calculate total dimensions
        total_width = self.parcels_x * parcel_size
        total_height = self.parcels_y * parcel_size
        
        # Create collection for parcels
        collection_name = f"Parcels_{self.parcels_x}x{self.parcels_y}"
        if collection_name in bpy.data.collections:
            # Delete existing collection and all its objects
            existing_collection = bpy.data.collections[collection_name]
            for obj in list(existing_collection.objects):
                bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.collections.remove(existing_collection)
            self.report({'INFO'}, f"Removed existing collection: {collection_name}")
        
        parcels_collection = bpy.data.collections.new(collection_name)
        context.scene.collection.children.link(parcels_collection)
        
        
        # Create single subdivided plane for all parcels
        bpy.ops.mesh.primitive_plane_add(
            location=(0, 0, 0),
            size=1.0  # Start with 1m plane
        )
        
        parcels_plane = context.active_object
        parcels_plane.name = f"Parcels_Grid_{self.parcels_x}x{self.parcels_y}"
        
        # Scale to total dimensions
        parcels_plane.scale = (total_width, total_height, 1.0)
        
        # Apply scale to freeze it at (1,1,1)
        bpy.context.view_layer.objects.active = parcels_plane
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        
        # Build the parcel grid mesh using standalone bmesh (in object mode)
        bm = bmesh.new()
        
        # Create grid vertices
        vertices = []
        for y in range(self.parcels_y + 1):
            for x in range(self.parcels_x + 1):
                # Calculate position
                pos_x = (x / self.parcels_x) - 0.5
                pos_y = (y / self.parcels_y) - 0.5
                pos_z = 0.0
                
                # Scale to actual dimensions
                pos_x *= total_width
                pos_y *= total_height
                
                # Create vertex
                vert = bm.verts.new((pos_x, pos_y, pos_z))
                vertices.append(vert)
        
        # Create faces
        for y in range(self.parcels_y):
            for x in range(self.parcels_x):
                # Calculate vertex indices
                v1 = vertices[y * (self.parcels_x + 1) + x]
                v2 = vertices[y * (self.parcels_x + 1) + x + 1]
                v3 = vertices[(y + 1) * (self.parcels_x + 1) + x + 1]
                v4 = vertices[(y + 1) * (self.parcels_x + 1) + x]
                
                # Create face
                bm.faces.new([v1, v2, v3, v4])
        
        # Write bmesh to mesh data and free
        bm.to_mesh(parcels_plane.data)
        bm.free()
        parcels_plane.data.update()
        
        # Add to collection
        parcels_collection.objects.link(parcels_plane)
        # Note: Newly created objects are not initially in scene collection, so no need to unlink
        
        
        # Select the parcels plane
        bpy.ops.object.select_all(action='DESELECT')
        for obj in parcels_collection.objects:
            obj.select_set(True)
        
        # Center view on parcels
        bpy.ops.view3d.view_selected()
        
        self.report({'INFO'}, f"Created subdivided plane with {self.parcels_x}x{self.parcels_y} parcels ({total_width}m x {total_height}m)")
        return {'FINISHED'}


    def draw(self, context):
        layout = self.layout
        layout.prop(self, "parcels_x")
        layout.prop(self, "parcels_y")
        
        # Show total dimensions (fixed 16m per parcel)
        total_width = self.parcels_x * 16.0
        total_height = self.parcels_y * 16.0
        layout.label(text=f"Total size: {total_width}m x {total_height}m")
        layout.label(text="Each parcel: 16m x 16m (Decentraland standard)")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
