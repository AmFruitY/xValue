"""
xvalue_predict_dag.py
─────────────────────
Weekly: estimates every current player's transfer value with the saved best
model, so the front end follows this week's stats.

    predict_values
      Trusted Zone (this week's FBref stats, injuries, transfers)
      + exploitation_zone/models/xvalue_xgb_best.joblib
      → exploitation_zone/predictions/latest.parquet  (+ a dated copy in history/)

The three DAGs together:
    fbref_current_stats_dag  weekly        download → parse → clean → verify
    xvalue_predict_dag       weekly        predict current players' values (this DAG)
    xvalue_model_dag         15 Feb/15 Sep build features → retrain, after each window

Schedule: Mondays 06:00 UTC, after the weekly FBref DAG (Sunday at midnight).
Needs a saved model: run xvalue_model_dag once first.
"""

from datetime import datetime, timedelta

from airflow import DAG
try:                                                   # Airflow 3
    from airflow.providers.standard.operators.bash import BashOperator
except ImportError:                                    # Airflow 2
    from airflow.operators.bash import BashOperator

SCRIPTS = "/opt/airflow/project/etl"

with DAG(
    dag_id="xvalue_predict_dag",
    description="Weekly transfer-value estimates for every current player, with the saved best model.",
    default_args={"owner": "xvalue", "depends_on_past": False, "retries": 1,
                  "retry_delay": timedelta(minutes=10)},
    start_date=datetime(2024, 1, 1),
    schedule="0 6 * * 1",      # Mondays 06:00 UTC, after the weekly FBref DAG
    catchup=False,
    max_active_runs=1,
    tags=["xvalue", "exploitation", "model", "predictions"],
) as dag:

    BashOperator(
        task_id="predict_values",
        bash_command=f"python -u {SCRIPTS}/model/predict_values.py",
        execution_timeout=timedelta(minutes=20),
        doc_md=(
            "Builds this season's player features with the same code as the training data, "
            "applies the saved best model and writes `exploitation_zone/predictions/latest.parquet` "
            "(the front end reads it) plus a dated copy in `predictions/history/`."
        ),
    )