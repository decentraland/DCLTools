# Decentraland Blender Tools

A comprehensive Blender add-on for Decentraland scene and wearable creation. Provides tools for scene setup, material management, texture optimization, avatar development, collider workflow, and more.

Compatible with **Blender 2.80 through 5.0+**.

---

## Installation

1. Download the `DCLBlender_toolkit.zip` file from the [Releases](https://github.com/decentraland/DCLTools/releases) page
2. In Blender: **Edit > Preferences > Add-ons > Install...**
3. Select the `DCLBlender_toolkit.zip` file
4. Enable **"Decentraland Tools"** in the add-ons list
5. Open the panel in **3D Viewport > Sidebar (N) > Decentraland Tools**

---

## Features

### Scene Creation

| Tool | Description |
|------|-------------|
| **Create Parcels** | Generate a parcel grid with customizable X/Y dimensions (16m per parcel, Decentraland standard) |
| **Scene Limitations Calculator** | Analyze current scene usage against Decentraland limits (triangles, entities, bodies, materials, textures, height) |
| **Scene Validator (Pre-flight)** | One-click pre-flight check: validates triangle count, entities, bodies, materials, textures, height, non-applied transforms, missing materials, and non-power-of-two textures against DCL limits with green/yellow/red status |

### Export

| Tool | Description |
|------|-------------|
| **Export Lights (Experimental)** | Export lights from a collection to a JSON file formatted for the Decentraland SDK (position, color, intensity, range) |
| **Quick Export glTF (.glb)** | One-click glTF/GLB export with DCL-optimized defaults: binary format, apply modifiers, no cameras/lights, output next to the .blend file. Reports file size after export |

### Avatars

| Tool | Description |
|------|-------------|
| **Avatar Shapes** | Import editable Decentraland avatar base meshes (Shape A, Shape B, or both) for wearable development |
| **Avatar Limitations Calculator** | Check selected objects against wearable triangle/material/texture limits per category (upper body, hat, helmet, etc.) |

### Converter

| Tool | Description |
|------|-------------|
| **Particle to Armature** | Convert particle systems into armature-driven animations for Decentraland compatibility |

### Materials & Textures

| Tool | Description |
|------|-------------|
| **Replace Materials** | Replace one or more materials with another across the scene. Supports multi-source selection with search, and scope to selected objects |
| **Clean Unused Materials** | Remove unused material slots from objects (slots not referenced by any face) and/or globally orphan materials with zero users. Supports selected-only scope and fake-user handling |
| **Resize Textures** | Batch resize textures to target resolutions (64 - 1024px) with optional backup. Works on selected objects or all textures |
| **Validate Textures** | Check all textures for glTF/DCL compatibility: non-power-of-two dimensions, oversized textures, non-square textures, and unsupported formats. Configurable max size threshold |
| **Enable Backface Culling** | Enable backface culling on all materials in the scene |

### CleanUp

| Tool | Description |
|------|-------------|
| **Remove Empty Objects** | Remove empty objects, meshes with no geometry, or meshes without materials |
| **Apply Transforms** | Apply location, rotation, and scale transforms to selected or all objects |
| **Rename Mesh Data to Object Name** | Sync mesh data block names with their parent object names |
| **Rename Textures by Material** | Automatically rename textures based on their material node usage (baseColor, hrm, normal, emissive) |
| **Batch Rename Objects** | Rename multiple selected objects with three modes: Add Prefix, Add Suffix, or Find & Replace |

### LOD Generator

| Tool | Description |
|------|-------------|
| **Generate LODs** | Create Level of Detail copies of selected meshes using decimation. Configurable LOD levels (1-4) with per-level ratio sliders displayed directly in the panel. Defaults: LOD 1 at 50%, LOD 2 at 15%, LOD 3 at 5%. Optionally places LODs in a dedicated collection |

### Viewer

| Tool | Description |
|------|-------------|
| **Toggle Display Mode** | Switch viewport display for objects between Bounds, Wire, Textured, and Solid |

### Collider Management

| Tool | Description |
|------|-------------|
| **Add _collider Suffix** | Rename selected objects to append the `_collider` suffix |
| **Remove UVs from Colliders** | Strip UV mapping data from all objects containing `_collider` in their name |
| **Strip Materials from Colliders** | Remove all material slots from collider objects |
| **Simplify Colliders** | Apply decimation to reduce polygon count on collider meshes with adjustable ratio |

### Documentation

| Tool | Description |
|------|-------------|
| **Open Documentation** | Links to Decentraland creator documentation |
| **Scene Limits Guide** | Links to the official scene limitations reference |
| **Asset Guidelines** | Links to 3D asset optimization guidelines |

---

## UI Overview

The panel is organized into collapsible sections in the **3D Viewport Sidebar (N key)**. Each section can be expanded or collapsed to keep the workspace clean.

Every tool supports:
- **Undo** (Ctrl+Z) for all operations
- **Scope selection** - apply to selected objects or the entire scene
- **Dialog options** - configurable parameters before execution
- **Status feedback** - results reported in the Blender info bar

---

## Version

Current version: **1.1.0**
Compatible with Blender 2.80 - 5.0+
