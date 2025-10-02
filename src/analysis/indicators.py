"""Technical indicators calculator using stored OHLCV data."""

from datetime import datetime
from typing import Literal

import pandas as pd

from src.data.storage.market_data_db import MarketDataDB


class TechnicalIndicators:
    """Calculate technical indicators from stored price data."""

    def __init__(self, db_path: str | None = None):
        """Initialize with database connection."""
        self.db = MarketDataDB(db_path)

    def __enter__(self) -> "TechnicalIndicators":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close database connection."""
        self.db.close()

    def _get_price_data(
        self,
        symbol: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """
        Get price data as pandas DataFrame.

        Args:
            symbol: Stock symbol
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            DataFrame with OHLCV data
        """
        data = self.db.get_stock_prices(symbol, start_date, end_date)
        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp")
        df.set_index("timestamp", inplace=True)

        return df

    def calculate_sma(
        self,
        symbol: str,
        window: int = 50,
        price_column: Literal["open", "high", "low", "close"] = "close",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.Series:
        """
        Calculate Simple Moving Average (SMA).

        Args:
            symbol: Stock symbol
            window: Number of periods (default 50)
            price_column: Which price to use (default 'close')
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            Series with SMA values
        """
        df = self._get_price_data(symbol, start_date, end_date)
        if df.empty:
            return pd.Series(dtype=float)

        sma = df[price_column].rolling(window=window, min_periods=window).mean()
        return sma.dropna()

    def calculate_ema(
        self,
        symbol: str,
        window: int = 20,
        price_column: Literal["open", "high", "low", "close"] = "close",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.Series:
        """
        Calculate Exponential Moving Average (EMA).

        Args:
            symbol: Stock symbol
            window: Number of periods (default 20)
            price_column: Which price to use (default 'close')
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            Series with EMA values
        """
        df = self._get_price_data(symbol, start_date, end_date)
        if df.empty:
            return pd.Series(dtype=float)

        ema = df[price_column].ewm(span=window, adjust=False, min_periods=window).mean()
        return ema.dropna()

    def calculate_macd(
        self,
        symbol: str,
        short_window: int = 12,
        long_window: int = 26,
        signal_window: int = 9,
        price_column: Literal["open", "high", "low", "close"] = "close",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """
        Calculate MACD (Moving Average Convergence Divergence).

        Args:
            symbol: Stock symbol
            short_window: Short EMA period (default 12)
            long_window: Long EMA period (default 26)
            signal_window: Signal line EMA period (default 9)
            price_column: Which price to use (default 'close')
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            DataFrame with columns: macd, signal, histogram
        """
        df = self._get_price_data(symbol, start_date, end_date)
        if df.empty:
            return pd.DataFrame()

        # Calculate short and long EMAs
        short_ema = df[price_column].ewm(span=short_window, adjust=False).mean()
        long_ema = df[price_column].ewm(span=long_window, adjust=False).mean()

        # MACD line
        macd_line = short_ema - long_ema

        # Signal line
        signal_line = macd_line.ewm(span=signal_window, adjust=False).mean()

        # Histogram
        histogram = macd_line - signal_line

        result = pd.DataFrame({"macd": macd_line, "signal": signal_line, "histogram": histogram})

        return result.dropna()

    def calculate_rsi(
        self,
        symbol: str,
        window: int = 14,
        price_column: Literal["open", "high", "low", "close"] = "close",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.Series:
        """
        Calculate Relative Strength Index (RSI).

        Args:
            symbol: Stock symbol
            window: Number of periods (default 14)
            price_column: Which price to use (default 'close')
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            Series with RSI values (0-100)
        """
        df = self._get_price_data(symbol, start_date, end_date)
        if df.empty:
            return pd.Series(dtype=float)

        # Calculate price changes
        delta = df[price_column].diff()

        # Separate gains and losses
        gains = delta.where(delta > 0, 0)
        losses = -delta.where(delta < 0, 0)

        # Calculate average gains and losses
        avg_gains = gains.rolling(window=window, min_periods=window).mean()
        avg_losses = losses.rolling(window=window, min_periods=window).mean()

        # Calculate RS and RSI
        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))

        return rsi.dropna()

    def calculate_bollinger_bands(
        self,
        symbol: str,
        window: int = 20,
        num_std: float = 2.0,
        price_column: Literal["open", "high", "low", "close"] = "close",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """
        Calculate Bollinger Bands.

        Args:
            symbol: Stock symbol
            window: Number of periods (default 20)
            num_std: Number of standard deviations (default 2.0)
            price_column: Which price to use (default 'close')
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            DataFrame with columns: middle, upper, lower
        """
        df = self._get_price_data(symbol, start_date, end_date)
        if df.empty:
            return pd.DataFrame()

        # Middle band (SMA)
        middle = df[price_column].rolling(window=window, min_periods=window).mean()

        # Standard deviation
        std = df[price_column].rolling(window=window, min_periods=window).std()

        # Upper and lower bands
        upper = middle + (std * num_std)
        lower = middle - (std * num_std)

        result = pd.DataFrame({"middle": middle, "upper": upper, "lower": lower})

        return result.dropna()

    def calculate_atr(
        self,
        symbol: str,
        window: int = 14,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.Series:
        """
        Calculate Average True Range (ATR).

        Args:
            symbol: Stock symbol
            window: Number of periods (default 14)
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            Series with ATR values
        """
        df = self._get_price_data(symbol, start_date, end_date)
        if df.empty:
            return pd.Series(dtype=float)

        # Calculate True Range components
        high_low = df["high"] - df["low"]
        high_close = abs(df["high"] - df["close"].shift())
        low_close = abs(df["low"] - df["close"].shift())

        # True Range is the maximum of the three
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

        # ATR is the moving average of True Range
        atr = true_range.rolling(window=window, min_periods=window).mean()

        return atr.dropna()

    def calculate_stochastic(
        self,
        symbol: str,
        k_window: int = 14,
        d_window: int = 3,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """
        Calculate Stochastic Oscillator.

        Args:
            symbol: Stock symbol
            k_window: %K period (default 14)
            d_window: %D period (default 3)
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            DataFrame with columns: k, d
        """
        df = self._get_price_data(symbol, start_date, end_date)
        if df.empty:
            return pd.DataFrame()

        # Calculate %K
        low_min = df["low"].rolling(window=k_window, min_periods=k_window).min()
        high_max = df["high"].rolling(window=k_window, min_periods=k_window).max()

        k = 100 * (df["close"] - low_min) / (high_max - low_min)

        # Calculate %D (SMA of %K)
        d = k.rolling(window=d_window, min_periods=d_window).mean()

        result = pd.DataFrame({"k": k, "d": d})

        return result.dropna()

    def calculate_obv(
        self,
        symbol: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.Series:
        """
        Calculate On-Balance Volume (OBV).

        Args:
            symbol: Stock symbol
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            Series with OBV values
        """
        df = self._get_price_data(symbol, start_date, end_date)
        if df.empty:
            return pd.Series(dtype=float)

        # Price direction
        price_change = df["close"].diff()

        # OBV calculation
        obv = (price_change > 0).astype(int) * df["volume"] - (price_change < 0).astype(int) * df[
            "volume"
        ]

        obv = obv.cumsum()

        return obv

    def calculate_all_indicators(
        self,
        symbol: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """
        Calculate all indicators at once and return as DataFrame.

        Args:
            symbol: Stock symbol
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            DataFrame with all indicators
        """
        df = self._get_price_data(symbol, start_date, end_date)
        if df.empty:
            return pd.DataFrame()

        result = df.copy()

        # Moving averages
        result["sma_20"] = self.calculate_sma(symbol, 20, start_date=start_date, end_date=end_date)
        result["sma_50"] = self.calculate_sma(symbol, 50, start_date=start_date, end_date=end_date)
        result["sma_200"] = self.calculate_sma(
            symbol, 200, start_date=start_date, end_date=end_date
        )
        result["ema_12"] = self.calculate_ema(symbol, 12, start_date=start_date, end_date=end_date)
        result["ema_26"] = self.calculate_ema(symbol, 26, start_date=start_date, end_date=end_date)

        # MACD
        macd = self.calculate_macd(symbol, start_date=start_date, end_date=end_date)
        result = result.join(macd)

        # RSI
        result["rsi_14"] = self.calculate_rsi(symbol, start_date=start_date, end_date=end_date)

        # Bollinger Bands
        bb = self.calculate_bollinger_bands(symbol, start_date=start_date, end_date=end_date)
        result = result.join(bb, rsuffix="_bb")

        # ATR
        result["atr_14"] = self.calculate_atr(symbol, start_date=start_date, end_date=end_date)

        # Stochastic
        stoch = self.calculate_stochastic(symbol, start_date=start_date, end_date=end_date)
        result = result.join(stoch, rsuffix="_stoch")

        # OBV
        result["obv"] = self.calculate_obv(symbol, start_date=start_date, end_date=end_date)

        return result.dropna(how="all", axis=1)
