"""Final test: 2x leverage vs buy & hold on all tickers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.storage.market_data_db import MarketDataDB
from src.models.trend_detector import TrendDetector, TradingSignal


def quick_backtest(ticker, start, end, leverage=2.0):
    """Quick backtest with leverage."""
    db = MarketDataDB()

    query = """
        SELECT DATE(timestamp) as date, close
        FROM stock_prices
        WHERE symbol = ? AND DATE(timestamp) >= ? AND DATE(timestamp) <= ?
        ORDER BY timestamp
    """
    data = db.conn.execute(query, [ticker, start, end]).fetchall()

    if not data:
        return None

    detector = TrendDetector(db=db, min_confidence=0.75, confirmation_days=1, long_only=True)

    cash = 10000.0
    shares = 0
    position = None

    for date, price in data:
        price = float(price)
        signal = detector.generate_signal(ticker, date, price)

        if signal.signal == TradingSignal.BUY and position is None:
            lev = leverage if signal.confidence >= 0.75 else 1.0
            shares = (cash * lev) / price
            position = {"entry": price, "lev": lev}
            cash = 0

        elif signal.signal == TradingSignal.SELL and position is not None:
            cash = shares * price
            position = None
            shares = 0

    if position:
        cash = shares * float(data[-1][1])

    strategy_return = (cash / 10000 - 1) * 100
    bh_return = (float(data[-1][1]) / float(data[0][1]) - 1) * 100

    return {"strategy": strategy_return, "buy_hold": bh_return, "ticker": ticker}


tickers = ["AAPL", "NVDA", "BABA", "INTC", "UNH", "MARA", "RIOT", "OPEN"]
print(f"\n{'='*80}")
print("FINAL STRATEGY: 2x Leverage (confidence >= 75%)")
print(f"{'='*80}\n")

print(f"{'Ticker':<8} | {'Strategy':<12} | {'Buy&Hold':<12} | {'Outperform':<12}")
print(f"{'-'*8}-+-{'-'*12}-+-{'-'*12}-+-{'-'*12}")

for ticker in tickers:
    result = quick_backtest(ticker, "2023-01-01", "2025-09-30", leverage=2.0)
    if result:
        outperform = result["strategy"] - result["buy_hold"]
        symbol = "WIN" if outperform > 0 else "LOSE"
        print(
            f"{ticker:<8} | {result['strategy']:>11.2f}% | {result['buy_hold']:>11.2f}% | "
            f"{outperform:>+10.2f}% {symbol}"
        )

print(f"\n{'='*80}\n")
print("Current watchlist signals: python scripts/watchlist_signals.py\n")
