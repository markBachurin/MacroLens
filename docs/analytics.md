# MacroLens — Analytics Layer

## Overview

The analytics layer computes statistical relationships between macroeconomic series. It reads from `normalized_series` and writes results to three tables: `correlation_results`, `regression_results`, and `anomaly_flags`.

All statistical computations operate on **daily percentage changes**, not raw price levels. This is a fundamental design decision explained in detail below.

---

## Directory Structure

```
analytics/
├── __init__.py
├── correlations.py      ← Rolling Pearson correlation for all series pairs
├── regression.py        ← OLS regression, VIF computation
└── lag_analysis.py      ← Cross-correlation at multiple lags
```

**Note:** Anomaly detection is not a separate module. The `anomaly_flag` column is computed in `transformation/snapshot_builder.py` when writing to `daily_snapshot`: `abs(zscore_252d) > 2.5`.

---

## Why Percentage Changes, Not Raw Levels

Computing Pearson correlation on raw price levels produces **spurious correlation**. S&P 500 and WTI crude have both generally trended upward over 20 years. Their correlation on raw levels approaches 1.0 — not because they are economically related, but because they share a common upward trend.

Daily percentage changes remove this trend. The correlation on returns measures genuine co-movement: does a 2% drop in WTI today coincide with a 1% drop in equities today? This is the economically meaningful question.

This decision is documented explicitly because it is a common interview question and a common mistake in financial data analysis.

---

## Component: `correlations.py`

### Algorithm

For each pair of series, compute Pearson r over three rolling windows: 30, 90, and 252 trading days.

```python
from scipy.stats import pearsonr
import pandas as pd

def compute_rolling_correlation(series_a: pd.Series, series_b: pd.Series, window: int) -> pd.DataFrame:
    results = []
    for i in range(window, len(series_a)):
        a_window = series_a.iloc[i-window:i]
        b_window = series_b.iloc[i-window:i]
        
        # drop dates where either series has NaN
        mask = a_window.notna() & b_window.notna()
        a_clean = a_window[mask]
        b_clean = b_window[mask]
        
        if len(a_clean) < window * 0.8:  # require 80% data completeness
            continue
            
        r, p_value = pearsonr(a_clean, b_clean)
        results.append({
            "date": series_a.index[i],
            "pearson_r": r,
            "p_value": p_value,
            "n_observations": len(a_clean),
        })
    return pd.DataFrame(results)
```

### Series Pairs

```
WTI      ↔  S&P 500       (energy ↔ equity)
WTI      ↔  Gold          (energy ↔ safe haven)
WTI      ↔  CPI           (energy ↔ inflation)
WTI      ↔  Brent         (sanity check — should be ~0.98)
FED_FUNDS ↔ S&P 500       (monetary policy ↔ equity)
FED_FUNDS ↔ Gold          (monetary policy ↔ safe haven)
T10Y     ↔  S&P 500       (rates ↔ equity)
T10Y     ↔  WTI           (rates ↔ energy)
S&P 500  ↔  NASDAQ        (sanity check — should be ~0.99)
```

### Output Schema (`correlation_results`)

| Column | Type | Notes |
|---|---|---|
| `series_a` | VARCHAR(100) | Internal key of first series |
| `series_b` | VARCHAR(100) | Internal key of second series |
| `window_days` | INT | 30, 90, or 252 |
| `date` | DATE | End date of the rolling window |
| `pearson_r` | FLOAT | Range: -1 to +1 |
| `p_value` | FLOAT | Statistical significance |
| `n_observations` | INT | Actual non-null observations used |

`UNIQUE(series_a, series_b, window_days, date)`

### Interpreting Results

- `pearson_r = 0.6` — 60% of the variance in series B's daily returns is explained by linear co-movement with series A.
- `p_value < 0.05` — the correlation is statistically significant at the 5% level.
- `n_observations < window * 0.8` — insufficient data, result excluded.

**Known finding from the data:** WTI and S&P 500 30-day rolling correlation ranges from -0.4 to +0.8 over 20 years. The relationship is regime-dependent — it is strongly positive during risk-on periods and weakly negative or zero during supply shocks. This is why rolling windows are essential: a single static correlation hides this variation.

---

## Component: `regression.py`

### OLS Regression

Uses `statsmodels.OLS` with rolling 252-day windows.

**Primary regression:**
```
S&P 500 daily returns = β₀ + β₁(WTI return) + β₂(FED_FUNDS change) + β₃(T10Y change) + ε
```

**Univariate regressions** for every pair (WTI → CPI, T10Y → Gold, etc.)

### Implementation

```python
import statsmodels.api as sm
import pandas as pd

def compute_rolling_ols(y: pd.Series, X: pd.DataFrame, window: int) -> pd.DataFrame:
    results = []
    X_with_const = sm.add_constant(X)
    
    for i in range(window, len(y)):
        y_window = y.iloc[i-window:i]
        X_window = X_with_const.iloc[i-window:i]
        
        mask = y_window.notna() & X_window.notna().all(axis=1)
        
        model = sm.OLS(y_window[mask], X_window[mask]).fit()
        results.append({
            "date": y.index[i],
            "beta": model.params[1],        # slope coefficient
            "r_squared": model.rsquared,
            "p_value": model.pvalues[1],
        })
    return pd.DataFrame(results)
```

### VIF Computation

Variance Inflation Factor detects multicollinearity among independent variables.

```python
from statsmodels.stats.outliers_influence import variance_inflation_factor

def compute_vif(X: pd.DataFrame) -> dict:
    vif_data = {}
    for i, col in enumerate(X.columns):
        vif_data[col] = variance_inflation_factor(X.values, i)
    return vif_data
```

**Rule:** If VIF > 5 for any variable, it is flagged in `regression_results`. A VIF of 5 means the variable's variance is inflated 5× due to collinearity with other predictors, making beta estimates unreliable.

### Statistical Assumptions and Limitations

**Assumptions made:**
- Linearity: reasonable for short windows in normal market conditions
- Independence: daily returns are approximately independent (serial correlation is low for broad indices)

**Documented limitations:**
- **Heteroscedasticity:** Financial returns exhibit volatility clustering — periods of high volatility cluster together. OLS standard errors assume constant variance. In production, HAC-robust standard errors (Newey-West) would be used.
- **Regime changes:** The 2008 financial crisis and 2020 COVID shock create structural breaks. A 252-day window straddling either event will produce unreliable betas.
- **No causality:** Regression establishes association, not causation. A beta of 0.3 for WTI on S&P 500 means they co-move — it does not mean WTI causes equity returns.

### Output Schema (`regression_results`)

| Column | Type | Notes |
|---|---|---|
| `dependent` | VARCHAR(100) | Dependent variable key |
| `independent` | VARCHAR(100) | Independent variable key |
| `window_days` | INT | Rolling window size |
| `date` | DATE | End date of window |
| `beta` | FLOAT | Slope coefficient |
| `r_squared` | FLOAT | Model fit quality |
| `p_value` | FLOAT | Significance of beta |
| `vif` | FLOAT | Multicollinearity indicator |

**Implementation note:** The current model is fixed to one regression (SP500 ~ WTI + FED_FUNDS + T10Y) with a fixed 252-day window. The actual database columns are flat per-variable (`beta_wti`, `beta_fed`, `beta_t10y`, `p_value_wti`, `p_value_fed`, `p_value_t10y`, `vif_wti`, `vif_fed`, `vif_t10y`, `r_squared`, `date`) with `UNIQUE(date)`. The schema above reflects the logical design; see `ingestion/loaders/postgres_gate.py` → `upload_regression_results` for the exact DDL.

---

## Component: `lag_analysis.py`

### Purpose

Lag analysis answers: does series A **lead** or **lag** series B? For example: do oil price changes precede inflation changes, and by how many days?

### Algorithm

```python
def compute_lag_correlation(series_a: pd.Series, series_b: pd.Series, lag: int) -> tuple[float, float]:
    series_b_lagged = series_b.shift(-lag)  # positive lag = b leads a
    
    mask = series_a.notna() & series_b_lagged.notna()
    r, p = pearsonr(series_a[mask], series_b_lagged[mask])
    return r, p
```

**Lags computed:** 1, 5, 10, 20, 60 business days

**Interpretation:** If WTI vs CPI shows highest correlation at lag=20, oil price movements lead inflation by approximately 4 calendar weeks. This is economically plausible: energy costs take time to propagate through the supply chain into consumer prices.

### Limitation

With 9 pairs × 5 lags = 45 tests, some will appear significant by chance (multiple comparison problem). In production, Bonferroni correction would be applied: significance threshold becomes `0.05 / 45 = 0.001` instead of `0.05`. This is documented as a known limitation.

---

## Component: `anomaly_detector.py`

### Algorithm

```python
ANOMALY_THRESHOLD = float(os.getenv("ANOMALY_ZSCORE_THRESHOLD", "2.5"))

def detect_anomalies(series_id: str, date: str, zscore: float) -> bool:
    if zscore is None:
        return False
    return abs(zscore) > ANOMALY_THRESHOLD
```

### Threshold Justification

Z-score of 2.5 corresponds to approximately the 99th percentile of a normal distribution — a value occurring roughly 1.2% of the time. For 8 series with 252 trading days per year, this produces approximately 3-4 anomaly flags per year per series if returns were perfectly normal.

Financial returns have fat tails (kurtosis > 3), so actual anomaly frequency is higher. The threshold is configurable via `ANOMALY_ZSCORE_THRESHOLD` environment variable.

### Airflow Alert Callback

When new rows are written to `anomaly_flags`, an Airflow `on_success_callback` on the analytics DAG sends an email:

```python
def anomaly_alert_callback(context):
    # query anomaly_flags for today
    # if new flags exist, send email via Airflow's SMTP config
    # include: series name, current value, z-score, 30-day range
```

### Output Schema (`anomaly_flags`)

| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | |
| `series_id` | VARCHAR(100) NOT NULL | |
| `date` | DATE NOT NULL | |
| `zscore` | FLOAT | |
| `direction` | VARCHAR(10) | `high` or `low` |
| `threshold` | FLOAT | Value of threshold at detection time |
| `resolved` | BOOLEAN DEFAULT FALSE | Manually resolved flag |

`UNIQUE(series_id, date)`

---

## Airflow DAG: `analytics`

Located at `dags/analytics_dag.py`. Runs on a fixed schedule — no `ExternalTaskSensor`. Relies on timing alone to ensure the transform DAG has completed first.

```
compute_correlations → compute_regressions → compute_lag_analysis
```

### Schedule

```python
schedule = "0 6 * * *"  # 06:00 UTC daily
```

Runs one hour after the transform DAG (05:00 UTC). `catchup=False`, `start_date=2026-01-01`.

---

## Key Interview Questions

**Q: Why Pearson and not Spearman correlation?**

Pearson measures linear relationships and assumes approximate normality. Spearman is rank-based and distribution-free. For daily percentage returns of major financial indices, normality is approximately satisfied (with fat tails). Pearson is appropriate and its output (r) is directly interpretable as a linear co-movement measure. Spearman would be more appropriate for ordinal data or heavily skewed distributions.

**Q: What does R² = 0.15 mean for the S&P 500 regression?**

The model — WTI return, Fed Funds change, 10Y yield change — explains 15% of the variance in daily S&P 500 returns. The remaining 85% is unexplained. This is not a weak model for financial data — daily equity returns are notoriously noisy. The macroeconomic factors are meaningful signals, not the only signals.

**Q: How would you scale this to 500 series instead of 8?**

The current approach computes all pairwise correlations — O(n²) pairs. At 500 series this is 124,750 pairs × 3 windows = 374,250 computations per day. Two approaches: (1) pre-filter to only economically meaningful pairs using a domain-specific configuration, reducing pairs to ~100; (2) parallelize using Airflow's dynamic task mapping. The database upsert would also need batching — currently using row-by-row `executemany`, which would need to switch to `copy_expert` for bulk insert.

**Q: Are your correlations stable over time?**

No — and this is by design. The rolling window approach explicitly reveals regime changes. WTI and S&P 500 correlation is positive during demand-driven oil price increases (global growth) and negative or zero during supply shocks (OPEC cuts). A single static correlation hides this. The dashboard's time series view of rolling correlation is more informative than any single number.
