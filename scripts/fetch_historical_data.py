"""Fetch 5 years of historical market data from Polygon.io and store in DuckDB."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.tickers import TICKER_SYMBOLS, get_category_features, print_ticker_summary
from src.data.collectors.polygon_collector import PolygonCollector
from src.data.storage.market_data_db import MarketDataDB

# Use configured tickers with metadata
DEFAULT_TICKERS = TICKER_SYMBOLS


def fetch_historical_ohlcv(
    tickers: list[str], years: int = 5, batch_days: int = 365
) -> None:
    """
    Fetch historical OHLCV data for specified tickers.

    Args:
        tickers: List of ticker symbols
        years: Number of years of historical data to fetch
        batch_days: Days per batch (Polygon has limits)
    """
    print(f"\n{'='*60}")
    print(f"Fetching {years} years of OHLCV data for {len(tickers)} tickers")
    print(f"{'='*60}\n")

    end_date = datetime.now()
    start_date = end_date - timedelta(days=years * 365)

    with PolygonCollector() as collector, MarketDataDB() as db:
        total_records = 0

        for ticker in tickers:
            print(f"\n[{ticker}] Fetching data...")

            # Check if we already have data for this ticker
            latest_date = db.get_latest_date(ticker)
            if latest_date:
                print(f"  Latest data: {latest_date.date()}")
                # Start from day after latest date
                fetch_start = latest_date + timedelta(days=1)
                if fetch_start >= end_date:
                    print(f"  ✓ Already up to date")
                    continue
            else:
                fetch_start = start_date
                print(f"  No existing data, fetching from {fetch_start.date()}")

            # Fetch data in batches to avoid API limits
            current_start = fetch_start
            ticker_records = 0

            while current_start < end_date:
                current_end = min(current_start + timedelta(days=batch_days), end_date)

                try:
                    print(
                        f"  Fetching {current_start.date()} to {current_end.date()}...",
                        end=" ",
                    )
                    prices = collector.get_stock_prices(ticker, current_start, current_end)

                    if prices:
                        count = db.insert_stock_prices(prices)
                        ticker_records += count
                        print(f"✓ {count} records")
                    else:
                        print("⚠ No data")

                except Exception as e:
                    print(f"✗ Error: {e}")

                current_start = current_end + timedelta(days=1)

            total_records += ticker_records
            print(f"  Total for {ticker}: {ticker_records} records")

        print(f"\n{'='*60}")
        print(f"✓ Historical fetch complete: {total_records} total records")
        print(f"{'='*60}\n")


def fetch_historical_short_data(tickers: list[str]) -> None:
    """
    Fetch all available historical short interest and short volume data.

    Args:
        tickers: List of ticker symbols
    """
    print(f"\n{'='*60}")
    print(f"Fetching short data for {len(tickers)} tickers")
    print(f"{'='*60}\n")

    with PolygonCollector() as collector, MarketDataDB() as db:
        # Fetch short interest (bi-monthly data, goes back to 2017)
        print("\n[Short Interest] Fetching bi-monthly data...")
        short_interest_total = 0

        for ticker in tickers:
            try:
                print(f"  {ticker}...", end=" ")
                response = collector.get_short_interest(ticker=ticker, limit=10000)

                if response.results:
                    count = db.insert_short_interest(response.results)
                    short_interest_total += count
                    print(f"✓ {count} records")
                else:
                    print("⚠ No data")

            except Exception as e:
                print(f"✗ Error: {e}")

        print(f"  Total short interest records: {short_interest_total}")

        # Fetch short volume (daily data, goes back to Jan 2024)
        print("\n[Short Volume] Fetching daily data...")
        short_volume_total = 0

        # Short volume is only available from Jan 2024
        start_date = datetime(2024, 1, 16)
        end_date = datetime.now()

        for ticker in tickers:
            try:
                print(f"  {ticker}...", end=" ")

                # Fetch in batches by date
                current_date = start_date
                ticker_count = 0

                while current_date <= end_date:
                    date_str = current_date.strftime("%Y-%m-%d")
                    response = collector.get_short_volume(ticker=ticker, date=date_str, limit=1)

                    if response.results:
                        count = db.insert_short_volume(response.results)
                        ticker_count += count

                    current_date += timedelta(days=1)

                short_volume_total += ticker_count
                print(f"✓ {ticker_count} records")

            except Exception as e:
                print(f"✗ Error: {e}")

        print(f"  Total short volume records: {short_volume_total}")

        print(f"\n{'='*60}")
        print(f"✓ Short data fetch complete")
        print(f"{'='*60}\n")


def main():
    """Main entry point."""
    print("\n" + "=" * 60)
    print("HISTORICAL MARKET DATA FETCHER")
    print("=" * 60)

    # Print ticker configuration
    print_ticker_summary()

    # Allow custom ticker list via command line
    if len(sys.argv) > 1:
        tickers = sys.argv[1].split(",")
        print(f"\nUsing custom tickers: {', '.join(tickers)}")
    else:
        tickers = DEFAULT_TICKERS
        print(f"\nUsing configured {len(tickers)} Tier 1 tickers")

    # Fetch OHLCV data (5 years)
    fetch_historical_ohlcv(tickers, years=5)

    # Fetch short data
    fetch_historical_short_data(tickers)

    # Print summary statistics
    print("\n" + "=" * 60)
    print("DATABASE STATISTICS")
    print("=" * 60)

    with MarketDataDB() as db:
        stats = db.get_table_stats()

        for table_name, table_stats in stats.items():
            print(f"\n{table_name.upper().replace('_', ' ')}:")
            for key, value in table_stats.items():
                print(f"  {key.replace('_', ' ').title()}: {value}")

    print("\n✓ Done!\n")


if __name__ == "__main__":
    main()
