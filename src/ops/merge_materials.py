"""
Merge flat-color materials into a single palette-backed material.

Decentraland creators frequently author one material per color, which produces
one draw call per material for no visual benefit. This tool collapses every
*flat* (untextured) PBR material on the selected objects into ONE material
backed by a tiny palette atlas:

  * BaseColor palette  (sRGB)      - one swatch per unique colour (+ alpha)
  * ORM palette        (Non-Color) - matching roughness / metallic per swatch
  * Emissive palette   (sRGB)      - emission per swatch, black where unused

Each face that used a flat material is re-pointed at the merged material and its
UVs are collapsed onto the centre of its swatch, so the visual result is
identical while the draw-call count drops to one.

Emissive and semi-transparent flat colors are merged too. Transparency cannot
share a material with opaque geometry (glTF alphaMode is per material), so
translucent swatches land on a second "_Blend" material that reuses the very
same palette images - two materials at most, instead of one per color.

Atlas dimensions are always powers of two, which render engines require for
mipmapping and compressed texture formats.

Materials that carry an image texture (BaseColor / Normal / Roughness /
Metallic / Emission / Alpha) are NOT touched - it makes no sense to bake a real
texture into a few-pixel palette. They are left as-is and reported so the
creator knows what stayed separate.

This operator is destructive (it edits meshes in place) and supports Undo.
"""

import math

import bpy

from .collider_utils import is_collider

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
    __slots__ = ("index", "color_linear", "roughness", "metallic", "alpha", "emission_linear")

    def __init__(self, index, color_linear, roughness, metallic, alpha, emission_linear):
        self.index = index
        self.color_linear = color_linear
        self.roughness = roughness
        self.metallic = metallic
        self.alpha = alpha
        self.emission_linear = emission_linear

    @property
    def is_translucent(self):
        return self.alpha < 0.999

    @property
    def is_emissive(self):
        return any(c > 0.0 for c in self.emission_linear)


class _SwatchTable:
    """Deduplicates flat materials into unique swatches across all objects."""

    def __init__(self):
        self._by_key = {}
        self.swatches = []

    def get_or_add(self, color_linear, roughness, metallic, alpha, emission_linear):
        key = (
            tuple(round(c, _COLOR_ROUND) for c in color_linear),
            round(roughness, _SCALAR_ROUND),
            round(metallic, _SCALAR_ROUND),
            round(alpha, _SCALAR_ROUND),
            tuple(round(c, _COLOR_ROUND) for c in emission_linear),
        )
        existing = self._by_key.get(key)
        if existing is not None:
            return existing
        sw = _Swatch(len(self.swatches), color_linear, roughness, metallic, alpha, emission_linear)
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
    __slots__ = ("flat", "reason", "color_linear", "roughness", "metallic", "alpha", "emission_linear")

    def __init__(
        self,
        flat,
        reason="",
        color_linear=None,
        roughness=0.5,
        metallic=0.0,
        alpha=1.0,
        emission_linear=(0.0, 0.0, 0.0),
    ):
        self.flat = flat
        self.reason = reason
        self.color_linear = color_linear
        self.roughness = roughness
        self.metallic = metallic
        self.alpha = alpha
        # Raw colour * strength, NOT clamped to 1 - HDR glow above 1.0 is
        # preserved by normalising the whole palette (see _emission_scale).
        self.emission_linear = emission_linear


def analyze_material(material, merge_emissive=True, merge_transparent=True):
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

    # Transmission (real glass) cannot live in a palette: glTF carries it as a
    # per-material factor, so merging would silently turn glass opaque.
    transmission = _constant_scalar(_socket(principled, "Transmission Weight", "Transmission"), 0.0)
    if transmission is None:
        return _Analysis(False, "textured transmission")
    if transmission > 0.0:
        return _Analysis(False, "uses transmission (glass)")

    # Emission. Colour * strength is kept raw here; the operator normalises the
    # whole palette so values above 1.0 survive as emissive strength.
    emis_col = _socket(principled, "Emission Color", "Emission")
    emis_str = _socket(principled, "Emission Strength")
    emission = (0.0, 0.0, 0.0)
    if emis_col is not None:
        if emis_col.is_linked:
            return _Analysis(False, "textured emission")
        strength = _constant_scalar(emis_str, 0.0) if emis_str is not None else 0.0
        if strength is None:
            return _Analysis(False, "textured emission strength")
        raw = tuple(c * strength for c in emis_col.default_value[:3])
        if any(c > 0.0 for c in raw):
            if not merge_emissive:
                return _Analysis(False, "emissive")
            emission = raw

    # Transparency. Keyed off the real Alpha socket, never blend_method: Blender
    # (4.2+/EEVEE Next, 5.x) defaults that flag to "HASHED" even on fully opaque
    # materials.
    alpha_socket = _socket(principled, "Alpha")
    alpha = 1.0
    if alpha_socket is not None:
        if alpha_socket.is_linked:
            return _Analysis(False, "uses alpha texture")
        alpha = float(alpha_socket.default_value)
        if alpha < 0.999 and not merge_transparent:
            return _Analysis(False, "partial transparency")

    return _Analysis(
        True,
        color_linear=color,
        roughness=roughness,
        metallic=metallic,
        alpha=alpha,
        emission_linear=emission,
    )


# ---------------------------------------------------------------------------
# Palette image + merged material construction
# ---------------------------------------------------------------------------


def _next_pot(n):
    """Smallest power of two >= n."""
    p = 1
    while p < n:
        p *= 2
    return p


def _grid_dims(count):
    """Grid of swatches whose pixel size is a power of two on both axes.

    TILE is itself a power of two, so rounding the column/row counts up to
    powers of two is enough to make cols*TILE x rows*TILE power-of-two - which
    render engines need for mipmapping and compressed texture formats.
    """
    cols = _next_pot(max(1, math.ceil(math.sqrt(count))))
    rows = _next_pot(max(1, math.ceil(count / cols)))
    return cols, rows


def _swatch_uv_center(index, cols, rows):
    col = index % cols
    row = index // cols
    u = (col * TILE + TILE * 0.5) / (cols * TILE)
    v = (row * TILE + TILE * 0.5) / (rows * TILE)
    return (u, v)


def _emission_scale(swatches):
    """Peak emission across swatches, used to normalise the emissive palette.

    An 8-bit texture only holds 0..1, so HDR glow is carried by dividing every
    swatch by the peak and handing the peak to the material's Emission Strength
    (which glTF exports as KHR_materials_emissive_strength). The product is
    unchanged, so bright emitters stay bright.
    """
    peak = 0.0
    for sw in swatches:
        for c in sw.emission_linear:
            peak = max(peak, c)
    return peak if peak > 1.0 else 1.0


def _build_palette_images(swatches, name_prefix, need_alpha, need_emissive, emission_scale=1.0):
    """Build the palette images. Returns (base, orm, emissive_or_None)."""
    cols, rows = _grid_dims(len(swatches))
    width, height = cols * TILE, rows * TILE

    base = bpy.data.images.new(f"{name_prefix}_BaseColor", width=width, height=height, alpha=need_alpha)
    base.colorspace_settings.name = "sRGB"
    orm = bpy.data.images.new(f"{name_prefix}_ORM", width=width, height=height, alpha=False)
    orm.colorspace_settings.name = "Non-Color"
    emis = None
    if need_emissive:
        emis = bpy.data.images.new(f"{name_prefix}_Emissive", width=width, height=height, alpha=False)
        emis.colorspace_settings.name = "sRGB"

    # Tiles past the last swatch are never sampled (UVs land on tile centres and
    # sampling is Closest), but seed them as opaque / unoccluded / unlit anyway so
    # engine-side mipmapping cannot bleed transparency or shadow into real
    # swatches at distance.
    pixel_count = width * height
    base_buf = [0.0, 0.0, 0.0, 1.0] * pixel_count
    orm_buf = [1.0, 0.5, 0.0, 1.0] * pixel_count
    emis_buf = [0.0, 0.0, 0.0, 1.0] * pixel_count if need_emissive else None

    def srgb_clamped(v):
        return min(1.0, max(0.0, _linear_to_srgb(v)))

    for sw in swatches:
        col = sw.index % cols
        row = sw.index // cols
        # sRGB-encode the linear colour so the sRGB texture samples back to the
        # original linear value the BSDF expects.
        base_px = (
            srgb_clamped(sw.color_linear[0]),
            srgb_clamped(sw.color_linear[1]),
            srgb_clamped(sw.color_linear[2]),
            sw.alpha,
        )
        # glTF ORM convention: R=occlusion, G=roughness, B=metallic (raw/linear)
        orm_px = (1.0, sw.roughness, sw.metallic, 1.0)
        emis_px = (
            (
                srgb_clamped(sw.emission_linear[0] / emission_scale),
                srgb_clamped(sw.emission_linear[1] / emission_scale),
                srgb_clamped(sw.emission_linear[2] / emission_scale),
                1.0,
            )
            if need_emissive
            else None
        )
        for py in range(row * TILE, row * TILE + TILE):
            for px in range(col * TILE, col * TILE + TILE):
                i = (py * width + px) * 4
                base_buf[i : i + 4] = base_px
                orm_buf[i : i + 4] = orm_px
                if emis_buf is not None:
                    emis_buf[i : i + 4] = emis_px

    base.pixels.foreach_set(base_buf)
    orm.pixels.foreach_set(orm_buf)
    base.pack()
    orm.pack()
    if emis is not None:
        emis.pixels.foreach_set(emis_buf)
        emis.pack()
    return base, orm, emis


def _ensure_slot(obj, mesh, material):
    """Return the index of the slot holding *material*, appending one if needed."""
    for si, slot in enumerate(obj.material_slots):
        if slot.material is material:
            return si
    mesh.materials.append(material)
    return len(obj.material_slots) - 1


def _set_alpha_mode(material, blended):
    """Drive the exported glTF alphaMode across Blender versions.

    ``blend_method`` is the legacy flag; 4.2+/EEVEE Next added
    ``surface_render_method``. Set whichever exists so the result does not
    depend on which one the active glTF exporter reads.
    """
    if hasattr(material, "blend_method"):
        material.blend_method = "BLEND" if blended else "OPAQUE"
    if hasattr(material, "surface_render_method"):
        material.surface_render_method = "BLENDED" if blended else "DITHERED"


def _build_merged_material(name, base_img, orm_img, emis_img=None, blended=False, emission_scale=1.0):
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

    if emis_img is not None:
        emis_tex = tree.nodes.new("ShaderNodeTexImage")
        emis_tex.image = emis_img
        emis_tex.interpolation = "Closest"
        emis_tex.location = (-300, -500)
        emis_socket = bsdf.inputs.get("Emission Color") or bsdf.inputs.get("Emission")
        if emis_socket is not None:
            tree.links.new(emis_tex.outputs["Color"], emis_socket)
            strength = bsdf.inputs.get("Emission Strength")
            if strength is not None:
                # The palette holds emission normalised to 0..1; this multiplier
                # restores the original brightness and exports as
                # KHR_materials_emissive_strength when above 1.
                strength.default_value = emission_scale

    if blended:
        tree.links.new(base_tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    _set_alpha_mode(mat, blended)

    return mat


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------


class OBJECT_OT_merge_materials(bpy.types.Operator):
    bl_idname = "object.merge_materials"
    bl_label = "Merge Flat Materials"
    bl_description = (
        "Merge all flat-color materials on the selected objects into a single "
        "palette-backed material to cut draw calls, including metallic, "
        "emissive and transparent colors. Textured materials are left untouched"
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

    merge_emissive: bpy.props.BoolProperty(
        name="Include Emissive",
        description=(
            "Merge emissive flat colors too, baking their glow into an emissive "
            "palette. Disable to leave emissive materials separate"
        ),
        default=True,
    )

    merge_transparent: bpy.props.BoolProperty(
        name="Include Transparent",
        description=(
            "Merge semi-transparent flat colors onto a second alpha-blended "
            "material that shares the same palette (glTF alphaMode is per "
            "material, so they cannot share one with opaque geometry)"
        ),
        default=True,
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

        candidates = [
            o
            for o in (context.selected_objects if self.scope_selected else bpy.data.objects)
            if o.type == "MESH" and o.data is not None
        ]
        # Colliders are collision-only geometry that Decentraland never renders,
        # so they have no business in a visual atlas - merging them would just
        # hand them a material they should not have in the first place.
        objects = [o for o in candidates if not is_collider(o)]
        skipped_colliders = len(candidates) - len(objects)
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
                analysis = analyze_material(mat, self.merge_emissive, self.merge_transparent)
                if analysis.flat:
                    mat_to_swatch[mat.name] = table.get_or_add(
                        analysis.color_linear,
                        analysis.roughness,
                        analysis.metallic,
                        analysis.alpha,
                        analysis.emission_linear,
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

        # 2) Build the shared palette, plus one merged material per alpha mode.
        # Both materials sample the very same images, so the only reason a
        # second one exists is glTF's per-material alphaMode.
        need_emissive = any(sw.is_emissive for sw in table.swatches)
        need_alpha = any(sw.is_translucent for sw in table.swatches)
        emis_scale = _emission_scale(table.swatches) if need_emissive else 1.0
        base_img, orm_img, emis_img = _build_palette_images(
            table.swatches, self.merged_name, need_alpha, need_emissive, emis_scale
        )
        merged_mat = _build_merged_material(
            self.merged_name, base_img, orm_img, emis_img, blended=False, emission_scale=emis_scale
        )
        blend_mat = None
        if need_alpha:
            blend_mat = _build_merged_material(
                f"{self.merged_name}_Blend",
                base_img,
                orm_img,
                emis_img,
                blended=True,
                emission_scale=emis_scale,
            )
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

            # Add the merged material(s) as slots on this object (reusing them if
            # somehow already present), then point every flat face at the slot
            # matching its alpha mode. This leaves the old flat slots
            # unreferenced so the cleanup below can drop them; textured slots
            # keep their faces and survive.
            merged_idx = None
            blend_idx = None

            for poly in mesh.polygons:
                sw = slot_swatch.get(poly.material_index)
                if sw is None:
                    continue
                u, v = _swatch_uv_center(sw.index, cols, rows)
                for li in poly.loop_indices:
                    uv_data[li].uv = (u, v)
                if sw.is_translucent and blend_mat is not None:
                    if blend_idx is None:
                        blend_idx = _ensure_slot(obj, mesh, blend_mat)
                    poly.material_index = blend_idx
                else:
                    if merged_idx is None:
                        merged_idx = _ensure_slot(obj, mesh, merged_mat)
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
        target = merged_mat.name if blend_mat is None else f"{merged_mat.name} + {blend_mat.name}"
        atlas_w, atlas_h = cols * TILE, rows * TILE
        msg = (
            f"Merged {flat_material_count} flat materials into '{target}' "
            f"({len(table)} swatches, {atlas_w}x{atlas_h} atlas) across {affected_objects} object(s)."
        )
        if leftover:
            msg += f" Left {leftover} textured/special material(s) untouched."
        if skipped_colliders:
            msg += f" Skipped {skipped_colliders} collider mesh(es)."
        if emis_scale > 1.0:
            msg += f" Emissive strength {emis_scale:.2f}x preserved."
        self.report({"INFO"}, msg)
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "merged_name")
        layout.prop(self, "scope_selected")
        layout.prop(self, "merge_emissive")
        layout.prop(self, "merge_transparent")
        layout.prop(self, "cleanup_slots")
        box = layout.box()
        box.scale_y = 0.8
        box.label(text="Flat colors are merged into one palette material.", icon="INFO")
        box.label(text="Color, roughness, metallic and glow are baked per swatch.")
        box.label(text="Transparent colors get a second, blended material.")
        box.label(text="Textured materials always stay separate.")
        box.label(text="Colliders are skipped - they are never rendered.")
