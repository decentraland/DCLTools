# DCLTools - Decentraland Blender Tools

A collection of Blender add-ons designed for Decentraland asset creation and optimization workflows.

## Collider Toolkit

A Blender add-on that provides tools for optimizing collider meshes in Decentraland projects.

### Features

#### UV Cleanup
- **Remove UVs from Colliders**: Removes UV mapping data from objects with `_collider` suffix
- **Strip Materials from Colliders**: Removes all material slots from collider objects

#### Collider Management
- **Add _collider Suffix**: Renames selected objects to add `_collider` suffix
- **Simplify Colliders**: Applies decimation to reduce polygon count on collider objects
- **Cleanup Colliders**: Removes doubles, dissolves degenerate faces, and optimizes mesh geometry

### Installation

1. Download the `collider_toolkit.zip` file
2. In Blender: Edit > Preferences > Add-ons > Install...
3. Select the `collider_toolkit.zip` file
4. Enable "Collider Toolkit" in the add-ons list
5. Find the panel in 3D Viewport > Sidebar (N) > "Collider Toolkit"

### Usage

The add-on provides a clean UI with collapsible sections:
- **UV Cleanup**: Tools for removing unnecessary UV data from collision meshes
- **Collider Management**: Tools for organizing and optimizing collider objects

Each tool includes options for:
- Scope selection (All objects vs Selected only)
- Customizable parameters
- Undo support
- Progress feedback

### Benefits

- **Reduced file size**: Removing UVs and materials from colliders reduces export size
- **Faster loading**: Optimized colliders improve scene load times
- **Cleaner pipeline**: Automated tools for consistent collider naming and optimization
- **Memory optimization**: Reduced RAM usage for collider meshes

### Considerations

- Only use on collision-only meshes
- Always backup files before running tools
- Verify object naming conventions
- Test in your specific game engine before production use

### Version

Current version: 1.0.0
Compatible with Blender 2.80+
