"""Relative Strength analysis - Compare stock performance vs market (SPY/QQQ)."""

from datetime import datetime, timedelta

from src.data.storage.market_data_db import MarketDataDB


class RelativeStrengthAnalyzer:
    """Analyze stock performance relative to market indices."""

    def __init__(self, db: MarketDataDB):
        """Initialize analyzer."""
        self.db = db

    def calculate_relative_strength(
        self,
        ticker: str,
        benchmark: str = "SPY",
        days: int = 60,
        date: datetime | None = None,
    ) -> dict:
        """
        Calculate relative strength ratio comparing stock vs benchmark.

        Args:
            ticker: Stock ticker
            benchmark: Benchmark ticker (default: SPY)
            days: Lookback period (default: 60 days)
            date: End date (None = latest)

        Returns:
            {
                "rs_ratio": float,  # > 1.0 = outperforming, < 1.0 = underperforming
                "ticker_return": float,  # Stock return %
                "benchmark_return": float,  # Benchmark return %
                "strength": str,  # "VERY_STRONG", "STRONG", "NEUTRAL", "WEAK", "VERY_WEAK"
                "confidence_adjustment": float,  # -0.20 to +0.20
                "reasoning": str
            }
        """
        if date is None:
            date = datetime.now()

        start_date = date - timedelta(days=days)

        # Get stock returns
        ticker_data = self._get_price_data(ticker, start_date, date)
        if not ticker_data:
            return self._default_rs()

        ticker_return = self._calculate_return(
            ticker_data["start_price"], ticker_data["end_price"]
        )

        # Get benchmark returns
        benchmark_data = self._get_price_data(benchmark, start_date, date)
        if not benchmark_data:
            return self._default_rs()

        benchmark_return = self._calculate_return(
            benchmark_data["start_price"], benchmark_data["end_price"]
        )

        # Calculate relative strength ratio
        # RS = (1 + stock_return) / (1 + benchmark_return)
        rs_ratio = (1 + ticker_return) / (1 + benchmark_return)

        # Classify strength
        strength, confidence_adj, reasoning = self._classify_strength(
            rs_ratio, ticker_return, benchmark_return, ticker, benchmark
        )

        return {
            "rs_ratio": rs_ratio,
            "ticker_return": ticker_return,
            "benchmark_return": benchmark_return,
            "strength": strength,
            "confidence_adjustment": confidence_adj,
            "reasoning": reasoning,
        }

    def _get_price_data(
        self, ticker: str, start_date: datetime, end_date: datetime
    ) -> dict | None:
        """Get start and end prices for a ticker."""
        query = """
            SELECT close, timestamp
            FROM stock_prices
            WHERE symbol = ?
                AND timestamp >= ?
                AND timestamp <= ?
            ORDER BY timestamp ASC
        """

        results = self.db.conn.execute(
            query, [ticker, start_date, end_date]
        ).fetchall()

        if not results or len(results) < 2:
            return None

        start_price = float(results[0][0])
        end_price = float(results[-1][0])

        return {"start_price": start_price, "end_price": end_price}

    def _calculate_return(self, start_price: float, end_price: float) -> float:
        """Calculate percentage return."""
        if start_price <= 0:
            return 0.0
        return (end_price - start_price) / start_price

    def _classify_strength(
        self,
        rs_ratio: float,
        ticker_return: float,
        benchmark_return: float,
        ticker: str,
        benchmark: str,
    ) -> tuple[str, float, str]:
        """
        Classify relative strength and determine confidence adjustment.

        Strength Levels:
            VERY_STRONG: RS > 1.5 (50%+ outperformance)
            STRONG: RS 1.2-1.5 (20-50% outperformance)
            NEUTRAL: RS 0.9-1.2 (-10% to +20%)
            WEAK: RS 0.7-0.9 (-30% to -10% underperformance)
            VERY_WEAK: RS < 0.7 (>30% underperformance)

        Confidence Adjustments:
            VERY_STRONG: +20%
            STRONG: +15%
            NEUTRAL: 0%
            WEAK: -10%
            VERY_WEAK: -20%
        """
        if rs_ratio >= 1.5:
            # Massive outperformance
            strength = "VERY_STRONG"
            confidence_adj = +0.20
            reasoning = (
                f"{ticker} up {ticker_return:+.1%} vs {benchmark} {benchmark_return:+.1%}. "
                f"RS ratio {rs_ratio:.2f}x - Exceptional strength!"
            )

        elif rs_ratio >= 1.2:
            # Strong outperformance
            strength = "STRONG"
            confidence_adj = +0.15
            reasoning = (
                f"{ticker} up {ticker_return:+.1%} vs {benchmark} {benchmark_return:+.1%}. "
                f"RS ratio {rs_ratio:.2f}x - Strong outperformer"
            )

        elif rs_ratio >= 1.1:
            # Modest outperformance
            strength = "ABOVE_AVERAGE"
            confidence_adj = +0.05
            reasoning = (
                f"{ticker} up {ticker_return:+.1%} vs {benchmark} {benchmark_return:+.1%}. "
                f"RS ratio {rs_ratio:.2f}x - Above average"
            )

        elif rs_ratio >= 0.9:
            # In-line with market
            strength = "NEUTRAL"
            confidence_adj = 0.0
            reasoning = (
                f"{ticker} {ticker_return:+.1%} vs {benchmark} {benchmark_return:+.1%}. "
                f"RS ratio {rs_ratio:.2f}x - Market perform"
            )

        elif rs_ratio >= 0.7:
            # Underperforming
            strength = "WEAK"
            confidence_adj = -0.10
            reasoning = (
                f"{ticker} {ticker_return:+.1%} vs {benchmark} {benchmark_return:+.1%}. "
                f"RS ratio {rs_ratio:.2f}x - Underperformer"
            )

        else:
            # Massive underperformance
            strength = "VERY_WEAK"
            confidence_adj = -0.20
            reasoning = (
                f"{ticker} {ticker_return:+.1%} vs {benchmark} {benchmark_return:+.1%}. "
                f"RS ratio {rs_ratio:.2f}x - Severe underperformance"
            )

        return strength, confidence_adj, reasoning

    def _default_rs(self) -> dict:
        """Return default RS when data unavailable."""
        return {
            "rs_ratio": 1.0,
            "ticker_return": 0.0,
            "benchmark_return": 0.0,
            "strength": "NEUTRAL",
            "confidence_adjustment": 0.0,
            "reasoning": "Insufficient data for RS calculation",
        }

    def get_strength_color(self, strength: str) -> str:
        """Get color for strength display (for rich console)."""
        colors = {
            "VERY_STRONG": "bold green",
            "STRONG": "green",
            "ABOVE_AVERAGE": "cyan",
            "NEUTRAL": "yellow",
            "WEAK": "orange",
            "VERY_WEAK": "red",
        }
        return colors.get(strength, "white")

    def should_trade(self, rs_ratio: float, strength: str) -> bool:
        """
        Determine if stock is worth trading based on RS.

        Rules:
            - VERY_WEAK (RS < 0.7): Avoid - losing to market badly
            - WEAK (RS < 0.9): Caution - lagging market
            - NEUTRAL (RS 0.9-1.2): OK to trade if other signals strong
            - STRONG (RS > 1.2): Preferred - beating market
            - VERY_STRONG (RS > 1.5): Top priority - exceptional strength

        Returns:
            True if OK to trade, False if should avoid
        """
        # Avoid stocks that are severely underperforming
        if strength in ["VERY_WEAK", "WEAK"]:
            return False

        return True

    def compare_multiple_stocks(
        self, tickers: list[str], benchmark: str = "SPY", days: int = 60
    ) -> list[dict]:
        """
        Compare multiple stocks and rank by relative strength.

        Args:
            tickers: List of stock tickers
            benchmark: Benchmark ticker
            days: Lookback period

        Returns:
            List of dicts sorted by RS ratio (highest first)
        """
        results = []

        for ticker in tickers:
            rs_data = self.calculate_relative_strength(ticker, benchmark, days)
            rs_data["ticker"] = ticker
            results.append(rs_data)

        # Sort by RS ratio (highest first)
        results.sort(key=lambda x: x["rs_ratio"], reverse=True)

        return results

    def get_sector_relative_strength(self, sector_etf: str) -> dict:
        """
        Get sector strength vs SPY.

        Common sector ETFs:
            XLK - Technology
            XLF - Financials
            XLE - Energy
            XLV - Healthcare
            XLI - Industrials
            XLP - Consumer Staples
            XLY - Consumer Discretionary
            XLU - Utilities
            XLB - Materials
            XLRE - Real Estate
            XLC - Communications

        Returns:
            RS analysis for the sector
        """
        return self.calculate_relative_strength(
            ticker=sector_etf, benchmark="SPY", days=60
        )
