"""
Quick test to verify options aggregates approach works.

This tests:
1. Calculating key strikes from stock price
2. Finding contract tickers for specific strikes
3. Fetching aggregates for those contracts
4. Converting to OptionsChainContract format
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.data.collectors.polygon_options_flow import PolygonOptionsFlow
from src.data.storage.market_data_db import MarketDataDB


def main():
    print("Testing Options Aggregates Approach")
    print("=" * 60)

    # Test with SPY on a known date
    test_ticker = "SPY"
    test_date = datetime(2024, 3, 15)  # Friday, March 15, 2024
    expiration = "2024-04-19"  # April 2024 monthly expiration

    print(f"\nTest ticker: {test_ticker}")
    print(f"Test date: {test_date.date()}")
    print(f"Expiration: {expiration}")

    with PolygonOptionsFlow() as collector, MarketDataDB() as db:
        # Get SPY price on test date
        price_query = """
            SELECT close
            FROM stock_prices
            WHERE symbol = ? AND DATE(timestamp) = DATE(?)
            LIMIT 1
        """
        price_result = db.conn.execute(price_query, [test_ticker, test_date]).fetchone()

        if not price_result:
            print("ERROR: No stock price data for test date")
            print("   Run: .\\tasks.ps1 fetch-historical first")
            return

        stock_price = float(price_result[0])
        print(f"Stock price: ${stock_price:.2f}")

        # Test 1: Calculate key strikes
        print("\n" + "=" * 60)
        print("TEST 1: Calculate Key Strikes")
        print("=" * 60)

        key_strikes = collector.calculate_key_strikes(stock_price, num_strikes=2)
        print(f"Key strikes for ${stock_price:.2f}:")
        for strike, label in key_strikes:
            print(f"  {label:>5}: ${strike:.2f}")

        # Test 2: Find contract ticker for ATM call
        print("\n" + "=" * 60)
        print("TEST 2: Find Contract Ticker")
        print("=" * 60)

        atm_strike = key_strikes[0][0]  # First strike is ATM
        print(f"Looking up ATM call at ${atm_strike:.2f}...")

        contract_ticker = collector.find_contract_ticker(
            underlying_ticker=test_ticker,
            strike_price=atm_strike,
            expiration_date=expiration,
            contract_type="call",
        )

        if contract_ticker:
            print(f"SUCCESS: Found contract: {contract_ticker}")
        else:
            print("ERROR: Contract not found")
            return

        # Test 3: Fetch aggregates
        print("\n" + "=" * 60)
        print("TEST 3: Fetch Aggregates")
        print("=" * 60)

        date_str = test_date.strftime("%Y-%m-%d")
        print(f"Fetching aggregates for {date_str}...")

        aggs = collector.get_options_aggregates(
            contract_ticker=contract_ticker,
            from_date=date_str,
            to_date=date_str,
            timespan="day",
        )

        if aggs:
            print(f"SUCCESS: Retrieved {len(aggs)} bar(s)")
            agg = aggs[0]
            print(f"  Open:   ${agg.get('o', 'N/A')}")
            print(f"  High:   ${agg.get('h', 'N/A')}")
            print(f"  Low:    ${agg.get('l', 'N/A')}")
            print(f"  Close:  ${agg.get('c', 'N/A')}")
            print(f"  Volume: {agg.get('v', 'N/A'):,}")
        else:
            print("ERROR: No aggregates data")
            return

        # Test 4: Full historical flow fetch
        print("\n" + "=" * 60)
        print("TEST 4: Full Historical Flow Fetch")
        print("=" * 60)

        print(f"Fetching all key contracts for {test_date.date()}...")

        contracts = collector.get_historical_flow_via_aggregates(
            underlying_ticker=test_ticker,
            current_price=stock_price,
            date=test_date,
            expiration_date=expiration,
        )

        if contracts:
            print(f"SUCCESS: Retrieved {len(contracts)} contracts")

            # Show summary by type and strike
            calls = [c for c in contracts if c.contract_type == "call"]
            puts = [c for c in contracts if c.contract_type == "put"]

            print(f"\n  Calls: {len(calls)}")
            for c in calls:
                print(
                    f"    ${c.strike_price:.2f} - Vol: {c.volume:,} - Last: ${c.last_price}"
                )

            print(f"\n  Puts: {len(puts)}")
            for c in puts:
                print(
                    f"    ${c.strike_price:.2f} - Vol: {c.volume:,} - Last: ${c.last_price}"
                )

            # Calculate P/C ratio
            call_vol = sum(c.volume for c in calls if c.volume)
            put_vol = sum(c.volume for c in puts if c.volume)

            if call_vol > 0:
                pc_ratio = put_vol / call_vol
                print(f"\n  Put/Call Ratio: {pc_ratio:.2f}")
            else:
                print("\n  Put/Call Ratio: N/A (no call volume)")

        else:
            print("ERROR: No contracts retrieved")
            return

        # Test 5: Aggregate to daily flow
        print("\n" + "=" * 60)
        print("TEST 5: Aggregate to Daily Flow")
        print("=" * 60)

        flow = collector.aggregate_daily_flow(
            contracts=contracts, ticker=test_ticker, date=test_date, previous_day_oi={}
        )

        print(f"Daily flow metrics:")
        print(f"  Call Volume: {flow.total_call_volume:,}")
        print(f"  Put Volume:  {flow.total_put_volume:,}")
        print(f"  P/C Ratio:   {float(flow.put_call_ratio):.2f}")
        print(f"  Unusual Calls: {flow.unusual_call_contracts}")
        print(f"  Unusual Puts:  {flow.unusual_put_contracts}")
        print(f"  Max Pain:    ${flow.max_pain_price}")

        print("\n" + "=" * 60)
        print("SUCCESS: ALL TESTS PASSED!")
        print("=" * 60)
        print("\nReady to run full historical fetch:")
        print("   .\\tasks.ps1 fetch-options-flow")
        print("=" * 60)


if __name__ == "__main__":
    main()
