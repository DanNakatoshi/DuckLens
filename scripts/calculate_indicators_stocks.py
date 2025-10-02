"""Calculate technical indicators for AAPL and NVDA."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analysis.indicators import TechnicalIndicators
from src.config.tickers import STOCK_SYMBOLS
from src.data.storage.market_data_db import MarketDataDB


def calculate_indicators(tickers: list[str]) -> None:
    """
    Calculate all technical indicators for stocks.

    Args:
        tickers: List of stock symbols (AAPL, NVDA)
    """
    print(f"\n{'='*70}")
    print(f"CALCULATING INDICATORS: {', '.join(tickers)}")
    print(f"{'='*70}\n")

    with MarketDataDB() as db:
        indicators = TechnicalIndicators(db.db_path)

        for ticker in tickers:
            print(f"[{ticker}] Calculating indicators...")

            try:
                # Calculate all indicators
                result = indicators.calculate_all_indicators(ticker)

                if result.empty:
                    print(f"  ERROR: No data to calculate indicators")
                    continue

                # Convert DataFrame to list of dicts for insertion
                records = result.to_dict("records")

                # Insert into database
                db.insert_technical_indicators(records)

                print(f"  -> Success: {len(records)} records saved to database")
                print(f"     Indicators: SMA, EMA, MACD, RSI, BB, ATR, Stochastic, OBV")

            except Exception as e:
                print(f"  ERROR: {e}")
                import traceback
                traceback.print_exc()

    print(f"\n{'='*70}")
    print("-> Indicator calculation complete")
    print(f"{'='*70}\n")


def main():
    """Main entry point."""
    tickers = STOCK_SYMBOLS  # AAPL, NVDA
    calculate_indicators(tickers)


if __name__ == "__main__":
    main()
