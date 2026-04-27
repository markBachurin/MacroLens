import json
from boto3 import Session
import os
from datetime import datetime, timezone
from ingestion.loaders.aws_s3_client import get_s3_client
from ingestion.loaders.base import StorageGate

from dotenv import load_dotenv
load_dotenv()


class S3_StorageGate(StorageGate):
    def __init__(self):
        self.s3: Session = get_s3_client()

    def platform(self) -> str:
        return "s3"

    def upload_series(self, records: list[dict], source: str, series_id: str, state: str = "raw") -> None:
        if source is None or series_id is None:
            raise ValueError("Missing Value for archive_raw_payload")

        key: str = f"{state}_payload/{source}/{series_id}/{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}.json"

        body = json.dumps(records, indent=2)
        self.s3.put_object(
            Bucket=os.getenv("S3_BUCKET"),
            Key=key,
            Body=body,
            ContentType="application/json"
        )

        print(f"Uploaded to S3: {key}")
