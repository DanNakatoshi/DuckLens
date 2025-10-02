"""
Fetch historical economic indicator data from FRED API.

This script fetches economic indicators (Fed rates, CPI, unemployment, GDP, etc.)
from the Federal Reserve Economic Data (FRED) API and stores them in DuckDB.

Usage:
    python scripts/fetch_economic_data.py [--years YEARS] [--series SERIES_ID]

Examples:
    # Fetch 5 years of all economic indicators
    python scripts/fetch_economic_data.py --years 5

    # Fetch 10 years of specific indicator
    python scripts/fetch_economic_data.py --years 10 --series FEDFUNDS

    # Fetch all indicators from 2020 onwards
    python scripts/fetch_economic_data.py --start-date 2020-01-01
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from src.data.collectors.fred_collector import FREDCollector
from src.data.storage.market_data_db import MarketDataDB


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Fetch economic indicators from FRED API"
    )
    parser.add_argument(
        "--years",
        type=int,
        default=5,
        help="Number of years of historical data to fetch (default: 5)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date in YYYY-MM-DD format (overrides --years)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--series",
        type=str,
        help="Specific FRED series ID to fetch (e.g., FEDFUNDS). If not specified, fetches all series.",
    )
    parser.add_argument(
        "--list-series",
        action="store_true",
        help="List all available series and exit",
    )
    return parser.parse_args()


def list_available_series():
    """Print all available economic series."""
    # Access class variable directly without needing API key
    print("\n📊 Available Economic Indicators:\n")
    print(f"{'Series ID':<15} {'Indicator Name'}")
    print("-" * 80)
    for series_id, name in sorted(FREDCollector.ECONOMIC_SERIES.items()):
        print(f"{series_id:<15} {name}")
    print(f"\n✓ Total: {len(FREDCollector.ECONOMIC_SERIES)} indicators")


def fetch_economic_data(
    start_date: datetime,
    end_date: datetime,
    series_id: str | None = None,
):
    """
    Fetch economic indicators and store in database.

    Args:
        start_date: Start date for data fetch
        end_date: End date for data fetch
        series_id: Optional specific series to fetch
    """
    print("🏛️  FRED Economic Data Fetcher")
    print("=" * 60)
    print(f"Date range: {start_date.date()} to {end_date.date()}")
    print(f"Series: {series_id if series_id else 'ALL'}")
    print("=" * 60)

    # Initialize collector and database
    collector = FREDCollector()
    db = MarketDataDB()

    try:
        if series_id:
            # Fetch single series
            print(f"\n📥 Fetching {series_id}...")

            # Check for existing data
            latest_date = db.get_latest_economic_date(series_id)
            if latest_date:
                print(f"   Latest data: {latest_date}")
                if latest_date >= end_date.date():
                    print(f"   ✓ Already up to date")
                    return
                # Fetch only missing data
                fetch_start = datetime.combine(latest_date, datetime.min.time()) + timedelta(days=1)
                print(f"   Fetching from {fetch_start.date()} onwards...")
            else:
                fetch_start = start_date
                print(f"   No existing data, fetching from {fetch_start.date()}")

            indicators = collector.get_economic_indicator(
                series_id=series_id,
                start_date=fetch_start,
                end_date=end_date,
            )

            # Store in database
            if indicators:
                count = db.insert_economic_indicators(indicators)
                print(f"   ✓ Stored {count} observations")
            else:
                print(f"   ⚠ No data available")

        else:
            # Fetch all series
            total_stored = 0
            series_count = len(collector.ECONOMIC_SERIES)

            print(f"\n📥 Fetching {series_count} economic indicators...\n")

            for idx, (sid, name) in enumerate(collector.ECONOMIC_SERIES.items(), 1):
                print(f"[{idx}/{series_count}] {sid:<15} {name[:40]:<40}", end=" ")

                try:
                    # Check for existing data
                    latest_date = db.get_latest_economic_date(sid)
                    if latest_date:
                        if latest_date >= end_date.date():
                            print("✓ Up to date")
                            continue
                        # Fetch only missing data
                        fetch_start = datetime.combine(latest_date, datetime.min.time()) + timedelta(days=1)
                    else:
                        fetch_start = start_date

                    indicators = collector.get_economic_indicator(
                        series_id=sid,
                        start_date=fetch_start,
                        end_date=end_date,
                    )

                    if indicators:
                        count = db.insert_economic_indicators(indicators)
                        total_stored += count
                        print(f"✓ {count} obs")
                    else:
                        print("⚠ No data")

                except Exception as e:
                    print(f"✗ Error: {e}")
                    continue

            print(f"\n{'=' * 60}")
            print(f"✅ Total observations stored: {total_stored}")

        # Print summary statistics
        print(f"\n📊 Database Summary:")
        stats = db.get_table_stats()
        if "economic_indicators" in stats:
            econ_stats = stats["economic_indicators"]
            print(f"   Total observations: {econ_stats.get('total_rows', 0):,}")
            print(f"   Unique series: {econ_stats.get('unique_series', 0)}")
            print(f"   Date range: {econ_stats.get('earliest_date')} to {econ_stats.get('latest_date')}")

    finally:
        db.close()


def main():
    """Main entry point."""
    args = parse_args()

    # List series and exit
    if args.list_series:
        list_available_series()
        return

    # Determine date range
    if args.end_date:
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d")
    else:
        end_date = datetime.now()

    if args.start_date:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
    else:
        start_date = end_date - timedelta(days=365 * args.years)

    # Validate series if specified
    if args.series:
        collector = FREDCollector()
        if args.series not in collector.ECONOMIC_SERIES:
            print(f"❌ Error: Unknown series '{args.series}'")
            print(f"\nUse --list-series to see available series.")
            return

    # Fetch data
    fetch_economic_data(
        start_date=start_date,
        end_date=end_date,
        series_id=args.series,
    )


if __name__ == "__main__":
    main()
