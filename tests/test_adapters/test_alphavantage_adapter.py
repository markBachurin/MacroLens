import pytest
from unittest.mock import patch, MagicMock

# alphavantage adapter

class TestAlphaVantageAdapter:
    @patch("ingestion.adapters.alphaVantage.settings")
    @patch("ingestion.adapters.alphaVantage.requests.get")
    def test_fetch_returns_records(self, mock_get, mock_settings):
        mock_settings.alpha_vantage_api_key = "test-key"
        mock_get.return_value.json.return_value = {
            "Time Series FX (Daily)": {
                "2024-01-02": {"4. close": "1.095"},
                "2024-01-03": {"4. close": "1.098"},
            }
        }
        mock_get.return_value.raise_for_status = MagicMock()

        from ingestion.adapters.alphaVantage import AlphaVantageAdapter
        adapter = AlphaVantageAdapter()
        records = adapter.fetch("EUR/USD", "2024-01-01", "2024-01-05")

        assert len(records) == 2
        assert records[0]["date"] == "2024-01-02"
        assert records[0]["value"] == pytest.approx(1.095)

    @patch("ingestion.adapters.alphaVantage.settings")
    @patch("ingestion.adapters.alphaVantage.requests.get")
    def test_fetch_raises_on_rate_limit(self, mock_get, mock_settings):
        mock_settings.alpha_vantage_api_key = "test-key"
        mock_get.return_value.json.return_value = {
            "Note": "Thank you for using Alpha Vantage! rate limit"
        }
        mock_get.return_value.raise_for_status = MagicMock()

        from ingestion.adapters.alphaVantage import AlphaVantageAdapter
        adapter = AlphaVantageAdapter()

        with pytest.raises(RuntimeError, match="rate limit"):
            adapter.fetch("EUR/USD", "2024-01-01", "2024-01-05")

    @patch("ingestion.adapters.alphaVantage.settings")
    def test_raises_when_api_key_missing(self, mock_settings):
        mock_settings.alpha_vantage_api_key = ""

        from ingestion.adapters.alphaVantage import AlphaVantageAdapter
        with pytest.raises(ValueError, match="ALPHA_VANTAGE_API_KEY"):
            AlphaVantageAdapter()

    @patch("ingestion.adapters.alphaVantage.settings")
    @patch("ingestion.adapters.alphaVantage.requests.get")
    def test_fetch_filters_out_of_range(self, mock_get, mock_settings):
        mock_settings.alpha_vantage_api_key = "test-key"
        mock_get.return_value.json.return_value = {
            "Time Series FX (Daily)": {
                "2023-12-29": {"4. close": "1.090"},
                "2024-01-02": {"4. close": "1.095"},
            }
        }
        mock_get.return_value.raise_for_status = MagicMock()

        from ingestion.adapters.alphaVantage import AlphaVantageAdapter
        adapter = AlphaVantageAdapter()
        records = adapter.fetch("EUR/USD", "2024-01-01", "2024-01-05")

        assert len(records) == 1
        assert records[0]["date"] == "2024-01-02"