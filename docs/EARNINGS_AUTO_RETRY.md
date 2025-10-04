# Earnings Auto-Retry Feature

## Problem Solved

> "Is it possible to have this option to repeat until the necessary data is complete fetching?"

**Answer: YES!** ✅ Menu option 13 now includes automatic retry.

## How It Works

### Intelligent Retry Logic

```
Attempt 1: Fetch all 62 tickers
├─ Success: Got 58/62 (93.5%) ✓
├─ Coverage check: 93.5% > 80% target ✓
└─ DONE! ✓

OR if incomplete:

Attempt 1: Fetch all 62 tickers
├─ Success: Got 45/62 (72.6%)
├─ Coverage check: 72.6% < 80% target ✗
├─ Wait 30 seconds...
│
Attempt 2: Fetch all 62 tickers again
├─ Success: Got 52/62 (83.9%) ✓
├─ Coverage check: 83.9% > 80% target ✓
└─ DONE! ✓
```

### Features

✅ **Automatic retry** - Up to 3 attempts by default
✅ **Coverage tracking** - Shows progress after each attempt
✅ **Missing ticker report** - Lists exactly what's missing
✅ **Smart delays** - 30 second wait between retries (respects API limits)
✅ **Success threshold** - Completes when ≥80% of tickers have data
✅ **Pass-through args** - All fetch_earnings.py options work

## Usage

### Simple (Recommended)

```powershell
# From menu - option 13
.\menu.ps1

# Or directly
.\tasks.ps1 fetch-earnings
```

This automatically:
1. Fetches next 90 days of earnings
2. Checks coverage (target: 80%+ tickers)
3. Retries up to 3 times if incomplete
4. Shows missing tickers at end

### Advanced Options

```powershell
# More retries (up to 5 attempts)
python scripts/fetch_earnings_retry.py --max-attempts 5

# Stricter coverage requirement (90%)
python scripts/fetch_earnings_retry.py --min-coverage 0.90

# Faster retries (15 second delay)
python scripts/fetch_earnings_retry.py --retry-delay 15

# Shorter date range (60 days)
python scripts/fetch_earnings_retry.py --days-ahead 60

# Include historical data for backtesting
python scripts/fetch_earnings_retry.py --include-historical

# Force specific API
python scripts/fetch_earnings_retry.py --source finnhub
python scripts/fetch_earnings_retry.py --source alphavantage
```

## Example Output

```
======================================================================
FETCH EARNINGS WITH AUTO-RETRY
======================================================================

Watchlist: 62 tickers
Target: 50+ tickers (80% coverage)
Max attempts: 3

======================================================================
ATTEMPT 1/3
======================================================================

Using: Finnhub API (60 calls/minute)
Date range: Next 90 days
Estimated time: ~1.1 minutes

Fetching earnings for 62 tickers from Finnhub
Rate limit: 60 calls/minute (much better than Alpha Vantage!)

[GOOGL] ✓ Next earnings: 2025-10-28 (26 days)
[AAPL] ✓ Next earnings: 2025-10-23 (21 days)
[MSFT] ✓ Next earnings: 2025-10-28 (26 days)
...

======================================================================
RESULTS: Fetched 58 earnings dates
======================================================================

✓ Saved 58 earnings dates to database

======================================================================
COVERAGE CHECK
======================================================================
Tickers with earnings: 58/62 (93.5%)

✓ SUCCESS! Earnings data is complete

⚠ Missing earnings for 4 tickers:
   - CSIQ
   - BE
   - TSM
   - BA

These tickers may not have announced earnings yet.

======================================================================
```

## Why Some Tickers Are Missing

**Normal reasons:**
1. **Not announced yet** - Companies announce earnings 2-4 weeks in advance
2. **Beyond 90 days** - Using `--days-ahead 90` only fetches confirmed dates
3. **Irregular schedule** - Some companies announce on different cycles
4. **API limitations** - Free tier may have data gaps

**This is OK!** The system:
- ✅ Works fine with 80%+ coverage
- ✅ Shows "Earnings: Unknown" for missing tickers
- ✅ Doesn't block trades (just doesn't apply earnings boost/penalty)
- ✅ Updates automatically when you re-run weekly

## Comparison: Old vs New

### Old Way (Manual)
```powershell
# Run once
python scripts/fetch_earnings.py

# Check manually
# If incomplete, run again
python scripts/fetch_earnings.py

# Check again
# If still incomplete, run again
python scripts/fetch_earnings.py

# Finally check in database...
```

### New Way (Auto-Retry) ✅
```powershell
# Just run once - it handles everything
.\tasks.ps1 fetch-earnings
```

Done! No manual checking needed.

## When to Use Each Mode

### Use Auto-Retry (Default)
- ✅ Weekly refresh (menu option 13)
- ✅ Initial setup
- ✅ After adding new tickers
- ✅ When you want "set and forget"

### Use Manual (Single-Run)
- 🔧 Testing/debugging
- 🔧 Custom date ranges
- 🔧 Quick spot checks
- 🔧 When you want to control retries yourself

```powershell
# Manual mode (no retry)
python scripts/fetch_earnings.py
```

## Error Handling

The retry script handles:
- ✅ API failures (network issues, rate limits)
- ✅ Incomplete data (missing tickers)
- ✅ Invalid API keys (shows setup instructions)
- ✅ Timeout issues (respects delays)

## Integration with Daily Update

You can add to daily update workflow:

```python
# In scripts/update_daily_data.py (optional)

print("Fetching Earnings Calendar (with retry)")
subprocess.run([
    "python", "scripts/fetch_earnings_retry.py",
    "--max-attempts", "2",  # Quick retries for daily
    "--retry-delay", "15"   # Faster for automation
])
```

## Summary

**You asked:** Can the fetch repeat until complete?

**We built:**
- ✅ Auto-retry wrapper script
- ✅ Coverage tracking (80%+ target)
- ✅ Smart delays (respects API limits)
- ✅ Missing ticker reports
- ✅ Integrated into menu (option 13)
- ✅ All options configurable

**Usage:**
```powershell
# Simple
.\tasks.ps1 fetch-earnings

# Advanced
python scripts/fetch_earnings_retry.py --max-attempts 5 --min-coverage 0.90
```

No more manual checking - it just works! 🎯
