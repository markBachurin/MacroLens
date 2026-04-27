import json
import boto3
from datetime import datetime
from ingestion.loaders.base import Client
from config.settings import settings

class S3_Client(Client):
    def platform(self) -> str:
        return "s3"

    def upload_series(self, records: list[dict], source: str, series_id: str, state: str = "raw") -> None:
        s3 = self._get_s3_client()
        if source is None or series_id is None:
            raise ValueError("Missing Value for archive_raw_payload")

        key: str = f"{state}_payload/{source}/{series_id}/{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"

        body = json.dumps(records, indent=2)
        s3.put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=body,
            ContentType="application/json"
        )

        print(f"Uploaded to S3: {key}")

    def _get_s3_client(self) -> boto3.Session:
        return boto3.client(
            "s3",
            aws_access_key_id=settings.aws_access_key,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name="us-east-1",
        )