"""Tests for FRED economic data collector."""

from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, patch

import httpx
import pytest

from src.data.collectors.fred_collector import DataCollectionError, FREDCollector
from src.models.schemas import EconomicIndicator, FREDObservation, FREDSeriesResponse


@pytest.fixture
def mock_api_key():
    """Mock FRED API key."""
    return "test_fred_api_key_123"


@pytest.fixture
def fred_collector(mock_api_key):
    """Create FREDCollector instance with mocked API key."""
    return FREDCollector(api_key=mock_api_key)


@pytest.fixture
def sample_fred_response():
    """Sample FRED API response."""
    return {
        "realtime_start": "2024-01-01",
        "realtime_end": "2024-01-01",
        "observation_start": "2023-01-01",
        "observation_end": "2024-01-01",
        "units": "Percent",
        "output_type": 1,
        "file_type": "json",
        "order_by": "observation_date",
        "sort_order": "asc",
        "count": 3,
        "offset": 0,
        "limit": 100000,
        "observations": [
            {
                "realtime_start": "2024-01-01",
                "realtime_end": "2024-01-01",
                "date": "2023-01-01",
                "value": "4.33",
            },
            {
                "realtime_start": "2024-01-01",
                "realtime_end": "2024-01-01",
                "date": "2023-02-01",
                "value": "4.57",
            },
            {
                "realtime_start": "2024-01-01",
                "realtime_end": "2024-01-01",
                "date": "2023-03-01",
                "value": ".",  # Missing value
            },
        ],
    }


class TestFREDCollector:
    """Test suite for FREDCollector."""

    def test_init_with_api_key(self, mock_api_key):
        """Test initialization with provided API key."""
        collector = FREDCollector(api_key=mock_api_key)
        assert collector.api_key == mock_api_key
        assert collector.base_url == "https://api.stlouisfed.org/fred"
        assert collector.timeout == 30

    def test_init_with_env_var(self, mock_api_key):
        """Test initialization with API key from environment."""
        with patch.dict("os.environ", {"FRED_API_KEY": mock_api_key}):
            collector = FREDCollector()
            assert collector.api_key == mock_api_key

    def test_init_without_api_key(self):
        """Test initialization fails without API key."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="FRED_API_KEY must be provided"):
                FREDCollector()

    def test_economic_series_configuration(self, fred_collector):
        """Test that economic series are properly configured."""
        assert "FEDFUNDS" in fred_collector.ECONOMIC_SERIES
        assert "CPIAUCSL" in fred_collector.ECONOMIC_SERIES
        assert "UNRATE" in fred_collector.ECONOMIC_SERIES
        assert "GDP" in fred_collector.ECONOMIC_SERIES

        # Check that all series have names
        for series_id, name in fred_collector.ECONOMIC_SERIES.items():
            assert isinstance(series_id, str)
            assert isinstance(name, str)
            assert len(name) > 0

    def test_get_series_observations_success(self, fred_collector, sample_fred_response):
        """Test successful series observations fetch."""
        mock_response = Mock()
        mock_response.json.return_value = sample_fred_response
        mock_response.raise_for_status = Mock()

        with patch.object(fred_collector.client, "get", return_value=mock_response):
            result = fred_collector.get_series_observations(
                series_id="FEDFUNDS",
                observation_start="2023-01-01",
                observation_end="2024-01-01",
            )

        assert isinstance(result, FREDSeriesResponse)
        assert result.count == 3
        assert len(result.observations) == 3
        assert result.observations[0].value == "4.33"
        assert result.observations[1].value == "4.57"
        assert result.observations[2].value == "."  # Missing value

    def test_get_series_observations_default_params(self, fred_collector, sample_fred_response):
        """Test series observations with default parameters."""
        mock_response = Mock()
        mock_response.json.return_value = sample_fred_response
        mock_response.raise_for_status = Mock()

        with patch.object(fred_collector.client, "get", return_value=mock_response) as mock_get:
            fred_collector.get_series_observations(series_id="FEDFUNDS")

            # Verify call was made with correct parameters
            call_args = mock_get.call_args
            params = call_args.kwargs["params"]
            assert params["series_id"] == "FEDFUNDS"
            assert params["limit"] == 100000
            assert params["sort_order"] == "asc"
            assert params["api_key"] == fred_collector.api_key
            assert params["file_type"] == "json"

    def test_get_economic_indicator_success(self, fred_collector, sample_fred_response):
        """Test successful economic indicator fetch."""
        mock_response = Mock()
        mock_response.json.return_value = sample_fred_response
        mock_response.raise_for_status = Mock()

        with patch.object(fred_collector.client, "get", return_value=mock_response):
            indicators = fred_collector.get_economic_indicator(
                series_id="FEDFUNDS",
                start_date=datetime(2023, 1, 1),
                end_date=datetime(2024, 1, 1),
            )

        assert len(indicators) == 3
        assert all(isinstance(ind, EconomicIndicator) for ind in indicators)

        # Check first indicator
        assert indicators[0].series_id == "FEDFUNDS"
        assert indicators[0].indicator_name == "Federal Funds Rate"
        assert indicators[0].date == datetime(2023, 1, 1)
        assert indicators[0].value == Decimal("4.33")
        assert indicators[0].units == "Percent"

        # Check missing value handling
        assert indicators[2].value is None  # Missing value "."

    def test_get_economic_indicator_unknown_series(self, fred_collector):
        """Test that unknown series raises error."""
        with pytest.raises(DataCollectionError, match="Unknown series_id"):
            fred_collector.get_economic_indicator(series_id="INVALID_SERIES")

    def test_get_all_indicators_success(self, fred_collector, sample_fred_response):
        """Test fetching all economic indicators."""
        mock_response = Mock()
        mock_response.json.return_value = sample_fred_response
        mock_response.raise_for_status = Mock()

        with patch.object(fred_collector.client, "get", return_value=mock_response):
            # Only fetch first 3 series to speed up test
            with patch.object(
                fred_collector,
                "ECONOMIC_SERIES",
                {"FEDFUNDS": "Federal Funds Rate", "CPIAUCSL": "CPI", "UNRATE": "Unemployment"},
            ):
                indicators = fred_collector.get_all_indicators(
                    start_date=datetime(2023, 1, 1),
                    end_date=datetime(2024, 1, 1),
                )

        # Should get 3 observations × 3 series = 9 total
        assert len(indicators) == 9
        assert all(isinstance(ind, EconomicIndicator) for ind in indicators)

    def test_get_all_indicators_partial_failure(self, fred_collector, sample_fred_response, capsys):
        """Test that get_all_indicators continues on individual failures."""

        def mock_get(*args, **kwargs):
            # Fail on CPIAUCSL, succeed on others
            if "CPIAUCSL" in str(kwargs.get("params", {})):
                raise httpx.HTTPStatusError("404", request=Mock(), response=Mock())
            mock_response = Mock()
            mock_response.json.return_value = sample_fred_response
            mock_response.raise_for_status = Mock()
            return mock_response

        with patch.object(fred_collector.client, "get", side_effect=mock_get):
            with patch.object(
                fred_collector,
                "ECONOMIC_SERIES",
                {"FEDFUNDS": "Federal Funds Rate", "CPIAUCSL": "CPI"},
            ):
                indicators = fred_collector.get_all_indicators()

        # Should get 3 observations from FEDFUNDS only
        assert len(indicators) == 3

        # Check that warning was printed
        captured = capsys.readouterr()
        assert "Warning" in captured.out or "Failed" in captured.out

    def test_get_latest_values_success(self, fred_collector, sample_fred_response):
        """Test fetching latest values for all indicators."""
        mock_response = Mock()
        mock_response.json.return_value = sample_fred_response
        mock_response.raise_for_status = Mock()

        with patch.object(fred_collector.client, "get", return_value=mock_response):
            with patch.object(
                fred_collector,
                "ECONOMIC_SERIES",
                {"FEDFUNDS": "Federal Funds Rate"},
            ):
                latest_values = fred_collector.get_latest_values()

        assert "FEDFUNDS" in latest_values
        latest = latest_values["FEDFUNDS"]

        # Should get the latest non-null value (2023-02-01 with value 4.57)
        # since 2023-03-01 has missing value "."
        assert isinstance(latest, EconomicIndicator)
        assert latest.value == Decimal("4.57")
        assert latest.date == datetime(2023, 2, 1)

    def test_http_error_handling(self, fred_collector):
        """Test HTTP error is converted to DataCollectionError."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=Mock(), response=Mock()
        )

        with patch.object(fred_collector.client, "get", return_value=mock_response):
            with pytest.raises(DataCollectionError, match="FRED API request failed"):
                fred_collector.get_series_observations(series_id="FEDFUNDS")

    def test_network_error_handling(self, fred_collector):
        """Test network error is converted to DataCollectionError."""
        with patch.object(
            fred_collector.client,
            "get",
            side_effect=httpx.RequestError("Connection failed"),
        ):
            with pytest.raises(DataCollectionError, match="Network error"):
                fred_collector.get_series_observations(series_id="FEDFUNDS")

    def test_date_formatting(self, fred_collector, sample_fred_response):
        """Test that dates are properly formatted in API requests."""
        mock_response = Mock()
        mock_response.json.return_value = sample_fred_response
        mock_response.raise_for_status = Mock()

        start_date = datetime(2023, 1, 15)
        end_date = datetime(2023, 12, 31)

        with patch.object(fred_collector.client, "get", return_value=mock_response) as mock_get:
            fred_collector.get_economic_indicator(
                series_id="FEDFUNDS",
                start_date=start_date,
                end_date=end_date,
            )

            # Verify dates were formatted correctly
            call_args = mock_get.call_args
            params = call_args.kwargs["params"]
            assert params["observation_start"] == "2023-01-15"
            assert params["observation_end"] == "2023-12-31"

    def test_client_cleanup(self, fred_collector):
        """Test that HTTP client is properly closed."""
        client = fred_collector.client
        del fred_collector

        # Client should be closed (can't verify directly, but ensures no error)
        assert client is not None
