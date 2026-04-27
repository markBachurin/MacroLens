import sys
from pathlib import Path
from dotenv import load_dotenv
sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

if len(sys.argv) < 2:
    print("Usage: python dir/test_loader.py <source_name>")
    sys.exit(1)


from ingestion.config.series_config import get_source_series
from ingestion.loaders.postgres_gate import Postgres_StorageGate
from ingestion.loaders.aws_s3_gate import S3_StorageGate
from datetime import date


from ingestion.validators.series_validator import validate, print_errors

source = sys.argv[1]

if source == "fred":
    from ingestion.adapters.fred import FredAdapter
    adapter = FredAdapter()
elif source == "yfinance":
    from ingestion.adapters.yfinance import YfinanceAdapter
    adapter = YfinanceAdapter()
else:
    print(f"Unknown source: {source}")
    sys.exit(1)

for series_key, data in get_source_series(source).items():
    records = adapter.fetch(data["series_id"], "2024-01-01", "2024-04-15")

    valid_records, error_logs = validate(records, series_key)

    print_errors(error_logs)

    s3_gate = S3_StorageGate()
    postgres_gate = Postgres_StorageGate()



    s3_gate.upload_series(valid_records, source, series_key, date.today(), "validated")
    # keep state below "raw" cuz validated table is not yet created in postgres
    postgres_gate.upload_series(valid_records, source, series_key, date.today(), "raw")
