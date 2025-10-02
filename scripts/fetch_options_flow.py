"""
Fetch historical options flow data from Polygon.io.

This script fetches options chain snapshots for all tracked tickers and
stores daily aggregated flow metrics. Designed to backfill up to 2 years
of historical data (limited by Polygon Options Starter plan).

Usage:
    python scripts/fetch_options_flow.py [--days DAYS] [--ticker TICKER]
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

from src.config.tickers import TICKER_SYMBOLS
from src.data.collectors.polygon_options_flow import PolygonOptionsFlow
from src.data.storage.market_data_db import MarketDataDB


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Fetch options flow data from Polygon")
    parser.add_argument(
        "--days", type=int, default=730, help="Number of days to fetch (default: 730 = 2 years)"
    )
    parser.add_argument(
        "--ticker", type=str, help="Specific ticker to fetch (default: all tickers)"
    )
    parser.add_argument(
        "--start-date", type=str, help="Start date in YYYY-MM-DD format (overrides --days)"
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date in YYYY-MM-DD format (default: today)",
    )
    return parser.parse_args()


def get_previous_day_oi(db: MarketDataDB, ticker: str, date: datetime) -> dict[str, int]:
    """
    Get open interest from previous trading day for comparison.

    Args:
        db: Database connection
        ticker: Underlying ticker
        date: Current date

    Returns:
        Dict mapping contract_ticker -> open_interest
    """
    # Look back up to 7 days to find previous trading day
    for days_back in range(1, 8):
        prev_date = date - timedelta(days=days_back)

        query = """
            SELECT contract_ticker, open_interest
            FROM options_contracts_snapshot
            WHERE underlying_ticker = ? AND snapshot_date = DATE(?)
        """

        result = db.conn.execute(query, [ticker, prev_date]).fetchall()

        if result:
            return {row[0]: row[1] for row in result if row[1] is not None}

    return {}


def get_next_monthly_expiration(from_date: datetime) -> str:
    """
    Get the next monthly options expiration date (3rd Friday).

    Args:
        from_date: Date to start searching from

    Returns:
        Expiration date string in YYYY-MM-DD format
    """
    # Start with first day of next month
    if from_date.month == 12:
        year = from_date.year + 1
        month = 1
    else:
        year = from_date.year
        month = from_date.month + 1

    # Find 3rd Friday
    first_day = datetime(year, month, 1)
    # Get to first Friday
    days_until_friday = (4 - first_day.weekday()) % 7
    first_friday = first_day + timedelta(days=days_until_friday)
    # Add 2 more weeks to get 3rd Friday
    third_friday = first_friday + timedelta(weeks=2)

    return third_friday.strftime("%Y-%m-%d")


def fetch_options_flow(
    tickers: list[str], start_date: datetime, end_date: datetime
) -> None:
    """
    Fetch historical options flow data using aggregates endpoint.

    This uses the Options Aggregates API to fetch historical data for key strikes
    (ATM, ±5%, ±10%) instead of snapshots which only return current data.

    Args:
        tickers: List of ticker symbols
        start_date: Start date for data fetch
        end_date: End date for data fetch
    """
    print("📊 Options Flow Data Fetcher (Aggregates Mode)")
    print("=" * 60)
    print(f"Tickers: {len(tickers)}")
    print(f"Date range: {start_date.date()} to {end_date.date()}")
    print(f"Total days: {(end_date - start_date).days}")
    print(f"Strategy: Fetch 6 key strikes (ATM, ±5%, ±10%) per day")
    print("=" * 60)

    with PolygonOptionsFlow() as collector, MarketDataDB() as db:
        total_flow_records = 0
        total_contracts = 0
        errors = []

        for ticker_idx, ticker in enumerate(tickers, 1):
            print(f"\n[{ticker_idx}/{len(tickers)}] {ticker}")
            print("-" * 40)

            ticker_flow_count = 0
            ticker_contract_count = 0

            # Check what dates we already have
            existing_query = """
                SELECT MAX(date) as latest_date
                FROM options_flow_daily
                WHERE ticker = ?
            """
            result = db.conn.execute(existing_query, [ticker]).fetchone()
            latest_date = result[0] if result and result[0] else None

            if latest_date:
                # Resume from day after latest
                fetch_start = datetime.fromisoformat(str(latest_date)) + timedelta(days=1)
                if fetch_start > end_date:
                    print(f"  ✓ Already up to date (latest: {latest_date})")
                    continue
                print(f"  Latest data: {latest_date}, resuming from {fetch_start.date()}")
            else:
                fetch_start = start_date
                print(f"  No existing data, fetching from {fetch_start.date()}")

            # Get expiration date to use (next monthly expiration from start)
            expiration_date = get_next_monthly_expiration(fetch_start)
            print(f"  Using expiration: {expiration_date}")

            # Iterate through dates (market is only open Mon-Fri)
            current_date = fetch_start
            while current_date <= end_date:
                # Skip weekends
                if current_date.weekday() >= 5:  # Saturday=5, Sunday=6
                    current_date += timedelta(days=1)
                    continue

                date_str = current_date.strftime("%Y-%m-%d")

                # Update expiration if we've passed it
                if date_str >= expiration_date:
                    expiration_date = get_next_monthly_expiration(current_date)
                    print(f"\n  Updated expiration: {expiration_date}")

                print(f"  {date_str}...", end=" ", flush=True)

                try:
                    # Get current stock price for calculating strikes
                    price_query = """
                        SELECT close
                        FROM stock_prices
                        WHERE symbol = ? AND DATE(timestamp) = DATE(?)
                        LIMIT 1
                    """
                    price_result = db.conn.execute(
                        price_query, [ticker, current_date]
                    ).fetchone()

                    if not price_result:
                        print("No price data")
                        current_date += timedelta(days=1)
                        continue

                    current_price = float(price_result[0])

                    # Fetch historical options data via aggregates
                    contracts = collector.get_historical_flow_via_aggregates(
                        underlying_ticker=ticker,
                        current_price=current_price,
                        date=current_date,
                        expiration_date=expiration_date,
                    )

                    if not contracts:
                        print("No contracts")
                        current_date += timedelta(days=1)
                        continue

                    # Get previous day OI for comparison
                    # (Note: OI not available in aggregates, so this will be empty)
                    prev_oi = get_previous_day_oi(db, ticker, current_date)

                    # Aggregate to daily flow
                    flow = collector.aggregate_daily_flow(
                        contracts=contracts,
                        ticker=ticker,
                        date=current_date,
                        previous_day_oi=prev_oi,
                    )

                    # Store in database
                    db.insert_options_flow_daily([flow])
                    db.insert_options_contracts(contracts)

                    ticker_flow_count += 1
                    ticker_contract_count += len(contracts)

                    print(f"✓ {len(contracts)} contracts, P/C: {float(flow.put_call_ratio):.2f}")

                except Exception as e:
                    error_msg = f"{ticker} {date_str}: {str(e)[:50]}"
                    errors.append(error_msg)
                    print(f"✗ {str(e)[:30]}")

                current_date += timedelta(days=1)

            print(f"\n  Summary: {ticker_flow_count} days, {ticker_contract_count} contracts")
            total_flow_records += ticker_flow_count
            total_contracts += ticker_contract_count

        # Print final summary
        print(f"\n{'=' * 60}")
        print(f"✅ Options Flow Fetch Complete")
        print(f"\n📊 Summary:")
        print(f"  Flow records: {total_flow_records:,}")
        print(f"  Contracts: {total_contracts:,}")
        print(f"  Errors: {len(errors)}")

        if errors:
            print(f"\n⚠ Errors encountered:")
            for error in errors[:10]:  # Show first 10
                print(f"  - {error}")
            if len(errors) > 10:
                print(f"  ... and {len(errors) - 10} more")

        print(f"\n{'=' * 60}")
        print("✓ Done!")
        print(f"\n💡 Note: Aggregates mode provides volume and price data")
        print("   but lacks greeks, IV, and OI. For complete data with these")
        print("   fields, use snapshots for recent dates only.")
        print("=" * 60)


def main():
    """Main entry point."""
    args = parse_args()

    # Determine date range
    if args.end_date:
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d")
    else:
        end_date = datetime.now()

    if args.start_date:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
    else:
        start_date = end_date - timedelta(days=args.days)

    # Determine tickers
    if args.ticker:
        tickers = [args.ticker.upper()]
    else:
        tickers = TICKER_SYMBOLS

    # Fetch data
    fetch_options_flow(tickers, start_date, end_date)


if __name__ == "__main__":
    main()
