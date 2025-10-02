"""Backtest trend strategy on AAPL and NVDA."""

import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.tickers import STOCK_SYMBOLS
from src.data.storage.market_data_db import MarketDataDB
from src.models.trend_detector import TrendDetector, TradingSignal


def backtest_stock(ticker: str, start_date: str, end_date: str) -> dict:
    """
    Backtest trend strategy on a single stock.

    Args:
        ticker: Stock symbol (AAPL, NVDA)
        start_date: Start date YYYY-MM-DD
        end_date: End date YYYY-MM-DD

    Returns:
        Dictionary with backtest results
    """
    db = MarketDataDB()

    # Initialize trend detector
    detector = TrendDetector(
        db=db,
        min_confidence=0.6,
        block_high_impact_events=True,
        min_adx=0,
        confirmation_days=1,
        long_only=True,  # Only long positions, exit on death cross
    )

    # Get all price data for the period
    query = """
        SELECT DATE(timestamp) as date, close
        FROM stock_prices
        WHERE symbol = ?
        AND DATE(timestamp) >= DATE(?)
        AND DATE(timestamp) <= DATE(?)
        ORDER BY timestamp
    """
    results = db.conn.execute(query, [ticker, start_date, end_date]).fetchall()

    if not results:
        print(f"ERROR: No data for {ticker}")
        return {}

    # Simulation variables
    position = None  # Current position: {'entry_price': float, 'entry_date': str, 'signal': SignalData}
    trades = []  # Completed trades
    cash = 10000.0  # Starting capital
    shares = 0

    print(f"\n{'='*70}")
    print(f"BACKTESTING: {ticker}")
    print(f"{'='*70}")
    print(f"Period: {start_date} to {end_date}")
    print(f"Starting capital: ${cash:,.2f}\n")

    # Iterate through each day
    for date, price in results:
        price = float(price)
        signal_data = detector.generate_signal(ticker, date, price)

        # Entry logic
        if signal_data.signal == TradingSignal.BUY and position is None:
            # Buy with all cash
            shares = cash / price
            position = {
                "entry_price": price,
                "entry_date": date,
                "signal": signal_data,
                "shares": shares,
            }
            cash = 0
            print(f"[BUY] {date} @ ${price:.2f}")
            print(f"  Reason: {signal_data.reasoning}")
            print(f"  Shares: {shares:.2f}\n")

        # Exit logic
        elif signal_data.signal == TradingSignal.SELL and position is not None:
            # Sell all shares
            cash = shares * price
            entry_price = position["entry_price"]
            entry_date = position["entry_date"]
            pnl = cash - (shares * entry_price)
            pnl_pct = (price / entry_price - 1) * 100

            # Calculate holding days
            entry_dt = datetime.strptime(str(entry_date), "%Y-%m-%d")
            exit_dt = datetime.strptime(str(date), "%Y-%m-%d")
            holding_days = (exit_dt - entry_dt).days

            trades.append(
                {
                    "entry_date": entry_date,
                    "entry_price": entry_price,
                    "exit_date": date,
                    "exit_price": price,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "holding_days": holding_days,
                }
            )

            print(f"[SELL] {date} @ ${price:.2f}")
            print(f"  Reason: {signal_data.reasoning}")
            print(f"  Entry: {entry_date} @ ${entry_price:.2f}")
            print(f"  Holding: {holding_days} days")
            print(f"  P&L: ${pnl:,.2f} ({pnl_pct:+.2f}%)\n")

            position = None
            shares = 0

    # Close any open position at end
    if position is not None:
        final_price = float(results[-1][1])
        final_date = results[-1][0]
        cash = shares * final_price
        entry_price = position["entry_price"]
        entry_date = position["entry_date"]
        pnl = cash - (shares * entry_price)
        pnl_pct = (final_price / entry_price - 1) * 100

        entry_dt = datetime.strptime(str(entry_date), "%Y-%m-%d")
        exit_dt = datetime.strptime(str(final_date), "%Y-%m-%d")
        holding_days = (exit_dt - entry_dt).days

        trades.append(
            {
                "entry_date": entry_date,
                "entry_price": entry_price,
                "exit_date": final_date,
                "exit_price": final_price,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "holding_days": holding_days,
            }
        )

        print(f"[CLOSE] {final_date} @ ${final_price:.2f} (end of period)")
        print(f"  Entry: {entry_date} @ ${entry_price:.2f}")
        print(f"  Holding: {holding_days} days")
        print(f"  P&L: ${pnl:,.2f} ({pnl_pct:+.2f}%)\n")

        shares = 0

    # Calculate results
    final_value = cash
    total_return = final_value - 10000.0
    total_return_pct = (final_value / 10000.0 - 1) * 100

    # Buy & hold comparison
    first_price = float(results[0][1])
    last_price = float(results[-1][1])
    bh_return_pct = (last_price / first_price - 1) * 100

    # Trade statistics
    winning_trades = [t for t in trades if t["pnl"] > 0]
    losing_trades = [t for t in trades if t["pnl"] <= 0]
    win_rate = len(winning_trades) / len(trades) * 100 if trades else 0

    total_wins = sum(t["pnl"] for t in winning_trades) if winning_trades else 0
    total_losses = abs(sum(t["pnl"] for t in losing_trades)) if losing_trades else 0
    profit_factor = total_wins / total_losses if total_losses > 0 else float("inf")

    avg_holding_days = sum(t["holding_days"] for t in trades) / len(trades) if trades else 0

    # Print results
    print(f"{'='*70}")
    print("RESULTS")
    print(f"{'='*70}\n")

    print(f"Final Value:      ${final_value:,.2f}")
    print(f"Total Return:     ${total_return:,.2f} ({total_return_pct:+.2f}%)")
    print(f"Buy & Hold:       {bh_return_pct:+.2f}%")
    print(f"Outperformance:   {total_return_pct - bh_return_pct:+.2f}%\n")

    print(f"Total Trades:     {len(trades)}")
    print(f"Winning Trades:   {len(winning_trades)} ({win_rate:.1f}%)")
    print(f"Losing Trades:    {len(losing_trades)}")
    print(f"Profit Factor:    {profit_factor:.2f}")
    print(f"Avg Hold:         {avg_holding_days:.0f} days\n")

    return {
        "ticker": ticker,
        "final_value": final_value,
        "total_return_pct": total_return_pct,
        "bh_return_pct": bh_return_pct,
        "num_trades": len(trades),
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "avg_holding_days": avg_holding_days,
        "trades": trades,
    }


def main():
    """Main entry point."""
    tickers = STOCK_SYMBOLS  # AAPL, NVDA

    # Test period: Last 2 years (2023-2025)
    start_date = "2023-01-01"
    end_date = "2025-09-30"

    print(f"\n{'='*70}")
    print("STOCK TREND STRATEGY BACKTEST")
    print(f"{'='*70}")
    print(f"Tickers: {', '.join(tickers)}")
    print(f"Period: {start_date} to {end_date}")
    print(f"Strategy: Long-only, exit on death cross")
    print(f"Confidence: 60%, Confirmation: 1 day")
    print(f"{'='*70}\n")

    results = []

    for ticker in tickers:
        result = backtest_stock(ticker, start_date, end_date)
        if result:
            results.append(result)

    # Summary comparison
    if results:
        print(f"\n{'='*70}")
        print("COMPARISON SUMMARY")
        print(f"{'='*70}\n")

        print(f"{'Ticker':<10} | {'Return':<12} | {'B&H':<12} | {'Trades':<8} | {'Win Rate':<10}")
        print(f"{'-'*10}-+-{'-'*12}-+-{'-'*12}-+-{'-'*8}-+-{'-'*10}")

        for r in results:
            return_str = f"+{r['total_return_pct']:.2f}%"
            bh_str = f"+{r['bh_return_pct']:.2f}%"
            wr_str = f"{r['win_rate']:.1f}%"
            print(
                f"{r['ticker']:<10} | {return_str:<12} | {bh_str:<12} | "
                f"{r['num_trades']:<8} | {wr_str:<10}"
            )

        print(f"\n{'='*70}\n")


if __name__ == "__main__":
    main()
