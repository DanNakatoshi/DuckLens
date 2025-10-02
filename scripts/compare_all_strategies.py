"""Compare multiple strategy variations to find what beats buy & hold."""

import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.storage.market_data_db import MarketDataDB
from src.models.trend_detector import TrendDetector, TradingSignal


class StrategyBacktester:
    """Backtest different strategy variations."""

    def __init__(self, ticker: str, start_date: str, end_date: str):
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.db = MarketDataDB()

        # Get price data
        query = """
            SELECT DATE(timestamp) as date, close, high, low
            FROM stock_prices
            WHERE symbol = ?
            AND DATE(timestamp) >= DATE(?)
            AND DATE(timestamp) <= DATE(?)
            ORDER BY timestamp
        """
        self.price_data = self.db.conn.execute(
            query, [ticker, start_date, end_date]
        ).fetchall()

    def get_indicators(self, date):
        """Get technical indicators for a date."""
        query = """
            SELECT sma_20, sma_50, sma_200, macd, rsi_14
            FROM technical_indicators
            WHERE symbol = ? AND DATE(timestamp) = DATE(?)
        """
        result = self.db.conn.execute(query, [self.ticker, date]).fetchone()
        if result:
            return {
                "sma_20": float(result[0]) if result[0] else None,
                "sma_50": float(result[1]) if result[1] else None,
                "sma_200": float(result[2]) if result[2] else None,
                "macd": float(result[3]) if result[3] else None,
                "rsi": float(result[4]) if result[4] else None,
            }
        return None

    def strategy_baseline(self, verbose=False):
        """Baseline: Current strategy (death cross exit)."""
        detector = TrendDetector(
            db=self.db,
            min_confidence=0.6,
            confirmation_days=1,
            long_only=True,
        )

        cash = 10000.0
        shares = 0
        position = None
        trades = []

        for date, price, high, low in self.price_data:
            price = float(price)
            signal_data = detector.generate_signal(self.ticker, date, price)

            if signal_data.signal == TradingSignal.BUY and position is None:
                shares = cash / price
                position = {"entry_price": price, "entry_date": date}
                cash = 0
                if verbose:
                    print(f"[BUY] {date} @ ${price:.2f}")

            elif signal_data.signal == TradingSignal.SELL and position is not None:
                cash = shares * price
                pnl_pct = (price / position["entry_price"] - 1) * 100
                trades.append({"pnl_pct": pnl_pct})
                if verbose:
                    print(f"[SELL] {date} @ ${price:.2f} ({pnl_pct:+.2f}%)")
                position = None
                shares = 0

        # Close at end
        if position:
            final_price = float(self.price_data[-1][1])
            cash = shares * final_price
            pnl_pct = (final_price / position["entry_price"] - 1) * 100
            trades.append({"pnl_pct": pnl_pct})
            shares = 0

        return cash, trades

    def strategy_leverage(self, leverage=1.5, verbose=False):
        """Option 1: Use leverage on strong trends (ADX > 40)."""
        detector = TrendDetector(
            db=self.db,
            min_confidence=0.6,
            confirmation_days=1,
            long_only=True,
        )

        cash = 10000.0
        shares = 0
        position = None
        trades = []

        for date, price, high, low in self.price_data:
            price = float(price)
            signal_data = detector.generate_signal(self.ticker, date, price)
            indicators = self.get_indicators(date)

            if signal_data.signal == TradingSignal.BUY and position is None:
                # Use leverage if strong trend (high confidence, healthy RSI)
                rsi = indicators["rsi"] if indicators else None
                use_leverage = (
                    signal_data.confidence >= 0.75
                    and rsi
                    and 40 < rsi < 75
                )

                multiplier = leverage if use_leverage else 1.0
                shares = (cash * multiplier) / price
                position = {
                    "entry_price": price,
                    "entry_date": date,
                    "leverage": multiplier,
                }
                cash = 0
                if verbose:
                    print(f"[BUY] {date} @ ${price:.2f} (leverage: {multiplier:.1f}x)")

            elif signal_data.signal == TradingSignal.SELL and position is not None:
                cash = shares * price
                pnl_pct = (price / position["entry_price"] - 1) * 100 * position["leverage"]
                trades.append({"pnl_pct": pnl_pct})
                if verbose:
                    print(f"[SELL] {date} @ ${price:.2f} ({pnl_pct:+.2f}%)")
                position = None
                shares = 0

        if position:
            final_price = float(self.price_data[-1][1])
            cash = shares * final_price
            pnl_pct = (final_price / position["entry_price"] - 1) * 100 * position["leverage"]
            trades.append({"pnl_pct": pnl_pct})

        return cash, trades

    def strategy_hybrid(self, core_pct=0.5, verbose=False):
        """Option 2: Hold 50% permanently, trade 50%."""
        detector = TrendDetector(
            db=self.db,
            min_confidence=0.6,
            confirmation_days=1,
            long_only=True,
        )

        initial_cash = 10000.0

        # Buy core position at start
        first_price = float(self.price_data[0][1])
        core_shares = (initial_cash * core_pct) / first_price

        # Trading portion
        cash = initial_cash * (1 - core_pct)
        shares = 0
        position = None
        trades = []

        for date, price, high, low in self.price_data:
            price = float(price)
            signal_data = detector.generate_signal(self.ticker, date, price)

            if signal_data.signal == TradingSignal.BUY and position is None:
                shares = cash / price
                position = {"entry_price": price, "entry_date": date}
                cash = 0
                if verbose:
                    print(f"[BUY] {date} @ ${price:.2f} (trading portion)")

            elif signal_data.signal == TradingSignal.SELL and position is not None:
                cash = shares * price
                pnl_pct = (price / position["entry_price"] - 1) * 100
                trades.append({"pnl_pct": pnl_pct})
                if verbose:
                    print(f"[SELL] {date} @ ${price:.2f} ({pnl_pct:+.2f}%)")
                position = None
                shares = 0

        # Calculate final value
        if position:
            final_price = float(self.price_data[-1][1])
            cash = shares * final_price
            pnl_pct = (final_price / position["entry_price"] - 1) * 100
            trades.append({"pnl_pct": pnl_pct})
            shares = 0

        final_price = float(self.price_data[-1][1])
        total_value = cash + (core_shares * final_price)

        return total_value, trades

    def strategy_trailing_stop(self, stop_pct=0.15, verbose=False):
        """Option 4: Use trailing stop loss instead of death cross."""
        detector = TrendDetector(
            db=self.db,
            min_confidence=0.6,
            confirmation_days=1,
            long_only=True,
        )

        cash = 10000.0
        shares = 0
        position = None
        trades = []

        for date, price, high, low in self.price_data:
            price = float(price)
            high = float(high)
            signal_data = detector.generate_signal(self.ticker, date, price)

            # Entry
            if signal_data.signal == TradingSignal.BUY and position is None:
                shares = cash / price
                position = {
                    "entry_price": price,
                    "entry_date": date,
                    "highest_price": high,
                    "stop_loss": price * (1 - stop_pct),
                }
                cash = 0
                if verbose:
                    print(f"[BUY] {date} @ ${price:.2f} (stop: ${position['stop_loss']:.2f})")

            # Update trailing stop
            elif position is not None:
                if high > position["highest_price"]:
                    position["highest_price"] = high
                    position["stop_loss"] = high * (1 - stop_pct)

                # Check stop loss
                if price <= position["stop_loss"]:
                    cash = shares * price
                    pnl_pct = (price / position["entry_price"] - 1) * 100
                    trades.append({"pnl_pct": pnl_pct})
                    if verbose:
                        print(f"[STOP] {date} @ ${price:.2f} ({pnl_pct:+.2f}%) - hit trailing stop")
                    position = None
                    shares = 0

        if position:
            final_price = float(self.price_data[-1][1])
            cash = shares * final_price
            pnl_pct = (final_price / position["entry_price"] - 1) * 100
            trades.append({"pnl_pct": pnl_pct})

        return cash, trades

    def strategy_better_exits(self, verbose=False):
        """Option 3: Exit on RSI > 80 OR MACD bearish crossover."""
        detector = TrendDetector(
            db=self.db,
            min_confidence=0.6,
            confirmation_days=1,
            long_only=True,
        )

        cash = 10000.0
        shares = 0
        position = None
        trades = []

        for date, price, high, low in self.price_data:
            price = float(price)
            signal_data = detector.generate_signal(self.ticker, date, price)
            indicators = self.get_indicators(date)

            # Entry
            if signal_data.signal == TradingSignal.BUY and position is None:
                shares = cash / price
                position = {"entry_price": price, "entry_date": date}
                cash = 0
                if verbose:
                    print(f"[BUY] {date} @ ${price:.2f}")

            # Exit on overbought OR price below SMA_20
            elif position is not None and indicators:
                rsi = indicators["rsi"]
                sma_20 = indicators["sma_20"]

                should_exit = False
                exit_reason = ""

                # Exit if RSI overbought AND price falling
                if rsi and rsi > 80 and sma_20 and price < sma_20:
                    should_exit = True
                    exit_reason = "RSI overbought + price < SMA_20"

                # Exit on death cross (backup)
                elif signal_data.signal == TradingSignal.SELL:
                    should_exit = True
                    exit_reason = "Death cross"

                if should_exit:
                    cash = shares * price
                    pnl_pct = (price / position["entry_price"] - 1) * 100
                    trades.append({"pnl_pct": pnl_pct})
                    if verbose:
                        print(f"[SELL] {date} @ ${price:.2f} ({pnl_pct:+.2f}%) - {exit_reason}")
                    position = None
                    shares = 0

        if position:
            final_price = float(self.price_data[-1][1])
            cash = shares * final_price
            pnl_pct = (final_price / position["entry_price"] - 1) * 100
            trades.append({"pnl_pct": pnl_pct})

        return cash, trades

    def calculate_buy_hold(self):
        """Calculate buy & hold return."""
        first_price = float(self.price_data[0][1])
        last_price = float(self.price_data[-1][1])
        return 10000 * (last_price / first_price)


def main():
    """Test all strategies on multiple tickers."""
    tickers = ["AAPL", "NVDA", "SPY", "QQQ"]
    start_date = "2023-01-01"
    end_date = "2025-09-30"

    print(f"\n{'='*100}")
    print("STRATEGY COMPARISON - FIND WHAT BEATS BUY & HOLD")
    print(f"{'='*100}")
    print(f"Period: {start_date} to {end_date}")
    print(f"Tickers: {', '.join(tickers)}")
    print(f"Starting capital: $10,000\n")

    all_results = []

    for ticker in tickers:
        print(f"\n{'='*100}")
        print(f"{ticker}")
        print(f"{'='*100}\n")

        bt = StrategyBacktester(ticker, start_date, end_date)

        # Calculate all strategies
        bh_value = bt.calculate_buy_hold()
        baseline_value, baseline_trades = bt.strategy_baseline()
        leverage_value, leverage_trades = bt.strategy_leverage(leverage=1.5)
        hybrid_value, hybrid_trades = bt.strategy_hybrid(core_pct=0.5)
        trailing_value, trailing_trades = bt.strategy_trailing_stop(stop_pct=0.15)
        better_exits_value, better_exits_trades = bt.strategy_better_exits()

        # Store results
        results = {
            "ticker": ticker,
            "buy_hold": (bh_value - 10000) / 100,
            "baseline": (baseline_value - 10000) / 100,
            "leverage_1.5x": (leverage_value - 10000) / 100,
            "hybrid_50_50": (hybrid_value - 10000) / 100,
            "trailing_15%": (trailing_value - 10000) / 100,
            "better_exits": (better_exits_value - 10000) / 100,
            "baseline_trades": len(baseline_trades),
            "leverage_trades": len(leverage_trades),
            "hybrid_trades": len(hybrid_trades),
            "trailing_trades": len(trailing_trades),
            "better_exits_trades": len(better_exits_trades),
        }

        # Print results for this ticker
        print(f"Buy & Hold:           {results['buy_hold']:>8.2f}%")
        print(f"Baseline (current):   {results['baseline']:>8.2f}% ({results['baseline_trades']} trades)")
        print(f"Leverage 1.5x:        {results['leverage_1.5x']:>8.2f}% ({results['leverage_trades']} trades)")
        print(f"Hybrid 50/50:         {results['hybrid_50_50']:>8.2f}% ({results['hybrid_trades']} trades)")
        print(f"Trailing Stop 15%:    {results['trailing_15%']:>8.2f}% ({results['trailing_trades']} trades)")
        print(f"Better Exits (RSI):   {results['better_exits']:>8.2f}% ({results['better_exits_trades']} trades)")

        # Highlight best strategy
        strategies = [
            ("Baseline", results["baseline"]),
            ("Leverage 1.5x", results["leverage_1.5x"]),
            ("Hybrid 50/50", results["hybrid_50_50"]),
            ("Trailing Stop", results["trailing_15%"]),
            ("Better Exits", results["better_exits"]),
        ]
        best_strategy = max(strategies, key=lambda x: x[1])
        beats_bh = best_strategy[1] > results["buy_hold"]

        print(f"\n-> Best: {best_strategy[0]} ({best_strategy[1]:.2f}%)")
        if beats_bh:
            print(f"   *** BEATS BUY & HOLD by {best_strategy[1] - results['buy_hold']:.2f}% ***")
        else:
            print(f"   Still underperforms by {best_strategy[1] - results['buy_hold']:.2f}%")

        all_results.append(results)

    # Summary table
    print(f"\n{'='*100}")
    print("SUMMARY - ALL TICKERS")
    print(f"{'='*100}\n")

    print(f"{'Ticker':<8} | {'Buy&Hold':<10} | {'Baseline':<10} | {'Leverage':<10} | {'Hybrid':<10} | {'Trailing':<10} | {'BetterExit':<10}")
    print(f"{'-'*8}-+-{'-'*10}-+-{'-'*10}-+-{'-'*10}-+-{'-'*10}-+-{'-'*10}-+-{'-'*10}")

    for r in all_results:
        print(
            f"{r['ticker']:<8} | "
            f"{r['buy_hold']:>9.2f}% | "
            f"{r['baseline']:>9.2f}% | "
            f"{r['leverage_1.5x']:>9.2f}% | "
            f"{r['hybrid_50_50']:>9.2f}% | "
            f"{r['trailing_15%']:>9.2f}% | "
            f"{r['better_exits']:>9.2f}%"
        )

    print(f"\n{'='*100}\n")


if __name__ == "__main__":
    main()
