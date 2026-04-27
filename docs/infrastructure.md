# MacroLens — Infrastructure & Database

## Overview

MacroLens runs entirely in Docker containers orchestrated by a single `docker-compose.yml`. The infrastructure is designed for a single-VPS deployment with minimal operational overhead — no Kubernetes, no Celery, no Redis. Every architectural choice is consciously justified and interview-defensible.

---

## Docker Architecture

### Services

| Service | Image | Purpose | Port |
|---|---|---|---|
| `postgres` | `postgres:16-alpine` | Single database instance for app data + Airflow metadata | 5432 (internal only) |
| `airflow-init` | `macrolens` (custom) | One-time init: DB migration + admin user creation | — |
| `airflow-webserver` | `macrolens` (custom) | Airflow UI | 8080 |
| `airflow-scheduler` | `macrolens` (custom) | DAG scheduling and task execution | — |
| `db-init` | `macrolens` (custom) | One-time app table creation | — |
| `api` | `macrolens-api` (custom) | Django REST API + dashboard | 8000 |

### Custom Image (`Dockerfile`)

```dockerfile
FROM apache/airflow:2.9.0

USER root
RUN apt-get update && apt-get install -y gcc python3-dev && rm -rf /var/lib/apt/lists/*

USER airflow
COPY pyproject.toml .
RUN pip install --no-cache-dir -e "."
```

Base image is official Airflow 2.9.0. Additional system packages (`gcc`, `python3-dev`) are required for `psycopg2` compilation. Project dependencies are installed via `pyproject.toml`.

**Why not `_PIP_ADDITIONAL_REQUIREMENTS`?** That Airflow variable installs packages at container startup, on every restart. Building them into the image via `Dockerfile` installs once at build time — faster startup, reproducible environment.

### Full Startup Sequence (from scratch)

```bash
# 1. Build custom images
docker compose build

# 2. Start postgres only
docker compose up -d postgres

# 3. Create Airflow metadata database (separate from app DB)
docker exec -it macrolens-postgres-1 psql -U user -d db -c "CREATE DATABASE airflow;"

# 4. Initialize Airflow metadata tables + create admin user
docker compose up airflow-init

# 5. Create application tables (raw_series, normalized_series, etc.)
docker compose up db-init

# 6. Start all services
docker compose up -d
```

### Full Reset Procedure

```bash
docker compose down -v   # -v removes volumes, wipes all data
# then repeat startup sequence above
```

---

## Two-Database Strategy

One PostgreSQL container, two databases:

| Database | Purpose | Owner |
|---|---|---|
| `db` | Application data: all series, analytics results | MacroLens pipeline |
| `airflow` | Airflow metadata: DAG runs, task states, XCom | Airflow internally |

**Why separate databases?** Airflow creates ~30 tables in its metadata DB. Mixing them with application tables creates confusion and schema management complexity. Separate databases provide clean isolation at negligible cost.

**Why not separate containers?** A second PostgreSQL container would require a second port, second volume, and second healthcheck. One container with two databases is operationally simpler and sufficient for this workload.

---

## Environment Variables

All secrets and configuration are stored in `.env` at the project root. `.env` is in `.gitignore`. `.env.example` is committed with placeholder values.

```bash
# API Keys
FRED_API_KEY=
ALPHA_VANTAGE_API_KEY=        # note: not ALPHAVANTAGE_KEY

# PostgreSQL
PG_HOST=localhost          # Use 'postgres' inside Docker network
PG_PORT=5432
PG_DB=db
PG_USER=user
PG_PASSWORD=password

# AWS
AWS_ACCESS_KEY=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1
S3_BUCKET=macro-lens

# Airflow
AIRFLOW__WEBSERVER__SECRET_KEY=

# Django
DJANGO_SECRET_KEY=
DEBUG=True
```

**Important:** Inside Docker containers, `PG_HOST` must be `postgres` (the Docker service name), not `localhost`. `localhost` inside a container refers to the container itself. The `.env` file uses `localhost` for local script development — Airflow and the API containers override `PG_HOST` via their `environment:` section in `docker-compose.yml`.

---

## Volume Mounts

Airflow containers mount the following directories:

```yaml
volumes:
  - ./dags:/opt/airflow/dags             # DAG files — picked up automatically
  - ./ingestion:/opt/airflow/ingestion   # Importable from DAGs
  - ./transformation:/opt/airflow/transformation
  - ./analytics:/opt/airflow/analytics
  - ./.env:/opt/airflow/.env             # Loaded inside DAG functions
```

`PYTHONPATH=/opt/airflow` is set on all Airflow containers, making `ingestion`, `transformation`, and `analytics` importable as Python packages.

**DAG hot-reload:** The scheduler polls `dags/` every 30 seconds. Changes to DAG files are picked up without container restart. This is why imports inside DAG functions (not at module level) are important — they are re-evaluated on each task execution, not on scheduler parse.

---

## Database Schema

### `raw_series`

Immutable ingestion record. Every validated data point from every source lands here.

```sql
CREATE TABLE IF NOT EXISTS raw_series (
    id SERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL,       -- 'fred', 'yfinance'
    series_id VARCHAR(100) NOT NULL,   -- source-specific ID e.g. 'DCOILWTICO'
    series_key VARCHAR(100) NOT NULL,  -- internal key e.g. 'WTI'
    date DATE NOT NULL,
    value FLOAT NOT NULL,
    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_raw_source_series_date UNIQUE(source, series_id, date)
);
```

**Idempotency:** `ON CONFLICT (source, series_id, date) DO UPDATE SET value = EXCLUDED.value, ingested_at = NOW()`. Re-running the ingestion DAG for the same date range updates existing records rather than failing or duplicating.

**Why not `series_name` and `unit`?** These are derivable from `SERIES_CONFIG` using `series_key`. Storing them would create redundancy — 72 WTI records all with `series_name = "WTI Crude Oil Price"`. The `series_key` foreign key into the config is sufficient.

### `normalized_series`

Cleaned, aligned, enriched data. The analytics layer reads exclusively from this table.

```sql
CREATE TABLE IF NOT EXISTS normalized_series (
    id SERIAL PRIMARY KEY,
    series_id VARCHAR(100) NOT NULL,
    series_name VARCHAR(255) NOT NULL,
    category VARCHAR(50) NOT NULL,
    date DATE NOT NULL,
    value FLOAT NOT NULL,
    pct_change FLOAT,
    zscore_252d FLOAT,
    is_forward_filled BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT unique_normalized_series_date UNIQUE(series_id, date)
);
```

### `daily_snapshot`

One row per series per day. Materialized current state for fast API reads.

```sql
CREATE TABLE IF NOT EXISTS daily_snapshot (
    id SERIAL PRIMARY KEY,
    series_id VARCHAR(100) NOT NULL,
    date DATE NOT NULL,
    value FLOAT,
    pct_change FLOAT,
    zscore_252d FLOAT,
    anomaly_flag BOOLEAN,
    CONSTRAINT unique_snapshot_series_date UNIQUE(series_id, date)
);
```

### `correlation_results`

```sql
CREATE TABLE IF NOT EXISTS correlation_results (
    id SERIAL PRIMARY KEY,
    series_a VARCHAR(100) NOT NULL,
    series_b VARCHAR(100) NOT NULL,
    window_days INT NOT NULL,
    date DATE NOT NULL,
    pearson_r FLOAT,
    p_value FLOAT,
    n_observations INT,
    CONSTRAINT unique_correlation UNIQUE(series_a, series_b, window_days, date)
);
```

### `regression_results`

```sql
CREATE TABLE IF NOT EXISTS regression_results (
    id SERIAL PRIMARY KEY,
    dependent VARCHAR(100) NOT NULL,
    independent VARCHAR(100) NOT NULL,
    window_days INT NOT NULL,
    date DATE NOT NULL,
    beta FLOAT,
    r_squared FLOAT,
    p_value FLOAT,
    vif FLOAT
);
```

**Implementation note:** The current implementation uses a fixed model (SP500 ~ WTI + FED_FUNDS + T10Y) and stores flat per-variable columns (`beta_wti`, `beta_fed`, `beta_t10y`, `p_value_wti`, `p_value_fed`, `p_value_t10y`, `vif_wti`, `vif_fed`, `vif_t10y`, `r_squared`, `date`) with `UNIQUE(date)`. See `postgres_gate.py` → `upload_regression_results` for the actual DDL.

### `lag_results`

```sql
CREATE TABLE IF NOT EXISTS lag_results (
    id SERIAL PRIMARY KEY,
    series_a VARCHAR(100) NOT NULL,
    series_b VARCHAR(100) NOT NULL,
    lag_days INT NOT NULL,
    date DATE NOT NULL,
    pearson_r FLOAT,
    p_value FLOAT,
    CONSTRAINT unique_lag UNIQUE(series_a, series_b, lag_days, date)
);
```

One row per pair per lag value. `date` is the end date of the full data window used for the computation. Pairs and lags are defined in `analytics/lag_analysis.py`.

### `anomaly_flags`

```sql
CREATE TABLE IF NOT EXISTS anomaly_flags (
    id SERIAL PRIMARY KEY,
    series_id VARCHAR(100) NOT NULL,
    date DATE NOT NULL,
    zscore FLOAT,
    direction VARCHAR(10),             -- 'high' or 'low'
    threshold FLOAT,
    resolved BOOLEAN DEFAULT FALSE,
    CONSTRAINT unique_anomaly UNIQUE(series_id, date)
);
```

---

## Why PostgreSQL and Not a Columnar Store

A common interview question. The justified answer:

The dataset is small — 15 series × 252 trading days × 20 years = ~75,000 rows in `normalized_series`. PostgreSQL handles this trivially. A columnar store (Redshift, BigQuery, ClickHouse) adds operational complexity and cost without benefit at this scale.

The analytics layer reads data via pandas, which does its own vectorized computation in memory. It does not rely on database-level column-optimized scans. PostgreSQL's row-oriented storage is fine when the bottleneck is Python computation, not database I/O.

**When the answer would change:** At 10,000 series with 20 years of history (~500M rows), the query `SELECT * FROM normalized_series WHERE series_id IN (...)` becomes slow. At that point, partitioning by `series_id` or migrating to a columnar store would be justified.

---

## Why LocalExecutor and Not CeleryExecutor

CeleryExecutor enables true distributed task execution across multiple worker machines. It requires Redis as a message broker and adds operational complexity.

For a single-VPS deployment running 4 DAGs with ~15 total tasks per day, LocalExecutor executes tasks directly in the scheduler process. One fewer moving part, one fewer failure mode.

**When the answer would change:** Multiple worker nodes, hundreds of DAGs, or tasks that need to be isolated from the scheduler process. At that scale, CeleryExecutor with Redis is the standard choice.

---

## S3 Archival Strategy

Raw API payloads are archived to S3 before validation. This provides:
- **Recoverability:** If a bug corrupts `raw_series`, replay from S3 archives
- **Auditability:** Every data point is traceable to an archived JSON file with a specific date

**Path structure:**
```
s3://macro-lens/
  raw_payload/
    fred/
      DCOILWTICO/
        20260420_040023_123456.json    ← timestamp, not date (multiple runs per day safe)
      FEDFUNDS/
        20260420_040023_234567.json
    yfinance/
      ^GSPC/
        20260420_040031_345678.json
```

**Note on filename format:** The actual key uses `{YYYYMMDD_HHMMSS_ffffff}.json` (datetime + microseconds), not `{date}.json`. This means multiple runs on the same day produce separate archive files with no overwrite risk.

**Cost estimate:** ~500KB/day uncompressed. At 20 years of backfill: ~365MB. S3 Standard pricing: < $0.01/month. Negligible.

**IAM policy:** The `Macro-Lens-User` IAM user has `AmazonS3FullAccess` scoped to the `macro-lens` bucket only. No other AWS permissions are granted.

---

## Key Interview Questions

**Q: What happens when a DAG fails halfway through?**

The `ON CONFLICT DO UPDATE` upsert strategy means partial runs are safe. If `load_fred` fails after loading 3 of 5 series, re-triggering the DAG will load all 5 series — the 3 already loaded will be updated in place, not duplicated. S3 archives are append-only and do not need rollback. The raw payload is archived in the first task, so even if loading fails, the data is preserved in S3 for manual recovery.

**Q: How would you scale this to 500 series?**

Four changes: (1) Replace row-by-row `cursor.execute` with `cursor.executemany` or `copy_expert` for bulk inserts. (2) Add `series_id` index to all tables — currently only the UNIQUE constraint provides indexing. (3) Parallelize DAG tasks using Airflow's dynamic task mapping so each series runs as an independent task. (4) Consider partitioning `normalized_series` by `series_id` or date range. The adapter and validator layers are already source-agnostic — no changes needed there.

**Q: How do you manage secrets?**

Environment variables loaded from `.env` file, never committed to Git. `.env.example` with placeholder values is committed as documentation. Inside Docker containers, sensitive values are passed via `environment:` in `docker-compose.yml` and not written to any logs. AWS credentials are IAM user keys with least-privilege S3 access only.
