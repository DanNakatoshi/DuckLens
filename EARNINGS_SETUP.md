# Earnings Calendar Setup

The system now supports earnings data from two sources. You can add either or both API keys - the system will auto-detect and use the best one available.

## Option 1: Finnhub (Recommended - Fastest)

**Why Finnhub?**
- ✅ 60 API calls/minute (vs Alpha Vantage's 25/day!)
- ✅ Fetch all 62 tickers in ~2 minutes
- ✅ Free tier is very generous

**Setup:**

1. Get free API key: https://finnhub.io/register
2. Add to `.env` file:
   ```
   FINNHUB_API_KEY=your_key_here
   ```

## Option 2: Alpha Vantage (Fallback)

**Why Alpha Vantage?**
- ✅ Free tier available
- ⚠️ Only 25 calls/day limit (can only fetch 25 tickers)
- ⚠️ Slower: ~5 minutes for 25 tickers

**Setup:**

1. Get free API key: https://www.alphavantage.co/support/#api-key
2. Add to `.env` file:
   ```
   ALPHA_VANTAGE_API_KEY=your_key_here
   ```

## Initial Data Fetch

After adding your API key(s), run:

```powershell
# From menu (option 13) - RECOMMENDED (auto-retry)
.\menu.ps1

# Or directly with auto-retry
.\tasks.ps1 fetch-earnings

# Or with Python (auto-retry until complete)
python scripts/fetch_earnings_retry.py

# Manual single-run (no retry)
python scripts/fetch_earnings.py
```

**Auto-Retry Feature:**
- ✅ Automatically retries up to 3 times if data is incomplete
- ✅ Checks coverage after each attempt (target: 80%+ tickers)
- ✅ Shows missing tickers and retry progress
- ✅ Handles API failures gracefully with 30-second delays

## Auto-Detection

The script automatically:
1. Checks which API keys you have configured
2. Prefers Finnhub (faster) if available
3. Falls back to Alpha Vantage if Finnhub not configured
4. Handles rate limiting automatically

## Smart Fetching Strategy (Saves API Calls!)

**Default: Next 90 Days Only (Recommended)**
- ✅ Confirmed earnings dates only
- ✅ Saves API calls by avoiding far-future estimates
- ✅ Perfect for daily trading (1 quarter ahead)

```powershell
# Default: Next 90 days (confirmed dates)
python scripts/fetch_earnings.py

# Even shorter range (60 days)
python scripts/fetch_earnings.py --days-ahead 60

# Backtest mode: Includes past 365 days
python scripts/fetch_earnings.py --include-historical
```

**Why 90 days?**
- Companies announce earnings ~1 month in advance
- Beyond 90 days = mostly estimates (low accuracy)
- Saves API calls for what matters: near-term confirmed dates

## Force Specific API

You can override auto-detection:

```powershell
# Force Finnhub
python scripts/fetch_earnings.py --source finnhub

# Force Alpha Vantage
python scripts/fetch_earnings.py --source alphavantage

# Limit Alpha Vantage to fewer tickers
python scripts/fetch_earnings.py --source alphavantage --limit 10
```

## What Happens Next?

Once earnings data is loaded:

1. **Morning Check** will show "Earnings: X days" for each ticker
2. **Signal Confidence** will be adjusted:
   - 🚫 **0-2 days before**: Earnings filter BLOCKS trade (too risky)
   - ⚠️ **3-10 days before**: -15% confidence penalty
   - ✅ **1-3 days after**: +5% confidence boost (relief rally)
3. **Trade Journal** will log earnings proximity for every trade

## Refresh Schedule

Earnings dates change, so refresh weekly:

```powershell
# Run weekly (auto-retry ensures completeness)
.\tasks.ps1 fetch-earnings
```

## Advanced Retry Options

Customize the retry behavior:

```powershell
# More aggressive retries (up to 5 attempts)
python scripts/fetch_earnings_retry.py --max-attempts 5

# Require 90% coverage (stricter)
python scripts/fetch_earnings_retry.py --min-coverage 0.90

# Faster retries (15 second delay)
python scripts/fetch_earnings_retry.py --retry-delay 15

# Combined with other options
python scripts/fetch_earnings_retry.py --max-attempts 5 --days-ahead 60
```

## Troubleshooting

**If some tickers still missing after retries:**

1. **Check if earnings announced yet**
   - Some tickers may not have Q4 dates announced
   - This is normal - not all companies announce 90 days ahead

2. **Try alternate API source**
   ```powershell
   python scripts/fetch_earnings_retry.py --source alphavantage
   ```

3. **Check individual ticker manually**
   ```powershell
   python scripts/fetch_earnings.py --source finnhub
   # Look for error messages for specific tickers
   ```

The earnings filter is already integrated into your strategy - it will activate as soon as you add an API key and fetch the data!
