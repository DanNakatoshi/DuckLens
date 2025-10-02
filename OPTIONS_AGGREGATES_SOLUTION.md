# Options Flow: Aggregates Solution

## Problem
The Options Chain Snapshot endpoint (`/v3/snapshot/options/{ticker}`) only returns **current** data, not historical snapshots from past dates. Historical chain snapshots require Polygon Options Advanced plan ($999/month).

## Solution
Use the **Options Aggregates endpoint** (`/v2/aggs/ticker/{optionsTicker}/range/1/day/{from}/{to}`) to fetch historical data for specific contracts.

### How It Works

1. **Calculate Key Strikes**: For each trading day, calculate 6 key strikes based on stock price:
   - ATM (at-the-money): closest to current price
   - ±5% OTM: 5% above/below current price
   - ±10% OTM: 10% above/below current price

2. **Construct Contract Tickers**: Use OCC format to build contract ticker symbols:
   ```
   Format: O:{UNDERLYING}{YYMMDD}{C/P}{STRIKE*1000:08d}
   Example: O:SPY240315C00510000 = SPY Call $510 expiring 2024-03-15
   ```

3. **Fetch Aggregates**: For each contract, fetch OHLCV data for the specific date

4. **Aggregate to Daily Flow**: Combine 6 contracts (3 calls + 3 puts) into daily flow metrics:
   - Put/Call ratio
   - Total volume by type
   - Unusual activity detection
   - Max pain calculation

## Test Results

**Test Date**: March 15, 2024
**Ticker**: SPY
**Stock Price**: $509.83

### Retrieved Data (9 contracts):

**Calls (5 strikes)**:
- ATM $510: 10,987 volume
- -5% $485: 28 volume
- +5% $535: 1,303 volume
- -10% $460: 721 volume
- +10% $560: 831 volume

**Puts (4 strikes)**:
- ATM $510: 9,880 volume
- -5% $485: 9,330 volume
- -10% $460: 7,971 volume
- +10% $560: 1 volume

**Metrics**:
- **Put/Call Ratio**: 1.96 (bearish sentiment)
- **Total Call Volume**: 13,870
- **Total Put Volume**: 27,182
- **Unusual Activity**: 2 call strikes, 3 put strikes with volume > 1,000

## Limitations vs Snapshots

### Available in Aggregates ✅
- Volume (actual trades)
- Price (OHLC)
- VWAP

### NOT Available in Aggregates ❌
- Open Interest (OI)
- Greeks (delta, gamma, theta, vega)
- Implied Volatility (IV)
- Bid/Ask quotes
- Bid/Ask sizes

### Workarounds

**For Open Interest**: Track from daily snapshots going forward (can't backfill)

**For Greeks/IV**:
- Option 1: Calculate ourselves using Black-Scholes (doable but complex)
- Option 2: Accept limitation and use volume-based metrics only
- Option 3: Use snapshots for recent data, aggregates for historical

## CatBoost Feature Impact

### Features Still Available (Volume-Based) ✅
1. **Put/Call Ratio** - Primary sentiment indicator
2. **Put/Call Ratio MA5** - Smoothed trend
3. **Put/Call Ratio Percentile** - Historical context
4. **Volume-weighted metrics** - Can use volume * price approximations
5. **Unusual Activity Score** - Based on volume thresholds
6. **Smart Money Index** - Volume at ask vs bid (limited without quotes)
7. **Max Pain Price** - Strike with highest total volume

### Features NOT Available (Requires OI/Greeks/IV) ❌
1. **OI Momentum** - Requires open interest tracking
2. **IV Rank** - Requires IV history
3. **IV Skew** - Requires call vs put IV
4. **Delta-weighted volume** - Requires delta
5. **Gamma exposure** - Requires gamma
6. **High OI strikes** - Requires open interest data

## Recommendations

### For Historical Backfill (2 years)
✅ **Use Aggregates** - Gets you:
- Put/Call ratios (primary indicator)
- Volume trends
- Price action
- Unusual volume spikes

### For Recent Data (Last 30 days)
✅ **Use Snapshots** - Gets you:
- All greeks, IV, OI
- Complete feature set
- Real-time quotes

### Hybrid Approach (Best of Both)
```
Historical (2+ years ago): Aggregates only
Recent (30 days):          Snapshots with full data
Daily Updates:             Snapshots for new data
```

This gives you:
- Long history for P/C ratio trends (2+ years)
- Full feature set for recent training data
- Cost-effective with Options Starter plan

## Implementation Status

### ✅ Completed
1. `polygon_options_flow.py`:
   - `calculate_key_strikes()` - Calculate ATM, ±5%, ±10%
   - `construct_contract_ticker()` - Build OCC format tickers
   - `find_contract_ticker()` - Auto-construct for historical dates
   - `get_options_aggregates()` - Fetch OHLCV for contracts
   - `get_historical_flow_via_aggregates()` - Full flow for a date

2. `fetch_options_flow.py`:
   - Updated to use aggregates approach
   - Resume-safe (checks existing data)
   - Monthly expiration tracking

3. `test_aggregates_approach.py`:
   - 5-test validation suite
   - **All tests passing** ✅

4. `tasks.ps1`:
   - Added `test-aggregates` command
   - Added `test-contract` command

### ⏭️ Next Steps
1. Run full 2-year backfill: `.\tasks.ps1 fetch-options-flow`
2. Calculate indicators: `.\tasks.ps1 calc-options-metrics`
3. Review signals: `.\tasks.ps1 show-options-flow`
4. Begin CatBoost model training

## Usage

```powershell
# Test the approach (already passed)
.\tasks.ps1 test-aggregates

# Fetch 2 years of historical data (30-60 min)
.\tasks.ps1 fetch-options-flow

# Calculate ML features
.\tasks.ps1 calc-options-metrics

# View current signals
.\tasks.ps1 show-options-flow
```

## Data Efficiency

**Per ticker per day**: 6 contracts (12 with calls+puts each)
**34 tickers × 500 days × 6 contracts** = ~102,000 API calls
**Polygon Options Starter**: Unlimited requests ✅

Estimated time: 30-60 minutes for full 2-year backfill
