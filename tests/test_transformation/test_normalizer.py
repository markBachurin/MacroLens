import pytest
import pandas as pd
import numpy as np

from transformation.normalizer import (
    forward_fill,
    compute_pct_change,
    compute_252d_zscore,
    prepare,
)

# forward fill

class TestForwardFill:
    def test_fills_missing_business_days(self):
        # Mon + Wed only — Tue should be filled
        s = pd.Series(
            [100.0, 102.0],
            index=pd.to_datetime(["2024-01-01", "2024-01-03"])
        )
        filled, mask = forward_fill(s, frequency="daily")

        assert pd.Timestamp("2024-01-02") in filled.index
        assert filled["2024-01-02"] == 100.0
        assert mask["2024-01-02"] is np.True_  # was forward filled

    def test_original_dates_not_marked_as_filled(self):
        s = pd.Series(
            [100.0, 102.0],
            index=pd.to_datetime(["2024-01-02", "2024-01-03"])
        )
        _, mask = forward_fill(s, frequency="daily")

        assert mask["2024-01-02"] is np.False_
        assert mask["2024-01-03"] is np.False_

    def test_daily_fill_limit_is_5(self):
        # 8 consecutive missing business days — only first 5 should be filled
        dates = pd.bdate_range("2024-01-02", periods=1).tolist() + \
                pd.bdate_range("2024-01-15", periods=1).tolist()
        s = pd.Series([100.0, 200.0], index=dates)

        filled, _ = forward_fill(s, frequency="daily")
        middle = filled["2024-01-03":"2024-01-12"]

        non_null = middle.dropna()
        assert len(non_null) == 5

    def test_monthly_fill_has_no_limit(self):
        s = pd.Series(
            [100.0, 110.0],
            index=pd.to_datetime(["2024-01-02", "2024-04-01"])
        )
        filled, _ = forward_fill(s, frequency="monthly")
        # All business days between Jan and Apr should be filled
        assert filled.isna().sum() == 0


# compute pect change

class TestComputePctChange:
    def test_basic_pct_change(self):
        s = pd.Series([100.0, 110.0, 99.0], index=pd.date_range("2024-01-01", periods=3))
        result = compute_pct_change(s)

        assert pd.isna(result.iloc[0])
        assert result.iloc[1] == pytest.approx(0.10)
        assert result.iloc[2] == pytest.approx(-0.1, rel=1e-3)

    def test_returns_series(self):
        s = pd.Series([1.0, 2.0], index=pd.date_range("2024-01-01", periods=2))
        result = compute_pct_change(s)
        assert isinstance(result, pd.Series)


# ── compute_252d_zscore ───────────────────────────────────────────────────────

class TestCompute252dZscore:
    def test_returns_nan_for_short_series(self):
        s = pd.Series(range(100), index=pd.bdate_range("2020-01-01", periods=100), dtype=float)
        result = compute_252d_zscore(s)
        # need 252 points for a full window — first 251 should be NaN
        assert result.iloc[:251].isna().all()

    def test_returns_values_after_252_points(self):
        np.random.seed(42)
        s = pd.Series(
            np.random.normal(100, 10, 300),
            index=pd.bdate_range("2020-01-01", periods=300)
        )
        result = compute_252d_zscore(s)
        assert result.iloc[252:].notna().all()

    def test_zscore_near_zero_for_stable_series(self):
        # perfectly flat series → zscore should be 0 or NaN (std = 0)
        s = pd.Series([100.0] * 300, index=pd.bdate_range("2020-01-01", periods=300))
        result = compute_252d_zscore(s)
        # std of constant series is 0 → division by zero → NaN or inf
        assert result.iloc[252:].isna().all() or (result.iloc[252:].abs() < 1e-6).all()


# prepare

class TestPrepare:
    def test_prepare_returns_list_of_dicts(self):
        idx = pd.date_range("2024-01-01", periods=3)
        s = pd.Series([70.0, 72.0, 71.0], index=idx)
        pct = pd.Series([None, 0.028, -0.013], index=idx)
        zscore = pd.Series([None, None, 0.5], index=idx)
        filled = pd.Series([False, False, False], index=idx)

        records = prepare(s, pct, zscore, filled)

        assert len(records) == 3
        assert records[0]["date"] == "2024-01-01"
        assert records[0]["value"] == 70.0
        assert records[2]["zscore_252d"] == pytest.approx(0.5)

    def test_prepare_skips_nan_values(self):
        idx = pd.date_range("2024-01-01", periods=3)
        s = pd.Series([70.0, float("nan"), 71.0], index=idx)
        pct = pd.Series([None, None, 0.014], index=idx)
        zscore = pd.Series([None, None, 0.3], index=idx)
        filled = pd.Series([False, False, False], index=idx)

        records = prepare(s, pct, zscore, filled)

        assert len(records) == 2
        assert records[0]["value"] == 70.0
        assert records[1]["value"] == 71.0

    def test_prepare_none_for_nan_pct_and_zscore(self):
        idx = pd.date_range("2024-01-01", periods=2)
        s = pd.Series([70.0, 72.0], index=idx)
        pct = pd.Series([float("nan"), 0.028], index=idx)
        zscore = pd.Series([float("nan"), float("nan")], index=idx)
        filled = pd.Series([False, False], index=idx)

        records = prepare(s, pct, zscore, filled)

        assert records[0]["pct_change"] is None
        assert records[0]["zscore_252d"] is None
        assert records[1]["pct_change"] == pytest.approx(0.028)