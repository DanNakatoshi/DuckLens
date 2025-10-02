"""
CatBoost model for filtering entry signals.

Instead of predicting future prices, this model predicts:
"Given current technical setup, what's the probability this trade will be profitable?"

Used to filter out weak entry signals and improve win rate.
"""

import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

import pandas as pd
from catboost import CatBoostClassifier, Pool
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import TimeSeriesSplit

from src.data.storage.market_data_db import MarketDataDB


class CatBoostEntryFilter:
    """
    CatBoost model to filter entry signals.

    Predicts: Will a BUY signal at this moment lead to profit?
    Target: 1 (profitable) if price is higher after holding period, 0 (loss) otherwise
    """

    def __init__(
        self,
        db: MarketDataDB,
        model_dir: str = "models",
        holding_days: int = 30,  # Average holding period from backtest
        profit_threshold: float = 0.02,  # 2% profit to classify as win
    ):
        """
        Initialize CatBoost entry filter.

        Args:
            db: Database connection
            model_dir: Directory to save trained models
            holding_days: Expected holding period in days
            profit_threshold: Minimum profit % to classify as successful trade
        """
        self.db = db
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)
        self.holding_days = holding_days
        self.profit_threshold = profit_threshold

        self.model: CatBoostClassifier | None = None
        self.feature_names: list[str] = []

    def prepare_training_data(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime,
    ) -> tuple[pd.DataFrame, pd.Series]:
        """
        Prepare training data from historical price and indicators.

        Args:
            ticker: Stock ticker (e.g., 'SPY')
            start_date: Start date for training
            end_date: End date for training

        Returns:
            Tuple of (features DataFrame, target Series)
        """
        # Get all data
        query = """
        SELECT
            sp.timestamp as date,
            sp.open, sp.high, sp.low, sp.close, sp.volume,

            -- Technical indicators
            ti.sma_20, ti.sma_50, ti.sma_200,
            ti.ema_12, ti.ema_26,
            ti.macd, ti.macd_signal, ti.macd_histogram,
            ti.rsi_14,
            ti.bb_upper, ti.bb_middle, ti.bb_lower,
            ti.atr_14,
            ti.stoch_k, ti.stoch_d,
            ti.obv

        FROM stock_prices sp
        LEFT JOIN technical_indicators ti
            ON sp.symbol = ti.symbol AND DATE(sp.timestamp) = DATE(ti.timestamp)
        WHERE sp.symbol = ?
          AND DATE(sp.timestamp) >= DATE(?)
          AND DATE(sp.timestamp) <= DATE(?)
        ORDER BY sp.timestamp
        """

        df = pd.read_sql_query(
            query, self.db.conn, params=[ticker, start_date, end_date], parse_dates=["date"]
        )

        if df.empty:
            raise ValueError(f"No data found for {ticker} between {start_date} and {end_date}")

        # Add derived features
        df = self._add_derived_features(df)

        # Add target: Was this a good entry point?
        df = self._add_target_labels(df)

        # Drop rows with missing data
        df = df.dropna(subset=["target", "future_return"])

        # Separate features and target
        exclude_cols = [
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "future_close",
            "future_return",
            "target",
        ]
        feature_cols = [col for col in df.columns if col not in exclude_cols]

        X = df[feature_cols].fillna(0)
        y = df["target"]

        self.feature_names = feature_cols

        # Add metadata for analysis
        df["entry_date"] = df["date"]
        df["entry_price"] = df["close"]

        return X, y, df

    def _add_derived_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add engineered features from raw indicators."""

        # Price momentum
        df["price_change_1d"] = df["close"].pct_change(1)
        df["price_change_5d"] = df["close"].pct_change(5)
        df["price_change_10d"] = df["close"].pct_change(10)
        df["price_change_20d"] = df["close"].pct_change(20)

        # Volume features
        df["volume_ma_20"] = df["volume"].rolling(20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_ma_20"]

        # Volatility
        df["volatility_10d"] = df["close"].pct_change().rolling(10).std()
        df["volatility_20d"] = df["close"].pct_change().rolling(20).std()

        # Distance from moving averages (key trend signals)
        df["distance_sma_20"] = (df["close"] - df["sma_20"]) / df["sma_20"]
        df["distance_sma_50"] = (df["close"] - df["sma_50"]) / df["sma_50"]
        df["distance_sma_200"] = (df["close"] - df["sma_200"]) / df["sma_200"]

        # Trend alignment (bullish = 2, neutral = 1, bearish = 0)
        df["sma_alignment"] = (df["sma_20"] > df["sma_50"]).astype(int) + (
            df["sma_50"] > df["sma_200"]
        ).astype(int)

        # Golden cross / Death cross indicators
        df["golden_cross"] = (
            (df["sma_50"] > df["sma_200"]) & (df["sma_50"].shift(1) <= df["sma_200"].shift(1))
        ).astype(int)
        df["death_cross"] = (
            (df["sma_50"] < df["sma_200"]) & (df["sma_50"].shift(1) >= df["sma_200"].shift(1))
        ).astype(int)

        # MACD signals
        df["macd_crossover"] = (
            (df["macd"] > df["macd_signal"]) & (df["macd"].shift(1) <= df["macd_signal"].shift(1))
        ).astype(int)
        df["macd_bullish"] = (df["macd"] > df["macd_signal"]).astype(int)

        # RSI signals
        df["rsi_oversold"] = (df["rsi_14"] < 30).astype(int)
        df["rsi_overbought"] = (df["rsi_14"] > 70).astype(int)
        df["rsi_healthy"] = ((df["rsi_14"] >= 40) & (df["rsi_14"] <= 70)).astype(int)

        # Bollinger Band position
        df["bb_position"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"]

        # Price vs high/low
        df["high_low_range"] = (df["high"] - df["low"]) / df["close"]
        df["close_position"] = (df["close"] - df["low"]) / (df["high"] - df["low"])

        # Days above/below moving averages
        df["days_above_sma_20"] = (df["close"] > df["sma_20"]).rolling(20).sum()
        df["days_above_sma_50"] = (df["close"] > df["sma_50"]).rolling(50).sum()

        return df

    def _add_target_labels(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add target labels: Was this a good entry point?

        Target = 1 if price is higher by profit_threshold after holding_days
        Target = 0 otherwise
        """
        # Calculate future return
        df["future_close"] = df["close"].shift(-self.holding_days)
        df["future_return"] = (df["future_close"] - df["close"]) / df["close"]

        # Binary classification: Win if return > threshold
        df["target"] = (df["future_return"] > self.profit_threshold).astype(int)

        return df

    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        iterations: int = 500,
        learning_rate: float = 0.05,
        depth: int = 6,
    ) -> dict:
        """
        Train CatBoost classifier.

        Args:
            X: Feature matrix
            y: Target labels (1 = profitable entry, 0 = unprofitable)
            iterations: Number of boosting iterations
            learning_rate: Learning rate
            depth: Tree depth

        Returns:
            Dictionary with training metrics
        """
        print(f"\nTraining CatBoost Entry Filter...")
        print(f"Training samples: {len(X)}")
        print(f"Profitable entries: {y.sum()} ({y.mean():.1%})")
        print(f"Unprofitable entries: {len(y) - y.sum()} ({1 - y.mean():.1%})")

        # Use TimeSeriesSplit for time-based cross-validation
        tscv = TimeSeriesSplit(n_splits=3)

        train_scores = []
        val_scores = []

        for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
            print(f"\nFold {fold + 1}/3:")

            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

            # Create CatBoost model
            model = CatBoostClassifier(
                iterations=iterations,
                learning_rate=learning_rate,
                depth=depth,
                loss_function="Logloss",
                eval_metric="AUC",
                random_seed=42,
                verbose=False,
            )

            # Train
            model.fit(
                X_train,
                y_train,
                eval_set=(X_val, y_val),
                verbose=100,
            )

            # Evaluate
            train_pred = model.predict(X_train)
            val_pred = model.predict(X_val)

            train_acc = accuracy_score(y_train, train_pred)
            val_acc = accuracy_score(y_val, val_pred)

            train_scores.append(train_acc)
            val_scores.append(val_acc)

            print(f"  Train accuracy: {train_acc:.3f}")
            print(f"  Val accuracy: {val_acc:.3f}")

        # Train final model on all data
        print(f"\nTraining final model on all data...")
        self.model = CatBoostClassifier(
            iterations=iterations,
            learning_rate=learning_rate,
            depth=depth,
            loss_function="Logloss",
            eval_metric="AUC",
            random_seed=42,
            verbose=False,
        )

        self.model.fit(X, y, verbose=100)

        # Final predictions
        final_pred = self.model.predict(X)
        final_proba = self.model.predict_proba(X)[:, 1]

        print(f"\n{'=' * 60}")
        print("FINAL MODEL PERFORMANCE")
        print(f"{'=' * 60}")
        print(f"Accuracy: {accuracy_score(y, final_pred):.3f}")
        print(f"\nClassification Report:")
        print(classification_report(y, final_pred, target_names=["Loss", "Profit"]))

        # Feature importance
        feature_importance = pd.DataFrame(
            {"feature": self.feature_names, "importance": self.model.feature_importances_}
        ).sort_values("importance", ascending=False)

        print(f"\nTop 10 Most Important Features:")
        print(feature_importance.head(10).to_string(index=False))

        # Save model
        model_path = self.model_dir / f"entry_filter_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(self.model, f)
        print(f"\nModel saved to: {model_path}")

        return {
            "accuracy": accuracy_score(y, final_pred),
            "cv_train_scores": train_scores,
            "cv_val_scores": val_scores,
            "feature_importance": feature_importance,
        }

    def predict_entry_quality(self, X: pd.DataFrame) -> tuple[int, float]:
        """
        Predict if this is a good entry point.

        Args:
            X: Feature vector (single row or DataFrame)

        Returns:
            Tuple of (prediction, confidence)
            prediction: 1 = good entry, 0 = bad entry
            confidence: Probability of profit (0-1)
        """
        if self.model is None:
            raise ValueError("Model not trained yet. Call train() first.")

        prediction = self.model.predict(X)[0]
        confidence = self.model.predict_proba(X)[0, 1]  # Probability of class 1 (profit)

        return int(prediction), float(confidence)

    def load_model(self, model_path: str):
        """Load a trained model from disk."""
        with open(model_path, "rb") as f:
            self.model = pickle.load(f)
        print(f"Model loaded from: {model_path}")
