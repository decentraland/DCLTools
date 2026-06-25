"""
Merge flat-color materials into a single palette-backed material.

Decentraland creators frequently author one material per color, which produces
one draw call per material for no visual benefit. This tool collapses every
*flat* (untextured) PBR material on the selected objects into ONE material
backed by a tiny palette atlas:

  * BaseColor palette  (sRGB)      - one swatch per unique colour
  * ORM palette        (Non-Color) - matching roughness / metallic per swatch

Each face that used a flat material is re-pointed at the merged material and its
UVs are collapsed onto the centre of its swatch, so the visual result is
identical while the draw-call count drops to one.

Materials that carry an image texture (BaseColor / Normal / Roughness /
Metallic), use transparency, or emit light are NOT touched - it makes no sense
to bake a real texture into a few-pixel palette. They are left as-is and
reported so the creator knows what stayed separate.

This operator is destructive (it edits meshes in place) and supports Undo.
"""

import math

import bpy

# ---------------------------------------------------------------------------
# sRGB <-> Linear (matches the glTF / Blender colour pipeline; mirrors
# export_material_atlas.py so the two tools agree on colour handling)
# ---------------------------------------------------------------------------


def _linear_to_srgb(v):
    if v <= 0.0031308:
        return max(0.0, v * 12.92)
    return 1.055 * math.pow(v, 1.0 / 2.4) - 0.055


# ---------------------------------------------------------------------------
# Swatch table
# ---------------------------------------------------------------------------

# How many unique (colour, roughness, metallic) combinations differ before two
# materials are considered the same swatch.
_COLOR_ROUND = 4
_SCALAR_ROUND = 3

# Pixel size of one swatch tile. Padding (>1px) guarantees the swatch centre is
# a pure colour even under bilinear filtering / mipmapping in the DCL renderer.
TILE = 8


class _Swatch:
    __slots__ = ("index", "color_linear", "roughness", "metallic")

    def __init__(self, index, color_linear, roughness, metallic):
        self.index = index
        self.color_linear = color_linear
        self.roughness = roughness
        self.metallic = metallic


class _SwatchTable:
    """Deduplicates flat materials into unique swatches across all objects."""

    def __init__(self):
        self._by_key = {}
        self.swatches = []

    def get_or_add(self, color_linear, roughness, metallic):
        key = (
            tuple(round(c, _COLOR_ROUND) for c in color_linear),
            round(roughness, _SCALAR_ROUND),
            round(metallic, _SCALAR_ROUND),
        )
        existing = self._by_key.get(key)
        if existing is not None:
            return existing
        sw = _Swatch(len(self.swatches), color_linear, roughness, metallic)
        self._by_key[key] = sw
        self.swatches.append(sw)
        return sw

    def __len__(self):
        return len(self.swatches)


# ---------------------------------------------------------------------------
# Material analysis - decide flat vs. leave-alone
# ---------------------------------------------------------------------------


def _find_principled(material):
    tree = material.node_tree
    for node in tree.nodes:
        if node.type == "OUTPUT_MATERIAL" and getattr(node, "is_active_output", False):
            surf = node.inputs.get("Surface")
            if surf and surf.is_linked:
                from_node = surf.links[0].from_node
                if from_node and from_node.type == "BSDF_PRINCIPLED":
                    return from_node
    for node in tree.nodes:
        if node.type == "BSDF_PRINCIPLED":
            return node
    return None


def _socket(principled, *names):
    for name in names:
        s = principled.inputs.get(name)
        if s:
            return s
    return None


def _constant_color(socket):
    """Return a linear (r, g, b) if the socket is a flat colour, else None.

    A socket is flat when it is unlinked, or linked to a plain RGB node. Any
    image texture (directly or upstream) means the material is textured.
    """
    if socket is None:
        return None
    if not socket.is_linked:
        dv = socket.default_value
        return (dv[0], dv[1], dv[2])
    from_node = socket.links[0].from_node
    node_type = getattr(from_node, "type", "")
    if node_type == "RGB":
        out = from_node.outputs[0].default_value
        return (out[0], out[1], out[2])
    # TEX_IMAGE, MIX with a texture, etc. -> not flat
    return None


def _constant_scalar(socket, default):
    """Return the scalar value if unlinked, else None (linked = textured)."""
    if socket is None:
        return default
    if socket.is_linked:
        return None
    return float(socket.default_value)


class _Analysis:
    __slots__ = ("flat", "reason", "color_linear", "roughness", "metallic")

    def __init__(self, flat, reason="", color_linear=None, roughness=0.5, metallic=0.0):
        self.flat = flat
        self.reason = reason
        self.color_linear = color_linear
        self.roughness = roughness
        self.metallic = metallic


def analyze_material(material):
    """Classify a material as a flat-colour merge candidate or leave-alone."""
    if material is None:
        return _Analysis(False, "empty slot")
    if not material.use_nodes or not material.node_tree:
        return _Analysis(False, "no nodes")

    principled = _find_principled(material)
    if not principled:
        return _Analysis(False, "no Principled BSDF")

    color = _constant_color(_socket(principled, "Base Color"))
    if color is None:
        return _Analysis(False, "textured base color")

    # Normal map -> textured
    normal = _socket(principled, "Normal")
    if normal is not None and normal.is_linked:
        return _Analysis(False, "has normal map")

    roughness = _constant_scalar(_socket(principled, "Roughness"), 0.5)
    if roughness is None:
        return _Analysis(False, "textured roughness")

    metallic = _constant_scalar(_socket(principled, "Metallic"), 0.0)
    if metallic is None:
        return _Analysis(False, "textured metallic")

    # Emission -> leave alone (palette would silently drop the glow)
    emis_str = _socket(principled, "Emission Strength")
    emis_col = _socket(principled, "Emission Color", "Emission")
    strength = float(getattr(emis_str, "default_value", 0.0)) if emis_str else 0.0
    if (
        strength > 0.0
        and emis_col is not None
        and (emis_col.is_linked or any(c > 0.0 for c in emis_col.default_value[:3]))
    ):
        return _Analysis(False, "emissive")

    # Transparency -> leave alone only when alpha is *actually* used. The
    # blend_method flag alone is unreliable: Blender (4.2+/EEVEE Next, 5.x)
    # defaults it to "HASHED" even on fully opaque materials, so we key off the
    # real Alpha socket instead - a linked alpha, or a constant below 1.0.
    alpha = _socket(principled, "Alpha")
    if alpha is not None:
        if alpha.is_linked:
            return _Analysis(False, "uses alpha texture")
        if float(alpha.default_value) < 0.999:
            return _Analysis(False, "partial transparency")

    return _Analysis(True, color_linear=color, roughness=roughness, metallic=metallic)


# ---------------------------------------------------------------------------
# Palette image + merged material construction
# ---------------------------------------------------------------------------


def _grid_dims(count):
    cols = max(1, math.ceil(math.sqrt(count)))
    rows = max(1, math.ceil(count / cols))
    return cols, rows


def _swatch_uv_center(index, cols, rows):
    col = index % cols
    row = index // cols
    u = (col * TILE + TILE * 0.5) / (cols * TILE)
    v = (row * TILE + TILE * 0.5) / (rows * TILE)
    return (u, v)


def _build_palette_images(swatches, name_prefix):
    cols, rows = _grid_dims(len(swatches))
    width, height = cols * TILE, rows * TILE

    base = bpy.data.images.new(f"{name_prefix}_BaseColor", width=width, height=height, alpha=False)
    base.colorspace_settings.name = "sRGB"
    orm = bpy.data.images.new(f"{name_prefix}_ORM", width=width, height=height, alpha=False)
    orm.colorspace_settings.name = "Non-Color"

    base_buf = [0.0] * (width * height * 4)
    orm_buf = [0.0] * (width * height * 4)

    for sw in swatches:
        col = sw.index % cols
        row = sw.index // cols
        # sRGB-encode the linear colour so the sRGB texture samples back to the
        # original linear value the BSDF expects.
        r = min(1.0, max(0.0, _linear_to_srgb(sw.color_linear[0])))
        g = min(1.0, max(0.0, _linear_to_srgb(sw.color_linear[1])))
        b = min(1.0, max(0.0, _linear_to_srgb(sw.color_linear[2])))
        # glTF ORM convention: R=occlusion, G=roughness, B=metallic (raw/linear)
        orm_px = (1.0, sw.roughness, sw.metallic, 1.0)
        for py in range(row * TILE, row * TILE + TILE):
            for px in range(col * TILE, col * TILE + TILE):
                i = (py * width + px) * 4
                base_buf[i] = r
                base_buf[i + 1] = g
                base_buf[i + 2] = b
                base_buf[i + 3] = 1.0
                orm_buf[i] = orm_px[0]
                orm_buf[i + 1] = orm_px[1]
                orm_buf[i + 2] = orm_px[2]
                orm_buf[i + 3] = orm_px[3]

    base.pixels.foreach_set(base_buf)
    orm.pixels.foreach_set(orm_buf)
    base.pack()
    orm.pack()
    return base, orm


def _build_merged_material(name, base_img, orm_img):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()

    out = tree.nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (300, 0)
    tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    base_tex = tree.nodes.new("ShaderNodeTexImage")
    base_tex.image = base_img
    base_tex.interpolation = "Closest"
    base_tex.location = (-300, 200)
    tree.links.new(base_tex.outputs["Color"], bsdf.inputs["Base Color"])

    orm_tex = tree.nodes.new("ShaderNodeTexImage")
    orm_tex.image = orm_img
    orm_tex.interpolation = "Closest"
    orm_tex.location = (-300, -150)
    sep = tree.nodes.new("ShaderNodeSeparateColor")
    sep.location = (0, -150)
    tree.links.new(orm_tex.outputs["Color"], sep.inputs["Color"])
    tree.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    tree.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])

    return mat


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------


class OBJECT_OT_merge_materials(bpy.types.Operator):
    bl_idname = "object.merge_materials"
    bl_label = "Merge Flat Materials"
    bl_description = (
        "Merge all flat-color materials on the selected objects into a single "
        "palette-backed material to cut draw calls. Textured, emissive and "
        "transparent materials are left untouched"
    )
    bl_options = {"REGISTER", "UNDO"}

    scope_selected: bpy.props.BoolProperty(
        name="Only Selected Objects",
        description="Merge materials only on selected objects (otherwise all mesh objects)",
        default=True,
    )

    merged_name: bpy.props.StringProperty(
        name="Merged Material Name",
        description="Name for the new combined material",
        default="Merged_Atlas",
    )

    cleanup_slots: bpy.props.BoolProperty(
        name="Remove Unused Slots",
        description="Remove leftover empty material slots after merging",
        default=True,
    )

    def execute(self, context):
        if context.mode != "OBJECT":
            try:
                bpy.ops.object.mode_set(mode="OBJECT")
            except Exception:
                pass

        objects = [
            o
            for o in (context.selected_objects if self.scope_selected else bpy.data.objects)
            if o.type == "MESH" and o.data is not None
        ]
        if not objects:
            self.report({"ERROR"}, "No mesh objects to process")
            return {"CANCELLED"}

        # 1) Classify every material used on these objects.
        table = _SwatchTable()
        mat_to_swatch = {}  # material name -> _Swatch
        left_alone = {}  # reason -> count
        for obj in objects:
            for slot in obj.material_slots:
                mat = slot.material
                if mat is None or mat.name in mat_to_swatch or mat.name in left_alone:
                    continue
                analysis = analyze_material(mat)
                if analysis.flat:
                    mat_to_swatch[mat.name] = table.get_or_add(
                        analysis.color_linear, analysis.roughness, analysis.metallic
                    )
                else:
                    left_alone[mat.name] = analysis.reason

        flat_material_count = len(mat_to_swatch)
        if flat_material_count < 2:
            self.report(
                {"WARNING"},
                f"Need at least 2 flat-color materials to merge (found {flat_material_count})",
            )
            return {"CANCELLED"}

        # 2) Build palette images + one merged material.
        base_img, orm_img = _build_palette_images(table.swatches, self.merged_name)
        merged_mat = _build_merged_material(self.merged_name, base_img, orm_img)
        cols, rows = _grid_dims(len(table))

        # 3) Re-point faces + collapse their UVs onto the swatch centre.
        affected_objects = 0
        for obj in objects:
            mesh = obj.data

            # slot index -> swatch (only for flat slots on this object)
            slot_swatch = {}
            for si, slot in enumerate(obj.material_slots):
                mat = slot.material
                if mat is not None and mat.name in mat_to_swatch:
                    slot_swatch[si] = mat_to_swatch[mat.name]
            if not slot_swatch:
                continue

            uv_layer = mesh.uv_layers.active
            if uv_layer is None:
                uv_layer = mesh.uv_layers.new(name="UVMap")
            uv_data = uv_layer.data

            # Add the merged material as a single slot on this object (reusing it
            # if somehow already present), then point every flat face at that one
            # slot. This leaves the old flat slots unreferenced so the cleanup
            # below can drop them; textured slots keep their faces and survive.
            merged_idx = None
            for si, slot in enumerate(obj.material_slots):
                if slot.material is merged_mat:
                    merged_idx = si
                    break
            if merged_idx is None:
                mesh.materials.append(merged_mat)
                merged_idx = len(obj.material_slots) - 1

            for poly in mesh.polygons:
                sw = slot_swatch.get(poly.material_index)
                if sw is None:
                    continue
                u, v = _swatch_uv_center(sw.index, cols, rows)
                for li in poly.loop_indices:
                    uv_data[li].uv = (u, v)
                poly.material_index = merged_idx

            mesh.update()
            affected_objects += 1

            if self.cleanup_slots:
                prev_active = context.view_layer.objects.active
                context.view_layer.objects.active = obj
                try:
                    bpy.ops.object.material_slot_remove_unused()
                except Exception:
                    pass
                finally:
                    context.view_layer.objects.active = prev_active

        leftover = len(left_alone)
        msg = (
            f"Merged {flat_material_count} flat materials into '{merged_mat.name}' "
            f"({len(table)} swatches) across {affected_objects} object(s)."
        )
        if leftover:
            msg += f" Left {leftover} textured/special material(s) untouched."
        self.report({"INFO"}, msg)
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "merged_name")
        layout.prop(self, "scope_selected")
        layout.prop(self, "cleanup_slots")
        box = layout.box()
        box.scale_y = 0.8
        box.label(text="Flat colors are merged into one palette material.", icon="INFO")
        box.label(text="Textured / emissive / transparent stay separate.")
