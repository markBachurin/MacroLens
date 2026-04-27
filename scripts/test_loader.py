import sys

if len(sys.argv) < 2:
    print("Usage: python dir/test_loader.py <source_name>")
    sys.exit(1)


from ingestion.config.series_config import get_source_series
from ingestion.loaders.postgres_gate import Postgres_Client
from ingestion.loaders.aws_s3_gate import S3_Client


from ingestion.validators.series_validator import validate, print_errors

source = sys.argv[1]

if source == "fred":
    from ingestion.adapters.fred import FredAdapter
    adapter = FredAdapter()
elif source == "yfinance":
    from ingestion.adapters.yfinance import YfinanceAdapter
    adapter = YfinanceAdapter()
elif source == "treasury":
    from ingestion.adapters.treasury import TreasuryAdapter
    adapter = TreasuryAdapter()
elif source == "alphavantage":
    from ingestion.adapters.alphaVantage import AlphaVantageAdapter
    adapter = AlphaVantageAdapter()
else:
    print(f"Unknown source: {source}")
    sys.exit(1)

for series_key, data in get_source_series(source).items():
    records = adapter.fetch(data["series_id"], "2024-01-01", "2024-04-15")

    valid_records, error_logs = validate(records, series_key)

    print_errors(error_logs)

    s3_client = S3_Client()
    postgres_client = Postgres_Client()



    s3_client.upload_series(valid_records, source, series_key, "validated")
    # keep state below "raw" cuz validated table is not yet created in postgres
    postgres_client.upload_series(valid_records, source, series_key, "raw")
