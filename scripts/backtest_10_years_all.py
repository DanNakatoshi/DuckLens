"""Backtest 2x leverage strategy on all watchlist tickers - 10 YEARS."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.tickers import TICKER_SYMBOLS
from src.data.storage.market_data_db import MarketDataDB
from src.models.trend_detector import TrendDetector, TradingSignal


def detailed_backtest(ticker, start, end, leverage=2.0):
    """Backtest with 2x leverage and detailed stats."""
    db = MarketDataDB()

    query = """
        SELECT DATE(timestamp) as date, close
        FROM stock_prices
        WHERE symbol = ? AND DATE(timestamp) >= ? AND DATE(timestamp) <= ?
        ORDER BY timestamp
    """
    data = db.conn.execute(query, [ticker, start, end]).fetchall()

    if not data or len(data) < 200:  # Need at least 200 days for 10-year test
        return None

    detector = TrendDetector(db=db, min_confidence=0.75, confirmation_days=1, long_only=True)

    cash = 10000.0
    shares = 0
    position = None
    trades = []

    for date, price in data:
        price = float(price)
        signal = detector.generate_signal(ticker, date, price)

        if signal.signal == TradingSignal.BUY and position is None:
            lev = leverage if signal.confidence >= 0.75 else 1.0
            shares = (cash * lev) / price
            position = {"entry_date": date, "entry_price": price, "lev": lev}
            cash = 0

        elif signal.signal == TradingSignal.SELL and position is not None:
            cash = shares * price
            pnl = cash - 10000.0
            pnl_pct = (cash / 10000 - 1) * 100
            hold_days = (date - position["entry_date"]).days

            trades.append({
                "entry_date": position["entry_date"],
                "exit_date": date,
                "entry_price": position["entry_price"],
                "exit_price": price,
                "pnl_pct": pnl_pct,
                "hold_days": hold_days,
            })

            position = None
            shares = 0

    # Close final position
    if position:
        final_price = float(data[-1][1])
        cash = shares * final_price
        pnl_pct = (cash / 10000 - 1) * 100
        hold_days = (data[-1][0] - position["entry_date"]).days

        trades.append({
            "entry_date": position["entry_date"],
            "exit_date": data[-1][0],
            "entry_price": position["entry_price"],
            "exit_price": final_price,
            "pnl_pct": pnl_pct,
            "hold_days": hold_days,
        })

    strategy_return = (cash / 10000 - 1) * 100
    bh_return = (float(data[-1][1]) / float(data[0][1]) - 1) * 100

    # Calculate win rate
    winning_trades = [t for t in trades if t["pnl_pct"] > 0]
    win_rate = (len(winning_trades) / len(trades) * 100) if trades else 0

    # Calculate average hold time
    avg_hold_days = sum(t["hold_days"] for t in trades) / len(trades) if trades else 0

    return {
        "strategy": strategy_return,
        "buy_hold": bh_return,
        "ticker": ticker,
        "trades": len(trades),
        "win_rate": win_rate,
        "avg_hold_days": avg_hold_days,
        "first_date": data[0][0],
        "last_date": data[-1][0],
    }


def main():
    """Main entry point."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=10 * 365)  # 10 years

    print(f"\n{'='*110}")
    print("2X LEVERAGE STRATEGY - 10 YEAR BACKTEST - ALL WATCHLIST TICKERS")
    print(f"{'='*110}")
    print(f"Period: {start_date.date()} to {end_date.date()}")
    print("Strategy: 2x leverage on high confidence (>75%) | Death cross exit | Long-only")
    print(f"{'='*110}\n")

    print(f"{'Ticker':<8} | {'Strategy':<12} | {'Buy&Hold':<12} | {'Outperform':<13} | {'Trades':<7} | {'Win%':<6} | {'Avg Days':<9} | {'Result':<6}")
    print(f"{'-'*8}-+-{'-'*12}-+-{'-'*12}-+-{'-'*13}-+-{'-'*7}-+-{'-'*6}-+-{'-'*9}-+-{'-'*6}")

    results = []
    winners = []
    losers = []
    no_data = []

    for ticker in sorted(TICKER_SYMBOLS):
        result = detailed_backtest(ticker, start_date, end_date, leverage=2.0)

        if result:
            outperform = result["strategy"] - result["buy_hold"]
            status = "WIN" if outperform > 0 else "LOSE"

            if outperform > 0:
                winners.append((ticker, outperform))
            else:
                losers.append((ticker, outperform))

            results.append(result)

            print(
                f"{ticker:<8} | {result['strategy']:>11.2f}% | {result['buy_hold']:>11.2f}% | "
                f"{outperform:>+11.2f}% | {result['trades']:>6} | {result['win_rate']:>5.1f}% | "
                f"{result['avg_hold_days']:>8.0f} | {status:<6}"
            )
        else:
            no_data.append(ticker)
            print(f"{ticker:<8} | {'N/A':<12} | {'N/A':<12} | {'N/A':<13} | {'N/A':<7} | {'N/A':<6} | {'N/A':<9} | NO DATA")

    # Summary
    total_tested = len(winners) + len(losers)
    win_rate = (len(winners) / total_tested * 100) if total_tested > 0 else 0

    print(f"\n{'-'*110}")
    print(f"SUMMARY: {len(winners)} Winners | {len(losers)} Losers | Win Rate: {win_rate:.1f}%")
    print(f"{'-'*110}\n")

    if winners:
        print("TOP 10 PERFORMERS (by outperformance vs Buy&Hold):")
        for i, (ticker, outperform) in enumerate(sorted(winners, key=lambda x: x[1], reverse=True)[:10], 1):
            ticker_result = [r for r in results if r["ticker"] == ticker][0]
            print(f"  {i:2}. {ticker:<8} +{outperform:>8.2f}%  ({ticker_result['trades']} trades, {ticker_result['win_rate']:.0f}% win rate, {ticker_result['avg_hold_days']:.0f} day avg hold)")

    if losers:
        print(f"\nWORST 5 PERFORMERS:")
        for i, (ticker, outperform) in enumerate(sorted(losers, key=lambda x: x[1])[:5], 1):
            ticker_result = [r for r in results if r["ticker"] == ticker][0]
            print(f"  {i}. {ticker:<8} {outperform:>8.2f}%  ({ticker_result['trades']} trades, {ticker_result['win_rate']:.0f}% win rate)")

    if no_data:
        print(f"\nNO DATA ({len(no_data)} tickers):")
        print(f"  {', '.join(no_data)}")
        print(f"  Run: python scripts/fetch_10_years_all.py")

    # Overall stats
    if results:
        avg_strategy_return = sum(r["strategy"] for r in results) / len(results)
        avg_bh_return = sum(r["buy_hold"] for r in results) / len(results)
        avg_trades = sum(r["trades"] for r in results) / len(results)
        avg_win_rate = sum(r["win_rate"] for r in results) / len(results)
        avg_hold_days = sum(r["avg_hold_days"] for r in results) / len(results)

        print(f"\n{'-'*110}")
        print("PORTFOLIO AVERAGES (across all tickers):")
        print(f"  Avg Strategy Return:  {avg_strategy_return:>8.2f}%")
        print(f"  Avg Buy&Hold Return:  {avg_bh_return:>8.2f}%")
        print(f"  Avg Outperformance:   {avg_strategy_return - avg_bh_return:>+8.2f}%")
        print(f"  Avg Trades per Stock: {avg_trades:>8.1f}")
        print(f"  Avg Win Rate:         {avg_win_rate:>8.1f}%")
        print(f"  Avg Hold Period:      {avg_hold_days:>8.0f} days ({avg_hold_days/365:.1f} years)")
        print(f"{'-'*110}\n")

    print("Next steps:")
    print("1. Run: .\\tasks.ps1 watchlist  (see current BUY signals)")
    print("2. Run: .\\tasks.ps1 portfolio  (review your positions)")
    print("3. Review top performers above for trading opportunities\n")


if __name__ == "__main__":
    main()
