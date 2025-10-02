"""Unit tests for Polygon options collector."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.data.collectors.polygon_options_collector import PolygonOptionsCollector
from src.models.schemas import (
    PolygonAdditionalUnderlying,
    PolygonOptionsContract,
    PolygonOptionsContractsResponse,
)
from src.utils.exceptions import DataCollectionError


@pytest.fixture
def mock_options_response():
    """Mock response for options contracts endpoint."""
    return {
        "request_id": "603902c0-a5a5-406f-bd08-f030f92418fa",
        "results": [
            {
                "cfi": "OCASPS",
                "contract_type": "call",
                "exercise_style": "american",
                "expiration_date": "2021-11-19",
                "primary_exchange": "BATO",
                "shares_per_contract": 100,
                "strike_price": 85,
                "ticker": "O:AAPL211119C00085000",
                "underlying_ticker": "AAPL",
            },
            {
                "additional_underlyings": [
                    {"amount": 44, "type": "equity", "underlying": "VMW"},
                    {"amount": 6.53, "type": "currency", "underlying": "USD"},
                ],
                "cfi": "OCASPS",
                "contract_type": "call",
                "exercise_style": "american",
                "expiration_date": "2021-11-19",
                "primary_exchange": "BATO",
                "shares_per_contract": 100,
                "strike_price": 90,
                "ticker": "O:AAPL211119C00090000",
                "underlying_ticker": "AAPL",
            },
        ],
        "status": "OK",
    }


@pytest.fixture
def collector():
    """Create a PolygonOptionsCollector instance with mocked API key."""
    with patch("src.data.collectors.polygon_options_collector.settings") as mock_settings:
        mock_settings.polygon_api_key = "test_api_key"
        # Disable retry decorator for faster tests
        with patch(
            "src.data.collectors.polygon_options_collector.retry", lambda **kwargs: lambda f: f
        ):
            return PolygonOptionsCollector(api_key="test_api_key")


class TestPolygonOptionsCollector:
    """Test suite for PolygonOptionsCollector."""

    def test_init(self, collector):
        """Test collector initialization."""
        assert collector.api_key == "test_api_key"
        assert collector.BASE_URL == "https://api.polygon.io"
        assert isinstance(collector.client, httpx.Client)

    def test_context_manager(self):
        """Test context manager protocol."""
        with patch("src.data.collectors.polygon_options_collector.settings") as mock_settings:
            mock_settings.polygon_api_key = "test_api_key"
            with PolygonOptionsCollector() as collector:
                assert isinstance(collector, PolygonOptionsCollector)

    def test_get_options_contracts_success(self, collector, mock_options_response):
        """Test successful options contracts fetch."""
        with patch.object(collector.client, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_options_response
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            response = collector.get_options_contracts(
                underlying_ticker="AAPL", contract_type="call", limit=10
            )

            assert isinstance(response, PolygonOptionsContractsResponse)
            assert response.status == "OK"
            assert len(response.results) == 2
            assert response.results[0].ticker == "O:AAPL211119C00085000"
            assert response.results[0].strike_price == 85
            assert response.results[0].contract_type == "call"

            # Verify API call
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert call_args[0][0] == "/v3/reference/options/contracts"
            assert call_args[1]["params"]["underlying_ticker"] == "AAPL"
            assert call_args[1]["params"]["contract_type"] == "call"

    def test_get_options_contracts_with_additional_underlyings(
        self, collector, mock_options_response
    ):
        """Test parsing of contracts with additional underlyings."""
        with patch.object(collector.client, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_options_response
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            response = collector.get_options_contracts(underlying_ticker="AAPL")

            # Check second contract with additional underlyings
            contract = response.results[1]
            assert contract.ticker == "O:AAPL211119C00090000"
            assert len(contract.additional_underlyings) == 2
            assert contract.additional_underlyings[0].amount == 44
            assert contract.additional_underlyings[0].type == "equity"
            assert contract.additional_underlyings[0].underlying == "VMW"

    def test_get_options_contracts_all_parameters(self, collector, mock_options_response):
        """Test options contracts fetch with all parameters."""
        with patch.object(collector.client, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_options_response
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            response = collector.get_options_contracts(
                underlying_ticker="AAPL",
                ticker="O:AAPL211119C00085000",
                contract_type="call",
                expiration_date="2021-11-19",
                as_of="2021-11-01",
                strike_price=85.0,
                expired=True,
                order="desc",
                limit=50,
                sort="strike_price",
            )

            assert response.status == "OK"

            # Verify all parameters were passed
            call_args = mock_get.call_args[1]["params"]
            assert call_args["underlying_ticker"] == "AAPL"
            assert call_args["ticker"] == "O:AAPL211119C00085000"
            assert call_args["contract_type"] == "call"
            assert call_args["expiration_date"] == "2021-11-19"
            assert call_args["as_of"] == "2021-11-01"
            assert call_args["strike_price"] == 85.0
            assert call_args["expired"] == "true"
            assert call_args["order"] == "desc"
            assert call_args["limit"] == 50
            assert call_args["sort"] == "strike_price"

    def test_get_options_contracts_limit_enforcement(self, collector, mock_options_response):
        """Test that limit is enforced to max 1000."""
        with patch.object(collector.client, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_options_response
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            collector.get_options_contracts(limit=2000)

            # Should be capped at 1000
            call_args = mock_get.call_args[1]["params"]
            assert call_args["limit"] == 1000

    def test_get_all_contracts_paginated_single_page(self, collector, mock_options_response):
        """Test paginated fetch with single page."""
        with patch.object(collector.client, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_options_response
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            responses = collector.get_all_contracts_paginated(underlying_ticker="AAPL")

            assert len(responses) == 1
            assert responses[0].status == "OK"
            mock_get.assert_called_once()

    def test_get_all_contracts_paginated_multiple_pages(self, collector):
        """Test paginated fetch with multiple pages."""
        page1_response = {
            "request_id": "page1",
            "results": [
                {
                    "ticker": "O:AAPL211119C00085000",
                    "strike_price": 85,
                    "contract_type": "call",
                }
            ],
            "status": "OK",
            "next_url": "https://api.polygon.io/v3/reference/options/contracts?cursor=page2",
        }
        page2_response = {
            "request_id": "page2",
            "results": [
                {
                    "ticker": "O:AAPL211119C00090000",
                    "strike_price": 90,
                    "contract_type": "call",
                }
            ],
            "status": "OK",
            "next_url": None,
        }

        with patch.object(collector.client, "get") as mock_get:
            mock_response1 = MagicMock()
            mock_response1.json.return_value = page1_response
            mock_response1.raise_for_status = MagicMock()

            mock_response2 = MagicMock()
            mock_response2.json.return_value = page2_response
            mock_response2.raise_for_status = MagicMock()

            mock_get.side_effect = [mock_response1, mock_response2]

            responses = collector.get_all_contracts_paginated(underlying_ticker="AAPL", max_pages=5)

            assert len(responses) == 2
            assert responses[0].results[0].strike_price == 85
            assert responses[1].results[0].strike_price == 90
            assert mock_get.call_count == 2

    def test_get_all_contracts_paginated_max_pages_limit(self, collector):
        """Test that pagination respects max_pages limit."""
        response_with_next = {
            "request_id": "page",
            "results": [{"ticker": "O:AAPL211119C00085000"}],
            "status": "OK",
            "next_url": "https://api.polygon.io/v3/reference/options/contracts?cursor=next",
        }

        with patch.object(collector.client, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = response_with_next
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            responses = collector.get_all_contracts_paginated(underlying_ticker="AAPL", max_pages=3)

            # Should stop at max_pages even though next_url exists
            assert len(responses) == 3
            assert mock_get.call_count == 3

    def test_retry_on_transient_error(self, collector, mock_options_response):
        """Test that the collector retries on transient errors."""
        with patch.object(collector.client, "get") as mock_get:
            # First two calls fail, third succeeds
            mock_get.side_effect = [
                httpx.ConnectError("Connection failed"),
                httpx.ConnectError("Connection failed"),
                MagicMock(
                    json=MagicMock(return_value=mock_options_response),
                    raise_for_status=MagicMock(),
                ),
            ]

            response = collector.get_options_contracts(underlying_ticker="AAPL")

            assert response.status == "OK"
            assert mock_get.call_count == 3
