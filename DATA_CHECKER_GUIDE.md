# Data Integrity Checker - User Guide

## What It Does

The data integrity checker verifies that all your market data is complete and identifies any gaps before you start trading.

## How to Run

```bash
.\tasks.ps1 check-data
```

## What It Checks

### ✅ CRITICAL (Must Have - Strategy Won't Work Without These)

1. **OHLCV Data** - Price history (Open, High, Low, Close, Volume)
   - **Status:** INCOMPLETE (only 5 years, need 10 years)
   - **Impact:** Can still trade, but limited backtest history
   - **Fix:** `.\tasks.ps1 fetch-10-years`

2. **Technical Indicators** - SMA, EMA, MACD calculations
   - **Status:** OK for most stocks
   - **Impact:** Strategy depends on these
   - **Fix:** `.\tasks.ps1 calc-indicators`

### ⚠️ OPTIONAL (Nice to Have - Strategy Works Without These)

3. **Short Volume Data** - Short selling activity
   - **Current:** 57.9% coverage (55/95 tickers)
   - **Impact:** Helps identify bearish sentiment, but not required
   - **Note:** Missing data is OK, just a warning

4. **Options Flow Data** - Options trading activity
   - **Current:** 32.6% coverage (31/95 tickers)
   - **Impact:** Shows institutional positioning, but not required
   - **Note:** Missing data is OK, just a warning

5. **Economic Indicators** - FRED data (GDP, unemployment, etc.)
   - **Current:** 6 series with recent data
   - **Impact:** Macro context, but not required
   - **Fix:** `.\tasks.ps1 fetch-economic`

---

## Exit Codes

The checker returns different exit codes for automation:

- **0** = All critical data present, ready to trade ✅
- **1** = Missing critical data (OHLCV or indicators) ❌
- **2** = Warnings only (optional data missing) ⚠️

---

## Understanding the Output

### Example: CRITICAL Issue

```
+-------------------------------------------------------------------+
| CRITICAL ISSUES FOUND (3)                                         |
|                                                                   |
|   - MSFT: MISSING OHLCV data - cannot trade this stock!           |
|   - AMZN: MISSING indicators - run calc-indicators!               |
|   - GOOGL: STALE data (last update: 2025-09-15)                  |
+-------------------------------------------------------------------+

Fix these issues before trading!
```

**What to do:** Run the suggested commands to fix critical issues before trading.

### Example: Warnings Only

```
+-------------------------------------------------------------------+
| WARNINGS (12)                                                     |
|                                                                   |
|   - META: OHLCV data incomplete (75.3% coverage)                  |
|   - JPM: OHLCV data incomplete (68.1% coverage)                   |
|   ... and 10 more                                                 |
|                                                                   |
| These are non-critical issues. Strategy can still work.           |
+-------------------------------------------------------------------+

Optional improvements:
  - .\tasks.ps1 fetch-10-years  (complete OHLCV data)
  - .\tasks.ps1 calc-indicators  (update all indicators)
```

**What to do:** Optional - you can trade now, but running these commands will give you more complete data.

### Example: All OK

```
+-------------------------------------------------------------------+
| ALL CRITICAL DATA PRESENT                                         |
|                                                                   |
|   ✓ OHLCV data: 95/95 tickers OK                                  |
|   ✓ Technical indicators: Calculated                              |
|   ✓ Short volume: 57.9% coverage                                  |
|   ✓ Options flow: 32.6% coverage                                  |
|   ✓ Economic data: 6 series                                       |
|                                                                   |
| Your strategy is ready to trade!                                  |
+-------------------------------------------------------------------+

System ready for trading!

Next steps:
  - .\tasks.ps1 morning   (morning check at 8 AM)
  - .\tasks.ps1 intraday  (trading decision at 3 PM)
```

**What to do:** You're ready to trade! Run morning/intraday checks.

---

## Common Issues & Fixes

### Issue 1: Missing OHLCV Data

**Symptom:**
```
MSFT: MISSING OHLCV data - cannot trade this stock!
```

**Cause:** New ticker added but data not fetched yet

**Fix:**
```bash
.\tasks.ps1 fetch-10-years
```

This will download 10 years of price history for all tickers (takes ~20-30 mins).

---

### Issue 2: Missing Indicators

**Symptom:**
```
AMZN: MISSING indicators - run calc-indicators!
```

**Cause:** Indicators not calculated yet

**Fix:**
```bash
.\tasks.ps1 calc-indicators
```

This calculates SMA, EMA, MACD for all tickers (takes ~2-3 mins).

---

### Issue 3: Stale Data

**Symptom:**
```
GOOGL: OHLCV data is stale (last update: 2025-09-25)
```

**Cause:** Data hasn't been updated in over 7 days

**Fix:**
```bash
.\tasks.ps1 update-daily
```

This fetches latest data for all tickers (takes ~5-10 mins).

---

### Issue 4: VIX Missing (Expected!)

**Symptom:**
```
VIX: MISSING OHLCV data - cannot trade this stock!
```

**Cause:** VIX is an index, not a stock - Polygon.io doesn't have stock data for it

**Fix:** This is expected and OK. You're not trading VIX directly anyway. The checker shows this as a "critical issue" but you can ignore it for VIX specifically. You use VXX (tradeable VIX ETF) instead, which should have data.

---

## When to Run the Checker

### 1. **After Adding New Tickers**
```bash
# You just added 39 new stocks
.\tasks.ps1 check-data
# Will show which new tickers need data
.\tasks.ps1 fetch-10-years
```

### 2. **Before Starting a New Trading Week**
```bash
# Monday morning before market open
.\tasks.ps1 check-data
```

### 3. **When Strategy Fails with "No Data" Errors**
```bash
# If morning_check or intraday fails
.\tasks.ps1 check-data
# Identify which ticker is missing data
```

### 4. **After System Downtime/Reinstall**
```bash
.\tasks.ps1 check-data
# Verify all data is intact
```

---

## Integration with Daily Workflow

**Recommended weekly routine:**

```bash
# Sunday night or Monday morning
.\tasks.ps1 check-data        # Verify data integrity
.\tasks.ps1 update-daily       # Fetch latest prices
.\tasks.ps1 calc-indicators    # Update indicators

# Then during the week:
.\tasks.ps1 morning            # 8 AM check
.\tasks.ps1 intraday           # 3 PM trading
```

---

## Summary

**Purpose:** Ensure all critical data is present before trading
**Command:** `.\tasks.ps1 check-data`
**Time:** ~10-30 seconds to run
**When:** After adding tickers, before weekly trading, or when errors occur

**Critical vs Optional:**
- CRITICAL = OHLCV + Indicators (must have)
- OPTIONAL = Short volume, options, economic (nice to have)

The checker will tell you exactly what's missing and how to fix it! 🎯
