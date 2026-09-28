"""
upload_landing.py
─────────────────
Stage 1 of the Landing Zone pipeline.

Uploads CSV files from the local `data/landing/` folder to MinIO under the
`landing/temporal/` prefix.  This is the *Temporal Landing Zone* — raw CSVs
exactly as produced by the scrapers / external sources, with no transformation.

The next stage (csv_to_parquet_landing.py) reads from this prefix, converts
every file to Parquet, and writes the result to `landing/persistent/`.
"""

from pathlib import Path
from etl.shared.minio_client import upload_file

# Local directory that contains the raw CSV files
LANDING_DIR = Path("data/landing")

# MinIO prefix for the Temporal Landing Zone
TEMPORAL_PREFIX = "landing/temporal"


def main() -> None:
    if not LANDING_DIR.exists():
        print(f"[WARN] Directory '{LANDING_DIR}' does not exist. Nothing to upload.")
        return

    csv_files = [f for f in LANDING_DIR.rglob("*") if f.is_file() and f.suffix.lower() == ".csv"]

    if not csv_files:
        print(f"[WARN] No CSV files found in '{LANDING_DIR}'. Nothing to upload.")
        return

    print(f"[INFO] Found {len(csv_files)} CSV file(s) to upload to Temporal Landing Zone.")

    count = 0
    for file_path in csv_files:
        relative_path = file_path.relative_to(LANDING_DIR)
        object_key = f"{TEMPORAL_PREFIX}/{relative_path.as_posix()}"
        upload_file(local_path=file_path, object_key=object_key)
        count += 1

    print(f"\n[DONE] Uploaded {count} CSV file(s) to s3://.../{TEMPORAL_PREFIX}/")


if __name__ == "__main__":
    main()
