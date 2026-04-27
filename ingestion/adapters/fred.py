import requests
from ingestion.adapters.base import BaseAdapter
from config.settings import settings

class FredAdapter(BaseAdapter):
    BASE_URL =  "https://api.stlouisfed.org/fred/series/observations"

    def __init__(self):
        self.FRED_API_KEY =  settings.fred_api_key
        if not self.FRED_API_KEY:
            raise ValueError("FRED_API_KEY environment variable is not set")


    def fetch(self, series_id, start_date, end_date) -> list[dict]:
        response = requests.get(self.BASE_URL, params={
            "series_id" : series_id,
            "api_key" : self.FRED_API_KEY,
            "observation_start" : start_date,
            "observation_end": end_date,
            "file_type": "json"
        })

        # check for silent request errors
        response.raise_for_status()

        data = response.json()

        if "observations" not in data:
            raise ValueError(f"Unexpected FRED response: {data}")

        return [
            {
                "date" : obs["date"],
                "value": float(obs["value"])
            }
            for obs in data["observations"] if obs["value"] != "." and obs["value"] is not None
        ]
