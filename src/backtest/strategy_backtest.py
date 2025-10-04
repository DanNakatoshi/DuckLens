"""Backtesting engine for portfolio rebalancing strategy."""

from datetime import datetime, timedelta, date
from typing import Optional
import pandas as pd

from src.data.storage.market_data_db import MarketDataDB
from src.analysis.portfolio_analyzer import PortfolioAnalyzer
from src.allocation.position_sizer import PositionSizer


class StrategyBacktest:
    """Backtest portfolio optimization and rebalancing strategy."""

    def __init__(self, initial_capital: float = 30000.0):
        """
        Initialize backtest engine.

        Args:
            initial_capital: Starting capital
        """
        self.initial_capital = initial_capital
        self.db = MarketDataDB()

    def run_backtest(
        self,
        start_date: date,
        end_date: date,
        watchlist: list[str],
        rebalance_frequency_days: int = 30,
        max_positions: int = 5,
        use_margin: bool = False,
        margin_limit_pct: float = 25.0,
    ) -> dict:
        """
        Run backtest with rebalancing strategy.

        Args:
            start_date: Start date for backtest
            end_date: End date for backtest
            watchlist: List of symbols to trade
            rebalance_frequency_days: How often to check for rebalancing (days)
            max_positions: Maximum number of positions
            use_margin: Whether to use margin
            margin_limit_pct: Max margin as % of total portfolio

        Returns:
            Dict with backtest results
        """
        # Initialize portfolio
        cash = self.initial_capital
        positions = {}  # symbol -> {quantity, avg_cost, entry_date}
        portfolio_value_history = []
        trades = []
        rebalance_dates = []

        current_date = start_date

        while current_date <= end_date:
            # Calculate current portfolio value
            portfolio_value = cash

            for symbol, pos in list(positions.items()):
                # Get price for this date
                price = self._get_price(symbol, current_date)

                if price is None:
                    # Symbol delisted or no data - close position
                    cash += pos["quantity"] * pos.get("last_price", pos["avg_cost"])
                    del positions[symbol]
                    continue

                # Update position value
                positions[symbol]["last_price"] = price
                portfolio_value += pos["quantity"] * price

            # Record portfolio value
            portfolio_value_history.append(
                {"date": current_date, "value": portfolio_value, "cash": cash}
            )

            # Check if rebalancing day
            days_since_last_rebalance = (
                (current_date - rebalance_dates[-1]).days
                if rebalance_dates
                else rebalance_frequency_days + 1
            )

            if days_since_last_rebalance >= rebalance_frequency_days:
                # Rebalance portfolio
                rebalance_dates.append(current_date)

                # Find opportunities
                opportunities = self._find_opportunities(
                    watchlist, current_date, list(positions.keys())
                )

                # Find underperformers
                underperformers = self._find_underperformers(
                    positions, current_date
                )

                # Execute rebalancing
                if opportunities and underperformers:
                    # Sell worst performer
                    worst = underperformers[0]
                    symbol = worst["symbol"]
                    pos = positions[symbol]
                    sell_price = self._get_price(symbol, current_date)

                    if sell_price:
                        proceeds = pos["quantity"] * sell_price
                        cash += proceeds

                        trades.append(
                            {
                                "date": current_date,
                                "symbol": symbol,
                                "action": "SELL",
                                "quantity": pos["quantity"],
                                "price": sell_price,
                                "value": proceeds,
                                "reason": worst.get("reason", "Rebalancing"),
                            }
                        )

                        del positions[symbol]

                    # Buy best opportunity
                    best = opportunities[0]
                    symbol = best["symbol"]
                    buy_price = best["price"]

                    # Calculate position size
                    margin_available = cash * 2 if use_margin else 0
                    margin_used = sum(
                        pos.get("margin_used", 0) for pos in positions.values()
                    )

                    sizer = PositionSizer(
                        portfolio_value, cash, margin_available, margin_used
                    )

                    position_calc = sizer.calculate_position_size(
                        signal_strength=best.get("signal_strength", 60),
                        risk_level="MEDIUM",
                        price=buy_price,
                        use_margin=use_margin,
                    )

                    if position_calc["quantity"] > 0:
                        quantity = position_calc["quantity"]
                        cost = quantity * buy_price

                        # Check if we have enough cash
                        if cost <= cash + position_calc.get("margin_needed", 0):
                            positions[symbol] = {
                                "quantity": quantity,
                                "avg_cost": buy_price,
                                "entry_date": current_date,
                                "last_price": buy_price,
                                "margin_used": position_calc.get("margin_needed", 0),
                            }

                            cash -= cost - position_calc.get("margin_needed", 0)

                            trades.append(
                                {
                                    "date": current_date,
                                    "symbol": symbol,
                                    "action": "BUY",
                                    "quantity": quantity,
                                    "price": buy_price,
                                    "value": cost,
                                    "reason": best.get("reason", "New opportunity"),
                                }
                            )

            # Move to next day
            current_date += timedelta(days=1)

        # Calculate final results
        final_value = portfolio_value_history[-1]["value"] if portfolio_value_history else self.initial_capital

        # Calculate returns
        total_return = ((final_value - self.initial_capital) / self.initial_capital) * 100

        # Calculate SPY benchmark return
        spy_start = self._get_price("SPY", start_date)
        spy_end = self._get_price("SPY", end_date)
        spy_return = (
            ((spy_end - spy_start) / spy_start * 100) if spy_start and spy_end else 0
        )

        # Calculate alpha
        alpha = total_return - spy_return

        # Calculate max drawdown
        max_dd = self._calculate_max_drawdown(portfolio_value_history)

        # Calculate Sharpe ratio
        sharpe = self._calculate_sharpe_ratio(portfolio_value_history)

        # Win rate
        winning_trades = [
            t for t in trades
            if t["action"] == "SELL" and self._is_winning_trade(t, trades)
        ]
        win_rate = (
            (len(winning_trades) / len([t for t in trades if t["action"] == "SELL"]) * 100)
            if trades
            else 0
        )

        return {
            "initial_capital": self.initial_capital,
            "final_value": final_value,
            "total_return_pct": total_return,
            "spy_return_pct": spy_return,
            "alpha": alpha,
            "max_drawdown_pct": max_dd,
            "sharpe_ratio": sharpe,
            "total_trades": len(trades),
            "win_rate_pct": win_rate,
            "avg_holding_days": self._calculate_avg_holding_days(trades),
            "rebalance_count": len(rebalance_dates),
            "portfolio_history": portfolio_value_history,
            "trades": trades,
        }

    def _get_price(self, symbol: str, date: date) -> Optional[float]:
        """Get closing price for a symbol on a specific date."""
        result = self.db.conn.execute(
            """
            SELECT close FROM stock_prices
            WHERE symbol = ? AND DATE(timestamp) = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """,
            [symbol, date],
        ).fetchone()

        return float(result[0]) if result else None

    def _find_opportunities(
        self, watchlist: list[str], date: date, exclude_symbols: list[str]
    ) -> list:
        """Find best opportunities on a given date."""
        opportunities = []

        for symbol in watchlist:
            if symbol in exclude_symbols:
                continue

            price = self._get_price(symbol, date)
            if not price:
                continue

            # Get technical indicators
            indicators = self.db.conn.execute(
                """
                SELECT rsi_14, macd_histogram, sma_20, sma_50
                FROM technical_indicators
                WHERE symbol = ? AND DATE(timestamp) = ?
                LIMIT 1
            """,
                [symbol, date],
            ).fetchone()

            if not indicators:
                continue

            rsi, macd_hist, sma20, sma50 = indicators

            # Calculate simple signal strength
            strength = 50

            if rsi:
                if 40 <= float(rsi) <= 60:
                    strength += 10
                elif float(rsi) < 30:
                    strength += 15

            if macd_hist and float(macd_hist) > 0:
                strength += 15

            if sma20 and sma50 and float(sma20) > float(sma50):
                strength += 15

            if strength >= 60:
                opportunities.append(
                    {"symbol": symbol, "price": price, "signal_strength": strength}
                )

        # Sort by signal strength
        opportunities.sort(key=lambda x: x["signal_strength"], reverse=True)

        return opportunities

    def _find_underperformers(self, positions: dict, date: date) -> list:
        """Find underperforming positions."""
        underperformers = []

        for symbol, pos in positions.items():
            current_price = self._get_price(symbol, date)
            if not current_price:
                continue

            # Calculate return since entry
            entry_price = pos["avg_cost"]
            return_pct = ((current_price - entry_price) / entry_price) * 100

            # Get indicators
            indicators = self.db.conn.execute(
                """
                SELECT rsi_14, macd_histogram
                FROM technical_indicators
                WHERE symbol = ? AND DATE(timestamp) = ?
                LIMIT 1
            """,
                [symbol, date],
            ).fetchone()

            if not indicators:
                continue

            rsi, macd_hist = indicators

            # Check if underperforming
            is_underperforming = False
            reason = ""

            if return_pct < -5:
                is_underperforming = True
                reason = f"Loss: {return_pct:.1f}%"
            elif rsi and float(rsi) > 70:
                is_underperforming = True
                reason = f"Overbought (RSI: {rsi:.0f})"
            elif macd_hist and float(macd_hist) < -0.5:
                is_underperforming = True
                reason = "Negative momentum"

            if is_underperforming:
                underperformers.append(
                    {"symbol": symbol, "return_pct": return_pct, "reason": reason}
                )

        # Sort by worst performance
        underperformers.sort(key=lambda x: x["return_pct"])

        return underperformers

    def _calculate_max_drawdown(self, history: list) -> float:
        """Calculate maximum drawdown from peak."""
        if not history:
            return 0

        peak = history[0]["value"]
        max_dd = 0

        for record in history:
            value = record["value"]
            if value > peak:
                peak = value
            dd = ((peak - value) / peak) * 100
            if dd > max_dd:
                max_dd = dd

        return max_dd

    def _calculate_sharpe_ratio(self, history: list) -> float:
        """Calculate Sharpe ratio (simplified)."""
        if len(history) < 2:
            return 0

        # Calculate daily returns
        returns = []
        for i in range(1, len(history)):
            prev_val = history[i - 1]["value"]
            curr_val = history[i]["value"]
            ret = ((curr_val - prev_val) / prev_val) if prev_val > 0 else 0
            returns.append(ret)

        if not returns:
            return 0

        # Sharpe = mean(returns) / std(returns) * sqrt(252)
        import numpy as np

        mean_return = np.mean(returns)
        std_return = np.std(returns)

        if std_return == 0:
            return 0

        sharpe = (mean_return / std_return) * np.sqrt(252)

        return sharpe

    def _calculate_avg_holding_days(self, trades: list) -> float:
        """Calculate average holding period in days."""
        holding_periods = []

        # Match buy/sell pairs
        buys = {t["symbol"]: t for t in trades if t["action"] == "BUY"}
        sells = [t for t in trades if t["action"] == "SELL"]

        for sell in sells:
            symbol = sell["symbol"]
            if symbol in buys:
                buy = buys[symbol]
                days = (sell["date"] - buy["date"]).days
                holding_periods.append(days)

        return sum(holding_periods) / len(holding_periods) if holding_periods else 0

    def _is_winning_trade(self, sell_trade: dict, all_trades: list) -> bool:
        """Check if a sell trade was profitable."""
        symbol = sell_trade["symbol"]
        sell_price = sell_trade["price"]

        # Find corresponding buy
        for trade in all_trades:
            if (
                trade["action"] == "BUY"
                and trade["symbol"] == symbol
                and trade["date"] < sell_trade["date"]
            ):
                buy_price = trade["price"]
                return sell_price > buy_price

        return False

    def compare_strategies(
        self, start_date: date, end_date: date, watchlist: list[str]
    ) -> dict:
        """
        Compare different rebalancing strategies.

        Returns:
            Dict with comparison results
        """
        # Strategy 1: Buy and hold (no rebalancing)
        buy_hold = self.run_backtest(
            start_date, end_date, watchlist, rebalance_frequency_days=9999, max_positions=5
        )

        # Strategy 2: Monthly rebalancing, no margin
        monthly_no_margin = self.run_backtest(
            start_date, end_date, watchlist, rebalance_frequency_days=30, use_margin=False
        )

        # Strategy 3: Weekly rebalancing, no margin
        weekly_no_margin = self.run_backtest(
            start_date, end_date, watchlist, rebalance_frequency_days=7, use_margin=False
        )

        # Strategy 4: Monthly rebalancing, with margin
        monthly_with_margin = self.run_backtest(
            start_date, end_date, watchlist, rebalance_frequency_days=30, use_margin=True
        )

        return {
            "buy_and_hold": buy_hold,
            "monthly_no_margin": monthly_no_margin,
            "weekly_no_margin": weekly_no_margin,
            "monthly_with_margin": monthly_with_margin,
        }
