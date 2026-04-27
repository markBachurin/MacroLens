from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ingestion.config.series_config import get_series

def validate(records: list[dict], series_key: str) -> tuple[list[dict], list[str]]:
    error_logs = []

    records, error_log = validate_duplicate_dates(records, series_key)
    error_logs += error_log

    records, error_log = validate_future_dates(records, series_key)
    error_logs += error_log

    records, error_log = validate_null_records(records, series_key)
    error_logs += error_log

    records, error_log = validate_out_of_bound(records, series_key)
    error_logs += error_log

    return records, error_logs


def validate_duplicate_dates(records: list[dict], series_key: str) -> tuple[list, list]:
    seen = set()
    valid_records = []
    error_log = []

    for record in records:
        date = record["date"]
        if date in seen:
            error_log.append(f"[{datetime.now()}] - {series_key}: duplicate date {record['date']}")
        else:
            seen.add(date)
            valid_records.append(record)
    return valid_records, error_log


def validate_future_dates(records: list[dict], series_key: str) -> tuple[list, list]:
    valid_records = []
    error_log = []

    today = datetime.today().date()

    for record in records:
        record_date = datetime.strptime(record["date"], "%Y-%m-%d").date()
        if record_date > today:
            error_log.append(f"[{datetime.now()}] - {series_key}: date {record['date']} is in the future")
        else:
            valid_records.append(record)
    return valid_records, error_log


def validate_null_records(records: list[dict], series_key: str) -> tuple[list, list]:
    valid_records = []
    error_log = []

    for record in records:
        if record["date"] is None or record["value"] is None:
            error_log.append(f"[{datetime.now()}] - {series_key}: null value detected: date: {record['date']}, value: {record['value']}")
        else:
            valid_records.append(record)
    return valid_records, error_log


def validate_out_of_bound(records: list[dict], series_key: str) -> tuple[list, list]:
    valid_records = []
    error_log = []

    series = get_series(series_key)
    valid_min = series["valid_min"]
    valid_max = series["valid_max"]

    for record in records:
        if valid_min <= record["value"] <= valid_max:
            valid_records.append(record)
        else:
            error_log.append(f"[{datetime.now()}] - {series_key}: value {record['value']} on {record['date']} out of bounds [{valid_min}, {valid_max}]")
    return valid_records, error_log

def print_errors(error_logs: list[str]) -> None:
    for error in error_logs:
        print(error)