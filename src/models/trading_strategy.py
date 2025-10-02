"""
Trading Strategy Framework for DuckLens.

This module defines entry/exit signals for backtesting:
- Entry: Support reclaim, breakout above highs, momentum indicators
- Exit: Resistance hit, stop loss, take profit, trailing stop
- Position sizing and risk management
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Literal

from src.data.storage.market_data_db import MarketDataDB


class SignalType(Enum):
    """Types of trading signals."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class EntryReason(Enum):
    """Reasons for entering a position."""

    SUPPORT_RECLAIM = "SUPPORT_RECLAIM"  # Price reclaims support level
    BREAKOUT_HIGH = "BREAKOUT_HIGH"  # Breaks above recent high
    MOMENTUM = "MOMENTUM"  # Strong momentum indicators
    ML_PREDICTION = "ML_PREDICTION"  # CatBoost prediction
    OVERSOLD_BOUNCE = "OVERSOLD_BOUNCE"  # RSI < 30 + reversal
    VOLUME_SURGE = "VOLUME_SURGE"  # Unusual volume + price increase


class ExitReason(Enum):
    """Reasons for exiting a position."""

    TAKE_PROFIT = "TAKE_PROFIT"  # Hit profit target
    STOP_LOSS = "STOP_LOSS"  # Hit stop loss
    TRAILING_STOP = "TRAILING_STOP"  # Trailing stop triggered
    RESISTANCE_HIT = "RESISTANCE_HIT"  # Hit resistance level
    TIME_EXIT = "TIME_EXIT"  # Max holding period reached
    ML_SELL_SIGNAL = "ML_SELL_SIGNAL"  # CatBoost sell signal
    OVERBOUGHT = "OVERBOUGHT"  # RSI > 70


@dataclass
class TradingSignal:
    """A buy or sell signal with context."""

    ticker: str
    date: datetime
    signal_type: SignalType
    entry_reason: EntryReason | None
    exit_reason: ExitReason | None
    price: Decimal
    confidence: float  # 0-1, from ML model
    stop_loss: Decimal | None
    take_profit: Decimal | None
    indicators: dict  # Supporting indicator values
    reasoning: str = ""  # Detailed explanation of why this signal was generated


@dataclass
class Position:
    """An open trading position."""

    ticker: str
    entry_date: datetime
    entry_price: Decimal
    entry_reason: EntryReason
    shares: int
    stop_loss: Decimal
    take_profit: Decimal
    trailing_stop_pct: float = 0.05  # 5% trailing stop
    highest_price: Decimal | None = None  # For trailing stop

    def update_trailing_stop(self, current_price: Decimal) -> None:
        """Update trailing stop based on highest price."""
        if self.highest_price is None or current_price > self.highest_price:
            self.highest_price = current_price
            # Update stop loss to trailing stop level
            new_stop = current_price * Decimal(1 - self.trailing_stop_pct)
            if new_stop > self.stop_loss:
                self.stop_loss = new_stop


@dataclass
class Trade:
    """A completed trade with entry and exit."""

    ticker: str
    entry_date: datetime
    exit_date: datetime
    entry_price: Decimal
    exit_price: Decimal
    shares: int
    entry_reason: EntryReason
    exit_reason: ExitReason
    profit_loss: Decimal
    profit_pct: float
    holding_days: int
    confidence: float  # ML confidence at entry


class TradingStrategy:
    """
    Trading strategy implementation with configurable signals.

    This class generates buy/sell signals based on:
    1. Technical indicators (support/resistance, breakouts)
    2. Market data (volume, volatility)
    3. ML predictions (CatBoost confidence scores)
    """

    def __init__(
        self,
        db: MarketDataDB,
        lookback_days: int = 60,
        support_window: int = 20,
        resistance_window: int = 20,
        breakout_window: int = 30,
        stop_loss_pct: float = 0.08,  # 8% stop loss
        take_profit_pct: float = 0.15,  # 15% take profit
        max_holding_days: int = 60,
    ):
        """
        Initialize trading strategy.

        Args:
            db: Database connection
            lookback_days: Days to look back for indicators
            support_window: Days to identify support levels
            resistance_window: Days to identify resistance levels
            breakout_window: Days to check for breakout above high
            stop_loss_pct: Stop loss percentage (e.g., 0.08 = 8%)
            take_profit_pct: Take profit percentage (e.g., 0.15 = 15%)
            max_holding_days: Maximum holding period
        """
        self.db = db
        self.lookback_days = lookback_days
        self.support_window = support_window
        self.resistance_window = resistance_window
        self.breakout_window = breakout_window
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.max_holding_days = max_holding_days

    def get_support_level(self, ticker: str, date: datetime) -> Decimal | None:
        """
        Calculate support level as lowest low in lookback window.

        Args:
            ticker: Stock ticker
            date: Current date

        Returns:
            Support price level or None
        """
        query = """
            SELECT MIN(low) as support
            FROM stock_prices
            WHERE symbol = ?
              AND DATE(timestamp) >= DATE(?) - INTERVAL '{} days'
              AND DATE(timestamp) < DATE(?)
        """.format(
            self.support_window
        )

        result = self.db.conn.execute(query, [ticker, date, date]).fetchone()
        return Decimal(str(result[0])) if result and result[0] else None

    def get_resistance_level(self, ticker: str, date: datetime) -> Decimal | None:
        """
        Calculate resistance level as highest high in lookback window.

        Args:
            ticker: Stock ticker
            date: Current date

        Returns:
            Resistance price level or None
        """
        query = """
            SELECT MAX(high) as resistance
            FROM stock_prices
            WHERE symbol = ?
              AND DATE(timestamp) >= DATE(?) - INTERVAL '{} days'
              AND DATE(timestamp) < DATE(?)
        """.format(
            self.resistance_window
        )

        result = self.db.conn.execute(query, [ticker, date, date]).fetchone()
        return Decimal(str(result[0])) if result and result[0] else None

    def check_breakout(self, ticker: str, date: datetime, current_price: Decimal) -> bool:
        """
        Check if price breaks out above recent high.

        Args:
            ticker: Stock ticker
            date: Current date
            current_price: Current price

        Returns:
            True if breakout detected
        """
        query = """
            SELECT MAX(high) as prev_high
            FROM stock_prices
            WHERE symbol = ?
              AND DATE(timestamp) >= DATE(?) - INTERVAL '{} days'
              AND DATE(timestamp) < DATE(?)
        """.format(
            self.breakout_window
        )

        result = self.db.conn.execute(query, [ticker, date, date]).fetchone()

        if result and result[0]:
            prev_high = Decimal(str(result[0]))
            # Breakout if current price > previous high by at least 0.5%
            return current_price > prev_high * Decimal("1.005")

        return False

    def check_support_reclaim(self, ticker: str, date: datetime, current_price: Decimal) -> bool:
        """
        Check if price reclaims support after dipping below.

        Args:
            ticker: Stock ticker
            date: Current date
            current_price: Current price

        Returns:
            True if support reclaim detected
        """
        support = self.get_support_level(ticker, date)

        if not support:
            return False

        # Check if price was below support recently and now above
        query = """
            SELECT MIN(low) as recent_low, MAX(close) as recent_close
            FROM stock_prices
            WHERE symbol = ?
              AND DATE(timestamp) >= DATE(?) - INTERVAL '5 days'
              AND DATE(timestamp) < DATE(?)
        """

        result = self.db.conn.execute(query, [ticker, date, date]).fetchone()

        if result and result[0] and result[1]:
            recent_low = Decimal(str(result[0]))
            recent_close = Decimal(str(result[1]))

            # Support reclaim: dipped below support, now back above
            return recent_low < support and current_price > support * Decimal("1.01")

        return False

    def get_indicators(self, ticker: str, date: datetime) -> dict:
        """
        Get all indicator values for a ticker on a date.

        Args:
            ticker: Stock ticker
            date: Date

        Returns:
            Dictionary of indicator values
        """
        # Get technical indicators
        indicators_query = """
            SELECT
                sma_20, sma_50, sma_200,
                ema_12, ema_26,
                macd, macd_signal, macd_histogram,
                rsi_14,
                bb_upper, bb_middle, bb_lower,
                atr_14
            FROM technical_indicators
            WHERE symbol = ? AND DATE(timestamp) = DATE(?)
        """

        ind_result = self.db.conn.execute(indicators_query, [ticker, date]).fetchone()

        indicators = {}

        if ind_result:
            indicators = {
                "sma_20": float(ind_result[0]) if ind_result[0] else None,
                "sma_50": float(ind_result[1]) if ind_result[1] else None,
                "sma_200": float(ind_result[2]) if ind_result[2] else None,
                "ema_12": float(ind_result[3]) if ind_result[3] else None,
                "ema_26": float(ind_result[4]) if ind_result[4] else None,
                "macd": float(ind_result[5]) if ind_result[5] else None,
                "macd_signal": float(ind_result[6]) if ind_result[6] else None,
                "macd_histogram": float(ind_result[7]) if ind_result[7] else None,
                "rsi_14": float(ind_result[8]) if ind_result[8] else None,
                "bb_upper": float(ind_result[9]) if ind_result[9] else None,
                "bb_middle": float(ind_result[10]) if ind_result[10] else None,
                "bb_lower": float(ind_result[11]) if ind_result[11] else None,
                "atr_14": float(ind_result[12]) if ind_result[12] else None,
            }

        # Get options flow indicators if available
        options_query = """
            SELECT
                put_call_ratio,
                smart_money_index,
                unusual_activity_score,
                iv_rank,
                flow_signal
            FROM options_flow_indicators
            WHERE ticker = ? AND DATE(date) = DATE(?)
        """

        opt_result = self.db.conn.execute(options_query, [ticker, date]).fetchone()

        if opt_result:
            indicators.update(
                {
                    "put_call_ratio": float(opt_result[0]) if opt_result[0] else None,
                    "smart_money_index": float(opt_result[1]) if opt_result[1] else None,
                    "unusual_activity_score": (float(opt_result[2]) if opt_result[2] else None),
                    "iv_rank": float(opt_result[3]) if opt_result[3] else None,
                    "flow_signal": opt_result[4] if opt_result[4] else None,
                }
            )

        return indicators

    def generate_buy_signal(
        self,
        ticker: str,
        date: datetime,
        current_price: Decimal,
        ml_confidence: float | None = None,
        min_confidence_threshold: float = 0.5,
    ) -> TradingSignal | None:
        """
        Generate buy signal based on multiple conditions.

        Args:
            ticker: Stock ticker
            date: Current date
            current_price: Current price
            ml_confidence: ML model confidence (0-1)
            min_confidence_threshold: Minimum confidence to generate signal (sit out if below)

        Returns:
            TradingSignal if buy conditions met and confidence high enough, None otherwise
        """
        indicators = self.get_indicators(ticker, date)

        # Check various entry conditions
        entry_reason = None
        confidence = ml_confidence or 0.5
        reasoning_parts = []

        # Get support and resistance for reasoning
        support = self.get_support_level(ticker, date)
        resistance = self.get_resistance_level(ticker, date)

        # Condition 1: Support reclaim
        if self.check_support_reclaim(ticker, date, current_price):
            entry_reason = EntryReason.SUPPORT_RECLAIM
            confidence = max(confidence, 0.6)
            reasoning_parts.append(
                f"🔵 SUPPORT RECLAIM: Price reclaimed support level (${support:.2f}). "
                f"Recent dip below support followed by bounce = bullish reversal signal."
            )

        # Condition 2: Breakout above recent high
        elif self.check_breakout(ticker, date, current_price):
            entry_reason = EntryReason.BREAKOUT_HIGH
            confidence = max(confidence, 0.65)
            resistance_info = f"(prev high ${resistance:.2f})" if resistance else ""
            reasoning_parts.append(
                f"🚀 BREAKOUT: Price broke above {self.breakout_window}-day high {resistance_info}. "
                f"Momentum continuation pattern detected."
            )

        # Condition 3: Oversold bounce (RSI < 30 + MACD crossover)
        elif (
            indicators.get("rsi_14")
            and indicators["rsi_14"] < 30
            and indicators.get("macd_histogram")
            and indicators["macd_histogram"] > 0
        ):
            entry_reason = EntryReason.OVERSOLD_BOUNCE
            confidence = max(confidence, 0.55)
            reasoning_parts.append(
                f"📉➡️📈 OVERSOLD BOUNCE: RSI = {indicators['rsi_14']:.1f} (oversold < 30). "
                f"MACD histogram = {indicators['macd_histogram']:.3f} (turned positive). "
                f"Oversold + momentum reversal = bounce opportunity."
            )

        # Condition 4: Strong ML prediction
        elif ml_confidence and ml_confidence > 0.7:
            entry_reason = EntryReason.ML_PREDICTION
            confidence = ml_confidence
            reasoning_parts.append(
                f"🤖 ML PREDICTION: CatBoost model predicts UP move with {ml_confidence:.1%} confidence. "
                f"Model identified favorable pattern in features (indicators + options flow + price action)."
            )

        # Condition 5: Options flow bullish + momentum
        elif (
            indicators.get("flow_signal") == "BULLISH"
            and indicators.get("macd_histogram")
            and indicators["macd_histogram"] > 0
            and indicators.get("rsi_14")
            and indicators["rsi_14"] > 50
        ):
            entry_reason = EntryReason.MOMENTUM
            confidence = max(confidence, 0.6)
            pc_ratio = indicators.get("put_call_ratio", "N/A")
            reasoning_parts.append(
                f"💪 MOMENTUM: Options flow = BULLISH (P/C ratio = {pc_ratio}), "
                f"MACD histogram = {indicators['macd_histogram']:.3f} (positive), "
                f"RSI = {indicators['rsi_14']:.1f} (above 50). "
                f"Multiple confirmations of bullish momentum."
            )

        # No entry signal OR confidence too low
        if not entry_reason:
            # Build reasoning for why we're NOT trading
            reasons_to_skip = []
            if ml_confidence and ml_confidence < min_confidence_threshold:
                reasons_to_skip.append(
                    f"ML confidence {ml_confidence:.1%} < threshold {min_confidence_threshold:.1%}"
                )

            if indicators.get("rsi_14"):
                rsi = indicators["rsi_14"]
                if 40 < rsi < 60:
                    reasons_to_skip.append(f"RSI neutral ({rsi:.1f})")

            if indicators.get("macd_histogram") is not None:
                if abs(indicators["macd_histogram"]) < 0.1:
                    reasons_to_skip.append("MACD weak")

            # Return None, but log reasoning if verbose mode
            return None

        # Check if confidence meets minimum threshold
        if confidence < min_confidence_threshold:
            reasoning_parts.append(
                f"\n⚠️  SIGNAL REJECTED: Confidence {confidence:.1%} < threshold {min_confidence_threshold:.1%}. "
                f"Sitting out this trade to preserve capital."
            )
            return None

        # Calculate stop loss and take profit
        stop_loss = current_price * Decimal(1 - self.stop_loss_pct)
        take_profit = current_price * Decimal(1 + self.take_profit_pct)

        # Build complete reasoning
        reasoning = "\n".join(reasoning_parts)

        # Add technical context
        technical_context = []
        if indicators.get("sma_20") and indicators.get("sma_50"):
            trend = "bullish" if indicators["sma_20"] > indicators["sma_50"] else "bearish"
            technical_context.append(f"Trend: {trend} (SMA20 vs SMA50)")

        if indicators.get("rsi_14"):
            technical_context.append(f"RSI: {indicators['rsi_14']:.1f}")

        if indicators.get("macd_histogram"):
            macd_direction = "bullish" if indicators["macd_histogram"] > 0 else "bearish"
            technical_context.append(f"MACD: {macd_direction}")

        if technical_context:
            reasoning += f"\n\n📊 Technical Context: {', '.join(technical_context)}"

        # Add ML context if available
        if ml_confidence:
            reasoning += f"\n🤖 ML Confidence: {ml_confidence:.1%}"

        reasoning += f"\n\n💰 Entry: ${current_price:.2f} | SL: ${stop_loss:.2f} (-{self.stop_loss_pct:.1%}) | TP: ${take_profit:.2f} (+{self.take_profit_pct:.1%})"
        reasoning += f"\n🎯 Overall Confidence: {confidence:.1%}"

        return TradingSignal(
            ticker=ticker,
            date=date,
            signal_type=SignalType.BUY,
            entry_reason=entry_reason,
            exit_reason=None,
            price=current_price,
            confidence=confidence,
            stop_loss=stop_loss,
            take_profit=take_profit,
            indicators=indicators,
            reasoning=reasoning,
        )

    def generate_sell_signal(
        self,
        position: Position,
        ticker: str,
        date: datetime,
        current_price: Decimal,
        ml_confidence: float | None = None,
    ) -> TradingSignal | None:
        """
        Generate sell signal for open position.

        Args:
            position: Open position
            ticker: Stock ticker
            date: Current date
            current_price: Current price
            ml_confidence: ML sell confidence

        Returns:
            TradingSignal if sell conditions met, None otherwise
        """
        indicators = self.get_indicators(ticker, date)
        exit_reason = None
        reasoning_parts = []

        # Update trailing stop
        position.update_trailing_stop(current_price)

        # Calculate current P&L
        entry_price = position.entry_price
        current_pnl_pct = float((current_price - entry_price) / entry_price * 100)
        current_pnl = (current_price - entry_price) * Decimal(position.shares)
        holding_days = (date - position.entry_date).days

        # Condition 1: Stop loss hit
        if current_price <= position.stop_loss:
            exit_reason = ExitReason.STOP_LOSS
            loss_pct = float((current_price - entry_price) / entry_price * 100)
            reasoning_parts.append(
                f"🛑 STOP LOSS HIT: Price ${current_price:.2f} <= stop ${position.stop_loss:.2f}. "
                f"Current P&L: {loss_pct:+.1f}%. Cutting losses to preserve capital."
            )

        # Condition 2: Take profit hit
        elif current_price >= position.take_profit:
            exit_reason = ExitReason.TAKE_PROFIT
            profit_pct = float((current_price - entry_price) / entry_price * 100)
            reasoning_parts.append(
                f"🎯 TAKE PROFIT HIT: Price ${current_price:.2f} >= target ${position.take_profit:.2f}. "
                f"Profit: {profit_pct:+.1f}%. Locking in gains at target."
            )

        # Condition 3: Trailing stop hit
        elif position.highest_price and current_price < position.highest_price * Decimal(
            1 - position.trailing_stop_pct
        ):
            exit_reason = ExitReason.TRAILING_STOP
            peak = float(position.highest_price)
            drop_from_peak = float((peak - float(current_price)) / peak * 100)
            reasoning_parts.append(
                f"📉 TRAILING STOP HIT: Price ${current_price:.2f} dropped {drop_from_peak:.1f}% "
                f"from peak ${peak:.2f}. Trailing stop at {position.trailing_stop_pct:.1%} triggered. "
                f"Protecting profits gained since entry."
            )

        # Condition 4: Max holding period
        elif (date - position.entry_date).days >= self.max_holding_days:
            exit_reason = ExitReason.TIME_EXIT
            reasoning_parts.append(
                f"⏰ TIME EXIT: Held for {holding_days} days >= max {self.max_holding_days} days. "
                f"Current P&L: {current_pnl_pct:+.1f}%. "
                f"Exiting to redeploy capital into fresher opportunities."
            )

        # Condition 5: Hit resistance
        else:
            resistance = self.get_resistance_level(ticker, date)
            if resistance and current_price >= resistance * Decimal("0.99"):
                exit_reason = ExitReason.RESISTANCE_HIT
                reasoning_parts.append(
                    f"🚧 RESISTANCE HIT: Price ${current_price:.2f} approached resistance ${resistance:.2f}. "
                    f"High probability of reversal at resistance. Taking profits here."
                )

        # Condition 6: Overbought
        if (
            not exit_reason
            and indicators.get("rsi_14")
            and indicators["rsi_14"] > 75
            and indicators.get("macd_histogram")
            and indicators["macd_histogram"] < 0
        ):
            exit_reason = ExitReason.OVERBOUGHT
            reasoning_parts.append(
                f"📊 OVERBOUGHT: RSI = {indicators['rsi_14']:.1f} (overbought > 75). "
                f"MACD histogram = {indicators['macd_histogram']:.3f} (turned negative). "
                f"Momentum exhaustion detected. Exiting before reversal."
            )

        # Condition 7: ML sell signal
        if not exit_reason and ml_confidence and ml_confidence > 0.75:
            exit_reason = ExitReason.ML_SELL_SIGNAL
            reasoning_parts.append(
                f"🤖 ML SELL SIGNAL: CatBoost model predicts DOWN move with {ml_confidence:.1%} confidence. "
                f"Model detected bearish pattern. Exiting proactively."
            )

        # No exit signal - holding
        if not exit_reason:
            # Build reasoning for why we're HOLDING
            hold_reasons = []
            if current_pnl_pct > 0:
                hold_reasons.append(f"Currently profitable ({current_pnl_pct:+.1f}%)")
            if position.highest_price and current_price >= position.highest_price * Decimal(0.95):
                hold_reasons.append("Near peak price")
            if indicators.get("rsi_14") and 30 < indicators["rsi_14"] < 70:
                hold_reasons.append(f"RSI neutral ({indicators['rsi_14']:.1f})")

            # Not returning signal, just logging hold decision
            return None

        # Build complete reasoning
        reasoning = "\n".join(reasoning_parts)

        # Add position context
        reasoning += f"\n\n📍 Position Details:"
        reasoning += f"\n  Entry: ${entry_price:.2f} on {position.entry_date.date()} ({position.entry_reason.value})"
        reasoning += f"\n  Current: ${current_price:.2f}"
        reasoning += f"\n  Holding: {holding_days} days"
        reasoning += f"\n  Current P&L: {current_pnl_pct:+.1f}% (${current_pnl:+,.2f})"

        if position.highest_price:
            reasoning += f"\n  Peak Price: ${position.highest_price:.2f}"

        # Add technical context
        technical_context = []
        if indicators.get("rsi_14"):
            technical_context.append(f"RSI: {indicators['rsi_14']:.1f}")

        if indicators.get("macd_histogram"):
            macd_direction = "bullish" if indicators["macd_histogram"] > 0 else "bearish"
            technical_context.append(f"MACD: {macd_direction}")

        if technical_context:
            reasoning += f"\n\n📊 Technical Context: {', '.join(technical_context)}"

        if ml_confidence:
            reasoning += f"\n🤖 ML Sell Confidence: {ml_confidence:.1%}"

        return TradingSignal(
            ticker=ticker,
            date=date,
            signal_type=SignalType.SELL,
            entry_reason=None,
            exit_reason=exit_reason,
            price=current_price,
            confidence=ml_confidence or 0.5,
            stop_loss=None,
            take_profit=None,
            indicators=indicators,
            reasoning=reasoning,
        )
