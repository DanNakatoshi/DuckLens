# Market Data Collection Guide

This guide explains how to fetch and store historical market data from Polygon.io.

## Overview

The system fetches and stores three types of data in DuckDB:
1. **OHLCV Data** - Daily open, high, low, close, and volume for stocks/ETFs
2. **Short Interest** - Bi-monthly short interest data (since 2017)
3. **Short Volume** - Daily short volume data (since Jan 2024)

## Quick Start

### Initial Setup - Fetch 5 Years of Historical Data

This fetches data for 19 major market ETFs/indices:

```powershell
.\tasks.ps1 fetch-historical
```

**What it fetches:**
- SPY, QQQ, DIA, IWM, VTI (Major market indices)
- Sector ETFs: XLF, XLE, XLK, XLV, XLI, XLP, XLY, XLU, XLB, XLRE, XLC
- VXX (Volatility)
- EFA, EEM (International)

**Time:** 10-30 minutes depending on API rate limits

### Daily Updates (Run After Market Hours)

Update all tickers with the latest data:

```powershell
.\tasks.ps1 update-daily
```

**Best Practice:** Schedule this to run automatically after 4 PM ET when markets close.

### View Database Statistics

```powershell
.\tasks.ps1 db-stats
```

## Custom Ticker Lists

### Fetch Historical Data for Custom Tickers

```powershell
poetry run python scripts/fetch_historical_data.py AAPL,MSFT,GOOGL,TSLA
```

### Daily Update for Custom Tickers

```powershell
poetry run python scripts/update_daily_data.py NVDA,AMD,INTC
```

## Default Tickers

The system tracks 19 major ETFs by default:

| Category | Tickers | Description |
|----------|---------|-------------|
| **Major Indices** | SPY | S&P 500 ETF |
| | QQQ | NASDAQ 100 ETF |
| | DIA | Dow Jones ETF |
| | IWM | Russell 2000 ETF |
| | VTI | Total Stock Market ETF |
| **Sector ETFs** | XLF | Financial Select Sector |
| | XLE | Energy Select Sector |
| | XLK | Technology Select Sector |
| | XLV | Health Care Select Sector |
| | XLI | Industrial Select Sector |
| | XLP | Consumer Staples Select Sector |
| | XLY | Consumer Discretionary Select Sector |
| | XLU | Utilities Select Sector |
| | XLB | Materials Select Sector |
| | XLRE | Real Estate Select Sector |
| | XLC | Communication Services Select Sector |
| **Volatility** | VXX | Short-Term VIX Futures ETF |
| **International** | EFA | iShares MSCI EAFE ETF |
| | EEM | iShares MSCI Emerging Markets ETF |

## Database Schema

### Tables

#### 1. `stock_prices`
Daily OHLCV data with 5 years of history.

```sql
CREATE TABLE stock_prices (
    symbol VARCHAR NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    open DECIMAL(18, 4) NOT NULL,
    high DECIMAL(18, 4) NOT NULL,
    low DECIMAL(18, 4) NOT NULL,
    close DECIMAL(18, 4) NOT NULL,
    volume BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, timestamp)
)
```

#### 2. `short_interest`
Bi-monthly short interest data going back to 2017.

```sql
CREATE TABLE short_interest (
    ticker VARCHAR NOT NULL,
    settlement_date DATE NOT NULL,
    short_interest BIGINT,
    avg_daily_volume BIGINT,
    days_to_cover DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ticker, settlement_date)
)
```

#### 3. `short_volume`
Daily short volume data from Jan 2024 onwards.

```sql
CREATE TABLE short_volume (
    ticker VARCHAR NOT NULL,
    date DATE NOT NULL,
    short_volume BIGINT,
    total_volume BIGINT,
    short_volume_ratio DECIMAL(6, 2),
    exempt_volume BIGINT,
    non_exempt_volume BIGINT,
    -- Exchange-specific volumes
    adf_short_volume BIGINT,
    nasdaq_carteret_short_volume BIGINT,
    nasdaq_chicago_short_volume BIGINT,
    nyse_short_volume BIGINT,
    -- ... more exchange fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ticker, date)
)
```

## Querying the Data

### Python Example

```python
from src.data.storage.market_data_db import MarketDataDB
from datetime import datetime, timedelta

with MarketDataDB() as db:
    # Get last 30 days of SPY prices
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    prices = db.get_stock_prices("SPY", start_date, end_date)

    # Get database statistics
    stats = db.get_table_stats()
    print(stats)
```

### Direct DuckDB Queries

```python
import duckdb

conn = duckdb.connect('./data/ducklens.db')

# Get latest prices for all symbols
result = conn.execute("""
    SELECT symbol, MAX(timestamp) as latest_date, close
    FROM stock_prices
    GROUP BY symbol, close
    ORDER BY symbol
""").fetchdf()

# Get tickers with highest short interest
result = conn.execute("""
    SELECT ticker, settlement_date, short_interest, days_to_cover
    FROM short_interest
    WHERE settlement_date = (SELECT MAX(settlement_date) FROM short_interest)
    ORDER BY days_to_cover DESC
    LIMIT 10
""").fetchdf()

conn.close()
```

## Automation with Task Scheduler (Windows)

To automatically update data daily:

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger: Daily at 4:30 PM
4. Action: Start a program
   - Program: `powershell.exe`
   - Arguments: `-File "D:\GitHub\DuckLens\tasks.ps1" update-daily`
   - Start in: `D:\GitHub\DuckLens`

## API Rate Limits

Polygon.io Stocks Starter plan:
- 5 API calls per minute
- Unlimited requests per day
- The scripts include automatic retry with exponential backoff

## Troubleshooting

### "Module not found" errors
```powershell
.\tasks.ps1 install
```

### Check API key
Make sure your `.env` file has:
```
POLYGON_API_KEY=your_key_here
```

### Check database
```powershell
.\tasks.ps1 check-duckdb
```

## Files Created

- `src/models/schemas.py` - Added short interest/volume models
- `src/data/collectors/polygon_collector.py` - Extended with short data methods
- `src/data/storage/market_data_db.py` - DuckDB storage manager
- `scripts/fetch_historical_data.py` - Historical data fetcher (5 years)
- `scripts/update_daily_data.py` - Daily update script
- `tasks.ps1` - Added new commands

## Available Commands Summary

```powershell
# Development
.\tasks.ps1 test           # Run all tests
.\tasks.ps1 lint           # Lint code
.\tasks.ps1 format         # Format code
.\tasks.ps1 type-check     # Type check
.\tasks.ps1 install        # Install dependencies

# Data Collection
.\tasks.ps1 fetch-historical   # Fetch 5 years of data (one-time)
.\tasks.ps1 update-daily       # Update with latest data (daily)
.\tasks.ps1 db-stats           # View database statistics

# Testing & Debugging
.\tasks.ps1 fetch-polygon      # Test Polygon connection
.\tasks.ps1 check-duckdb       # Check database tables
.\tasks.ps1 test-polygon       # Run Polygon collector tests
```
