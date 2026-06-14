import sys
import os
from PIL import Image

image_path = sys.argv[1]
if not image_path:
    print("Please provide an image path")
    sys.exit(1)

# List of filters to test
filters = {
    "LANCZOS": Image.Resampling.LANCZOS,
    "BICUBIC": Image.Resampling.BICUBIC,
    "BILINEAR": Image.Resampling.BILINEAR,
    "BOX": Image.Resampling.BOX,
    "NEAREST": Image.Resampling.NEAREST,
    "HAMMING": Image.Resampling.HAMMING
}

print(f"PILLOW RESULTS for {image_path}:")

for filter_name, filter_val in filters.items():
    img = Image.open(image_path)
    img = img.convert("RGB")
    img = img.resize((150, 150), filter_val)
    
    total = img.width * img.height
    navy_count = 0
    light_blue_count = 0
    
    pixels = img.getdata()
    for r, g, b in pixels:
        if r < 80 and g < 80 and b > 80:
            navy_count += 1
        if r > 180 and g > 190 and b > 210 and b > r and b > g:
            light_blue_count += 1
            
    navy_pct = (navy_count / total) * 100
    light_blue_pct = (light_blue_count / total) * 100
    is_placeholder = navy_pct >= 20 and light_blue_pct >= 20
    
    print(f"Filter: {filter_name:<10} | Navy: {navy_count} ({navy_pct:.2f}%) | L-Blue: {light_blue_count} ({light_blue_pct:.2f}%) | Placeholder: {is_placeholder}")
