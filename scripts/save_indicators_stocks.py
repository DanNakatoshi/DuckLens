"""Calculate and save technical indicators for AAPL and NVDA."""

import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analysis.indicators import TechnicalIndicators
from src.config.tickers import STOCK_SYMBOLS
from src.data.storage.market_data_db import MarketDataDB


def save_indicators(tickers: list[str]) -> None:
    """
    Calculate and save all technical indicators for stocks.

    Args:
        tickers: List of stock symbols (AAPL, NVDA)
    """
    print(f"\n{'='*70}")
    print(f"CALCULATING & SAVING INDICATORS: {', '.join(tickers)}")
    print(f"{'='*70}\n")

    with MarketDataDB() as db:
        indicators = TechnicalIndicators(db.db_path)

        for ticker in tickers:
            print(f"[{ticker}] Calculating indicators...")

            try:
                # Calculate all indicators
                df = indicators.calculate_all_indicators(ticker)

                if df.empty:
                    print(f"  ERROR: No data to calculate indicators")
                    continue

                # Add symbol column
                df["symbol"] = ticker

                # Reset index to get date as a column
                df = df.reset_index()

                # Rename columns to match database schema
                df = df.rename(
                    columns={
                        "date": "timestamp",
                    }
                )

                # Select only columns that exist in database
                columns = [
                    "symbol",
                    "timestamp",
                    "sma_20",
                    "sma_50",
                    "sma_200",
                    "ema_12",
                    "ema_26",
                    "macd",
                    "macd_signal",
                    "macd_histogram",
                    "rsi_14",
                    "bb_middle",
                    "bb_upper",
                    "bb_lower",
                    "atr_14",
                    "stoch_k",
                    "stoch_d",
                    "obv",
                ]

                # Filter to existing columns
                df = df[[col for col in columns if col in df.columns]]

                # Convert numpy types to Python types for DuckDB compatibility
                for col in df.columns:
                    if df[col].dtype == 'float64' or df[col].dtype == 'float32':
                        df[col] = df[col].astype(float)
                    elif df[col].dtype == 'int64' or df[col].dtype == 'int32':
                        df[col] = df[col].astype(int)

                # Delete existing data for this symbol first
                db.conn.execute("DELETE FROM technical_indicators WHERE symbol = ?", [ticker])

                # Insert using DuckDB register
                db.conn.register("temp_indicators", df)

                col_list = ", ".join(df.columns)
                insert_sql = f"""
                    INSERT INTO technical_indicators ({col_list})
                    SELECT {col_list} FROM temp_indicators
                """

                db.conn.execute(insert_sql)
                db.conn.unregister("temp_indicators")
                total_inserted = len(df)

                print(f"  -> Success: {total_inserted} records saved to database")
                print(f"     Indicators: {', '.join([c for c in df.columns if c not in ['symbol', 'timestamp']])}")

            except Exception as e:
                print(f"  ERROR: {e}")
                import traceback
                traceback.print_exc()

    print(f"\n{'='*70}")
    print("-> Indicator save complete")
    print(f"{'='*70}\n")


def main():
    """Main entry point."""
    tickers = STOCK_SYMBOLS  # AAPL, NVDA
    save_indicators(tickers)


if __name__ == "__main__":
    main()
