"""Test Polygon Options API access."""

import os
from dotenv import load_dotenv
import httpx

load_dotenv()

api_key = os.getenv("POLYGON_API_KEY")

if not api_key:
    print("❌ POLYGON_API_KEY not found in .env")
    exit(1)

print(f"✓ API Key found: {api_key[:10]}...{api_key[-4:]}")
print()

# Test 1: Stocks API (should work)
print("Test 1: Stocks API Access")
print("-" * 40)
stocks_url = f"https://api.polygon.io/v2/aggs/ticker/SPY/range/1/day/2024-01-01/2024-01-05?apiKey={api_key}"

try:
    response = httpx.get(stocks_url, timeout=10)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("✅ Stocks API: Working")
    elif response.status_code == 401:
        print("❌ Stocks API: 401 Unauthorized - Invalid API key")
    else:
        print(f"⚠ Stocks API: {response.status_code} - {response.text[:100]}")
except Exception as e:
    print(f"❌ Error: {e}")

print()

# Test 2: Options API (checking access)
print("Test 2: Options API Access")
print("-" * 40)
options_url = f"https://api.polygon.io/v3/snapshot/options/SPY?apiKey={api_key}"

try:
    response = httpx.get(options_url, timeout=10)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print("✅ Options API: Working!")
        print(f"   Results: {data.get('results', [])[:1]}")  # Show first result
    elif response.status_code == 401:
        print("❌ Options API: 401 Unauthorized")
        print("   Your API key does not have Options access")
        print("   Required: Options Starter plan or higher")
    elif response.status_code == 403:
        print("❌ Options API: 403 Forbidden")
        print("   Your plan doesn't include Options data")
    else:
        print(f"⚠ Options API: {response.status_code}")
        print(f"   Response: {response.text[:200]}")

except Exception as e:
    print(f"❌ Error: {e}")

print()

# Test 3: Check plan details via API
print("Test 3: Check Your Polygon Plan")
print("-" * 40)
# Note: Polygon doesn't have a public endpoint to check plan details
# You need to visit: https://polygon.io/dashboard
print("Visit: https://polygon.io/dashboard")
print("Check if 'Options' is listed under your plan features")
