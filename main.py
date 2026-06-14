#!/usr/bin/env python3
import os
import sys
import io
import requests
import psycopg2
import boto3
from botocore.config import Config
from PIL import Image
from dotenv import load_dotenv
import warnings

# Suppress Pillow deprecation warnings for getdata compatibility
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Load env variables from parent directory if present, or current directory
# Since this script runs from fix_r2_image_python, we search both ../.env and .env
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_env = os.path.join(script_dir, "../.env")
local_env = os.path.join(script_dir, ".env")

if os.path.exists(parent_env):
    load_dotenv(dotenv_path=parent_env)
elif os.path.exists(local_env):
    load_dotenv(dotenv_path=local_env)
else:
    load_dotenv() # fall back to default behavior

# ─── CONFIG ──────────────────────────────────────────────────────────────────
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET = os.getenv("R2_BUCKET_NAME")
DATABASE_URL = os.getenv("DATABASE_URL")

# Placeholder configuration
R2_PUBLIC_BASE_URL = os.getenv("R2_PUBLIC_BASE_URL", "").rstrip("/")
PLACEHOLDER_NAME = os.getenv("PLACEHOLDER_NAME", "placeholder.jpg")

# The URL that will be set in the database for placeholder images
DATABASE_PLACE_HOLDER_URL = f"{R2_PUBLIC_BASE_URL}/{PLACEHOLDER_NAME}"

# Check command line argument for dry run, default to False (matching DRY_RUN = false in TS)
# We support '--dry-run' CLI argument to override
DRY_RUN = True
if "--dry-run" in sys.argv:
    DRY_RUN = True

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Detection thresholds (% of total pixels)
NAVY_THRESHOLD = 20  # min % of dark navy-blue pixels (silhouette)
LIGHT_BLUE_THRESHOLD = 20  # min % of light-blue pixels (background)
# ─────────────────────────────────────────────────────────────────────────────

# Validate environment variables early
if not all([R2_ACCOUNT_ID, R2_ACCESS_KEY, R2_SECRET_KEY, R2_BUCKET, R2_PUBLIC_BASE_URL]):
    print(
        "❌ Missing required env vars. Check R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME, R2_PUBLIC_BASE_URL in your .env",
        file=sys.stderr
    )
    sys.exit(1)

# ─── R2 CLIENT ───────────────────────────────────────────────────────────────
s3_client = boto3.client(
    "s3",
    endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=R2_ACCESS_KEY,
    aws_secret_access_key=R2_SECRET_KEY,
    config=Config(signature_version="s3v4"),
    region_name="auto"
)

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def is_placeholder(image_bytes: bytes) -> bool:
    """Return True if the image matches the placeholder color signature."""
    try:
        # Load image with PIL and convert to RGB to strip alpha (matching Jimp.rgba(false))
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
        img = img.resize((150, 150)) # match sharp/jimp's 150x150 thumbnail

        width, height = img.size
        total = width * height
        navy_count = 0
        light_blue_count = 0

        # Iterate over RGB pixels
        pixels = img.getdata()
        for r, g, b in pixels:
            # Navy blue: low R, low G, higher B (the silhouette)
            if r < 80 and g < 80 and b > 80:
                navy_count += 1
            
            # Light blue: high RGB but B dominant (the background)
            if r > 180 and g > 190 and b > 210 and b > r and b > g:
                light_blue_count += 1

        navy_pct = (navy_count / total) * 100
        light_blue_pct = (light_blue_count / total) * 100

        return navy_pct >= NAVY_THRESHOLD and light_blue_pct >= LIGHT_BLUE_THRESHOLD
    except Exception as err:
        print(f"    [WARN] Could not process image: {err}", file=sys.stderr)
        return False

def build_public_url(key: str) -> str:
    """Helper: build public URL for a given object key."""
    return f"{R2_PUBLIC_BASE_URL}/{key}"

def list_all_images():
    """Yield all image keys in the bucket (no prefix — flat bucket)."""
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
                yield key

        if response.get("IsTruncated"):
            continuation_token = response.get("NextContinuationToken")
        else:
            break

def import_placeholder_image(key: str = "placeholder.jpg") -> str:
    """Import a placeholder image from a URL and upload it to R2."""
    placeholder_url = os.getenv("PLACEHOLDER_IMAGE_URL")
    if not placeholder_url:
        raise ValueError("PLACEHOLDER_IMAGE_URL environment variable must be set")

    resp = requests.get(placeholder_url)
    if not resp.ok:
        raise RuntimeError(f"Failed to fetch placeholder image: {resp.status_code} {resp.reason}")

    content_type = resp.headers.get("content-type") or "application/octet-stream"

    s3_client.put_object(
        Bucket=R2_BUCKET,
        Key=key,
        Body=resp.content,
        ContentType=content_type
    )

    return f"{R2_PUBLIC_BASE_URL}/{key}"

def set_placeholder_image() -> str:
    """Set placeholder image based on PLACEHOLDER_NAME env var."""
    # Build the public URL for the expected placeholder location
    public_url = DATABASE_PLACE_HOLDER_URL

    # Try a HEAD request to see if the object already exists publicly
    try:
        head_resp = requests.head(public_url)
        if head_resp.ok:
            print(f"Existing placeholder found: {public_url}")
            return public_url
    except Exception as err:
        print(f"Placeholder existence check failed: {err}", file=sys.stderr)

    # If the placeholder is not present, upload it
    uploaded_url = import_placeholder_image(PLACEHOLDER_NAME)
    print(f"New placeholder uploaded: {uploaded_url}")
    return uploaded_url

# ─── MAIN ────────────────────────────────────────────────────────────────────
def main():
    print(f"Scanning bucket : {R2_BUCKET}")
    print(f"Credentials     : Access Key ID: {R2_ACCESS_KEY[:4]}... / Secret Access Key: {'*' * 8}")
    print(f"Mode            : {'DRY RUN (no deletions)' if DRY_RUN else '⚠️  LIVE — will delete!'}\n")

    total = 0
    placeholders = []
    errors = []

    # Setup database connection
    conn = None
    if DATABASE_URL:
        try:
            conn = psycopg2.connect(DATABASE_URL)
            print("[db] Connected to PostgreSQL database successfully.")
        except Exception as err:
            print(f"[db] Warning: Failed to connect to database: {err}. Proceeding without database updates.", file=sys.stderr)
    else:
        print("[db] Warning: DATABASE_URL is not set. Proceeding without database updates.", file=sys.stderr)

    try:
        for key in list_all_images():
            total += 1
            try:
                # Get image from R2
                response = s3_client.get_object(Bucket=R2_BUCKET, Key=key)
                buffer = response["Body"].read()
                
                placeholder = is_placeholder(buffer)

                if placeholder:
                    placeholders.append(key)
                    print(f"[📦  PLACEHOLDER] {key}")
                    
                    # Extract NPI from filename (remove extension)
                    npi = os.path.splitext(key)[0]
                    # Use the placeholder image URL from the environment for DB updates
                    placeholder_url = DATABASE_PLACE_HOLDER_URL

                    # Update database if connected
                    if conn:
                        try:
                            with conn.cursor() as cur:
                                cur.execute(
                                    "UPDATE doctors SET image_url = %s WHERE npi = %s",
                                    (placeholder_url, npi)
                                )
                            conn.commit()
                            print(f"[db] image_url updated for NPI {npi} with placeholder URL")
                        except Exception as db_err:
                            print(f"[db] failed to update image_url for NPI {npi}: {db_err}", file=sys.stderr)
                            try:
                                conn.rollback()
                            except Exception:
                                pass

                    # Delete placeholder image from R2 (unless dry run)
                    if not DRY_RUN:
                        try:
                            s3_client.delete_object(Bucket=R2_BUCKET, Key=key)
                            print(f"[r2] deleted placeholder for NPI {npi}")
                        except Exception as del_err:
                            print(f"[r2] failed to delete placeholder for NPI {npi}: {del_err}", file=sys.stderr)
                    else:
                        print(f"[r2] DRY RUN – not deleting placeholder for NPI {npi}")
                else:
                    print(f"[🖼️ REAL] {key}")
            except Exception as err:
                errors.append({"key": key, "error": str(err)})
                print(f"  [ERROR]       {key} — {err}", file=sys.stderr)
    finally:
        if conn:
            conn.close()

    print(f"\n{'─' * 60}")
    print(f"Total scanned : {total}")
    print(f"Placeholders  : {len(placeholders)}")
    print(f"Errors        : {len(errors)}")

    if len(placeholders) == 0:
        print("\nNo placeholders found. Nothing to delete.")
        return

    if DRY_RUN:
        print("\nDRY RUN — the following would be deleted:")
        for key in placeholders:
            print(f"  {key}")
        print("\nSet DRY_RUN = false to actually delete them.")
    else:
        # Note: The original TS script had a final loop to delete the placeholders.
        # Although they were already deleted during the scan loop, we replicate it here
        # with try-except to ensure exact logic equivalence while gracefully handling 
        # any already-deleted files.
        print(f"\nDeleting {len(placeholders)} placeholder(s)...")
        deleted = 0
        for key in placeholders:
            try:
                s3_client.delete_object(Bucket=R2_BUCKET, Key=key)
                print(f"  ✓ Deleted: {key}")
                deleted += 1
            except Exception as err:
                print(f"  ✗ Failed to delete {key}: {err}", file=sys.stderr)
        print(f"\nDone. {deleted}/{len(placeholders)} deleted.")

if __name__ == "__main__":
    if "--set-placeholder" in sys.argv:
        try:
            set_placeholder_image()
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            main()
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
