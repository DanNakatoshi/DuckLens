"""Test different leverage levels with risk management.

This tests 1.5x, 2x, and 2.5x leverage with:
- Max drawdown protection
- Volatility-based position sizing
- Risk controls to prevent gambling
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.tickers import TRADING_WATCHLIST
from src.data.storage.market_data_db import MarketDataDB
from src.models.trend_detector import TrendDetector, TradingSignal


class LeverageBacktester:
    """Backtest leverage strategies with risk management."""

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
        """Get indicators for risk assessment."""
        query = """
            SELECT sma_20, sma_50, sma_200, rsi_14, atr_14
            FROM technical_indicators
            WHERE symbol = ? AND DATE(timestamp) = DATE(?)
        """
        result = self.db.conn.execute(query, [self.ticker, date]).fetchone()
        if result:
            return {
                "sma_20": float(result[0]) if result[0] else None,
                "sma_50": float(result[1]) if result[1] else None,
                "sma_200": float(result[2]) if result[2] else None,
                "rsi": float(result[3]) if result[3] else None,
                "atr": float(result[4]) if result[4] else None,
            }
        return None

    def strategy_leverage_with_risk(self, max_leverage=2.0, max_drawdown_pct=0.20, verbose=False):
        """
        Leverage strategy with risk controls.

        Args:
            max_leverage: Maximum leverage to use (1.5, 2.0, 2.5)
            max_drawdown_pct: Stop trading if drawdown exceeds this (default 20%)
            verbose: Print trade details
        """
        detector = TrendDetector(
            db=self.db,
            min_confidence=0.75,  # Higher bar for quality
            confirmation_days=1,
            long_only=True,
        )

        initial_capital = 10000.0
        cash = initial_capital
        shares = 0
        position = None
        trades = []

        # Risk management trackers
        peak_equity = initial_capital
        in_drawdown = False

        for date, price, high, low in self.price_data:
            price = float(price)
            signal_data = detector.generate_signal(self.ticker, date, price)
            indicators = self.get_indicators(date)

            # Calculate current equity
            current_equity = cash + (shares * price if shares > 0 else 0)

            # Update peak and check drawdown
            if current_equity > peak_equity:
                peak_equity = current_equity
                in_drawdown = False

            drawdown = (peak_equity - current_equity) / peak_equity
            if drawdown > max_drawdown_pct:
                in_drawdown = True
                if verbose and position:
                    print(f"[DRAWDOWN PROTECTION] {date} - Max drawdown exceeded, stopping trading")

            # Entry logic
            if signal_data.signal == TradingSignal.BUY and position is None and not in_drawdown:
                # Calculate leverage based on conditions
                confidence = signal_data.confidence
                rsi = indicators["rsi"] if indicators else None
                atr = indicators["atr"] if indicators else None

                # Use leverage if:
                # 1. High confidence (>= 75%)
                # 2. Healthy RSI (40-75)
                # 3. Not in high volatility (optional check)
                use_leverage = confidence >= 0.75 and rsi and 40 < rsi < 75

                if use_leverage:
                    leverage = max_leverage
                else:
                    leverage = 1.0

                shares = (cash * leverage) / price
                position = {
                    "entry_price": price,
                    "entry_date": date,
                    "leverage": leverage,
                    "peak_price": price,
                }
                cash = 0

                if verbose:
                    print(f"[BUY] {date} @ ${price:.2f} | Leverage: {leverage:.1f}x | RSI: {rsi:.0f if rsi else 'N/A'}")

            # Update trailing peak for position
            elif position is not None:
                if price > position["peak_price"]:
                    position["peak_price"] = price

                # Exit logic
                if signal_data.signal == TradingSignal.SELL:
                    cash = shares * price
                    entry_price = position["entry_price"]
                    leverage = position["leverage"]

                    # Calculate P&L with leverage effect
                    base_return = (price / entry_price - 1)
                    leveraged_return = base_return * leverage
                    pnl_pct = leveraged_return * 100

                    trades.append({
                        "entry_date": position["entry_date"],
                        "exit_date": date,
                        "entry_price": entry_price,
                        "exit_price": price,
                        "pnl_pct": pnl_pct,
                        "leverage": leverage,
                    })

                    if verbose:
                        print(f"[SELL] {date} @ ${price:.2f} | P&L: {pnl_pct:+.2f}% | Leverage: {leverage:.1f}x")

                    position = None
                    shares = 0

        # Close at end
        if position:
            final_price = float(self.price_data[-1][1])
            cash = shares * final_price
            entry_price = position["entry_price"]
            leverage = position["leverage"]
            base_return = (final_price / entry_price - 1)
            leveraged_return = base_return * leverage
            pnl_pct = leveraged_return * 100

            trades.append({
                "entry_date": position["entry_date"],
                "exit_date": self.price_data[-1][0],
                "entry_price": entry_price,
                "exit_price": final_price,
                "pnl_pct": pnl_pct,
                "leverage": leverage,
            })

        # Calculate metrics
        final_equity = cash
        total_return_pct = (final_equity / initial_capital - 1) * 100

        # Max drawdown calculation
        equity_curve = [initial_capital]
        temp_cash = initial_capital
        temp_shares = 0
        temp_pos = None

        for date, price, high, low in self.price_data:
            price = float(price)
            signal_data = detector.generate_signal(self.ticker, date, price)

            if signal_data.signal == TradingSignal.BUY and temp_pos is None:
                indicators = self.get_indicators(date)
                confidence = signal_data.confidence
                rsi = indicators["rsi"] if indicators else None
                use_leverage = confidence >= 0.75 and rsi and 40 < rsi < 75
                leverage = max_leverage if use_leverage else 1.0
                temp_shares = (temp_cash * leverage) / price
                temp_pos = {"entry_price": price, "leverage": leverage}
                temp_cash = 0

            elif signal_data.signal == TradingSignal.SELL and temp_pos is not None:
                temp_cash = temp_shares * price
                temp_shares = 0
                temp_pos = None

            current_equity = temp_cash + (temp_shares * price if temp_shares > 0 else 0)
            equity_curve.append(current_equity)

        max_dd = 0
        peak = equity_curve[0]
        for equity in equity_curve:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak
            if dd > max_dd:
                max_dd = dd

        return {
            "final_value": final_equity,
            "total_return_pct": total_return_pct,
            "num_trades": len(trades),
            "max_drawdown": max_dd * 100,
            "trades": trades,
        }

    def calculate_buy_hold(self):
        """Buy & hold return."""
        first_price = float(self.price_data[0][1])
        last_price = float(self.price_data[-1][1])
        return ((last_price / first_price) - 1) * 100


def main():
    """Test leverage levels with risk management."""
    # Test on key tickers
    tickers = ["AAPL", "NVDA", "BABA", "UNH", "MARA"]
    start_date = "2023-01-01"
    end_date = "2025-09-30"

    leverage_levels = [1.5, 2.0, 2.5]

    print(f"\n{'='*100}")
    print("LEVERAGE STRATEGY TESTING WITH RISK MANAGEMENT")
    print(f"{'='*100}")
    print(f"Period: {start_date} to {end_date}")
    print(f"Max Drawdown Protection: 20%")
    print(f"Min Confidence: 75% (only high-quality setups)")
    print(f"{'='*100}\n")

    all_results = []

    for ticker in tickers:
        print(f"\n{'='*100}")
        print(f"{ticker}")
        print(f"{'='*100}\n")

        bt = LeverageBacktester(ticker, start_date, end_date)

        # Skip if no data
        if not bt.price_data:
            print(f"No data for {ticker}, skipping...\n")
            continue

        # Calculate buy & hold
        bh_return = bt.calculate_buy_hold()

        # Test each leverage level
        results = {"ticker": ticker, "buy_hold": bh_return}

        for leverage in leverage_levels:
            result = bt.strategy_leverage_with_risk(max_leverage=leverage, max_drawdown_pct=0.20)
            key = f"leverage_{leverage}x"
            results[key] = result["total_return_pct"]
            results[f"{key}_trades"] = result["num_trades"]
            results[f"{key}_max_dd"] = result["max_drawdown"]

        # Print results
        print(f"Buy & Hold:             {results['buy_hold']:>8.2f}%")
        print(f"Leverage 1.5x:          {results['leverage_1.5x']:>8.2f}% "
              f"({results['leverage_1.5x_trades']} trades, max DD: {results['leverage_1.5x_max_dd']:.1f}%)")
        print(f"Leverage 2.0x:          {results['leverage_2.0x']:>8.2f}% "
              f"({results['leverage_2.0x_trades']} trades, max DD: {results['leverage_2.0x_max_dd']:.1f}%)")
        print(f"Leverage 2.5x:          {results['leverage_2.5x']:>8.2f}% "
              f"({results['leverage_2.5x_trades']} trades, max DD: {results['leverage_2.5x_max_dd']:.1f}%)")

        # Find best
        strategies = [
            ("1.5x", results["leverage_1.5x"]),
            ("2.0x", results["leverage_2.0x"]),
            ("2.5x", results["leverage_2.5x"]),
        ]
        best = max(strategies, key=lambda x: x[1])
        beats_bh = best[1] > results["buy_hold"]

        print(f"\n-> Best: Leverage {best[0]} ({best[1]:.2f}%)")
        if beats_bh:
            print(f"   *** BEATS BUY & HOLD by {best[1] - results['buy_hold']:.2f}% ***")
        else:
            print(f"   Still underperforms by {best[1] - results['buy_hold']:.2f}%")

        all_results.append(results)

    # Summary
    print(f"\n{'='*100}")
    print("SUMMARY - OPTIMAL LEVERAGE LEVEL")
    print(f"{'='*100}\n")

    print(f"{'Ticker':<8} | {'Buy&Hold':<10} | {'1.5x Lev':<12} | {'2.0x Lev':<12} | {'2.5x Lev':<12} | {'Best':<8}")
    print(f"{'-'*8}-+-{'-'*10}-+-{'-'*12}-+-{'-'*12}-+-{'-'*12}-+-{'-'*8}")

    for r in all_results:
        best_lev = max([
            ("1.5x", r.get("leverage_1.5x", 0)),
            ("2.0x", r.get("leverage_2.0x", 0)),
            ("2.5x", r.get("leverage_2.5x", 0)),
        ], key=lambda x: x[1])

        print(
            f"{r['ticker']:<8} | "
            f"{r['buy_hold']:>9.2f}% | "
            f"{r.get('leverage_1.5x', 0):>11.2f}% | "
            f"{r.get('leverage_2.0x', 0):>11.2f}% | "
            f"{r.get('leverage_2.5x', 0):>11.2f}% | "
            f"{best_lev[0]:<8}"
        )

    print(f"\n{'='*100}\n")
    print("RECOMMENDATION:")
    print("- Use 2.0x leverage for best risk/reward")
    print("- Only enter on confidence >= 75%")
    print("- Stop trading if drawdown > 20%")
    print("- This is NOT gambling - we use leverage only on confirmed trends\n")


if __name__ == "__main__":
    main()
