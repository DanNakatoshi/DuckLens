"""
Train CatBoost model and run backtest.

This script:
1. Trains CatBoost model on historical data
2. Runs backtest to evaluate performance
3. Generates performance report with win rate, Sharpe ratio, etc.
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
    parser = argparse.ArgumentParser(description="Train CatBoost and run backtest")

    parser.add_argument("--train-start", type=str, help="Training start date (YYYY-MM-DD)")
    parser.add_argument("--train-end", type=str, help="Training end date (YYYY-MM-DD)")
    parser.add_argument("--test-start", type=str, help="Backtest start date (YYYY-MM-DD)")
    parser.add_argument("--test-end", type=str, help="Backtest end date (YYYY-MM-DD)")

    parser.add_argument(
        "--prediction-days", type=int, default=5, help="Days ahead to predict (default: 5)"
    )
    parser.add_argument(
        "--profit-threshold",
        type=float,
        default=0.02,
        help="Profit threshold for UP label (default: 0.02 = 2%%)",
    )

    parser.add_argument(
        "--capital", type=float, default=100000, help="Starting capital (default: 100000)"
    )
    parser.add_argument(
        "--position-size", type=float, default=0.1, help="Position size %% (default: 0.1 = 10%%)"
    )
    parser.add_argument(
        "--max-positions", type=int, default=5, help="Max concurrent positions (default: 5)"
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
    parser.add_argument("--model-suffix", type=str, default="", help="Model filename suffix")

    parser.add_argument(
        "--tickers",
        type=str,
        help="Comma-separated tickers to trade (default: all tickers)",
    )

    return parser.parse_args()


def print_backtest_report(results):
    """Print formatted backtest results."""
    print(f"\n{'=' * 80}")
    print("BACKTEST RESULTS")
    print(f"{'=' * 80}\n")

    print(f"Period: {results.start_date.date()} to {results.end_date.date()}")
    print(
        f"Duration: {(results.end_date - results.start_date).days} days "
        f"({(results.end_date - results.start_date).days / 365:.1f} years)"
    )

    print(f"\n{'CAPITAL':30} {'':>20}")
    print(f"{'-' * 50}")
    print(f"{'Starting Capital':30} ${results.starting_capital:>19,.2f}")
    print(f"{'Ending Capital':30} ${results.ending_capital:>19,.2f}")
    print(f"{'Total Return':30} ${results.total_return:>19,.2f}")
    print(
        f"{'Total Return %':30} {results.total_return_pct:>19.2f}%"
    )
    print(f"{'Commission Paid':30} ${results.total_commission:>19,.2f}")

    print(f"\n{'TRADE STATISTICS':30} {'':>20}")
    print(f"{'-' * 50}")
    print(f"{'Total Trades':30} {results.total_trades:>20,}")
    print(f"{'Winning Trades':30} {results.winning_trades:>20,}")
    print(f"{'Losing Trades':30} {results.losing_trades:>20,}")
    print(f"{'Win Rate':30} {results.win_rate:>19.2%}")

    print(f"\n{'PROFIT/LOSS':30} {'':>20}")
    print(f"{'-' * 50}")
    print(f"{'Average Profit (Winners)':30} ${results.avg_profit:>19,.2f}")
    print(f"{'Average Loss (Losers)':30} ${results.avg_loss:>19,.2f}")
    print(f"{'Profit Factor':30} {results.profit_factor:>20.2f}")

    print(f"\n{'RISK METRICS':30} {'':>20}")
    print(f"{'-' * 50}")
    print(f"{'Max Drawdown':30} {results.max_drawdown:>19.2%}")
    if results.max_drawdown_date:
        print(f"{'Max Drawdown Date':30} {str(results.max_drawdown_date.date()):>20}")
    print(f"{'Sharpe Ratio':30} {results.sharpe_ratio:>20.2f}")
    print(f"{'Sortino Ratio':30} {results.sortino_ratio:>20.2f}")

    print(f"\n{'HOLDING PERIOD':30} {'':>20}")
    print(f"{'-' * 50}")
    print(f"{'Average Holding Days':30} {results.avg_holding_days:>20.1f}")

    # Trade breakdown by entry reason
    print(f"\n{'ENTRY REASON BREAKDOWN':50}")
    print(f"{'-' * 80}")
    from collections import Counter

    entry_reasons = Counter(t.entry_reason for t in results.trades)
    for reason, count in entry_reasons.most_common():
        reason_trades = [t for t in results.trades if t.entry_reason == reason]
        reason_winners = [t for t in reason_trades if t.profit_loss > 0]
        reason_win_rate = len(reason_winners) / len(reason_trades) if reason_trades else 0
        reason_pnl = sum(t.profit_loss for t in reason_trades)

        print(
            f"{reason.value:30} {count:>5} trades | "
            f"Win: {reason_win_rate:>5.1%} | "
            f"P&L: ${reason_pnl:>12,.2f}"
        )

    # Exit reason breakdown
    print(f"\n{'EXIT REASON BREAKDOWN':50}")
    print(f"{'-' * 80}")
    exit_reasons = Counter(t.exit_reason for t in results.trades)
    for reason, count in exit_reasons.most_common():
        reason_trades = [t for t in results.trades if t.exit_reason == reason]
        reason_winners = [t for t in reason_trades if t.profit_loss > 0]
        reason_win_rate = len(reason_winners) / len(reason_trades) if reason_trades else 0
        reason_pnl = sum(t.profit_loss for t in reason_trades)

        print(
            f"{reason.value:30} {count:>5} trades | "
            f"Win: {reason_win_rate:>5.1%} | "
            f"P&L: ${reason_pnl:>12,.2f}"
        )

    # Top 10 best trades
    print(f"\n{'TOP 10 BEST TRADES':80}")
    print(f"{'-' * 80}")
    best_trades = sorted(results.trades, key=lambda t: t.profit_loss, reverse=True)[:10]
    print(f"{'Ticker':8} {'Entry':12} {'Exit':12} {'Days':>5} {'Entry':>10} {'Exit':>10} {'P&L':>12}")
    for trade in best_trades:
        print(
            f"{trade.ticker:8} {str(trade.entry_date.date()):12} "
            f"{str(trade.exit_date.date()):12} {trade.holding_days:>5} "
            f"${trade.entry_price:>9.2f} ${trade.exit_price:>9.2f} "
            f"${trade.profit_loss:>11,.2f}"
        )

    # Top 10 worst trades
    print(f"\n{'TOP 10 WORST TRADES':80}")
    print(f"{'-' * 80}")
    worst_trades = sorted(results.trades, key=lambda t: t.profit_loss)[:10]
    print(f"{'Ticker':8} {'Entry':12} {'Exit':12} {'Days':>5} {'Entry':>10} {'Exit':>10} {'P&L':>12}")
    for trade in worst_trades:
        print(
            f"{trade.ticker:8} {str(trade.entry_date.date()):12} "
            f"{str(trade.exit_date.date()):12} {trade.holding_days:>5} "
            f"${trade.entry_price:>9.2f} ${trade.exit_price:>9.2f} "
            f"${trade.profit_loss:>11,.2f}"
        )

    print(f"\n{'=' * 80}\n")


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
        # Default: 2 years backtest
        test_start = test_end - timedelta(days=730)

    if args.train_end:
        train_end = datetime.strptime(args.train_end, "%Y-%m-%d")
    else:
        # Train up to backtest start
        train_end = test_start - timedelta(days=1)

    if args.train_start:
        train_start = datetime.strptime(args.train_start, "%Y-%m-%d")
    else:
        # Default: 3 years training
        train_start = train_end - timedelta(days=1095)

    # Determine tickers
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",")]
    else:
        tickers = TICKER_SYMBOLS

    print(f"\n{'=' * 80}")
    print("CATBOOST TRAINING & BACKTESTING")
    print(f"{'=' * 80}")
    print(f"\nTickers: {len(tickers)} ({', '.join(tickers[:10])}{'...' if len(tickers) > 10 else ''})")
    print(f"\nTraining Period: {train_start.date()} to {train_end.date()}")
    print(f"  Duration: {(train_end - train_start).days} days ({(train_end - train_start).days / 365:.1f} years)")
    print(f"\nBacktest Period: {test_start.date()} to {test_end.date()}")
    print(f"  Duration: {(test_end - test_start).days} days ({(test_end - test_start).days / 365:.1f} years)")
    print(f"\nStrategy Parameters:")
    print(f"  Prediction Days: {args.prediction_days}")
    print(f"  Profit Threshold: {args.profit_threshold:.1%}")
    print(f"  Stop Loss: {args.stop_loss:.1%}")
    print(f"  Take Profit: {args.take_profit:.1%}")
    print(f"  Max Holding Days: {args.max_holding_days}")
    print(f"  Min ML Confidence: {args.min_confidence:.1%}")
    print(f"\nPortfolio Parameters:")
    print(f"  Starting Capital: ${args.capital:,.2f}")
    print(f"  Position Size: {args.position_size:.1%}")
    print(f"  Max Positions: {args.max_positions}")
    print(f"{'=' * 80}\n")

    with MarketDataDB() as db:
        # Initialize trainer
        trainer = CatBoostTrainer(
            db=db,
            prediction_days=args.prediction_days,
            profit_threshold=args.profit_threshold,
        )

        if not args.skip_training:
            # Prepare training data
            print("Preparing training data...")
            X, full_df = trainer.prepare_training_data(tickers, train_start, train_end)

            print(f"\nDataset size: {len(full_df):,} samples")
            print(f"Features: {len(trainer.feature_names)}")

            # Train direction model
            metrics = trainer.train_direction_model(X, full_df["target_direction"])

            # Train return model
            return_metrics = trainer.train_return_model(X, full_df["target_return"])

            # Save models
            trainer.save_models(suffix=args.model_suffix)

        else:
            print("Loading pre-trained models...")
            trainer.load_models(suffix=args.model_suffix)

        # Run backtest
        print(f"\n{'=' * 80}")
        print("RUNNING BACKTEST")
        print(f"{'=' * 80}\n")

        config = BacktestConfig(
            starting_capital=Decimal(str(args.capital)),
            position_size_pct=args.position_size,
            max_positions=args.max_positions,
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

        results = engine.run(tickers, test_start, test_end)

        # Print report
        print_backtest_report(results)


if __name__ == "__main__":
    main()
