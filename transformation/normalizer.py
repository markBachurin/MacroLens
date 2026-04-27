import pandas as pd
from ingestion.config.series_config import SERIES_CONFIG
from ingestion.loaders.postgres_gate import Postgres_StorageGate


def normalize():
    gate = Postgres_StorageGate()

    for series_key, data in SERIES_CONFIG.items():
        rows = gate.query_raw_by_series_key(series_key)

        if not rows:
            continue

        s = pd.Series(
            data=[row[1] for row in rows],
            index=pd.to_datetime([row[0] for row in rows])
        )

        s, is_forward_filled_mask = forward_fill(s, data["frequency"])
        pct_change = compute_pct_change(s)
        zscore = compute_252d_zscore(s)

        records = prepare(s, pct_change, zscore, is_forward_filled_mask)

        gate.upload_normalized_series(records, series_key)

    gate.close()

def prepare(s: pd.Series, pct_change: pd.Series, zscore: pd.Series, is_forward_filled: pd.Series) -> list[dict]:
    return [
        {"date": date.strftime("%Y-%m-%d"),
         "value": float(value),
         "pct_change": float(pct_change.get(date)) if pd.notna(pct_change.get(date)) else None,
         "zscore_252d": float(zscore.get(date)) if pd.notna(zscore.get(date)) else None,
        "is_forward_filled": bool(is_forward_filled.get(date))
         }
        for date, value in s.items()
        if pd.notna(value)
    ]

def forward_fill(s: pd.Series, frequency: str):
    full_index = pd.bdate_range(
        start=s.index.min(),
        end=pd.Timestamp.today()
    )

    original_dates = set(s.index)

    s = s.reindex(full_index)

    is_forward_filled = pd.Series(
        data=[date not in original_dates for date in full_index],
        index=full_index
    )

    limit = None if frequency == "monthly" else 5
    return s.ffill(limit=limit), is_forward_filled


def compute_pct_change(s: pd.Series) -> pd.Series:
    return s.pct_change()

def compute_252d_zscore(s: pd.Series) -> pd.Series:
    rolling_mean = s.rolling(window=252).mean()
    rolling_std = s.rolling(window=252).std()

    return (s - rolling_mean) / rolling_std
