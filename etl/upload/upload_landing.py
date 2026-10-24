"""
upload_landing.py
─────────────────
Uploads raw data files from the local `data/raw/current_season/` directory
directly to MinIO under the `Landing Zone/current_season/` prefix as Parquet.

Behavior:
  - Scans `data/raw/current_season/` recursively.
  - Converts CSV files to snappy-compressed Parquet in-memory and uploads
    them as .parquet files.
  - If any file is already a .parquet file, uploads it directly as-is.
  - Ignores hidden files and markers like `.gitkeep`.
"""

import io
import os
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from etl.shared.minio_client import upload_bytes, upload_file

# Local directory containing raw current season files
CURRENT_SEASON_DIR = Path(os.getenv("CURRENT_SEASON_DIR", "data/raw/current_season"))

# Destination prefix in MinIO Landing Zone
LANDING_PREFIX = os.getenv("MINIO_LANDING_PREFIX", "Landing Zone/current_season")


def _convert_csv_to_parquet_bytes(file_path: Path) -> tuple[io.BytesIO, int]:
    """Reads a CSV file and converts it into an in-memory Snappy Parquet buffer."""
    df = pd.read_csv(file_path)
    table = pa.Table.from_pandas(df, preserve_index=False)
    buf = io.BytesIO()
    pq.write_table(table, buf, compression="snappy")
    buf.seek(0)
    return buf, len(df)


def main() -> None:
    if not CURRENT_SEASON_DIR.exists():
        print(f"[WARN] Directory '{CURRENT_SEASON_DIR}' does not exist. Nothing to upload.")
        return

    # Find all data files, excluding hidden files and .gitkeep
    files_to_upload = [
        f for f in CURRENT_SEASON_DIR.rglob("*")
        if f.is_file() and not f.name.startswith(".")
    ]

    if not files_to_upload:
        print(f"[INFO] No data files found in '{CURRENT_SEASON_DIR}'. Nothing to upload.")
        return

    print(
        f"[INFO] Found {len(files_to_upload)} file(s) in '{CURRENT_SEASON_DIR}' "
        f"to upload to MinIO under '{LANDING_PREFIX}/'."
    )

    count_uploaded = 0
    count_errors = 0

    for file_path in files_to_upload:
        relative_path = file_path.relative_to(CURRENT_SEASON_DIR)
        suffix = file_path.suffix.lower()

        try:
            if suffix == ".csv":
                parquet_dest_path = relative_path.with_suffix(".parquet").as_posix()
                object_key = f"{LANDING_PREFIX}/{parquet_dest_path}"
                print(f"\n[>>] Converting CSV -> Parquet: {relative_path.as_posix()}")
                buf, row_count = _convert_csv_to_parquet_bytes(file_path)
                print(f"     Rows: {row_count:,} | Target: {object_key}")
                upload_bytes(data=buf, object_key=object_key)
                count_uploaded += 1

            elif suffix == ".parquet":
                object_key = f"{LANDING_PREFIX}/{relative_path.as_posix()}"
                print(f"\n[>>] Uploading existing Parquet: {relative_path.as_posix()} -> {object_key}")
                upload_file(local_path=file_path, object_key=object_key)
                count_uploaded += 1

            else:
                print(f"[SKIP] Unsupported file format '{file_path.name}' (expected .csv or .parquet)")

        except Exception as exc:
            print(f"[ERR] Failed to process '{file_path}': {exc}")
            count_errors += 1

    print(
        f"\n[DONE] Successfully uploaded {count_uploaded} file(s) to 's3://.../{LANDING_PREFIX}/'."
        + (f" ({count_errors} error(s))" if count_errors else "")
    )


if __name__ == "__main__":
    main()
