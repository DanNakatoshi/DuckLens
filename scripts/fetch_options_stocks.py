"""Fetch options flow data for AAPL and NVDA."""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from src.config.tickers import STOCK_SYMBOLS
from src.data.collectors.polygon_options_flow import PolygonOptionsFlow
from src.data.storage.market_data_db import MarketDataDB

# Load environment variables
load_dotenv()


def fetch_options_flow(tickers: list[str], days_back: int = 90) -> None:
    """
    Fetch recent options flow for stocks.

    Args:
        tickers: List of stock symbols (AAPL, NVDA)
        days_back: Number of days to fetch (default 90 = ~3 months)
    """
    print(f"\n{'='*70}")
    print(f"FETCHING OPTIONS FLOW: {', '.join(tickers)}")
    print(f"{'='*70}\n")

    end_date = datetime(2025, 9, 30)
    start_date = end_date - timedelta(days=days_back)

    print(f"Date range: {start_date.date()} to {end_date.date()}")
    print(f"Days: {days_back}\n")

    with PolygonOptionsFlow() as flow, MarketDataDB() as db:
        for ticker in tickers:
            print(f"[{ticker}] Fetching options data...")

            try:
                # Get current price to calculate strike range
                price_query = """
                    SELECT close
                    FROM stock_prices
                    WHERE symbol = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                """
                result = db.conn.execute(price_query, [ticker]).fetchone()

                if not result:
                    print(f"  ERROR: No price data found")
                    continue

                current_price = float(result[0])
                print(f"  Current price: ${current_price:.2f}")

                # Fetch daily snapshots for last 90 days
                total_records = 0
                current_date = start_date

                while current_date <= end_date:
                    try:
                        # Get options snapshot for this date
                        contracts = flow.get_options_snapshot(
                            ticker, current_date, strike_range_pct=0.15
                        )

                        if contracts:
                            # Aggregate and save
                            daily_flow = flow.aggregate_daily_flow(
                                ticker, current_date, contracts
                            )
                            db.insert_options_flow([daily_flow])
                            total_records += 1

                            if total_records % 10 == 0:
                                print(f"  Progress: {total_records} days processed")

                    except Exception as e:
                        if "404" not in str(e):  # Skip 404s (no data for that day)
                            print(f"  WARN {current_date.date()}: {e}")

                    current_date += timedelta(days=1)

                print(f"  -> Total: {total_records} days of flow data")

            except Exception as e:
                print(f"  ERROR: {e}")

    print(f"\n{'='*70}")
    print("-> Options flow fetch complete")
    print(f"{'='*70}\n")


def main():
    """Main entry point."""
    tickers = STOCK_SYMBOLS  # AAPL, NVDA
    fetch_options_flow(tickers, days_back=90)


if __name__ == "__main__":
    main()
