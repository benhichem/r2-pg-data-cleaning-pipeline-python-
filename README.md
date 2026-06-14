# R2 Placeholder Image Remover (Python Migration)

This is a Python 3 migration of the TypeScript R2 Placeholder Image Remover script (`src/scripts/fix_r2_image_url.ts`).

## Functionality

1. **Scans R2 Bucket**: Retrieves all images (`.jpg`, `.jpeg`, `.png`, `.webp`) in the configured Cloudflare R2 bucket.
2. **Detects Placeholders**: Downloads each image and analyzes its pixel colors (using Pillow). It identifies placeholder silhouette images with a dark navy silhouette on a light blue background.
3. **Database Update**: If a placeholder is detected, it updates the doctor's record in the PostgreSQL database.
4. **Deletes Placeholders**: Deletes the detected placeholders from the R2 bucket to save storage.
5. **Set Global Placeholder Utility**: Supports setting a global placeholder image using the `--set-placeholder` flag.

## Requirements

The script requires Python 3.x and the following dependencies:
- `boto3` (AWS SDK for Python, used for R2/S3 API)
- `Pillow` (Image processing)
- `psycopg2-binary` (PostgreSQL client)
- `requests` (HTTP requests)
- `python-dotenv` (Load configuration from `.env`)

## Installation

It is recommended to run the script inside a virtual environment.

```bash
# Navigate to the script folder
cd fix_r2_image_python

# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

The script loads configuration from the `.env` file in the parent project directory. Ensure the following environment variables are set:

```ini
R2_ACCOUNT_ID=your_account_id
R2_ACCESS_KEY_ID=your_access_key_id
R2_SECRET_ACCESS_KEY=your_secret_access_key
R2_BUCKET_NAME=your_bucket_name
R2_PUBLIC_BASE_URL=your_public_base_url (optional, defaults to R2 bucket endpoint)
DATABASE_URL=postgresql://user:password@host:port/database
PLACEHOLDER_NAME=placeholder.jpg (required for --set-placeholder)
PLACEHOLDER_IMAGE_URL=https://example.com/placeholder.jpg (required for --set-placeholder)
```

## Usage

Ensure your virtual environment is active.

### 1. Run in Dry Run Mode (Highly Recommended)
This mode scans the R2 bucket and identifies placeholders without deleting any files from R2 or updating the database.
```bash
python main.py --dry-run
```

### 2. Run in Live Mode
This scans, updates the database, and deletes identified placeholder images from R2.
```bash
python main.py
```

### 3. Upload/Set Global Placeholder Image
This uploads the default placeholder image defined by `PLACEHOLDER_IMAGE_URL` to R2 using the key `PLACEHOLDER_NAME`.
```bash
python main.py --set-placeholder
```

---

# Evaluation Dataset Builder (`build_eval_dataset.py`)

This is a Python 3 migration of the TS script `src/scripts/build_eval_dataset.ts`. It downloads a random sample of images from the R2 bucket, classifies them via the color-signature detector, and sorts them into `eval/placeholder/` or `eval/real/` folders on disk. This facilitates ground-truth verification and testing.

## Usage

### 1. Build Default Dataset (100 sample images)
```bash
python build_eval_dataset.py
```

### 2. Customize Sample Size and Output Path
You can customize the size of the random sample and the folder where the dataset is generated:
```bash
python build_eval_dataset.py --sample-size=50 --output=./custom_eval
```

