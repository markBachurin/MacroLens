from abc import ABC, abstractmethod


class Client(ABC):
    @property
    @abstractmethod
    def platform(self) -> str:
        ...

    @abstractmethod
    def upload_series(self, records: list[dict], source: str, series_key: str, state: str) -> None:
        ...

