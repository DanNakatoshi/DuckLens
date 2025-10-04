"""
Fetch missing tech stocks for ML training
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from src.data.collectors.polygon_collector import PolygonCollector
from src.data.storage.market_data_db import MarketDataDB
from datetime import datetime, timedelta

load_dotenv()

# Priority tech stocks missing from database
MISSING_TECH = [
    'MSFT',   # Microsoft - most important
    'AMZN',   # Amazon
    'META',   # Meta/Facebook
    'NFLX',   # Netflix
    'TSM',    # Taiwan Semi
    'AVGO',   # Broadcom
    'ORCL',   # Oracle
    'ADBE',   # Adobe
    'CRM',    # Salesforce
    'QCOM',   # Qualcomm
    'CSCO',   # Cisco
]

def main():
    print("="*80)
    print("FETCHING MISSING TECH STOCKS FOR ML TRAINING")
    print("="*80)
    print(f"Symbols: {', '.join(MISSING_TECH)}\n")

    db = MarketDataDB()
    collector = PolygonCollector(db)

    # Fetch 5 years of data (2020-2025)
    end_date = datetime(2025, 10, 1)
    start_date = end_date - timedelta(days=5*365)

    print(f"Date range: {start_date.date()} to {end_date.date()}\n")

    for i, symbol in enumerate(MISSING_TECH, 1):
        print(f"[{i}/{len(MISSING_TECH)}] Fetching {symbol}...")
        try:
            collector.fetch_ohlcv(symbol, start_date, end_date)
            print(f"  OK {symbol} - Success")
        except Exception as e:
            print(f"  FAIL {symbol} - Error: {e}")

    print("\n" + "="*80)
    print("FETCH COMPLETE")
    print("="*80)
    print("\nNow you can retrain models:")
    print("  python scripts/train_catboost_models.py")

if __name__ == "__main__":
    main()
