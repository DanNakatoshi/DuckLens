"""
Build economic calendar from existing FRED indicator data.

This script analyzes the economic_indicators table and creates calendar events
for each data release (CPI, NFP, GDP, FOMC, etc.). This provides a historical
record of when economic events occurred for feature engineering.

Usage:
    python scripts/build_economic_calendar.py [--years YEARS]
"""

import argparse
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
from dotenv import load_dotenv

load_dotenv()

from src.data.storage.market_data_db import MarketDataDB
from src.models.schemas import EconomicCalendarEvent


# Mapping of FRED series to calendar event types
SERIES_TO_EVENT_TYPE = {
    # CPI releases (monthly, high impact)
    "CPIAUCSL": ("CPI", "Consumer Price Index Release", "high"),
    "CPILFESL": ("CPI", "Core CPI Release", "high"),
    # Employment (monthly, high impact)
    "PAYEMS": ("NFP", "Nonfarm Payrolls Release", "high"),
    "UNRATE": ("NFP", "Unemployment Rate Release", "high"),
    "ICSA": ("JOBLESS_CLAIMS", "Initial Jobless Claims", "medium"),
    # PCE (monthly, high impact - Fed's preferred inflation gauge)
    "PCEPI": ("PCE", "PCE Price Index Release", "high"),
    "PCEPILFE": ("PCE", "Core PCE Release", "high"),
    # GDP (quarterly, high impact)
    "GDP": ("GDP", "GDP Release", "high"),
    "GDPC1": ("GDP", "Real GDP Release", "high"),
    # Retail Sales (monthly, medium impact)
    "RSXFS": ("RETAIL_SALES", "Retail Sales Release", "medium"),
    # Housing (monthly, medium impact)
    "HOUST": ("HOUSING_STARTS", "Housing Starts Release", "medium"),
    "PERMIT": ("HOUSING_STARTS", "Building Permits Release", "medium"),
    # Consumer Sentiment (monthly, medium impact)
    "UMCSENT": ("CONSUMER_SENTIMENT", "Consumer Sentiment Release", "medium"),
    # Fed Funds (monthly, high impact - FOMC decisions)
    "FEDFUNDS": ("FOMC", "FOMC Meeting / Fed Funds Rate", "high"),
}


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Build economic calendar from FRED data"
    )
    parser.add_argument(
        "--years",
        type=int,
        help="Number of years to process (default: all available data)",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild entire calendar (default: only add new events)",
    )
    return parser.parse_args()


def calculate_previous_value(
    db: MarketDataDB, series_id: str, current_date: datetime
) -> Decimal | None:
    """Get the previous period's value for comparison."""
    # Look back up to 60 days for previous value
    start_date = current_date - timedelta(days=60)
    end_date = current_date - timedelta(days=1)

    indicators = db.get_economic_indicators(
        series_id=series_id, start_date=start_date, end_date=end_date
    )

    if indicators:
        # Get most recent value before current date
        latest = max(indicators, key=lambda x: x["date"])
        return Decimal(str(latest["value"])) if latest["value"] is not None else None

    return None


def build_calendar_from_indicators(years: int | None = None) -> None:
    """
    Build economic calendar events from indicator data.

    Args:
        years: Number of years to process (None = all data)
    """
    print("📅 Building Economic Calendar from FRED Data")
    print("=" * 60)

    db = MarketDataDB()

    try:
        # Determine date range
        if years:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365 * years)
            print(f"Processing last {years} years: {start_date.date()} to {end_date.date()}")
        else:
            start_date = None
            end_date = None
            print(f"Processing all available data")

        total_events = 0
        events_by_type = {}

        print(f"\n📊 Processing {len(SERIES_TO_EVENT_TYPE)} indicator series...\n")

        for series_id, (event_type, event_name, impact) in SERIES_TO_EVENT_TYPE.items():
            try:
                print(f"  {series_id:<15} {event_name[:40]:<40}", end=" ")

                # Get all observations for this series
                indicators = db.get_economic_indicators(
                    series_id=series_id, start_date=start_date, end_date=end_date
                )

                if not indicators:
                    print("⚠ No data")
                    continue

                # Create calendar event for each observation
                events = []
                for ind in indicators:
                    release_date = datetime.combine(ind["date"], datetime.min.time())

                    # Get previous value for context
                    previous_value = calculate_previous_value(db, series_id, release_date)

                    # Create event
                    event = EconomicCalendarEvent(
                        event_id=f"{event_type}_{release_date.strftime('%Y%m%d')}_{series_id}",
                        event_type=event_type,
                        event_name=event_name,
                        release_date=release_date,
                        actual_value=(
                            Decimal(str(ind["value"])) if ind["value"] is not None else None
                        ),
                        forecast_value=None,  # No forecast data from FRED
                        previous_value=previous_value,
                        surprise=None,  # Can't calculate without forecast
                        impact=impact,
                        description=f"{ind['indicator_name']} ({series_id})",
                    )
                    events.append(event)

                # Insert events
                if events:
                    count = db.insert_calendar_events(events)
                    total_events += count
                    events_by_type[event_type] = events_by_type.get(event_type, 0) + count
                    print(f"✓ {count} events")
                else:
                    print("⚠ No events")

            except Exception as e:
                print(f"✗ Error: {str(e)[:30]}")
                continue

        # Print summary
        print(f"\n{'=' * 60}")
        print(f"✅ Calendar Build Complete")
        print(f"\n📊 Summary by Event Type:")
        for event_type, count in sorted(events_by_type.items()):
            print(f"  {event_type:<20} {count:>6} events")

        print(f"\n📈 Total Events Created: {total_events:,}")

        # Show recent events
        print(f"\n📅 Recent Events (last 30 days):")
        recent_date = datetime.now() - timedelta(days=30)
        recent_events = db.conn.execute(
            """
            SELECT event_type, event_name, release_date, actual_value, impact
            FROM economic_calendar
            WHERE release_date >= ?
            ORDER BY release_date DESC
            LIMIT 10
        """,
            [recent_date],
        ).fetchall()

        if recent_events:
            print(f"\n{'Date':<12} {'Type':<10} {'Event':<35} {'Value':<10} {'Impact'}")
            print("-" * 80)
            for event in recent_events:
                date_str = event[2].strftime("%Y-%m-%d") if event[2] else "N/A"
                value_str = f"{event[3]:.2f}" if event[3] else "N/A"
                print(
                    f"{date_str:<12} {event[0]:<10} {event[1][:35]:<35} {value_str:<10} {event[4]}"
                )
        else:
            print("  No recent events found")

    finally:
        db.close()

    print(f"\n{'=' * 60}")
    print("✓ Done!")
    print("=" * 60)


def main():
    """Main entry point."""
    args = parse_args()

    build_calendar_from_indicators(years=args.years)


if __name__ == "__main__":
    main()
