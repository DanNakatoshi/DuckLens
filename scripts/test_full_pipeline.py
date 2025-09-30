"""Test the full data pipeline: Polygon.io -> DuckDB."""
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.collectors.polygon_collector import PolygonCollector
from src.data.storage.duckdb_manager import DuckDBManager


def main():
    print("Testing full pipeline: Polygon.io -> DuckDB\n")
    
    # Initialize
    db = DuckDBManager("./data/test_pipeline.db")
    
    # Fetch data from Polygon
    print("1. Fetching AAPL data from Polygon.io...")
    with PolygonCollector() as collector:
        to_date = datetime.now()
        from_date = to_date - timedelta(days=7)
        prices = collector.get_stock_prices("AAPL", from_date, to_date)
    
    print(f"   Fetched {len(prices)} price records")
    
    # Store in DuckDB
    print("\n2. Storing in DuckDB...")
    inserted = db.insert_stock_prices(prices)
    print(f"   Inserted {inserted} new records")
    
    # Retrieve and verify
    print("\n3. Retrieving from DuckDB...")
    stored_prices = db.get_stock_prices("AAPL", limit=5)
    print(f"   Retrieved {len(stored_prices)} recent records:")
    
    for price in stored_prices[:3]:
        print(f"   - {price.timestamp.date()}: ${price.close}")
    
    # Check latest timestamp
    latest = db.get_latest_timestamp("AAPL")
    print(f"\n4. Latest data point: {latest}")
    
    # Get all symbols
    symbols = db.get_symbols()
    print(f"\n5. Symbols in database: {symbols}")
    
    print("\n? Full pipeline test successful!")


if __name__ == "__main__":
    main()
