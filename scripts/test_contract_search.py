"""Test contract search to debug lookup."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.data.collectors.polygon_options_flow import PolygonOptionsFlow

with PolygonOptionsFlow() as collector:
    print("Testing contract search...")

    # Test 1: Find any active SPY options
    print("\nTest 1: Any active SPY options")
    endpoint = "/v3/reference/options/contracts"
    params = {
        "underlying_ticker": "SPY",
        "limit": 5,
        "sort": "expiration_date",
        "order": "asc",
    }

    data = collector._make_request(endpoint, params)
    print(f"Status: {data.get('status')}")

    if data.get('results'):
        print(f"Found {len(data['results'])} contracts")
        for result in data['results'][:5]:
            print(f"  {result.get('ticker')}")
            print(f"    Expiry: {result.get('expiration_date')}")
            print(f"    Strike: {result.get('strike_price')}")
            print(f"    Type: {result.get('contract_type')}")
    else:
        print("No results")

    # Test 2: Check expiration_date.gte filter
    print("\nTest 2: Future expirations")
    future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    params2 = {
        "underlying_ticker": "SPY",
        "expiration_date.gte": future_date,
        "limit": 3,
    }

    data2 = collector._make_request(endpoint, params2)
    if data2.get('results'):
        print(f"Found {len(data2['results'])} contracts expiring after {future_date}")
        for result in data2['results'][:3]:
            print(f"  {result.get('ticker')} - Exp: {result.get('expiration_date')} - Strike: {result.get('strike_price')}")
    else:
        print("No results")
