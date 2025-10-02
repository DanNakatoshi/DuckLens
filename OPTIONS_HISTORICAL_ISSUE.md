# Options Historical Data Issue

## Problem Discovered

The Options Chain Snapshot endpoint (`/v3/snapshot/options/{ticker}`) only returns **current/recent** options data, not historical snapshots from past dates.

When trying to fetch data from 2024-03-14, the API returns 401 errors because:
1. Historical options snapshots require **Options Advanced** plan ($999/month)
2. The snapshot endpoint is designed for real-time/recent data only

## Your Current Access

✅ **Options Starter Plan** includes:
- Current options chain snapshots
- Options aggregates (OHLC for specific contracts)
- 2 years of aggregate history
- 15-minute delayed data

❌ **Does NOT include:**
- Historical chain snapshots from past dates
- Time-travel to see options chain as it was on specific dates

## Solutions

### Option 1: Current Data Only (Recommended)

Modify the approach to only fetch **today's** options data going forward:

```python
# Instead of backfilling 2 years
# Only fetch today's snapshot daily

# This gives you:
# - Today's put/call ratio
# - Today's unusual activity
# - Today's OI levels
# - Forward-looking features
```

**Pros:**
- Works with your current plan
- Still provides valuable ML features
- Can start collecting data from today forward

**Cons:**
- No historical options data for training
- Limited to ~60 days of data after 2 months of collection

### Option 2: Use Options Aggregates for Historical

Use the **Options Aggregates** endpoint instead:

```
GET /v2/aggs/ticker/{optionsTicker}/range/1/day/{from}/{to}
```

This requires knowing specific contract tickers (e.g., `O:SPY250930C00345000`).

**Approach:**
1. Get today's active contracts from snapshot
2. Use aggregates endpoint to get historical data for those contracts
3. Backfill last 2 years for key strikes (ATM, ATM±10%)

**Pros:**
- Works with your plan
- Gets 2 years of historical data
- Can calculate historical P/C ratios

**Cons:**
- More complex (need to track contracts)
- Only covers contracts that still exist today
- Missing expired contracts from past

### Option 3: Simplified Historical Estimation

Calculate estimated historical options metrics from:
1. **VIX** (volatility index - you already track this)
2. **Stock volatility** (from your OHLCV data)
3. **Volume patterns** (unusual volume in stock = likely unusual options)

**Pros:**
- No additional API calls needed
- Works with data you already have
- Still provides useful volatility/sentiment features

**Cons:**
- Not true options flow data
- Less accurate than real options data

### Option 4: Upgrade to Options Advanced

$999/month for historical options snapshots.

## Recommended Path Forward

**Phase 1: Start collecting current data (today)**
```powershell
# Modify script to only fetch today's snapshot
.\tasks.ps1 fetch-options-flow --days 1
```

Run this daily to build up historical data going forward.

**Phase 2: Use VIX as volatility proxy**

You already have VIX in your tickers. Use it as:
- Volatility regime indicator
- Fear/greed gauge
- Substitute for IV rank

**Phase 3: Add simple options aggregates**

For SPY only, fetch historical aggregates for:
- ATM call
- ATM put
- OTM call (+10%)
- OTM put (-10%)

This gives you basic P/C ratio estimation.

## Updated Feature Set (Without Historical Options)

You can still build a strong model with:

**Volatility Indicators:**
- VIX level (fear gauge)
- VIX changes (volatility of volatility)
- Stock volatility (ATR, Bollinger Band width)

**Sentiment Indicators:**
- Short interest changes
- Volume patterns
- Price momentum

**Economic Indicators:**
- All 23 FRED indicators
- Economic calendar events

**Technical Indicators:**
- All 8 indicators you have

This is still **50+ features** - plenty for CatBoost!

## Decision Needed

Which approach do you prefer?

1. ✅ **Start collecting today, proceed with current 50+ features** (recommended)
2. Build simplified historical using aggregates (complex)
3. Use VIX as volatility proxy (simple)
4. Upgrade to Options Advanced ($999/month)

Let me know and I'll implement the chosen solution!
