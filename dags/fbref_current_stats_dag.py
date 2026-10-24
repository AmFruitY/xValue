"""
fbref_current_stats_dag.py
──────────────────────────
Airflow DAG representing the current-season FBref stats scraping and parsing
pipeline for the Big 5 leagues.

Note on VM Execution:
─────────────────────
Real scraping (with xvfb and headless browsers) is run locally or outside the VM.
In the VM, tasks in this DAG are represented using EmptyOperator so that the DAG
graph and structure appear in the Airflow UI and runs complete cleanly without
failing on missing display/browser dependencies.

Stages Represented:
───────────────────
  Stage 1 — Download (one league after another, never in parallel):
      download_fbref_<league>
  Stage 2 — Parse:
      parse_fbref

Schedule: @weekly (every Monday at 00:00), also triggerable manually.
"""

from datetime import datetime, timedelta

from airflow import DAG
try:
    from airflow.operators.empty import EmptyOperator
except ImportError:
    from airflow.operators.dummy import DummyOperator as EmptyOperator

LEAGUES = [
    "eng-premier-league",
    "esp-la-liga",
    "fra-ligue-1",
    "ger-bundesliga",
    "ita-serie-a",
]

# ── Default task settings ────────────────────────────────────────────────────
default_args = {
    "owner": "xvalue",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

# ── DAG definition ───────────────────────────────────────────────────────────
with DAG(
    dag_id="fbref_current_stats_dag",
    description="Downloads current-season FBref pages of the Big 5 leagues and parses them to CSV (display representation in VM).",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule="@weekly",   # Runs every Monday — also triggerable manually
    catchup=False,
    max_active_runs=1,
    tags=["xvalue", "fbref", "scraping"],
) as dag:

    # ── Stage 1: download each league's pages → data/raw/html/<league>/ ──
    download_tasks = [
        EmptyOperator(
            task_id=f"download_fbref_{league}",
            doc_md=(
                f"Downloads the Standard, Shooting, Playing Time and Miscellaneous "
                f"pages of `{league}` with a real browser and saves "
                f"them to `data/raw/html/{league}/`."
            ),
        )
        for league in LEAGUES
    ]

    # ── Stage 2: parse the HTML pages → data/raw/current_season/<league>/*.csv ──
    t_parse = EmptyOperator(
        task_id="parse_fbref",
        doc_md=(
            "Parses the saved FBref pages of every league into one CSV per league "
            "(`data/raw/current_season/<league>/<league>_<season>_stats_fbref.csv`) and a dated "
            "snapshot under `data/raw/snapshots/<league>/`."
        ),
    )

    # ── Pipeline graph ────────────────────────────────────────────────────
    #
    #   download (eng) ──▶ download (esp) ──▶ ... ──▶ download (ita) ──▶ parse_fbref
    #
    for upstream, downstream in zip(download_tasks, download_tasks[1:]):
        upstream >> downstream
    download_tasks[-1] >> t_parse
