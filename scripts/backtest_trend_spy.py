"""
Backtest trend-change strategy on SPY only.

Tests the simplified approach:
- Detect trend changes (BULLISH/BEARISH/NEUTRAL)
- BUY when trend flips to bullish
- SELL when trend flips to bearish
- DON'T TRADE when neutral or high-impact event
- Block trading on economic event days
"""

import argparse
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.data.storage.market_data_db import MarketDataDB
from src.models.trend_detector import TradingSignal, TrendDetector


def main():
    parser = argparse.ArgumentParser(description="Backtest trend-change strategy on SPY")
    parser.add_argument(
        "--start-date",
        type=str,
        default="2020-01-01",
        help="Backtest start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Backtest end date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=100000,
        help="Starting capital (default: 100000)",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.7,
        help="Min confidence to trade (default: 0.7 = 70%%)",
    )
    parser.add_argument(
        "--min-adx",
        type=float,
        default=25.0,
        help="Min ADX for trend strength (default: 25)",
    )
    parser.add_argument(
        "--confirmation-days",
        type=int,
        default=2,
        help="Days to confirm trend before trading (default: 2)",
    )
    parser.add_argument(
        "--block-events",
        action="store_true",
        default=True,
        help="Block trading on high-impact event days (default: True)",
    )
    parser.add_argument(
        "--long-only",
        action="store_true",
        default=True,
        help="Long-only: only exit on death cross, ignore short-term bearish (default: True)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Output detailed reasoning log",
    )

    args = parser.parse_args()

    start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d")

    print("=" * 80)
    print("TREND-CHANGE BACKTEST: SPY ONLY (IMPROVED)")
    print("=" * 80)
    print(f"\nTicker: SPY (S&P 500 ETF)")
    print(f"Period: {args.start_date} to {args.end_date}")
    print(f"Starting Capital: ${args.capital:,.2f}")
    print(f"Min Confidence: {args.min_confidence:.0%}")
    print(f"Min ADX (Trend Strength): {args.min_adx}")
    print(f"Confirmation Days: {args.confirmation_days}")
    print(f"Block High-Impact Events: {args.block_events}")
    print("\nStrategy:")
    print("  BUY: Trend changes to BULLISH (confirmed + strong)")
    print("  SELL: Trend changes to BEARISH (confirmed + strong)")
    print("  DON'T TRADE: Weak trend, unconfirmed, or high-impact event")
    print("\n" + "=" * 80 + "\n")

    # Connect to database
    db = MarketDataDB()

    # Check data availability
    query = """
    SELECT COUNT(*)
    FROM stock_prices
    WHERE symbol = 'SPY'
      AND DATE(timestamp) >= DATE(?)
      AND DATE(timestamp) <= DATE(?)
    """
    result = db.conn.execute(query, [start_date, end_date]).fetchone()
    days_available = result[0] if result else 0

    if days_available == 0:
        print("[ERROR] No SPY data available for this date range!")
        print("\nRun this first:")
        print("  .\\tasks.ps1 fetch-historical")
        print("  .\\tasks.ps1 calc-indicators")
        return

    print(f"Data Check: {days_available} trading days available\n")

    # Initialize trend detector
    detector = TrendDetector(
        db=db,
        min_confidence=args.min_confidence,
        block_high_impact_events=args.block_events,
        min_adx=args.min_adx,
        confirmation_days=args.confirmation_days,
        long_only=args.long_only,
    )

    # Get trading days
    trading_days_query = """
    SELECT DISTINCT DATE(timestamp) as date
    FROM stock_prices
    WHERE symbol = 'SPY'
      AND DATE(timestamp) >= DATE(?)
      AND DATE(timestamp) <= DATE(?)
    ORDER BY date
    """

    from datetime import date as date_type
    trading_days = [
        datetime.combine(row[0], datetime.min.time())
        if isinstance(row[0], date_type)
        else datetime.fromisoformat(str(row[0]))
        for row in db.conn.execute(trading_days_query, [start_date, end_date]).fetchall()
    ]

    print("=" * 80)
    print("RUNNING BACKTEST")
    print("=" * 80 + "\n")

    # Open log file if verbose
    log_file = None
    if args.verbose:
        log_file = open("trend_backtest_spy.log", "w", encoding="utf-8")
        log_file.write("=" * 80 + "\n")
        log_file.write("TREND-CHANGE BACKTEST LOG: SPY\n")
        log_file.write("=" * 80 + "\n\n")

    # Backtest state
    capital = Decimal(str(args.capital))
    position_shares = Decimal("0")
    position_entry_price = None
    position_entry_date = None

    trades = []
    signals_generated = 0
    signals_blocked = 0

    for i, date in enumerate(trading_days):
        # Get current price
        price_query = """
        SELECT close
        FROM stock_prices
        WHERE symbol = 'SPY' AND DATE(timestamp) = DATE(?)
        """
        price_result = db.conn.execute(price_query, [date]).fetchone()

        if not price_result:
            continue

        current_price = Decimal(str(price_result[0]))

        # Generate signal
        signal = detector.generate_signal("SPY", date, current_price)

        if not signal:
            continue

        # Log signal
        if log_file:
            log_file.write(f"\n{'=' * 80}\n")
            log_file.write(f"Date: {date.strftime('%Y-%m-%d')}\n")
            log_file.write(f"Price: ${current_price:.2f}\n")
            log_file.write(f"Signal: {signal.signal.value}\n")
            log_file.write(f"Trend: {signal.trend.value}\n")
            log_file.write(f"Confidence: {signal.confidence:.1%}\n")
            log_file.write(f"\n{signal.reasoning}\n")

        # Process signal
        if signal.signal == TradingSignal.BUY and position_shares == 0:
            # Open long position
            position_shares = capital / current_price
            position_entry_price = current_price
            position_entry_date = date
            signals_generated += 1

            if log_file:
                log_file.write(f"\n[ACTION] BUY {position_shares:.2f} shares @ ${current_price:.2f}\n")
                log_file.write(f"Position Value: ${capital:.2f}\n")

            print(
                f"[BUY] {date.strftime('%Y-%m-%d')} | ${current_price:.2f} | "
                f"Shares: {position_shares:.2f} | Conf: {signal.confidence:.1%}"
            )

        elif signal.signal == TradingSignal.SELL and position_shares > 0:
            # Close position
            exit_value = position_shares * current_price
            pnl = exit_value - capital
            pnl_pct = (current_price / position_entry_price - 1) * 100

            trades.append({
                "entry_date": position_entry_date,
                "exit_date": date,
                "entry_price": position_entry_price,
                "exit_price": current_price,
                "shares": position_shares,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "days_held": (date - position_entry_date).days,
            })

            capital = exit_value
            signals_generated += 1

            if log_file:
                log_file.write(
                    f"\n[ACTION] SELL {position_shares:.2f} shares @ ${current_price:.2f}\n"
                )
                log_file.write(f"Entry: ${position_entry_price:.2f} on {position_entry_date.strftime('%Y-%m-%d')}\n")
                log_file.write(f"Exit: ${current_price:.2f} on {date.strftime('%Y-%m-%d')}\n")
                log_file.write(f"P&L: ${pnl:,.2f} ({pnl_pct:+.2f}%)\n")
                log_file.write(f"New Capital: ${capital:,.2f}\n")

            win_loss = "WIN" if pnl > 0 else "LOSS"
            print(
                f"[{win_loss}] {date.strftime('%Y-%m-%d')} | "
                f"${position_entry_price:.2f} -> ${current_price:.2f} | "
                f"P&L: ${pnl:,.2f} ({pnl_pct:+.2f}%) | "
                f"{(date - position_entry_date).days} days"
            )

            position_shares = Decimal("0")
            position_entry_price = None
            position_entry_date = None

        elif signal.signal == TradingSignal.DONT_TRADE:
            if signal.blocked_by_event:
                signals_blocked += 1

                if log_file:
                    log_file.write("\n[ACTION] NO TRADE (blocked by event)\n")

        # Progress update
        if (i + 1) % 50 == 0:
            current_value = capital if position_shares == 0 else position_shares * current_price
            print(
                f"Progress: {i+1}/{len(trading_days)} | "
                f"Date: {date.strftime('%Y-%m-%d')} | "
                f"Value: ${current_value:,.2f} | "
                f"Trades: {len(trades)}"
            )

    # Close any open position at end
    if position_shares > 0:
        final_price_query = """
        SELECT close
        FROM stock_prices
        WHERE symbol = 'SPY' AND DATE(timestamp) = DATE(?)
        """
        final_price_result = db.conn.execute(final_price_query, [trading_days[-1]]).fetchone()
        final_price = Decimal(str(final_price_result[0])) if final_price_result else current_price

        exit_value = position_shares * final_price
        pnl = exit_value - capital
        pnl_pct = (final_price / position_entry_price - 1) * 100

        trades.append({
            "entry_date": position_entry_date,
            "exit_date": trading_days[-1],
            "entry_price": position_entry_price,
            "exit_price": final_price,
            "shares": position_shares,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "days_held": (trading_days[-1] - position_entry_date).days,
        })

        capital = exit_value

        print(f"\n[CLOSE] Final position closed @ ${final_price:.2f}")
        print(f"P&L: ${pnl:,.2f} ({pnl_pct:+.2f}%)")

    # Calculate results
    starting_capital = Decimal(str(args.capital))
    ending_capital = capital
    total_return = ending_capital - starting_capital
    total_return_pct = (ending_capital / starting_capital - 1) * 100

    winners = [t for t in trades if t["pnl"] > 0]
    losers = [t for t in trades if t["pnl"] <= 0]
    win_rate = len(winners) / len(trades) * 100 if trades else 0

    avg_win = sum(t["pnl"] for t in winners) / len(winners) if winners else 0
    avg_loss = sum(t["pnl"] for t in losers) / len(losers) if losers else 0
    profit_factor = (
        abs(sum(t["pnl"] for t in winners) / sum(t["pnl"] for t in losers))
        if losers and sum(t["pnl"] for t in losers) != 0
        else 0
    )

    avg_holding_days = sum(t["days_held"] for t in trades) / len(trades) if trades else 0

    # Calculate max drawdown
    equity_curve = [starting_capital]
    running_capital = starting_capital
    for trade in trades:
        running_capital += trade["pnl"]
        equity_curve.append(running_capital)

    peak = starting_capital
    max_drawdown = Decimal("0")
    for equity in equity_curve:
        if equity > peak:
            peak = equity
        drawdown = (peak - equity) / peak * 100
        if drawdown > max_drawdown:
            max_drawdown = drawdown

    # Buy and hold comparison
    first_price_query = """
    SELECT close FROM stock_prices
    WHERE symbol = 'SPY' AND DATE(timestamp) = DATE(?)
    """
    first_price_result = db.conn.execute(first_price_query, [trading_days[0]]).fetchone()
    first_price = Decimal(str(first_price_result[0])) if first_price_result else Decimal("0")

    last_price_query = """
    SELECT close FROM stock_prices
    WHERE symbol = 'SPY' AND DATE(timestamp) = DATE(?)
    """
    last_price_result = db.conn.execute(last_price_query, [trading_days[-1]]).fetchone()
    last_price = Decimal(str(last_price_result[0])) if last_price_result else Decimal("0")

    buy_hold_return_pct = (
        (last_price / first_price - 1) * 100 if first_price > 0 else Decimal("0")
    )

    # Print results
    print("\n" + "=" * 80)
    print("BACKTEST RESULTS")
    print("=" * 80)

    print("\nCAPITAL")
    print("-" * 50)
    print(f"Starting: ${starting_capital:,.2f}")
    print(f"Ending:   ${ending_capital:,.2f}")
    print(f"Return:   ${total_return:,.2f} ({total_return_pct:+.2f}%)")

    print("\nBUY & HOLD COMPARISON")
    print("-" * 50)
    print(f"SPY Buy & Hold: {buy_hold_return_pct:+.2f}%")
    print(f"Strategy Alpha: {(total_return_pct - buy_hold_return_pct):+.2f}%")

    print("\nTRADES")
    print("-" * 50)
    print(f"Total:    {len(trades)}")
    print(f"Winners:  {len(winners)}")
    print(f"Losers:   {len(losers)}")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"Avg Holding: {avg_holding_days:.1f} days")

    print("\nRISK METRICS")
    print("-" * 50)
    print(f"Max Drawdown:  {max_drawdown:.2f}%")
    print(f"Profit Factor: {profit_factor:.2f}")
    print(f"Avg Win:       ${avg_win:,.2f}")
    print(f"Avg Loss:      ${avg_loss:,.2f}")

    print("\nSIGNALS")
    print("-" * 50)
    print(f"Signals Generated: {signals_generated}")
    print(f"Blocked by Events: {signals_blocked}")
    print(
        f"Event Block Rate:  {signals_blocked / (signals_generated + signals_blocked) * 100:.1f}%"
        if (signals_generated + signals_blocked) > 0 else "N/A"
    )

    if log_file:
        log_file.write("\n\n" + "=" * 80 + "\n")
        log_file.write("BACKTEST SUMMARY\n")
        log_file.write("=" * 80 + "\n")
        log_file.write(f"Total Return: ${total_return:,.2f} ({total_return_pct:+.2f}%)\n")
        log_file.write(f"Trades: {len(trades)} | Win Rate: {win_rate:.1f}%\n")
        log_file.write(f"Max Drawdown: {max_drawdown:.2f}%\n")
        log_file.close()
        print(f"\n[LOG] Detailed reasoning saved to: trend_backtest_spy.log")

    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
