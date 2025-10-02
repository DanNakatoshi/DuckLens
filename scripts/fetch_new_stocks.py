"""Fetch historical data for new watchlist stocks."""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from src.data.collectors.polygon_collector import PolygonCollector
from src.data.storage.market_data_db import MarketDataDB

load_dotenv()

# New tickers to fetch
NEW_TICKERS = ["BABA", "INTC", "IREN", "OPEN", "UNH", "MARA", "RIOT"]


def fetch_stock_data(tickers: list[str], years: int = 5) -> None:
    """Fetch 5 years of OHLCV data for stocks."""
    print(f"\n{'='*70}")
    print(f"FETCHING NEW STOCKS: {', '.join(tickers)}")
    print(f"{'='*70}\n")

    end_date = datetime(2025, 9, 30)
    start_date = end_date - timedelta(days=years * 365)

    with PolygonCollector() as collector, MarketDataDB() as db:
        for ticker in tickers:
            print(f"\n[{ticker}] Fetching OHLCV data...")
            print(f"  Range: {start_date.date()} to {end_date.date()}")

            # Check existing data
            latest_date = db.get_latest_date(ticker)
            if latest_date:
                print(f"  Latest data: {latest_date.date()}")
                if latest_date.date() >= end_date.date():
                    print(f"  -> Already up to date")
                    continue
                fetch_start = latest_date + timedelta(days=1)
            else:
                fetch_start = start_date
                print(f"  No existing data")

            # Fetch in yearly batches
            total_records = 0
            current_start = fetch_start

            while current_start < end_date:
                current_end = min(current_start + timedelta(days=365), end_date)

                try:
                    print(f"  Batch: {current_start.date()} to {current_end.date()}...", end=" ")
                    prices = collector.get_stock_prices(ticker, current_start, current_end)

                    if prices:
                        count = db.insert_stock_prices(prices)
                        total_records += count
                        print(f"OK {count} bars")
                    else:
                        print("WARN No data")

                except Exception as e:
                    print(f"ERROR: {e}")

                current_start = current_end + timedelta(days=1)

            print(f"  -> Total: {total_records} bars")

    print(f"\n{'='*70}")
    print("-> Stock data fetch complete")
    print(f"{'='*70}\n")


def main():
    """Main entry point."""
    print(f"\nFetching data for new watchlist tickers...")
    print(f"Tickers: {', '.join(NEW_TICKERS)}\n")

    fetch_stock_data(NEW_TICKERS, years=5)


if __name__ == "__main__":
    main()
