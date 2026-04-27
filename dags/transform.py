from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

def run_normalizer():
    from transformation.normalizer import normalize
    return normalize()

def run_derived():
    from transformation.derived_series import compute_derived
    return compute_derived()

def run_snapshot_builder():
    from transformation.snapshot_builder import build_snapshots
    return build_snapshots()

dag_id="transform"
start_date=datetime(2026, 1, 1)
schedule="0 5 * * *"

with DAG(
    dag_id=dag_id,
    start_date=start_date,
    schedule=schedule,
    catchup=False
) as dag:
    t1 = PythonOperator(
        task_id="normalize",
        python_callable=run_normalizer,
    )

    t2 = PythonOperator(
        task_id="compute_derived",
        python_callable=run_derived,
    )

    t3 = PythonOperator(
        task_id="build_snapshots",
        python_callable=run_snapshot_builder
    )

    t1 >> t2 >> t3