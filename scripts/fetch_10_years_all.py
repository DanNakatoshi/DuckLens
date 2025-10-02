"""Fetch 10 years of historical data for all watchlist tickers."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from src.analysis.indicators import TechnicalIndicators
from src.config.tickers import TICKER_SYMBOLS
from src.data.collectors.polygon_collector import PolygonCollector
from src.data.storage.market_data_db import MarketDataDB

load_dotenv()


def fetch_ticker_data(ticker: str, start_date: datetime, end_date: datetime, db: MarketDataDB, collector: PolygonCollector) -> int:
    """Fetch data for a single ticker."""

    # Check if already exists
    latest_date = db.get_latest_date(ticker)
    if latest_date:
        if latest_date.date() >= end_date.date():
            print(f"  [{ticker}] Already up to date (latest: {latest_date.date()})")
            return 0
        fetch_start = latest_date + timedelta(days=1)
        print(f"  [{ticker}] Updating from {fetch_start.date()}")
    else:
        fetch_start = start_date
        print(f"  [{ticker}] Fetching {(end_date - start_date).days // 365} years")

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

        except Exception as e:
            print(f"    ERROR: {e}")
            break

        current_start = current_end + timedelta(days=1)

    if total_records > 0:
        print(f"  [{ticker}] Fetched {total_records} bars")

    return total_records


def calculate_indicators_for_ticker(ticker: str, db: MarketDataDB) -> bool:
    """Calculate and save technical indicators for a ticker."""
    try:
        indicators_calc = TechnicalIndicators(db.db_path)
        df = indicators_calc.calculate_all_indicators(ticker)

        if df.empty:
            print(f"  [{ticker}] No data to calculate indicators")
            return False

        # Save indicators
        df["symbol"] = ticker
        df = df.reset_index()
        df = df.rename(columns={"date": "timestamp"})

        columns = [
            "symbol", "timestamp", "sma_20", "sma_50", "sma_200",
            "ema_12", "ema_26", "macd", "macd_signal", "macd_histogram",
            "rsi_14", "bb_middle", "bb_upper", "bb_lower",
            "atr_14", "stoch_k", "stoch_d", "obv", "adx"
        ]

        df = df[[col for col in columns if col in df.columns]]

        # Convert numpy types to Python native types
        for col in df.columns:
            if df[col].dtype == 'float64' or df[col].dtype == 'float32':
                df[col] = df[col].astype(float)
            elif df[col].dtype == 'int64' or df[col].dtype == 'int32':
                df[col] = df[col].astype(int)

        db.conn.execute("DELETE FROM technical_indicators WHERE symbol = ?", [ticker])
        db.conn.register("temp_indicators", df)
        col_list = ", ".join(df.columns)
        db.conn.execute(f"""
            INSERT INTO technical_indicators ({col_list})
            SELECT {col_list} FROM temp_indicators
        """)
        db.conn.unregister("temp_indicators")

        print(f"  [{ticker}] Indicators calculated: {len(df)} records")
        return True

    except Exception as e:
        print(f"  [{ticker}] Indicator error: {e}")
        return False


def main():
    """Main entry point."""
    print("=" * 80)
    print("FETCH 10 YEARS OF HISTORICAL DATA - ALL WATCHLIST TICKERS")
    print("=" * 80)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=10 * 365)  # 10 years

    print(f"\nDate Range: {start_date.date()} to {end_date.date()}")
    print(f"Tickers: {len(TICKER_SYMBOLS)}")
    print(f"\nThis will take 20-40 minutes depending on API rate limits...\n")

    # Step 1: Fetch all OHLCV data
    print("=" * 80)
    print("STEP 1: FETCH OHLCV DATA")
    print("=" * 80)

    total_fetched = 0
    total_tickers = len(TICKER_SYMBOLS)
    success_count = 0

    with PolygonCollector() as collector, MarketDataDB() as db:
        for i, ticker in enumerate(TICKER_SYMBOLS, 1):
            print(f"\n[{i}/{total_tickers}] {ticker}")

            try:
                records = fetch_ticker_data(ticker, start_date, end_date, db, collector)
                total_fetched += records
                success_count += 1
            except Exception as e:
                print(f"  [{ticker}] FAILED: {e}")

        print(f"\n{'=' * 80}")
        print(f"OHLCV FETCH COMPLETE")
        print(f"{'=' * 80}")
        print(f"Success: {success_count}/{total_tickers} tickers")
        print(f"Total records: {total_fetched:,}")

    # Step 2: Calculate indicators
    print(f"\n{'=' * 80}")
    print("STEP 2: CALCULATE TECHNICAL INDICATORS")
    print(f"{'=' * 80}\n")

    indicator_success = 0

    with MarketDataDB() as db:
        for i, ticker in enumerate(TICKER_SYMBOLS, 1):
            print(f"[{i}/{total_tickers}] {ticker}")

            if calculate_indicators_for_ticker(ticker, db):
                indicator_success += 1

    # Summary
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")
    print(f"OHLCV Data:   {success_count}/{total_tickers} tickers ({total_fetched:,} bars)")
    print(f"Indicators:   {indicator_success}/{total_tickers} tickers")
    print(f"{'=' * 80}\n")

    print("Next steps:")
    print("1. Run: .\\tasks.ps1 backtest-all  (backtest 10 years)")
    print("2. Run: .\\tasks.ps1 watchlist     (see current signals)")
    print("3. Run: .\\tasks.ps1 portfolio     (review your positions)\n")


if __name__ == "__main__":
    main()
