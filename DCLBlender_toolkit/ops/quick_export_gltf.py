import bpy
import os


class OBJECT_OT_quick_export_gltf(bpy.types.Operator):
    bl_idname = "object.quick_export_gltf"
    bl_label = "Quick Export glTF"
    bl_description = "One-click glTF/GLB export with Decentraland-optimized settings"
    bl_options = {'REGISTER', 'UNDO'}

    export_format: bpy.props.EnumProperty(
        name="Format",
        description="Export file format",
        items=[
            ('GLB', 'glTF Binary (.glb)', 'Single binary file (recommended for DCL)'),
            ('GLTF_SEPARATE', 'glTF Separate (.gltf + .bin)', 'Separate files'),
        ],
        default='GLB',
    )

    export_selected: bpy.props.BoolProperty(
        name="Selected Only",
        description="Export only selected objects",
        default=False,
    )

    apply_modifiers: bpy.props.BoolProperty(
        name="Apply Modifiers",
        description="Apply modifiers before exporting",
        default=True,
    )

    export_cameras: bpy.props.BoolProperty(
        name="Export Cameras",
        description="Include cameras in the export",
        default=False,
    )

    export_lights: bpy.props.BoolProperty(
        name="Export Lights",
        description="Include lights in the export (punctual lights extension)",
        default=False,
    )

    export_folder: bpy.props.StringProperty(
        name="Export Folder",
        description="Subfolder name for the export (created next to the .blend file)",
        default="export",
    )

    filename: bpy.props.StringProperty(
        name="Filename",
        description="Name of the exported file (without extension)",
        default="scene",
    )

    def execute(self, context):
        # Determine output directory
        if bpy.data.filepath:
            blend_dir = os.path.dirname(bpy.data.filepath)
            out_dir = os.path.join(blend_dir, self.export_folder)
        else:
            home_dir = os.path.expanduser("~")
            out_dir = os.path.join(home_dir, "Desktop", self.export_folder)

        os.makedirs(out_dir, exist_ok=True)

        ext = ".glb" if self.export_format == 'GLB' else ".gltf"
        filepath = os.path.join(out_dir, self.filename + ext)

        # Build export kwargs
        kwargs = {
            'filepath': filepath,
            'export_format': self.export_format,
            'use_selection': self.export_selected,
            'export_apply': self.apply_modifiers,
            'export_cameras': self.export_cameras,
            'export_lights': self.export_lights,
            'export_yup': True,
        }

        try:
            bpy.ops.export_scene.gltf(**kwargs)
            file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
            size_str = self._format_size(file_size)
            self.report({'INFO'}, f"Exported to {filepath} ({size_str})")
        except Exception as e:
            self.report({'ERROR'}, f"Export failed: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}

    def _format_size(self, size_bytes):
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.2f} MB"

    def draw(self, context):
        layout = self.layout

        layout.prop(self, "export_format")
        layout.separator()

        layout.prop(self, "filename")
        layout.prop(self, "export_folder")
        layout.separator()

        col = layout.column(align=True)
        col.prop(self, "export_selected")
        col.prop(self, "apply_modifiers")
        col.prop(self, "export_cameras")
        col.prop(self, "export_lights")

        layout.separator()
        # Show output path preview
        if bpy.data.filepath:
            blend_dir = os.path.dirname(bpy.data.filepath)
            out_dir = os.path.join(blend_dir, self.export_folder)
        else:
            out_dir = os.path.join("~/Desktop", self.export_folder)

        ext = ".glb" if self.export_format == 'GLB' else ".gltf"
        layout.label(text=f"Output: {out_dir}/{self.filename}{ext}", icon='FILE')

    def invoke(self, context, event):
        # Default filename from blend file
        if bpy.data.filepath:
            blend_name = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
            self.filename = blend_name
        return context.window_manager.invoke_props_dialog(self, width=450)
