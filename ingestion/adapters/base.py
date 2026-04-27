from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import List

@dataclass
class SeriesPoint:
    source: str
    series_id: str
    series_name: str
    date: date
    value: float
    unit: str | None = None


class BaseAdapter(ABC):
    source: str

    @abstractmethod
    def fetch(self, series_id: str, start: date, end: date) -> List[SeriesPoint]:
        # fetch data points for one series over a date range
        ...

