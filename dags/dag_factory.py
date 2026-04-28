from datetime import date, datetime
from airflow import DAG
from airflow.operators.python import PythonOperator

from typing import Type, Dict, Any
from ingestion.adapters.base import BaseAdapter


def create_extract_task(source: str, adapter_class: Type[BaseAdapter]):
    def extract(**context) -> None:
        from ingestion.config.series_config import get_source_series

        payload = {}
        adapter = adapter_class()
        for series_key, data in get_source_series(source).items():
            records = adapter.fetch(
                data["series_id"],
                "2000-01-01",
                date.today().strftime("%Y-%m-%d")
            )
            payload[series_key] = records

        context["ti"].xcom_push(key="raw_payload", value=payload)
    return extract

def create_archive_task(source: str):
    def archive_raw(**context) -> None:
        from ingestion.loaders.aws_s3_gate import S3_Client
        from ingestion.config.series_config import get_source_series

        raw_payload = context["ti"].xcom_pull(task_ids=f"extract_{source}", key="raw_payload")
        s3_gate = S3_Client()
        for series_key, records in raw_payload.items():
            series_id = get_source_series(source)[series_key]["series_id"]
            s3_gate.upload_series(records, source, series_id, "raw")
        context["ti"].xcom_push(key="raw_records", value=raw_payload)

    return archive_raw

def create_validate_task(source: str):
    def validate_records(**context) -> None:
        from ingestion.validators.series_validator import validate, print_errors

        raw_keyed_records = context["ti"].xcom_pull(task_ids=f"archive_raw_{source}", key="raw_records")
        validated = {}
        for series_key, records in raw_keyed_records.items():
            valid, errors = validate(records, series_key)
            print_errors(errors)
            validated[series_key] = valid
        context["ti"].xcom_push(key="validated_records", value=validated)

    return validate_records

def create_load_task(source: str):
    def load_records(**context):
        from ingestion.loaders.postgres_gate import Postgres_Client

        valid_records = context["ti"].xcom_pull(task_ids=f"validate_{source}", key="validated_records")
        postgres_gate = Postgres_Client()
        try:
            for series_key, records in valid_records.items():
                postgres_gate.upload_series(records, source, series_key, "raw")
        finally:
            postgres_gate.close()

    return load_records



