"""Polygon.io options data collector."""

from datetime import datetime

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import settings
from src.models.schemas import PolygonOptionsContractsResponse
from src.utils.exceptions import DataCollectionError


class PolygonOptionsCollector:
    """Collector for Polygon.io options data."""

    BASE_URL = "https://api.polygon.io"

    def __init__(self, api_key: str | None = None):
        """Initialize collector with API key."""
        self.api_key = api_key or settings.polygon_api_key
        self.client = httpx.Client(
            base_url=self.BASE_URL, timeout=30.0, params={"apiKey": self.api_key}
        )

    def __enter__(self) -> "PolygonOptionsCollector":
        return self

    def __exit__(self, *args: object) -> None:
        self.client.close()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def get_options_contracts(
        self,
        underlying_ticker: str | None = None,
        ticker: str | None = None,
        contract_type: str | None = None,
        expiration_date: str | None = None,
        as_of: str | None = None,
        strike_price: float | None = None,
        expired: bool = False,
        order: str = "asc",
        limit: int = 10,
        sort: str = "ticker",
    ) -> PolygonOptionsContractsResponse:
        """
        Get options contracts from Polygon.io.

        Args:
            underlying_ticker: Query for contracts relating to an underlying stock ticker
            ticker: Query by specific options ticker (deprecated by Polygon)
            contract_type: Query by type of contract (call, put, other)
            expiration_date: Query by contract expiration (YYYY-MM-DD)
            as_of: Point in time for contracts as of this date (YYYY-MM-DD)
            strike_price: Query by strike price of a contract
            expired: Query for expired contracts (default False)
            order: Order results (asc/desc) based on sort field
            limit: Limit number of results (default 10, max 1000)
            sort: Sort field used for ordering (ticker, expiration_date, strike_price)

        Returns:
            PolygonOptionsContractsResponse with contract data

        Raises:
            DataCollectionError: If the API request fails
        """
        params = {
            "order": order,
            "limit": min(limit, 1000),  # Enforce max limit
            "sort": sort,
            "expired": str(expired).lower(),
        }

        # Add optional parameters
        if underlying_ticker:
            params["underlying_ticker"] = underlying_ticker
        if ticker:
            params["ticker"] = ticker
        if contract_type:
            params["contract_type"] = contract_type
        if expiration_date:
            params["expiration_date"] = expiration_date
        if as_of:
            params["as_of"] = as_of
        if strike_price is not None:
            params["strike_price"] = strike_price

        try:
            response = self.client.get("/v3/reference/options/contracts", params=params)
            response.raise_for_status()
            return PolygonOptionsContractsResponse(**response.json())
        except httpx.HTTPError as e:
            raise DataCollectionError(f"Failed to fetch options contracts: {e}") from e
        except Exception as e:
            raise DataCollectionError(f"Unexpected error: {e}") from e

    def get_all_contracts_paginated(
        self,
        underlying_ticker: str | None = None,
        contract_type: str | None = None,
        expiration_date: str | None = None,
        max_pages: int = 10,
    ) -> list[PolygonOptionsContractsResponse]:
        """
        Get multiple pages of options contracts.

        Args:
            underlying_ticker: Query for contracts relating to an underlying stock ticker
            contract_type: Query by type of contract (call, put, other)
            expiration_date: Query by contract expiration (YYYY-MM-DD)
            max_pages: Maximum number of pages to fetch (default 10)

        Returns:
            List of PolygonOptionsContractsResponse objects
        """
        responses = []
        page = 1

        while page <= max_pages:
            response = self.get_options_contracts(
                underlying_ticker=underlying_ticker,
                contract_type=contract_type,
                expiration_date=expiration_date,
                limit=1000,  # Max per page
            )

            responses.append(response)

            # Check if there's a next page
            if not response.next_url:
                break

            page += 1

        return responses
