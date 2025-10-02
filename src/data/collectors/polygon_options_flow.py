"""
Polygon.io Options Flow Collector.

This module fetches options chain snapshots and aggregates data to track
smart money flow, put/call ratios, open interest changes, and unusual activity.

Designed for CatBoost feature engineering and market trend prediction.
"""

import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.models.schemas import OptionsChainContract, OptionsFlowDaily


class DataCollectionError(Exception):
    """Raised when data collection fails."""

    pass


class PolygonOptionsFlow:
    """Collector for options flow data from Polygon.io."""

    def __init__(self, api_key: str | None = None, timeout: int = 60):
        """
        Initialize options flow collector.

        Args:
            api_key: Polygon API key. If None, reads from POLYGON_API_KEY env var
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.getenv("POLYGON_API_KEY")
        if not self.api_key:
            raise ValueError("POLYGON_API_KEY must be provided or set in environment")

        self.base_url = "https://api.polygon.io"
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)

    def __enter__(self) -> "PolygonOptionsFlow":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close HTTP client."""
        if hasattr(self, "client"):
            self.client.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        reraise=True,
    )
    def _make_request(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Make HTTP request to Polygon API with retry logic.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response as dictionary

        Raises:
            DataCollectionError: If request fails after retries
        """
        if params is None:
            params = {}

        params["apiKey"] = self.api_key

        url = f"{self.base_url}{endpoint}"

        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise DataCollectionError(f"Polygon API request failed: {e}") from e
        except httpx.RequestError as e:
            raise DataCollectionError(f"Network error: {e}") from e
        except Exception as e:
            raise DataCollectionError(f"Unexpected error: {e}") from e

    def get_options_chain_snapshot(
        self,
        underlying_ticker: str,
        strike_price_gte: float | None = None,
        strike_price_lte: float | None = None,
        expiration_date_gte: str | None = None,
        expiration_date_lte: str | None = None,
        contract_type: str | None = None,
        limit: int = 250,
    ) -> list[OptionsChainContract]:
        """
        Get options chain snapshot for an underlying ticker.

        This is the PRIMARY method for options flow analysis. It returns all
        contracts with volume, OI, IV, greeks, and quotes in one request.

        Args:
            underlying_ticker: Underlying asset ticker (e.g., "SPY")
            strike_price_gte: Minimum strike price filter
            strike_price_lte: Maximum strike price filter
            expiration_date_gte: Minimum expiration date (YYYY-MM-DD)
            expiration_date_lte: Maximum expiration date (YYYY-MM-DD)
            contract_type: "call" or "put" (None for both)
            limit: Max results per request (default 250, max 250)

        Returns:
            List of OptionsChainContract objects

        Raises:
            DataCollectionError: If request fails
        """
        params: dict[str, Any] = {
            "limit": min(limit, 250),
            "order": "asc",
            "sort": "ticker",
        }

        if strike_price_gte:
            params["strike_price.gte"] = strike_price_gte
        if strike_price_lte:
            params["strike_price.lte"] = strike_price_lte
        if expiration_date_gte:
            params["expiration_date.gte"] = expiration_date_gte
        if expiration_date_lte:
            params["expiration_date.lte"] = expiration_date_lte
        if contract_type:
            params["contract_type"] = contract_type

        endpoint = f"/v3/snapshot/options/{underlying_ticker}"

        contracts = []
        next_url = None

        while True:
            if next_url:
                # Use full next_url (already has apiKey)
                response = self.client.get(next_url, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()
            else:
                data = self._make_request(endpoint, params)

            if data.get("status") != "OK":
                raise DataCollectionError(f"API returned status: {data.get('status')}")

            results = data.get("results", [])

            for result in results:
                try:
                    contract = self._parse_chain_contract(result, underlying_ticker)
                    contracts.append(contract)
                except Exception as e:
                    # Skip malformed contracts
                    print(f"Warning: Failed to parse contract: {e}")
                    continue

            # Check for pagination
            next_url = data.get("next_url")
            if not next_url:
                break

        return contracts

    def _parse_chain_contract(
        self, data: dict[str, Any], underlying_ticker: str
    ) -> OptionsChainContract:
        """Parse raw contract data from chain snapshot into OptionsChainContract."""
        details = data.get("details", {})
        day = data.get("day", {})
        greeks = data.get("greeks", {})
        last_quote = data.get("last_quote", {})
        last_trade = data.get("last_trade", {})

        # Parse expiration date
        exp_date_str = details.get("expiration_date")
        if exp_date_str:
            expiration_date = datetime.strptime(exp_date_str, "%Y-%m-%d")
        else:
            raise ValueError("Contract missing expiration_date")

        # Parse strike price
        strike_price = details.get("strike_price")
        if strike_price is None:
            raise ValueError("Contract missing strike_price")

        # Contract type
        contract_type = details.get("contract_type", "").lower()
        if contract_type not in ["call", "put"]:
            contract_type = "call"  # Default

        # Volume and OI from day data
        volume = day.get("volume")
        open_interest = data.get("open_interest")

        # Last price
        last_price = None
        if last_trade and "price" in last_trade:
            last_price = Decimal(str(last_trade["price"]))
        elif day.get("close"):
            last_price = Decimal(str(day["close"]))

        # Snapshot time
        snapshot_time = datetime.now()  # Use current time as snapshot time
        if "last_updated" in day:
            # Convert nanosecond timestamp to datetime
            try:
                snapshot_time = datetime.fromtimestamp(day["last_updated"] / 1_000_000_000)
            except (ValueError, TypeError):
                pass

        return OptionsChainContract(
            ticker=details.get("ticker", ""),
            underlying_ticker=underlying_ticker,
            strike_price=Decimal(str(strike_price)),
            expiration_date=expiration_date,
            contract_type=contract_type,
            last_price=last_price,
            volume=volume,
            open_interest=open_interest,
            delta=Decimal(str(greeks["delta"])) if greeks.get("delta") is not None else None,
            gamma=Decimal(str(greeks["gamma"])) if greeks.get("gamma") is not None else None,
            theta=Decimal(str(greeks["theta"])) if greeks.get("theta") is not None else None,
            vega=Decimal(str(greeks["vega"])) if greeks.get("vega") is not None else None,
            implied_volatility=(
                Decimal(str(data["implied_volatility"]))
                if data.get("implied_volatility") is not None
                else None
            ),
            bid=Decimal(str(last_quote["bid"])) if last_quote.get("bid") is not None else None,
            ask=Decimal(str(last_quote["ask"])) if last_quote.get("ask") is not None else None,
            bid_size=last_quote.get("bid_size"),
            ask_size=last_quote.get("ask_size"),
            break_even_price=(
                Decimal(str(data["break_even_price"]))
                if data.get("break_even_price") is not None
                else None
            ),
            snapshot_time=snapshot_time,
        )

    def aggregate_daily_flow(
        self,
        contracts: list[OptionsChainContract],
        ticker: str,
        date: datetime,
        previous_day_oi: dict[str, int] | None = None,
    ) -> OptionsFlowDaily:
        """
        Aggregate individual contracts into daily flow metrics.

        This is where we calculate put/call ratio, OI changes, unusual activity, etc.

        Args:
            contracts: List of contract snapshots
            ticker: Underlying ticker
            date: Date for this flow data
            previous_day_oi: Dict mapping contract_ticker -> OI from previous day

        Returns:
            OptionsFlowDaily object with aggregated metrics
        """
        if previous_day_oi is None:
            previous_day_oi = {}

        # Separate calls and puts
        calls = [c for c in contracts if c.contract_type == "call"]
        puts = [c for c in contracts if c.contract_type == "put"]

        # Volume metrics
        total_call_volume = sum(c.volume for c in calls if c.volume)
        total_put_volume = sum(c.volume for c in puts if c.volume)

        # Put/Call ratio
        if total_call_volume > 0:
            put_call_ratio = Decimal(total_put_volume) / Decimal(total_call_volume)
        else:
            put_call_ratio = Decimal("0")

        # Open Interest
        total_call_oi = sum(c.open_interest for c in calls if c.open_interest)
        total_put_oi = sum(c.open_interest for c in puts if c.open_interest)

        # OI Changes
        call_oi_change = 0
        put_oi_change = 0
        for c in calls:
            if c.open_interest and c.ticker in previous_day_oi:
                call_oi_change += c.open_interest - previous_day_oi[c.ticker]
        for c in puts:
            if c.open_interest and c.ticker in previous_day_oi:
                put_oi_change += c.open_interest - previous_day_oi[c.ticker]

        # Average IV
        call_ivs = [float(c.implied_volatility) for c in calls if c.implied_volatility]
        put_ivs = [float(c.implied_volatility) for c in puts if c.implied_volatility]

        avg_call_iv = Decimal(str(sum(call_ivs) / len(call_ivs))) if call_ivs else None
        avg_put_iv = Decimal(str(sum(put_ivs) / len(put_ivs))) if put_ivs else None

        # Net Greeks
        net_delta = sum(float(c.delta) * (c.volume or 0) for c in contracts if c.delta and c.volume)
        net_gamma = sum(float(c.gamma) * (c.volume or 0) for c in contracts if c.gamma and c.volume)
        net_theta = sum(float(c.theta) * (c.volume or 0) for c in contracts if c.theta and c.volume)
        net_vega = sum(float(c.vega) * (c.volume or 0) for c in contracts if c.vega and c.volume)

        # Unusual Activity (simple threshold: volume > 1000 for now)
        # TODO: Calculate based on 20-day average volume
        unusual_call_contracts = sum(1 for c in calls if c.volume and c.volume > 1000)
        unusual_put_contracts = sum(1 for c in puts if c.volume and c.volume > 1000)

        # Smart Money (volume executed at ask = bullish aggression)
        call_volume_at_ask = 0
        put_volume_at_ask = 0
        for c in calls:
            if c.volume and c.last_price and c.ask:
                # If last price is within 5% of ask, assume aggressive buying
                if abs(float(c.last_price - c.ask) / float(c.ask)) < 0.05:
                    call_volume_at_ask += c.volume
        for c in puts:
            if c.volume and c.last_price and c.ask:
                if abs(float(c.last_price - c.ask) / float(c.ask)) < 0.05:
                    put_volume_at_ask += c.volume

        # Max Pain (simplified: strike with highest total OI)
        strike_oi = {}
        for c in contracts:
            if c.strike_price and c.open_interest:
                strike_key = float(c.strike_price)
                strike_oi[strike_key] = strike_oi.get(strike_key, 0) + c.open_interest

        max_pain_price = None
        if strike_oi:
            max_pain_strike = max(strike_oi.items(), key=lambda x: x[1])[0]
            max_pain_price = Decimal(str(max_pain_strike))

        return OptionsFlowDaily(
            ticker=ticker,
            date=date,
            total_call_volume=total_call_volume,
            total_put_volume=total_put_volume,
            put_call_ratio=put_call_ratio,
            total_call_oi=total_call_oi,
            total_put_oi=total_put_oi,
            call_oi_change=call_oi_change,
            put_oi_change=put_oi_change,
            avg_call_iv=avg_call_iv,
            avg_put_iv=avg_put_iv,
            iv_rank=None,  # Calculated later by indicators module
            net_delta=Decimal(str(net_delta)) if net_delta else None,
            net_gamma=Decimal(str(net_gamma)) if net_gamma else None,
            net_theta=Decimal(str(net_theta)) if net_theta else None,
            net_vega=Decimal(str(net_vega)) if net_vega else None,
            unusual_call_contracts=unusual_call_contracts,
            unusual_put_contracts=unusual_put_contracts,
            call_volume_at_ask=call_volume_at_ask,
            put_volume_at_ask=put_volume_at_ask,
            max_pain_price=max_pain_price,
        )

    def calculate_key_strikes(
        self, current_price: float, num_strikes: int = 3
    ) -> list[tuple[float, str]]:
        """
        Calculate key strike prices to track for historical data.

        For efficient historical fetching, we track:
        - ATM (at-the-money): closest to current price
        - ±5% OTM (out-of-the-money)
        - ±10% OTM

        Args:
            current_price: Current stock price
            num_strikes: Number of strikes above/below ATM (default 3 for ±5%, ±10%, ±15%)

        Returns:
            List of (strike_price, label) tuples
            Example: [(580.0, 'ATM'), (551.0, '-5%'), (609.0, '+5%'), ...]
        """
        strikes = []

        # ATM (round to nearest $5)
        atm_strike = round(current_price / 5) * 5
        strikes.append((atm_strike, "ATM"))

        # OTM strikes at 5%, 10%, 15% intervals
        percentages = [0.05, 0.10, 0.15][:num_strikes]

        for pct in percentages:
            # Below current price (for puts)
            lower_strike = round((current_price * (1 - pct)) / 5) * 5
            strikes.append((lower_strike, f"-{int(pct*100)}%"))

            # Above current price (for calls)
            upper_strike = round((current_price * (1 + pct)) / 5) * 5
            strikes.append((upper_strike, f"+{int(pct*100)}%"))

        return strikes

    def construct_contract_ticker(
        self,
        underlying_ticker: str,
        strike_price: float,
        expiration_date: str,
        contract_type: str,
    ) -> str:
        """
        Construct OCC-formatted options contract ticker.

        For historical contracts, the reference API only returns active contracts.
        We need to construct the ticker ourselves using OCC format.

        Format: O:{UNDERLYING}{YYMMDD}{C/P}{STRIKE*1000:08d}
        Example: O:SPY240315C00510000 = SPY Call 510.00 expiring 2024-03-15

        Args:
            underlying_ticker: Underlying asset (e.g., "SPY")
            strike_price: Strike price (e.g., 510.0)
            expiration_date: Expiration date YYYY-MM-DD
            contract_type: "call" or "put"

        Returns:
            Contract ticker in OCC format
        """
        from datetime import datetime

        # Parse expiration date
        exp = datetime.strptime(expiration_date, "%Y-%m-%d")
        exp_str = exp.strftime("%y%m%d")  # YYMMDD

        # Type code
        type_code = "C" if contract_type.lower() == "call" else "P"

        # Strike price in pennies (multiply by 1000), 8 digits, zero-padded
        strike_pennies = int(strike_price * 1000)
        strike_str = f"{strike_pennies:08d}"

        # Construct ticker
        ticker = f"O:{underlying_ticker}{exp_str}{type_code}{strike_str}"

        return ticker

    def find_contract_ticker(
        self,
        underlying_ticker: str,
        strike_price: float,
        expiration_date: str,
        contract_type: str,
    ) -> str | None:
        """
        Find the contract ticker for a specific strike/expiration.

        For active contracts, uses the Option Contract endpoint to look up.
        For historical contracts (expired), constructs ticker using OCC format.

        Args:
            underlying_ticker: Underlying asset (e.g., "SPY")
            strike_price: Strike price (e.g., 580.0)
            expiration_date: Expiration date YYYY-MM-DD
            contract_type: "call" or "put"

        Returns:
            Contract ticker (e.g., "O:SPY240315C00580000") or None if not found
        """
        from datetime import datetime

        exp = datetime.strptime(expiration_date, "%Y-%m-%d")

        # If expiration is in the past, construct ticker (can't query expired contracts)
        if exp < datetime.now():
            return self.construct_contract_ticker(
                underlying_ticker, strike_price, expiration_date, contract_type
            )

        # For future expirations, try to look up from reference API
        endpoint = f"/v3/reference/options/contracts"

        params = {
            "underlying_ticker": underlying_ticker,
            "strike_price": strike_price,
            "expiration_date": expiration_date,
            "contract_type": contract_type,
            "limit": 1,
        }

        try:
            data = self._make_request(endpoint, params)

            if data.get("status") == "OK" and data.get("results"):
                return data["results"][0].get("ticker")

            # Fallback to construction if not found
            return self.construct_contract_ticker(
                underlying_ticker, strike_price, expiration_date, contract_type
            )

        except Exception as e:
            print(f"Warning: Failed to find contract ticker, using constructed: {e}")
            return self.construct_contract_ticker(
                underlying_ticker, strike_price, expiration_date, contract_type
            )

    def get_options_aggregates(
        self,
        contract_ticker: str,
        from_date: str,
        to_date: str,
        timespan: str = "day",
    ) -> list[dict[str, Any]]:
        """
        Get historical aggregates (OHLCV) for a specific options contract.

        This is the KEY method for historical options data with Options Starter plan.

        Args:
            contract_ticker: Options contract ticker (e.g., "O:SPY240315C00580000")
            from_date: Start date YYYY-MM-DD
            to_date: End date YYYY-MM-DD
            timespan: Timespan (default "day")

        Returns:
            List of aggregate bars with open, high, low, close, volume, vwap

        Raises:
            DataCollectionError: If request fails
        """
        endpoint = f"/v2/aggs/ticker/{contract_ticker}/range/1/{timespan}/{from_date}/{to_date}"

        params = {
            "adjusted": "true",
            "sort": "asc",
        }

        try:
            data = self._make_request(endpoint, params)

            if data.get("status") != "OK":
                raise DataCollectionError(f"API returned status: {data.get('status')}")

            results = data.get("results", [])
            return results

        except DataCollectionError:
            # No data for this contract/date range is expected (not all strikes trade)
            return []

    def get_historical_flow_via_aggregates(
        self,
        underlying_ticker: str,
        current_price: float,
        date: datetime,
        expiration_date: str,
    ) -> list[OptionsChainContract]:
        """
        Get historical options flow data using aggregates endpoint.

        This method:
        1. Calculates key strikes (ATM, ±5%, ±10%)
        2. Finds contract tickers for those strikes
        3. Fetches aggregates for each contract
        4. Converts aggregates to OptionsChainContract format

        Args:
            underlying_ticker: Underlying asset (e.g., "SPY")
            current_price: Stock price on this date
            date: Date to fetch data for
            expiration_date: Options expiration to use (YYYY-MM-DD)

        Returns:
            List of OptionsChainContract objects for key strikes
        """
        contracts = []
        date_str = date.strftime("%Y-%m-%d")

        # Calculate key strikes
        key_strikes = self.calculate_key_strikes(current_price, num_strikes=2)

        # Fetch both calls and puts for each strike
        for strike_price, label in key_strikes:
            for contract_type in ["call", "put"]:
                # Find contract ticker
                contract_ticker = self.find_contract_ticker(
                    underlying_ticker, strike_price, expiration_date, contract_type
                )

                if not contract_ticker:
                    continue

                # Fetch aggregate for this date
                aggs = self.get_options_aggregates(
                    contract_ticker, date_str, date_str, timespan="day"
                )

                if not aggs:
                    continue

                # Convert aggregate to OptionsChainContract
                agg = aggs[0]  # Should be single day
                contract = self._parse_aggregate_to_contract(
                    agg,
                    contract_ticker,
                    underlying_ticker,
                    strike_price,
                    expiration_date,
                    contract_type,
                    date,
                )

                contracts.append(contract)

        return contracts

    def _parse_aggregate_to_contract(
        self,
        agg: dict[str, Any],
        contract_ticker: str,
        underlying_ticker: str,
        strike_price: float,
        expiration_date: str,
        contract_type: str,
        date: datetime,
    ) -> OptionsChainContract:
        """
        Parse aggregate bar into OptionsChainContract format.

        Note: Aggregates don't have greeks, IV, or OI, so those fields will be None.
        This is a limitation of using aggregates vs snapshots.

        Args:
            agg: Aggregate bar from API
            contract_ticker: Contract ticker
            underlying_ticker: Underlying asset
            strike_price: Strike price
            expiration_date: Expiration date
            contract_type: "call" or "put"
            date: Date of this bar

        Returns:
            OptionsChainContract with available data
        """
        expiration = datetime.strptime(expiration_date, "%Y-%m-%d")

        return OptionsChainContract(
            ticker=contract_ticker,
            underlying_ticker=underlying_ticker,
            strike_price=Decimal(str(strike_price)),
            expiration_date=expiration,
            contract_type=contract_type,
            last_price=Decimal(str(agg["c"])) if agg.get("c") else None,  # Close price
            volume=agg.get("v"),  # Volume
            open_interest=None,  # Not available in aggregates
            delta=None,  # Not available in aggregates
            gamma=None,  # Not available in aggregates
            theta=None,  # Not available in aggregates
            vega=None,  # Not available in aggregates
            implied_volatility=None,  # Not available in aggregates
            bid=None,  # Not available in aggregates
            ask=None,  # Not available in aggregates
            bid_size=None,  # Not available in aggregates
            ask_size=None,  # Not available in aggregates
            break_even_price=None,  # Not available in aggregates
            snapshot_time=date,
        )
