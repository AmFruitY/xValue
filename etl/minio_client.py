"""
minio_client.py
───────────────
A thin wrapper around boto3 that provides a pre-configured S3 client
pointing at your local MinIO instance.

Usage example
─────────────
    from etl.minio_client import upload_file, download_file

    # Upload a local CSV to MinIO
    upload_file(local_path="data/raw/all_players.csv",
                object_key="raw/all_players.csv")

    # Download it back later
    download_file(object_key="raw/all_players.csv",
                  local_path="data/raw/all_players.csv")
"""

import os
import boto3
from botocore.client import Config
from dotenv import load_dotenv
from pathlib import Path

# Load variables from .env.local (next to this file's project root)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env.local")

# ── Read config from environment ────────────────────────────────────────────
_ENDPOINT  = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
_ACCESS    = os.getenv("MINIO_ROOT_USER", "minioadmin")
_SECRET    = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin123")
_BUCKET    = os.getenv("MINIO_BUCKET", "xvalue-data")


def get_client() -> boto3.client:
    """
    Return a boto3 S3 client pre-configured for your local MinIO.

    The signature_version='s3v4' setting is required by MinIO.
    path_style=True tells boto3 to use http://host:port/bucket
    instead of http://bucket.host:port (virtual-hosted style).
    """
    return boto3.client(
        "s3",
        endpoint_url=_ENDPOINT,
        aws_access_key_id=_ACCESS,
        aws_secret_access_key=_SECRET,
        config=Config(signature_version="s3v4"),
    )


def upload_file(local_path: str | Path, object_key: str, bucket: str = _BUCKET) -> None:
    """
    Upload a local file to MinIO.

    Args:
        local_path:  Path on your machine, e.g. "data/raw/all_players.csv"
        object_key:  Destination path inside the bucket, e.g. "raw/all_players.csv"
        bucket:      Bucket name (defaults to MINIO_BUCKET env var)
    """
    client = get_client()
    local_path = Path(local_path)
    print(f"  ↑ Uploading '{local_path}' → s3://{bucket}/{object_key}")
    client.upload_file(str(local_path), bucket, object_key)
    print(f"  ✓ Upload complete")


def download_file(object_key: str, local_path: str | Path, bucket: str = _BUCKET) -> None:
    """
    Download a file from MinIO to a local path.

    Args:
        object_key:  Source path inside the bucket, e.g. "raw/all_players.csv"
        local_path:  Destination on your machine, e.g. "data/raw/all_players.csv"
        bucket:      Bucket name (defaults to MINIO_BUCKET env var)
    """
    client = get_client()
    local_path = Path(local_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"  ↓ Downloading s3://{bucket}/{object_key} → '{local_path}'")
    client.download_file(bucket, object_key, str(local_path))
    print(f"  ✓ Download complete")


def list_objects(prefix: str = "", bucket: str = _BUCKET) -> list[str]:
    """List all object keys in the bucket, optionally filtered by prefix."""
    client = get_client()
    response = client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    return [obj["Key"] for obj in response.get("Contents", [])]
