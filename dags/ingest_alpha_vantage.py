from ingestion.adapters.alphaVantage import AlphaVantageAdapter
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

from ingestion.dag_factory import create_extract_task, create_archive_task, create_validate_task, create_load_task

dag_id="ingest_alphavantage"
source="alphavantage"
adapter_class=AlphaVantageAdapter
start_date: datetime = datetime(2026, 1, 1)
schedule: str = "0 4 * * *"
catchup: bool = False

with DAG(
        dag_id=dag_id,
        start_date=start_date,
        schedule=schedule,
        catchup=catchup
) as dag:
    t1 = PythonOperator(
        task_id=f"extract_{source}",
        python_callable=create_extract_task(source, adapter_class)
    )
    t2 = PythonOperator(
        task_id=f"archive_raw_{source}",
        python_callable=create_archive_task(source)
    )
    t3 = PythonOperator(
        task_id=f"validate_{source}",
        python_callable=create_validate_task(source)
    )
    t4 = PythonOperator(
        task_id=f"load_{source}",
        python_callable=create_load_task(source)
    )

    t1 >> t2 >> t3 >> t4