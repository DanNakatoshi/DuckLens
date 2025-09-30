"""Polygon.io data collector."""

from datetime import datetime

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import settings
from src.models.schemas import (
    PolygonAggregatesResponse,
    PolygonTickersResponse,
    StockPrice,
)
from src.utils.exceptions import DataCollectionError


class PolygonCollector:
    """Collector for Polygon.io stock data."""

    BASE_URL = "https://api.polygon.io"

    def __init__(self, api_key: str | None = None):
        """Initialize collector with API key."""
        self.api_key = api_key or settings.polygon_api_key
        self.client = httpx.Client(
            base_url=self.BASE_URL, timeout=30.0, params={"apiKey": self.api_key}
        )

    def __enter__(self) -> "PolygonCollector":
        return self

    def __exit__(self, *args: object) -> None:
        self.client.close()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def get_ticker_details(self, ticker: str) -> PolygonTickersResponse:
        """Get ticker details from Polygon.io."""
        try:
            response = self.client.get(
                "/v3/reference/tickers", params={"ticker": ticker, "active": "true"}
            )
            response.raise_for_status()
            return PolygonTickersResponse(**response.json())
        except httpx.HTTPError as e:
            raise DataCollectionError(f"Failed to fetch ticker details: {e}") from e
        except Exception as e:
            raise DataCollectionError(f"Unexpected error: {e}") from e

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def get_aggregates(
        self,
        ticker: str,
        from_date: datetime,
        to_date: datetime,
        timespan: str = "day",
        multiplier: int = 1,
    ) -> PolygonAggregatesResponse:
        """Get aggregate bars for a ticker."""
        from_str = from_date.strftime("%Y-%m-%d")
        to_str = to_date.strftime("%Y-%m-%d")

        try:
            response = self.client.get(
                f"/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_str}/{to_str}",
                params={"adjusted": "true", "sort": "asc"},
            )
            response.raise_for_status()
            return PolygonAggregatesResponse(**response.json())
        except httpx.HTTPError as e:
            raise DataCollectionError(f"Failed to fetch aggregates: {e}") from e
        except Exception as e:
            raise DataCollectionError(f"Unexpected error: {e}") from e

    def get_stock_prices(
        self, ticker: str, from_date: datetime, to_date: datetime
    ) -> list[StockPrice]:
        """Get stock prices as normalized StockPrice objects."""
        response = self.get_aggregates(ticker, from_date, to_date)

        if not response.results:
            return []

        return [StockPrice.from_polygon_bar(ticker, bar) for bar in response.results]
