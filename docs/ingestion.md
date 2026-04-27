# MacroLens — Ingestion Layer

## Overview

The ingestion layer fetches raw financial data from four external sources, validates it, archives it to S3, and loads clean records into PostgreSQL. It is the first and most critical layer of the pipeline — all downstream layers depend on the quality of data produced here.

Three principles:
- **Source isolation** — each data source has its own adapter and fails independently
- **Idempotency** — every operation can be re-run safely without duplicating data
- **Auditability** — raw API payloads are archived to S3 before any transformation

---

## Directory Structure

```
ingestion/
├── adapters/
│   ├── base.py             ← Abstract BaseAdapter + SeriesPoint dataclass
│   ├── fred.py             ← FRED API adapter
│   ├── yfinance.py         ← yfinance adapter
│   ├── treasury.py         ← U.S. Treasury Fiscal Data XML adapter
│   └── alphaVantage.py     ← Alpha Vantage FX adapter
├── config/
│   └── series_config.py    ← Single source of truth for all series metadata
├── loaders/
│   ├── base.py             ← Abstract Client base class
│   ├── db_connection.py    ← psycopg2 connection factory
│   ├── postgres_gate.py    ← All Postgres read/write operations
│   ├── aws_s3_gate.py      ← S3 upload implementation
│   └── aws_s3_client.py    ← boto3 client factory
├── validators/
│   └── series_validator.py ← Validation rules, pure functions
└── dag_factory.py          ← Reusable DAG task factory for all ingestion DAGs
```
[base.py](../ingestion/loaders/base.py)
---

## Component: `series_config.py`

The central registry for all tracked series. Every other component reads from here — adapters use it to know what to fetch, validators use it for bounds checking, loaders use it for metadata.

### Full SERIES_CONFIG

```python
SERIES_CONFIG = {
    "WTI":           { "source": "fred",        "series_id": "DCOILWTICO",      "name": "WTI Crude Oil Price",                       "unit": "USD/barrel", "category": "energy",   "valid_min": -5.0,  "valid_max": 200.0,   "frequency": "daily"   },
    "BRENT":         { "source": "fred",        "series_id": "DCOILBRENTEU",    "name": "Brent Crude Oil Price",                     "unit": "USD/barrel", "category": "energy",   "valid_min":  0.0,  "valid_max": 200.0,   "frequency": "daily"   },
    "SP500":         { "source": "yfinance",    "series_id": "^GSPC",           "name": "S&P500",                                    "unit": "index",      "category": "equity",   "valid_min": 100.0, "valid_max": 20000.0, "frequency": "daily"   },
    "NASDAQ":        { "source": "yfinance",    "series_id": "^IXIC",           "name": "NASDAQ Composite",                          "unit": "index",      "category": "equity",   "valid_min": 100.0, "valid_max": 30000.0, "frequency": "daily"   },
    "FED_FUNDS":     { "source": "fred",        "series_id": "FEDFUNDS",        "name": "Federal Funds Effective Rate",              "unit": "percent",    "category": "rates",    "valid_min":  0.0,  "valid_max":  25.0,   "frequency": "monthly" },
    "CPI":           { "source": "fred",        "series_id": "CPIAUCSL",        "name": "Consumer Price Index (All Urban)",          "unit": "index",      "category": "macro",    "valid_min": 10.0,  "valid_max": 500.0,   "frequency": "monthly" },
    "GOLD":          { "source": "yfinance",    "series_id": "GC=F",            "name": "Gold Futures",                              "unit": "USD/oz",     "category": "macro",    "valid_min": 100.0, "valid_max": 5000.0,  "frequency": "daily"   },
    "T10Y":          { "source": "fred",        "series_id": "DGS10",           "name": "10-Year Treasury Constant Maturity Rate",   "unit": "percent",    "category": "rates",    "valid_min": -1.0,  "valid_max":  20.0,   "frequency": "daily"   },
    "T2Y":           { "source": "treasury",    "series_id": "BC_2YEAR",        "name": "2-Year Treasury Yield",                     "unit": "percent",    "category": "rates",    "valid_min": -1.0,  "valid_max":  20.0,   "frequency": "daily"   },
    "T10Y_TREASURY": { "source": "treasury",    "series_id": "BC_10YEAR",       "name": "10-Year Treasury Yield",                    "unit": "percent",    "category": "rates",    "valid_min": -1.0,  "valid_max":  20.0,   "frequency": "daily"   },
    "EURUSD":        { "source": "alphavantage","series_id": "EUR/USD",          "name": "Euro / US Dollar Exchange Rate",            "unit": "USD",        "category": "forex",    "valid_min":  0.5,  "valid_max":   2.0,   "frequency": "daily"   },
    "VIX":           { "source": "yfinance",    "series_id": "^VIX",            "name": "CBOE Volatility Index",                     "unit": "index",      "category": "equity",   "valid_min":  5.0,  "valid_max":  90.0,   "frequency": "daily"   },
    "YIELD_SPREAD":  { "source": "derived",     "series_id": "DERIVED_YIELD_SPREAD","name": "Yield Curve Spread (10Y - 2Y)",         "unit": "percent",    "category": "derived",  "valid_min": -5.0,  "valid_max":  10.0,   "frequency": "daily"   },
    "REAL_WTI":      { "source": "derived",     "series_id": "DERIVED_REAL_WTI","name": "Real WTI Crude Oil Price (CPI-adjusted)", "unit": "USD/barrel", "category": "derived",  "valid_min": -5.0,  "valid_max": 200.0,   "frequency": "daily"   },
    "WTI_SP500":     { "source": "derived",     "series_id": "DERIVED_WTI_SP500","name": "WTI to S&P500 Ratio",                    "unit": "ratio",      "category": "derived",  "valid_min":  0.0,  "valid_max": 100.0,   "frequency": "daily"   },
}
```

15 series total: 5 from FRED, 4 from yfinance, 2 from Treasury, 1 from Alpha Vantage, 3 derived.

### Helper Functions

| Function | Signature | Description |
|---|---|---|
| `get_source_series` | `(source: str) -> dict` | All series for a given source |
| `get_series` | `(series_key: str) -> dict` | Config for one series by internal key |
| `get_field` | `(series: str, field: str) -> str` | Single field for a series |

---

## Component: Adapters

### Base Adapter (`adapters/base.py`)

```python
@dataclass
class SeriesPoint:
    source: str
    series_id: str
    series_name: str
    date: date
    value: float
    unit: str | None = None

class BaseAdapter(ABC):
    source: str

    @abstractmethod
    def fetch(self, series_id: str, start: date, end: date) -> List[SeriesPoint]:
        ...
```

All adapters in practice return `list[dict]` with keys `date` and `value` (not `SeriesPoint` instances — the dataclass is defined but not enforced at runtime).

### FRED Adapter (`adapters/fred.py`)

- **Endpoint:** `GET https://api.stlouisfed.org/fred/series/observations`
- **Auth:** `FRED_API_KEY` environment variable
- **FRED-specific handling:** missing values returned as `"."` string — filtered out explicitly; values come back as strings, cast to `float`
- **Error handling:** `response.raise_for_status()`, checks for `"observations"` key in response, raises on missing `FRED_API_KEY` at init time

### yfinance Adapter (`adapters/yfinance.py`)

- No API key required
- Returns pandas DataFrame; `Close` column contains the relevant value
- Date index is timezone-aware — stripped via `.strftime("%Y-%m-%d")`
- Values cast from `np.float64` to plain Python `float` (required for JSON serialization and psycopg2)
- Raises `ValueError` on empty DataFrame (invalid ticker or no data for range)

### Treasury Adapter (`adapters/treasury.py`)

- **Endpoint:** `https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml`
- **Auth:** None required
- Fetches XML data, one HTTP request per calendar year in the requested range
- Parses Atom XML with OData/ADO.NET namespaces
- `series_id` is an XML element name (e.g. `BC_2YEAR`, `BC_10YEAR`)

### Alpha Vantage Adapter (`adapters/alphaVantage.py`)

- **Endpoint:** `https://www.alphavantage.co/query` with `function=FX_DAILY`
- **Auth:** `ALPHA_VANTAGE_API_KEY` environment variable (note: not `ALPHAVANTAGE_KEY`)
- `series_id` is a slash-separated pair e.g. `"EUR/USD"` — split into `from_symbol` / `to_symbol`
- Detects rate limit via `"Note"` or `"Information"` keys in response — raises `RuntimeError`
- Filters by date range client-side (API returns full history)

---

## Component: Validator (`validators/series_validator.py`)

Pure functions — no database, no network, no side effects. Fully unit-testable in isolation.

### Interface

```python
def validate(records: list[dict], series_key: str) -> tuple[list[dict], list[str]]:
```

Returns `(valid_records, error_messages)`. Never raises. Errors are logged; the DAG decides whether to fail.

### Validation Rules (applied in order)

1. **`validate_duplicate_dates`** — keeps first occurrence of each date, logs duplicates. O(n) using a `set`.
2. **`validate_future_dates`** — drops records where `date > today`
3. **`validate_null_records`** — drops records where `date` or `value` is `None`
4. **`validate_out_of_bound`** — compares value against `valid_min` / `valid_max` from `series_config.py`

```python
def print_errors(error_logs: list[str]) -> None:
    for error in error_logs:
        print(error)
```

Each error log entry is formatted: `[{datetime}] - {series_key}: {message}`

---

## Component: `dag_factory.py`

A factory that generates the four standard task callables for every ingestion DAG. All ingestion DAGs share identical task structure — `dag_factory.py` eliminates code duplication.

### Generated Tasks

```python
def create_extract_task(source: str, adapter_class: Type[BaseAdapter]) -> Callable
def create_archive_task(source: str) -> Callable
def create_validate_task(source: str) -> Callable
def create_load_task(source: str) -> Callable
```

Each function returns a Python callable suitable for `PythonOperator`. The `source` string determines XCom task IDs (e.g. `extract_fred`, `archive_raw_fred`).

**Data flow through XCom:**
```
extract_{source}   → xcom_push("raw_payload", {series_key: records})
archive_raw_{source} → xcom_pull("raw_payload") → xcom_push("raw_records", same payload)
validate_{source}  → xcom_pull("raw_records") → xcom_push("validated_records", filtered)
load_{source}      → xcom_pull("validated_records") → writes to raw_series table
```

**Import pattern:** All non-Airflow imports are inside function bodies, not at module level. Airflow parses DAG files every 30 seconds — top-level imports of heavy libraries slow this cycle.

---

## Component: Client (`loaders/`)

### `aws_s3_gate.py` — S3 Upload

```python
def upload_series(self, records: list[dict], source: str, series_id: str, state: str = "raw") -> None
```

**S3 key structure:**
```
{state}_payload/{source}/{series_id}/{YYYYMMDD_HHMMSS_ffffff}.json
```
Example: `raw_payload/fred/DCOILWTICO/20260420_040023_123456.json`

The timestamp filename (not a date) means multiple runs on the same day produce separate files — no overwrite risk.

### `postgres_gate.py` — Postgres Read/Write

Key methods:

| Method | Operation |
|---|---|
| `upload_series(records, source, series_key, state)` | Upsert into `{state}_series` table |
| `upload_normalized_series(records, series_key)` | Upsert into `normalized_series` |
| `upload_snapshot(records)` | Upsert into `daily_snapshot` |
| `upload_correlations(records)` | Upsert into `correlation_results` |
| `upload_lag_results(records)` | Upsert into `lag_results` |
| `upload_regression_results(records)` | Upsert into `regression_results` |
| `query_raw_by_series_key(series_key)` | `SELECT date, value FROM raw_series` |
| `query_normalized_by_series_id(series_id)` | `SELECT date, value, pct_change, zscore_252d FROM normalized_series` |
| `query_snapshot_entries()` | All normalized series with non-null zscore |

**Upsert strategy (raw_series):**
```sql
INSERT INTO raw_series (source, series_id, series_key, date, value)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (source, series_id, date)
DO UPDATE SET value = EXCLUDED.value, ingested_at = NOW();
```

**Note:** boto3 client and psycopg2 connection are instantiated in `__init__`, not at class level. Class-level instantiation happens at import time before `load_dotenv()` runs, resulting in `None` credentials.

---

## Airflow DAGs

Four ingestion DAGs, all using `dag_factory.py`:

| DAG ID | Source | Adapter | Schedule |
|---|---|---|---|
| `ingest_fred` | fred | `FredAdapter` | `0 4 * * *` (04:00 UTC) |
| `ingest_yfinance` | yfinance | `YfinanceAdapter` | `0 4 * * *` |
| `ingest_treasury` | treasury | `TreasuryAdapter` | `0 4 * * *` |
| `ingest_alpha_vantage` | alphavantage | `AlphaVantageAdapter` | `0 4 * * *` |

All DAGs: `catchup=False`, `start_date=2026-01-01`.

Task chain for each DAG:
```
extract_{source} → archive_raw_{source} → validate_{source} → load_{source}
```

---

## Environment Variables Required

| Variable | Used By | Description |
|---|---|---|
| `FRED_API_KEY` | `FredAdapter` | FRED API authentication |
| `ALPHA_VANTAGE_API_KEY` | `AlphaVantageAdapter` | Alpha Vantage authentication |
| `PG_HOST` | `db_connection.py` | Postgres host (`postgres` inside Docker) |
| `PG_PORT` | `db_connection.py` | Postgres port (default 5432) |
| `PG_DB` | `db_connection.py` | Database name |
| `PG_USER` | `db_connection.py` | Database user |
| `PG_PASSWORD` | `db_connection.py` | Database password |
| `AWS_ACCESS_KEY` | `aws_s3_client.py` | AWS IAM access key |
| `AWS_SECRET_ACCESS_KEY` | `aws_s3_client.py` | AWS IAM secret |
| `S3_BUCKET` | `aws_s3_gate.py` | Target S3 bucket name |

---

## Data Flow Summary

```
FRED API
    │
    │  HTTP GET /fred/series/observations
    ▼
FredAdapter.fetch()
    │  returns list[dict]
    ▼
S3_Client.upload_series()
    │  raw_payload/fred/{series_id}/{YYYYMMDD_HHMMSS_ffffff}.json
    ▼
validate(records, series_key)
    │  returns (valid_records, errors)
    ▼
Postgres_Client.upload_series()
    │  INSERT INTO raw_series ON CONFLICT DO UPDATE
    ▼
raw_series table
```

---

## Testing

```bash
pytest tests/test_validators/ -v
```

Current test coverage:
- `test_duplicate_dates` — two records with same date, expects one kept and one error
- `test_future_dates` — record with future date, expects it dropped
- `test_null_records` — null date and null value, expects both dropped
- `test_out_of_bound` — values outside WTI bounds, expects them dropped
- `test_validate_happy_path` — all valid records, expects zero errors

Adapter tests mock HTTP calls using the `responses` library — no real network calls in CI.
