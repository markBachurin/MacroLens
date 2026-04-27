import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch

from transformation.derived_series import (
    to_series,
    to_df,
    get_derived_metrics,
)


# ── to_series ─────────────────────────────────────────────────────────────────

class TestToSeries:
    def test_converts_rows_to_series(self):
        rows = [
            ("2024-01-01", 4.43),
            ("2024-01-02", 4.50),
        ]
        s = to_series(rows)

        assert isinstance(s, pd.Series)
        assert len(s) == 2
        assert s.iloc[0] == 4.43

    def test_index_is_datetime(self):
        rows = [("2024-01-01", 4.43)]
        s = to_series(rows)
        assert isinstance(s.index, pd.DatetimeIndex)

    def test_empty_rows_returns_empty_series(self):
        s = to_series([])
        assert s.empty


# ── to_df ─────────────────────────────────────────────────────────────────────

class TestToDf:
    def _make_series(self, values, dates=None):
        if dates is None:
            dates = pd.date_range("2024-01-01", periods=len(values))
        return pd.Series(values, index=dates)

    def test_builds_dataframe_with_correct_columns(self):
        idx = pd.date_range("2024-01-01", periods=3)
        t10y = self._make_series([4.0, 4.1, 4.2], idx)
        t2y = self._make_series([3.8, 3.9, 4.0], idx)
        wti = self._make_series([75.0, 76.0, 74.0], idx)
        cpi = self._make_series([310.0, 311.0, 312.0], idx)
        sp500 = self._make_series([4800.0, 4850.0, 4900.0], idx)

        df = to_df(t10y, t2y, wti, cpi, sp500)

        assert set(df.columns) == {"T10Y", "T2Y", "WTI", "CPI", "SP500"}
        assert len(df) == 3


# ── get_derived_metrics ───────────────────────────────────────────────────────

class TestGetDerivedMetrics:
    def _base_df(self):
        idx = pd.date_range("2024-01-01", periods=5)
        return pd.DataFrame({
            "T10Y":  [4.5, 4.6, 4.7, 4.8, 4.9],
            "T2Y":   [4.0, 4.1, 4.2, 4.3, 4.4],
            "WTI":   [75.0, 76.0, 74.0, 73.0, 77.0],
            "CPI":   [310.0, 311.0, 312.0, 313.0, 314.0],
            "SP500": [4800.0, 4850.0, 4900.0, 4950.0, 5000.0],
        }, index=idx)

    def test_yield_spread_is_t10y_minus_t2y(self):
        df = get_derived_metrics(self._base_df())
        expected = df["T10Y"] - df["T2Y"]
        pd.testing.assert_series_equal(df["yield_spread"], expected, check_names=False)

    def test_real_wti_is_cpi_adjusted(self):
        df = get_derived_metrics(self._base_df())
        cpi_base = 310.0
        expected_first = 75.0 * (cpi_base / 310.0)
        assert df["real_wti"].iloc[0] == pytest.approx(expected_first)

    def test_wti_sp500_ratio_computed(self):
        df = get_derived_metrics(self._base_df())
        expected = 75.0 / 4800.0 * 1000
        assert df["wti_sp500_ratio"].iloc[0] == pytest.approx(expected)

    def test_derived_columns_present(self):
        df = get_derived_metrics(self._base_df())
        assert "yield_spread" in df.columns
        assert "real_wti" in df.columns
        assert "wti_sp500_ratio" in df.columns

    def test_nan_inputs_produce_nan_outputs(self):
        idx = pd.date_range("2024-01-01", periods=3)
        df = pd.DataFrame({
            "T10Y":  [None, 4.6, 4.7],
            "T2Y":   [4.0, None, 4.2],
            "WTI":   [75.0, 76.0, None],
            "CPI":   [310.0, None, 312.0],
            "SP500": [4800.0, 4850.0, None],
        }, index=idx)

        result = get_derived_metrics(df)
        # first row: T2Y present, T10Y null → yield_spread should be NaN
        assert pd.isna(result["yield_spread"].iloc[0])


# ── snapshot_builder ──────────────────────────────────────────────────────────

class TestSnapshotBuilder:
    @patch("transformation.snapshot_builder.Postgres_Client")
    def test_anomaly_flag_set_when_zscore_above_threshold(self, mock_gate_cls):
        from transformation.snapshot_builder import build_snapshots
        from ingestion.config.series_config import SERIES_CONFIG

        # pick a real series key so SERIES_CONFIG lookup works
        series_key = "WTI"
        series_id = SERIES_CONFIG[series_key]["series_id"]

        mock_gate = MagicMock()
        mock_gate_cls.return_value = mock_gate

        # row: (date, value, pct_change, zscore_252d)
        mock_gate.query_normalized_by_series_id.side_effect = lambda sid: (
            [("2024-01-01", 75.0, 0.01, 3.0)]  # zscore > 2.5 → anomaly
            if sid == series_id else []
        )

        build_snapshots()

        uploaded = mock_gate.upload_snapshot.call_args_list
        # find the call that contains WTI records
        wti_call = next(
            (c for c in uploaded if c[0][0] and c[0][0][0]["series_id"] == series_id),
            None
        )
        assert wti_call is not None
        assert wti_call[0][0][0]["anomaly_flag"] is True

    @patch("transformation.snapshot_builder.Postgres_Client")
    def test_anomaly_flag_false_when_zscore_below_threshold(self, mock_gate_cls):
        from transformation.snapshot_builder import build_snapshots
        from ingestion.config.series_config import SERIES_CONFIG

        series_key = "WTI"
        series_id = SERIES_CONFIG[series_key]["series_id"]

        mock_gate = MagicMock()
        mock_gate_cls.return_value = mock_gate

        mock_gate.query_normalized_by_series_id.side_effect = lambda sid: (
            [("2024-01-01", 75.0, 0.01, 1.0)]  # zscore < 2.5
            if sid == series_id else []
        )

        build_snapshots()

        uploaded = mock_gate.upload_snapshot.call_args_list
        wti_call = next(
            (c for c in uploaded if c[0][0] and c[0][0][0]["series_id"] == series_id),
            None
        )
        assert wti_call is not None
        assert wti_call[0][0][0]["anomaly_flag"] is False

    @patch("transformation.snapshot_builder.Postgres_Client")
    def test_skips_series_with_no_rows(self, mock_gate_cls):
        from transformation.snapshot_builder import build_snapshots

        mock_gate = MagicMock()
        mock_gate_cls.return_value = mock_gate
        mock_gate.query_normalized_by_series_id.return_value = []

        build_snapshots()

        mock_gate.upload_snapshot.assert_not_called()

    @patch("transformation.snapshot_builder.Postgres_Client")
    def test_anomaly_flag_false_when_zscore_is_none(self, mock_gate_cls):
        from transformation.snapshot_builder import build_snapshots
        from ingestion.config.series_config import SERIES_CONFIG

        series_key = "WTI"
        series_id = SERIES_CONFIG[series_key]["series_id"]

        mock_gate = MagicMock()
        mock_gate_cls.return_value = mock_gate

        mock_gate.query_normalized_by_series_id.side_effect = lambda sid: (
            [("2024-01-01", 75.0, None, None)]
            if sid == series_id else []
        )

        build_snapshots()

        uploaded = mock_gate.upload_snapshot.call_args_list
        wti_call = next(
            (c for c in uploaded if c[0][0] and c[0][0][0]["series_id"] == series_id),
            None
        )
        assert wti_call is not None
        assert wti_call[0][0][0]["anomaly_flag"] is False