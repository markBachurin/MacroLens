import pytest
from unittest.mock import patch, MagicMock


# fred adapter

class TestFredAdapter:
    @patch("ingestion.adapters.fred.settings")
    @patch("ingestion.adapters.fred.requests.get")
    def test_fetch_returns_records(self, mock_get, mock_settings):
        mock_settings.fred_api_key = "test-key"
        mock_get.return_value.json.return_value = {
            "observations": [
                {"date": "2024-01-01", "value": "75.5"},
                {"date": "2024-01-02", "value": "76.0"},
            ]
        }

        mock_get.return_value.raise_for_status = MagicMock()

        from ingestion.adapters.fred import FredAdapter
        adapter = FredAdapter()
        records = adapter.fetch("DCOILWTICO", "2024-01-01", "2024-01-02")

        assert len(records) == 2
        assert records[0]["date"] == "2024-01-01"
        assert records[0]["value"] == 75.5

    @patch("ingestion.adapters.fred.settings")
    @patch("ingestion.adapters.fred.requests.get")
    def test_fetch_skips_missing_values(self, mock_get, mock_settings):
        mock_settings.fred_api_key = "test-key"
        mock_get.return_value.json.return_value = {
            "observations": [
                {"date": "2024-01-01", "value": "."},
                {"date": "2024-01-02", "value": "76.0"},
            ]
        }
        mock_get.return_value.raise_for_status = MagicMock()

        from ingestion.adapters.fred import FredAdapter
        adapter = FredAdapter()
        records = adapter.fetch("DCOILWTICO", "2024-01-01", "2024-01-02")

        assert len(records) == 1
        assert records[0]["date"] == "2024-01-02"

    @patch("ingestion.adapters.fred.settings")
    @patch("ingestion.adapters.fred.requests.get")
    def test_fetch_raises_on_missing_observations_key(self, mock_get, mock_settings):
        mock_settings.fred_api_key = "test-key"
        mock_get.return_value.json.return_value = {"error": "bad request"}
        mock_get.return_value.raise_for_status = MagicMock()

        from ingestion.adapters.fred import FredAdapter
        adapter = FredAdapter()

        with pytest.raises(ValueError, match="Unexpected FRED response"):
            adapter.fetch("DCOILWTICO", "2024-01-01", "2024-01-02")

    @patch("ingestion.adapters.fred.settings")
    def test_raises_when_api_key_missing(self, mock_settings):
        mock_settings.fred_api_key = ""

        from ingestion.adapters.fred import FredAdapter
        with pytest.raises(ValueError, match="FRED_API_KEY"):
            FredAdapter()