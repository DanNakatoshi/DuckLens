"""Enhanced trend detector with earnings calendar and volume spike filters."""

from datetime import datetime
from typing import Optional

from src.data.collectors.earnings_calendar import SimpleEarningsCalendar
from src.data.storage.market_data_db import MarketDataDB
from src.models.trade_journal import TradeJournal, TradeLog
from src.models.trend_detector import TrendDetector, TradingSignal, TrendSignal


class EnhancedTrendDetector(TrendDetector):
    """
    Enhanced trend detector with:
    1. Earnings calendar filter (avoid trading near earnings)
    2. Volume spike detector (reduce confidence on unusual activity)
    3. Trade logging (track every signal for analysis)
    """

    def __init__(
        self,
        db: MarketDataDB,
        min_confidence: float = 0.6,
        block_high_impact_events: bool = True,
        min_adx: float = 25.0,
        confirmation_days: int = 2,
        long_only: bool = False,
        log_trades: bool = True,
        block_earnings_window: int = 3,  # Days before earnings to avoid trading
        volume_spike_threshold: float = 3.0,  # 3x average volume = spike
    ):
        super().__init__(
            db=db,
            min_confidence=min_confidence,
            block_high_impact_events=block_high_impact_events,
            min_adx=min_adx,
            confirmation_days=confirmation_days,
            long_only=long_only,
        )

        self.log_trades = log_trades
        self.trade_journal = TradeJournal() if log_trades else None
        self.earnings_calendar = SimpleEarningsCalendar()
        self.block_earnings_window = block_earnings_window
        self.volume_spike_threshold = volume_spike_threshold

    def generate_signal(
        self, ticker: str, date: datetime | str, price: float
    ) -> TrendSignal:
        """
        Generate trading signal with earnings and volume filters.

        Enhancements:
        1. Block trades within N days of earnings
        2. Reduce confidence on volume spikes (unusual activity)
        3. Log all signals to trade journal
        """
        # Get base signal from parent
        signal = super().generate_signal(ticker, date, price)

        # Convert date to datetime if string
        if isinstance(date, str):
            date = datetime.fromisoformat(date)

        # Check earnings calendar
        days_until_earnings = self.earnings_calendar.days_until_next_earnings(
            ticker, date
        )

        if days_until_earnings and days_until_earnings <= self.block_earnings_window:
            # Block trading near earnings
            if signal.signal == TradingSignal.BUY:
                signal.signal = TradingSignal.DONT_TRADE
                signal.confidence = 0.0
                signal.reasoning = (
                    f"[EARNINGS SOON] {days_until_earnings} days until earnings - "
                    f"avoiding entry\n{signal.reasoning}"
                )
                signal.blocked_by_event = True

        # Check volume spike
        volume_data = self._get_volume_data(ticker, date)
        if volume_data:
            current_volume = volume_data["current_volume"]
            avg_volume = volume_data["avg_volume"]

            if current_volume > avg_volume * self.volume_spike_threshold:
                # Volume spike detected - reduce confidence
                volume_ratio = current_volume / avg_volume
                confidence_penalty = min(0.3, (volume_ratio - self.volume_spike_threshold) * 0.1)

                original_confidence = signal.confidence
                signal.confidence = max(0.0, signal.confidence - confidence_penalty)

                signal.reasoning = (
                    f"[VOLUME SPIKE] Volume {volume_ratio:.1f}x average - "
                    f"confidence reduced from {original_confidence:.0%} to {signal.confidence:.0%}\n"
                    f"{signal.reasoning}"
                )

        # Log trade if enabled
        if self.log_trades and signal.signal in [TradingSignal.BUY, TradingSignal.SELL]:
            self._log_trade_signal(
                ticker=ticker,
                signal=signal,
                price=price,
                date=date,
                days_until_earnings=days_until_earnings,
                volume_data=volume_data,
            )

        return signal

    def _get_volume_data(self, ticker: str, date: datetime) -> Optional[dict]:
        """Get volume and average volume for spike detection."""
        query = """
            SELECT
                sp.volume as current_volume,
                AVG(sp.volume) OVER (
                    ORDER BY sp.timestamp
                    ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
                ) as avg_volume
            FROM stock_prices sp
            WHERE sp.symbol = ?
            AND DATE(sp.timestamp) = DATE(?)
        """

        result = self.db.conn.execute(query, [ticker, date]).fetchone()

        if result and result[0] and result[1]:
            return {
                "current_volume": float(result[0]),
                "avg_volume": float(result[1]),
            }

        return None

    def _log_trade_signal(
        self,
        ticker: str,
        signal: TrendSignal,
        price: float,
        date: datetime,
        days_until_earnings: Optional[int],
        volume_data: Optional[dict],
    ):
        """Log trade signal to journal for later analysis."""
        # Get current indicators
        indicators = self._get_indicators_for_log(ticker, date)

        # Get VXX level for market regime
        vxx_level = self._get_vxx_level(date)

        trade_log = TradeLog(
            symbol=ticker,
            direction=signal.signal.value,
            quantity=0,  # Will be filled in by portfolio manager
            price=price,
            trade_date=date.strftime("%Y-%m-%d"),
            trade_value=0,  # Will be filled in
            signal_type=self._extract_signal_type(signal.reasoning),
            confidence=signal.confidence,
            trend_state=signal.trend.value,
            sma_20=indicators.get("sma_20"),
            sma_50=indicators.get("sma_50"),
            sma_200=indicators.get("sma_200"),
            rsi_14=indicators.get("rsi_14"),
            macd=indicators.get("macd"),
            volume=volume_data["current_volume"] if volume_data else None,
            volume_avg=volume_data["avg_volume"] if volume_data else None,
            days_until_earnings=days_until_earnings,
            vxx_level=vxx_level,
            market_regime=self._determine_market_regime(vxx_level),
            reasoning=signal.reasoning,
            notes=f"Confidence: {signal.confidence:.0%}, Trend: {signal.trend.value}",
        )

        self.trade_journal.log_trade(trade_log)

    def _get_indicators_for_log(self, ticker: str, date: datetime) -> dict:
        """Get technical indicators for logging."""
        query = """
            SELECT sma_20, sma_50, sma_200, rsi_14, macd
            FROM technical_indicators
            WHERE symbol = ? AND DATE(timestamp) = DATE(?)
        """

        result = self.db.conn.execute(query, [ticker, date]).fetchone()

        if result:
            return {
                "sma_20": float(result[0]) if result[0] else None,
                "sma_50": float(result[1]) if result[1] else None,
                "sma_200": float(result[2]) if result[2] else None,
                "rsi_14": float(result[3]) if result[3] else None,
                "macd": float(result[4]) if result[4] else None,
            }

        return {}

    def _get_vxx_level(self, date: datetime) -> Optional[float]:
        """Get VXX level for market regime detection."""
        query = """
            SELECT close
            FROM stock_prices
            WHERE symbol = 'VXX'
            AND DATE(timestamp) = DATE(?)
        """

        result = self.db.conn.execute(query, [date]).fetchone()
        return float(result[0]) if result else None

    def _determine_market_regime(self, vxx_level: Optional[float]) -> str:
        """Determine market regime from VXX level."""
        if not vxx_level:
            return "NORMAL"

        if vxx_level > 50:
            return "CRASH"
        elif vxx_level > 30:
            return "VOLATILE"
        elif vxx_level < 15:
            return "COMPLACENT"
        else:
            return "NORMAL"

    def _extract_signal_type(self, reasoning: str) -> str:
        """Extract signal type from reasoning."""
        if "DEATH CROSS" in reasoning:
            return "DEATH_CROSS"
        elif "GOLDEN CROSS" in reasoning or "MACD" in reasoning:
            return "GOLDEN_CROSS"
        elif "TREND CHANGE" in reasoning:
            return "TREND_CHANGE"
        elif "EARNINGS" in reasoning:
            return "EARNINGS_BLOCK"
        elif "VOLUME" in reasoning:
            return "VOLUME_SPIKE"
        else:
            return "OTHER"
