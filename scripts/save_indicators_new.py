"""Calculate and save indicators for new stocks."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analysis.indicators import TechnicalIndicators
from src.data.storage.market_data_db import MarketDataDB

NEW_TICKERS = ["BABA", "INTC", "IREN", "OPEN", "UNH", "MARA", "RIOT"]


def save_indicators(tickers: list[str]) -> None:
    """Calculate and save indicators."""
    print(f"\n{'='*70}")
    print(f"CALCULATING INDICATORS: {', '.join(tickers)}")
    print(f"{'='*70}\n")

    with MarketDataDB() as db:
        indicators = TechnicalIndicators(db.db_path)

        for ticker in tickers:
            print(f"[{ticker}] Calculating indicators...")

            try:
                df = indicators.calculate_all_indicators(ticker)

                if df.empty:
                    print(f"  ERROR: No data")
                    continue

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

                # Delete existing
                db.conn.execute("DELETE FROM technical_indicators WHERE symbol = ?", [ticker])

                # Insert
                db.conn.register("temp_indicators", df)
                col_list = ", ".join(df.columns)
                db.conn.execute(f"""
                    INSERT INTO technical_indicators ({col_list})
                    SELECT {col_list} FROM temp_indicators
                """)
                db.conn.unregister("temp_indicators")

                print(f"  -> Success: {len(df)} records saved")

            except Exception as e:
                print(f"  ERROR: {e}")

    print(f"\n{'='*70}")
    print("-> Complete")
    print(f"{'='*70}\n")


def main():
    save_indicators(NEW_TICKERS)


if __name__ == "__main__":
    main()
