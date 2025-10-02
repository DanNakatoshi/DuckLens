# Quick Start: Trading & Backtesting

## 🚀 Fast Track (15 minutes)

### Step 1: Run Default Backtest

```powershell
# Train model + backtest with defaults
# - 3 years training data
# - 2 years backtest period
# - $100k starting capital
# - 5-day prediction horizon
.\tasks.ps1 train-backtest
```

**Expected Output**:
```
BACKTEST RESULTS
================================================================================

CAPITAL
--------------------------------------------------
Starting Capital              $100,000.00
Ending Capital                $142,500.00
Total Return                   $42,500.00
Total Return %                     42.50%

TRADE STATISTICS
--------------------------------------------------
Total Trades                          156
Winning Trades                         91
Losing Trades                          65
Win Rate                            58.3%

PROFIT/LOSS
--------------------------------------------------
Average Profit (Winners)           $812.45
Average Loss (Losers)            ($-356.20)
Profit Factor                         2.28

RISK METRICS
--------------------------------------------------
Max Drawdown                        18.2%
Sharpe Ratio                         1.85
Sortino Ratio                        2.41
```

### Step 2: Interpret Results

**Good Strategy** if you see:
- ✅ Total Return > 20% (for 2-year period)
- ✅ Win Rate > 50%
- ✅ Sharpe Ratio > 1.0
- ✅ Max Drawdown < 25%
- ✅ Profit Factor > 1.5

**Needs Improvement** if:
- ❌ Total Return < 10%
- ❌ Win Rate < 45%
- ❌ Sharpe Ratio < 0.5
- ❌ Max Drawdown > 35%

### Step 3 (Optional): Find Better Configuration

```powershell
# Test multiple configurations (takes 2-4 hours)
.\tasks.ps1 optimize

# Quick mode (takes 30 mins, tests fewer configs)
poetry run python scripts/optimize_strategy.py --quick
```

## 📊 Common Use Cases

### Use Case 1: Swing Trading (5-30 days)

**Goal**: Catch short-term price swings

```powershell
poetry run python scripts/train_and_backtest.py `
    --prediction-days 15 `
    --stop-loss 0.08 `
    --take-profit 0.15 `
    --max-holding-days 45 `
    --min-confidence 0.65
```

**Expected**: Higher win rate, more trades, moderate returns

### Use Case 2: Momentum Trading (15-60 days)

**Goal**: Ride longer trends

```powershell
poetry run python scripts/train_and_backtest.py `
    --prediction-days 30 `
    --stop-loss 0.10 `
    --take-profit 0.25 `
    --max-holding-days 90 `
    --min-confidence 0.60
```

**Expected**: Higher returns, lower win rate, fewer trades

### Use Case 3: Conservative (Minimize Drawdown)

**Goal**: Lower risk, steady returns

```powershell
poetry run python scripts/train_and_backtest.py `
    --prediction-days 5 `
    --stop-loss 0.05 `
    --take-profit 0.10 `
    --max-holding-days 30 `
    --min-confidence 0.70 `
    --position-size 0.05 `
    --max-positions 3
```

**Expected**: Low drawdown, high win rate, modest returns

### Use Case 4: Aggressive (Maximize Returns)

**Goal**: Higher risk, higher reward

```powershell
poetry run python scripts/train_and_backtest.py `
    --prediction-days 60 `
    --stop-loss 0.12 `
    --take-profit 0.40 `
    --max-holding-days 120 `
    --min-confidence 0.55 `
    --position-size 0.15 `
    --max-positions 8
```

**Expected**: High volatility, larger drawdowns, potential for high returns

## 🎯 Parameter Tuning Guide

### If Win Rate Too Low (< 45%)

**Try**:
```powershell
--min-confidence 0.70      # Be more selective
--stop-loss 0.10          # Give trades more room
--prediction-days 15       # Use mid-range predictions
```

### If Max Drawdown Too High (> 30%)

**Try**:
```powershell
--position-size 0.05      # Smaller positions
--max-positions 3          # Fewer concurrent trades
--stop-loss 0.06          # Tighter stop loss
```

### If Too Few Trades (< 50 per year)

**Try**:
```powershell
--min-confidence 0.55      # Lower threshold
--tickers SPY,QQQ,IWM,AAPL,MSFT,GOOGL,AMZN,NVDA,TSLA,AMD,META  # More tickers
```

### If Sharpe Ratio Too Low (< 0.5)

**Try**:
```powershell
--take-profit 0.20        # Higher profit targets
--trailing-stop enabled    # Let winners run
--max-holding-days 60     # Give trades time to develop
```

## 📈 Reading the Performance Report

### Section 1: Capital
```
Starting Capital              $100,000.00
Ending Capital                $142,500.00
Total Return                   $42,500.00   ← Profit in dollars
Total Return %                     42.50%   ← % gain (aim for 15%+ per year)
```

### Section 2: Trade Statistics
```
Total Trades                          156   ← More trades = more opportunities
Winning Trades                         91
Losing Trades                          65
Win Rate                            58.3%   ← Aim for 50-60%
```

### Section 3: Profit/Loss
```
Average Profit (Winners)           $812.45
Average Loss (Losers)            ($-356.20)
Profit Factor                         2.28   ← Aim for > 1.5
```
**Profit Factor = 2.28** means for every $1 lost, you make $2.28 in profits

### Section 4: Risk Metrics
```
Max Drawdown                        18.2%   ← Aim for < 20%
Max Drawdown Date              2024-03-15   ← When it occurred
Sharpe Ratio                         1.85   ← Aim for > 1.0
Sortino Ratio                        2.41   ← Aim for > 1.5
```

**Max Drawdown = 18.2%** means portfolio dropped 18.2% from peak before recovering

**Sharpe Ratio = 1.85** means good risk-adjusted returns

### Section 5: Entry Reason Breakdown
```
SUPPORT_RECLAIM                   42 trades | Win: 61.9% | P&L:   $18,245.00
BREAKOUT_HIGH                     38 trades | Win: 57.9% | P&L:   $14,820.00
ML_PREDICTION                     31 trades | Win: 54.8% | P&L:   $11,235.00
OVERSOLD_BOUNCE                   25 trades | Win: 60.0% | P&L:    $8,940.00
MOMENTUM                          20 trades | Win: 50.0% | P&L:    $6,180.00
```

**Insight**: Support reclaim has highest win rate → prioritize these signals

### Section 6: Exit Reason Breakdown
```
TAKE_PROFIT                       68 trades | Win: 100% | P&L:   $55,216.00  ← Good!
TRAILING_STOP                     31 trades | Win: 100% | P&L:   $15,842.00  ← Good!
STOP_LOSS                         40 trades | Win:   0% | P&L:  ($-14,240.00)← Expected
TIME_EXIT                         12 trades | Win:  41% | P&L:   ($-1,480.00)← Acceptable
OVERBOUGHT                         5 trades | Win:  60% | P&L:    $2,140.00  ← Good timing
```

## 🔧 Advanced: Optimization

### Run Full Optimization

Tests 192 different configurations:

```powershell
.\tasks.ps1 optimize
```

**Parameter Grid**:
- Prediction days: [5, 15, 30, 60]
- Stop loss: [5%, 8%, 10%]
- Take profit: [10%, 15%, 20%, 30%]
- Max holding: [30, 60, 90 days]
- Min confidence: [55%, 60%, 65%, 70%]

**Output**:
- `optimization_results.csv` with all results
- Top 10 by return, Sharpe ratio, win rate

### Analyze Results

```powershell
# View CSV in Excel or:
poetry run python -c "import pandas as pd; print(pd.read_csv('optimization_results.csv').nlargest(10, 'sharpe_ratio'))"
```

**Look for**:
- Configurations with Sharpe > 1.5 across multiple runs
- Consistent win rate > 55%
- Max drawdown < 20%

## 📝 Command Reference

### Training & Backtesting

```powershell
# Default (recommended first run)
.\tasks.ps1 train-backtest

# Custom dates
poetry run python scripts/train_and_backtest.py `
    --train-start 2019-01-01 --train-end 2022-12-31 `
    --test-start 2023-01-01 --test-end 2025-01-01

# Skip training (use existing model)
poetry run python scripts/train_and_backtest.py --skip-training

# Specific tickers only
poetry run python scripts/train_and_backtest.py --tickers SPY,QQQ,AAPL

# With custom capital
poetry run python scripts/train_and_backtest.py --capital 50000
```

### Optimization

```powershell
# Full optimization
.\tasks.ps1 optimize

# Quick mode (fewer configs)
poetry run python scripts/optimize_strategy.py --quick

# Custom output file
poetry run python scripts/optimize_strategy.py --output my_results.csv

# Specific tickers
poetry run python scripts/optimize_strategy.py --tickers SPY,QQQ,IWM
```

## 🎓 Next Steps

1. ✅ Run default backtest
2. ✅ Review results and understand metrics
3. ⏳ Try 2-3 different configurations for your trading style
4. ⏳ Run optimization to find best parameters
5. ⏳ Validate on different time periods (2020-2022, 2022-2024)
6. ⏳ Compare results across bull/bear markets
7. ⏳ Implement paper trading if satisfied with backtest

## ❓ FAQ

**Q: How long does training take?**
A: 5-15 minutes for CatBoost training, 10-30 minutes for backtest

**Q: Can I use this for day trading?**
A: Not recommended. System designed for 5-60 day holding periods

**Q: What if I don't have options data?**
A: System will work without it, using only price/indicator features

**Q: How do I know if results are realistic?**
A: Commission costs and slippage are included. Walk-forward test on multiple periods for validation

**Q: Can I add my own signals?**
A: Yes! Edit [src/models/trading_strategy.py](src/models/trading_strategy.py) `generate_buy_signal()` method

**Q: What return is realistic?**
A: 15-30% annual return with 15-20% max drawdown is strong performance

## 📚 Full Documentation

See [TRADING_SYSTEM_GUIDE.md](TRADING_SYSTEM_GUIDE.md) for complete details
