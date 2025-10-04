"""
Unusual Options Activity & Volume Detector.

Monitors watchlist tickers for:
- Unusual options volume (calls/puts)
- Unusual stock volume
- Smart money flow signals
- Short-term trading opportunities
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from src.data.collectors.polygon_options_flow import PolygonOptionsFlow
from src.data.storage.market_data_db import MarketDataDB


@dataclass
class UnusualActivitySignal:
    """Represents an unusual activity signal for short-term trading."""

    ticker: str
    signal_type: str  # "unusual_calls", "unusual_puts", "volume_spike", "smart_money"
    current_price: float
    volume: int
    avg_volume_20d: int
    volume_ratio: float  # current / average

    # Options-specific
    call_volume: Optional[int] = None
    put_volume: Optional[int] = None
    put_call_ratio: Optional[float] = None
    unusual_call_contracts: Optional[int] = None
    unusual_put_contracts: Optional[int] = None

    # Confidence scoring
    confidence: float = 0.0
    reason: str = ""
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class UnusualActivityDetector:
    """Detects unusual options and volume activity for short-term opportunities."""

    def __init__(self, db: MarketDataDB, api_key: str = None):
        """
        Initialize detector.

        Args:
            db: Market data database connection
            api_key: Polygon API key (optional, reads from env if None)
        """
        self.db = db
        self.options_flow = PolygonOptionsFlow(api_key=api_key)

    def scan_watchlist(self, tickers: list[str]) -> list[UnusualActivitySignal]:
        """
        Scan watchlist for unusual activity signals.

        Args:
            tickers: List of ticker symbols to scan

        Returns:
            List of unusual activity signals sorted by confidence
        """
        signals = []

        for ticker in tickers:
            # Check volume spike
            volume_signal = self._check_volume_spike(ticker)
            if volume_signal:
                signals.append(volume_signal)

            # Check options flow
            options_signal = self._check_unusual_options(ticker)
            if options_signal:
                signals.append(options_signal)

        # Sort by confidence descending
        signals.sort(key=lambda x: x.confidence, reverse=True)

        return signals

    def _check_volume_spike(self, ticker: str) -> Optional[UnusualActivitySignal]:
        """
        Check for unusual stock volume spike.

        Args:
            ticker: Ticker symbol

        Returns:
            Signal if volume is unusual, None otherwise
        """
        # Get today's volume
        today_query = """
            SELECT volume, close
            FROM stock_prices
            WHERE symbol = ?
            AND DATE(timestamp) = CURRENT_DATE
            ORDER BY timestamp DESC
            LIMIT 1
        """
        today_data = self.db.conn.execute(today_query, [ticker]).fetchone()

        if not today_data:
            return None

        current_volume = int(today_data[0])
        current_price = float(today_data[1])

        # Get 20-day average volume
        avg_query = """
            SELECT AVG(volume) as avg_volume
            FROM stock_prices
            WHERE symbol = ?
            AND DATE(timestamp) >= CURRENT_DATE - INTERVAL '20 days'
            AND DATE(timestamp) < CURRENT_DATE
        """
        avg_data = self.db.conn.execute(avg_query, [ticker]).fetchone()

        if not avg_data or not avg_data[0]:
            return None

        avg_volume = int(avg_data[0])

        # Calculate volume ratio
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0

        # Flag if volume is 2x+ average
        if volume_ratio >= 2.0:
            # Higher confidence for bigger spikes
            confidence = min(0.90, 0.60 + (volume_ratio - 2.0) * 0.10)

            return UnusualActivitySignal(
                ticker=ticker,
                signal_type="volume_spike",
                current_price=current_price,
                volume=current_volume,
                avg_volume_20d=avg_volume,
                volume_ratio=volume_ratio,
                confidence=confidence,
                reason=f"Volume {volume_ratio:.1f}x above 20-day avg"
            )

        return None

    def _check_unusual_options(self, ticker: str) -> Optional[UnusualActivitySignal]:
        """
        Check for unusual options activity.

        Args:
            ticker: Ticker symbol

        Returns:
            Signal if options activity is unusual, None otherwise
        """
        try:
            # Get current stock price
            price_query = """
                SELECT close
                FROM stock_prices
                WHERE symbol = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """
            price_data = self.db.conn.execute(price_query, [ticker]).fetchone()

            if not price_data:
                return None

            current_price = float(price_data[0])

            # Get options chain snapshot
            # Focus on near-term options (next 30 days)
            today = datetime.now()
            exp_start = (today + timedelta(days=7)).strftime("%Y-%m-%d")
            exp_end = (today + timedelta(days=30)).strftime("%Y-%m-%d")

            contracts = self.options_flow.get_options_chain_snapshot(
                underlying_ticker=ticker,
                expiration_date_gte=exp_start,
                expiration_date_lte=exp_end,
                limit=250
            )

            if not contracts:
                return None

            # Aggregate flow
            flow = self.options_flow.aggregate_daily_flow(
                contracts=contracts,
                ticker=ticker,
                date=today
            )

            # Check for unusual activity
            total_volume = flow.total_call_volume + flow.total_put_volume

            # Unusual calls (bullish)
            if flow.unusual_call_contracts >= 5 and float(flow.put_call_ratio) < 0.7:
                confidence = min(0.85, 0.65 + flow.unusual_call_contracts * 0.02)

                return UnusualActivitySignal(
                    ticker=ticker,
                    signal_type="unusual_calls",
                    current_price=current_price,
                    volume=total_volume,
                    avg_volume_20d=0,  # Not tracked for options
                    volume_ratio=0.0,
                    call_volume=flow.total_call_volume,
                    put_volume=flow.total_put_volume,
                    put_call_ratio=float(flow.put_call_ratio),
                    unusual_call_contracts=flow.unusual_call_contracts,
                    unusual_put_contracts=flow.unusual_put_contracts,
                    confidence=confidence,
                    reason=f"Unusual call buying: {flow.unusual_call_contracts} contracts, P/C ratio {flow.put_call_ratio:.2f}"
                )

            # Unusual puts (bearish)
            if flow.unusual_put_contracts >= 5 and float(flow.put_call_ratio) > 1.5:
                confidence = min(0.85, 0.65 + flow.unusual_put_contracts * 0.02)

                return UnusualActivitySignal(
                    ticker=ticker,
                    signal_type="unusual_puts",
                    current_price=current_price,
                    volume=total_volume,
                    avg_volume_20d=0,
                    volume_ratio=0.0,
                    call_volume=flow.total_call_volume,
                    put_volume=flow.total_put_volume,
                    put_call_ratio=float(flow.put_call_ratio),
                    unusual_call_contracts=flow.unusual_call_contracts,
                    unusual_put_contracts=flow.unusual_put_contracts,
                    confidence=confidence,
                    reason=f"Unusual put buying: {flow.unusual_put_contracts} contracts, P/C ratio {flow.put_call_ratio:.2f}"
                )

            # Smart money flow (aggressive call buying at ask)
            if flow.call_volume_at_ask > 0:
                aggression_ratio = flow.call_volume_at_ask / flow.total_call_volume if flow.total_call_volume > 0 else 0

                if aggression_ratio > 0.6 and flow.total_call_volume > 500:
                    confidence = min(0.80, 0.60 + aggression_ratio * 0.20)

                    return UnusualActivitySignal(
                        ticker=ticker,
                        signal_type="smart_money",
                        current_price=current_price,
                        volume=total_volume,
                        avg_volume_20d=0,
                        volume_ratio=0.0,
                        call_volume=flow.total_call_volume,
                        put_volume=flow.total_put_volume,
                        put_call_ratio=float(flow.put_call_ratio),
                        confidence=confidence,
                        reason=f"Smart money call buying: {aggression_ratio*100:.0f}% at ask"
                    )

        except Exception as e:
            # Silently skip if options data unavailable (401 = requires paid subscription)
            error_msg = str(e)
            if "401" not in error_msg:
                # Only print non-auth errors
                print(f"Warning: Failed to check options for {ticker}: {e}")
            return None

        return None

    def close(self):
        """Close connections."""
        if hasattr(self, 'options_flow'):
            self.options_flow.close()
