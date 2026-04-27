from ingestion.loaders.postgres_gate import Postgres_Client
import pandas as pd
from scipy.stats import pearsonr,ConstantInputWarning
import warnings

warnings.filterwarnings("ignore", category=ConstantInputWarning)

CORRELATION_PAIRS = [
    ("DCOILWTICO", "^GSPC"),
    ("DCOILWTICO", "GC=F"),
    ("DCOILWTICO", "CPIAUCSL"),
    ("FEDFUNDS", "^GSPC"),
    ("FEDFUNDS", "GC=F"),
    ("DGS10", "^GSPC"),
    ("DGS10", "DCOILWTICO"),
    ("^GSPC", "^IXIC"),
    ("^VIX", "^GSPC"),
]

WINDOWS = [30, 90, 252]

def compute_correlations() -> None:
    gate = Postgres_Client()

    series_ids=set()
    for a,b in CORRELATION_PAIRS:
        series_ids.add(a)
        series_ids.add(b)

    series_map={}
    for series_id in series_ids:
        rows = gate.query_normalized_by_series_id(series_id)
        series_map[series_id] = to_pct_change_series(rows)

    records = []
    for series_a, series_b in CORRELATION_PAIRS:
        print(f"Computing {series_a} vs {series_b}...")
        a = series_map[series_a]
        b = series_map[series_b]

        # align on same dates
        df = pd.DataFrame({"a": a, "b": b}).dropna()

        for window in WINDOWS:
            window_records = compute_rolling_correlation(df, series_a, series_b, window)
            records.extend(window_records)

    gate.upload_correlations(records)
    gate.close()

def compute_rolling_correlation(
        df: pd.DataFrame,
        series_a: str,
        series_b: str,
        window: int
    )   -> list[dict]:
    records=[]

    for i in range(window, len(df)):
        window_df = df.iloc[i - window:i]

        if len(window_df.dropna()) < window * 0.8:
            continue

        try:
            if window_df["a"].std() == 0 or window_df["b"].std() == 0:
                continue
            r, p = pearsonr(window_df["a"], window_df["b"])
            records.append({
                "series_a": series_a,
                "series_b": series_b,
                "window_days": window,
                "date": df.index[i].strftime("%Y-%m-%d"),
                "pearson_r": float(r),
                "p_value": float(p),
                "n_observations": len(window_df.dropna()),
            })
        except Exception:
            continue
    return records

def to_pct_change_series(rows: list) -> pd.Series:
    s = pd.Series(
        data=[row[1] for row in rows],
        index=pd.to_datetime([row[0] for row in rows])
    )

    return s.pct_change()
