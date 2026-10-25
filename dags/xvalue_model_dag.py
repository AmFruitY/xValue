"""
xvalue_model_dag.py
───────────────────
Airflow DAG: Trusted Zone → Exploitation Zone → model.

    build_features ──▶ train_model
    (DuckDB)           (scikit-learn + XGBoost)

  build_features: builds df_xvalue (one row per incoming transfer, with the
      player's running stats and injury history) from the Trusted tables and
      writes it to exploitation_zone/df_xvalue/.
  train_model: trains the XGBoost experiments on df_xvalue, scores the saved
      best model (champion) and the new one (challenger) on the same test set,
      and keeps the better one in exploitation_zone/models/ for the front end.

Separate from the FBref DAG because it uses every source (FBref stats,
injuries, transfers), not only FBref. Schedule: every Monday at 06:00 UTC,
after the weekly FBref DAG (Sunday at midnight). Also triggerable manually.
"""

from datetime import datetime, timedelta

from airflow import DAG
try:                                                   # Airflow 3
    from airflow.providers.standard.operators.bash import BashOperator
except ImportError:                                    # Airflow 2
    from airflow.operators.bash import BashOperator

# Where the repository is mounted inside the Airflow containers.
SCRIPTS = "/opt/airflow/project/etl"

default_args = {
    "owner": "xvalue",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 0,          # a rerun on the same data gives the same result
}

with DAG(
    dag_id="xvalue_model_dag",
    description="Builds the model's feature table from the Trusted Zone and trains the transfer-fee model.",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule="0 6 * * 1",      # Mondays 06:00 UTC, after the weekly FBref DAG
    catchup=False,
    max_active_runs=1,
    tags=["xvalue", "exploitation", "model"],
) as dag:

    t_features = BashOperator(
        task_id="build_features",
        bash_command=f"python -u {SCRIPTS}/exploitation/build_features.py",
        execution_timeout=timedelta(minutes=20),
        doc_md="Trusted Zone → `exploitation_zone/df_xvalue/df_xvalue.parquet` (DuckDB).",
    )

    t_train = BashOperator(
        task_id="train_model",
        bash_command=f"python -u {SCRIPTS}/model/train_model.py",
        execution_timeout=timedelta(minutes=45),
        doc_md=(
            "Trains the XGBoost experiments on df_xvalue and keeps the better of the saved "
            "model and the new one (same test set) in `exploitation_zone/models/`."
        ),
    )

    t_features >> t_train
