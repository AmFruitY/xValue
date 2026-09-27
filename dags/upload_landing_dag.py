"""
upload_landing_dag.py
─────────────────────
Airflow DAG that uploads static files from the local `data/landing/` folder
to MinIO so that downstream PySpark jobs can read them via the S3 API.

This DAG is the first of three specialised pipelines that replace the
monolithic xvalue_etl_pipeline:

    1. upload_landing_dag   ← you are here
    2. download_dag         (downloads raw data from FBref / Understat / etc.)
    3. processing_dag       (cleans, joins, and builds the exploitation zone)

Schedule: @weekly (every Monday at 00:00), also triggerable manually.
"""

import os
import sys
import importlib
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

# ── Project root inside the container ────────────────────────────────────────
# The docker-compose bind mount puts the project at /opt/airflow/project
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
    # Reload in case Airflow reuses the process across runs
    importlib.reload(module)
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
        "Uploads static files from data/landing/ to the MinIO landing zone. "
        "Run this before any downstream processing DAG."
    ),
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule="@weekly",   # Runs every Monday — also triggerable manually
    catchup=False,        # Don't backfill missed runs
    tags=["xvalue", "minio", "landing"],
) as dag:

    # ── Upload static landing files to MinIO ──────────────────────────────
    t_upload_landing = PythonOperator(
        task_id="upload_landing",
        python_callable=run_etl,
        op_args=["etl.upload_landing"],
        doc_md=(
            "Iterates over every file inside `data/landing/` and uploads it to "
            "MinIO under the `landing/` prefix. "
            "PySpark and DuckDB jobs in the processing DAG read from this prefix."
        ),
    )

    # ── Pipeline graph ────────────────────────────────────────────────────
    #
    #   upload_landing   (single task — no dependencies)
    #
    t_upload_landing
