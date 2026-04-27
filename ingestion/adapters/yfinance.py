from ingestion.adapters.base import BaseAdapter
import yfinance as yf

class YfinanceAdapter(BaseAdapter):
    def __init__(self):
        pass

    def fetch(self, series_id: str, start, end) -> list[dict]:
        ticker = yf.Ticker(series_id)
        df = ticker.history(start=start, end=end)

        if df.empty:
            raise ValueError("Data Frame is empty")

        return [
            {
                "date": index.strftime("%Y-%m-%d"),
                "value" : float(row["Close"])
            }
            for index, row in df.iterrows()
        ]


