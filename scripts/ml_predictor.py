"""
ML Predictor - Load trained CatBoost models and generate predictions
"""
import os
import sys
import yaml
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from catboost import CatBoostClassifier
from src.data.storage.market_data_db import MarketDataDB
from ml_feature_engineering import FeatureEngineering


class MLPredictor:
    """Load and use trained CatBoost models for predictions"""

    def __init__(self, models_dir: str = "models/catboost", ticker_configs_dir: str = "config/tickers"):
        self.models_dir = Path(models_dir)
        self.ticker_configs_dir = Path(ticker_configs_dir)
        self.models: Dict[str, CatBoostClassifier] = {}
        self.metadata: Dict[str, dict] = {}
        self.ticker_configs: Dict[str, dict] = {}
        self.db = MarketDataDB()
        self.fe = FeatureEngineering(self.db)

        # Load all available models
        self._load_all_models()

    def _load_all_models(self):
        """Load all trained models from disk"""
        if not self.models_dir.exists():
            print(f"WARNING: Models directory not found: {self.models_dir}")
            return

        model_files = list(self.models_dir.glob("*.cbm"))
        print(f"Loading {len(model_files)} CatBoost models...")

        for model_path in model_files:
            symbol = model_path.stem  # e.g., "NVDA" from "NVDA.cbm"
            try:
                # Load model
                model = CatBoostClassifier()
                model.load_model(str(model_path))
                self.models[symbol] = model

                # Load metadata
                metadata_path = self.models_dir / f"{symbol}_metadata.pkl"
                if metadata_path.exists():
                    with open(metadata_path, 'rb') as f:
                        self.metadata[symbol] = pickle.load(f)

                print(f"  OK {symbol}: AUC={self.metadata[symbol].get('auc', 0):.4f}")
            except Exception as e:
                print(f"  FAIL {symbol}: Failed to load - {e}")

        print(f"Successfully loaded {len(self.models)} models\n")

    def load_ticker_config(self, symbol: str) -> dict:
        """Load per-ticker configuration"""
        if symbol in self.ticker_configs:
            return self.ticker_configs[symbol]

        config_path = self.ticker_configs_dir / f"{symbol}.yaml"
        if not config_path.exists():
            config_path = self.ticker_configs_dir / "default.yaml"

        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                self.ticker_configs[symbol] = config
                return config
        except Exception as e:
            print(f"WARNING: Could not load config for {symbol}: {e}")
            return {}

    def predict(self, symbol: str, date: str) -> Optional[Tuple[float, dict]]:
        """
        Generate ML prediction for a symbol on a specific date

        Args:
            symbol: Stock symbol
            date: Date in YYYY-MM-DD format

        Returns:
            (confidence, details) tuple or None if prediction not available
            - confidence: Float 0-1 representing ML confidence
            - details: Dict with prediction metadata
        """
        # Check if model exists
        if symbol not in self.models:
            return None

        # Get metadata and feature columns
        metadata = self.metadata.get(symbol, {})
        feature_cols = metadata.get('feature_cols', [])
        if not feature_cols:
            return None

        # Calculate features for this date
        # Need historical data to calculate indicators
        try:
            df = self.fe.calculate_technical_indicators(symbol, date, date)
            if df.empty or date not in df.index.strftime('%Y-%m-%d').values:
                return None

            # Get features for this date
            features = df.loc[date, feature_cols]

            # Handle missing features
            if features.isna().any():
                return None

            # Make prediction
            model = self.models[symbol]
            confidence = model.predict_proba([features])[0, 1]  # Probability of positive class

            details = {
                'symbol': symbol,
                'date': date,
                'confidence': float(confidence),
                'model_auc': metadata.get('auc', 0),
                'target_return': metadata.get('target_return', 0.10),
                'target_days': metadata.get('target_days', 10)
            }

            return confidence, details

        except Exception as e:
            # print(f"WARNING: Prediction failed for {symbol} on {date}: {e}")
            return None

    def get_top_predictions(self, date: str, min_confidence: float = 0.75, top_n: int = 10) -> list:
        """
        Get top N predictions across all tickers for a given date

        Args:
            date: Date in YYYY-MM-DD format
            min_confidence: Minimum ML confidence threshold
            top_n: Number of top predictions to return

        Returns:
            List of (symbol, confidence, details) sorted by confidence
        """
        predictions = []

        for symbol in self.models.keys():
            result = self.predict(symbol, date)
            if result:
                confidence, details = result
                if confidence >= min_confidence:
                    predictions.append((symbol, confidence, details))

        # Sort by confidence descending
        predictions.sort(key=lambda x: x[1], reverse=True)

        return predictions[:top_n]

    def get_ticker_threshold(self, symbol: str) -> float:
        """
        Get optimal confidence threshold for a ticker from its config

        Args:
            symbol: Stock symbol

        Returns:
            Confidence threshold (0.0 - 1.0)
        """
        config = self.load_ticker_config(symbol)
        return config.get('min_ml_confidence', 0.75)

    def is_signal_valid(self, symbol: str, date: str, market_regime: str = 'NEUTRAL', vix: float = 20.0) -> bool:
        """
        Check if ML signal is valid based on ticker-specific rules

        Args:
            symbol: Stock symbol
            date: Date in YYYY-MM-DD format
            market_regime: Current market regime (BULLISH/NEUTRAL/BEARISH)
            vix: Current VIX level

        Returns:
            True if signal meets all criteria
        """
        # Get prediction
        result = self.predict(symbol, date)
        if not result:
            return False

        confidence, details = result

        # Get ticker config
        config = self.load_ticker_config(symbol)

        # Check ML confidence threshold
        min_confidence = config.get('min_ml_confidence', 0.75)
        if confidence < min_confidence:
            return False

        # Check VIX threshold
        max_vix = config.get('max_vix_for_entry', 30)
        if vix > max_vix:
            return False

        # Check preferred regimes
        preferred_regimes = config.get('preferred_regimes', ['BULLISH'])
        if market_regime not in preferred_regimes:
            return False

        return True


def main():
    """Test ML predictor"""
    predictor = MLPredictor()

    # Test prediction for NVDA on a specific date
    symbol = 'NVDA'
    test_date = '2024-01-10'

    print(f"\n{'='*60}")
    print(f"Testing ML Prediction for {symbol} on {test_date}")
    print(f"{'='*60}\n")

    result = predictor.predict(symbol, test_date)
    if result:
        confidence, details = result
        print(f"Prediction: {confidence:.1%} confidence")
        print(f"Model AUC: {details['model_auc']:.4f}")
        print(f"Target: {details['target_return']*100:.0f}% gain in {details['target_days']} days")

        # Check if signal is valid
        is_valid = predictor.is_signal_valid(symbol, test_date, market_regime='BULLISH', vix=15.0)
        print(f"Signal Valid: {'YES' if is_valid else 'NO'}")
    else:
        print(f"No prediction available for {symbol} on {test_date}")

    # Test top predictions
    print(f"\n{'='*60}")
    print(f"Top 10 Predictions for {test_date}")
    print(f"{'='*60}\n")

    top_preds = predictor.get_top_predictions(test_date, min_confidence=0.60, top_n=10)

    if top_preds:
        print(f"{'Symbol':<8} {'Confidence':<12} {'Model AUC':<12}")
        print("-" * 40)
        for symbol, conf, details in top_preds:
            print(f"{symbol:<8} {conf:>10.1%}   {details['model_auc']:>10.4f}")
    else:
        print("No predictions above confidence threshold")


if __name__ == "__main__":
    main()
