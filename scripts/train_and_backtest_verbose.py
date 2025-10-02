"""
Train CatBoost model and run backtest with VERBOSE reasoning logs.

This version outputs detailed reasoning for every trade decision to a log file,
including why trades were taken, why they were skipped (cash-on-sidelines),
and exit reasoning.
"""

import argparse
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.backtest.engine import BacktestConfig, BacktestEngine
from src.config.tickers import TICKER_SYMBOLS
from src.data.storage.market_data_db import MarketDataDB
from src.ml.catboost_model import CatBoostTrainer
from src.models.trading_strategy import TradingStrategy


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Train CatBoost and run backtest with reasoning logs"
    )

    parser.add_argument("--train-start", type=str, help="Training start date (YYYY-MM-DD)")
    parser.add_argument("--train-end", type=str, help="Training end date (YYYY-MM-DD)")
    parser.add_argument("--test-start", type=str, help="Backtest start date (YYYY-MM-DD)")
    parser.add_argument("--test-end", type=str, help="Backtest end date (YYYY-MM-DD)")

    parser.add_argument(
        "--prediction-days", type=int, default=5, help="Days ahead to predict (default: 5)"
    )

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
        default=0.6,
        help="Min ML confidence to trade (default: 0.6)",
    )

    parser.add_argument("--skip-training", action="store_true", help="Skip training, load models")

    parser.add_argument(
        "--tickers",
        type=str,
        help="Comma-separated tickers to trade (default: all tickers)",
    )

    parser.add_argument(
        "--log-file",
        type=str,
        default="trade_reasoning.log",
        help="Output log file (default: trade_reasoning.log)",
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Determine date ranges
    if args.test_end:
        test_end = datetime.strptime(args.test_end, "%Y-%m-%d")
    else:
        test_end = datetime.now()

    if args.test_start:
        test_start = datetime.strptime(args.test_start, "%Y-%m-%d")
    else:
        test_start = test_end - timedelta(days=730)

    if args.train_end:
        train_end = datetime.strptime(args.train_end, "%Y-%m-%d")
    else:
        train_end = test_start - timedelta(days=1)

    if args.train_start:
        train_start = datetime.strptime(args.train_start, "%Y-%m-%d")
    else:
        train_start = train_end - timedelta(days=1095)

    # Determine tickers
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",")]
    else:
        tickers = TICKER_SYMBOLS

    print(f"\n{'=' * 80}")
    print("CATBOOST TRAINING & BACKTESTING (VERBOSE MODE)")
    print(f"{'=' * 80}")
    print(f"\nLogging reasoning to: {args.log_file}")
    print(f"\nMin Confidence Threshold: {args.min_confidence:.1%}")
    print("  Signals below this threshold will be REJECTED (cash-on-sidelines)")
    print(f"{'=' * 80}\n")

    # Open log file
    log_file = open(args.log_file, "w", encoding="utf-8")
    log_file.write(f"TRADE REASONING LOG\n")
    log_file.write(f"{'=' * 80}\n")
    log_file.write(f"Generated: {datetime.now()}\n")
    log_file.write(f"Backtest Period: {test_start.date()} to {test_end.date()}\n")
    log_file.write(f"Min Confidence Threshold: {args.min_confidence:.1%}\n")
    log_file.write(f"Tickers: {', '.join(tickers)}\n")
    log_file.write(f"{'=' * 80}\n\n")

    with MarketDataDB() as db:
        # Initialize trainer
        trainer = CatBoostTrainer(
            db=db,
            prediction_days=args.prediction_days,
            profit_threshold=0.02,
        )

        if not args.skip_training:
            print("Training CatBoost models...")
            X, full_df = trainer.prepare_training_data(tickers, train_start, train_end)
            trainer.train_direction_model(X, full_df["target_direction"])
            trainer.train_return_model(X, full_df["target_return"])
            trainer.save_models()
        else:
            print("Loading pre-trained models...")
            trainer.load_models()

        # Run backtest with verbose logging
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

        engine = BacktestEngine(db=db, config=config, strategy=strategy, ml_trainer=trainer)

        # Get trading days
        trading_days_query = """
            SELECT DISTINCT DATE(timestamp) as date
            FROM stock_prices
            WHERE DATE(timestamp) >= DATE(?)
              AND DATE(timestamp) <= DATE(?)
            ORDER BY date
        """

        trading_days = [
            datetime.fromisoformat(row[0])
            for row in db.conn.execute(trading_days_query, [test_start, test_end]).fetchall()
        ]

        print(f"\n{'=' * 80}")
        print("RUNNING BACKTEST WITH VERBOSE LOGGING")
        print(f"{'=' * 80}\n")

        signals_generated = 0
        signals_rejected = 0
        trades_opened = 0
        trades_closed = 0
        cash_on_sidelines_days = 0

        # Simulate trading day by day
        for day_idx, date in enumerate(trading_days):
            if day_idx % 50 == 0:
                print(f"Progress: {day_idx}/{len(trading_days)} days ({day_idx/len(trading_days)*100:.1f}%)")

            log_file.write(f"\n{'=' * 80}\n")
            log_file.write(f"DATE: {date.date()}\n")
            log_file.write(f"{'=' * 80}\n\n")

            # Track equity
            portfolio_value = engine.get_portfolio_value(date)
            cash_pct = float(engine.cash / portfolio_value * 100) if portfolio_value > 0 else 100

            log_file.write(f"Portfolio Value: ${portfolio_value:,.2f}\n")
            log_file.write(f"Cash: ${engine.cash:,.2f} ({cash_pct:.1f}%)\n")
            log_file.write(f"Open Positions: {len(engine.positions)}\n\n")

            # Check existing positions for exits
            for ticker, position in list(engine.positions.items()):
                current_price = engine.get_current_price(ticker, date)
                if not current_price:
                    continue

                # Get ML prediction
                ml_prediction = engine.get_ml_prediction(ticker, date)
                ml_confidence = ml_prediction[1] if ml_prediction else None

                # Check for sell signal
                sell_signal = strategy.generate_sell_signal(
                    position, ticker, date, current_price, ml_confidence
                )

                if sell_signal:
                    # Log sell reasoning
                    log_file.write(f"🔴 SELL SIGNAL: {ticker}\n")
                    log_file.write(f"{'-' * 80}\n")
                    log_file.write(f"{sell_signal.reasoning}\n")
                    log_file.write(f"{'=' * 80}\n\n")

                    trade = engine.close_position(
                        ticker, date, current_price, sell_signal.exit_reason
                    )
                    if trade:
                        trades_closed += 1
                        result = "WIN" if trade.profit_loss > 0 else "LOSS"
                        print(
                            f"  {result} | {ticker} | ${trade.entry_price:.2f} -> ${trade.exit_price:.2f} | "
                            f"P&L: ${trade.profit_loss:,.2f} ({trade.profit_pct:+.1f}%)"
                        )

            # Look for new entry signals
            day_had_opportunity = False

            for ticker in tickers:
                if ticker in engine.positions:
                    continue

                current_price = engine.get_current_price(ticker, date)
                if not current_price:
                    continue

                day_had_opportunity = True

                # Get ML prediction
                ml_prediction = engine.get_ml_prediction(ticker, date)
                if ml_prediction:
                    direction, confidence, expected_return = ml_prediction
                else:
                    confidence = None

                # Check for buy signal
                buy_signal = strategy.generate_buy_signal(
                    ticker, date, current_price, confidence, args.min_confidence
                )

                if buy_signal:
                    signals_generated += 1

                    # Log buy reasoning
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
                            trades_opened += 1
                            print(
                                f"  ENTRY | {ticker} | ${current_price:.2f} | "
                                f"Conf: {buy_signal.confidence:.2f}"
                            )
                        else:
                            log_file.write(
                                f"⚠️  Could not open position (insufficient capital)\n\n"
                            )
                    else:
                        log_file.write(
                            f"⚠️  Max positions reached ({config.max_positions}), "
                            f"skipping this signal\n\n"
                        )

                elif confidence is not None and confidence < args.min_confidence:
                    # Signal was rejected due to low confidence
                    signals_rejected += 1

                    log_file.write(f"💰 CASH ON SIDELINES: {ticker}\n")
                    log_file.write(f"{'-' * 80}\n")
                    log_file.write(
                        f"Signal confidence {confidence:.1%} < threshold {args.min_confidence:.1%}\n"
                    )
                    log_file.write(f"DECISION: Not trading - preserving capital\n")
                    log_file.write(f"{'=' * 80}\n\n")

            # Track cash-on-sidelines days
            if day_had_opportunity and len(engine.positions) == 0:
                cash_on_sidelines_days += 1
                log_file.write(f"📊 100% CASH TODAY (no positions opened)\n\n")

        # Close any remaining positions
        for ticker in list(engine.positions.keys()):
            final_price = engine.get_current_price(ticker, test_end)
            if final_price:
                from src.models.trading_strategy import ExitReason

                log_file.write(f"\n🔴 FINAL EXIT: {ticker}\n")
                log_file.write(f"{'-' * 80}\n")
                log_file.write(f"Backtest ended, closing position at ${final_price:.2f}\n")
                log_file.write(f"{'=' * 80}\n\n")

                engine.close_position(ticker, test_end, final_price, ExitReason.TIME_EXIT)

        # Calculate results
        results = engine._calculate_results(test_start, test_end)

        # Write summary to log
        log_file.write(f"\n{'=' * 80}\n")
        log_file.write(f"BACKTEST SUMMARY\n")
        log_file.write(f"{'=' * 80}\n\n")
        log_file.write(f"Total Trading Days: {len(trading_days)}\n")
        log_file.write(f"Signals Generated: {signals_generated}\n")
        log_file.write(f"Signals Rejected (Low Confidence): {signals_rejected}\n")
        log_file.write(
            f"Rejection Rate: {signals_rejected / (signals_generated + signals_rejected) * 100:.1f}%\n\n"
        )
        log_file.write(f"Trades Opened: {trades_opened}\n")
        log_file.write(f"Trades Closed: {trades_closed}\n")
        log_file.write(f"Cash-on-Sidelines Days: {cash_on_sidelines_days}\n")
        log_file.write(f"Cash-on-Sidelines %: {cash_on_sidelines_days / len(trading_days) * 100:.1f}%\n\n")

        log_file.write(f"Total Return: ${results.total_return:,.2f} ({results.total_return_pct:.2f}%)\n")
        log_file.write(f"Win Rate: {results.win_rate:.1%}\n")
        log_file.write(f"Sharpe Ratio: {results.sharpe_ratio:.2f}\n")
        log_file.write(f"Max Drawdown: {results.max_drawdown:.1%}\n")

        log_file.close()

        # Print summary to console
        print(f"\n{'=' * 80}")
        print(f"VERBOSE BACKTEST COMPLETE")
        print(f"{'=' * 80}")
        print(f"\nTotal Return: ${results.total_return:,.2f} ({results.total_return_pct:.2f}%)")
        print(f"Win Rate: {results.win_rate:.1%}")
        print(f"Total Trades: {results.total_trades}")
        print(f"\nSignal Statistics:")
        print(f"  Signals Generated: {signals_generated}")
        print(f"  Signals Rejected: {signals_rejected}")
        print(
            f"  Rejection Rate: {signals_rejected / (signals_generated + signals_rejected) * 100:.1f}%"
        )
        print(f"\nCash Management:")
        print(f"  Days with 100% Cash: {cash_on_sidelines_days}")
        print(f"  Cash-on-Sidelines %: {cash_on_sidelines_days / len(trading_days) * 100:.1f}%")
        print(f"\nDetailed reasoning saved to: {args.log_file}")
        print(f"{'=' * 80}\n")


if __name__ == "__main__":
    main()
