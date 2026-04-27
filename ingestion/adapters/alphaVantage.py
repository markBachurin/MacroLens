import os
import requests
from ingestion.adapters.base import BaseAdapter
from datetime import date

class AlphaVantageAdapter(BaseAdapter):
    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self):
        self.api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        if not self.api_key:
            raise ValueError("ALPHA_VANTAGE_API_KEY env var is not set")

    def fetch(self, series_id: str, start_date: date, end_date: date) -> list[dict]:
        from_symbol, to_symbol = series_id.split("/")

        response = requests.get(self.BASE_URL,
            params = {
                "function": "FX_DAILY",
                "from_symbol": from_symbol,
                "to_symbol": to_symbol,
                "outputsize": "full",
                "apikey": self.api_key
            })

        response.raise_for_status()
        data = response.json()

        if "Note" in data or "Information" in data:
            raise RuntimeError(f"Alpha Vantage rate limit hit: {data.get('Note') or data.get('Information')}")

        time_series = data.get("Time Series FX (Daily)")
        if not time_series:
            raise RuntimeError(f"Unexpected Alpha Vantage response: {data}")

        records = []
        for date_str, values in time_series.items():
            if date_str < start_date or date_str > end_date:
                continue

            try:
                records.append({
                    "date": date_str,
                    "value": float(values["4. close"])
                })
            except (KeyError, ValueError):
                continue

        return sorted(records, key=lambda x: x["date"])