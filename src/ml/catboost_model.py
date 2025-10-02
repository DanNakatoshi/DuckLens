"""
CatBoost model for market trend prediction.

This module trains CatBoost models to predict:
1. Market direction (UP/DOWN) for next N days
2. Confidence scores for entry/exit signals
3. Expected return over holding period
"""

import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

import pandas as pd
from catboost import CatBoostClassifier, CatBoostRegressor, Pool
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split

from src.data.storage.market_data_db import MarketDataDB


class CatBoostTrainer:
    """
    CatBoost model trainer for market prediction.

    Trains models to predict market direction and expected returns
    based on technical indicators, economic data, and options flow.
    """

    def __init__(
        self,
        db: MarketDataDB,
        model_dir: str = "models",
        prediction_days: int = 5,
        profit_threshold: float = 0.02,  # 2% profit target
    ):
        """
        Initialize CatBoost trainer.

        Args:
            db: Database connection
            model_dir: Directory to save trained models
            prediction_days: Days ahead to predict
            profit_threshold: Minimum profit % to classify as UP
        """
        self.db = db
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)
        self.prediction_days = prediction_days
        self.profit_threshold = profit_threshold

        self.direction_model: CatBoostClassifier | None = None
        self.return_model: CatBoostRegressor | None = None
        self.feature_names: list[str] = []

    def prepare_features(
        self, ticker: str, start_date: datetime, end_date: datetime
    ) -> pd.DataFrame:
        """
        Prepare feature dataset for training.

        Combines:
        - Technical indicators
        - Options flow metrics
        - Economic calendar events
        - Price action features

        Args:
            ticker: Stock ticker
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with features and target labels
        """
        query = """
        SELECT
            sp.symbol,
            sp.timestamp as date,
            sp.open,
            sp.high,
            sp.low,
            sp.close,
            sp.volume,

            -- Technical indicators
            ti.sma_20,
            ti.sma_50,
            ti.sma_200,
            ti.ema_12,
            ti.ema_26,
            ti.macd,
            ti.macd_signal,
            ti.macd_histogram,
            ti.rsi_14,
            ti.bb_upper,
            ti.bb_middle,
            ti.bb_lower,
            ti.atr_14,
            ti.obv,
            ti.adx,

            -- Options flow (if available)
            ofi.put_call_ratio,
            ofi.put_call_ratio_ma5,
            ofi.put_call_ratio_percentile,
            ofi.smart_money_index,
            ofi.oi_momentum,
            ofi.unusual_activity_score,
            ofi.iv_rank,
            ofi.iv_skew,
            ofi.delta_weighted_volume,
            ofi.gamma_exposure,
            ofi.max_pain_distance,
            ofi.flow_signal

        FROM stock_prices sp
        LEFT JOIN technical_indicators ti
            ON sp.symbol = ti.ticker AND DATE(sp.timestamp) = DATE(ti.date)
        LEFT JOIN options_flow_indicators ofi
            ON sp.symbol = ofi.ticker AND DATE(sp.timestamp) = DATE(ofi.date)
        WHERE sp.symbol = ?
          AND DATE(sp.timestamp) >= DATE(?)
          AND DATE(sp.timestamp) <= DATE(?)
        ORDER BY sp.timestamp
        """

        df = pd.read_sql_query(
            query, self.db.conn, params=[ticker, start_date, end_date], parse_dates=["date"]
        )

        if df.empty:
            return df

        # Add derived features
        df = self._add_derived_features(df)

        # Add target labels (future return)
        df = self._add_target_labels(df)

        # Drop rows with missing targets
        df = df.dropna(subset=["target_return", "target_direction"])

        return df

    def _add_derived_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add derived features from price and indicators."""
        # Price momentum
        df["price_change_1d"] = df["close"].pct_change(1)
        df["price_change_5d"] = df["close"].pct_change(5)
        df["price_change_10d"] = df["close"].pct_change(10)

        # Volume features
        df["volume_ma_20"] = df["volume"].rolling(20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_ma_20"]

        # Volatility
        df["volatility_10d"] = df["close"].pct_change().rolling(10).std()

        # Distance from moving averages
        df["distance_sma_20"] = (df["close"] - df["sma_20"]) / df["sma_20"]
        df["distance_sma_50"] = (df["close"] - df["sma_50"]) / df["sma_50"]
        df["distance_sma_200"] = (df["close"] - df["sma_200"]) / df["sma_200"]

        # Trend strength
        df["trend_alignment"] = (df["sma_20"] > df["sma_50"]).astype(int) + (
            df["sma_50"] > df["sma_200"]
        ).astype(int)

        # High/Low ranges
        df["high_low_range"] = (df["high"] - df["low"]) / df["close"]

        # Days since features
        df["days_above_sma_20"] = (df["close"] > df["sma_20"]).rolling(20).sum()
        df["days_above_sma_50"] = (df["close"] > df["sma_50"]).rolling(50).sum()

        # Encode categorical flow_signal
        if "flow_signal" in df.columns:
            df["flow_bullish"] = (df["flow_signal"] == "BULLISH").astype(int)
            df["flow_bearish"] = (df["flow_signal"] == "BEARISH").astype(int)
        else:
            df["flow_bullish"] = 0
            df["flow_bearish"] = 0

        return df

    def _add_target_labels(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add target labels for prediction."""
        # Calculate future return
        df["future_close"] = df["close"].shift(-self.prediction_days)
        df["target_return"] = (df["future_close"] - df["close"]) / df["close"]

        # Binary direction (UP if return > threshold)
        df["target_direction"] = (df["target_return"] > self.profit_threshold).astype(int)

        return df

    def prepare_training_data(
        self, tickers: list[str], start_date: datetime, end_date: datetime
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Prepare training data for all tickers.

        Args:
            tickers: List of tickers
            start_date: Start date
            end_date: End date

        Returns:
            Tuple of (features DataFrame, full DataFrame with targets)
        """
        all_data = []

        for ticker in tickers:
            print(f"Preparing features for {ticker}...")
            df = self.prepare_features(ticker, start_date, end_date)
            if not df.empty:
                all_data.append(df)

        # Combine all tickers
        full_df = pd.concat(all_data, ignore_index=True)

        # Select feature columns (exclude target and metadata)
        exclude_cols = [
            "symbol",
            "date",
            "open",
            "high",
            "low",
            "close",
            "future_close",
            "target_return",
            "target_direction",
            "flow_signal",  # Already encoded
        ]

        feature_cols = [col for col in full_df.columns if col not in exclude_cols]
        features_df = full_df[feature_cols].copy()

        # Fill missing values
        features_df = features_df.fillna(0)

        self.feature_names = feature_cols

        return features_df, full_df

    def train_direction_model(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        test_size: float = 0.2,
        iterations: int = 1000,
        learning_rate: float = 0.03,
        depth: int = 6,
    ) -> dict:
        """
        Train CatBoost classifier for direction prediction.

        Args:
            X: Features DataFrame
            y: Target labels (0=DOWN, 1=UP)
            test_size: Test set proportion
            iterations: Number of boosting iterations
            learning_rate: Learning rate
            depth: Tree depth

        Returns:
            Dictionary with training metrics
        """
        print("\nTraining direction model...")

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )

        print(f"Training samples: {len(X_train)}")
        print(f"Test samples: {len(X_test)}")
        print(f"UP samples: {y_train.sum()} ({y_train.mean():.1%})")

        # Train model
        self.direction_model = CatBoostClassifier(
            iterations=iterations,
            learning_rate=learning_rate,
            depth=depth,
            loss_function="Logloss",
            eval_metric="Accuracy",
            random_seed=42,
            verbose=100,
            early_stopping_rounds=50,
        )

        self.direction_model.fit(
            X_train,
            y_train,
            eval_set=(X_test, y_test),
            use_best_model=True,
            plot=False,
        )

        # Evaluate
        y_pred_train = self.direction_model.predict(X_train)
        y_pred_test = self.direction_model.predict(X_test)

        train_acc = accuracy_score(y_train, y_pred_train)
        test_acc = accuracy_score(y_test, y_pred_test)

        print(f"\nTraining Accuracy: {train_acc:.4f}")
        print(f"Test Accuracy: {test_acc:.4f}")

        print("\nClassification Report (Test Set):")
        print(classification_report(y_test, y_pred_test, target_names=["DOWN", "UP"]))

        print("\nConfusion Matrix (Test Set):")
        print(confusion_matrix(y_test, y_pred_test))

        # Feature importance
        feature_importance = self.direction_model.get_feature_importance()
        importance_df = pd.DataFrame(
            {"feature": self.feature_names, "importance": feature_importance}
        ).sort_values("importance", ascending=False)

        print("\nTop 10 Important Features:")
        print(importance_df.head(10).to_string(index=False))

        return {
            "train_accuracy": train_acc,
            "test_accuracy": test_acc,
            "feature_importance": importance_df,
        }

    def train_return_model(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        test_size: float = 0.2,
        iterations: int = 1000,
        learning_rate: float = 0.03,
        depth: int = 6,
    ) -> dict:
        """
        Train CatBoost regressor for return prediction.

        Args:
            X: Features DataFrame
            y: Target returns
            test_size: Test set proportion
            iterations: Number of boosting iterations
            learning_rate: Learning rate
            depth: Tree depth

        Returns:
            Dictionary with training metrics
        """
        print("\nTraining return model...")

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )

        # Train model
        self.return_model = CatBoostRegressor(
            iterations=iterations,
            learning_rate=learning_rate,
            depth=depth,
            loss_function="RMSE",
            eval_metric="RMSE",
            random_seed=42,
            verbose=100,
            early_stopping_rounds=50,
        )

        self.return_model.fit(
            X_train,
            y_train,
            eval_set=(X_test, y_test),
            use_best_model=True,
            plot=False,
        )

        # Evaluate
        y_pred_train = self.return_model.predict(X_train)
        y_pred_test = self.return_model.predict(X_test)

        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

        train_rmse = mean_squared_error(y_train, y_pred_train, squared=False)
        test_rmse = mean_squared_error(y_test, y_pred_test, squared=False)
        train_mae = mean_absolute_error(y_train, y_pred_train)
        test_mae = mean_absolute_error(y_test, y_pred_test)
        train_r2 = r2_score(y_train, y_pred_train)
        test_r2 = r2_score(y_test, y_pred_test)

        print(f"\nTraining RMSE: {train_rmse:.4f}")
        print(f"Test RMSE: {test_rmse:.4f}")
        print(f"Training MAE: {train_mae:.4f}")
        print(f"Test MAE: {test_mae:.4f}")
        print(f"Training R²: {train_r2:.4f}")
        print(f"Test R²: {test_r2:.4f}")

        return {
            "train_rmse": train_rmse,
            "test_rmse": test_rmse,
            "train_mae": train_mae,
            "test_mae": test_mae,
            "train_r2": train_r2,
            "test_r2": test_r2,
        }

    def save_models(self, suffix: str = "") -> None:
        """
        Save trained models to disk.

        Args:
            suffix: Optional suffix for model filename
        """
        if self.direction_model:
            direction_path = self.model_dir / f"direction_model{suffix}.cbm"
            self.direction_model.save_model(str(direction_path))
            print(f"Saved direction model to {direction_path}")

        if self.return_model:
            return_path = self.model_dir / f"return_model{suffix}.cbm"
            self.return_model.save_model(str(return_path))
            print(f"Saved return model to {return_path}")

        # Save feature names
        features_path = self.model_dir / f"feature_names{suffix}.pkl"
        with open(features_path, "wb") as f:
            pickle.dump(self.feature_names, f)
        print(f"Saved feature names to {features_path}")

    def load_models(self, suffix: str = "") -> None:
        """
        Load trained models from disk.

        Args:
            suffix: Optional suffix for model filename
        """
        direction_path = self.model_dir / f"direction_model{suffix}.cbm"
        if direction_path.exists():
            self.direction_model = CatBoostClassifier()
            self.direction_model.load_model(str(direction_path))
            print(f"Loaded direction model from {direction_path}")

        return_path = self.model_dir / f"return_model{suffix}.cbm"
        if return_path.exists():
            self.return_model = CatBoostRegressor()
            self.return_model.load_model(str(return_path))
            print(f"Loaded return model from {return_path}")

        # Load feature names
        features_path = self.model_dir / f"feature_names{suffix}.pkl"
        if features_path.exists():
            with open(features_path, "rb") as f:
                self.feature_names = pickle.load(f)
            print(f"Loaded feature names from {features_path}")

    def predict(self, X: pd.DataFrame) -> tuple[int, float, float]:
        """
        Make prediction for new data.

        Args:
            X: Features DataFrame (single row)

        Returns:
            Tuple of (direction, direction_confidence, expected_return)
        """
        if self.direction_model is None or self.return_model is None:
            raise ValueError("Models not trained or loaded")

        # Ensure features match training
        X = X[self.feature_names].fillna(0)

        # Predict direction
        direction = int(self.direction_model.predict(X)[0])
        direction_proba = self.direction_model.predict_proba(X)[0]
        direction_confidence = float(direction_proba[direction])

        # Predict expected return
        expected_return = float(self.return_model.predict(X)[0])

        return direction, direction_confidence, expected_return
