"""
xvalue_pipeline.py
──────────────────
Airflow DAG that orchestrates the full xValue ETL pipeline.

Schedule: weekly (every Monday at 00:00)
Can also be triggered manually from the Airflow UI at http://localhost:8080

Pipeline stages
───────────────
Stage 1 — Download (parallel)
    upload_landing   →  landing files to MinIO
    download_stats   →  data/raw/all_players.csv  + upload to MinIO
    download_u23     →  data/u23_players.csv

Stage 2 — Process (after downloads)
    join_players         →  data/processed/all_players_joined.csv
    limpieza_spark       →  data/trusted/ (PySpark writes Parquet to MinIO)

Stage 3 — Enrich (after processing)
    extract_market_value →  data/processed/player_market_value.csv
    exploitation_zone    →  data/exploitation/ (DuckDB reads/writes MinIO)
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
    1. Sets the working directory to PROJECT_DIR so that relative paths
       in the ETL scripts (e.g. Path("data/raw")) resolve correctly.
    2. Adds the project to sys.path so 'etl.*' imports work.
    3. Imports the given module and calls its main() function.

    Args:
        module_name: dotted module path, e.g. "etl.download_stats"
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
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# ── DAG definition ───────────────────────────────────────────────────────────
with DAG(
    dag_id="xvalue_etl_pipeline",
    description="Full xValue ETL pipeline: download → clean → exploit",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule="@weekly",   # Runs every Monday — also triggerable manually
    catchup=False,        # Don't backfill missed runs
    tags=["xvalue", "etl"],
) as dag:

    # ── Stage 1: Download & Upload (run in parallel) ──────────────────
    t_upload_landing = PythonOperator(
        task_id="upload_landing",
        python_callable=run_etl,
        op_args=["etl.upload_landing"],
        doc_md=(
            "Uploads static files from `data/landing/` to MinIO so PySpark can read them."
        ),
    )

    t_download_stats = PythonOperator(
        task_id="download_stats",
        python_callable=run_etl,
        op_args=["etl.download_stats"],
        doc_md=(
            "Scrapes FBref for player season stats across Big 5 leagues (2018–2023). "
            "Saves to `data/raw/all_players.csv` and uploads to MinIO."
        ),
    )

    t_download_u23 = PythonOperator(
        task_id="download_u23",
        python_callable=run_etl,
        op_args=["etl.download_u23"],
        doc_md=(
            "Same FBref scrape as download_stats but filters to players aged under 23. "
            "Saves to `data/u23_players.csv`."
        ),
    )

    # ── Stage 2: Process (depend on downloads) ────────────────────────────
    t_join_players = PythonOperator(
        task_id="join_players",
        python_callable=run_etl,
        op_args=["etl.join_players"],
        doc_md=(
            "Joins all_players.csv with players.csv (Transfermarkt bios) on "
            "player name + birth year. Saves to `data/processed/all_players_joined.csv`."
        ),
    )

    t_limpieza = PythonOperator(
        task_id="limpieza_spark",
        python_callable=run_etl,
        op_args=["etl.limpieza_spark"],
        doc_md=(
            "PySpark job that cleans and validates datasets from the landing zone in MinIO. "
            "Writes trusted data back to MinIO as Parquet files."
        ),
    )

    # ── Stage 3: Enrich (depend on stage 2) ──────────────────────────────
    t_market_value = PythonOperator(
        task_id="extract_market_value",
        python_callable=run_etl,
        op_args=["etl.extract_player_market_value"],
        doc_md=(
            "Extracts player name, league, and market value from the joined dataset. "
            "Saves to `data/processed/player_market_value.csv`."
        ),
    )

    t_exploitation = PythonOperator(
        task_id="exploitation_zone",
        python_callable=run_etl,
        op_args=["etl.exploitation_zone"],
        doc_md=(
            "Builds the exploitation zone from the trusted DuckDB: injury features, "
            "market value features, and KPI segments. Exports Parquet files."
        ),
    )

    # ── Task dependencies (the pipeline graph) ───────────────────────────
    #
    #   upload_landing ──┐
    #   download_stats ──┼──▶ join_players     ──▶ extract_market_value
    #   download_u23   ──┴──▶ limpieza_spark   ──▶ exploitation_zone
    #
    [t_upload_landing, t_download_stats, t_download_u23] >> t_join_players >> t_market_value
    [t_upload_landing, t_download_stats, t_download_u23] >> t_limpieza >> t_exploitation
