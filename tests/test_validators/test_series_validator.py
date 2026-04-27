from ingestion.validators.series_validator import (
    validate_duplicate_dates,
    validate_future_dates,
    validate_null_records,
    validate_out_of_bound,
    validate
)

from datetime import date, timedelta

def test_duplicate_dates():
    records = [
        {"date":"2024-01-01", "value":70.0},
        {"date":"2024-01-01", "value":71.0},
        {"date":"2024-01-02", "value":72.0}
    ]

    valid, errors = validate_duplicate_dates(records, "WTI")
    assert len(valid) == 2
    assert len(errors) == 1
    assert "duplicate" in errors[0]


def test_future_dates():
    records = [
        {"date": str(date.today() + timedelta(days=2)), "value": 70.0},
        {"date": "2024-01-01", "value": 71.0},
        {"date": "2024-01-02", "value": 72.0}
    ]

    valid, errors = validate_future_dates(records, "WTI")
    assert len(valid) == 2
    assert len(errors) == 1
    assert "future" in errors[0]

def test_null_records():
    records = [
        {"date": None, "value": 70.0},
        {"date": "2024-01-01", "value": 71.0},
        {"date": "2024-01-02", "value": None}
    ]

    valid, errors = validate_null_records(records, "WTI")
    assert len(valid) == 1
    assert len(errors) == 2
    assert "null value" in errors[0]

def test_out_of_bound():
    records = [
        {"date": "2024-01-01", "value": -10.0},
        {"date": "2024-01-01", "value": 71.0},
        {"date": "2024-01-02", "value": 350.0}
    ]

    valid, errors = validate_out_of_bound(records, "WTI")
    assert len(valid) == 1
    assert len(errors ) == 2
    assert "out of bounds" in errors[0]

def test_validate_happy_path():
    records = [
        {"date": "2024-01-01", "value": 70.0},
        {"date": "2024-01-02", "value": 72.0},
        {"date": "2024-01-03", "value": 68.0},
    ]

    valid, errors = validate(records, "WTI")
    assert len(valid) == 3
    assert len(errors) == 0

