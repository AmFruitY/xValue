"""
fbref_current_stats_dag.py
──────────────────────────
Airflow DAG for the current-season FBref stats of the Big 5 leagues:
download → parse straight into the Landing Zone → clean to Trusted → verify.

Note on VM Execution:
─────────────────────
Real scraping (with xvfb and headless browsers) is run locally or outside the VM.
In the VM, the download and parse tasks are represented using EmptyOperator so
that the DAG graph appears in the Airflow UI and runs complete cleanly without
failing on missing display/browser dependencies.

The cleaning and verification tasks are REAL: they run inside the Airflow
container and work on the current-season files in the MinIO Landing Zone.

Stages:
───────
  Stage 1 — Download (one league after another, never in parallel):
      download_fbref_<league>                                  (represented)
  Stage 2 — Parse and land:
      parse_fbref: HTML pages → one Parquet file per league, uploaded to
      landing_zone/<league>/<league>_<season>_stats_fbref.parquet  (represented)
  Stage 3 — Clean:
      clean_to_trusted: current season, FBref stats only        (real)
  Stage 4 — Verify:
      verify_trusted: current season                            (real)

Schedule: @weekly (Sunday at midnight), also triggerable manually.
"""

from datetime import datetime, timedelta

from airflow import DAG
try:
    from airflow.operators.empty import EmptyOperator
except ImportError:
    from airflow.operators.dummy import DummyOperator as EmptyOperator
try:                                                   # Airflow 3
    from airflow.providers.standard.operators.bash import BashOperator
except ImportError:                                    # Airflow 2
    from airflow.operators.bash import BashOperator

LEAGUES = [
    "eng-premier-league",
    "esp-la-liga",
    "fra-ligue-1",
    "ger-bundesliga",
    "ita-serie-a",
]

# Where the repository is mounted inside the Airflow containers.
SCRIPTS = "/opt/airflow/project/etl/processing"

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
    description="Current-season FBref stats of the Big 5 leagues: download, parse into the "
                "Landing Zone, clean to the Trusted Zone and verify.",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule="@weekly",
    catchup=False,
    max_active_runs=1,
    tags=["xvalue", "fbref", "scraping", "trusted"],
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

    # ── Stage 2: parse the HTML pages straight into the Landing Zone ──
    t_parse = EmptyOperator(
        task_id="parse_fbref",
        doc_md=(
            "Parses the four saved pages of every league into one table per league "
            "(one row per player per club) and uploads it as Parquet to the MinIO "
            "Landing Zone: `xvalue-data/landing_zone/<league>/<league>_<season>_stats_fbref.parquet`. "
            "This season's file is replaced every week: FBref's tables are season-to-date totals."
        ),
    )

    # ── Stage 3: clean this season's FBref stats into the Trusted Zone (real) ──
    # Only the folders league=<league>/season=<this season> are replaced;
    # every historical season stays as it is.
    t_clean = BashOperator(
        task_id="clean_to_trusted",
        bash_command=(
            f"python -u {SCRIPTS}/clean_to_trusted.py "
            "--seasons current --tables fbref_player_stats"
        ),
        execution_timeout=timedelta(minutes=30),
        doc_md=(
            "Runs the PySpark cleaning job on this season's FBref stats only. "
            "A file that breaks a rule is not written and the task fails (red)."
        ),
    )

    # ── Stage 4: verify this season in the Trusted Zone (real) ──
    t_verify = BashOperator(
        task_id="verify_trusted",
        bash_command=f"python -u {SCRIPTS}/verify_trusted.py --seasons current",
        retries=0,                          # the data won't change in 10 minutes
        execution_timeout=timedelta(minutes=10),
        doc_md=(
            "Checks this season in the Trusted Zone: every league present, the right "
            "clubs and the known values in `reference_checks.csv`. Any FAIL turns the task red."
        ),
    )

    # ── Pipeline graph ────────────────────────────────────────────────────
    #
    #   download (eng) ──▶ ... ──▶ download (ita) ──▶ parse (→ Landing) ──▶ clean ──▶ verify
    #
    for upstream, downstream in zip(download_tasks, download_tasks[1:]):
        upstream >> downstream
    download_tasks[-1] >> t_parse >> t_clean >> t_verify