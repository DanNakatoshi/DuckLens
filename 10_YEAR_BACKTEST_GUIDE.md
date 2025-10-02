# 10-Year Backtest Guide

## Overview

You can now backtest your 2x leverage trend-following strategy across **10 years of historical data** for all watchlist tickers.

This will show you:
- ✓ How the strategy performed during different market regimes (2015-2025)
- ✓ Performance during COVID crash (2020)
- ✓ Performance during inflation era (2021-2022)
- ✓ Performance during current bull market (2023-2025)
- ✓ Win rate, average hold time, and trades per stock
- ✓ Which stocks are best suited for your strategy

---

## Quick Start (2 Commands)

### Step 1: Fetch 10 Years of Data (~30-60 minutes)

```powershell
.\tasks.ps1 fetch-10-years
```

**What it does:**
1. Fetches 10 years of OHLCV data for all 58 watchlist tickers
2. Automatically calculates all technical indicators
3. Saves everything to database

**Expected output:**
```
OHLCV Data:   58/58 tickers (150,000+ bars)
Indicators:   58/58 tickers
```

### Step 2: Run 10-Year Backtest (~5 minutes)

```powershell
.\tasks.ps1 backtest-10-years
```

**What it does:**
- Backtests every ticker with 2x leverage strategy
- Shows strategy return vs buy & hold
- Calculates win rate, trades, and average hold time
- Ranks top performers

**Expected output:**
```
Ticker   | Strategy     | Buy&Hold     | Outperform   | Trades | Win%  | Avg Days | Result
---------|--------------|--------------|--------------|--------|-------|----------|-------
NVDA     | +5200.50%    | +2100.30%    | +3100.20%    | 8      | 87.5% | 456      | WIN
AAPL     | +1850.20%    | +450.10%     | +1400.10%    | 12     | 91.7% | 304      | WIN
...
```

---

## What to Expect

### Market Regimes Covered (2015-2025)

**2015-2019: Bull Market**
- Steady uptrend with minor corrections
- Your strategy should outperform buy & hold by catching trends early

**2020: COVID Crash & Recovery**
- March crash: Death cross exit should save you 30-40%
- April-Dec rally: Golden cross entry should capture recovery

**2021-2022: Inflation & Bear Market**
- Fed rate hikes cause volatility
- Death cross exit protects during drawdowns
- Long-only avoids whipsaws in bear market

**2023-2025: AI Bull Market**
- NVDA, tech stocks explode
- 2x leverage amplifies gains
- Should see +1000-3000% on AI stocks

### Realistic 10-Year Results

**What's Good:**
- Total return: +500-2000% (across all stocks)
- Win rate: 70-90% (beat buy & hold)
- Average hold: 200-500 days (long-term trends)
- Trades: 5-15 per stock over 10 years

**What's Excellent:**
- Total return: +2000-5000% (NVDA, AAPL, tech leaders)
- Win rate: 85-95%
- Outperform: +1000-3000% vs buy & hold

**What's Concerning:**
- Total return: <100% (strategy failed)
- Win rate: <60% (losing vs buy & hold)
- Too many trades: >20 (overtrading, whipsaws)

---

## Interpreting Results

### Top Section: Individual Ticker Results

```
Ticker   | Strategy     | Buy&Hold     | Outperform   | Trades | Win%  | Avg Days | Result
NVDA     | +5200.50%    | +2100.30%    | +3100.20%    | 8      | 87.5% | 456      | WIN
```

**What to look at:**
1. **Outperform** - How much better than buy & hold?
   - >+500%: Excellent (2x leverage working)
   - +100-500%: Good (catching trends early)
   - <+100%: Okay (minimal improvement)
   - Negative: Bad (strategy hurt returns)

2. **Win%** - Did you beat buy & hold consistently?
   - >85%: Excellent
   - 70-85%: Good
   - <70%: Needs improvement

3. **Avg Days** - How long did you hold?
   - 300-500 days: Perfect (1-1.5 years = long-term trends)
   - 100-300 days: Okay (medium-term)
   - <100 days: Bad (overtrading, whipsaws)

4. **Trades** - How many trades over 10 years?
   - 5-12 trades: Perfect (2-3 major trends captured)
   - 15-20 trades: Okay (some whipsaws)
   - >25 trades: Bad (too much churn)

### Bottom Section: Portfolio Averages

```
Avg Strategy Return:  +1250.50%
Avg Buy&Hold Return:  +425.30%
Avg Outperformance:   +825.20%
Avg Trades per Stock: 9.2
Avg Win Rate:         82.5%
Avg Hold Period:      385 days (1.1 years)
```

**This tells you:**
- Whether the strategy works across **all** stocks (not just cherry-picked winners)
- Average outperformance (should be +500-1000% for good strategy)
- Whether you're holding long enough (should be 300-500 days)

---

## What Can Go Wrong?

### 1. No Data for Some Tickers

```
NEON     | N/A          | N/A          | N/A          | N/A    | N/A   | N/A      | NO DATA
```

**Fix:**
```powershell
python scripts/add_ticker.py NEON
```

### 2. Strategy Underperforms Buy & Hold

```
INTC     | +50.20%      | +125.50%     | -75.30%      | 15     | 60.0% | 120      | LOSE
```

**Reasons:**
- Stock is in sideways/choppy range (not trending)
- Too many whipsaws (look at trades: 15 is high)
- Short hold period (120 days = getting stopped out early)

**Solution:**
- Don't trade non-trending stocks
- Stick to NVDA, AAPL, GOOGL, etc. (clear trends)

### 3. Too Few Trades

```
VXX      | +5.20%       | +15.50%      | -10.30%      | 2      | 50.0% | 800      | LOSE
```

**Reason:**
- Stock doesn't trend (VXX is volatility, spikes up/down)
- Strategy designed for uptrending stocks, not mean-reverting

**Solution:**
- Remove VXX from trading (keep as crash indicator only)

---

## Top Performers Analysis

After running backtest, you'll see:

```
TOP 10 PERFORMERS (by outperformance vs Buy&Hold):
  1. NVDA      +3100.20%  (8 trades, 88% win rate, 456 day avg hold)
  2. AAPL      +1400.10%  (12 trades, 92% win rate, 304 day avg hold)
  3. GOOGL     +980.50%   (10 trades, 80% win rate, 365 day avg hold)
  ...
```

**These are your BEST stocks to trade:**
- Consistent trends
- High win rate
- Long hold periods (avoiding whipsaws)
- 2x leverage amplifying gains

**Focus on these for future trades!**

---

## Next Steps After Backtest

### 1. Review Top Performers

Focus your watchlist on stocks that:
- Beat buy & hold by >500%
- Win rate >80%
- Average hold >300 days

### 2. Check Current Signals

```powershell
.\tasks.ps1 watchlist
```

See if any top performers have BUY signals today.

### 3. Review Your Portfolio

```powershell
.\tasks.ps1 portfolio
```

Compare your holdings against top performers. Should you:
- Add positions in top performers?
- Exit positions in underperformers?

### 4. Set Up Daily Routine

```powershell
.\tasks.ps1 update-daily
```

Every day after market close:
1. Fetch latest data
2. See watchlist BUY/SELL signals
3. Review portfolio recommendations
4. Update positions interactively

---

## FAQ

**Q: Why 10 years instead of 5?**

A: 10 years covers more market cycles:
- 2015-2019: Bull market
- 2020: Crash & recovery
- 2021-2022: Bear market
- 2023-2025: AI bull market

This tests your strategy in all conditions.

**Q: Can I backtest just 1-2 stocks?**

A: Yes! Edit the script:

```python
# In backtest_10_years_all.py, line 108
for ticker in ["NVDA", "AAPL"]:  # Just these two
```

**Q: What if I only have 3 years of data?**

A: The backtest will run on whatever data you have. It auto-adjusts to available data range.

**Q: Why are some tickers missing data?**

A: They might be:
- New IPOs (< 10 years old)
- Delisted/renamed
- Not available on Polygon API

Run `python scripts/add_ticker.py TICKER` to try fetching manually.

**Q: Should I trade all stocks or just top performers?**

A: **Top performers only!** Focus on stocks with:
- >500% outperformance
- >80% win rate
- >300 day average hold

Quality > quantity.

---

## Summary

**To backtest 10 years:**

```powershell
# Step 1: Fetch data (30-60 min)
.\tasks.ps1 fetch-10-years

# Step 2: Run backtest (5 min)
.\tasks.ps1 backtest-10-years
```

**Look for:**
- Top performers (>500% outperformance)
- High win rate (>80%)
- Long hold periods (>300 days)

**Focus your trading on these winners!**
