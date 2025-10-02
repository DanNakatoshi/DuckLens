"""Tests for options flow collector and analyzer."""

from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from src.data.collectors.polygon_options_flow import PolygonOptionsFlow
from src.models.schemas import OptionsChainContract, OptionsFlowDaily


@pytest.fixture
def mock_api_key():
    """Mock Polygon API key."""
    return "test_polygon_api_key_123"


@pytest.fixture
def options_flow_collector(mock_api_key):
    """Create PolygonOptionsFlow instance with mocked API key."""
    return PolygonOptionsFlow(api_key=mock_api_key)


@pytest.fixture
def sample_chain_response():
    """Sample options chain response from Polygon."""
    return {
        "status": "OK",
        "results": [
            {
                "break_even_price": 451.2,
                "details": {
                    "contract_type": "call",
                    "exercise_style": "american",
                    "expiration_date": "2025-12-19",
                    "shares_per_contract": 100,
                    "strike_price": 450,
                    "ticker": "O:SPY251219C00450000",
                },
                "day": {
                    "change": 1.5,
                    "change_percent": 3.2,
                    "close": 48.5,
                    "high": 49.0,
                    "low": 47.0,
                    "open": 47.0,
                    "previous_close": 47.0,
                    "volume": 5000,
                    "vwap": 48.2,
                    "last_updated": 1609459200000000000,
                },
                "greeks": {
                    "delta": 0.55,
                    "gamma": 0.01,
                    "theta": -0.05,
                    "vega": 0.25,
                },
                "implied_volatility": 0.18,
                "last_quote": {
                    "ask": 48.7,
                    "ask_size": 10,
                    "bid": 48.3,
                    "bid_size": 15,
                    "last_updated": 1609459200000000000,
                    "midpoint": 48.5,
                },
                "last_trade": {
                    "price": 48.5,
                    "size": 10,
                    "exchange": 316,
                    "conditions": [209],
                },
                "open_interest": 1500,
            },
            {
                "break_even_price": 448.0,
                "details": {
                    "contract_type": "put",
                    "exercise_style": "american",
                    "expiration_date": "2025-12-19",
                    "shares_per_contract": 100,
                    "strike_price": 450,
                    "ticker": "O:SPY251219P00450000",
                },
                "day": {
                    "volume": 8000,
                    "close": 2.0,
                },
                "greeks": {
                    "delta": -0.45,
                    "gamma": 0.01,
                    "theta": -0.03,
                    "vega": 0.25,
                },
                "implied_volatility": 0.20,
                "last_quote": {
                    "ask": 2.05,
                    "bid": 1.95,
                    "ask_size": 20,
                    "bid_size": 25,
                },
                "last_trade": {
                    "price": 2.0,
                    "size": 50,
                },
                "open_interest": 2000,
            },
        ],
    }


class TestPolygonOptionsFlow:
    """Test suite for PolygonOptionsFlow collector."""

    def test_init_with_api_key(self, mock_api_key):
        """Test initialization with provided API key."""
        collector = PolygonOptionsFlow(api_key=mock_api_key)
        assert collector.api_key == mock_api_key
        assert collector.base_url == "https://api.polygon.io"

    def test_init_without_api_key(self):
        """Test initialization fails without API key."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="POLYGON_API_KEY must be provided"):
                PolygonOptionsFlow()

    def test_parse_chain_contract(self, options_flow_collector, sample_chain_response):
        """Test parsing chain contract from API response."""
        contract_data = sample_chain_response["results"][0]

        contract = options_flow_collector._parse_chain_contract(contract_data, "SPY")

        assert isinstance(contract, OptionsChainContract)
        assert contract.ticker == "O:SPY251219C00450000"
        assert contract.underlying_ticker == "SPY"
        assert contract.strike_price == Decimal("450")
        assert contract.contract_type == "call"
        assert contract.volume == 5000
        assert contract.open_interest == 1500
        assert contract.delta == Decimal("0.55")
        assert contract.implied_volatility == Decimal("0.18")

    def test_aggregate_daily_flow(self, options_flow_collector, sample_chain_response):
        """Test aggregating contracts into daily flow metrics."""
        contracts = []
        for contract_data in sample_chain_response["results"]:
            contract = options_flow_collector._parse_chain_contract(contract_data, "SPY")
            contracts.append(contract)

        flow = options_flow_collector.aggregate_daily_flow(
            contracts=contracts,
            ticker="SPY",
            date=datetime(2025, 1, 15),
            previous_day_oi={},
        )

        assert isinstance(flow, OptionsFlowDaily)
        assert flow.ticker == "SPY"
        assert flow.total_call_volume == 5000
        assert flow.total_put_volume == 8000
        # P/C ratio = 8000 / 5000 = 1.6
        assert float(flow.put_call_ratio) == pytest.approx(1.6, rel=0.01)
        assert flow.total_call_oi == 1500
        assert flow.total_put_oi == 2000

    def test_put_call_ratio_calculation(self, options_flow_collector):
        """Test put/call ratio calculation."""
        # Create test contracts
        call = OptionsChainContract(
            ticker="O:TEST",
            underlying_ticker="TEST",
            strike_price=Decimal("100"),
            expiration_date=datetime(2025, 12, 19),
            contract_type="call",
            volume=1000,
            open_interest=500,
            snapshot_time=datetime.now(),
        )

        put = OptionsChainContract(
            ticker="O:TEST2",
            underlying_ticker="TEST",
            strike_price=Decimal("100"),
            expiration_date=datetime(2025, 12, 19),
            contract_type="put",
            volume=1500,
            open_interest=600,
            snapshot_time=datetime.now(),
        )

        flow = options_flow_collector.aggregate_daily_flow(
            contracts=[call, put],
            ticker="TEST",
            date=datetime.now(),
        )

        # P/C = 1500 / 1000 = 1.5
        assert float(flow.put_call_ratio) == pytest.approx(1.5, rel=0.01)

    def test_zero_call_volume_handling(self, options_flow_collector):
        """Test handling when call volume is zero."""
        put = OptionsChainContract(
            ticker="O:TEST",
            underlying_ticker="TEST",
            strike_price=Decimal("100"),
            expiration_date=datetime(2025, 12, 19),
            contract_type="put",
            volume=1000,
            open_interest=500,
            snapshot_time=datetime.now(),
        )

        flow = options_flow_collector.aggregate_daily_flow(
            contracts=[put], ticker="TEST", date=datetime.now()
        )

        # Should handle gracefully, P/C ratio = 0 when no calls
        assert flow.put_call_ratio == Decimal("0")
        assert flow.total_call_volume == 0
        assert flow.total_put_volume == 1000

    def test_oi_change_calculation(self, options_flow_collector):
        """Test open interest change calculation."""
        contract = OptionsChainContract(
            ticker="O:TEST",
            underlying_ticker="TEST",
            strike_price=Decimal("100"),
            expiration_date=datetime(2025, 12, 19),
            contract_type="call",
            volume=1000,
            open_interest=1500,  # Today's OI
            snapshot_time=datetime.now(),
        )

        # Previous day had OI of 1200
        previous_oi = {"O:TEST": 1200}

        flow = options_flow_collector.aggregate_daily_flow(
            contracts=[contract],
            ticker="TEST",
            date=datetime.now(),
            previous_day_oi=previous_oi,
        )

        # OI change = 1500 - 1200 = +300
        assert flow.call_oi_change == 300

    def test_max_pain_calculation(self, options_flow_collector):
        """Test max pain price calculation."""
        # Create contracts at different strikes
        contracts = [
            OptionsChainContract(
                ticker=f"O:TEST{i}",
                underlying_ticker="TEST",
                strike_price=Decimal(str(strike)),
                expiration_date=datetime(2025, 12, 19),
                contract_type="call",
                volume=100,
                open_interest=oi,
                snapshot_time=datetime.now(),
            )
            for i, (strike, oi) in enumerate([(95, 1000), (100, 5000), (105, 2000)])
        ]

        flow = options_flow_collector.aggregate_daily_flow(
            contracts=contracts, ticker="TEST", date=datetime.now()
        )

        # Max pain should be 100 (highest OI)
        assert flow.max_pain_price == Decimal("100")

    def test_net_greeks_calculation(self, options_flow_collector):
        """Test net greeks calculation with volume weighting."""
        contracts = [
            OptionsChainContract(
                ticker="O:TEST1",
                underlying_ticker="TEST",
                strike_price=Decimal("100"),
                expiration_date=datetime(2025, 12, 19),
                contract_type="call",
                volume=1000,
                open_interest=500,
                delta=Decimal("0.5"),
                gamma=Decimal("0.01"),
                theta=Decimal("-0.05"),
                vega=Decimal("0.25"),
                snapshot_time=datetime.now(),
            ),
            OptionsChainContract(
                ticker="O:TEST2",
                underlying_ticker="TEST",
                strike_price=Decimal("100"),
                expiration_date=datetime(2025, 12, 19),
                contract_type="put",
                volume=500,
                open_interest=300,
                delta=Decimal("-0.45"),
                gamma=Decimal("0.01"),
                snapshot_time=datetime.now(),
            ),
        ]

        flow = options_flow_collector.aggregate_daily_flow(
            contracts=contracts, ticker="TEST", date=datetime.now()
        )

        # Net delta = (0.5 * 1000) + (-0.45 * 500) = 500 - 225 = 275
        assert flow.net_delta is not None
        assert float(flow.net_delta) == pytest.approx(275, rel=0.01)

    def test_unusual_activity_detection(self, options_flow_collector):
        """Test detection of unusual volume contracts."""
        # High volume call
        high_vol_call = OptionsChainContract(
            ticker="O:TEST1",
            underlying_ticker="TEST",
            strike_price=Decimal("100"),
            expiration_date=datetime(2025, 12, 19),
            contract_type="call",
            volume=5000,  # Unusual (> 1000 threshold)
            open_interest=500,
            snapshot_time=datetime.now(),
        )

        # Normal volume put
        normal_put = OptionsChainContract(
            ticker="O:TEST2",
            underlying_ticker="TEST",
            strike_price=Decimal("100"),
            expiration_date=datetime(2025, 12, 19),
            contract_type="put",
            volume=500,
            open_interest=300,
            snapshot_time=datetime.now(),
        )

        flow = options_flow_collector.aggregate_daily_flow(
            contracts=[high_vol_call, normal_put], ticker="TEST", date=datetime.now()
        )

        assert flow.unusual_call_contracts == 1
        assert flow.unusual_put_contracts == 0
