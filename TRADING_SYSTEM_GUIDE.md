# DuckLens Trading System Guide

## Overview

Complete backtesting and ML-powered trading system with:
- **CatBoost ML Models** for market direction prediction
- **Multiple Entry Signals**: Support reclaim, breakouts, momentum, ML predictions
- **Risk Management**: Stop loss, take profit, trailing stops
- **Performance Metrics**: Win rate, Sharpe ratio, max drawdown, profit factor
- **Hyperparameter Optimization**: Find best configuration automatically

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA COLLECTION                               │
├─────────────────────────────────────────────────────────────────────┤
│ ✓ Historical Prices (5+ years)                                       │
│ ✓ Technical Indicators (SMA, EMA, MACD, RSI, Bollinger Bands, etc.) │
│ ✓ Options Flow (P/C ratio, Smart Money, Unusual Activity)           │
│ ✓ Economic Calendar (CPI, FOMC, NFP, GDP releases)                  │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────┐
│                        FEATURE ENGINEERING                            │
├─────────────────────────────────────────────────────────────────────┤
│ • Price momentum (1d, 5d, 10d changes)                              │
│ • Volume ratios and unusual activity                                 │
│ • Distance from moving averages                                      │
│ • Trend alignment (SMA20 > SMA50 > SMA200)                          │
│ • Options flow signals (bullish/bearish)                             │
│ • Volatility measures (10-day std dev)                               │
│ └─→ 35+ features per data point                                     │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────┐
│                        CATBOOST TRAINING                              │
├─────────────────────────────────────────────────────────────────────┤
│ 1. Direction Model (Binary Classification)                          │
│    • Predicts UP (profit > 2%) or DOWN                              │
│    • Outputs confidence score (0-1)                                  │
│    • Metrics: Accuracy, Precision, Recall, F1                       │
│                                                                       │
│ 2. Return Model (Regression)                                         │
│    • Predicts expected return % over N days                          │
│    • Metrics: RMSE, MAE, R²                                          │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────┐
│                        TRADING STRATEGY                               │
├─────────────────────────────────────────────────────────────────────┤
│ BUY SIGNALS:                                                          │
│ ✓ Support Reclaim: Price dips below support, reclaims above         │
│ ✓ Breakout: Breaks above 30-day high                                 │
│ ✓ Oversold Bounce: RSI < 30 + MACD crossover bullish               │
│ ✓ ML Prediction: CatBoost confidence > 70%                          │
│ ✓ Momentum: Options flow bullish + positive MACD + RSI > 50        │
│                                                                       │
│ SELL SIGNALS:                                                         │
│ ✓ Stop Loss: Price hits 8% below entry (configurable)               │
│ ✓ Take Profit: Price hits 15% above entry (configurable)            │
│ ✓ Trailing Stop: 5% below highest price since entry                 │
│ ✓ Resistance: Price hits resistance level                            │
│ ✓ Time Exit: Held for max days (60 default)                         │
│ ✓ Overbought: RSI > 75 + negative MACD                              │
│ ✓ ML Sell Signal: CatBoost predicts down with high confidence       │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────┐
│                          BACKTESTING                                  │
├─────────────────────────────────────────────────────────────────────┤
│ • Realistic position sizing (10% capital per position)               │
│ • Commission costs (0.1% per trade)                                  │
│ • Max concurrent positions (5 default)                               │
│ • Day-by-day simulation with actual historical prices                │
│ • Position tracking with trailing stops                              │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      PERFORMANCE ANALYSIS                             │
├─────────────────────────────────────────────────────────────────────┤
│ METRICS:                                                              │
│ • Total Return % and $                                                │
│ • Win Rate (winning trades / total trades)                           │
│ • Profit Factor (gross profit / gross loss)                          │
│ • Sharpe Ratio (risk-adjusted return)                                │
│ • Sortino Ratio (downside risk-adjusted)                             │
│ • Max Drawdown % and date                                             │
│ • Average holding period                                              │
│                                                                       │
│ BREAKDOWNS:                                                           │
│ • Performance by entry reason                                         │
│ • Performance by exit reason                                          │
│ • Best and worst trades                                               │
│ • Equity curve over time                                              │
└─────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Data Requirements

Ensure you have collected all necessary data:

```powershell
# Stock prices (5 years)
.\tasks.ps1 fetch-historical

# Technical indicators
.\tasks.ps1 calc-indicators

# Options flow (2 years)
.\tasks.ps1 fetch-options-flow
.\tasks.ps1 calc-options-metrics

# Economic calendar
.\tasks.ps1 fetch-economic
.\tasks.ps1 build-calendar
```

### 2. Train Model & Run Backtest

**Default Configuration** (3 years training, 2 years backtest):

```powershell
.\tasks.ps1 train-backtest
```

**Custom Configuration**:

```powershell
poetry run python scripts/train_and_backtest.py `
    --train-start 2019-01-01 `
    --train-end 2022-12-31 `
    --test-start 2023-01-01 `
    --test-end 2025-01-01 `
    --prediction-days 15 `
    --stop-loss 0.10 `
    --take-profit 0.20 `
    --max-holding-days 45 `
    --capital 50000
```

### 3. Optimize Strategy

Find the best hyperparameter configuration:

```powershell
# Full optimization (several hours, 192 configurations)
.\tasks.ps1 optimize

# Quick mode (faster, 32 configurations)
poetry run python scripts/optimize_strategy.py --quick

# Custom date range
poetry run python scripts/optimize_strategy.py `
    --start-date 2023-01-01 `
    --end-date 2025-01-01 `
    --output my_results.csv
```

## Configuration Parameters

### Prediction Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `prediction_days` | 5 | Days ahead to predict (5, 15, 30, 60) |
| `profit_threshold` | 0.02 | Min profit % to label as UP (2%) |

**Guidance**:
- **5 days**: Short-term swing trading
- **15 days**: Mid-range momentum trading
- **30 days**: Monthly trend following
- **60 days**: Longer-term position trading

### Risk Management Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `stop_loss_pct` | 0.08 | Stop loss % below entry (8%) |
| `take_profit_pct` | 0.15 | Take profit % above entry (15%) |
| `max_holding_days` | 60 | Maximum holding period |
| `trailing_stop_pct` | 0.05 | Trailing stop % below high (5%) |

**Guidance**:
- **Tight stop (5%)**: Lower drawdown, more stop-outs
- **Standard stop (8%)**: Balanced risk/reward
- **Wide stop (10%)**: Fewer stop-outs, higher drawdown risk

### Portfolio Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `starting_capital` | $100,000 | Starting cash |
| `position_size_pct` | 0.10 | % of capital per position (10%) |
| `max_positions` | 5 | Max concurrent positions |
| `commission_pct` | 0.001 | Commission per trade (0.1%) |
| `min_ml_confidence` | 0.60 | Min ML confidence to trade (60%) |

**Guidance**:
- **Aggressive (15% position size, 10 max positions)**: Higher volatility
- **Moderate (10% position size, 5 max positions)**: Balanced
- **Conservative (5% position size, 3 max positions)**: Lower volatility

## Entry Signals Explained

### 1. Support Reclaim
**What**: Price dips below support level (20-day low), then reclaims above it

**Logic**: Buyers stepping in at support = bullish reversal

**Example**: SPY drops to $500 (support), bounces to $505

### 2. Breakout Above High
**What**: Price breaks above 30-day high by at least 0.5%

**Logic**: New highs = momentum continuation

**Example**: SPY breaks above $520 (previous high was $518)

### 3. Oversold Bounce
**What**: RSI drops below 30 (oversold) + MACD turns positive

**Logic**: Oversold conditions + momentum reversal = bounce

**Example**: After selloff, RSI = 28, MACD crosses above signal line

### 4. ML Prediction
**What**: CatBoost model predicts UP with confidence > 70%

**Logic**: ML model sees favorable pattern in features

**Example**: Model predicts 3% return with 75% confidence

### 5. Momentum with Bullish Options Flow
**What**: Options flow shows bullish signal + MACD positive + RSI > 50

**Logic**: Multiple confirmations of bullish momentum

**Example**: P/C ratio low, smart money buying calls, MACD bullish

## Exit Signals Explained

### 1. Stop Loss
**What**: Price drops 8% below entry (or custom %)

**Logic**: Cut losses early to preserve capital

**Example**: Bought at $100, stop triggered at $92

### 2. Take Profit
**What**: Price rises 15% above entry (or custom %)

**Logic**: Lock in gains at target

**Example**: Bought at $100, sold at $115

### 3. Trailing Stop
**What**: Price drops 5% below highest price since entry

**Logic**: Let winners run, exit on reversal

**Example**: Bought at $100, peaked at $120, sold at $114 (5% below $120)

### 4. Resistance Hit
**What**: Price approaches resistance level (20-day high)

**Logic**: Resistance often causes reversal

**Example**: Price reaches $540 (resistance at $542)

### 5. Time Exit
**What**: Held for maximum days (60 default)

**Logic**: Avoid dead positions, redeploy capital

**Example**: Bought 65 days ago, still holding, force exit

### 6. Overbought
**What**: RSI > 75 + MACD turns negative

**Logic**: Overbought + momentum loss = reversal risk

**Example**: RSI = 77, MACD crosses below signal line

## Performance Metrics Explained

### Win Rate
**Formula**: Winning trades / Total trades

**Good Target**: 50-60%

**Interpretation**:
- > 60%: Excellent signal selection
- 50-60%: Good with proper risk/reward
- < 50%: Need better signals or risk management

### Profit Factor
**Formula**: Gross profit / Gross loss

**Good Target**: > 1.5

**Interpretation**:
- > 2.0: Excellent
- 1.5-2.0: Good
- 1.0-1.5: Marginal
- < 1.0: Losing strategy

### Sharpe Ratio
**Formula**: (Return - Risk-free rate) / Standard deviation of returns

**Good Target**: > 1.0

**Interpretation**:
- > 2.0: Excellent risk-adjusted returns
- 1.0-2.0: Good
- 0-1.0: Marginal
- < 0: Negative risk-adjusted returns

### Sortino Ratio
**Formula**: (Return - Risk-free rate) / Downside deviation

**Good Target**: > 1.5

**Interpretation**: Similar to Sharpe but only penalizes downside volatility (better for traders who don't mind upside volatility)

### Max Drawdown
**Formula**: (Peak - Trough) / Peak

**Good Target**: < 20%

**Interpretation**:
- < 15%: Low risk
- 15-25%: Moderate risk
- 25-40%: High risk
- > 40%: Very high risk

## Example Workflow

### Scenario: Mid-Range Swing Trading (5-30 days)

**Goal**: Find optimal configuration for swing trading with moderate risk

**Step 1**: Run optimization on 2-year backtest

```powershell
poetry run python scripts/optimize_strategy.py `
    --start-date 2023-01-01 `
    --end-date 2025-01-01 `
    --capital 100000 `
    --output swing_optimization.csv
```

**Step 2**: Review results sorted by Sharpe ratio

```
TOP 10 CONFIGURATIONS BY SHARPE RATIO
============================================================
Rank  Pred    SL    TP  Hold  Conf  Return   Win%  Sharpe  MaxDD
   1    15    8%   15%    45   65%   42.5%  58.3%   1.85   18.2%
   2    15   10%   20%    60   60%   38.2%  54.1%   1.72   16.5%
   3     5    8%   15%    30   70%   35.8%  61.2%   1.68   21.3%
```

**Step 3**: Test top configuration with different date ranges

```powershell
# Test on different 2-year period
poetry run python scripts/train_and_backtest.py `
    --train-start 2018-01-01 `
    --train-end 2021-12-31 `
    --test-start 2022-01-01 `
    --test-end 2024-01-01 `
    --prediction-days 15 `
    --stop-loss 0.08 `
    --take-profit 0.15 `
    --max-holding-days 45 `
    --min-confidence 0.65
```

**Step 4**: Analyze performance report

Look for:
- ✓ Win rate > 55%
- ✓ Sharpe ratio > 1.5
- ✓ Max drawdown < 20%
- ✓ Profit factor > 1.8
- ✓ Consistent performance across entry types

**Step 5**: If metrics look good, deploy to paper trading

## Common Patterns

### High Win Rate Strategy
**Configuration**:
- Prediction days: 5-15 (shorter term)
- Stop loss: 5% (tight)
- Take profit: 10% (modest)
- Min confidence: 70% (selective)

**Trade-off**: Lower total return, more trades, lower drawdown

### High Return Strategy
**Configuration**:
- Prediction days: 30-60 (longer term)
- Stop loss: 10% (wider)
- Take profit: 30% (ambitious)
- Min confidence: 55% (aggressive)

**Trade-off**: Higher volatility, larger drawdowns, fewer trades

### Balanced Strategy
**Configuration**:
- Prediction days: 15
- Stop loss: 8%
- Take profit: 15%
- Min confidence: 60%

**Trade-off**: Moderate across all metrics

## Troubleshooting

### Low Win Rate (< 45%)

**Possible Causes**:
- ML model overfit on training data
- Market regime changed (trained on bull market, tested on bear)
- Stop loss too tight (getting stopped out prematurely)

**Solutions**:
- Increase training data duration
- Add more diverse market conditions to training
- Widen stop loss or use trailing stops
- Increase min ML confidence threshold

### High Drawdown (> 30%)

**Possible Causes**:
- Position size too large
- Too many concurrent positions
- Stop loss too wide

**Solutions**:
- Reduce position_size_pct (10% → 5%)
- Reduce max_positions (5 → 3)
- Tighten stop loss (10% → 8%)
- Add more conservative entry filters

### Low Sharpe Ratio (< 0.5)

**Possible Causes**:
- High volatility relative to returns
- Inconsistent performance
- Too many whipsaw trades

**Solutions**:
- Increase min ML confidence (filter weak signals)
- Add more indicators to entry logic
- Increase take profit target
- Use longer prediction days for smoother returns

### Too Few Trades (< 20 per year)

**Possible Causes**:
- Min confidence too high
- Too selective entry criteria
- Not enough tickers in universe

**Solutions**:
- Lower min ML confidence (70% → 60%)
- Add more entry signal types
- Expand ticker universe (10 → 30 tickers)

## Advanced Topics

### Walk-Forward Optimization

Instead of single train/test split, use rolling windows:

```python
# Example: Train on 3 years, test on 1 year, roll forward
periods = [
    ("2018-01-01", "2020-12-31", "2021-01-01", "2021-12-31"),
    ("2019-01-01", "2021-12-31", "2022-01-01", "2022-12-31"),
    ("2020-01-01", "2022-12-31", "2023-01-01", "2023-12-31"),
]

for train_start, train_end, test_start, test_end in periods:
    # Train and backtest for each period
    # Average results for robustness
```

### Monte Carlo Simulation

Test strategy robustness by randomizing trade order:

```python
# Shuffle trades 1000 times
# Calculate distribution of returns, Sharpe, drawdown
# Confidence interval: "95% chance returns between X% and Y%"
```

### Market Regime Detection

Adjust strategy based on market conditions:

```python
# Bull market: More aggressive (wider stops, higher leverage)
# Bear market: More defensive (tight stops, higher cash)
# Sideways: Range trading (support/resistance focus)
```

## Files Reference

### Core Modules

- **[src/models/trading_strategy.py](src/models/trading_strategy.py)**: Entry/exit signal logic
- **[src/ml/catboost_model.py](src/ml/catboost_model.py)**: ML model training and prediction
- **[src/backtest/engine.py](src/backtest/engine.py)**: Backtesting simulation engine

### Scripts

- **[scripts/train_and_backtest.py](scripts/train_and_backtest.py)**: Train ML model and run backtest
- **[scripts/optimize_strategy.py](scripts/optimize_strategy.py)**: Hyperparameter optimization

### Commands

```powershell
# Train and backtest
.\tasks.ps1 train-backtest

# Optimize hyperparameters
.\tasks.ps1 optimize
```

## Next Steps

1. ✅ Collect all data (prices, indicators, options flow)
2. ✅ Run quick backtest with defaults
3. ⏳ Run full optimization to find best configuration
4. ⏳ Validate on different time periods
5. ⏳ Implement paper trading to verify live performance
6. ⏳ Deploy to live trading with proper risk management

---

**Questions? Issues?**

Open an issue at [github.com/anthropics/ducklens/issues](https://github.com/anthropics/ducklens/issues)
