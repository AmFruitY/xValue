"""
upload_landing_dag.py
─────────────────────
Airflow DAG that manages the full Landing Zone ingestion pipeline in MinIO.

Two-stage approach
──────────────────
  Stage 1 — Temporal Landing Zone
      upload_temporal_landing
      Reads CSV files from  data/landing/  on disk and uploads them to
      MinIO under  landing/temporal/ .  No transformation — raw data as-is.

  Stage 2 — Persistent Landing Zone
      csv_to_parquet_landing
      Reads every CSV from  landing/temporal/  in MinIO, converts it to
      Parquet (snappy-compressed), and writes it to  landing/persistent/ .
      This is the canonical format for all downstream PySpark / DuckDB jobs.

Pipeline graph
──────────────
  upload_temporal_landing  ──▶  csv_to_parquet_landing

This DAG is one of three that replace the monolithic xvalue_etl_pipeline:
    1. upload_landing_dag   ← you are here
    2. download_dag         (FBref / Understat / U23 scrapers)
    3. processing_dag       (join → clean → exploit)

Schedule: @weekly (every Monday at 00:00), also triggerable manually.
"""

import os
import sys
import importlib
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

# ── Project root inside the container ────────────────────────────────────────
PROJECT_DIR = "/opt/airflow/project"


def run_etl(module_name: str) -> None:
    """
    Helper that:
    1. Sets the working directory to PROJECT_DIR so relative paths in ETL
       scripts (e.g. Path("data/landing")) resolve correctly.
    2. Adds the project root to sys.path so 'etl.*' imports work.
    3. Imports the given module and calls its main() function.

    Args:
        module_name: dotted module path, e.g. "etl.upload_landing"
    """
    os.chdir(PROJECT_DIR)
    if PROJECT_DIR not in sys.path:
        sys.path.insert(0, PROJECT_DIR)

    module = importlib.import_module(module_name)
    importlib.reload(module)   # Reload in case Airflow reuses the process
    module.main()


# ── Default task settings ────────────────────────────────────────────────────
default_args = {
    "owner": "xvalue",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

# ── DAG definition ───────────────────────────────────────────────────────────
with DAG(
    dag_id="upload_landing_dag",
    description=(
        "Two-stage landing zone: uploads CSVs to MinIO (temporal), "
        "then converts them to Parquet (persistent)."
    ),
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule="@weekly",   # Runs every Monday — also triggerable manually
    catchup=False,
    tags=["xvalue", "minio", "landing"],
) as dag:

    # ── Stage 1: upload CSVs → landing/temporal/ ─────────────────────────
    t_upload_temporal = PythonOperator(
        task_id="upload_temporal_landing",
        python_callable=run_etl,
        op_args=["etl.upload.upload_landing"],
        doc_md=(
            "Scans `data/landing/` on disk for CSV files and uploads them to "
            "MinIO under `landing/temporal/`.  No transformation is applied — "
            "this is the raw, as-received data."
        ),
    )

    # ── Stage 2: convert CSVs → Parquet in landing/persistent/ ──────────
    t_csv_to_parquet = PythonOperator(
        task_id="csv_to_parquet_landing",
        python_callable=run_etl,
        op_args=["etl.upload.csv_to_parquet_landing"],
        doc_md=(
            "Reads every CSV from `landing/temporal/` in MinIO, converts it to "
            "Parquet (snappy-compressed) using pandas + pyarrow, and writes the "
            "result to `landing/persistent/`.  Downstream PySpark / DuckDB jobs "
            "read from this persistent prefix."
        ),
    )

    # ── Pipeline graph ────────────────────────────────────────────────────
    #
    #   upload_temporal_landing  ──▶  csv_to_parquet_landing
    #
    t_upload_temporal >> t_csv_to_parquet
