"""
CatBoost Feature Engineering Pipeline
Extracts ML features from DuckDB for per-ticker model training
"""
import os
import sys
import yaml
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.storage.market_data_db import MarketDataDB


class FeatureEngineering:
    """Extract and calculate ML features for stock prediction"""

    def __init__(self, db: MarketDataDB):
        self.db = db

    def calculate_technical_indicators(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Calculate all technical indicators for a symbol
        Returns DataFrame with features for ML training
        """

        # Fetch price data with extra history for indicator calculation
        lookback_days = 200  # Need history for 200-day MA
        adjusted_start = (datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

        query = """
            SELECT
                DATE(timestamp) as date,
                open, high, low, close, volume
            FROM stock_prices
            WHERE symbol = ?
            AND DATE(timestamp) BETWEEN ? AND ?
            ORDER BY timestamp ASC
        """

        result = self.db.conn.execute(query, [symbol, adjusted_start, end_date]).fetchall()

        if not result:
            return pd.DataFrame()

        # Convert to DataFrame and fix Decimal types
        df = pd.DataFrame(result, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')

        # Convert Decimal to float (DuckDB returns Decimal type)
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)

        # Calculate features
        self._add_price_features(df)
        self._add_volume_features(df)
        self._add_volatility_features(df)
        self._add_momentum_features(df)
        self._add_trend_features(df)

        # Filter to requested date range
        df = df[df.index >= start_date]

        return df

    def _add_price_features(self, df: pd.DataFrame):
        """Add price-based features"""
        # Moving averages
        df['MA_5'] = df['close'].rolling(5).mean()
        df['MA_10'] = df['close'].rolling(10).mean()
        df['MA_20'] = df['close'].rolling(20).mean()
        df['MA_50'] = df['close'].rolling(50).mean()
        df['MA_200'] = df['close'].rolling(200).mean()

        # Price relative to MAs
        df['PRICE_VS_MA_5'] = (df['close'] - df['MA_5']) / df['MA_5']
        df['PRICE_VS_MA_20'] = (df['close'] - df['MA_20']) / df['MA_20']
        df['PRICE_VS_MA_50'] = (df['close'] - df['MA_50']) / df['MA_50']
        df['PRICE_VS_MA_200'] = (df['close'] - df['MA_200']) / df['MA_200']

        # Bollinger Bands
        df['BB_MIDDLE'] = df['close'].rolling(20).mean()
        df['BB_STD'] = df['close'].rolling(20).std()
        df['BB_UPPER'] = df['BB_MIDDLE'] + 2 * df['BB_STD']
        df['BB_LOWER'] = df['BB_MIDDLE'] - 2 * df['BB_STD']
        df['BB_PCT'] = (df['close'] - df['BB_LOWER']) / (df['BB_UPPER'] - df['BB_LOWER'])

        # Support/Resistance
        df['HIGH_20'] = df['high'].rolling(20).max()
        df['LOW_20'] = df['low'].rolling(20).min()
        df['PRICE_VS_HIGH_20'] = (df['close'] - df['HIGH_20']) / df['HIGH_20']
        df['PRICE_VS_LOW_20'] = (df['close'] - df['LOW_20']) / df['LOW_20']

    def _add_volume_features(self, df: pd.DataFrame):
        """Add volume-based features"""
        df['VOLUME_MA_20'] = df['volume'].rolling(20).mean()
        df['VOLUME_RATIO_20'] = df['volume'] / df['VOLUME_MA_20']

        # Volume trend
        df['VOLUME_TREND_5'] = df['volume'].rolling(5).mean() / df['volume'].rolling(20).mean()

        # On-Balance Volume (OBV)
        df['PRICE_CHANGE'] = df['close'].diff()
        df['OBV'] = (np.sign(df['PRICE_CHANGE']) * df['volume']).cumsum()
        df['OBV_MA_20'] = df['OBV'].rolling(20).mean()
        df['OBV_TREND'] = (df['OBV'] - df['OBV_MA_20']) / df['OBV_MA_20'].abs()

    def _add_volatility_features(self, df: pd.DataFrame):
        """Add volatility features"""
        # ATR (Average True Range)
        df['TR'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        df['ATR_14'] = df['TR'].rolling(14).mean()
        df['ATR_20'] = df['TR'].rolling(20).mean()
        df['ATR_PCT'] = df['ATR_14'] / df['close']

        # Historical volatility
        df['VOLATILITY_20'] = df['close'].pct_change().rolling(20).std() * np.sqrt(252)
        df['VOLATILITY_50'] = df['close'].pct_change().rolling(50).std() * np.sqrt(252)

    def _add_momentum_features(self, df: pd.DataFrame):
        """Add momentum indicators"""
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['RSI_14'] = 100 - (100 / (1 + rs))

        # MACD
        ema_12 = df['close'].ewm(span=12, adjust=False).mean()
        ema_26 = df['close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = ema_12 - ema_26
        df['MACD_SIGNAL'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_HIST'] = df['MACD'] - df['MACD_SIGNAL']

        # Momentum
        df['MOMENTUM_5'] = df['close'].pct_change(5)
        df['MOMENTUM_10'] = df['close'].pct_change(10)
        df['MOMENTUM_20'] = df['close'].pct_change(20)

        # Rate of Change
        df['ROC_10'] = (df['close'] - df['close'].shift(10)) / df['close'].shift(10) * 100

    def _add_trend_features(self, df: pd.DataFrame):
        """Add trend indicators"""
        # ADX (Average Directional Index)
        high_diff = df['high'].diff()
        low_diff = -df['low'].diff()

        plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
        minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)

        atr = df['ATR_14']
        plus_di = 100 * (plus_dm.rolling(14).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(14).mean() / atr)

        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        df['ADX'] = dx.rolling(14).mean()
        df['PLUS_DI'] = plus_di
        df['MINUS_DI'] = minus_di

        # Moving Average Cross
        df['MA_CROSS_SIGNAL'] = np.where(df['MA_5'] > df['MA_20'], 1, -1)
        df['MA_CROSS_STRENGTH'] = abs(df['MA_5'] - df['MA_20']) / df['MA_20']

    def create_training_dataset(self, symbol: str, start_date: str, end_date: str,
                               target_return: float = 0.10, target_days: int = 10) -> pd.DataFrame:
        """
        Create ML training dataset with features and target labels

        Args:
            symbol: Stock symbol
            start_date: Start date for training data
            end_date: End date for training data
            target_return: Target return percentage (e.g., 0.10 = 10%)
            target_days: Days to achieve target return

        Returns:
            DataFrame with features and binary target (1 = achieved target, 0 = did not)
        """
        # Get features
        df = self.calculate_technical_indicators(symbol, start_date, end_date)

        if df.empty:
            return df

        # Calculate target: Did price increase by target_return% within target_days?
        df['FUTURE_MAX'] = df['close'].rolling(target_days, min_periods=1).max().shift(-target_days)
        df['TARGET'] = ((df['FUTURE_MAX'] - df['close']) / df['close']) >= target_return
        df['TARGET'] = df['TARGET'].astype(int)

        # Also calculate actual return for regression models (optional)
        df['FUTURE_RETURN'] = ((df['FUTURE_MAX'] - df['close']) / df['close']) * 100

        # Drop rows with NaN targets (end of dataset)
        df = df[df['TARGET'].notna()]

        return df


def main():
    """Test feature engineering"""
    db = MarketDataDB()
    fe = FeatureEngineering(db)

    # Test on NVDA
    print("Generating features for NVDA (2020-2024)...")
    df = fe.create_training_dataset('NVDA', '2020-01-01', '2024-12-31', target_return=0.10, target_days=10)

    print(f"\nDataset shape: {df.shape}")
    print(f"Target distribution:\n{df['TARGET'].value_counts()}")
    print(f"\nFeature columns ({len(df.columns)}):")
    print(df.columns.tolist())

    print(f"\nSample data:")
    print(df[['close', 'RSI_14', 'MACD', 'ATR_14', 'VOLUME_RATIO_20', 'TARGET']].tail(10))

    # Show feature summary
    print(f"\nFeature summary:")
    print(df.describe())


if __name__ == "__main__":
    main()
