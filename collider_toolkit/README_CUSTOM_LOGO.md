# Adding Custom Logo to Blender Add-on

## Method 1: Convert SVG to PNG (Recommended)

1. **Install cairosvg**:
   ```bash
   pip install cairosvg
   ```

2. **Run the conversion script**:
   ```bash
   python convert_logo.py
   ```

3. **Use the PNG in your add-on**:
   The script will create `assets/dcl-logo-mono.png` which can be used directly.

## Method 2: Manual Conversion

1. **Open your SVG** in a graphics editor (Inkscape, GIMP, etc.)
2. **Export as PNG** with dimensions 32x32 or 64x64 pixels
3. **Save as** `assets/dcl-logo-mono.png`

## Method 3: Use Blender's Icon System

For advanced users, you can register custom icons in Blender:

```python
import bpy
from bpy.utils import register_icon, unregister_icon

# Register custom icon
icon_id = register_icon("DCL_LOGO", "path/to/your/icon.png")

# Use in UI
row.label(text="", icon="DCL_LOGO")
```

## Method 4: Embed Icon as Base64

For a completely self-contained add-on:

```python
import base64
import io
from PIL import Image

# Convert your logo to base64 and embed it
LOGO_BASE64 = "iVBORw0KGgoAAAANSUhEUgAA..."  # Your logo as base64

def get_embedded_logo():
    logo_data = base64.b64decode(LOGO_BASE64)
    return logo_data
```

## Current Implementation

The add-on currently uses the `WORLD` icon as the closest match to the Decentraland logo. To use your actual logo:

1. Convert your SVG to PNG (32x32 or 64x64 pixels)
2. Replace the `load_custom_icon()` function to load your PNG
3. Register it as a custom Blender icon

## File Structure

```
collider_toolkit/
├── __init__.py
├── assets/
│   ├── dcl-logo-mono.svg    # Original SVG
│   └── dcl-logo-mono.png    # Converted PNG (after running convert_logo.py)
├── convert_logo.py          # Conversion script
└── README_CUSTOM_LOGO.md    # This guide
```
