# 🚀 Simple Start Guide - Test Your ETF Strategy

## Your Situation

You have **34 ETFs** (not individual stocks like AAPL):
- **Market**: SPY, QQQ, DIA, IWM, VTI
- **Sectors**: XLF, XLE, XLK, XLV, XLI, XLP, XLY, XLU, XLB, XLRE, XLC
- **Safe Haven**: GLD, TLT, TIP
- **Volatility**: VIX, UVXY, SVXY
- **Other**: HYG, LQD, BITO, COIN, UUP, USO, EFA, EEM, SQQQ, SH

## ✅ Quick Test (5 minutes)

Test your strategy using **ONLY indicators** (no ML training needed):

```powershell
# Fast test with your actual ETF data
.\tasks.ps1 test-indicators-only
```

**What this does**:
- Tests last 1 year with your 34 ETFs
- Uses technical indicators only:
  - Support reclaim
  - Breakout detection
  - Oversold bounce (RSI + MACD)
  - Momentum (options flow + indicators)
- No ML model training required
- Shows which tickers have data
- Runs backtest in ~5 minutes

**Example Output**:
```
Checking data availability...
  ✓ SPY    (252 days) - market_index
  ✓ QQQ    (252 days) - market_index
  ✓ GLD    (252 days) - safe_haven
  ✓ TLT    (252 days) - safe_haven
  ✓ XLF    (252 days) - sector
  ...

✓ 34/34 tickers have data

BACKTEST RESULTS (INDICATORS ONLY)
================================================================================

CAPITAL
--------------------------------------------------
Starting: $100,000.00
Ending:   $118,500.00
Return:   $18,500.00 (+18.50%)

TRADES
--------------------------------------------------
Total:    67
Winners:  38
Losers:   29
Win Rate: 56.7%

RISK METRICS
--------------------------------------------------
Sharpe Ratio:  1.42
Max Drawdown:  12.3%
Profit Factor: 1.85

TRADE ANALYSIS
--------------------------------------------------
SUPPORT_RECLAIM           18 trades | Win:  61.1% | P&L:   $7,240.00
BREAKOUT_HIGH             15 trades | Win:  60.0% | P&L:   $6,180.00
OVERSOLD_BOUNCE           21 trades | Win:  52.4% | P&L:   $3,820.00
MOMENTUM                  13 trades | Win:  53.8% | P&L:   $1,260.00
```

## 📊 With Detailed Reasoning

Want to see WHY each trade was made?

```powershell
# Same test + reasoning log
poetry run python scripts/test_strategy_indicators_only.py --verbose
```

This creates `indicator_strategy_test.log` with explanations like:

```
🟢 BUY SIGNAL: SPY
--------------------------------------------------------------------------------
🚀 BREAKOUT: Price broke above 30-day high ($520.50).
Momentum continuation pattern detected.

📊 Technical Context: Trend: bullish (SMA20 vs SMA50), RSI: 58.3, MACD: bullish

💰 Entry: $522.15 | SL: $480.38 (-8.0%) | TP: $600.50 (+15.0%)
🎯 Overall Confidence: 65.0%
```

## 🎯 Custom Tests

### Test Specific ETFs Only

```powershell
# Just major indices
poetry run python scripts/test_strategy_indicators_only.py --tickers SPY,QQQ,IWM

# Just safe havens
poetry run python scripts/test_strategy_indicators_only.py --tickers GLD,TLT,TIP

# Just sectors
poetry run python scripts/test_strategy_indicators_only.py --tickers XLF,XLE,XLK,XLV
```

### Different Time Periods

```powershell
# Test 2 years
poetry run python scripts/test_strategy_indicators_only.py --start-date 2023-01-01

# Specific range
poetry run python scripts/test_strategy_indicators_only.py `
    --start-date 2023-01-01 `
    --end-date 2024-12-31
```

### Different Risk Parameters

```powershell
# Conservative (tight stops)
poetry run python scripts/test_strategy_indicators_only.py --stop-loss 0.05 --take-profit 0.10

# Aggressive (wider stops)
poetry run python scripts/test_strategy_indicators_only.py --stop-loss 0.10 --take-profit 0.20

# Higher confidence threshold (trade less)
poetry run python scripts/test_strategy_indicators_only.py --min-confidence 0.60
```

## 💡 Why This Is Better for You

### ✅ Indicators-Only Strategy
- **Fast**: No ML training (5 mins vs 30 mins)
- **Simple**: Technical indicators you understand
- **Your Data**: Uses your 34 ETFs (SPY, QQQ, GLD, etc.)
- **Quick Iteration**: Test different parameters easily

### ❌ Full ML Strategy (Later)
- Requires 3+ years training data
- Takes 30-60 minutes
- More complex
- Good for optimization after you validate indicators work

## 📈 Expected Results

With your ETF data (1 year backtest):

**Market ETFs (SPY, QQQ, DIA)**:
- Higher returns (15-25%)
- More trades
- Good with breakout signals

**Safe Haven (GLD, TLT)**:
- Lower returns (5-15%)
- Good for cash preservation
- Good with support reclaim

**Sector ETFs (XLF, XLE, XLK)**:
- Mixed results (5-20%)
- Depends on sector rotation
- Good with momentum signals

**Volatility (VIX, UVXY)**:
- Higher volatility
- Harder to trade
- May have fewer signals

## 🔍 Next Steps After Test

### 1. Review Results
```powershell
# Did you make money?
# Was win rate > 50%?
# Was max drawdown < 20%?
```

### 2. Check Which ETFs Worked Best
```
TRADE ANALYSIS section shows:
- Which signals had best win rate?
- Which ETFs were most profitable?
```

### 3. Adjust if Needed
```powershell
# If win rate low, raise confidence threshold
--min-confidence 0.60

# If too few trades, lower threshold
--min-confidence 0.45

# If drawdown high, tighten stops
--stop-loss 0.06
```

### 4. Test Different Periods
```powershell
# Bull market (2023)
--start-date 2023-01-01 --end-date 2023-12-31

# Bear market (2022)
--start-date 2022-01-01 --end-date 2022-12-31

# Current year
--start-date 2024-01-01
```

## 🚀 Start Now!

```powershell
# Just run this:
.\tasks.ps1 test-indicators-only

# Wait 5 minutes, review results!
```

## 📚 If You Want More

After validating indicators work:

1. **Add ML predictions** (optional):
   ```powershell
   .\tasks.ps1 train-backtest
   ```

2. **Optimize parameters**:
   ```powershell
   .\tasks.ps1 optimize
   ```

3. **Get detailed reasoning**:
   ```powershell
   .\tasks.ps1 train-verbose
   ```

But start simple with indicators-only first! 🎯

## ❓ FAQ

**Q: Do I need ML models?**
A: No! Start with indicators-only test. ML is optional enhancement.

**Q: Will this work with my 34 ETFs?**
A: Yes! Script checks which tickers have data and uses only those.

**Q: How long does it take?**
A: ~5 minutes for 1 year backtest with all 34 ETFs.

**Q: Can I test just SPY?**
A: Yes! `--tickers SPY`

**Q: What if I get errors?**
A: Make sure you ran:
```powershell
.\tasks.ps1 fetch-historical    # Get price data
.\tasks.ps1 calc-indicators     # Calculate RSI, MACD, etc.
```

**Q: I want to see WHY trades were made**
A: Add `--verbose` flag to get detailed reasoning log

---

**Ready? Run this now:**
```powershell
.\tasks.ps1 test-indicators-only
```

Then come back and review the results! 🚀
