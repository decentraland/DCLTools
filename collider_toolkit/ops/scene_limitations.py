import bpy
import math
import mathutils

class OBJECT_OT_scene_limitations(bpy.types.Operator):
    bl_idname = "object.scene_limitations"
    bl_label = "Scene Limitations Calculator"
    bl_description = "Calculate Decentraland scene limitations based on parcel count"
    bl_options = {'REGISTER', 'UNDO'}

    parcel_count: bpy.props.IntProperty(
        name="Parcel Count",
        description="Number of parcels in your scene (e.g., 2x2 = 4 parcels)",
        default=4,
        min=1,
        max=100,
    )

    def calculate_limitations(self, n):
        """Calculate scene limitations based on parcel count"""
        import math
        
        # Basic calculations
        triangles = n * 10000
        entities = n * 200
        bodies = n * 300
        
        # Logarithmic calculations
        log_factor = math.log2(n + 1)
        materials = int(log_factor * 20)
        textures = int(log_factor * 10)
        height = int(log_factor * 20)
        
        # File size calculations
        if n <= 20:  # Genesis City
            total_file_size_mb = n * 15
            max_file_size_mb = min(50, total_file_size_mb)
        else:  # Worlds
            total_file_size_mb = 300  # Max for worlds
            max_file_size_mb = 50
        
        file_count = n * 200
        
        return {
            'triangles': triangles,
            'entities': entities,
            'bodies': bodies,
            'materials': materials,
            'textures': textures,
            'height': height,
            'total_file_size_mb': total_file_size_mb,
            'max_file_size_mb': max_file_size_mb,
            'file_count': file_count
        }

    def count_current_usage(self):
        """Count current scene usage"""
        # Count triangles in all mesh objects
        triangle_count = 0
        for obj in bpy.data.objects:
            if obj.type == 'MESH' and obj.data:
                triangle_count += len(obj.data.polygons)
        
        # Count entities (visible objects)
        entity_count = 0
        for obj in bpy.data.objects:
            if obj.type in {'MESH', 'EMPTY', 'LIGHT', 'CAMERA'} and not obj.hide_viewport:
                entity_count += 1
        
        # Count bodies (mesh objects)
        body_count = 0
        for obj in bpy.data.objects:
            if obj.type == 'MESH' and obj.data and not obj.hide_viewport:
                body_count += 1
        
        # Count materials
        material_count = len(bpy.data.materials)
        
        # Count textures
        texture_count = len(bpy.data.images)
        
        # Calculate max height - use bounding box to get actual geometry height
        max_height = 0
        height_debug_info = []
        
        for obj in bpy.data.objects:
            # Only count visible mesh objects that are actually in the scene
            if (obj.type == 'MESH' and 
                not obj.hide_viewport and 
                obj.data and 
                len(obj.users_collection) > 0):  # Must be in at least one collection
                
                # Get the bounding box in world space
                # This gives us the actual highest point of the geometry
                bbox_corners = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
                highest_z = max(corner.z for corner in bbox_corners)
                
                # Only consider reasonable heights (filter out extreme values)
                if 0 <= highest_z <= 100:  # Reasonable height range in meters
                    max_height = max(max_height, highest_z)
                    height_debug_info.append(f"  {obj.name}: highest_z={highest_z:.2f}")
                else:
                    height_debug_info.append(f"  {obj.name}: SKIPPED (unreasonable height {highest_z:.2f})")
        
        # Debug: Print height calculation details
        print(f"DEBUG: Height calculation details:")
        print(f"DEBUG: Max height calculated: {max_height} Blender units")
        print(f"DEBUG: Scene unit scale: {bpy.context.scene.unit_settings.scale_length}")
        for info in height_debug_info[:15]:  # Show first 15 objects
            print(info)
        if len(height_debug_info) > 15:
            print(f"DEBUG: ... and {len(height_debug_info) - 15} more objects")
        
        # Convert to meters (assuming Blender units are in meters by default)
        height_in_meters = max_height
        
        return {
            'triangles': triangle_count,
            'entities': entity_count,
            'bodies': body_count,
            'materials': material_count,
            'textures': texture_count,
            'height': int(height_in_meters)
        }

    def execute(self, context):
        limitations = self.calculate_limitations(self.parcel_count)
        current_usage = self.count_current_usage()
        
        # Create a detailed report with current usage vs limits
        report_lines = [
            f"=== DECENTRALAND SCENE LIMITATIONS ===",
            f"Parcel Count: {self.parcel_count} parcels",
            f"",
            f"RENDERING LIMITS (Current / Limit):",
            f"• Triangles: {current_usage['triangles']:,} / {limitations['triangles']:,} ({self._get_percentage(current_usage['triangles'], limitations['triangles'])}%)",
            f"• Entities: {current_usage['entities']:,} / {limitations['entities']:,} ({self._get_percentage(current_usage['entities'], limitations['entities'])}%)",
            f"• Bodies (Meshes): {current_usage['bodies']:,} / {limitations['bodies']:,} ({self._get_percentage(current_usage['bodies'], limitations['bodies'])}%)",
            f"• Materials: {current_usage['materials']:,} / {limitations['materials']:,} ({self._get_percentage(current_usage['materials'], limitations['materials'])}%)",
            f"• Textures: {current_usage['textures']:,} / {limitations['textures']:,} ({self._get_percentage(current_usage['textures'], limitations['textures'])}%)",
            f"• Height: {current_usage['height']} / {limitations['height']} meters ({self._get_percentage(current_usage['height'], limitations['height'])}%)",
            f"",
            f"FILE LIMITS:",
            f"• Total File Size: {limitations['total_file_size_mb']} MB",
            f"• Max File Size: {limitations['max_file_size_mb']} MB per file",
            f"• File Count: {limitations['file_count']:,} files",
            f"",
            f"IMPORTANT NOTES:",
            f"• Only rendered entities count toward limits",
            f"• Player avatars don't count toward limits",
            f"• Limits apply to what's visible at any time",
            f"• Genesis City: 15 MB per parcel (max 300 MB)",
            f"• Worlds: Up to 300 MB total"
        ]
        
        # Check for warnings
        warnings = []
        if current_usage['triangles'] > limitations['triangles']:
            warnings.append(f"⚠️  TRIANGLES: Exceeding limit by {current_usage['triangles'] - limitations['triangles']:,}")
        if current_usage['entities'] > limitations['entities']:
            warnings.append(f"⚠️  ENTITIES: Exceeding limit by {current_usage['entities'] - limitations['entities']:,}")
        if current_usage['bodies'] > limitations['bodies']:
            warnings.append(f"⚠️  BODIES: Exceeding limit by {current_usage['bodies'] - limitations['bodies']:,}")
        if current_usage['materials'] > limitations['materials']:
            warnings.append(f"⚠️  MATERIALS: Exceeding limit by {current_usage['materials'] - limitations['materials']:,}")
        if current_usage['textures'] > limitations['textures']:
            warnings.append(f"⚠️  TEXTURES: Exceeding limit by {current_usage['textures'] - limitations['textures']:,}")
        if current_usage['height'] > limitations['height']:
            warnings.append(f"⚠️  HEIGHT: Exceeding limit by {current_usage['height'] - limitations['height']}m")
        
        if warnings:
            report_lines.extend(["", "⚠️  WARNINGS:"] + warnings)
        
        # Print to console
        for line in report_lines:
            print(line)
        
        # Show in Blender
        if warnings:
            self.report({'WARNING'}, f"Scene analysis complete - {len(warnings)} warnings found. Check console for details.")
        else:
            self.report({'INFO'}, f"Scene analysis complete - All limits within bounds. Check console for details.")
        
        return {'FINISHED'}

    def _get_percentage(self, current, limit):
        """Calculate percentage usage"""
        if limit == 0:
            return "N/A"
        percentage = (current / limit) * 100
        return f"{percentage:.1f}"

    def draw(self, context):
        layout = self.layout
        
        # Input section
        col = layout.column(align=True)
        col.label(text="Enter your scene size:")
        col.prop(self, "parcel_count")
        
        # Calculate and show preview
        if self.parcel_count > 0:
            limitations = self.calculate_limitations(self.parcel_count)
            current_usage = self.count_current_usage()
            
            layout.separator()
            layout.label(text="Current Usage vs Limits:", icon='INFO')
            
            box = layout.box()
            col = box.column(align=True)
            
            # Show current usage vs limits
            triangles_pct = self._get_percentage(current_usage['triangles'], limitations['triangles'])
            entities_pct = self._get_percentage(current_usage['entities'], limitations['entities'])
            bodies_pct = self._get_percentage(current_usage['bodies'], limitations['bodies'])
            materials_pct = self._get_percentage(current_usage['materials'], limitations['materials'])
            textures_pct = self._get_percentage(current_usage['textures'], limitations['textures'])
            height_pct = self._get_percentage(current_usage['height'], limitations['height'])
            
            # Color coding for usage levels
            def get_icon(percentage_str):
                if percentage_str == "N/A":
                    return 'INFO'
                pct = float(percentage_str.replace('%', ''))
                if pct >= 100:
                    return 'ERROR'
                elif pct >= 80:
                    return 'WARNING'
                else:
                    return 'CHECKMARK'
            
            col.label(text=f"Triangles: {current_usage['triangles']:,} / {limitations['triangles']:,} ({triangles_pct}%)", icon=get_icon(triangles_pct))
            col.label(text=f"Entities: {current_usage['entities']:,} / {limitations['entities']:,} ({entities_pct}%)", icon=get_icon(entities_pct))
            col.label(text=f"Bodies: {current_usage['bodies']:,} / {limitations['bodies']:,} ({bodies_pct}%)", icon=get_icon(bodies_pct))
            col.label(text=f"Materials: {current_usage['materials']:,} / {limitations['materials']:,} ({materials_pct}%)", icon=get_icon(materials_pct))
            col.label(text=f"Textures: {current_usage['textures']:,} / {limitations['textures']:,} ({textures_pct}%)", icon=get_icon(textures_pct))
            col.label(text=f"Height: {current_usage['height']} / {limitations['height']}m ({height_pct}%)", icon=get_icon(height_pct))
            
            layout.separator()
            layout.label(text="File Limits:", icon='FILE')
            box2 = layout.box()
            col2 = box2.column(align=True)
            col2.label(text=f"File Size: {limitations['total_file_size_mb']} MB")
            col2.label(text=f"Files: {limitations['file_count']:,}")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
