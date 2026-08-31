"""
upload_landing.py
─────────────────
Uploads static files from the local `data/landing` folder to MinIO.
This ensures PySpark can read these raw files directly from the S3 API.
"""

from pathlib import Path
from etl.minio_client import upload_file

LANDING_DIR = Path("data/landing")

def main():
    if not LANDING_DIR.exists():
        print(f"Directory {LANDING_DIR} does not exist. Nothing to upload.")
        return

    # Upload all files in data/landing to MinIO under landing/
    count = 0
    for file_path in LANDING_DIR.rglob("*"):
        if file_path.is_file():
            # Create the object key by preserving the relative path
            relative_path = file_path.relative_to(LANDING_DIR)
            object_key = f"landing/{relative_path.as_posix()}"
            
            upload_file(local_path=file_path, object_key=object_key)
            count += 1
            
    print(f"\nUploaded {count} files from landing zone to MinIO.")

if __name__ == "__main__":
    main()
