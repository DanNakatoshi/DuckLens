"""Tests for DuckDB manager."""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from src.data.storage.duckdb_manager import DuckDBManager
from src.models.schemas import StockPrice
from src.utils.exceptions import DatabaseError


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test.db"
    manager = DuckDBManager(str(db_path))
    yield manager
    # Cleanup happens automatically with tmp_path


def test_database_initialization(temp_db: DuckDBManager) -> None:
    """Test that database initializes correctly."""
    assert temp_db.db_path is not None
    # Should not raise any errors
    symbols = temp_db.get_symbols()
    assert symbols == []


def test_insert_and_retrieve_stock_prices(temp_db: DuckDBManager) -> None:
    """Test inserting and retrieving stock prices."""
    # Create test data
    now = datetime.now()
    prices = [
        StockPrice(
            symbol="AAPL",
            timestamp=now,
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("149.00"),
            close=Decimal("154.00"),
            volume=1000000,
        ),
        StockPrice(
            symbol="AAPL",
            timestamp=now - timedelta(days=1),
            open=Decimal("148.00"),
            high=Decimal("151.00"),
            low=Decimal("147.00"),
            close=Decimal("150.00"),
            volume=900000,
        ),
    ]

    # Insert prices
    inserted = temp_db.insert_stock_prices(prices)
    assert inserted == 2

    # Retrieve prices
    retrieved = temp_db.get_stock_prices("AAPL")
    assert len(retrieved) == 2
    assert retrieved[0].symbol == "AAPL"
    assert retrieved[0].close == Decimal("154.00")


def test_insert_duplicate_prices(temp_db: DuckDBManager) -> None:
    """Test that duplicate prices are skipped."""
    now = datetime.now()
    price = StockPrice(
        symbol="AAPL",
        timestamp=now,
        open=Decimal("150.00"),
        high=Decimal("155.00"),
        low=Decimal("149.00"),
        close=Decimal("154.00"),
        volume=1000000,
    )

    # Insert once
    inserted1 = temp_db.insert_stock_prices([price])
    assert inserted1 == 1

    # Insert again (should skip)
    inserted2 = temp_db.insert_stock_prices([price])
    assert inserted2 == 0

    # Should still have only one record
    retrieved = temp_db.get_stock_prices("AAPL")
    assert len(retrieved) == 1


def test_get_stock_prices_with_date_filter(temp_db: DuckDBManager) -> None:
    """Test retrieving stock prices with date filters."""
    now = datetime.now()
    prices = [
        StockPrice(
            symbol="AAPL",
            timestamp=now - timedelta(days=i),
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("149.00"),
            close=Decimal("154.00"),
            volume=1000000,
        )
        for i in range(10)
    ]

    temp_db.insert_stock_prices(prices)

    # Get last 5 days
    start_date = now - timedelta(days=5)
    filtered = temp_db.get_stock_prices("AAPL", start_date=start_date)
    assert len(filtered) == 6  # Today + 5 days back

    # Get with limit
    limited = temp_db.get_stock_prices("AAPL", limit=3)
    assert len(limited) == 3


def test_get_latest_timestamp(temp_db: DuckDBManager) -> None:
    """Test getting latest timestamp for a symbol."""
    # Should be None for non-existent symbol
    latest = temp_db.get_latest_timestamp("AAPL")
    assert latest is None

    # Insert some prices
    now = datetime.now()
    prices = [
        StockPrice(
            symbol="AAPL",
            timestamp=now - timedelta(days=i),
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("149.00"),
            close=Decimal("154.00"),
            volume=1000000,
        )
        for i in range(5)
    ]
    temp_db.insert_stock_prices(prices)

    # Should return most recent timestamp
    latest = temp_db.get_latest_timestamp("AAPL")
    assert latest is not None
    assert latest.date() == now.date()


def test_get_symbols(temp_db: DuckDBManager) -> None:
    """Test getting list of all symbols."""
    # Insert prices for multiple symbols
    now = datetime.now()
    symbols_to_insert = ["AAPL", "GOOGL", "MSFT"]

    for symbol in symbols_to_insert:
        price = StockPrice(
            symbol=symbol,
            timestamp=now,
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("149.00"),
            close=Decimal("154.00"),
            volume=1000000,
        )
        temp_db.insert_stock_prices([price])

    # Get all symbols
    symbols = temp_db.get_symbols()
    assert len(symbols) == 3
    assert set(symbols) == set(symbols_to_insert)
