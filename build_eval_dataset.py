#!/usr/bin/env python3
import os
import sys
import io
import random
import hashlib
import requests
import boto3
from botocore.config import Config
from PIL import Image
from dotenv import load_dotenv
import warnings

# Suppress Pillow deprecation warnings for getdata compatibility
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Load env variables from parent directory if present, or current directory
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_env = os.path.join(script_dir, "../.env")
local_env = os.path.join(script_dir, ".env")

if os.path.exists(parent_env):
    load_dotenv(dotenv_path=parent_env)
elif os.path.exists(local_env):
    load_dotenv(dotenv_path=local_env)
else:
    load_dotenv()

# ─── CONFIGURATION ──────────────────────────────────────────────────────────
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET = os.getenv("R2_BUCKET_NAME")

# Allow sample size to be configured via command line argument, default to 100
SAMPLE_SIZE = 100
for arg in sys.argv:
    if arg.startswith("--sample-size="):
        try:
            SAMPLE_SIZE = int(arg.split("=")[1])
        except ValueError:
            pass

OUTPUT_BASE = "./eval"
# We can allow output base folder to be configured via CLI as well
for arg in sys.argv:
    if arg.startswith("--output="):
        OUTPUT_BASE = arg.split("=")[1]

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Detection thresholds (must match your remover script)
NAVY_THRESHOLD = 20
LIGHT_BLUE_THRESHOLD = 20
# ─────────────────────────────────────────────────────────────────────────────

# Validate environment variables early
if not all([R2_ACCOUNT_ID, R2_ACCESS_KEY, R2_SECRET_KEY, R2_BUCKET]):
    print(
        "❌ Missing required env vars. Set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME",
        file=sys.stderr
    )
    sys.exit(1)

# ─── R2 CLIENT ──────────────────────────────────────────────────────────────
s3_client = boto3.client(
    "s3",
    endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=R2_ACCESS_KEY,
    aws_secret_access_key=R2_SECRET_KEY,
    config=Config(signature_version="s3v4"),
    region_name="auto"
)

# ─── HELPER FUNCTIONS ────────────────────────────────────────────────────────

def is_placeholder(image_bytes: bytes) -> bool:
    """Return True if the image matches the placeholder color signature."""
    try:
        # Load with PIL, convert to RGB to strip alpha, and resize to 150×150
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
        img = img.resize((150, 150))

        width, height = img.size
        total = width * height
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
        return navy_pct >= NAVY_THRESHOLD and light_blue_pct >= LIGHT_BLUE_THRESHOLD
    except Exception as err:
        print(f"    Detection error: {err}", file=sys.stderr)
        return False

def get_all_image_keys() -> list[str]:
    """Retrieve all image keys in the bucket (no prefix — flat bucket)."""
    keys = []
    continuation_token = None
    while True:
        kwargs = {"Bucket": R2_BUCKET}
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token

        response = s3_client.list_objects_v2(**kwargs)
        contents = response.get("Contents", [])

        for obj in contents:
            key = obj.get("Key")
            if not key:
                continue
            ext = os.path.splitext(key)[1].lower() if "." in key else ""
            if ext in IMAGE_EXTENSIONS:
                keys.append(key)

        if response.get("IsTruncated"):
            continuation_token = response.get("NextContinuationToken")
        else:
            break
            
    return keys

def safe_filename(key: str) -> str:
    """Replace slashes and other problematic characters to avoid subdirectory creation."""
    base = os.path.basename(key)
    name, ext = os.path.splitext(base)
    h = hashlib.md5(key.encode('utf-8')).hexdigest()[:8]
    return f"{name}_{h}{ext}"

def ensure_dir(directory: str):
    """Ensure that a directory exists."""
    os.makedirs(directory, exist_ok=True)

# ─── DOWNLOAD AND SORT ───────────────────────────────────────────────────────
def build_dataset():
    print(f"🔍 Scanning bucket: {R2_BUCKET}")
    all_keys = get_all_image_keys()
    print(f"📸 Found {len(all_keys)} images.")

    # Select random sample
    sample_size = min(SAMPLE_SIZE, len(all_keys))
    sample_keys = random.sample(all_keys, sample_size)
    print(f"🎲 Selected {len(sample_keys)} random images for evaluation.\n")

    placeholder_dir = os.path.join(OUTPUT_BASE, "placeholder")
    real_dir = os.path.join(OUTPUT_BASE, "real")
    ensure_dir(placeholder_dir)
    ensure_dir(real_dir)

    success = 0
    errors = 0

    for i, key in enumerate(sample_keys):
        # Print progress without newline to match JS's process.stdout.write
        sys.stdout.write(f"[{i + 1}/{len(sample_keys)}] {key} ... ")
        sys.stdout.flush()

        try:
            # Get image from R2
            response = s3_client.get_object(Bucket=R2_BUCKET, Key=key)
            buffer = response["Body"].read()

            placeholder = is_placeholder(buffer)
            target_dir = placeholder_dir if placeholder else real_dir
            out_file = os.path.join(target_dir, safe_filename(key))

            # Write file locally
            with open(out_file, "wb") as f:
                f.write(buffer)

            print("📦 PLACEHOLDER" if placeholder else "🖼️ REAL")
            success += 1
        except Exception as err:
            print(f"❌ ERROR: {err}")
            errors += 1

    print(f"\n✅ Done. Successfully processed {success} images, {errors} errors.")
    print(f"\n📁 Evaluation dataset created at: {OUTPUT_BASE}/")
    print(f"   - placeholder/ : images the detector thinks are placeholders")
    print(f"   - real/        : images the detector thinks are normal")
    print(f"\n🔧 MANUAL STEP: Review both folders and move any misclassified files.")
    print(f"   After correction, the folder structure becomes your ground truth.")
    print(f"\n📊 Then run the evaluation script pointing to these folders.")

# ─── MAIN ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        build_dataset()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
