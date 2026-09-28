"""
csv_to_parquet_landing.py
─────────────────────────
Stage 2 of the Landing Zone pipeline.

Reads every CSV file from the *Temporal Landing Zone* (`landing/temporal/`)
in MinIO, converts it to Parquet (snappy-compressed), and writes the result
to the *Persistent Landing Zone* (`landing/persistent/`) in the same bucket.

No column transformations are applied — the schema is inferred by pandas and
preserved as-is.  The goal is simply to have an efficient, columnar format
available for downstream PySpark / DuckDB jobs.

Prerequisites
─────────────
    pip install pandas pyarrow boto3 python-dotenv
"""

import io
import os
from pathlib import PurePosixPath

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from etl.shared.minio_client import get_client, list_objects

# ── MinIO prefixes ────────────────────────────────────────────────────────────
TEMPORAL_PREFIX   = "landing/temporal"
PERSISTENT_PREFIX = "landing/persistent"

# ── Bucket (falls back to the same default as minio_client) ──────────────────
_BUCKET = os.getenv("MINIO_BUCKET", "xvalue-data")


def _read_csv_from_minio(client, object_key: str) -> pd.DataFrame:
    """Download a CSV object from MinIO and return it as a DataFrame."""
    response = client.get_object(Bucket=_BUCKET, Key=object_key)
    raw_bytes = response["Body"].read()
    return pd.read_csv(io.BytesIO(raw_bytes))


def _write_parquet_to_minio(client, df: pd.DataFrame, object_key: str) -> None:
    """Convert a DataFrame to Parquet (snappy) and upload it to MinIO."""
    table = pa.Table.from_pandas(df, preserve_index=False)
    buf = io.BytesIO()
    pq.write_table(table, buf, compression="snappy")
    buf.seek(0)
    client.put_object(
        Bucket=_BUCKET,
        Key=object_key,
        Body=buf,
        ContentLength=buf.getbuffer().nbytes,
        ContentType="application/octet-stream",
    )


def main() -> None:
    client = get_client()

    # List all objects in the Temporal Landing Zone
    temporal_keys = list_objects(prefix=TEMPORAL_PREFIX)
    csv_keys = [k for k in temporal_keys if k.lower().endswith(".csv")]

    if not csv_keys:
        print(f"[WARN] No CSV files found under '{TEMPORAL_PREFIX}/'. Nothing to convert.")
        return

    print(f"[INFO] Found {len(csv_keys)} CSV file(s) in Temporal Landing Zone.")

    converted = 0
    errors = 0

    for object_key in csv_keys:
        # Build the destination key: swap the prefix and change extension to .parquet
        relative = PurePosixPath(object_key).relative_to(TEMPORAL_PREFIX)
        dest_key = f"{PERSISTENT_PREFIX}/{relative.with_suffix('.parquet').as_posix()}"

        try:
            print(f"  [>>] {object_key}")
            df = _read_csv_from_minio(client, object_key)
            _write_parquet_to_minio(client, df, dest_key)
            print(f"  [OK] -> {dest_key}  ({len(df):,} rows)")
            converted += 1
        except Exception as exc:
            print(f"  [ERR] Failed to convert '{object_key}': {exc}")
            errors += 1

    print(
        f"\n[DONE] Converted {converted} file(s) to Parquet in '{PERSISTENT_PREFIX}/'."
        + (f"  ({errors} error(s))" if errors else "")
    )


if __name__ == "__main__":
    main()
