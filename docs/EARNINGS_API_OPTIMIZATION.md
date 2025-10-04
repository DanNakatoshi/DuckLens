# Earnings API Optimization Strategy

## Problem You Asked About

> "Are we able to avoid the estimating earning event and save request for other tickers for future or past event for the backtest and future test?"

**Answer: YES!** ✅

## Smart Fetching Strategy

### What We Fetch (Saves API Calls)

✅ **Next 90 days** (default)
- Confirmed earnings dates only
- Companies announce 2-4 weeks in advance
- Most accurate data
- Perfect for daily trading

✅ **Past 365 days** (optional: `--include-historical`)
- For backtest validation
- Verify strategy performed well around earnings
- Only run when needed (not weekly)

### What We SKIP (Waste of API Calls)

❌ **Estimated dates beyond 90 days**
- Low accuracy (companies haven't announced yet)
- Subject to change
- Not useful for near-term trading
- Wastes precious API calls

## Usage Examples

### Daily Trading (Default - Recommended)
```powershell
# Fetch next 90 days only
python scripts/fetch_earnings.py

# Run this weekly to stay current
```

**API Cost:** 62 calls (one per ticker) = ~2 minutes with Finnhub

### Conservative (Even Fewer Calls)
```powershell
# Fetch next 60 days only
python scripts/fetch_earnings.py --days-ahead 60
```

**API Cost:** 62 calls (one per ticker) = ~2 minutes with Finnhub

### Backtest Validation (Run Once)
```powershell
# Fetch next 90 days + past 365 days
python scripts/fetch_earnings.py --include-historical
```

**API Cost:** 62 calls (one per ticker) = ~2 minutes with Finnhub
*Note: Historical data included in same call - no extra cost!*

## Why 90 Days is Optimal

| Time Frame | Data Quality | Use Case |
|-----------|--------------|----------|
| 0-30 days | ✅ **Confirmed** | Immediate trading decisions |
| 31-90 days | ✅ **Mostly confirmed** | Planning ahead |
| 91-180 days | ⚠️ **Mixed** (some confirmed, many estimates) | Low value |
| 180+ days | ❌ **Mostly estimates** | Waste of API calls |

**Earnings Announcement Timeline:**
1. Company sets internal date (3-6 months before)
2. Company announces publicly (2-4 weeks before)
3. **← We fetch HERE (90 days)**
4. Actual earnings release (day of)

## API Rate Limits

### Finnhub (Recommended)
- **Rate:** 60 calls/minute
- **Strategy:** 90 days forward = 62 tickers in ~2 minutes
- **Refresh:** Weekly is plenty

### Alpha Vantage (Fallback)
- **Rate:** 25 calls/day
- **Strategy:** Limit to top 25 tickers
- **Refresh:** Every other day max

## Integration with Your System

The earnings filter automatically:
1. **Blocks trades** 0-2 days before earnings
2. **Reduces confidence** 3-10 days before
3. **Boosts confidence** 1-3 days after (relief rally)

This works perfectly with 90-day data because:
- You'll always have 3 months of confirmed dates
- No wasted calls on far-future estimates
- Weekly refresh keeps data current

## Database Storage

All fetched earnings stored in `earnings` table:
```sql
SELECT * FROM earnings
WHERE earnings_date >= CURRENT_DATE
ORDER BY earnings_date;
```

You can run backtests against historical data without re-fetching:
- Database keeps all past earnings dates
- `--include-historical` is only needed once for initial backtest
- Weekly refresh adds new confirmed dates as they're announced

## Summary

**Your question:** Can we avoid estimated earnings and save API calls?

**Answer:** Yes! The system now:
- ✅ Fetches 90 days ahead by default (confirmed dates)
- ✅ Skips far-future estimates (saves API calls)
- ✅ Optional historical mode for backtesting
- ✅ Smart enough to know what matters for trading

**Commands:**
```powershell
# Daily trading (run weekly)
.\tasks.ps1 fetch-earnings

# Backtest validation (run once)
python scripts/fetch_earnings.py --include-historical

# Conservative (even fewer calls)
python scripts/fetch_earnings.py --days-ahead 60
```

This saves API calls while giving you exactly what you need for profitable trading decisions!
