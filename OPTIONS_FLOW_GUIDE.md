# Options Flow Analysis Guide

Complete guide to the options flow analysis system for CatBoost market prediction.

## Overview

The options flow system tracks smart money positioning through options activity, providing critical features for machine learning models. It calculates put/call ratios, unusual volume detection, open interest changes, and sentiment signals that help predict market direction.

## Key Features for CatBoost

### 1. **Sentiment Indicators**
- **Put/Call Ratio**: Primary sentiment gauge (>1 = bearish, <1 = bullish)
- **P/C Ratio MA5**: 5-day moving average to smooth noise
- **P/C Ratio Percentile**: Current P/C vs 52-week range (0-100)

### 2. **Smart Money Flow**
- **Smart Money Index**: `(Call@Ask - Put@Ask) / Total Volume`
  - Positive = Bullish aggression (buying calls, selling puts)
  - Negative = Bearish aggression (buying puts, selling calls)
- **OI Momentum**: `(Today OI - Yesterday OI) / Yesterday OI`
  - Positive = Accumulation
  - Negative = Distribution

### 3. **Unusual Activity**
- Contracts with volume 3x+ their 20-day average
- High count signals institutional positioning

### 4. **Volatility Features**
- **IV Rank**: Current IV percentile vs 52-week range
  - 0 = Lowest volatility in year
  - 100 = Highest volatility in year
- **IV Skew**: Put IV - Call IV (fear gauge)
  - Positive = Puts expensive (fear)
  - Negative = Calls expensive (greed)

### 5. **Directional Indicators**
- **Delta-Weighted Volume**: `sum(delta * volume)` - Net directional exposure
- **Gamma Exposure**: Total gamma risk in the market

### 6. **Support/Resistance**
- **Max Pain Price**: Strike where most options expire worthless
- **High OI Call Strike**: Resistance level
- **High OI Put Strike**: Support level
- **Max Pain Distance**: `(Price - Max Pain) / Price`

### 7. **Signals**
- **Flow Signal**: BULLISH / BEARISH / NEUTRAL
  - Combines P/C ratio, smart money, OI momentum, unusual activity

## Setup

### 1. Ensure Polygon API Key

Your `.env` should have:
```
POLYGON_API_KEY=your_key_here
```

Options Starter plan provides:
- 15-minute delayed data (sufficient for daily analysis)
- 2 years historical data
- Chain snapshots with volume, OI, IV, greeks

### 2. Database Tables

Three tables store options data:

**options_flow_daily** - Daily aggregates
```sql
PRIMARY KEY (ticker, date)
Stores: P/C ratio, volume, OI, greeks, unusual activity
```

**options_flow_indicators** - CatBoost features
```sql
PRIMARY KEY (ticker, date)
Stores: All derived metrics for ML
```

**options_contracts_snapshot** - Individual contracts
```sql
PRIMARY KEY (contract_ticker, snapshot_date)
Stores: Strike, expiry, greeks, IV, quotes
```

## Usage

### Fetch Historical Data (Backfill)

```powershell
# Fetch 2 years for all tickers (may take 30-60 minutes)
.\tasks.ps1 fetch-options-flow

# Fetch specific ticker
poetry run python scripts/fetch_options_flow.py --ticker SPY

# Fetch last 30 days
poetry run python scripts/fetch_options_flow.py --days 30

# Custom date range
poetry run python scripts/fetch_options_flow.py --start-date 2024-01-01 --end-date 2024-12-31
```

### Calculate Indicators

```powershell
# Calculate all indicators
.\tasks.ps1 calc-options-metrics

# Calculate with signal display
poetry run python scripts/calculate_options_metrics.py --show-signals

# Calculate for specific ticker
poetry run python scripts/calculate_options_metrics.py --ticker SPY --show-signals

# Calculate last 30 days
poetry run python scripts/calculate_options_metrics.py --days 30
```

### View Current Signals

```powershell
# Show today's flow signals for all tickers
.\tasks.ps1 show-options-flow
```

Output example:
```
Ticker   Date         Signal        P/C      Unusual    IV Rank
----------------------------------------------------------------------
SPY      2025-01-15   BULLISH 📈    0.85     15         68
QQQ      2025-01-15   NEUTRAL ➡️    1.02     8          72
IWM      2025-01-15   BEARISH 📉    1.35     22         85
```

### Run Tests

```powershell
.\tasks.ps1 test-options-flow
```

## Daily Workflow

The options flow automatically integrates with your daily update:

```powershell
.\tasks.ps1 update-daily
```

This will:
1. Update stock prices
2. Update short data
3. Update economic indicators
4. **Update options flow** ← NEW
5. Calculate technical indicators
6. **Calculate options indicators** ← NEW

## CatBoost Feature Engineering

### Loading Features for ML

```python
from src.data.storage.market_data_db import MarketDataDB
import pandas as pd

with MarketDataDB() as db:
    # Load all options features for SPY
    query = """
        SELECT *
        FROM options_flow_indicators
        WHERE ticker = 'SPY'
        ORDER BY date
    """

    features_df = db.conn.execute(query).fetchdf()

    # Combine with other features
    # - Stock prices (OHLCV)
    # - Technical indicators (RSI, MACD, etc.)
    # - Economic indicators (FRED data)
    # - Economic calendar events
```

### Key Features for Model

**Most Important Features (based on market prediction literature):**

1. **put_call_ratio** - Primary sentiment indicator
2. **smart_money_index** - Institutional flow direction
3. **iv_rank** - Volatility regime
4. **oi_momentum** - Positioning changes
5. **unusual_activity_score** - Institutional interest
6. **flow_signal** - Composite signal (categorical)

**Secondary Features:**

7. **put_call_ratio_ma5** - Trend smoothing
8. **iv_skew** - Fear/greed gauge
9. **delta_weighted_volume** - Directional bias
10. **max_pain_distance** - Price targets

### Example Feature Matrix

```python
# Create feature set for CatBoost
features = [
    # Options flow
    'put_call_ratio',
    'put_call_ratio_ma5',
    'smart_money_index',
    'oi_momentum',
    'unusual_activity_score',
    'iv_rank',
    'iv_skew',
    'delta_weighted_volume',
    'gamma_exposure',
    'max_pain_distance',
    'days_to_nearest_expiry',

    # Technical indicators
    'rsi_14',
    'macd',
    'sma_50',
    'atr_14',

    # Economic
    'fed_funds_rate',
    'cpi_yoy',
    'days_since_cpi',

    # Calendar
    'days_to_fomc',

    # Categorical
    'flow_signal',  # BULLISH/BEARISH/NEUTRAL
]

# Target variable (what we're predicting)
target = 'market_direction_5d'  # Market up/down in next 5 days
```

## Interpretation Guide

### Put/Call Ratio

- **< 0.7**: Extremely bullish (complacency risk)
- **0.7 - 0.9**: Bullish
- **0.9 - 1.1**: Neutral
- **1.1 - 1.3**: Bearish
- **> 1.3**: Extremely bearish (contrarian bullish signal)

### Smart Money Index

- **> 0.2**: Strong bullish aggression
- **0.1 to 0.2**: Bullish
- **-0.1 to 0.1**: Neutral
- **-0.2 to -0.1**: Bearish
- **< -0.2**: Strong bearish aggression

### OI Momentum

- **> 10%**: Strong accumulation (bullish if calls, bearish if puts)
- **5% to 10%**: Moderate accumulation
- **-5% to 5%**: Neutral
- **-10% to -5%**: Moderate distribution
- **< -10%**: Strong distribution

### IV Rank

- **> 80**: High volatility environment (expect mean reversion)
- **50 - 80**: Above average volatility
- **20 - 50**: Normal volatility
- **< 20**: Low volatility (potential expansion ahead)

### Flow Signal

- **BULLISH**: Multiple positive indicators align
- **NEUTRAL**: Mixed signals or low conviction
- **BEARISH**: Multiple negative indicators align

## Advanced Usage

### Finding Unusual Activity

```python
# Query contracts with unusual volume
query = """
    SELECT
        underlying_ticker,
        strike_price,
        expiration_date,
        contract_type,
        volume,
        open_interest,
        implied_volatility
    FROM options_contracts_snapshot
    WHERE snapshot_date = '2025-01-15'
      AND underlying_ticker = 'SPY'
      AND volume > 1000  -- Unusual threshold
    ORDER BY volume DESC
    LIMIT 20
"""

unusual_contracts = db.conn.execute(query).fetchdf()
```

### Tracking OI Changes

```python
# Track open interest growth over time
query = """
    SELECT
        date,
        total_call_oi,
        total_put_oi,
        call_oi_change,
        put_oi_change
    FROM options_flow_daily
    WHERE ticker = 'SPY'
      AND date >= '2024-12-01'
    ORDER BY date
"""

oi_trend = db.conn.execute(query).fetchdf()
```

### Finding Support/Resistance

```python
# Current high OI strikes
query = """
    SELECT ticker, date, high_oi_call_strike, high_oi_put_strike
    FROM options_flow_indicators
    WHERE ticker = 'SPY'
    ORDER BY date DESC
    LIMIT 1
"""

levels = db.conn.execute(query).fetchone()
print(f"Call resistance: {levels[2]}")
print(f"Put support: {levels[3]}")
```

## Data Quality Notes

### Limitations

1. **15-Minute Delay**: Data is delayed, not real-time
2. **2-Year History**: Polygon Starter plan limits historical data
3. **Chain Snapshot**: Captures state at query time (not true historical)
4. **Weekend Gaps**: No data Saturday/Sunday
5. **Holidays**: Market closed days have no data

### Best Practices

1. **Run After Market Close**: Update daily after 4:30 PM ET
2. **Check for Gaps**: Use resume-safe fetch to backfill missing dates
3. **Validate Signals**: Cross-reference with price action
4. **Monitor API Limits**: Polygon has rate limits (120 req/min)

## Troubleshooting

### No Contracts Returned

**Issue**: `fetch_options_flow` returns "No contracts"

**Solutions**:
- Check if ticker has options (some ETFs don't)
- Widen strike price range (±20% may be too narrow)
- Verify ticker symbol is correct
- Check if market was open that day

### High Memory Usage

**Issue**: System runs out of memory during backfill

**Solutions**:
- Fetch one ticker at a time: `--ticker SPY`
- Reduce date range: `--days 30`
- Process in batches

### Slow Performance

**Issue**: Queries are slow

**Solutions**:
- Ensure indexes are created (automatically done on init)
- Use date filters in queries
- Consider aggregating to weekly for longer backtests

## Next Steps: CatBoost Training

After populating options flow data:

1. **Define Target Variable**
   - What are we predicting? (Market direction, volatility, specific moves)
   - Timeframe? (1-day, 5-day, 1-month ahead)
   - Classification or regression?

2. **Feature Engineering**
   - Combine options flow + technical + economic + calendar
   - Create lagged features (yesterday's P/C ratio, etc.)
   - Interaction features (P/C * VIX, etc.)

3. **Train/Test Split**
   - Walk-forward validation (avoid look-ahead bias)
   - Use 70% train, 15% validation, 15% test

4. **Model Training**
   - CatBoost handles categorical features natively
   - Use early stopping to prevent overfitting
   - Optimize hyperparameters

5. **Backtesting**
   - Test signals on historical data
   - Calculate metrics (accuracy, Sharpe ratio, max drawdown)
   - Evaluate across different market regimes

Ready to start CatBoost training? Let me know!

## Resources

- [Polygon Options API Docs](https://polygon.io/docs/options)
- [Put/Call Ratio Interpretation](https://www.investopedia.com/terms/p/putcallratio.asp)
- [Open Interest Analysis](https://www.investopedia.com/terms/o/openinterest.asp)
- [CatBoost Documentation](https://catboost.ai/docs/)
