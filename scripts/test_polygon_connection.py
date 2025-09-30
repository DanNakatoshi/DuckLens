"""Quick manual test for Polygon.io connection."""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta
from src.data.collectors.polygon_collector import PolygonCollector


def main():
    print("Testing Polygon.io connection...")
    
    with PolygonCollector() as collector:
        # Test ticker details
        print("\n1. Fetching AAPL ticker details...")
        response = collector.get_ticker_details("AAPL")
        print(f"   Status: {response.status}")
        if response.results:
            print(f"   Ticker: {response.results[0].ticker}")
            print(f"   Name: {response.results[0].name}")
        
        # Test aggregates
        print("\n2. Fetching AAPL price data (last 7 days)...")
        to_date = datetime.now()
        from_date = to_date - timedelta(days=7)
        
        prices = collector.get_stock_prices("AAPL", from_date, to_date)
        print(f"   Retrieved {len(prices)} price bars")
        if prices:
            latest = prices[-1]
            print(f"   Latest: {latest.timestamp.date()} - Close: ${latest.close}")
    
    print("\n? Connection successful!")


if __name__ == "__main__":
    main()
