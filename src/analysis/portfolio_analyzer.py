"""Portfolio analysis and optimization."""

from datetime import datetime, timedelta, date
from typing import Optional

from src.data.storage.market_data_db import MarketDataDB
from src.portfolio.portfolio_manager import PortfolioManager


class PortfolioAnalyzer:
    """Analyze current holdings and find optimization opportunities."""

    def __init__(self):
        """Initialize portfolio analyzer."""
        self.portfolio_manager = PortfolioManager()

    def analyze_holdings_performance(self, lookback_days: int = 30) -> list:
        """
        Analyze each holding's recent performance.

        Args:
            lookback_days: Number of days to analyze

        Returns:
            List of holdings with performance metrics
        """
        portfolio = self.portfolio_manager.load_portfolio()

        if not portfolio.positions:
            return []

        holdings_analysis = []

        with MarketDataDB() as db:
            for symbol, position in portfolio.positions.items():
                # Get price history
                start_date = datetime.now() - timedelta(days=lookback_days)

                prices = db.conn.execute(
                    """
                    SELECT timestamp, close
                    FROM stock_prices
                    WHERE symbol = ?
                    AND timestamp >= ?
                    ORDER BY timestamp
                """,
                    [symbol, start_date],
                ).fetchall()

                if not prices:
                    continue

                # Calculate performance metrics
                first_price = float(prices[0][1])
                latest_price = float(prices[-1][1])
                price_change_pct = (
                    ((latest_price - first_price) / first_price * 100)
                    if first_price > 0
                    else 0
                )

                # Get latest technical indicators
                latest_indicators = db.conn.execute(
                    """
                    SELECT rsi_14, macd, macd_histogram, sma_20, sma_50
                    FROM technical_indicators
                    WHERE symbol = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                """,
                    [symbol],
                ).fetchone()

                if latest_indicators:
                    rsi, macd, macd_hist, sma20, sma50 = latest_indicators
                else:
                    rsi = macd = macd_hist = sma20 = sma50 = None

                # Calculate SPY performance for comparison
                spy_prices = db.conn.execute(
                    """
                    SELECT close
                    FROM stock_prices
                    WHERE symbol = 'SPY'
                    AND timestamp >= ?
                    ORDER BY timestamp
                    LIMIT 1
                """,
                    [start_date],
                ).fetchone()

                spy_latest = db.conn.execute(
                    """
                    SELECT close
                    FROM stock_prices
                    WHERE symbol = 'SPY'
                    ORDER BY timestamp DESC
                    LIMIT 1
                """
                ).fetchone()

                spy_return = 0
                if spy_prices and spy_latest:
                    spy_first = float(spy_prices[0])
                    spy_last = float(spy_latest[0])
                    spy_return = (
                        ((spy_last - spy_first) / spy_first * 100) if spy_first > 0 else 0
                    )

                # Calculate alpha (excess return vs SPY)
                alpha = price_change_pct - spy_return

                # Determine trend direction
                trend = "NEUTRAL"
                if sma20 and sma50:
                    if float(sma20) > float(sma50):
                        trend = "UP"
                    else:
                        trend = "DOWN"

                # Determine signal strength
                signal_strength = self._calculate_signal_strength(
                    rsi, macd_hist, trend, price_change_pct
                )

                holdings_analysis.append(
                    {
                        "symbol": symbol,
                        "quantity": position.quantity,
                        "avg_cost": position.price_paid,  # Position uses price_paid, not avg_cost
                        "current_price": latest_price,
                        "position_value": position.quantity * latest_price,
                        "return_pct": price_change_pct,
                        "alpha": alpha,
                        "rsi": float(rsi) if rsi else None,
                        "macd": float(macd) if macd else None,
                        "macd_hist": float(macd_hist) if macd_hist else None,
                        "trend": trend,
                        "signal_strength": signal_strength,
                        "spy_return": spy_return,
                    }
                )

        return holdings_analysis

    def _calculate_signal_strength(
        self, rsi: float, macd_hist: float, trend: str, return_pct: float
    ) -> float:
        """
        Calculate overall signal strength (0-100).

        Higher = stronger buy signal
        Lower = weaker/sell signal
        """
        strength = 50  # Start neutral

        # RSI contribution (30 points)
        if rsi:
            if rsi < 30:
                strength += 15  # Oversold - good
            elif rsi > 70:
                strength -= 15  # Overbought - bad
            elif 40 <= rsi <= 60:
                strength += 5  # Neutral zone - ok

        # MACD contribution (20 points)
        if macd_hist:
            if macd_hist > 0:
                strength += 10  # Positive momentum
            else:
                strength -= 10  # Negative momentum

        # Trend contribution (20 points)
        if trend == "UP":
            strength += 10
        elif trend == "DOWN":
            strength -= 10

        # Recent performance contribution (30 points)
        if return_pct > 10:
            strength += 15  # Strong recent performance
        elif return_pct > 5:
            strength += 10
        elif return_pct > 0:
            strength += 5
        elif return_pct < -10:
            strength -= 15  # Weak recent performance
        elif return_pct < -5:
            strength -= 10
        elif return_pct < 0:
            strength -= 5

        return max(0, min(100, strength))

    def find_underperformers(
        self, min_alpha: float = -5.0, max_signal_strength: float = 40
    ) -> list:
        """
        Find holdings that are underperforming.

        Args:
            min_alpha: Minimum acceptable alpha vs SPY
            max_signal_strength: Max signal strength to be considered underperforming

        Returns:
            List of underperforming positions
        """
        holdings = self.analyze_holdings_performance()

        underperformers = []
        for holding in holdings:
            # Check if underperforming vs market
            if holding["alpha"] < min_alpha:
                holding["reason"] = (
                    f"Underperforming SPY by {abs(holding['alpha']):.1f}%"
                )
                underperformers.append(holding)
            # Check if weak technicals
            elif holding["signal_strength"] < max_signal_strength:
                holding["reason"] = (
                    f"Weak signal strength ({holding['signal_strength']:.0f}/100)"
                )
                underperformers.append(holding)

        # Sort by worst performance first
        underperformers.sort(key=lambda x: x["alpha"])

        return underperformers

    def find_better_opportunities(
        self, watchlist: list[str], min_signal_strength: float = 60
    ) -> list:
        """
        Screen for stocks with better signals than current holdings.

        Args:
            watchlist: List of symbols to screen
            min_signal_strength: Minimum signal strength to consider

        Returns:
            List of opportunities sorted by signal strength
        """
        opportunities = []

        with MarketDataDB() as db:
            for symbol in watchlist:
                # Get latest price and indicators
                latest = db.conn.execute(
                    """
                    SELECT
                        sp.close,
                        ti.rsi_14,
                        ti.macd,
                        ti.macd_histogram,
                        ti.sma_20,
                        ti.sma_50
                    FROM stock_prices sp
                    LEFT JOIN technical_indicators ti
                        ON sp.symbol = ti.symbol
                        AND sp.timestamp = ti.timestamp
                    WHERE sp.symbol = ?
                    ORDER BY sp.timestamp DESC
                    LIMIT 1
                """,
                    [symbol],
                ).fetchone()

                if not latest:
                    continue

                price, rsi, macd, macd_hist, sma20, sma50 = latest

                # Calculate trend
                trend = "NEUTRAL"
                if sma20 and sma50:
                    if float(sma20) > float(sma50):
                        trend = "UP"
                    else:
                        trend = "DOWN"

                # Get recent performance
                past_price = db.conn.execute(
                    """
                    SELECT close
                    FROM stock_prices
                    WHERE symbol = ?
                    AND timestamp <= CURRENT_TIMESTAMP - INTERVAL '30 days'
                    ORDER BY timestamp DESC
                    LIMIT 1
                """,
                    [symbol],
                ).fetchone()

                return_pct = 0
                if past_price:
                    old_price = float(past_price[0])
                    return_pct = (
                        ((float(price) - old_price) / old_price * 100)
                        if old_price > 0
                        else 0
                    )

                # Calculate signal strength
                signal_strength = self._calculate_signal_strength(
                    rsi, macd_hist, trend, return_pct
                )

                if signal_strength >= min_signal_strength:
                    opportunities.append(
                        {
                            "symbol": symbol,
                            "price": float(price),
                            "signal_strength": signal_strength,
                            "rsi": float(rsi) if rsi else None,
                            "macd_hist": float(macd_hist) if macd_hist else None,
                            "trend": trend,
                            "return_30d": return_pct,
                        }
                    )

        # Sort by signal strength
        opportunities.sort(key=lambda x: x["signal_strength"], reverse=True)

        return opportunities

    def generate_swap_recommendations(
        self, watchlist: list[str], max_recommendations: int = 5
    ) -> list:
        """
        Generate specific swap recommendations.

        Args:
            watchlist: List of symbols to consider as alternatives
            max_recommendations: Maximum number of recommendations

        Returns:
            List of swap recommendations
        """
        underperformers = self.find_underperformers()
        opportunities = self.find_better_opportunities(watchlist)

        recommendations = []

        for underperformer in underperformers[:max_recommendations]:
            # Find best alternative
            for opportunity in opportunities:
                # Don't recommend swapping into same symbol
                if opportunity["symbol"] == underperformer["symbol"]:
                    continue

                # Calculate expected improvement
                strength_diff = (
                    opportunity["signal_strength"] - underperformer["signal_strength"]
                )

                if strength_diff > 10:  # At least 10 points better
                    # Determine risk level
                    if opportunity["rsi"] and opportunity["rsi"] > 70:
                        risk_level = "HIGH"
                    elif opportunity["rsi"] and opportunity["rsi"] < 30:
                        risk_level = "MEDIUM"
                    else:
                        risk_level = "LOW"

                    recommendations.append(
                        {
                            "reduce_symbol": underperformer["symbol"],
                            "reduce_quantity": underperformer["quantity"],
                            "reduce_value": underperformer["position_value"],
                            "reduce_reason": underperformer["reason"],
                            "reduce_strength": underperformer["signal_strength"],
                            "increase_symbol": opportunity["symbol"],
                            "increase_price": opportunity["price"],
                            "increase_reason": f"Strong signal ({opportunity['signal_strength']:.0f}/100), {opportunity['trend']} trend",
                            "increase_strength": opportunity["signal_strength"],
                            "expected_gain": strength_diff,
                            "risk_level": risk_level,
                            "use_margin": False,  # Default conservative
                        }
                    )
                    break

        return recommendations[:max_recommendations]

    def find_rebalancing_opportunities(self, watchlist: list[str] = None) -> list:
        """
        Find rebalancing opportunities by comparing holdings with better alternatives.

        Args:
            watchlist: Optional list of symbols to consider. If None, uses common watchlist.

        Returns:
            List of rebalancing recommendations
        """
        # Default watchlist if not provided
        if watchlist is None:
            watchlist = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
                        "SPY", "QQQ", "DIA", "IWM", "XLF", "XLE", "XLK"]

        # Get swap recommendations
        recommendations = self.generate_swap_recommendations(watchlist, max_recommendations=3)

        return recommendations

    def get_portfolio_health_score(self) -> dict:
        """
        Calculate overall portfolio health metrics.

        Returns:
            Dict with health score and metrics
        """
        holdings = self.analyze_holdings_performance()

        if not holdings:
            return {"score": 0, "grade": "N/A", "issues": ["No positions"]}

        # Calculate metrics
        avg_alpha = sum(h["alpha"] for h in holdings) / len(holdings)
        avg_signal_strength = sum(h["signal_strength"] for h in holdings) / len(holdings)
        num_underperformers = sum(1 for h in holdings if h["alpha"] < 0)

        # Calculate score (0-100)
        score = 50  # Base score

        # Alpha contribution (30 points)
        if avg_alpha > 5:
            score += 20
        elif avg_alpha > 0:
            score += 10
        elif avg_alpha > -5:
            score += 0
        else:
            score -= 10

        # Signal strength contribution (40 points)
        if avg_signal_strength > 70:
            score += 30
        elif avg_signal_strength > 60:
            score += 20
        elif avg_signal_strength > 50:
            score += 10
        else:
            score -= 10

        # Diversification contribution (30 points)
        underperformer_pct = num_underperformers / len(holdings) * 100
        if underperformer_pct < 20:
            score += 20
        elif underperformer_pct < 40:
            score += 10
        elif underperformer_pct < 60:
            score += 0
        else:
            score -= 10

        score = max(0, min(100, score))

        # Determine grade
        if score >= 90:
            grade = "A"
        elif score >= 80:
            grade = "B"
        elif score >= 70:
            grade = "C"
        elif score >= 60:
            grade = "D"
        else:
            grade = "F"

        # Identify issues
        issues = []
        if avg_alpha < 0:
            issues.append(f"Portfolio underperforming SPY ({avg_alpha:.1f}% alpha)")
        if avg_signal_strength < 60:
            issues.append(
                f"Weak average signals ({avg_signal_strength:.0f}/100)"
            )
        if underperformer_pct > 50:
            issues.append(
                f"{num_underperformers}/{len(holdings)} positions underperforming"
            )

        return {
            "score": score,
            "grade": grade,
            "avg_alpha": avg_alpha,
            "avg_signal_strength": avg_signal_strength,
            "num_positions": len(holdings),
            "num_underperformers": num_underperformers,
            "issues": issues,
        }
