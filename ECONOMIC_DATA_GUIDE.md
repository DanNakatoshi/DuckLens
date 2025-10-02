# Economic Data Integration Guide

This guide covers the FRED (Federal Reserve Economic Data) integration for DuckLens.

## Overview

The economic data system fetches critical macroeconomic indicators from the Federal Reserve Economic Data (FRED) API, including:

- **Interest Rates & Monetary Policy**: Federal Funds Rate, Yield Curve, Breakeven Inflation
- **Inflation**: CPI, Core CPI, PCE, Core PCE
- **Employment**: Unemployment Rate, Payrolls, Jobless Claims
- **GDP & Growth**: GDP, Real GDP, Industrial Production
- **Consumer & Business**: Consumer Sentiment, Retail Sales, Housing Starts
- **Credit & Money Supply**: M2, Commercial Loans, Bank Lending Standards

## Setup

### 1. Get FRED API Key

1. Visit https://fred.stlouisfed.org/
2. Create a free account
3. Go to "My Account" → "API Keys"
4. Request an API key (instant approval)

### 2. Configure Environment

Add your API key to `.env`:

```bash
FRED_API_KEY=your_fred_api_key_here
```

## Available Commands

### Fetch Economic Data (Backfill)

Fetch 5 years of all economic indicators:

```powershell
.\tasks.ps1 fetch-economic
```

Custom date range:

```powershell
poetry run python scripts/fetch_economic_data.py --years 10
poetry run python scripts/fetch_economic_data.py --start-date 2020-01-01
```

Fetch specific indicator:

```powershell
poetry run python scripts/fetch_economic_data.py --series FEDFUNDS
```

### List Available Indicators

```powershell
.\tasks.ps1 list-economic
```

This shows all 23 economic indicators being tracked.

### Daily Updates

The economic data is automatically included in the daily update script:

```powershell
.\tasks.ps1 update-daily
```

This checks the last 30 days for any new economic data releases (most indicators are monthly).

### Run Tests

```powershell
.\tasks.ps1 test-fred
```

## Economic Indicators Tracked

| Series ID | Indicator Name | Frequency |
|-----------|---------------|-----------|
| **Interest Rates** |
| FEDFUNDS | Federal Funds Rate | Monthly |
| DFF | Federal Funds Effective Rate | Daily |
| T10Y2Y | 10Y-2Y Treasury Spread (Yield Curve) | Daily |
| T10YIE | 10-Year Breakeven Inflation Rate | Daily |
| **Inflation** |
| CPIAUCSL | Consumer Price Index (CPI) | Monthly |
| CPILFESL | Core CPI (ex Food & Energy) | Monthly |
| PCEPI | PCE Price Index | Monthly |
| PCEPILFE | Core PCE | Monthly |
| **Employment** |
| UNRATE | Unemployment Rate | Monthly |
| PAYEMS | Nonfarm Payrolls | Monthly |
| ICSA | Initial Jobless Claims | Weekly |
| U6RATE | U-6 Unemployment Rate | Monthly |
| **GDP & Growth** |
| GDP | Gross Domestic Product | Quarterly |
| GDPC1 | Real GDP | Quarterly |
| GDPPOT | Real Potential GDP | Quarterly |
| **Consumer & Business** |
| UMCSENT | Consumer Sentiment Index | Monthly |
| RSXFS | Retail Sales | Monthly |
| INDPRO | Industrial Production Index | Monthly |
| HOUST | Housing Starts | Monthly |
| PERMIT | Building Permits | Monthly |
| **Credit & Money** |
| M2SL | M2 Money Stock | Weekly |
| TOTCI | Commercial & Industrial Loans | Weekly |
| DRTSCILM | Bank Lending Standards | Quarterly |

## Database Schema

Economic indicators are stored in the `economic_indicators` table:

```sql
CREATE TABLE economic_indicators (
    series_id VARCHAR NOT NULL,         -- FRED series ID (e.g., 'FEDFUNDS')
    indicator_name VARCHAR NOT NULL,    -- Human-readable name
    date DATE NOT NULL,                 -- Observation date
    value DECIMAL(18, 6),              -- Indicator value (NULL if missing)
    units VARCHAR,                      -- Units of measurement
    created_at TIMESTAMP,
    PRIMARY KEY (series_id, date)
)
```

## Usage in Code

### Fetch Indicator Data

```python
from src.data.collectors.fred_collector import FREDCollector
from datetime import datetime, timedelta

collector = FREDCollector()

# Fetch Federal Funds Rate (last 5 years)
indicators = collector.get_economic_indicator(
    series_id="FEDFUNDS",
    start_date=datetime.now() - timedelta(days=365*5),
    end_date=datetime.now()
)

for ind in indicators:
    print(f"{ind.date}: {ind.value}%")
```

### Get Latest Values

```python
collector = FREDCollector()
latest_values = collector.get_latest_values()

# Check current Fed Funds Rate
fed_rate = latest_values["FEDFUNDS"]
print(f"Current Fed Funds Rate: {fed_rate.value}%")
print(f"As of: {fed_rate.date}")

# Check unemployment
unemployment = latest_values["UNRATE"]
print(f"Unemployment Rate: {unemployment.value}%")
```

### Query from Database

```python
from src.data.storage.market_data_db import MarketDataDB

with MarketDataDB() as db:
    # Get all CPI data
    cpi_data = db.get_economic_indicators(
        series_id="CPIAUCSL",
        start_date=datetime(2020, 1, 1)
    )

    # Get latest value for any series
    latest_date = db.get_latest_economic_date("FEDFUNDS")
    print(f"Latest Fed data: {latest_date}")
```

## Feature Engineering Examples

Economic indicators are perfect for market prediction models:

### 1. Fed Policy Indicator

```python
# Rising rates = hawkish, falling rates = dovish
fed_rate_change = current_fed_rate - fed_rate_3_months_ago
```

### 2. Yield Curve Inversion

```python
# Negative spread = inverted yield curve = recession warning
yield_curve = T10Y2Y_value  # Already pre-calculated by FRED
is_inverted = yield_curve < 0
```

### 3. Inflation Momentum

```python
# Accelerating inflation may trigger Fed tightening
cpi_mom = (current_cpi - prev_month_cpi) / prev_month_cpi
```

### 4. Employment Strength

```python
# Strong labor market = delayed rate cuts
unemployment_trend = unemployment_3mo_avg - unemployment_6mo_avg
```

## Resume Safety

The fetch script is resume-safe:
- Checks latest date for each series in the database
- Only fetches data after the latest date
- Skips series that are already up to date
- Uses `INSERT OR REPLACE` to handle duplicates

## Best Practices

1. **Initial Backfill**: Fetch 5 years of data to start:
   ```powershell
   .\tasks.ps1 fetch-economic
   ```

2. **Daily Updates**: Run after 4 PM ET to catch any new releases:
   ```powershell
   .\tasks.ps1 update-daily
   ```

3. **Check Stats**: Verify data coverage:
   ```powershell
   .\tasks.ps1 db-stats
   ```

4. **Monitor Frequency**: Most indicators are monthly, some are weekly/daily/quarterly

5. **Handle Missing Values**: FRED returns "." for missing values (converted to NULL)

## API Rate Limits

- Free tier: 120 requests/minute
- Our script: ~23 series × ~5 years = manageable
- Includes automatic retry logic with exponential backoff

## Integration with Market Data

Economic indicators complement your market data:

```python
# Example: Combine Fed policy with market volatility
if fed_rate_rising and vix_value > 20:
    market_signal = "CAUTION"
elif unemployment_falling and yield_curve_normal:
    market_signal = "BULLISH"
```

## Troubleshooting

### Missing API Key

```
ValueError: FRED_API_KEY must be provided or set in environment
```

**Solution**: Add `FRED_API_KEY` to your `.env` file.

### No Data Returned

Some series have limited historical data or may be discontinued. Check FRED website for data availability.

### Rate Limit Errors

If you hit rate limits, the retry logic will automatically back off. For large backfills, the script may take 5-10 minutes.

## Next Steps

After fetching economic data:

1. **Calculate Derived Features**: Yield curve slope, inflation acceleration, etc.
2. **Create Economic Calendar**: Track upcoming releases (CPI, NFP, FOMC)
3. **Build Regime Detection**: Identify economic regimes (expansion, recession, etc.)
4. **Integrate with ML Model**: Use as features for CatBoost market prediction

## Resources

- [FRED API Docs](https://fred.stlouisfed.org/docs/api/fred/)
- [FRED Data Series](https://fred.stlouisfed.org/categories)
- [Economic Calendar](https://www.investing.com/economic-calendar/)
