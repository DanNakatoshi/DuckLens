"""Market regime detection - Bull, Bear, Volatile, or Neutral."""

from datetime import datetime
from enum import Enum

from src.data.storage.market_data_db import MarketDataDB


class MarketRegime(Enum):
    """Market regime classification."""

    BULL = "BULL"  # SPY > 200 SMA, VIX < 20
    BEAR = "BEAR"  # SPY < 200 SMA, VIX > 30
    VOLATILE = "VOLATILE"  # VIX > 25
    NEUTRAL = "NEUTRAL"  # Everything else


class RegimeDetector:
    """Detect current market regime for strategy adjustment."""

    def __init__(self, db: MarketDataDB):
        """Initialize regime detector."""
        self.db = db

    def detect_regime(self, date: datetime | None = None) -> dict:
        """
        Detect current market regime.

        Args:
            date: Date to check (None = latest)

        Returns:
            {
                "regime": MarketRegime,
                "spy_price": float,
                "spy_sma_200": float,
                "vix": float,
                "confidence_threshold": float,
                "max_leverage": float,
                "reasoning": str
            }
        """
        if date is None:
            date = datetime.now()

        # Get SPY price and 200 SMA
        spy_data = self._get_spy_data(date)
        if not spy_data:
            return self._default_regime()

        spy_price = spy_data["price"]
        spy_sma_200 = spy_data["sma_200"]

        # Get VIX level
        vix = self._get_vix(date)
        if vix is None:
            vix = 20.0  # Default to moderate level

        # Classify regime
        regime, reasoning = self._classify_regime(spy_price, spy_sma_200, vix)

        # Get strategy parameters for this regime
        params = self._get_regime_parameters(regime, vix)

        return {
            "regime": regime,
            "spy_price": spy_price,
            "spy_sma_200": spy_sma_200,
            "vix": vix,
            "confidence_threshold": params["min_confidence"],
            "max_leverage": params["max_leverage"],
            "position_sizing": params["position_sizing"],
            "reasoning": reasoning,
        }

    def _get_spy_data(self, date: datetime) -> dict | None:
        """Get SPY price and 200-day SMA."""
        query = """
            SELECT
                sp.close as price,
                ti.sma_200
            FROM stock_prices sp
            LEFT JOIN technical_indicators ti
                ON sp.symbol = ti.symbol
                AND sp.timestamp::DATE = ti.timestamp::DATE
            WHERE sp.symbol = 'SPY'
                AND sp.timestamp::DATE <= ?
            ORDER BY sp.timestamp DESC
            LIMIT 1
        """

        result = self.db.conn.execute(query, [date]).fetchone()

        if not result or result[1] is None:
            return None

        return {"price": float(result[0]), "sma_200": float(result[1])}

    def _get_vix(self, date: datetime) -> float | None:
        """Get VIX level (volatility index)."""
        query = """
            SELECT close
            FROM stock_prices
            WHERE symbol = 'VIX'
                AND timestamp::DATE <= ?
            ORDER BY timestamp DESC
            LIMIT 1
        """

        result = self.db.conn.execute(query, [date]).fetchone()

        if not result:
            return None

        return float(result[0])

    def _classify_regime(
        self, spy_price: float, spy_sma_200: float, vix: float
    ) -> tuple[MarketRegime, str]:
        """
        Classify market regime based on indicators.

        Rules:
            - BULL: SPY > 200 SMA AND VIX < 20
            - BEAR: SPY < 200 SMA AND VIX > 30
            - VOLATILE: VIX > 25 (regardless of SPY)
            - NEUTRAL: Everything else
        """
        above_200 = spy_price > spy_sma_200
        pct_from_200 = ((spy_price - spy_sma_200) / spy_sma_200) * 100

        # Check for volatile regime first
        if vix > 25:
            if above_200:
                regime = MarketRegime.VOLATILE
                reasoning = (
                    f"VOLATILE market: High VIX ({vix:.1f}), "
                    f"SPY {pct_from_200:+.1f}% from 200 SMA"
                )
            else:
                # High VIX + below 200 SMA = bear market
                regime = MarketRegime.BEAR
                reasoning = (
                    f"BEAR market: SPY below 200 SMA ({pct_from_200:.1f}%), "
                    f"High VIX ({vix:.1f})"
                )
        elif above_200 and vix < 20:
            # Low VIX + above 200 SMA = bull market
            regime = MarketRegime.BULL
            reasoning = (
                f"BULL market: SPY {pct_from_200:+.1f}% above 200 SMA, "
                f"Low VIX ({vix:.1f})"
            )
        elif not above_200 and vix > 30:
            # Below 200 SMA + high VIX = bear market
            regime = MarketRegime.BEAR
            reasoning = (
                f"BEAR market: SPY {pct_from_200:.1f}% below 200 SMA, "
                f"Elevated VIX ({vix:.1f})"
            )
        else:
            # Mixed signals = neutral
            regime = MarketRegime.NEUTRAL
            reasoning = (
                f"NEUTRAL market: SPY {pct_from_200:+.1f}% from 200 SMA, "
                f"VIX {vix:.1f}"
            )

        return regime, reasoning

    def _get_regime_parameters(self, regime: MarketRegime, vix: float) -> dict:
        """
        Get strategy parameters based on market regime.

        Returns:
            {
                "min_confidence": float,  # Minimum confidence to trade
                "max_leverage": float,    # Maximum leverage to use
                "position_sizing": str    # Position sizing guidance
            }
        """
        if regime == MarketRegime.BULL:
            return {
                "min_confidence": 0.70,  # More aggressive
                "max_leverage": 2.0,  # Full leverage allowed
                "position_sizing": "30-40% per position (2x leverage on 75%+ confidence)",
            }
        elif regime == MarketRegime.BEAR:
            return {
                "min_confidence": 0.85,  # Very selective
                "max_leverage": 1.0,  # No leverage in bear markets
                "position_sizing": "10-15% per position (cash preservation mode)",
            }
        elif regime == MarketRegime.VOLATILE:
            # Adjust based on VIX level
            if vix > 35:
                # Extreme volatility
                return {
                    "min_confidence": 0.85,
                    "max_leverage": 1.0,
                    "position_sizing": "5-10% per position (extreme caution)",
                }
            else:
                # Moderate volatility
                return {
                    "min_confidence": 0.80,
                    "max_leverage": 1.5,
                    "position_sizing": "15-20% per position (reduced risk)",
                }
        else:  # NEUTRAL
            return {
                "min_confidence": 0.75,  # Standard threshold
                "max_leverage": 1.5,  # Moderate leverage
                "position_sizing": "20-25% per position (standard risk)",
            }

    def _default_regime(self) -> dict:
        """Return default regime when data is unavailable."""
        return {
            "regime": MarketRegime.NEUTRAL,
            "spy_price": 0.0,
            "spy_sma_200": 0.0,
            "vix": 20.0,
            "confidence_threshold": 0.75,
            "max_leverage": 1.5,
            "position_sizing": "20-25% per position",
            "reasoning": "Unable to determine regime - using conservative defaults",
        }

    def get_regime_color(self, regime: MarketRegime) -> str:
        """Get color for regime display (for rich console output)."""
        colors = {
            MarketRegime.BULL: "green",
            MarketRegime.BEAR: "red",
            MarketRegime.VOLATILE: "yellow",
            MarketRegime.NEUTRAL: "blue",
        }
        return colors.get(regime, "white")

    def should_avoid_new_positions(self, regime: MarketRegime, vix: float) -> bool:
        """
        Determine if we should avoid opening new positions.

        Returns:
            True: Sit on sidelines (extreme conditions)
            False: OK to trade with caution
        """
        if regime == MarketRegime.BEAR:
            return True  # Avoid new longs in bear markets

        if regime == MarketRegime.VOLATILE and vix > 35:
            return True  # Extreme volatility - stay out

        return False
