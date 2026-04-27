from ingestion.adapters.base import BaseAdapter
import requests
import xml.etree.ElementTree as ET

class TreasuryAdapter(BaseAdapter):
    BASE_URL = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"

    def __init__(self):
        pass

    def fetch(self, series_id: str, start_date: str, end_date: str) -> list[dict]:
        start_year = int(start_date[:4])
        end_year = int(end_date[:4])
        records = []

        for year in range(start_year, end_year + 1):
            response = requests.get(self.BASE_URL, params={
                "data": "daily_treasury_yield_curve",
                "field_tdr_date_value": str(year)
            })
            response.raise_for_status()

            root = ET.fromstring(response.content)
            ns = {
                "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
                "d": "http://schemas.microsoft.com/ado/2007/08/dataservices"
            }

            for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
                content = entry.find("{http://www.w3.org/2005/Atom}content")
                if content is None:
                    continue
                props = content.find("m:properties", ns)
                if props is None:
                    continue

                date_el = props.find("d:NEW_DATE", ns)
                val_el = props.find(f"d:{series_id}", ns)

                if date_el is None or val_el is None or not val_el.text:
                    continue

                date_str = date_el.text[:10]
                if date_str < start_date or date_str > end_date:
                    continue

                try:
                    records.append({
                        "date": date_str,
                        "value": float(val_el.text)
                    })
                except (ValueError, TypeError):
                    continue

        return records