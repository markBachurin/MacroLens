import pytest
from unittest.mock import patch, MagicMock

# yfinance adapter

class TestYfinanceAdapter:
    @patch("ingestion.adapters.yfinance.yf.Ticker")
    def test_fetch_returns_records(self, mock_ticker):
        import pandas as pd

        index = pd.to_datetime(["2024-01-02", "2024-01-03"])
        df = pd.DataFrame({"Close": [4800.0, 4850.0]}, index=index)

        mock_ticker.return_value.history.return_value = df

        from ingestion.adapters.yfinance import YfinanceAdapter
        adapter = YfinanceAdapter()
        records = adapter.fetch("^GSPC", "2024-01-01", "2024-01-05")

        assert len(records) == 2
        assert records[0]["value"] == 4800.0

    @patch("ingestion.adapters.yfinance.yf.Ticker")
    def test_fetch_raises_on_empty_dataframe(self, mock_ticker):
        import pandas as pd

        mock_ticker.return_value.history.return_value = pd.DataFrame()

        from ingestion.adapters.yfinance import YfinanceAdapter
        adapter = YfinanceAdapter()

        with pytest.raises(ValueError, match="empty"):
            adapter.fetch("^GSPC", "2024-01-01", "2024-01-05")