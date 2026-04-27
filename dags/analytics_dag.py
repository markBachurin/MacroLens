from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime


def run_correlations():
    from analytics.correlations import compute_correlations
    return compute_correlations()

def run_regression():
    from analytics.regression import compute_regression
    return compute_regression()

def run_lag_analysis():
    from analytics.lag_analysis import compute_lag_analysis
    return compute_lag_analysis()

start_date=datetime(2026, 1, 1)
schedule="0 6 * * *"

with DAG(
    dag_id="analytics",
    start_date=start_date,
    schedule=schedule,
    catchup=False
) as dag:
    t1 = PythonOperator(
        task_id="compute_correlations",
        python_callable=run_correlations,
    )

    t2 = PythonOperator(
        task_id="compute_regressions",
        python_callable=run_regression,
    )

    t3 = PythonOperator(
        task_id="compute_lag_analysis",
        python_callable=run_lag_analysis
    )

    t1 >> t2 >> t3