import os
import subprocess
import json
from PIL import Image

# Directories to check
dirs = ["eval/real", "eval/placeholder"]

mismatches = 0
total = 0

for d in dirs:
    if not os.path.exists(d):
        continue
    for f in os.listdir(d):
        if not f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            continue
        total += 1
        path = os.path.join(d, f)
        
        # 1. Pillow detection
        img = Image.open(path).convert("RGB").resize((150, 150), Image.Resampling.LANCZOS)
        w, h = img.size
        tot = w * h
        navy_count = 0
        light_blue_count = 0
        for r, g, b in img.getdata():
            if r < 80 and g < 80 and b > 80:
                navy_count += 1
            if r > 180 and g > 190 and b > 210 and b > r and b > g:
                light_blue_count += 1
        pillow_navy_pct = (navy_count / tot) * 100
        pillow_lblue_pct = (light_blue_count / tot) * 100
        pillow_is_placeholder = pillow_navy_pct >= 20 and pillow_lblue_pct >= 20
        
        # 2. Sharp detection via compare_sharp.js
        res = subprocess.run(
            ["npx", "tsx", "compare_sharp.js", path],
            capture_output=True,
            text=True
        )
        # Parse output of compare_sharp.js
        sharp_lines = res.stdout.splitlines()
        sharp_is_placeholder = False
        sharp_navy_pct = 0.0
        sharp_lblue_pct = 0.0
        for line in sharp_lines:
            if "Is Placeholder:" in line:
                sharp_is_placeholder = "true" in line.lower()
            elif "Navy pixels" in line:
                # e.g., "Navy pixels : 8879 (39.46%)"
                parts = line.split("(")
                if len(parts) > 1:
                    sharp_navy_pct = float(parts[1].replace("%", "").replace(")", "").strip())
            elif "L-Blue pixels" in line:
                parts = line.split("(")
                if len(parts) > 1:
                    sharp_lblue_pct = float(parts[1].replace("%", "").replace(")", "").strip())
                    
        if pillow_is_placeholder != sharp_is_placeholder:
            mismatches += 1
            print(f"MISMATCH for {path}:")
            print(f"  Pillow: Navy={pillow_navy_pct:.2f}%, L-Blue={pillow_lblue_pct:.2f}% | IsPlaceholder={pillow_is_placeholder}")
            print(f"  Sharp : Navy={sharp_navy_pct:.2f}%, L-Blue={sharp_lblue_pct:.2f}% | IsPlaceholder={sharp_is_placeholder}")
            
print(f"Scan complete. Total images checked: {total}. Mismatches: {mismatches}")
