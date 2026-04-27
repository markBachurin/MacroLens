import warnings
import numpy as np
import pandas as pd

import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor
from ingestion.loaders.postgres_gate import Postgres_StorageGate
from analytics.correlations import to_pct_change_series


WINDOW = 252

def compute_regression() -> None:
    gate = Postgres_StorageGate()

    sp500 = to_pct_change_series(gate.query_normalized_by_series_id("^GSPC"))
    wti = to_pct_change_series(gate.query_normalized_by_series_id("DCOILWTICO"))
    fed = to_pct_change_series(gate.query_normalized_by_series_id("FEDFUNDS"))
    t10y = to_pct_change_series(gate.query_normalized_by_series_id("DGS10"))

    df =  pd.DataFrame({
        "sp500": sp500,
        "wti": wti,
        "fed": fed,
        "t10y": t10y,
    }).dropna()

    records = []
    for i in range(WINDOW, len(df)):
        window_df = df.iloc[i - WINDOW:i]

        record = run_ols(window_df, df.index[i])
        if record:
            records.append(record)

    gate.upload_regression_results(records)
    gate.close()

def run_ols(window_df: pd.DataFrame, date) -> dict | None:
    y = window_df["sp500"]
    X = window_df[["wti", "fed","t10y"]]

    X = sm.add_constant(X)

    if y.std() == 0:
        return None

    # skip window if any independent variable is const
    if X["fed"].std() == 0 or X["t10y"].std() == 0 or X["wti"].std() == 0:
        return None


    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = sm.OLS(y,X).fit()
        if np.isnan(model.rsquared):
            return None

        # compute VIF for each independent variable
        vif_wti = variance_inflation_factor(X.values, 1)
        vif_fed = variance_inflation_factor(X.values, 2)
        vif_t10y = variance_inflation_factor(X.values, 3)

        return {
            "date": date.strftime("%Y-%m-%d"),
            "beta_wti": float(model.params["wti"]),
            "beta_fed": float(model.params["fed"]),
            "beta_t10y": float(model.params["t10y"]),
            "r_squared": float(model.rsquared),
            "p_value_wti": float(model.pvalues["wti"]),
            "p_value_fed": float(model.pvalues["fed"]),
            "p_value_t10y": float(model.pvalues["t10y"]),
            "vif_wti": float(vif_wti),
            "vif_fed": float(vif_fed),
            "vif_t10y": float(vif_t10y),
        }
    except Exception:
        return None