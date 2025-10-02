"""
FRED (Federal Reserve Economic Data) API collector.

This module provides methods to fetch economic indicators from the Federal Reserve
Economic Data (FRED) API maintained by the Federal Reserve Bank of St. Louis.

API Documentation: https://fred.stlouisfed.org/docs/api/fred/
"""

import os
from datetime import datetime, timedelta
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.models.schemas import EconomicIndicator, FREDSeriesResponse


class DataCollectionError(Exception):
    """Raised when data collection fails."""

    pass


class FREDCollector:
    """Collector for FRED economic indicators."""

    # Key economic indicators to track
    ECONOMIC_SERIES = {
        # Interest Rates & Monetary Policy
        "FEDFUNDS": "Federal Funds Rate",
        "DFF": "Federal Funds Effective Rate",
        "T10Y2Y": "10-Year Treasury Constant Maturity Minus 2-Year (Yield Curve)",
        "T10YIE": "10-Year Breakeven Inflation Rate",
        # Inflation
        "CPIAUCSL": "Consumer Price Index for All Urban Consumers",
        "CPILFESL": "Consumer Price Index Less Food & Energy (Core CPI)",
        "PCEPI": "Personal Consumption Expenditures Price Index",
        "PCEPILFE": "Personal Consumption Expenditures Excluding Food and Energy (Core PCE)",
        # Employment
        "UNRATE": "Unemployment Rate",
        "PAYEMS": "All Employees: Total Nonfarm Payrolls",
        "ICSA": "Initial Jobless Claims",
        "U6RATE": "Total Unemployed Plus Marginally Attached Plus Part Time",
        # GDP & Growth
        "GDP": "Gross Domestic Product",
        "GDPC1": "Real Gross Domestic Product",
        "GDPPOT": "Real Potential Gross Domestic Product",
        # Consumer & Business
        "UMCSENT": "University of Michigan Consumer Sentiment Index",
        "RSXFS": "Retail Sales",
        "INDPRO": "Industrial Production Index",
        "HOUST": "Housing Starts",
        "PERMIT": "New Private Housing Units Authorized by Building Permits",
        # Credit & Money Supply
        "M2SL": "M2 Money Stock",
        "TOTCI": "Commercial and Industrial Loans",
        "DRTSCILM": "Net Percentage of Banks Tightening Standards for C&I Loans",
    }

    def __init__(self, api_key: str | None = None, timeout: int = 30):
        """
        Initialize FRED collector.

        Args:
            api_key: FRED API key. If None, reads from FRED_API_KEY env var
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.getenv("FRED_API_KEY")
        if not self.api_key:
            raise ValueError("FRED_API_KEY must be provided or set in environment")

        self.base_url = "https://api.stlouisfed.org/fred"
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)

    def __del__(self):
        """Clean up HTTP client."""
        if hasattr(self, "client"):
            self.client.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        reraise=True,
    )
    def _make_request(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        """
        Make HTTP request to FRED API with retry logic.

        Args:
            endpoint: API endpoint (e.g., "series/observations")
            params: Query parameters

        Returns:
            JSON response as dictionary

        Raises:
            DataCollectionError: If request fails after retries
        """
        params["api_key"] = self.api_key
        params["file_type"] = "json"

        url = f"{self.base_url}/{endpoint}"

        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise DataCollectionError(f"FRED API request failed: {e}") from e
        except httpx.RequestError as e:
            raise DataCollectionError(f"Network error: {e}") from e
        except Exception as e:
            raise DataCollectionError(f"Unexpected error: {e}") from e

    def get_series_observations(
        self,
        series_id: str,
        observation_start: str | None = None,
        observation_end: str | None = None,
        limit: int = 100000,
        sort_order: str = "asc",
    ) -> FREDSeriesResponse:
        """
        Get observations for a FRED series.

        Args:
            series_id: FRED series ID (e.g., "FEDFUNDS", "CPIAUCSL")
            observation_start: Start date in YYYY-MM-DD format
            observation_end: End date in YYYY-MM-DD format
            limit: Maximum number of observations to return (default 100000)
            sort_order: Sort order: "asc" or "desc"

        Returns:
            FREDSeriesResponse with observations

        Raises:
            DataCollectionError: If request fails
        """
        params: dict[str, Any] = {
            "series_id": series_id,
            "limit": limit,
            "sort_order": sort_order,
        }

        if observation_start:
            params["observation_start"] = observation_start
        if observation_end:
            params["observation_end"] = observation_end

        data = self._make_request("series/observations", params)
        return FREDSeriesResponse(**data)

    def get_economic_indicator(
        self,
        series_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[EconomicIndicator]:
        """
        Get economic indicator data as normalized EconomicIndicator objects.

        Args:
            series_id: FRED series ID (e.g., "FEDFUNDS", "CPIAUCSL")
            start_date: Start date for observations
            end_date: End date for observations

        Returns:
            List of EconomicIndicator objects

        Raises:
            DataCollectionError: If series_id is not in ECONOMIC_SERIES
        """
        if series_id not in self.ECONOMIC_SERIES:
            raise DataCollectionError(
                f"Unknown series_id: {series_id}. "
                f"Must be one of: {list(self.ECONOMIC_SERIES.keys())}"
            )

        indicator_name = self.ECONOMIC_SERIES[series_id]

        # Format dates
        obs_start = start_date.strftime("%Y-%m-%d") if start_date else None
        obs_end = end_date.strftime("%Y-%m-%d") if end_date else None

        # Fetch data
        response = self.get_series_observations(
            series_id=series_id,
            observation_start=obs_start,
            observation_end=obs_end,
        )

        # Convert to EconomicIndicator objects
        indicators = []
        for obs in response.observations:
            indicator = EconomicIndicator.from_fred_observation(
                series_id=series_id,
                indicator_name=indicator_name,
                obs=obs,
                units=response.units,
            )
            indicators.append(indicator)

        return indicators

    def get_all_indicators(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[EconomicIndicator]:
        """
        Get all configured economic indicators.

        Args:
            start_date: Start date for observations
            end_date: End date for observations

        Returns:
            List of EconomicIndicator objects from all series

        Raises:
            DataCollectionError: If any request fails
        """
        all_indicators = []

        for series_id in self.ECONOMIC_SERIES.keys():
            try:
                indicators = self.get_economic_indicator(
                    series_id=series_id,
                    start_date=start_date,
                    end_date=end_date,
                )
                all_indicators.extend(indicators)
                print(f"✓ Fetched {len(indicators)} observations for {series_id}")
            except DataCollectionError as e:
                print(f"⚠ Warning: Failed to fetch {series_id}: {e}")
                continue

        return all_indicators

    def get_latest_values(self) -> dict[str, EconomicIndicator | None]:
        """
        Get the most recent value for each economic indicator.

        Returns:
            Dictionary mapping series_id to latest EconomicIndicator (or None if unavailable)
        """
        latest_values = {}

        # Get last 30 days of data to ensure we have recent values
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        for series_id in self.ECONOMIC_SERIES.keys():
            try:
                indicators = self.get_economic_indicator(
                    series_id=series_id,
                    start_date=start_date,
                    end_date=end_date,
                )

                # Find the latest non-null value
                latest = None
                for indicator in reversed(indicators):  # Start from most recent
                    if indicator.value is not None:
                        latest = indicator
                        break

                latest_values[series_id] = latest

            except DataCollectionError:
                latest_values[series_id] = None

        return latest_values
