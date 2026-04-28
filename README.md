# MacroLens

A macroeconomic analysis pipeline that ingests financial data from multiple sources, computes rolling statistical indicators, and serves them through a REST API and live dashboard.

**Data sources:** FRED, yfinance, US Treasury, Alpha Vantage  
**Series tracked:** S&P 500, NASDAQ, WTI/Brent crude, 10Y/2Y Treasury yields, Fed Funds Rate, CPI, Gold, VIX, EUR/USD + 3 derived series  
**Analytics:** Rolling Pearson correlation, OLS regression with VIF, lag analysis, z-score anomaly detection

---

## Architecture

```
External APIs
(FRED, yfinance, Treasury, AlphaVantage)
        │
        ▼
  Airflow DAGs          ← ingest → validate → archive (S3) → load
        │
        ▼
   PostgreSQL           ← raw_series → normalized_series → daily_snapshot
        │                              correlation_results, regression_results, lag_results
        ▼
  Django REST API       ← 9 endpoints
        │
        ▼
  Chart.js Dashboard    ← 7 pages (Current Regime, Anomalies, Correlations, Macro Factors,
                                    Regression, Lag Analysis, Fear & Greed)
```

All services run in Docker Compose on a single machine.

---

## Prerequisites

- Docker + Docker Compose
- FRED API key — free at [fred.stlouisfed.org/docs/api/api_key.html](https://fred.stlouisfed.org/docs/api/api_key.html)
- Alpha Vantage API key — free at [alphavantage.co/support/#api-key](https://www.alphavantage.co/support/#api-key)
- AWS S3 bucket + IAM credentials (for raw data archival)

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/markBachurin/MacroLens.git
cd MacroLens
```

### 2. Create your `.env` file

```bash
cp .env.example .env
```

Then fill in your credentials:

```env
# API Keys
FRED_API_KEY=your_fred_api_key
ALPHA_VANTAGE_API_KEY=your_alphavantage_api_key

# PostgreSQL
DATABASE_URL=""
PG_HOST=localhost
PG_PORT=5432
PG_DB=macrolens
PG_USER=your_db_user
PG_PASSWORD=your_db_password

# Django
DEBUG=False
DJANGO_SECRET_KEY=your_secret_key_here

# AWS S3
AWS_ACCESS_KEY=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
S3_BUCKET=your_s3_bucket_name
```

### 3. Start all services

```bash
docker compose up -d
```

This starts: PostgreSQL, Airflow (webserver + scheduler), database initialisation, and the Django API.

First run takes 3–5 minutes to build images and initialise the Airflow DB.

### 4. Verify everything is running

```bash
docker compose ps
```

All services should show `running`. Check logs if anything is unhealthy:

```bash
docker compose logs <service_name> -f
```

---

## Accessing the stack

| Service | URL | Credentials |
|---|---|---|
| Airflow UI | `http://localhost:8080` | admin / admin |
| REST API | `http://localhost:8000/api/` | — |
| Dashboard | `http://localhost:8000/dashboard/` | — |

---

## Running the pipeline

### Trigger ingestion manually

In the Airflow UI (`http://localhost:8080`), enable and trigger these DAGs in order:

| DAG | Schedule | Description |
|---|---|---|
| `ingest_fred` | 04:00 UTC | WTI, Brent, Fed Funds, CPI, 10Y Treasury |
| `ingest_yfinance` | 04:00 UTC | S&P 500, NASDAQ, Gold, VIX |
| `ingest_treasury` | 04:00 UTC | 2Y Treasury yield |
| `ingest_alphavantage` | 04:00 UTC | EUR/USD |
| `transform` | 05:00 UTC | Normalise, forward-fill, compute z-scores |
| `analytics` | 06:00 UTC | Correlations, OLS regression, lag analysis |

Or trigger all ingestion DAGs via CLI:

```bash
docker compose exec airflow-webserver airflow dags trigger ingest_fred
docker compose exec airflow-webserver airflow dags trigger ingest_yfinance
docker compose exec airflow-webserver airflow dags trigger ingest_treasury
docker compose exec airflow-webserver airflow dags trigger ingest_alphavantage
```

Then once ingestion completes:

```bash
docker compose exec airflow-webserver airflow dags trigger transform
docker compose exec airflow-webserver airflow dags trigger analytics
```

The dashboard will populate once the `analytics` DAG finishes.

---

## API Endpoints

Base URL: `http://localhost:8000/api/`

| Method | Endpoint | Description |
|---|---|---|
| GET | `/series/` | All 15 series with metadata |
| GET | `/series/<id>/` | Normalised history. Params: `?limit=252&offset=0` |
| GET | `/snapshot/latest/` | Latest value + z-score + anomaly flag per series |
| GET | `/correlations/` | Latest correlation matrix. Param: `?window=30\|90\|252` |
| GET | `/correlations/<a>/<b>/` | Rolling correlation history for one pair |
| GET | `/regression/latest/` | Latest OLS regression result |
| GET | `/regression/history/` | Full beta + R² history |
| GET | `/anomalies/` | Series flagged anomalous in the last 14 days |
| GET | `/lag/` | All lag analysis results |

---

## Running tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v
```

73 tests covering adapters, loaders, transformation, validators, and DAG structure.

---

## Adding a new data series

1. Add an entry to `ingestion/config/series_config.py`:

```python
"MY_SERIES": {
    "source": "fred",          # fred | yfinance | treasury | alphavantage
    "series_id": "SERIES_ID",
    "name": "My Series Name",
    "unit": "USD",
    "category": "macro",
    "valid_min": 0.0,
    "valid_max": 1000.0,
    "frequency": "daily",      # daily | monthly
},
```

2. That's it. The series will be picked up by the relevant ingest DAG on its next run.

---

## Project structure

```
MacroLens/
├── dags/                   # Airflow DAGs (ingest, transform, analytics)
├── ingestion/
│   ├── adapters/           # FRED, yfinance, Treasury, AlphaVantage clients
│   ├── loaders/            # PostgreSQL and S3 write clients
│   ├── validators/         # Data quality checks
│   └── config/             # Series metadata (single source of truth)
├── transformation/         # Normalisation, forward-fill, z-scores, derived series
├── analytics/              # Rolling correlations, OLS regression, lag analysis
├── api/                    # Django REST API + dashboard templates
├── dashboard/              # Chart.js frontend (static JS + HTML templates)
├── scripts/                # DB initialisation
├── tests/                  # pytest test suite
└── docs/                   # Deep-dive documentation per layer
```

---

## Documentation

Detailed technical documentation is in `docs/`:

- [`docs/ingestion.md`](docs/ingestion.md) — adapters, validation, S3 archival
- [`docs/transformation.md`](docs/transformation.md) — normalisation, z-scores, derived series
- [`docs/analytics.md`](docs/analytics.md) — correlation, regression, lag analysis methodology
- [`docs/api.md`](docs/api.md) — all endpoints, Django models, dashboard pages
- [`docs/infrastructure.md`](docs/infrastructure.md) — Docker Compose, Airflow setup, deployment
- [`docs/frontend.md`](docs/frontend.md) — Chart.js dashboard architecture