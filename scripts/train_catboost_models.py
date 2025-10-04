"""
Train CatBoost ML models per ticker
Creates models/catboost_{SYMBOL}.cbm files for each stock
"""
import os
import sys
import yaml
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from catboost import CatBoostClassifier, Pool
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix

from src.data.storage.market_data_db import MarketDataDB
from ml_feature_engineering import FeatureEngineering


class CatBoostTrainer:
    """Train and evaluate CatBoost models per ticker"""

    def __init__(self, models_dir: str = "models/catboost"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.db = MarketDataDB()
        self.fe = FeatureEngineering(self.db)

        # Features to use (exclude non-predictive columns)
        self.exclude_features = [
            'open', 'high', 'low', 'close', 'volume',  # Raw price/volume
            'FUTURE_MAX', 'TARGET', 'FUTURE_RETURN',   # Target variables
            'PRICE_CHANGE', 'OBV', 'OBV_MA_20',        # Calculated from features
            'TR', 'BB_MIDDLE', 'BB_STD', 'BB_UPPER', 'BB_LOWER'  # Redundant
        ]

    def train_model(self, symbol: str, start_date: str, end_date: str,
                   target_return: float = 0.10, target_days: int = 10,
                   test_size: float = 0.2) -> dict:
        """
        Train CatBoost model for a specific ticker

        Args:
            symbol: Stock symbol
            start_date: Training start date
            end_date: Training end date
            target_return: Target return for positive class (e.g., 0.10 = 10%)
            target_days: Days to achieve target
            test_size: Fraction of data for testing (0.2 = 20%)

        Returns:
            dict with model, metrics, and feature importance
        """
        print(f"\n{'='*60}")
        print(f"Training CatBoost model for {symbol}")
        print(f"{'='*60}")

        # Generate features
        print(f"Generating features from {start_date} to {end_date}...")
        df = self.fe.create_training_dataset(symbol, start_date, end_date, target_return, target_days)

        if df.empty or len(df) < 100:
            print(f"ERROR: Insufficient data for {symbol} ({len(df)} rows)")
            return None

        # Select features
        feature_cols = [col for col in df.columns if col not in self.exclude_features]
        X = df[feature_cols]
        y = df['TARGET']

        print(f"Dataset: {len(df)} samples, {len(feature_cols)} features")
        print(f"Target distribution: {y.value_counts().to_dict()}")
        print(f"Positive class: {y.sum()/len(y)*100:.1f}%")

        # Time series split (preserves temporal order)
        split_idx = int(len(df) * (1 - test_size))
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

        print(f"\nTrain: {len(X_train)} samples ({y_train.mean()*100:.1f}% positive)")
        print(f"Test:  {len(X_test)} samples ({y_test.mean()*100:.1f}% positive)")

        # Handle class imbalance
        pos_weight = (len(y_train) - y_train.sum()) / y_train.sum()
        print(f"Class weight: {pos_weight:.2f}")

        # Train CatBoost
        print("\nTraining CatBoost...")
        model = CatBoostClassifier(
            iterations=500,
            learning_rate=0.05,
            depth=6,
            loss_function='Logloss',
            eval_metric='AUC',
            random_seed=42,
            verbose=False,
            early_stopping_rounds=50,
            class_weights=[1, pos_weight]
        )

        # Create pools
        train_pool = Pool(X_train, y_train)
        test_pool = Pool(X_test, y_test)

        # Train
        model.fit(
            train_pool,
            eval_set=test_pool,
            verbose=100,
            plot=False
        )

        # Evaluate
        print("\n" + "="*60)
        print("EVALUATION RESULTS")
        print("="*60)

        y_pred = model.predict(X_test)
        y_pred_proba = model.predict_proba(X_test)[:, 1]

        # Metrics
        auc = roc_auc_score(y_test, y_pred_proba)
        print(f"\nAUC-ROC: {auc:.4f}")

        print("\nClassification Report:")
        print(classification_report(y_test, y_pred, target_names=['No Signal', 'BUY Signal']))

        print("\nConfusion Matrix:")
        cm = confusion_matrix(y_test, y_pred)
        print(cm)

        # Feature importance
        feature_importance = pd.DataFrame({
            'feature': feature_cols,
            'importance': model.feature_importances_
        }).sort_values('importance', ascending=False)

        print("\nTop 10 Most Important Features:")
        print(feature_importance.head(10).to_string(index=False))

        # Precision at different confidence thresholds
        print("\nPrecision at Different Confidence Thresholds:")
        for threshold in [0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9]:
            pred_at_threshold = (y_pred_proba >= threshold).astype(int)
            if pred_at_threshold.sum() > 0:
                precision = (y_test[pred_at_threshold == 1] == 1).mean()
                count = pred_at_threshold.sum()
                print(f"  {threshold:.2f}: Precision={precision:.3f}, Signals={count} ({count/len(y_test)*100:.1f}%)")
            else:
                print(f"  {threshold:.2f}: No signals")

        # Save model
        model_path = self.models_dir / f"{symbol}.cbm"
        model.save_model(str(model_path))
        print(f"\nModel saved: {model_path}")

        # Save metadata
        metadata = {
            'symbol': symbol,
            'train_start': start_date,
            'train_end': end_date,
            'target_return': target_return,
            'target_days': target_days,
            'auc': auc,
            'feature_cols': feature_cols,
            'feature_importance': feature_importance.to_dict('records'),
            'trained_at': datetime.now().isoformat()
        }

        metadata_path = self.models_dir / f"{symbol}_metadata.pkl"
        with open(metadata_path, 'wb') as f:
            pickle.dump(metadata, f)

        print(f"Metadata saved: {metadata_path}")

        return {
            'model': model,
            'auc': auc,
            'feature_importance': feature_importance,
            'metadata': metadata,
            'y_test': y_test,
            'y_pred_proba': y_pred_proba
        }

    def train_multiple_tickers(self, symbols: list, start_date: str, end_date: str):
        """Train models for multiple tickers"""
        results = {}

        for symbol in symbols:
            try:
                result = self.train_model(symbol, start_date, end_date)
                if result:
                    results[symbol] = result
            except Exception as e:
                print(f"\nERROR training {symbol}: {e}")
                continue

        # Summary
        print("\n" + "="*60)
        print("TRAINING SUMMARY")
        print("="*60)

        for symbol, result in results.items():
            print(f"{symbol:6s}: AUC={result['auc']:.4f}")

        return results


def main():
    """Train models for all watchlist tickers"""
    from src.config.tickers import TIER_2_STOCKS

    trainer = CatBoostTrainer()

    # Get all TIER_2_STOCKS symbols
    tickers = [t.symbol for t in TIER_2_STOCKS]

    print(f"Training CatBoost models for ALL {len(tickers)} watchlist tickers...")
    print(f"Period: 2020-01-01 to 2024-12-31")
    print(f"Target: 10% gain within 10 days")
    print(f"Tickers: {', '.join(tickers)}\n")

    results = trainer.train_multiple_tickers(
        symbols=tickers,
        start_date='2020-01-01',
        end_date='2024-12-31'
    )

    print("\n" + "="*60)
    print("TRAINING COMPLETE")
    print("="*60)
    print(f"Models saved to: {trainer.models_dir}")


if __name__ == "__main__":
    main()
