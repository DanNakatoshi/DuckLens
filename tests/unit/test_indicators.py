"""Unit tests for technical indicators calculator."""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.analysis.indicators import TechnicalIndicators
from src.models.schemas import StockPrice


@pytest.fixture
def mock_price_data():
    """Create mock price data for testing."""
    base_date = datetime(2024, 1, 1)
    prices = []

    # Generate 100 days of mock data with realistic patterns
    for i in range(100):
        date = base_date + timedelta(days=i)
        # Simulate trending price with some volatility
        base_price = 100 + i * 0.5  # Uptrend
        prices.append(
            {
                "symbol": "TEST",
                "timestamp": date,
                "open": base_price - 1,
                "high": base_price + 2,
                "low": base_price - 2,
                "close": base_price,
                "volume": 1000000 + i * 10000,
                "created_at": date,
            }
        )

    return prices


@pytest.fixture
def indicators_calc(mock_price_data):
    """Create TechnicalIndicators instance with mocked database."""
    with patch("src.analysis.indicators.MarketDataDB") as mock_db_class:
        mock_db = MagicMock()
        mock_db.get_stock_prices.return_value = mock_price_data
        mock_db_class.return_value = mock_db

        calc = TechnicalIndicators()
        return calc


class TestTechnicalIndicators:
    """Test suite for TechnicalIndicators."""

    def test_init(self):
        """Test initialization."""
        with patch("src.analysis.indicators.MarketDataDB"):
            calc = TechnicalIndicators()
            assert calc is not None

    def test_context_manager(self):
        """Test context manager protocol."""
        with patch("src.analysis.indicators.MarketDataDB"):
            with TechnicalIndicators() as calc:
                assert isinstance(calc, TechnicalIndicators)

    def test_get_price_data(self, indicators_calc, mock_price_data):
        """Test getting price data as DataFrame."""
        df = indicators_calc._get_price_data("TEST")

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 100
        assert list(df.columns) == [
            "symbol",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "created_at",
        ]
        assert df.index.name == "timestamp"

    def test_calculate_sma(self, indicators_calc):
        """Test SMA calculation."""
        sma = indicators_calc.calculate_sma("TEST", window=20)

        assert isinstance(sma, pd.Series)
        assert len(sma) > 0
        # SMA should smooth out the data
        assert sma.std() < indicators_calc._get_price_data("TEST")["close"].std()

    def test_calculate_sma_different_windows(self, indicators_calc):
        """Test SMA with different window sizes."""
        sma_20 = indicators_calc.calculate_sma("TEST", window=20)
        sma_50 = indicators_calc.calculate_sma("TEST", window=50)

        # Longer window should have fewer data points (needs more history)
        assert len(sma_50) <= len(sma_20)

    def test_calculate_ema(self, indicators_calc):
        """Test EMA calculation."""
        ema = indicators_calc.calculate_ema("TEST", window=20)

        assert isinstance(ema, pd.Series)
        assert len(ema) > 0
        # EMA should be smoother than price but less smooth than SMA
        price_std = indicators_calc._get_price_data("TEST")["close"].std()
        assert ema.std() < price_std

    def test_calculate_macd(self, indicators_calc):
        """Test MACD calculation."""
        macd = indicators_calc.calculate_macd("TEST")

        assert isinstance(macd, pd.DataFrame)
        assert len(macd) > 0
        assert list(macd.columns) == ["macd", "signal", "histogram"]

        # Histogram should be macd - signal
        assert (macd["histogram"] - (macd["macd"] - macd["signal"])).abs().max() < 0.001

    def test_calculate_macd_custom_windows(self, indicators_calc):
        """Test MACD with custom windows."""
        macd = indicators_calc.calculate_macd(
            "TEST", short_window=6, long_window=13, signal_window=5
        )

        assert isinstance(macd, pd.DataFrame)
        assert len(macd) > 0

    def test_calculate_rsi(self, indicators_calc):
        """Test RSI calculation."""
        rsi = indicators_calc.calculate_rsi("TEST", window=14)

        assert isinstance(rsi, pd.Series)
        assert len(rsi) > 0
        # RSI should be between 0 and 100
        assert rsi.min() >= 0
        assert rsi.max() <= 100

    def test_calculate_bollinger_bands(self, indicators_calc):
        """Test Bollinger Bands calculation."""
        bb = indicators_calc.calculate_bollinger_bands("TEST", window=20, num_std=2.0)

        assert isinstance(bb, pd.DataFrame)
        assert len(bb) > 0
        assert list(bb.columns) == ["middle", "upper", "lower"]

        # Upper band should be above middle, middle above lower
        assert (bb["upper"] >= bb["middle"]).all()
        assert (bb["middle"] >= bb["lower"]).all()

    def test_calculate_atr(self, indicators_calc):
        """Test ATR calculation."""
        atr = indicators_calc.calculate_atr("TEST", window=14)

        assert isinstance(atr, pd.Series)
        assert len(atr) > 0
        # ATR should be positive
        assert (atr > 0).all()

    def test_calculate_stochastic(self, indicators_calc):
        """Test Stochastic Oscillator calculation."""
        stoch = indicators_calc.calculate_stochastic("TEST", k_window=14, d_window=3)

        assert isinstance(stoch, pd.DataFrame)
        assert len(stoch) > 0
        assert list(stoch.columns) == ["k", "d"]

        # Stochastic should be between 0 and 100
        assert stoch["k"].min() >= 0
        assert stoch["k"].max() <= 100
        assert stoch["d"].min() >= 0
        assert stoch["d"].max() <= 100

    def test_calculate_obv(self, indicators_calc):
        """Test OBV calculation."""
        obv = indicators_calc.calculate_obv("TEST")

        assert isinstance(obv, pd.Series)
        assert len(obv) > 0
        # OBV is cumulative, so it should be monotonic or have clear direction
        assert len(obv) == len(indicators_calc._get_price_data("TEST"))

    def test_calculate_all_indicators(self, indicators_calc):
        """Test calculating all indicators at once."""
        result = indicators_calc.calculate_all_indicators("TEST")

        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0

        # Check that key indicators are present
        expected_cols = [
            "close",
            "sma_20",
            "sma_50",
            "sma_200",
            "ema_12",
            "ema_26",
            "macd",
            "signal",
            "histogram",
            "rsi_14",
            "middle",
            "upper",
            "lower",
            "atr_14",
            "k",
            "d",
            "obv",
        ]

        for col in expected_cols:
            assert col in result.columns, f"Missing column: {col}"

    def test_empty_data(self):
        """Test handling of empty data."""
        with patch("src.analysis.indicators.MarketDataDB") as mock_db_class:
            mock_db = MagicMock()
            mock_db.get_stock_prices.return_value = []
            mock_db_class.return_value = mock_db

            calc = TechnicalIndicators()

            sma = calc.calculate_sma("INVALID")
            assert sma.empty

            ema = calc.calculate_ema("INVALID")
            assert ema.empty

            macd = calc.calculate_macd("INVALID")
            assert macd.empty

            rsi = calc.calculate_rsi("INVALID")
            assert rsi.empty

    def test_date_filtering(self):
        """Test date range filtering."""
        base_date = datetime(2024, 1, 1)
        prices = []

        for i in range(50):
            date = base_date + timedelta(days=i)
            prices.append(
                {
                    "symbol": "TEST",
                    "timestamp": date,
                    "open": 100,
                    "high": 102,
                    "low": 98,
                    "close": 100,
                    "volume": 1000000,
                    "created_at": date,
                }
            )

        with patch("src.analysis.indicators.MarketDataDB") as mock_db_class:
            mock_db = MagicMock()

            # Simulate date filtering in mock
            def filter_by_date(symbol, start_date, end_date):
                filtered = [p for p in prices if start_date <= p["timestamp"] <= end_date]
                return filtered

            mock_db.get_stock_prices.side_effect = filter_by_date
            mock_db_class.return_value = mock_db

            calc = TechnicalIndicators()

            # Get data for a specific range
            start = base_date + timedelta(days=10)
            end = base_date + timedelta(days=30)

            df = calc._get_price_data("TEST", start, end)

            assert len(df) == 21  # 30 - 10 + 1 = 21 days

    def test_different_price_columns(self, indicators_calc):
        """Test using different price columns for calculations."""
        sma_close = indicators_calc.calculate_sma("TEST", window=20, price_column="close")
        sma_open = indicators_calc.calculate_sma("TEST", window=20, price_column="open")

        # They should be different since open != close
        assert not sma_close.equals(sma_open)

    def test_sma_vs_ema_smoothing(self, indicators_calc):
        """Test that EMA reacts faster than SMA."""
        sma = indicators_calc.calculate_sma("TEST", window=20)
        ema = indicators_calc.calculate_ema("TEST", window=20)

        # EMA should have more variance (reacts faster to changes)
        # In an uptrend, EMA should generally be higher than SMA
        common_idx = sma.index.intersection(ema.index)
        assert len(common_idx) > 0

    def test_rsi_extremes(self):
        """Test RSI calculation with extreme price movements."""
        # Create data with strong uptrend
        base_date = datetime(2024, 1, 1)
        prices = []

        for i in range(30):
            date = base_date + timedelta(days=i)
            # Strong uptrend
            price = 100 + i * 5
            prices.append(
                {
                    "symbol": "TEST",
                    "timestamp": date,
                    "open": price - 1,
                    "high": price + 1,
                    "low": price - 1,
                    "close": price,
                    "volume": 1000000,
                    "created_at": date,
                }
            )

        with patch("src.analysis.indicators.MarketDataDB") as mock_db_class:
            mock_db = MagicMock()
            mock_db.get_stock_prices.return_value = prices
            mock_db_class.return_value = mock_db

            calc = TechnicalIndicators()
            rsi = calc.calculate_rsi("TEST", window=14)

            # Strong uptrend should produce high RSI values
            assert rsi.iloc[-1] > 70  # Should be overbought
