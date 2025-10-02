"""Add a new ticker to watchlist and fetch data."""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from src.analysis.indicators import TechnicalIndicators
from src.data.collectors.polygon_collector import PolygonCollector
from src.data.storage.market_data_db import MarketDataDB

load_dotenv()


def add_ticker(ticker: str, years: int = 5):
    """
    Add a new ticker to the system.

    Steps:
    1. Fetch 5 years of historical data
    2. Calculate technical indicators
    3. Ready for trading!

    Args:
        ticker: Stock symbol to add
        years: Years of history to fetch
    """
    ticker = ticker.upper()

    print(f"\n{'='*70}")
    print(f"ADDING TICKER: {ticker}")
    print(f"{'='*70}\n")

    # Step 1: Fetch historical data
    print(f"[1/2] Fetching {years} years of historical data...")

    end_date = datetime.now()
    start_date = end_date - timedelta(days=years * 365)

    with PolygonCollector() as collector, MarketDataDB() as db:
        # Check if already exists
        latest_date = db.get_latest_date(ticker)
        if latest_date:
            print(f"  Found existing data up to: {latest_date.date()}")
            if latest_date.date() >= end_date.date():
                print(f"  -> Already up to date!")
            else:
                fetch_start = latest_date + timedelta(days=1)
                print(f"  Updating from {fetch_start.date()} to {end_date.date()}...")
        else:
            fetch_start = start_date
            print(f"  Fetching from {fetch_start.date()} to {end_date.date()}...")

        # Fetch in yearly batches
        total_records = 0
        current_start = fetch_start

        while current_start < end_date:
            current_end = min(current_start + timedelta(days=365), end_date)

            try:
                prices = collector.get_stock_prices(ticker, current_start, current_end)

                if prices:
                    count = db.insert_stock_prices(prices)
                    total_records += count
                    print(f"    {current_start.date()} to {current_end.date()}: {count} bars")
                else:
                    print(f"    {current_start.date()} to {current_end.date()}: No data")

            except Exception as e:
                print(f"    ERROR: {e}")
                return False

            current_start = current_end + timedelta(days=1)

        if total_records == 0 and not latest_date:
            print(f"  ERROR: No data found for {ticker}")
            print(f"  Make sure ticker symbol is correct")
            return False

        print(f"  -> Total: {total_records} new bars fetched\n")

        # Step 2: Calculate indicators
        print(f"[2/2] Calculating technical indicators...")

        try:
            indicators_calc = TechnicalIndicators(db.db_path)
            df = indicators_calc.calculate_all_indicators(ticker)

            if df.empty:
                print(f"  ERROR: Could not calculate indicators")
                return False

            # Save indicators
            df["symbol"] = ticker
            df = df.reset_index()
            df = df.rename(columns={"date": "timestamp"})

            columns = [
                "symbol", "timestamp", "sma_20", "sma_50", "sma_200",
                "ema_12", "ema_26", "macd", "macd_signal", "macd_histogram",
                "rsi_14", "bb_middle", "bb_upper", "bb_lower",
                "atr_14", "stoch_k", "stoch_d", "obv",
            ]

            df = df[[col for col in columns if col in df.columns]]

            db.conn.execute("DELETE FROM technical_indicators WHERE symbol = ?", [ticker])
            db.conn.register("temp_indicators", df)
            col_list = ", ".join(df.columns)
            db.conn.execute(f"""
                INSERT INTO technical_indicators ({col_list})
                SELECT {col_list} FROM temp_indicators
            """)
            db.conn.unregister("temp_indicators")

            print(f"  -> Success: {len(df)} indicator records saved\n")

        except Exception as e:
            print(f"  ERROR: {e}\n")
            return False

    print(f"{'='*70}")
    print(f"SUCCESS! {ticker} added to system")
    print(f"{'='*70}\n")

    print(f"Next steps:")
    print(f"1. Run 'python scripts/watchlist_signals.py' to see if there's a signal")
    print(f"2. Run 'python scripts/backtest_all_watchlist.py' to backtest")
    print(f"3. Add to src/config/tickers.py TIER_2_STOCKS for permanent watchlist\n")

    return True


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("\nUsage: python scripts/add_ticker.py <SYMBOL>")
        print("Example: python scripts/add_ticker.py MSFT\n")
        return

    ticker = sys.argv[1]
    add_ticker(ticker)


if __name__ == "__main__":
    main()
