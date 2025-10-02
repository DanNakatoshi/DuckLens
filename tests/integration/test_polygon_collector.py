"""Tests for Polygon.io collector."""

import httpx
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
from tenacity import RetryError

from src.data.collectors.polygon_collector import PolygonCollector
from src.utils.exceptions import DataCollectionError


def test_polygon_collector_initialization() -> None:
    """Test that collector initializes correctly."""
    collector = PolygonCollector()
    assert collector.api_key is not None
    assert collector.BASE_URL == "https://api.polygon.io"


def test_get_ticker_details() -> None:
    """Test fetching ticker details for AAPL."""
    with PolygonCollector() as collector:
        response = collector.get_ticker_details("AAPL")

        assert response.status == "OK"
        assert response.results is not None
        assert len(response.results) > 0

        ticker = response.results[0]
        assert ticker.ticker == "AAPL"
        assert ticker.name is not None
        assert ticker.market == "stocks"


def test_get_aggregates() -> None:
    """Test fetching aggregate data for AAPL."""
    with PolygonCollector() as collector:
        to_date = datetime.now()
        from_date = to_date - timedelta(days=7)

        response = collector.get_aggregates("AAPL", from_date, to_date)

        # Accept both OK and DELAYED status (depends on API plan)
        assert response.status in ("OK", "DELAYED")
        assert response.ticker == "AAPL"
        assert response.results is not None
        assert len(response.results) > 0

        # Check first bar structure
        bar = response.results[0]
        assert bar.o > 0  # Open price
        assert bar.h > 0  # High price
        assert bar.l > 0  # Low price
        assert bar.c > 0  # Close price
        assert bar.v > 0  # Volume
        assert bar.h >= bar.l  # High >= Low


def test_get_stock_prices() -> None:
    """Test fetching normalized stock prices."""
    with PolygonCollector() as collector:
        to_date = datetime.now()
        from_date = to_date - timedelta(days=7)

        prices = collector.get_stock_prices("AAPL", from_date, to_date)

        assert len(prices) > 0

        # Check first price
        price = prices[0]
        assert price.symbol == "AAPL"
        assert price.open > 0
        assert price.high > 0
        assert price.low > 0
        assert price.close > 0
        assert price.volume > 0
        assert price.high >= price.low
        assert isinstance(price.timestamp, datetime)


def test_invalid_ticker_returns_empty() -> None:
    """Test that invalid ticker returns empty results, not an error."""
    with PolygonCollector() as collector:
        to_date = datetime.now()
        from_date = to_date - timedelta(days=7)

        # Invalid ticker should return OK status but empty results
        response = collector.get_aggregates("INVALID_XYZ", from_date, to_date)
        assert response.status in ("OK", "NOT_FOUND", "DELAYED")
        # Results will be None or empty list for invalid ticker
        assert response.results is None or len(response.results) == 0


def test_network_error_handling() -> None:
    """Test that network errors are properly caught and wrapped in RetryError."""
    collector = PolygonCollector()

    # Mock the client to raise a connection error
    with patch.object(collector.client, "get", side_effect=httpx.ConnectError("Connection failed")):
        # The retry decorator wraps DataCollectionError in RetryError after all retries fail
        with pytest.raises(RetryError):
            collector.get_ticker_details("AAPL")
