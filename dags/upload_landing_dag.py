"""
upload_landing_dag.py
─────────────────────
Airflow DAG that manages the Landing Zone ingestion pipeline in MinIO for the
current season.

Approach
────────
  upload_current_season_landing
  Scans `data/raw/current_season/` on disk for raw data files (CSVs/Parquets).
  Directly converts CSVs to Snappy-compressed Parquet in-memory and uploads them
  to MinIO under `Landing Zone/current_season/`. Existing Parquet files are uploaded
  directly.

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
       scripts (e.g. Path("data/raw/current_season")) resolve correctly.
    2. Adds the project root to sys.path so 'etl.*' imports work.
    3. Imports the given module and calls its main() function.

    Args:
        module_name: dotted module path, e.g. "etl.upload.upload_landing"
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
        "Uploads current season raw data from data/raw/current_season/ to MinIO "
        "Landing Zone ('Landing Zone/current_season/') as Parquet."
    ),
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule="@weekly",   # Runs every Monday — also triggerable manually
    catchup=False,
    tags=["xvalue", "minio", "landing", "current_season"],
) as dag:

    t_upload_current_season = PythonOperator(
        task_id="upload_current_season_landing",
        python_callable=run_etl,
        op_args=["etl.upload.upload_landing"],
        doc_md=(
            "Scans `data/raw/current_season/` on disk for raw data files (CSVs and Parquets), "
            "converts CSVs directly to snappy-compressed Parquet in-memory, and uploads them to "
            "MinIO under `Landing Zone/current_season/`."
        ),
    )
