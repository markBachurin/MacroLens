import pandas as pd
from ingestion.loaders.postgres_gate import Postgres_Client
from transformation.normalizer import compute_pct_change, compute_252d_zscore

def compute_derived() -> None:
    postgres_client = Postgres_Client()

    t10y, t2y, wti, cpi, sp500 = get_series(postgres_client)

    df = to_df(t10y, t2y, wti, cpi, sp500)

    df = get_derived_metrics(df)

    upload_df(df, postgres_client)

    postgres_client.close()


def get_series(postgres_client: Postgres_Client):
    t10y = to_series(postgres_client.query_normalized_by_series_id("DGS10"))
    t2y = to_series(postgres_client.query_normalized_by_series_id("BC_2YEAR"))
    wti = to_series(postgres_client.query_normalized_by_series_id("DCOILWTICO"))
    cpi = to_series(postgres_client.query_normalized_by_series_id("CPIAUCSL"))
    sp500 = to_series(postgres_client.query_normalized_by_series_id("^GSPC"))
    return t10y, t2y, wti, cpi, sp500

def to_series(rows: list) -> pd.Series:
    return pd.Series(
        data=[row[1] for row in rows],
        index=pd.to_datetime([row[0] for row in rows])
    )

def to_df(t10y: pd.Series, t2y: pd.Series, wti: pd.Series, cpi: pd.Series, sp500: pd.Series) -> pd.DataFrame:
    return pd.DataFrame({
        "T10Y": t10y,
        "T2Y": t2y,
        "WTI": wti,
        "CPI": cpi,
        "SP500": sp500
    })

def get_derived_metrics(df: pd.DataFrame) -> pd.DataFrame:
    # each derived series only drops nulls for its own required columns
    yield_mask = df["T10Y"].notna() & df["T2Y"].notna()
    df.loc[yield_mask, "yield_spread"] = df.loc[yield_mask, "T10Y"] - df.loc[yield_mask, "T2Y"]

    wti_cpi_mask = df["WTI"].notna() & df["CPI"].notna()
    cpi_base = df.loc[wti_cpi_mask, "CPI"].iloc[0]
    df.loc[wti_cpi_mask, "real_wti"] = df.loc[wti_cpi_mask, "WTI"] * (cpi_base / df.loc[wti_cpi_mask, "CPI"])

    ratio_mask = df["WTI"].notna() & df["SP500"].notna()
    df.loc[ratio_mask, "wti_sp500_ratio"] = df.loc[ratio_mask, "WTI"] / df.loc[ratio_mask, "SP500"] * 1000

    return df

def upload_df(df: pd.DataFrame, postgres_client: Postgres_Client) -> None:
    import math
    for series_key, new_column in [
        ("YIELD_SPREAD", "yield_spread"),
        ("REAL_WTI", "real_wti"),
        ("WTI_SP500", "wti_sp500_ratio"),
    ]:
        s = df[new_column].dropna()
        pct_change = compute_pct_change(s)
        zscore = compute_252d_zscore(s)

        records = [
            {
                "date": date.strftime("%Y-%m-%d"),
                "value": float(value),
                "pct_change": float(pct_change.get(date)) if pd.notna(pct_change.get(date)) and math.isfinite(pct_change.get(date)) else None,
                "zscore_252d": float(zscore.get(date)) if pd.notna(zscore.get(date)) and math.isfinite(zscore.get(date)) else None,
                "is_forward_filled": False,
            }
            for date, value in s.items()
            if pd.notna(value)
        ]

        postgres_client.upload_normalized_series(records, series_key)