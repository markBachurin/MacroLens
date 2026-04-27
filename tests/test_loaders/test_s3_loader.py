import pytest
from unittest.mock import patch, MagicMock

# s3 client

class TestS3Client:
    @patch("ingestion.loaders.aws_s3_gate.settings")
    @patch("ingestion.loaders.aws_s3_gate.boto3.client")
    def test_upload_series_puts_object(self, mock_boto_client, mock_settings):
        mock_settings.s3_bucket = "test-bucket"
        mock_settings.aws_access_key = "key"
        mock_settings.aws_secret_access_key = "secret"

        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        from ingestion.loaders.aws_s3_gate import S3_Client
        client = S3_Client()

        records = [{"date": "2024-01-01", "value": 75.5}]
        client.upload_series(records, source="fred", series_id="WTI")

        mock_s3.put_object.assert_called_once()
        call_kwargs = mock_s3.put_object.call_args[1]
        assert call_kwargs["Bucket"] == "test-bucket"
        assert "raw_payload/fred/WTI/" in call_kwargs["Key"]

    @patch("ingestion.loaders.aws_s3_gate.settings")
    @patch("ingestion.loaders.aws_s3_gate.boto3.client")
    def test_upload_series_raises_on_missing_source(self, mock_boto_client, mock_settings):
        mock_settings.s3_bucket = "test-bucket"
        mock_settings.aws_access_key = "key"
        mock_settings.aws_secret_access_key = "secret"

        from ingestion.loaders.aws_s3_gate import S3_Client
        client = S3_Client()

        with pytest.raises(ValueError, match="Missing Value"):
            client.upload_series([{"date": "2024-01-01", "value": 1.0}], source=None, series_id="WTI")

    @patch("ingestion.loaders.aws_s3_gate.settings")
    @patch("ingestion.loaders.aws_s3_gate.boto3.client")
    def test_platform_returns_s3(self, mock_boto_client, mock_settings):
        mock_settings.s3_bucket = "test-bucket"
        mock_settings.aws_access_key = "key"
        mock_settings.aws_secret_access_key = "secret"

        from ingestion.loaders.aws_s3_gate import S3_Client
        client = S3_Client()
        assert client.platform() == "s3"