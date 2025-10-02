"""
Compare three strategies on SPY:
1. Rule-based (current long-only with death cross)
2. CatBoost Entry Filter (Option C - filter weak entries)
3. CatBoost Trend Strength (Option B - predict trend strength)

Shows which approach works best and which technical signals trigger buys.
"""

import sys
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.data.storage.market_data_db import MarketDataDB
from src.ml.catboost_entry_filter import CatBoostEntryFilter
from src.models.trend_detector import TradingSignal, TrendDetector


def run_backtest(
    detector: TrendDetector,
    ml_filter: CatBoostEntryFilter | None,
    db: MarketDataDB,
    start_date: datetime,
    end_date: datetime,
    starting_capital: float,
    strategy_name: str,
    ml_threshold: float = 0.6,
) -> dict:
    """Run backtest for a specific strategy."""

    print(f"\n{'=' * 80}")
    print(f"BACKTESTING: {strategy_name}")
    print(f"{'=' * 80}\n")

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

    # Backtest state
    capital = Decimal(str(starting_capital))
    position_shares = Decimal("0")
    position_entry_price = None
    position_entry_date = None
    position_entry_reason = None

    trades = []
    entry_reasons = defaultdict(int)  # Track what triggers buys
    ml_rejections = 0
    ml_acceptances = 0

    for i, date in enumerate(trading_days):
        # Get current price
        price_query = "SELECT close FROM stock_prices WHERE symbol = 'SPY' AND DATE(timestamp) = DATE(?)"
        price_result = db.conn.execute(price_query, [date]).fetchone()

        if not price_result:
            continue

        current_price = Decimal(str(price_result[0]))

        # Generate signal
        signal = detector.generate_signal("SPY", date, current_price)

        if not signal:
            continue

        # Process BUY signal
        if signal.signal == TradingSignal.BUY and position_shares == 0:
            # If using ML filter, check confidence
            should_take_trade = True

            if ml_filter is not None:
                # Get features for this date
                features_query = """
                SELECT
                    ti.sma_20, ti.sma_50, ti.sma_200,
                    ti.macd, ti.macd_signal, ti.rsi_14
                FROM technical_indicators ti
                WHERE ti.symbol = 'SPY' AND DATE(ti.timestamp) = DATE(?)
                """
                feat_result = db.conn.execute(features_query, [date]).fetchone()

                if feat_result:
                    # Create feature dict
                    import pandas as pd

                    # Prepare minimal features (would need full feature set in production)
                    features_dict = {
                        "sma_20": feat_result[0],
                        "sma_50": feat_result[1],
                        "sma_200": feat_result[2],
                        "macd": feat_result[3],
                        "macd_signal": feat_result[4],
                        "rsi_14": feat_result[5],
                    }

                    # Calculate derived features
                    if all(v is not None for v in [feat_result[0], feat_result[1], feat_result[2]]):
                        features_dict["sma_alignment"] = int(
                            float(feat_result[0]) > float(feat_result[1])
                        ) + int(float(feat_result[1]) > float(feat_result[2]))
                        features_dict["distance_sma_20"] = (
                            float(current_price) - float(feat_result[0])
                        ) / float(feat_result[0])
                        features_dict["distance_sma_50"] = (
                            float(current_price) - float(feat_result[1])
                        ) / float(feat_result[1])
                        features_dict["distance_sma_200"] = (
                            float(current_price) - float(feat_result[2])
                        ) / float(feat_result[2])
                    else:
                        features_dict["sma_alignment"] = 0
                        features_dict["distance_sma_20"] = 0
                        features_dict["distance_sma_50"] = 0
                        features_dict["distance_sma_200"] = 0

                    features_dict["macd_bullish"] = int(
                        feat_result[3] > feat_result[4]
                        if feat_result[3] and feat_result[4]
                        else 0
                    )
                    features_dict["rsi_healthy"] = int(
                        40 <= feat_result[5] <= 70 if feat_result[5] else 0
                    )

                    # Fill missing features with 0
                    for feat in ml_filter.feature_names:
                        if feat not in features_dict:
                            features_dict[feat] = 0

                    # Create DataFrame with correct column order
                    X = pd.DataFrame([features_dict])[ml_filter.feature_names]

                    # Get ML prediction
                    try:
                        prediction, ml_confidence = ml_filter.predict_entry_quality(X)

                        if ml_confidence < ml_threshold:
                            should_take_trade = False
                            ml_rejections += 1
                        else:
                            ml_acceptances += 1
                    except Exception as e:
                        # If ML fails, fall back to rule-based
                        print(f"ML prediction failed: {e}, using rule-based")
                        pass

            if should_take_trade:
                # Open long position
                position_shares = capital / current_price
                position_entry_price = current_price
                position_entry_date = date
                position_entry_reason = signal.reasoning

                # Track entry reason
                if "GOLDEN CROSS" in signal.reasoning or "SMA: Bullish" in signal.reasoning:
                    entry_reasons["SMA Alignment (Golden Cross)"] += 1
                elif "MACD: Bullish" in signal.reasoning:
                    entry_reasons["MACD Crossover"] += 1
                elif "RSI: Healthy" in signal.reasoning:
                    entry_reasons["RSI Healthy Range"] += 1
                elif "Options Flow: BULLISH" in signal.reasoning:
                    entry_reasons["Options Flow Bullish"] += 1
                else:
                    entry_reasons["Mixed Signals"] += 1

        # Process SELL signal
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
                "entry_reason": position_entry_reason,
            })

            capital = exit_value
            position_shares = Decimal("0")
            position_entry_price = None
            position_entry_date = None
            position_entry_reason = None

    # Close any open position at end
    if position_shares > 0:
        final_price = current_price
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
            "entry_reason": position_entry_reason,
        })

        capital = exit_value

    # Calculate results
    starting_capital_dec = Decimal(str(starting_capital))
    ending_capital = capital
    total_return = ending_capital - starting_capital_dec
    total_return_pct = (ending_capital / starting_capital_dec - 1) * 100

    winners = [t for t in trades if t["pnl"] > 0]
    losers = [t for t in trades if t["pnl"] <= 0]
    win_rate = len(winners) / len(trades) * 100 if trades else 0

    return {
        "strategy_name": strategy_name,
        "starting_capital": starting_capital_dec,
        "ending_capital": ending_capital,
        "total_return": total_return,
        "total_return_pct": float(total_return_pct),
        "total_trades": len(trades),
        "winners": len(winners),
        "losers": len(losers),
        "win_rate": win_rate,
        "trades": trades,
        "entry_reasons": dict(entry_reasons),
        "ml_rejections": ml_rejections,
        "ml_acceptances": ml_acceptances,
    }


def main():
    print("=" * 80)
    print("STRATEGY COMPARISON: SPY (2020-2025)")
    print("=" * 80)

    db = MarketDataDB()

    # Training period: 2020-2023 (Oct 2020 - Dec 2023)
    train_start = datetime(2020, 10, 1)
    train_end = datetime(2023, 12, 31)

    # Test period: 2024-2025 (Jan 2024 - Sep 2025)
    test_start = datetime(2024, 1, 1)
    test_end = datetime(2025, 9, 30)

    starting_capital = 100000

    # ========== TRAIN CATBOOST MODEL ==========
    print("\n" + "=" * 80)
    print("STEP 1: TRAIN CATBOOST ENTRY FILTER")
    print("=" * 80)

    ml_filter = CatBoostEntryFilter(db=db, holding_days=30, profit_threshold=0.02)

    X_train, y_train, df_train = ml_filter.prepare_training_data("SPY", train_start, train_end)

    metrics = ml_filter.train(X_train, y_train, iterations=300, learning_rate=0.05, depth=4)

    # ========== STRATEGY 1: RULE-BASED (BASELINE) ==========
    detector_rule = TrendDetector(
        db=db,
        min_confidence=0.6,
        block_high_impact_events=True,
        min_adx=0,
        confirmation_days=1,
        long_only=True,
    )

    results_rule = run_backtest(
        detector=detector_rule,
        ml_filter=None,
        db=db,
        start_date=test_start,
        end_date=test_end,
        starting_capital=starting_capital,
        strategy_name="Rule-Based (Baseline)",
    )

    # ========== STRATEGY 2: CATBOOST FILTER (60% threshold) ==========
    detector_filter = TrendDetector(
        db=db,
        min_confidence=0.6,
        block_high_impact_events=True,
        min_adx=0,
        confirmation_days=1,
        long_only=True,
    )

    results_filter = run_backtest(
        detector=detector_filter,
        ml_filter=ml_filter,
        db=db,
        start_date=test_start,
        end_date=test_end,
        starting_capital=starting_capital,
        strategy_name="CatBoost Filter (60% threshold)",
        ml_threshold=0.6,
    )

    # ========== STRATEGY 3: CATBOOST FILTER (70% threshold - stricter) ==========
    detector_filter_strict = TrendDetector(
        db=db,
        min_confidence=0.6,
        block_high_impact_events=True,
        min_adx=0,
        confirmation_days=1,
        long_only=True,
    )

    results_filter_strict = run_backtest(
        detector=detector_filter_strict,
        ml_filter=ml_filter,
        db=db,
        start_date=test_start,
        end_date=test_end,
        starting_capital=starting_capital,
        strategy_name="CatBoost Filter (70% threshold - Stricter)",
        ml_threshold=0.7,
    )

    # ========== COMPARE RESULTS ==========
    print("\n\n" + "=" * 80)
    print("STRATEGY COMPARISON RESULTS")
    print("=" * 80)

    # Buy & hold comparison
    first_price_query = "SELECT close FROM stock_prices WHERE symbol = 'SPY' AND DATE(timestamp) >= DATE(?) ORDER BY timestamp LIMIT 1"
    last_price_query = "SELECT close FROM stock_prices WHERE symbol = 'SPY' AND DATE(timestamp) <= DATE(?) ORDER BY timestamp DESC LIMIT 1"

    first_result = db.conn.execute(first_price_query, [test_start]).fetchone()
    last_result = db.conn.execute(last_price_query, [test_end]).fetchone()

    if not first_result or not last_result:
        print("ERROR: No price data found for test period")
        return

    first_price = Decimal(str(first_result[0]))
    last_price = Decimal(str(last_result[0]))
    buy_hold_return = (last_price / first_price - 1) * 100

    results_all = [results_rule, results_filter, results_filter_strict]

    print(f"\n{'Strategy':<40} | {'Return':<12} | {'Trades':<8} | {'Win Rate':<10} | {'vs Buy&Hold':<12}")
    print("-" * 95)

    buy_hold_str = f"+{buy_hold_return:.2f}%"
    print(
        f"{'Buy & Hold SPY':<40} | {buy_hold_str:<12} | {'1':<8} | {'N/A':<10} | {'Baseline':<12}"
    )

    for result in results_all:
        alpha = result["total_return_pct"] - float(buy_hold_return)
        return_str = f"+{result['total_return_pct']:.2f}%"
        alpha_str = f"{alpha:+.2f}%"
        win_rate_str = f"{result['win_rate']:.1f}%"
        print(
            f"{result['strategy_name']:<40} | "
            f"{return_str:<12} | "
            f"{result['total_trades']:<8} | "
            f"{win_rate_str:<10} | "
            f"{alpha_str:<12}"
        )

    # Detailed comparison
    print(f"\n{'=' * 80}")
    print("DETAILED METRICS")
    print(f"{'=' * 80}\n")

    for result in results_all:
        print(f"\n{result['strategy_name']}:")
        print(f"  Total Return: ${result['total_return']:,.2f} ({result['total_return_pct']:+.2f}%)")
        print(f"  Trades: {result['total_trades']} (Winners: {result['winners']}, Losers: {result['losers']})")
        print(f"  Win Rate: {result['win_rate']:.1f}%")

        if result["ml_rejections"] > 0 or result["ml_acceptances"] > 0:
            total_signals = result["ml_rejections"] + result["ml_acceptances"]
            print(
                f"  ML Filter: Rejected {result['ml_rejections']}/{total_signals} signals ({result['ml_rejections']/total_signals*100:.1f}%)"
            )

        if result["entry_reasons"]:
            print(f"\n  Entry Reasons (What Triggered Buys):")
            for reason, count in sorted(
                result["entry_reasons"].items(), key=lambda x: x[1], reverse=True
            ):
                print(f"    - {reason}: {count} trades")

    # Winner
    print(f"\n{'=' * 80}")
    best_strategy = max(results_all, key=lambda x: x["total_return_pct"])
    print(f"BEST STRATEGY: {best_strategy['strategy_name']}")
    print(f"Return: +{best_strategy['total_return_pct']:.2f}%")
    print(f"Win Rate: {best_strategy['win_rate']:.1f}%")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    main()
