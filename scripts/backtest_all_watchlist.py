"""Backtest 2x leverage strategy on all watchlist tickers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.tickers import TRADING_WATCHLIST
from src.data.storage.market_data_db import MarketDataDB
from src.models.trend_detector import TrendDetector, TradingSignal


def quick_backtest(ticker, start, end, leverage=2.0):
    """Quick backtest with 2x leverage."""
    db = MarketDataDB()

    query = """
        SELECT DATE(timestamp) as date, close
        FROM stock_prices
        WHERE symbol = ? AND DATE(timestamp) >= ? AND DATE(timestamp) <= ?
        ORDER BY timestamp
    """
    data = db.conn.execute(query, [ticker, start, end]).fetchall()

    if not data or len(data) < 50:
        return None

    detector = TrendDetector(db=db, min_confidence=0.75, confirmation_days=1, long_only=True)

    cash = 10000.0
    shares = 0
    position = None
    num_trades = 0

    for date, price in data:
        price = float(price)
        signal = detector.generate_signal(ticker, date, price)

        if signal.signal == TradingSignal.BUY and position is None:
            lev = leverage if signal.confidence >= 0.75 else 1.0
            shares = (cash * lev) / price
            position = {"entry": price, "lev": lev}
            cash = 0
            num_trades += 1

        elif signal.signal == TradingSignal.SELL and position is not None:
            cash = shares * price
            position = None
            shares = 0

    if position:
        cash = shares * float(data[-1][1])

    strategy_return = (cash / 10000 - 1) * 100
    bh_return = (float(data[-1][1]) / float(data[0][1]) - 1) * 100

    return {
        "strategy": strategy_return,
        "buy_hold": bh_return,
        "ticker": ticker,
        "trades": num_trades,
    }


print(f"\n{'='*90}")
print("2X LEVERAGE STRATEGY - ALL WATCHLIST TICKERS")
print(f"{'='*90}")
print("Period: 2023-01-01 to 2025-09-30")
print("Min Confidence: 75% | Confirmation: 1 day | Long-only")
print(f"{'='*90}\n")

print(f"{'Ticker':<8} | {'Strategy':<12} | {'Buy&Hold':<12} | {'Outperform':<12} | {'Trades':<8} | {'Result':<6}")
print(f"{'-'*8}-+-{'-'*12}-+-{'-'*12}-+-{'-'*12}-+-{'-'*8}-+-{'-'*6}")

winners = []
losers = []

for ticker in sorted(TRADING_WATCHLIST):
    result = quick_backtest(ticker, "2023-01-01", "2025-09-30", leverage=2.0)
    if result:
        outperform = result["strategy"] - result["buy_hold"]
        status = "WIN" if outperform > 0 else "LOSE"

        if outperform > 0:
            winners.append((ticker, outperform))
        else:
            losers.append((ticker, outperform))

        print(
            f"{ticker:<8} | {result['strategy']:>11.2f}% | {result['buy_hold']:>11.2f}% | "
            f"{outperform:>+10.2f}% | {result['trades']:>7} | {status:<6}"
        )
    else:
        print(f"{ticker:<8} | {'N/A':<12} | {'N/A':<12} | {'N/A':<12} | {'N/A':<8} | NO DATA")

print(f"\n{'-'*90}")
print(f"SUMMARY: {len(winners)} Winners | {len(losers)} Losers | Win Rate: {len(winners)/(len(winners)+len(losers))*100:.1f}%")
print(f"{'-'*90}\n")

if winners:
    print("TOP 5 PERFORMERS:")
    for ticker, outperform in sorted(winners, key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {ticker:<8} +{outperform:>8.2f}% vs Buy&Hold")
    print()

print("Run watchlist: python scripts/watchlist_signals.py\n")
