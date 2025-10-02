"""
Test trading strategy using ONLY technical indicators (no ML).

This tests your actual tickers (ETFs like SPY, QQQ, GLD, TLT, etc.)
without requiring ML model training. Good for quick validation.

Uses only:
- Support reclaim
- Breakout detection
- Oversold bounce (RSI + MACD)
- Momentum (indicators + options flow if available)
"""

import argparse
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.backtest.engine import BacktestConfig, BacktestEngine
from src.config.tickers import TICKER_SYMBOLS, TICKER_METADATA_MAP
from src.data.storage.market_data_db import MarketDataDB
from src.models.trading_strategy import TradingStrategy


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Test strategy with indicators only (no ML)"
    )

    parser.add_argument("--start-date", type=str, help="Backtest start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, help="Backtest end date (YYYY-MM-DD)")

    parser.add_argument(
        "--capital", type=float, default=100000, help="Starting capital (default: 100000)"
    )
    parser.add_argument(
        "--stop-loss", type=float, default=0.08, help="Stop loss %% (default: 0.08 = 8%%)"
    )
    parser.add_argument(
        "--take-profit", type=float, default=0.15, help="Take profit %% (default: 0.15 = 15%%)"
    )
    parser.add_argument(
        "--max-holding-days", type=int, default=60, help="Max holding days (default: 60)"
    )

    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.50,
        help="Min confidence to trade (default: 0.50, no ML so lower)",
    )

    parser.add_argument(
        "--tickers",
        type=str,
        help="Comma-separated tickers (default: all 34 ETFs)",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Output reasoning log",
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Determine date range
    if args.end_date:
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d")
    else:
        end_date = datetime.now()

    if args.start_date:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
    else:
        # Default: 1 year backtest
        start_date = end_date - timedelta(days=365)

    # Determine tickers
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",")]
    else:
        tickers = TICKER_SYMBOLS  # All 34 ETFs

    print(f"\n{'=' * 80}")
    print("INDICATOR-ONLY STRATEGY TEST")
    print(f"{'=' * 80}")
    print(f"\nYour Tickers: {len(tickers)} ETFs")
    print(f"  Market: SPY, QQQ, DIA, IWM")
    print(f"  Sectors: XLF, XLE, XLK, XLV, XLI, XLP, XLY, XLU, XLB, XLRE, XLC")
    print(f"  Safe Haven: GLD, TLT, TIP")
    print(f"  Volatility: VIX, UVXY, SVXY")
    print(f"  Other: HYG, LQD, BITO, COIN, UUP, USO, EFA, EEM, etc.")
    print(f"\nPeriod: {start_date.date()} to {end_date.date()}")
    print(f"Strategy: Technical indicators ONLY (no ML model)")
    print(f"  - Support reclaim")
    print(f"  - Breakout detection")
    print(f"  - Oversold bounce (RSI < 30 + MACD)")
    print(f"  - Momentum (options flow + MACD + RSI)")
    print(f"\nMin Confidence: {args.min_confidence:.1%}")
    print(f"{'=' * 80}\n")

    # Check which tickers have data
    with MarketDataDB() as db:
        print("Checking data availability...")

        available_tickers = []
        for ticker in tickers:
            query = """
                SELECT COUNT(*) as count
                FROM stock_prices
                WHERE symbol = ?
                  AND DATE(timestamp) >= DATE(?)
                  AND DATE(timestamp) <= DATE(?)
            """
            result = db.conn.execute(query, [ticker, start_date, end_date]).fetchone()

            if result and result[0] > 0:
                available_tickers.append(ticker)
                metadata = TICKER_METADATA_MAP.get(ticker)
                category = metadata.category if metadata else "unknown"
                print(f"  [OK] {ticker:6s} ({result[0]:>4} days) - {category}")
            else:
                print(f"  [NO DATA] {ticker:6s}")

        if not available_tickers:
            print("\n[ERROR] No tickers have data in this date range!")
            print("\nRun this first:")
            print("  .\\tasks.ps1 fetch-historical")
            print("  .\\tasks.ps1 calc-indicators")
            print("  .\\tasks.ps1 fetch-options-flow")
            print("  .\\tasks.ps1 calc-options-metrics")
            return

        print(f"\n[OK] {len(available_tickers)}/{len(tickers)} tickers have data\n")

        # Setup strategy config
        config = BacktestConfig(
            starting_capital=Decimal(str(args.capital)),
            stop_loss_pct=args.stop_loss,
            take_profit_pct=args.take_profit,
            max_holding_days=args.max_holding_days,
            min_ml_confidence=args.min_confidence,
        )

        strategy = TradingStrategy(
            db=db,
            stop_loss_pct=args.stop_loss,
            take_profit_pct=args.take_profit,
            max_holding_days=args.max_holding_days,
        )

        # Create backtest engine (no ML trainer = indicators only)
        engine = BacktestEngine(
            db=db, config=config, strategy=strategy, ml_trainer=None  # No ML!
        )

        # Open log file if verbose
        log_file = None
        if args.verbose:
            log_file = open("indicator_strategy_test.log", "w", encoding="utf-8")
            log_file.write(f"INDICATOR-ONLY STRATEGY TEST LOG\n")
            log_file.write(f"{'=' * 80}\n")
            log_file.write(f"Date: {datetime.now()}\n")
            log_file.write(f"Period: {start_date.date()} to {end_date.date()}\n")
            log_file.write(f"Tickers: {', '.join(available_tickers)}\n")
            log_file.write(f"Strategy: Indicators only (no ML)\n")
            log_file.write(f"{'=' * 80}\n\n")

        # Get trading days
        trading_days_query = """
            SELECT DISTINCT DATE(timestamp) as date
            FROM stock_prices
            WHERE DATE(timestamp) >= DATE(?)
              AND DATE(timestamp) <= DATE(?)
            ORDER BY date
        """

        from datetime import date as date_type
        trading_days = [
            datetime.combine(row[0], datetime.min.time()) if isinstance(row[0], date_type) else datetime.fromisoformat(str(row[0]))
            for row in db.conn.execute(trading_days_query, [start_date, end_date]).fetchall()
        ]

        print(f"{'=' * 80}")
        print("RUNNING BACKTEST")
        print(f"{'=' * 80}\n")

        signals_generated = 0
        signals_rejected = 0

        # Simulate trading day by day
        for day_idx, date in enumerate(trading_days):
            if day_idx % 20 == 0:
                portfolio_value = engine.get_portfolio_value(date)
                print(
                    f"Progress: {day_idx}/{len(trading_days)} | "
                    f"Date: {date.date()} | "
                    f"Portfolio: ${portfolio_value:,.2f} | "
                    f"Positions: {len(engine.positions)} | "
                    f"Trades: {len(engine.trades)}"
                )

            if log_file:
                log_file.write(f"\n{'=' * 80}\n")
                log_file.write(f"DATE: {date.date()}\n")
                log_file.write(f"{'=' * 80}\n\n")

            # Check existing positions for exits
            for ticker in list(engine.positions.keys()):
                current_price = engine.get_current_price(ticker, date)
                if not current_price:
                    continue

                position = engine.positions[ticker]

                # NO ML confidence (indicators only)
                sell_signal = strategy.generate_sell_signal(
                    position, ticker, date, current_price, ml_confidence=None
                )

                if sell_signal:
                    if log_file:
                        log_file.write(f"🔴 SELL SIGNAL: {ticker}\n")
                        log_file.write(f"{'-' * 80}\n")
                        log_file.write(f"{sell_signal.reasoning}\n")
                        log_file.write(f"{'=' * 80}\n\n")

                    trade = engine.close_position(
                        ticker, date, current_price, sell_signal.exit_reason
                    )
                    if trade:
                        result = "WIN" if trade.profit_loss > 0 else "LOSS"
                        print(
                            f"  {result} | {ticker} | "
                            f"${trade.entry_price:.2f} -> ${trade.exit_price:.2f} | "
                            f"P&L: ${trade.profit_loss:,.2f} ({trade.profit_pct:+.1f}%)"
                        )

            # Look for new entry signals
            for ticker in available_tickers:
                if ticker in engine.positions:
                    continue

                current_price = engine.get_current_price(ticker, date)
                if not current_price:
                    continue

                # Check for buy signal (NO ML confidence)
                buy_signal = strategy.generate_buy_signal(
                    ticker, date, current_price, ml_confidence=None, min_confidence_threshold=args.min_confidence
                )

                if buy_signal:
                    signals_generated += 1

                    if log_file:
                        log_file.write(f"🟢 BUY SIGNAL: {ticker}\n")
                        log_file.write(f"{'-' * 80}\n")
                        log_file.write(f"{buy_signal.reasoning}\n")
                        log_file.write(f"{'=' * 80}\n\n")

                    if len(engine.positions) < config.max_positions:
                        opened = engine.open_position(
                            ticker,
                            date,
                            current_price,
                            buy_signal.entry_reason,
                            buy_signal.stop_loss,
                            buy_signal.take_profit,
                        )

                        if opened:
                            metadata = TICKER_METADATA_MAP.get(ticker)
                            category = f"({metadata.category})" if metadata else ""
                            print(
                                f"  ENTRY | {ticker} {category} | ${current_price:.2f} | "
                                f"{buy_signal.entry_reason.value} | "
                                f"Conf: {buy_signal.confidence:.2f}"
                            )

        # Close remaining positions
        for ticker in list(engine.positions.keys()):
            final_price = engine.get_current_price(ticker, end_date)
            if final_price:
                from src.models.trading_strategy import ExitReason

                engine.close_position(ticker, end_date, final_price, ExitReason.TIME_EXIT)

        # Calculate results
        results = engine._calculate_results(start_date, end_date)

        # Write summary
        if log_file:
            log_file.write(f"\n{'=' * 80}\n")
            log_file.write(f"SUMMARY\n")
            log_file.write(f"{'=' * 80}\n\n")
            log_file.write(f"Total Return: ${results.total_return:,.2f} ({results.total_return_pct:.2f}%)\n")
            log_file.write(f"Win Rate: {results.win_rate:.1%}\n")
            log_file.write(f"Total Trades: {results.total_trades}\n")
            log_file.write(f"Sharpe Ratio: {results.sharpe_ratio:.2f}\n")
            log_file.write(f"Max Drawdown: {results.max_drawdown:.1%}\n")
            log_file.close()

        # Print summary
        print(f"\n{'=' * 80}")
        print(f"BACKTEST RESULTS (INDICATORS ONLY)")
        print(f"{'=' * 80}\n")

        print(f"CAPITAL")
        print(f"-" * 50)
        print(f"Starting: ${results.starting_capital:,.2f}")
        print(f"Ending:   ${results.ending_capital:,.2f}")
        print(f"Return:   ${results.total_return:,.2f} ({results.total_return_pct:+.2f}%)")

        print(f"\nTRADES")
        print(f"-" * 50)
        print(f"Total:    {results.total_trades}")
        print(f"Winners:  {results.winning_trades}")
        print(f"Losers:   {results.losing_trades}")
        print(f"Win Rate: {results.win_rate:.1%}")

        print(f"\nRISK METRICS")
        print(f"-" * 50)
        print(f"Sharpe Ratio:  {results.sharpe_ratio:.2f}")
        print(f"Max Drawdown:  {results.max_drawdown:.1%}")
        print(f"Profit Factor: {results.profit_factor:.2f}")

        print(f"\nTRADE ANALYSIS")
        print(f"-" * 50)
        from collections import Counter

        entry_reasons = Counter(t.entry_reason for t in results.trades)
        for reason, count in entry_reasons.most_common():
            reason_trades = [t for t in results.trades if t.entry_reason == reason]
            reason_winners = [t for t in reason_trades if t.profit_loss > 0]
            reason_win_rate = len(reason_winners) / len(reason_trades)
            reason_pnl = sum(t.profit_loss for t in reason_trades)

            print(
                f"{reason.value:25s} {count:>3} trades | "
                f"Win: {reason_win_rate:>5.1%} | "
                f"P&L: ${reason_pnl:>10,.2f}"
            )

        if args.verbose:
            print(f"\n[LOG] Detailed reasoning saved to: indicator_strategy_test.log")

        print(f"\n{'=' * 80}\n")


if __name__ == "__main__":
    main()
