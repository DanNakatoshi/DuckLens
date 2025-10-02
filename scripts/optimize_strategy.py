"""
Optimize strategy hyperparameters to find best configuration.

Tests different combinations of:
- Prediction days (5, 15, 30, 60)
- Stop loss % (5%, 8%, 10%)
- Take profit % (10%, 15%, 20%, 30%)
- Max holding days (30, 60, 90)
- Min ML confidence (0.55, 0.60, 0.65, 0.70)

Evaluates each configuration and ranks by:
- Total return %
- Win rate
- Sharpe ratio
- Max drawdown
"""

import argparse
import itertools
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd

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
    parser = argparse.ArgumentParser(description="Optimize strategy hyperparameters")

    parser.add_argument("--start-date", type=str, help="Backtest start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, help="Backtest end date (YYYY-MM-DD)")

    parser.add_argument(
        "--capital", type=float, default=100000, help="Starting capital (default: 100000)"
    )

    parser.add_argument(
        "--tickers",
        type=str,
        help="Comma-separated tickers to test (default: all tickers)",
    )

    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: test fewer combinations",
    )

    parser.add_argument(
        "--output",
        type=str,
        default="optimization_results.csv",
        help="Output CSV file (default: optimization_results.csv)",
    )

    return parser.parse_args()


def run_backtest_config(
    db: MarketDataDB,
    tickers: list[str],
    start_date: datetime,
    end_date: datetime,
    config_params: dict,
    trainer: CatBoostTrainer,
) -> dict:
    """Run backtest with specific configuration."""
    config = BacktestConfig(
        starting_capital=config_params["capital"],
        position_size_pct=0.1,  # Fixed
        max_positions=5,  # Fixed
        stop_loss_pct=config_params["stop_loss_pct"],
        take_profit_pct=config_params["take_profit_pct"],
        max_holding_days=config_params["max_holding_days"],
        min_ml_confidence=config_params["min_confidence"],
    )

    strategy = TradingStrategy(
        db=db,
        stop_loss_pct=config["stop_loss_pct"],
        take_profit_pct=config["take_profit_pct"],
        max_holding_days=config["max_holding_days"],
    )

    engine = BacktestEngine(db=db, config=config, strategy=strategy, ml_trainer=trainer)

    results = engine.run(tickers, start_date, end_date)

    return {
        "prediction_days": config_params["prediction_days"],
        "stop_loss_pct": config_params["stop_loss_pct"],
        "take_profit_pct": config_params["take_profit_pct"],
        "max_holding_days": config_params["max_holding_days"],
        "min_confidence": config_params["min_confidence"],
        "total_return_pct": results.total_return_pct,
        "win_rate": results.win_rate,
        "total_trades": results.total_trades,
        "sharpe_ratio": results.sharpe_ratio,
        "sortino_ratio": results.sortino_ratio,
        "max_drawdown": results.max_drawdown,
        "profit_factor": results.profit_factor,
        "avg_holding_days": results.avg_holding_days,
    }


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
        # Default: 2 years
        start_date = end_date - timedelta(days=730)

    # Determine tickers
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",")]
    else:
        tickers = TICKER_SYMBOLS

    print(f"\n{'=' * 80}")
    print("STRATEGY HYPERPARAMETER OPTIMIZATION")
    print(f"{'=' * 80}")
    print(f"\nTickers: {len(tickers)}")
    print(f"Period: {start_date.date()} to {end_date.date()}")
    print(f"Duration: {(end_date - start_date).days} days")

    # Define parameter grid
    if args.quick:
        param_grid = {
            "prediction_days": [5, 30],
            "stop_loss_pct": [0.08, 0.10],
            "take_profit_pct": [0.15, 0.20],
            "max_holding_days": [30, 60],
            "min_confidence": [0.60, 0.65],
        }
    else:
        param_grid = {
            "prediction_days": [5, 15, 30, 60],
            "stop_loss_pct": [0.05, 0.08, 0.10],
            "take_profit_pct": [0.10, 0.15, 0.20, 0.30],
            "max_holding_days": [30, 60, 90],
            "min_confidence": [0.55, 0.60, 0.65, 0.70],
        }

    # Generate all combinations
    param_combinations = [
        dict(zip(param_grid.keys(), values))
        for values in itertools.product(*param_grid.values())
    ]

    total_combinations = len(param_combinations)
    print(f"\nTotal configurations to test: {total_combinations}")
    print(f"{'=' * 80}\n")

    with MarketDataDB() as db:
        results_list = []

        for idx, params in enumerate(param_combinations, 1):
            print(f"\n[{idx}/{total_combinations}] Testing configuration:")
            print(f"  Prediction Days: {params['prediction_days']}")
            print(f"  Stop Loss: {params['stop_loss_pct']:.1%}")
            print(f"  Take Profit: {params['take_profit_pct']:.1%}")
            print(f"  Max Holding: {params['max_holding_days']} days")
            print(f"  Min Confidence: {params['min_confidence']:.1%}")

            # Train model for this prediction_days setting
            trainer = CatBoostTrainer(
                db=db,
                prediction_days=params["prediction_days"],
                profit_threshold=0.02,
            )

            # Check if model exists, otherwise train
            model_path = Path("models") / f"direction_model_pred{params['prediction_days']}.cbm"

            if model_path.exists():
                print(f"  Loading existing model...")
                trainer.load_models(suffix=f"_pred{params['prediction_days']}")
            else:
                print(f"  Training new model...")
                train_start = start_date - timedelta(days=1095)  # 3 years training
                train_end = start_date - timedelta(days=1)

                X, full_df = trainer.prepare_training_data(tickers, train_start, train_end)

                if len(full_df) == 0:
                    print("  ERROR: No training data available")
                    continue

                trainer.train_direction_model(X, full_df["target_direction"], iterations=500)
                trainer.train_return_model(X, full_df["target_return"], iterations=500)
                trainer.save_models(suffix=f"_pred{params['prediction_days']}")

            # Run backtest
            params["capital"] = Decimal(str(args.capital))

            try:
                result = run_backtest_config(
                    db, tickers, start_date, end_date, params, trainer
                )
                results_list.append(result)

                print(f"\n  Results:")
                print(f"    Return: {result['total_return_pct']:>6.2f}%")
                print(f"    Win Rate: {result['win_rate']:>6.1%}")
                print(f"    Trades: {result['total_trades']:>6}")
                print(f"    Sharpe: {result['sharpe_ratio']:>6.2f}")
                print(f"    Max DD: {result['max_drawdown']:>6.1%}")

            except Exception as e:
                print(f"  ERROR: {e}")
                continue

        # Convert to DataFrame
        results_df = pd.DataFrame(results_list)

        if results_df.empty:
            print("\nNo results collected!")
            return

        # Save to CSV
        results_df.to_csv(args.output, index=False)
        print(f"\nSaved results to {args.output}")

        # Print top configurations
        print(f"\n{'=' * 80}")
        print("TOP 10 CONFIGURATIONS BY TOTAL RETURN")
        print(f"{'=' * 80}\n")

        top_by_return = results_df.nlargest(10, "total_return_pct")

        print(f"{'Rank':>4} {'Pred':>5} {'SL':>6} {'TP':>6} {'Hold':>5} {'Conf':>6} {'Return':>8} {'Win%':>6} {'Sharpe':>7} {'MaxDD':>7}")
        print(f"{'-' * 80}")

        for rank, row in enumerate(top_by_return.itertuples(), 1):
            print(
                f"{rank:>4} {row.prediction_days:>5} "
                f"{row.stop_loss_pct:>5.0%} "
                f"{row.take_profit_pct:>5.0%} "
                f"{row.max_holding_days:>5} "
                f"{row.min_confidence:>5.0%} "
                f"{row.total_return_pct:>7.2f}% "
                f"{row.win_rate:>5.1%} "
                f"{row.sharpe_ratio:>6.2f} "
                f"{row.max_drawdown:>6.1%}"
            )

        print(f"\n{'=' * 80}")
        print("TOP 10 CONFIGURATIONS BY SHARPE RATIO")
        print(f"{'=' * 80}\n")

        top_by_sharpe = results_df.nlargest(10, "sharpe_ratio")

        print(f"{'Rank':>4} {'Pred':>5} {'SL':>6} {'TP':>6} {'Hold':>5} {'Conf':>6} {'Return':>8} {'Win%':>6} {'Sharpe':>7} {'MaxDD':>7}")
        print(f"{'-' * 80}")

        for rank, row in enumerate(top_by_sharpe.itertuples(), 1):
            print(
                f"{rank:>4} {row.prediction_days:>5} "
                f"{row.stop_loss_pct:>5.0%} "
                f"{row.take_profit_pct:>5.0%} "
                f"{row.max_holding_days:>5} "
                f"{row.min_confidence:>5.0%} "
                f"{row.total_return_pct:>7.2f}% "
                f"{row.win_rate:>5.1%} "
                f"{row.sharpe_ratio:>6.2f} "
                f"{row.max_drawdown:>6.1%}"
            )

        print(f"\n{'=' * 80}")
        print("TOP 10 CONFIGURATIONS BY WIN RATE")
        print(f"{'=' * 80}\n")

        top_by_winrate = results_df.nlargest(10, "win_rate")

        print(f"{'Rank':>4} {'Pred':>5} {'SL':>6} {'TP':>6} {'Hold':>5} {'Conf':>6} {'Return':>8} {'Win%':>6} {'Sharpe':>7} {'MaxDD':>7}")
        print(f"{'-' * 80}")

        for rank, row in enumerate(top_by_winrate.itertuples(), 1):
            print(
                f"{rank:>4} {row.prediction_days:>5} "
                f"{row.stop_loss_pct:>5.0%} "
                f"{row.take_profit_pct:>5.0%} "
                f"{row.max_holding_days:>5} "
                f"{row.min_confidence:>5.0%} "
                f"{row.total_return_pct:>7.2f}% "
                f"{row.win_rate:>5.1%} "
                f"{row.sharpe_ratio:>6.2f} "
                f"{row.max_drawdown:>6.1%}"
            )

        print(f"\n{'=' * 80}\n")


if __name__ == "__main__":
    main()
