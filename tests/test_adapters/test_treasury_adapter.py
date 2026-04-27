import pytest
from unittest.mock import patch, MagicMock

# treasury adapter

class TestTreasuryAdapter:
    @patch("ingestion.adapters.treasury.requests.get")
    def test_fetch_parses_xml(self, mock_get):
        xml_payload = """<?xml version="1.0" encoding="utf-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <content>
              <m:properties
                xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"
                xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices">
                <d:NEW_DATE>2024-01-02T00:00:00</d:NEW_DATE>
                <d:BC_2YEAR>4.43</d:BC_2YEAR>
              </m:properties>
            </content>
          </entry>
        </feed>"""

        mock_get.return_value.content = xml_payload.encode()
        mock_get.return_value.raise_for_status = MagicMock()

        from ingestion.adapters.treasury import TreasuryAdapter
        adapter = TreasuryAdapter()
        records = adapter.fetch("BC_2YEAR", "2024-01-01", "2024-12-31")

        assert len(records) == 1
        assert records[0]["date"] == "2024-01-02"
        assert records[0]["value"] == 4.43

    @patch("ingestion.adapters.treasury.requests.get")
    def test_fetch_filters_out_of_range_dates(self, mock_get):
        xml_payload = """<?xml version="1.0" encoding="utf-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <content>
              <m:properties
                xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"
                xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices">
                <d:NEW_DATE>2023-06-01T00:00:00</d:NEW_DATE>
                <d:BC_2YEAR>3.99</d:BC_2YEAR>
              </m:properties>
            </content>
          </entry>
        </feed>"""

        mock_get.return_value.content = xml_payload.encode()
        mock_get.return_value.raise_for_status = MagicMock()

        from ingestion.adapters.treasury import TreasuryAdapter
        adapter = TreasuryAdapter()
        records = adapter.fetch("BC_2YEAR", "2024-01-01", "2024-12-31")

        assert len(records) == 0