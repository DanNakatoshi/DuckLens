"""Fetch historical data for latest batch of tickers."""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from src.data.collectors.polygon_collector import PolygonCollector
from src.data.storage.market_data_db import MarketDataDB

load_dotenv()

# Latest batch of tickers
NEW_TICKERS = ["GOOGL", "BE", "NEE", "WDC", "MU", "AMD", "ENB", "ELV", "TSLA"]


def fetch_stock_data(tickers: list[str], years: int = 5) -> None:
    """Fetch 5 years of OHLCV data."""
    print(f"\n{'='*70}")
    print(f"FETCHING LATEST BATCH: {', '.join(tickers)}")
    print(f"{'='*70}\n")

    end_date = datetime(2025, 9, 30)
    start_date = end_date - timedelta(days=years * 365)

    with PolygonCollector() as collector, MarketDataDB() as db:
        for ticker in tickers:
            print(f"\n[{ticker}] Fetching OHLCV data...")
            print(f"  Range: {start_date.date()} to {end_date.date()}")

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
    print("-> Complete")
    print(f"{'='*70}\n")


def main():
    print(f"\nFetching latest batch of tickers...")
    print(f"Note: BTC and ETH are not available on Polygon as stock tickers")
    print(f"      Use MARA, RIOT (miners) or BITO (Bitcoin ETF) as crypto proxies")
    print(f"      GLD is already in the ETF watchlist\n")

    fetch_stock_data(NEW_TICKERS, years=5)


if __name__ == "__main__":
    main()
