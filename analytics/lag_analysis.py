import pandas as pd
from scipy.stats import pearsonr
from ingestion.loaders.postgres_gate import Postgres_StorageGate
from analytics.correlations import to_pct_change_series

LAG_PAIRS = [
    ("DCOILWTICO", "CPIAUCSL"),   # does oil lead inflation?
    ("DCOILWTICO", "^GSPC"),      # does oil lead stocks?
    ("FEDFUNDS", "^GSPC"),        # does fed rate lead stocks?
    ("FEDFUNDS", "GC=F"),         # does fed rate lead gold?
    ("DGS10", "^GSPC"),           # does 10Y yield lead stocks?
    ("DGS10", "DCOILWTICO"),      # does 10Y yield lead oil?
    ("^VIX", "^GSPC"),            # does fear lead stocks?
]

LAGS = [1,5,10,20,60]

def compute_lag_analysis() -> None:
    gate = Postgres_StorageGate()

    series_ids = set()
    for a, b in LAG_PAIRS:
        series_ids.add(a)
        series_ids.add(b)

    series_map = {}
    for series_id in series_ids:
        rows = gate.query_normalized_by_series_id(series_id)
        series_map[series_id] = to_pct_change_series(rows)

    records = []
    for series_a, series_b in LAG_PAIRS:
        a = series_map[series_a]
        b = series_map[series_b]

        df = pd.DataFrame({"a": a, "b": b}).dropna()

        for lag in LAGS:
            record = compute_lag(df, series_a, series_b, lag)
            if record:
                records.append(record)

    gate.upload_lag_results(records)
    gate.close()


def compute_lag(
        df: pd.DataFrame,
        series_a: str,
        series_b: str,
        lag: int
    ) -> dict | None:
    a = df["a"]
    b_lagged = df["b"].shift(-lag)

    combined = pd.DataFrame({"a":a, "b": b_lagged}).dropna()

    if len(combined) < 100:
        return None

    if combined["a"].std() == 0 or combined["b"].std() == 0:
        return None

    try:
        r, p = pearsonr(combined["a"], combined["b"])
        return {
            "series_a": series_a,
            "series_b": series_b,
            "lag_days": lag,
            "date": df.index[-1].strftime("%Y-%m-%d"),
            "pearson_r": float(r),
            "p_value": float(p),
        }
    except Exception:
        return None


