import sys

if len(sys.argv) < 2:
    print("Usage: python dir/test_adapter.py <adaptor_name>")
    sys.exit(1)

from ingestion.config.series_config import get_source_series

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

for series, data in get_source_series(source).items():

    records = adapter.fetch(data["series_id"], "2024-01-01", "2024-04-15")
    print(f"Got {len(records)} records")
    print(records[:5])