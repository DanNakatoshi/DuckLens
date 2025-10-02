"""
Trend change detection for trading signals.

Detects when market trend shifts between BULLISH, BEARISH, and NEUTRAL.
Generates BUY (trend turns bullish), SELL (trend turns bearish),
or DON'T TRADE (neutral or high-impact event day) signals.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from src.data.storage.market_data_db import MarketDataDB


class TrendState(Enum):
    """Market trend state."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class TradingSignal(Enum):
    """Trading signal type."""

    BUY = "BUY"
    SELL = "SELL"
    DONT_TRADE = "DONT_TRADE"


@dataclass
class TrendSignal:
    """Trend change signal with reasoning."""

    ticker: str
    date: datetime
    signal: TradingSignal
    trend: TrendState
    price: Decimal
    confidence: float  # 0-1
    reasoning: str

    # Signal details
    sma_aligned: bool
    macd_bullish: bool
    rsi_healthy: bool
    options_bullish: bool | None
    blocked_by_event: bool


class TrendDetector:
    """
    Detects trend changes and generates trading signals.

    Trend Detection Logic:
    - BULLISH: SMA_20 > SMA_50 > SMA_200, MACD > Signal, RSI 40-70, Options flow BULLISH
    - BEARISH: SMA_20 < SMA_50 < SMA_200, MACD < Signal, RSI 30-60, Options flow BEARISH
    - NEUTRAL: Mixed signals or don't have conviction

    Trading Signals:
    - BUY: Trend changes from BEARISH/NEUTRAL → BULLISH
    - SELL: Trend changes from BULLISH/NEUTRAL → BEARISH
    - DON'T TRADE: Neutral trend OR high-impact economic event
    """

    def __init__(
        self,
        db: MarketDataDB,
        min_confidence: float = 0.6,
        block_high_impact_events: bool = True,
        min_adx: float = 25.0,
        confirmation_days: int = 2,
        long_only: bool = True,
    ):
        """
        Initialize trend detector.

        Args:
            db: Database connection
            min_confidence: Minimum confidence to generate signal (0-1)
            block_high_impact_events: Block trading on high-impact event days + day before
            min_adx: Minimum ADX for trend strength (default 25 = moderate trend)
            confirmation_days: Days to confirm trend before trading (default 2)
            long_only: Only exit on death cross (SMA_50 < SMA_200), ignore short-term bearish (default True)
        """
        self.db = db
        self.min_confidence = min_confidence
        self.block_high_impact_events = block_high_impact_events
        self.min_adx = min_adx
        self.confirmation_days = confirmation_days
        self.long_only = long_only

        # Track previous trend state
        self.previous_trend: dict[str, TrendState] = {}

        # Track trend confirmation (how many days trend has been consistent)
        self.trend_confirmation_count: dict[str, int] = {}

    def detect_trend(self, ticker: str, date: datetime) -> tuple[TrendState, float, dict]:
        """
        Detect current market trend.

        Args:
            ticker: Stock ticker
            date: Current date

        Returns:
            Tuple of (trend_state, confidence, indicator_values)
        """
        # Get indicators
        indicators = self._get_indicators(ticker, date)

        if not indicators:
            return TrendState.NEUTRAL, 0.0, {}

        # Check trend components
        sma_aligned = self._check_sma_alignment(indicators)
        macd_bullish = self._check_macd(indicators)
        rsi_healthy = self._check_rsi(indicators)
        options_bullish = self._check_options_flow(indicators)

        # Calculate bullish/bearish score
        bullish_score = 0
        bearish_score = 0
        total_signals = 0

        # SMA alignment (strongest signal, weight = 2)
        if sma_aligned is True:
            bullish_score += 2
            total_signals += 2
        elif sma_aligned is False:
            bearish_score += 2
            total_signals += 2

        # MACD (weight = 1)
        if macd_bullish is True:
            bullish_score += 1
            total_signals += 1
        elif macd_bullish is False:
            bearish_score += 1
            total_signals += 1

        # RSI (weight = 1)
        if rsi_healthy is True:
            bullish_score += 1
            total_signals += 1
        elif rsi_healthy is False:
            bearish_score += 1
            total_signals += 1

        # Options flow (weight = 1, optional)
        if options_bullish is True:
            bullish_score += 1
            total_signals += 1
        elif options_bullish is False:
            bearish_score += 1
            total_signals += 1

        # Determine trend
        if total_signals == 0:
            return TrendState.NEUTRAL, 0.0, indicators

        bullish_pct = bullish_score / total_signals
        bearish_pct = bearish_score / total_signals

        # Need >60% conviction for trend
        if bullish_pct >= 0.6:
            return TrendState.BULLISH, bullish_pct, indicators
        elif bearish_pct >= 0.6:
            return TrendState.BEARISH, bearish_pct, indicators
        else:
            # Mixed signals
            confidence = max(bullish_pct, bearish_pct)
            return TrendState.NEUTRAL, confidence, indicators

    def generate_signal(
        self,
        ticker: str,
        date: datetime,
        current_price: Decimal,
    ) -> TrendSignal | None:
        """
        Generate trading signal based on trend change.

        Args:
            ticker: Stock ticker
            date: Current date
            current_price: Current price

        Returns:
            TrendSignal or None if below confidence threshold
        """
        # Check if blocked by economic event
        blocked_by_event = False
        event_reason = ""

        if self.block_high_impact_events:
            blocked_by_event, event_reason = self._check_economic_events(date)

        # Detect current trend
        current_trend, confidence, indicators = self.detect_trend(ticker, date)

        # Get previous trend (default to NEUTRAL if first time)
        previous_trend = self.previous_trend.get(ticker, TrendState.NEUTRAL)

        # Check ADX for trend strength
        adx = indicators.get("adx")
        adx_strong = adx is not None and adx >= self.min_adx

        # Update confirmation counter
        if current_trend == previous_trend:
            # Trend continues, increment counter
            self.trend_confirmation_count[ticker] = self.trend_confirmation_count.get(ticker, 0) + 1
        else:
            # Trend changed, reset counter
            self.trend_confirmation_count[ticker] = 1

        confirmed_days = self.trend_confirmation_count.get(ticker, 0)

        # Determine signal
        signal = TradingSignal.DONT_TRADE
        reasoning_parts = []

        if blocked_by_event:
            signal = TradingSignal.DONT_TRADE
            reasoning_parts.append(f"[BLOCKED] {event_reason}")
            reasoning_parts.append("Risk management: Avoid trading around high-impact events")
        elif confidence < self.min_confidence:
            signal = TradingSignal.DONT_TRADE
            reasoning_parts.append(
                f"[LOW CONFIDENCE] Trend confidence {confidence:.1%} < {self.min_confidence:.1%}"
            )
            reasoning_parts.append("Mixed signals - waiting for clearer direction")
        elif not adx_strong:
            signal = TradingSignal.DONT_TRADE
            adx_val = adx if adx else 0
            reasoning_parts.append(f"[WEAK TREND] ADX {adx_val:.1f} < {self.min_adx:.1f}")
            reasoning_parts.append("Trend not strong enough to trade")
        elif current_trend == TrendState.NEUTRAL:
            signal = TradingSignal.DONT_TRADE
            reasoning_parts.append("[NEUTRAL TREND] Market direction unclear")
            reasoning_parts.append("Waiting for trend to establish")
        elif current_trend == TrendState.BULLISH and previous_trend != TrendState.BULLISH:
            # Trend changed to bullish - check confirmation
            if confirmed_days >= self.confirmation_days:
                signal = TradingSignal.BUY
                reasoning_parts.append(
                    f"[TREND CHANGE CONFIRMED] {previous_trend.value} -> BULLISH"
                )
                reasoning_parts.append(f"Confirmed for {confirmed_days} days")
                reasoning_parts.append(f"Confidence: {confidence:.1%} | ADX: {adx:.1f}")
            else:
                signal = TradingSignal.DONT_TRADE
                reasoning_parts.append(f"[TREND CHANGE PENDING] {previous_trend.value} -> BULLISH")
                reasoning_parts.append(
                    f"Waiting for confirmation: {confirmed_days}/{self.confirmation_days} days"
                )
        elif current_trend == TrendState.BEARISH and previous_trend != TrendState.BEARISH:
            # Trend changed to bearish
            if self.long_only:
                # Long-only mode: Only sell on death cross (SMA_50 < SMA_200)
                sma_50 = indicators.get("sma_50")
                sma_200 = indicators.get("sma_200")
                death_cross = sma_50 is not None and sma_200 is not None and sma_50 < sma_200

                if death_cross and confirmed_days >= self.confirmation_days:
                    signal = TradingSignal.SELL
                    reasoning_parts.append(f"[DEATH CROSS CONFIRMED] Major trend reversal")
                    reasoning_parts.append(f"SMA_50 ({sma_50:.2f}) < SMA_200 ({sma_200:.2f})")
                    reasoning_parts.append(f"Confirmed for {confirmed_days} days - EXIT POSITION")
                else:
                    signal = TradingSignal.DONT_TRADE
                    reasoning_parts.append(f"[SHORT-TERM BEARISH] Ignoring in long-only mode")
                    reasoning_parts.append(f"Hold position - waiting for death cross to exit")
                    if death_cross:
                        reasoning_parts.append(
                            f"Death cross detected but needs confirmation: {confirmed_days}/{self.confirmation_days} days"
                        )
            else:
                # Normal mode: Sell on any bearish trend
                if confirmed_days >= self.confirmation_days:
                    signal = TradingSignal.SELL
                    reasoning_parts.append(
                        f"[TREND CHANGE CONFIRMED] {previous_trend.value} -> BEARISH"
                    )
                    reasoning_parts.append(f"Confirmed for {confirmed_days} days")
                    reasoning_parts.append(f"Confidence: {confidence:.1%} | ADX: {adx:.1f}")
                else:
                    signal = TradingSignal.DONT_TRADE
                    reasoning_parts.append(
                        f"[TREND CHANGE PENDING] {previous_trend.value} -> BEARISH"
                    )
                    reasoning_parts.append(
                        f"Waiting for confirmation: {confirmed_days}/{self.confirmation_days} days"
                    )
        else:
            # Trend continues, no signal
            signal = TradingSignal.DONT_TRADE
            reasoning_parts.append(f"[TREND CONTINUES] Still {current_trend.value}")
            reasoning_parts.append("No change - holding current position")

        # Add indicator details
        reasoning_parts.append("\n[INDICATORS]")

        sma_aligned = self._check_sma_alignment(indicators)
        if sma_aligned is True:
            reasoning_parts.append("  SMA: Bullish (20>50>200)")
        elif sma_aligned is False:
            reasoning_parts.append("  SMA: Bearish (20<50<200)")
        else:
            reasoning_parts.append("  SMA: Mixed")

        macd_bullish = self._check_macd(indicators)
        macd_val = indicators.get("macd")
        macd_sig = indicators.get("macd_signal")
        if macd_val is not None and macd_sig is not None:
            if macd_bullish:
                reasoning_parts.append(f"  MACD: Bullish ({macd_val:.2f} > {macd_sig:.2f})")
            else:
                reasoning_parts.append(f"  MACD: Bearish ({macd_val:.2f} < {macd_sig:.2f})")
        else:
            reasoning_parts.append("  MACD: No data")

        rsi = indicators.get("rsi_14")
        rsi_healthy = None
        if rsi:
            rsi_healthy = self._check_rsi(indicators)
            status = "Healthy" if rsi_healthy else "Unhealthy"
            reasoning_parts.append(f"  RSI: {status} ({rsi:.1f})")
        else:
            reasoning_parts.append("  RSI: No data")

        options_bullish = self._check_options_flow(indicators)
        flow = indicators.get("flow_signal")
        if flow:
            reasoning_parts.append(f"  Options Flow: {flow}")

        reasoning_parts.append(f"\n[PRICE] ${current_price:.2f}")

        # Update previous trend
        self.previous_trend[ticker] = current_trend

        return TrendSignal(
            ticker=ticker,
            date=date,
            signal=signal,
            trend=current_trend,
            price=current_price,
            confidence=confidence,
            reasoning="\n".join(reasoning_parts),
            sma_aligned=sma_aligned if sma_aligned is not None else False,
            macd_bullish=macd_bullish,
            rsi_healthy=rsi_healthy if rsi_healthy is not None else False,
            options_bullish=options_bullish,
            blocked_by_event=blocked_by_event,
        )

    def _get_indicators(self, ticker: str, date: datetime) -> dict:
        """Get technical indicators for date."""
        query = """
        SELECT
            ti.sma_20, ti.sma_50, ti.sma_200,
            ti.macd, ti.macd_signal,
            ti.rsi_14,
            ti.atr_14,
            ofi.flow_signal,
            ofi.put_call_ratio,
            ofi.smart_money_index,
            sp.close
        FROM technical_indicators ti
        LEFT JOIN options_flow_indicators ofi
            ON ti.symbol = ofi.ticker AND DATE(ti.timestamp) = DATE(ofi.date)
        LEFT JOIN stock_prices sp
            ON ti.symbol = sp.symbol AND DATE(ti.timestamp) = DATE(sp.timestamp)
        WHERE ti.symbol = ? AND DATE(ti.timestamp) = DATE(?)
        """

        result = self.db.conn.execute(query, [ticker, date]).fetchone()

        if not result:
            return {}

        # Calculate ADX proxy from ATR (since ADX column doesn't exist)
        atr = float(result[6]) if result[6] else None
        current_price = float(result[10]) if result[10] else 100

        # Simple ADX approximation: (ATR / Price) * 100 gives volatility %
        # Scale to 0-100 range. High volatility + trend alignment = strong trend
        adx_proxy = None
        if atr and current_price:
            volatility_pct = (atr / current_price) * 100
            # Map 0-5% volatility to 0-100 ADX scale
            adx_proxy = min(100, volatility_pct * 20)

        return {
            "sma_20": float(result[0]) if result[0] else None,
            "sma_50": float(result[1]) if result[1] else None,
            "sma_200": float(result[2]) if result[2] else None,
            "macd": float(result[3]) if result[3] else None,
            "macd_signal": float(result[4]) if result[4] else None,
            "rsi_14": float(result[5]) if result[5] else None,
            "atr_14": atr,
            "adx": adx_proxy,  # Approximate ADX from ATR
            "flow_signal": result[7] if result[7] else None,
            "put_call_ratio": float(result[8]) if result[8] else None,
            "smart_money_index": float(result[9]) if result[9] else None,
        }

    def _check_sma_alignment(self, indicators: dict) -> bool | None:
        """Check if SMAs are aligned for trend."""
        sma_20 = indicators.get("sma_20")
        sma_50 = indicators.get("sma_50")
        sma_200 = indicators.get("sma_200")

        if not all([sma_20, sma_50, sma_200]):
            return None

        # Bullish: 20 > 50 > 200
        if sma_20 > sma_50 > sma_200:
            return True
        # Bearish: 20 < 50 < 200
        elif sma_20 < sma_50 < sma_200:
            return False
        else:
            # Mixed
            return None

    def _check_macd(self, indicators: dict) -> bool:
        """Check MACD trend."""
        macd = indicators.get("macd")
        macd_signal = indicators.get("macd_signal")

        if macd is None or macd_signal is None:
            return False

        # Bullish if MACD > Signal
        return macd > macd_signal

    def _check_rsi(self, indicators: dict) -> bool | None:
        """Check if RSI is in healthy range."""
        rsi = indicators.get("rsi_14")

        if rsi is None:
            return None

        # Bullish healthy: 40-70
        if 40 <= rsi <= 70:
            return True
        # Bearish or extreme
        elif rsi < 40 or rsi > 70:
            return False
        else:
            return None

    def _check_options_flow(self, indicators: dict) -> bool | None:
        """Check options flow signal."""
        flow_signal = indicators.get("flow_signal")

        if not flow_signal:
            return None

        if flow_signal == "BULLISH":
            return True
        elif flow_signal == "BEARISH":
            return False
        else:
            return None

    def _check_economic_events(self, date: datetime) -> tuple[bool, str]:
        """
        Check if there's a high-impact economic event on this day or next day.

        Returns:
            Tuple of (is_blocked, reason)
        """
        # Check event on this day
        tomorrow = date + timedelta(days=1)

        query = """
        SELECT event_name, impact
        FROM economic_calendar
        WHERE DATE(release_date) = DATE(?) OR DATE(release_date) = DATE(?)
        ORDER BY
            CASE impact
                WHEN 'high' THEN 3
                WHEN 'medium' THEN 2
                WHEN 'low' THEN 1
                ELSE 0
            END DESC
        LIMIT 1
        """

        result = self.db.conn.execute(query, [date, tomorrow]).fetchone()

        if not result:
            return False, ""

        event_name = result[0]
        impact = result[1]

        # Block if high impact
        high_impact_keywords = [
            "FOMC",
            "Federal Funds Rate",
            "CPI",
            "Inflation",
            "Non-Farm Payroll",
            "NFP",
            "Employment",
            "Unemployment",
            "GDP",
            "Interest Rate Decision",
            "Fed Chair",
        ]

        is_high_impact = any(
            keyword.lower() in event_name.lower() for keyword in high_impact_keywords
        )

        if is_high_impact or (impact and impact.lower() == "high"):
            return True, f"High-impact event: {event_name}"

        return False, ""

    def reset_trend_history(self):
        """Reset trend history (useful for backtesting)."""
        self.previous_trend.clear()
        self.trend_confirmation_count.clear()
