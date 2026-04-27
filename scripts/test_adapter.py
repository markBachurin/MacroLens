import sys
from pathlib import Path
from dotenv import load_dotenv


if len(sys.argv) < 2:
    print("Usage: python dir/test_adapter.py <adaptor_name>")
    sys.exit(1)


sys.path.insert(0, str(Path(__file__).parent.parent))
from ingestion.config.series_config import get_source_series
load_dotenv()


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

for series, data in get_source_series(source).items():
    records = adapter.fetch(data["series_id"], "2024-01-01", "2024-04-15")
    print(f"Got {len(records)} records")
    print(records[:5])