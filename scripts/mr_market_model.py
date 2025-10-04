"""
MrMarket - SPY Trend Prediction Model
Predicts SPY direction and magnitude 30 days ahead, re-evaluated daily
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Tuple
import pickle

from catboost import CatBoostClassifier, CatBoostRegressor, Pool
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import classification_report, accuracy_score, mean_absolute_error

from src.data.storage.market_data_db import MarketDataDB


class MrMarketModel:
    """Predict SPY market trend 30 days ahead"""

    def __init__(self, db: MarketDataDB):
        self.db = db
        self.direction_model = None  # Classification: UP or DOWN
        self.magnitude_model = None  # Regression: % move
        self.lookback_days = 60  # Use 60 days of history for features

    def create_features(self, spy_data: pd.DataFrame) -> pd.DataFrame:
        """
        Create features from SPY price data for trend prediction

        Features include:
        - Price momentum (5, 10, 20, 30 day returns)
        - Moving averages (relative position)
        - Volatility (historical vol)
        - Volume trends
        - Technical indicators (RSI, MACD)
        - Market breadth proxies
        """
        df = spy_data.copy()
        df = df.sort_index()

        # Price momentum features
        for period in [5, 10, 20, 30]:
            df[f'RETURN_{period}D'] = df['close'].pct_change(period)

        # Moving averages
        for period in [10, 20, 50, 200]:
            df[f'MA_{period}'] = df['close'].rolling(period).mean()
            df[f'PRICE_VS_MA_{period}'] = (df['close'] - df[f'MA_{period}']) / df[f'MA_{period}']

        # Volatility
        df['VOLATILITY_20'] = df['close'].pct_change().rolling(20).std() * np.sqrt(252)
        df['VOLATILITY_60'] = df['close'].pct_change().rolling(60).std() * np.sqrt(252)

        # Volume
        df['VOLUME_MA_20'] = df['volume'].rolling(20).mean()
        df['VOLUME_RATIO'] = df['volume'] / df['VOLUME_MA_20']

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

        # Trend strength
        df['ADX'] = self._calculate_adx(df)

        # Rate of change
        df['ROC_10'] = (df['close'] - df['close'].shift(10)) / df['close'].shift(10) * 100

        # Bollinger Bands
        df['BB_MIDDLE'] = df['close'].rolling(20).mean()
        df['BB_STD'] = df['close'].rolling(20).std()
        df['BB_UPPER'] = df['BB_MIDDLE'] + 2 * df['BB_STD']
        df['BB_LOWER'] = df['BB_MIDDLE'] - 2 * df['BB_STD']
        df['BB_PCT'] = (df['close'] - df['BB_LOWER']) / (df['BB_UPPER'] - df['BB_LOWER'])

        return df

    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average Directional Index (ADX)"""
        high_diff = df['high'].diff()
        low_diff = -df['low'].diff()

        plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
        minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)

        tr = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )

        atr = pd.Series(tr).rolling(period).mean()
        plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(period).mean() / atr)

        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(period).mean()

        return adx

    def create_training_data(self, start_date: str, end_date: str,
                            prediction_horizon: int = 30) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Create training dataset with features and targets

        Args:
            start_date: Start date for training data
            end_date: End date for training data
            prediction_horizon: Days ahead to predict (default 30)

        Returns:
            (features_df, targets_df) tuple
        """
        # Fetch SPY data with extra history for indicators
        adjusted_start = (datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=200)).strftime('%Y-%m-%d')

        query = """
            SELECT DATE(timestamp) as date, open, high, low, close, volume
            FROM stock_prices
            WHERE symbol = 'SPY'
            AND DATE(timestamp) BETWEEN ? AND ?
            ORDER BY timestamp ASC
        """

        result = self.db.conn.execute(query, [adjusted_start, end_date]).fetchall()

        if not result:
            raise ValueError("No SPY data found")

        # Create DataFrame
        df = pd.DataFrame(result, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')

        # Convert Decimal to float
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)

        # Create features
        df = self.create_features(df)

        # Create targets (future returns)
        df['FUTURE_CLOSE'] = df['close'].shift(-prediction_horizon)
        df['FUTURE_RETURN'] = (df['FUTURE_CLOSE'] - df['close']) / df['close'] * 100

        # Direction: 1 = UP, 0 = DOWN
        df['DIRECTION'] = (df['FUTURE_RETURN'] > 0).astype(int)

        # Filter to requested date range
        df = df[df.index >= start_date]

        # Drop rows with NaN targets (end of dataset)
        df = df.dropna(subset=['FUTURE_RETURN', 'DIRECTION'])

        # Separate features and targets
        feature_cols = [col for col in df.columns if col not in
                       ['open', 'high', 'low', 'close', 'volume', 'FUTURE_CLOSE',
                        'FUTURE_RETURN', 'DIRECTION', 'MA_10', 'MA_20', 'MA_50', 'MA_200',
                        'VOLUME_MA_20', 'BB_MIDDLE', 'BB_STD', 'BB_UPPER', 'BB_LOWER']]

        features = df[feature_cols].copy()
        targets = df[['FUTURE_RETURN', 'DIRECTION']].copy()

        return features, targets

    def train_models(self, start_date: str, end_date: str, test_size: float = 0.2):
        """Train both direction and magnitude models"""
        print("="*80)
        print("TRAINING MRMARKET - SPY 30-DAY TREND PREDICTOR")
        print("="*80)
        print(f"Period: {start_date} to {end_date}")
        print(f"Prediction Horizon: 30 days")
        print()

        # Create training data
        print("Creating features...")
        features, targets = self.create_training_data(start_date, end_date, prediction_horizon=30)

        print(f"Dataset: {len(features)} samples, {len(features.columns)} features")
        print(f"Features: {', '.join(features.columns[:10])}...")
        print()

        # Split data (time-series preserving)
        split_idx = int(len(features) * (1 - test_size))
        X_train, X_test = features.iloc[:split_idx], features.iloc[split_idx:]
        y_direction_train, y_direction_test = targets['DIRECTION'].iloc[:split_idx], targets['DIRECTION'].iloc[split_idx:]
        y_magnitude_train, y_magnitude_test = targets['FUTURE_RETURN'].iloc[:split_idx], targets['FUTURE_RETURN'].iloc[split_idx:]

        print(f"Train: {len(X_train)} samples")
        print(f"Test:  {len(X_test)} samples")
        print()

        # Train Direction Model (Classification)
        print("Training DIRECTION model (UP/DOWN)...")
        self.direction_model = CatBoostClassifier(
            iterations=300,
            learning_rate=0.05,
            depth=6,
            loss_function='Logloss',
            eval_metric='Accuracy',
            random_seed=42,
            verbose=False,
            early_stopping_rounds=50
        )

        train_pool = Pool(X_train, y_direction_train)
        test_pool = Pool(X_test, y_direction_test)

        self.direction_model.fit(train_pool, eval_set=test_pool, verbose=50)

        # Evaluate direction
        y_pred_direction = self.direction_model.predict(X_test)
        accuracy = accuracy_score(y_direction_test, y_pred_direction)

        print(f"\nDirection Model Accuracy: {accuracy:.1%}")
        print("\nClassification Report:")
        print(classification_report(y_direction_test, y_pred_direction,
                                   target_names=['DOWN', 'UP']))

        # Train Magnitude Model (Regression)
        print("\nTraining MAGNITUDE model (% return)...")
        self.magnitude_model = CatBoostRegressor(
            iterations=300,
            learning_rate=0.05,
            depth=6,
            loss_function='MAE',
            random_seed=42,
            verbose=False,
            early_stopping_rounds=50
        )

        train_pool_reg = Pool(X_train, y_magnitude_train)
        test_pool_reg = Pool(X_test, y_magnitude_test)

        self.magnitude_model.fit(train_pool_reg, eval_set=test_pool_reg, verbose=50)

        # Evaluate magnitude
        y_pred_magnitude = self.magnitude_model.predict(X_test)
        mae = mean_absolute_error(y_magnitude_test, y_pred_magnitude)

        print(f"\nMagnitude Model MAE: {mae:.2f}%")
        print(f"Average predicted move: {np.mean(np.abs(y_pred_magnitude)):.2f}%")
        print(f"Average actual move: {np.mean(np.abs(y_magnitude_test)):.2f}%")

        # Feature importance
        print("\n" + "="*80)
        print("TOP 10 MOST IMPORTANT FEATURES")
        print("="*80)

        importance = pd.DataFrame({
            'feature': features.columns,
            'importance': self.direction_model.feature_importances_
        }).sort_values('importance', ascending=False)

        print(importance.head(10).to_string(index=False))

        return {
            'direction_accuracy': accuracy,
            'magnitude_mae': mae,
            'train_samples': len(X_train),
            'test_samples': len(X_test)
        }

    def predict(self, date: str) -> Dict:
        """
        Predict SPY trend for 30 days from given date

        Returns:
            {
                'date': prediction date,
                'direction': 'UP' or 'DOWN',
                'direction_confidence': float (0-1),
                'predicted_return': float (% return),
                'recommendation': str
            }
        """
        if not self.direction_model or not self.magnitude_model:
            raise ValueError("Models not trained yet")

        # Get historical data for features
        end_date = date
        start_date = (datetime.strptime(date, '%Y-%m-%d') - timedelta(days=200)).strftime('%Y-%m-%d')

        query = """
            SELECT DATE(timestamp) as date, open, high, low, close, volume
            FROM stock_prices
            WHERE symbol = 'SPY'
            AND DATE(timestamp) BETWEEN ? AND ?
            ORDER BY timestamp ASC
        """

        result = self.db.conn.execute(query, [start_date, end_date]).fetchall()
        df = pd.DataFrame(result, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')

        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)

        # Create features
        df = self.create_features(df)

        # Get features for prediction date
        if date not in df.index.strftime('%Y-%m-%d').values:
            raise ValueError(f"No data available for {date}")

        features_row = df.loc[date]

        feature_cols = [col for col in df.columns if col not in
                       ['open', 'high', 'low', 'close', 'volume', 'MA_10', 'MA_20',
                        'MA_50', 'MA_200', 'VOLUME_MA_20', 'BB_MIDDLE', 'BB_STD',
                        'BB_UPPER', 'BB_LOWER']]

        features = features_row[feature_cols].values.reshape(1, -1)

        # Predict direction
        direction_proba = self.direction_model.predict_proba(features)[0]
        direction = 'UP' if direction_proba[1] > 0.5 else 'DOWN'
        confidence = direction_proba[1] if direction == 'UP' else direction_proba[0]

        # Predict magnitude
        predicted_return = self.magnitude_model.predict(features)[0]

        # Generate recommendation
        if direction == 'UP' and confidence > 0.65:
            recommendation = "BULLISH - Go Long"
        elif direction == 'DOWN' and confidence > 0.65:
            recommendation = "BEARISH - Go Short/Cash"
        else:
            recommendation = "NEUTRAL - Low Conviction"

        return {
            'date': date,
            'direction': direction,
            'direction_confidence': float(confidence),
            'predicted_return': float(predicted_return),
            'recommendation': recommendation
        }

    def save_models(self, output_dir: str = "models/mrmarket"):
        """Save trained models to disk"""
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        self.direction_model.save_model(f"{output_dir}/direction_model.cbm")
        self.magnitude_model.save_model(f"{output_dir}/magnitude_model.cbm")

        # Save metadata
        metadata = {
            'trained_at': datetime.now().isoformat(),
            'prediction_horizon': 30,
            'lookback_days': self.lookback_days
        }

        with open(f"{output_dir}/metadata.pkl", 'wb') as f:
            pickle.dump(metadata, f)

        print(f"\nModels saved to: {output_dir}")

    def load_models(self, model_dir: str = "models/mrmarket"):
        """Load trained models from disk"""
        self.direction_model = CatBoostClassifier()
        self.direction_model.load_model(f"{model_dir}/direction_model.cbm")

        self.magnitude_model = CatBoostRegressor()
        self.magnitude_model.load_model(f"{model_dir}/magnitude_model.cbm")

        print(f"Models loaded from: {model_dir}")


def main():
    """Train and test MrMarket model"""
    db = MarketDataDB()
    mr_market = MrMarketModel(db)

    # Train on historical data
    results = mr_market.train_models('2020-01-01', '2024-12-31', test_size=0.2)

    # Save models
    mr_market.save_models()

    # Test prediction
    print("\n" + "="*80)
    print("EXAMPLE PREDICTION")
    print("="*80)

    test_date = '2024-10-01'
    prediction = mr_market.predict(test_date)

    print(f"\nDate: {prediction['date']}")
    print(f"Direction: {prediction['direction']} (Confidence: {prediction['direction_confidence']:.1%})")
    print(f"Predicted 30-day return: {prediction['predicted_return']:+.2f}%")
    print(f"Recommendation: {prediction['recommendation']}")
    print()


if __name__ == "__main__":
    main()
