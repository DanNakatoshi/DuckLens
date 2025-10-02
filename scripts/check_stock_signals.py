"""Check what signals are being generated for AAPL."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.storage.market_data_db import MarketDataDB
from src.models.trend_detector import TrendDetector


def check_signals(ticker: str, num_days: int = 20) -> None:
    """Check recent signals for a ticker."""
    db = MarketDataDB()

    detector = TrendDetector(
        db=db,
        min_confidence=0.6,
        block_high_impact_events=True,
        min_adx=0,
        confirmation_days=1,
        long_only=True,
    )

    # Get recent prices
    query = """
        SELECT DATE(timestamp) as date, close
        FROM stock_prices
        WHERE symbol = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """
    results = db.conn.execute(query, [ticker, num_days]).fetchall()
    results = list(reversed(results))  # Oldest first

    print(f"\n{'='*70}")
    print(f"SIGNAL CHECK: {ticker} (last {num_days} days)")
    print(f"{'='*70}\n")

    for date, price in results:
        price = float(price)
        signal_data = detector.generate_signal(ticker, date, price)

        print(f"{date} | ${price:>8.2f} | {signal_data.signal.value:<12} | Conf: {signal_data.confidence:.0%}")
        print(f"  {signal_data.reasoning}")
        print()


if __name__ == "__main__":
    check_signals("AAPL", num_days=20)
