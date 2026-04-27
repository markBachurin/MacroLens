import pytest
from unittest.mock import patch, MagicMock

# postgrs client

class TestPostgresClient:
    def _make_client(self, mock_conn):
        with patch("ingestion.loaders.postgres_gate.get_connection", return_value=mock_conn):
            from ingestion.loaders.postgres_gate import Postgres_Client
            return Postgres_Client()

    def test_upload_series_executes_upsert(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        client = self._make_client(mock_conn)

        records = [
            {"date": "2024-01-01", "value": 75.5},
            {"date": "2024-01-02", "value": 76.0},
        ]
        client.upload_series(records, source="fred", series_key="WTI")

        assert mock_cursor.execute.call_count == 2
        mock_conn.commit.assert_called_once()

    def test_upload_normalized_series_executes_upsert(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        client = self._make_client(mock_conn)

        records = [
            {"date": "2024-01-01", "value": 75.5, "pct_change": 0.01, "zscore_252d": 1.2, "is_forward_filled": False},
        ]
        client.upload_normalized_series(records, series_key="WTI")

        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    def test_query_raw_by_series_key_returns_rows(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("2024-01-01", 75.5), ("2024-01-02", 76.0)]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        client = self._make_client(mock_conn)
        rows = client.query_raw_by_series_key("WTI")

        assert len(rows) == 2
        assert rows[0] == ("2024-01-01", 75.5)

    def test_upload_snapshot_executes_upsert(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        client = self._make_client(mock_conn)

        records = [
            {
                "series_id": "DCOILWTICO",
                "date": "2024-01-01",
                "value": 75.5,
                "pct_change": 0.01,
                "zscore_252d": 1.2,
                "anomaly_flag": False,
            }
        ]
        client.upload_snapshot(records)

        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    def test_close_closes_connection(self):
        mock_conn = MagicMock()
        mock_conn.closed = False

        client = self._make_client(mock_conn)
        client.close()

        mock_conn.close.assert_called_once()

    def test_close_skips_already_closed_connection(self):
        mock_conn = MagicMock()
        mock_conn.closed = True

        client = self._make_client(mock_conn)
        client.close()

        mock_conn.close.assert_not_called()