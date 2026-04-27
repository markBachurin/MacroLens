# MacroLens — Transformation Layer

## Overview

The transformation layer takes validated raw records from `raw_series` and produces analysis-ready data in `normalized_series` and `daily_snapshot`. It solves three problems that raw ingested data cannot solve on its own:

1. **Frequency alignment** — FRED and yfinance operate on different calendars. Monthly series (CPI, Fed Funds Rate) need to be aligned to a daily business day index before they can be correlated with daily equity prices.
2. **Gap filling** — Financial markets are closed on weekends and holidays. Gaps must be forward-filled so that every series has a value on every business day.
3. **Derived metrics** — Raw prices are not directly comparable. Percentage change and rolling z-score normalize series onto comparable scales for statistical analysis.

---

## Directory Structure

```
transformation/
├── __init__.py
├── normalizer.py        ← Reindex, forward-fill, pct_change, z-score
├── derived_series.py    ← Computed series not available from raw sources
└── snapshot_builder.py ← Writes daily_snapshot table
```

---

## Component: `normalizer.py`

The core transformation. Reads from `raw_series`, applies all normalization steps, writes to `normalized_series`.

### Processing Pipeline (per series)

```
raw_series (DB)
    │
    ▼
pandas DataFrame
    │
    ├─ resample to business day calendar
    │
    ├─ forward-fill gaps (max 5 days for daily series)
    │      └─ forward-fill until next update (monthly series)
    │
    ├─ compute pct_change
    │      └─ (value_today - value_yesterday) / value_yesterday
    │
    ├─ compute zscore_252d
    │      └─ (value - rolling_252d_mean) / rolling_252d_std
    │
    └─ write to normalized_series (UPSERT)
```

### Resampling Strategy

The implementation uses `pd.bdate_range` to build a full business-day index, then `reindex` to align raw data to it — not `resample`:

```python
full_index = pd.bdate_range(start=s.index.min(), end=pd.Timestamp.today())
original_dates = set(s.index)
s = s.reindex(full_index)
is_forward_filled = pd.Series(
    data=[date not in original_dates for date in full_index],
    index=full_index
)
```

This produces an `is_forward_filled` mask before forward-filling, allowing the loader to correctly tag which values were gap-filled vs originally present.

### Forward-Fill Rules

**Daily series** (WTI, Brent, S&P 500, NASDAQ, Gold, T10Y):
```python
df.fillna(method='ffill', limit=5)
```
Maximum 5 business days forward-filled. This covers weekends (2 days) and most holidays. If a gap exceeds 5 days, it remains NaN and is flagged. The `is_forward_filled` column is set to `True` for all filled values.

**Monthly series** (CPI, FED_FUNDS):
```python
df.fillna(method='ffill')  # no limit
```
Monthly series are valid as "last known value" until the next release. CPI from January is the correct CPI for February 1st if February's CPI has not yet been released. No limit is appropriate here — this is not a gap, it is the correct economic interpretation.

### Percentage Change

```python
df['pct_change'] = df['value'].pct_change()
```

Daily percentage change. The first row is NaN (no prior value). This is the input to all downstream statistical calculations. **Correlation and regression are computed on percentage changes, not raw levels.** This is a critical design decision documented in the analytics layer.

### Rolling Z-Score (252-day)

```python
rolling_mean = df['value'].rolling(252).mean()
rolling_std = df['value'].rolling(252).std()
df['zscore_252d'] = (df['value'] - rolling_mean) / rolling_std
```

252 trading days ≈ 1 calendar year. The z-score measures how many standard deviations today's value is from its trailing 1-year mean. Used by the anomaly detector.

First 251 rows have NaN z-score (insufficient history). This is expected and handled gracefully in the anomaly detector.

---

## Component: `derived_series.py`

Computes series that are not directly available from any source but are analytically meaningful.

### Derived Series

**Yield Curve Spread (10Y - 2Y)**
```python
spread = t10y_series - t2y_series
```
The yield curve spread is a leading indicator of recession. When negative (inverted yield curve), it has historically preceded recessions by 12-18 months. Computed as a derived series rather than fetched directly.

**Real Oil Price (WTI / CPI-adjusted)**
```python
real_oil = wti_series / (cpi_series / cpi_base_value)
```
Nominal WTI prices are distorted by inflation. Real oil price allows fair comparison across decades.

**WTI / S&P 500 Ratio**
```python
wti_sp500_ratio = wti_series / sp500_series * 1000
```
Measures oil price relative to equity market level. Scaled by 1000 for readability.

### Implementation Note

Derived series are written to `normalized_series` with a `category` of `"derived"`. They have entries in `SERIES_CONFIG` with `"source": "derived"` (keys: `YIELD_SPREAD`, `REAL_WTI`, `WTI_SP500`) but no corresponding rows in `raw_series` — they are computed entirely within the transformation layer.

---

## Component: `snapshot_builder.py`

Writes one row per series per day to `daily_snapshot`. This table is the primary data source for the API's `/api/snapshot/latest/` endpoint — a single query returns the current state of all 15 series (12 sourced + 3 derived).

### Logic

For each series in `normalized_series` for today's date:
- Write `value`, `pct_change`, `zscore_252d`
- Set `anomaly_flag = True` if `abs(zscore_252d) > 2.5`
- Upsert on `(series_id, date)`

The snapshot table is effectively a materialized view of today's state. It avoids complex queries at API read time.

---

## Airflow DAG: `transform`

Located at `dags/transform.py`. Runs on a fixed schedule — no `ExternalTaskSensor` in the current implementation. Relies on timing to ensure ingestion has completed first.

```
normalize → compute_derived → build_snapshots
```

### Schedule

```python
schedule = "0 5 * * *"  # 05:00 UTC daily
```

`catchup=False`, `start_date=2026-01-01`. Runs one hour after ingestion DAGs (04:00 UTC), giving ingestion a full hour window to complete.

---

## Database: `normalized_series`

| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | |
| `series_id` | VARCHAR(100) NOT NULL | Internal key e.g. `WTI` |
| `series_name` | VARCHAR(255) NOT NULL | Human readable |
| `category` | VARCHAR(50) NOT NULL | `energy`, `equity`, `rates`, `macro`, `derived` |
| `date` | DATE NOT NULL | Business day |
| `value` | FLOAT NOT NULL | Normalized value |
| `pct_change` | FLOAT | Daily percentage change |
| `zscore_252d` | FLOAT | Rolling 1-year z-score |
| `is_forward_filled` | BOOLEAN NOT NULL DEFAULT FALSE | Gap-fill flag |

`UNIQUE(series_id, date)`

## Database: `daily_snapshot`

| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | |
| `series_id` | VARCHAR(100) NOT NULL | |
| `date` | DATE NOT NULL | |
| `value` | FLOAT | |
| `pct_change` | FLOAT | |
| `zscore_252d` | FLOAT | |
| `anomaly_flag` | BOOLEAN | True if \|zscore\| > 2.5 |

`UNIQUE(series_id, date)`

---

## Key Interview Questions

**Q: Why forward-fill instead of interpolate?**

Forward-fill ("last observation carried forward") is the correct economic interpretation. If the Fed Funds Rate is 5.33% on March 1st, it is 5.33% on March 2nd — the rate did not smoothly interpolate to a new value. Linear interpolation would imply knowledge of the future, which is not available in real-time.

**Q: Why 252 days for the z-score window?**

252 is the approximate number of trading days in a calendar year. Using a 1-year rolling window captures a full economic cycle's worth of daily variation while being responsive enough to detect anomalies within the current regime. A shorter window (e.g. 30 days) would be too sensitive to recent volatility. A longer window (e.g. 504 days) would be too slow to flag genuine anomalies.

**Q: How do you handle the first 251 days of z-score being NaN?**

They are stored as NULL in the database. The anomaly detector explicitly skips NULL z-scores. The API returns NULL for these values and the dashboard renders them as gaps. This is preferable to imputing values, which would generate false anomaly signals.

**Q: What happens if a series has a gap longer than 5 days?**

The `is_forward_filled` flag is not set for these rows — they remain NaN. The analytics layer uses `dropna()` before computing correlations, so these rows are excluded from statistical calculations. The daily snapshot marks these as missing values rather than silently imputing them.
