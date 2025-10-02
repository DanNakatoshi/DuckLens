"""
Options Flow Indicators Calculator.

Calculates derived metrics from raw options flow data for CatBoost feature engineering.
These indicators help identify market sentiment, smart money positioning, and trend signals.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pandas as pd

from src.data.storage.market_data_db import MarketDataDB
from src.models.schemas import OptionsFlowIndicators


class OptionsFlowAnalyzer:
    """Calculate options flow indicators for machine learning."""

    def __init__(self, db: MarketDataDB | None = None):
        """
        Initialize analyzer.

        Args:
            db: Database connection (creates new if None)
        """
        self.db = db or MarketDataDB()
        self.should_close_db = db is None

    def __enter__(self) -> "OptionsFlowAnalyzer":
        return self

    def __exit__(self, *args: object) -> None:
        if self.should_close_db and self.db:
            self.db.close()

    def calculate_all_indicators(
        self, ticker: str, start_date: datetime | None = None, end_date: datetime | None = None
    ) -> list[OptionsFlowIndicators]:
        """
        Calculate all options flow indicators for a ticker.

        Args:
            ticker: Stock ticker symbol
            start_date: Start date for calculation
            end_date: End date for calculation

        Returns:
            List of OptionsFlowIndicators objects
        """
        # Load flow data from database
        flow_df = self._load_flow_data(ticker, start_date, end_date)

        if flow_df.empty:
            return []

        # Calculate all derived metrics
        indicators = []

        for idx, row in flow_df.iterrows():
            date = row["date"]

            # Get historical data for rolling calculations
            hist_df = flow_df[flow_df["date"] <= date].tail(252)  # Last year

            indicator = OptionsFlowIndicators(
                ticker=ticker,
                date=date,
                # Sentiment indicators
                put_call_ratio=Decimal(str(row["put_call_ratio"])),
                put_call_ratio_ma5=self._calculate_pc_ma(hist_df, window=5),
                put_call_ratio_percentile=self._calculate_pc_percentile(
                    row["put_call_ratio"], hist_df
                ),
                # Smart money flow
                smart_money_index=self._calculate_smart_money_index(row),
                oi_momentum=self._calculate_oi_momentum(row),
                unusual_activity_score=Decimal(
                    str(row["unusual_call_contracts"] + row["unusual_put_contracts"])
                ),
                # Volatility features
                iv_rank=self._calculate_iv_rank(row, hist_df),
                iv_skew=self._calculate_iv_skew(row),
                # Directional bias
                delta_weighted_volume=self._calculate_delta_weighted_volume(row),
                gamma_exposure=(
                    Decimal(str(row["net_gamma"])) if row["net_gamma"] is not None else None
                ),
                # Support/resistance
                max_pain_distance=self._calculate_max_pain_distance(ticker, date, row),
                high_oi_call_strike=self._find_high_oi_strike(ticker, date, "call"),
                high_oi_put_strike=self._find_high_oi_strike(ticker, date, "put"),
                # Time features
                days_to_nearest_expiry=self._calculate_days_to_expiry(ticker, date),
                # Overall signal
                flow_signal=self._generate_flow_signal(row, hist_df),
            )

            indicators.append(indicator)

        return indicators

    def _load_flow_data(
        self, ticker: str, start_date: datetime | None, end_date: datetime | None
    ) -> pd.DataFrame:
        """Load options flow data from database."""
        query = "SELECT * FROM options_flow_daily WHERE ticker = ?"
        params = [ticker]

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)

        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date ASC"

        result = self.db.conn.execute(query, params).fetchdf()
        return result

    def _calculate_pc_ma(self, hist_df: pd.DataFrame, window: int = 5) -> Decimal | None:
        """Calculate moving average of put/call ratio."""
        if len(hist_df) < window:
            return None

        pc_ratios = hist_df["put_call_ratio"].tail(window)
        ma = pc_ratios.mean()

        return Decimal(str(ma)) if pd.notna(ma) else None

    def _calculate_pc_percentile(self, current_pc: float, hist_df: pd.DataFrame) -> Decimal | None:
        """Calculate percentile rank of current P/C ratio vs historical."""
        if len(hist_df) < 20:
            return None

        pc_ratios = hist_df["put_call_ratio"]
        percentile = (pc_ratios < current_pc).sum() / len(pc_ratios) * 100

        return Decimal(str(percentile))

    def _calculate_smart_money_index(self, row: pd.Series) -> Decimal | None:
        """
        Calculate smart money index.

        Formula: (Call Volume at Ask - Put Volume at Ask) / Total Volume
        Positive = Bullish aggression, Negative = Bearish aggression
        """
        total_volume = row["total_call_volume"] + row["total_put_volume"]

        if total_volume == 0:
            return None

        call_at_ask = row["call_volume_at_ask"]
        put_at_ask = row["put_volume_at_ask"]

        index = (call_at_ask - put_at_ask) / total_volume

        return Decimal(str(index))

    def _calculate_oi_momentum(self, row: pd.Series) -> Decimal | None:
        """
        Calculate open interest momentum.

        Formula: (Today Total OI - Yesterday Total OI) / Yesterday Total OI
        Positive = Accumulation, Negative = Distribution
        """
        total_oi = row["total_call_oi"] + row["total_put_oi"]
        oi_change = row["call_oi_change"] + row["put_oi_change"]

        if total_oi == 0 or oi_change == 0:
            return None

        yesterday_oi = total_oi - oi_change

        if yesterday_oi == 0:
            return None

        momentum = oi_change / yesterday_oi

        return Decimal(str(momentum))

    def _calculate_iv_rank(self, row: pd.Series, hist_df: pd.DataFrame) -> Decimal | None:
        """
        Calculate IV Rank.

        Formula: (Current IV - 52w Low) / (52w High - 52w Low) * 100
        0 = Lowest IV in year, 100 = Highest IV in year
        """
        # Use average of call and put IV
        current_call_iv = row["avg_call_iv"]
        current_put_iv = row["avg_put_iv"]

        if current_call_iv is None or current_put_iv is None:
            return None

        current_iv = (current_call_iv + current_put_iv) / 2

        # Get 52-week range
        hist_call_iv = hist_df["avg_call_iv"].dropna()
        hist_put_iv = hist_df["avg_put_iv"].dropna()

        if hist_call_iv.empty or hist_put_iv.empty:
            return None

        hist_avg_iv = (hist_call_iv + hist_put_iv) / 2

        iv_low = hist_avg_iv.min()
        iv_high = hist_avg_iv.max()

        if iv_high == iv_low:
            return Decimal("50")  # Default to middle

        iv_rank = (current_iv - iv_low) / (iv_high - iv_low) * 100

        return Decimal(str(iv_rank))

    def _calculate_iv_skew(self, row: pd.Series) -> Decimal | None:
        """
        Calculate IV Skew (fear gauge).

        Formula: Put IV - Call IV
        Positive = Puts more expensive (fear), Negative = Calls more expensive (greed)
        """
        put_iv = row["avg_put_iv"]
        call_iv = row["avg_call_iv"]

        if put_iv is None or call_iv is None:
            return None

        skew = put_iv - call_iv

        return Decimal(str(skew))

    def _calculate_delta_weighted_volume(self, row: pd.Series) -> Decimal | None:
        """
        Calculate delta-weighted volume (directional exposure).

        This is already calculated as net_delta in the flow data.
        """
        net_delta = row["net_delta"]

        return Decimal(str(net_delta)) if net_delta is not None else None

    def _calculate_max_pain_distance(
        self, ticker: str, date: datetime, row: pd.Series
    ) -> Decimal | None:
        """
        Calculate distance from current price to max pain.

        Formula: (Current Price - Max Pain) / Current Price
        Positive = Price above max pain, Negative = Price below max pain
        """
        max_pain = row["max_pain_price"]

        if max_pain is None:
            return None

        # Get current price from stock_prices table
        price_query = """
            SELECT close
            FROM stock_prices
            WHERE symbol = ? AND DATE(timestamp) = DATE(?)
            ORDER BY timestamp DESC
            LIMIT 1
        """

        result = self.db.conn.execute(price_query, [ticker, date]).fetchone()

        if not result or result[0] is None:
            return None

        current_price = result[0]

        if current_price == 0:
            return None

        distance = (current_price - float(max_pain)) / current_price

        return Decimal(str(distance))

    def _find_high_oi_strike(
        self, ticker: str, date: datetime, contract_type: str
    ) -> Decimal | None:
        """
        Find strike price with highest open interest.

        Args:
            ticker: Underlying ticker
            date: Date to check
            contract_type: "call" or "put"

        Returns:
            Strike price with highest OI
        """
        query = """
            SELECT strike_price, SUM(open_interest) as total_oi
            FROM options_contracts_snapshot
            WHERE underlying_ticker = ?
              AND snapshot_date = DATE(?)
              AND contract_type = ?
              AND open_interest IS NOT NULL
            GROUP BY strike_price
            ORDER BY total_oi DESC
            LIMIT 1
        """

        result = self.db.conn.execute(query, [ticker, date, contract_type]).fetchone()

        if not result:
            return None

        return Decimal(str(result[0]))

    def _calculate_days_to_expiry(self, ticker: str, date: datetime) -> int | None:
        """
        Calculate days to nearest contract expiration.

        Args:
            ticker: Underlying ticker
            date: Current date

        Returns:
            Days to nearest expiry
        """
        query = """
            SELECT MIN(expiration_date) as nearest_expiry
            FROM options_contracts_snapshot
            WHERE underlying_ticker = ?
              AND snapshot_date = DATE(?)
              AND expiration_date > DATE(?)
        """

        result = self.db.conn.execute(query, [ticker, date, date]).fetchone()

        if not result or result[0] is None:
            return None

        nearest_expiry = datetime.fromisoformat(str(result[0]))
        days = (nearest_expiry - date).days

        return days

    def _generate_flow_signal(self, row: pd.Series, hist_df: pd.DataFrame) -> str:
        """
        Generate overall options flow signal.

        Combines multiple factors:
        - Put/Call ratio (>1.2 bearish, <0.8 bullish)
        - Smart money index (positive bullish, negative bearish)
        - OI momentum (positive bullish, negative bearish)
        - Unusual activity (high activity = strong signal)

        Returns:
            "BULLISH", "BEARISH", or "NEUTRAL"
        """
        score = 0

        # Put/Call ratio (-2 to +2)
        pc_ratio = row["put_call_ratio"]
        if pc_ratio > 1.2:
            score -= 2  # Very bearish
        elif pc_ratio > 1.0:
            score -= 1  # Slightly bearish
        elif pc_ratio < 0.8:
            score += 2  # Very bullish
        elif pc_ratio < 1.0:
            score += 1  # Slightly bullish

        # Smart money index (-1 to +1)
        total_vol = row["total_call_volume"] + row["total_put_volume"]
        if total_vol > 0:
            call_at_ask = row["call_volume_at_ask"]
            put_at_ask = row["put_volume_at_ask"]
            smi = (call_at_ask - put_at_ask) / total_vol

            if smi > 0.1:
                score += 1  # Bullish aggression
            elif smi < -0.1:
                score -= 1  # Bearish aggression

        # OI momentum (-1 to +1)
        oi_change = row["call_oi_change"] + row["put_oi_change"]
        total_oi = row["total_call_oi"] + row["total_put_oi"]

        if total_oi > 0:
            oi_pct = oi_change / total_oi

            if oi_pct > 0.05:
                score += 1  # Accumulation
            elif oi_pct < -0.05:
                score -= 1  # Distribution

        # Unusual activity booster (0.5x multiplier)
        unusual = row["unusual_call_contracts"] + row["unusual_put_contracts"]
        if unusual > 10:
            score *= 1.5  # Amplify signal with high unusual activity

        # Generate signal
        if score >= 2:
            return "BULLISH"
        elif score <= -2:
            return "BEARISH"
        else:
            return "NEUTRAL"
