# DuckLens Trading Strategy: Data Sources & Math Explained

## Overview
Your CatBoost trading system uses **35+ features** from multiple data sources to predict market direction and generate buy/sell signals.

---

## 1. DATA SOURCES USED

### ✅ **Daily OHLC (Open, High, Low, Close) Data**
**Source:** `stock_prices` table from Polygon.io
**Usage:** Primary price data for all calculations

**Math:**
```
- Daily Returns = (Close - Previous Close) / Previous Close
- 5-Day Returns = (Close - Close[5 days ago]) / Close[5 days ago]
- 10-Day Returns = (Close - Close[10 days ago]) / Close[10 days ago]
- High-Low Range = (High - Low) / Close
```

---

### ✅ **Technical Indicators (Short, Medium, Long-term averages)**
**Source:** `technical_indicators` table
**Usage:** Trend identification, momentum, volatility

**Moving Averages:**
```
SMA_20  = Simple Moving Average (20 days) - Short-term trend
SMA_50  = Simple Moving Average (50 days) - Medium-term trend
SMA_200 = Simple Moving Average (200 days) - Long-term trend
EMA_12  = Exponential Moving Average (12 days)
EMA_26  = Exponential Moving Average (26 days)
```

**Trend Alignment Score:**
```
Trend Alignment = (SMA_20 > SMA_50) + (SMA_50 > SMA_200)
- Score 0 = Bearish (both false)
- Score 1 = Neutral (one true)
- Score 2 = Bullish (both true)
```

**Distance from Moving Averages:**
```
Distance from SMA_20  = (Close - SMA_20) / SMA_20
Distance from SMA_50  = (Close - SMA_50) / SMA_50
Distance from SMA_200 = (Close - SMA_200) / SMA_200

Example: If close=$100, SMA_20=$98
  Distance = (100-98)/98 = 2.04% above the 20-day average
```

**MACD (Moving Average Convergence Divergence):**
```
MACD Line = EMA_12 - EMA_26
Signal Line = 9-day EMA of MACD
Histogram = MACD - Signal

Interpretation:
- MACD > Signal = Bullish momentum
- MACD < Signal = Bearish momentum
```

**RSI (Relative Strength Index):**
```
RSI = 100 - (100 / (1 + RS))
RS = Average Gain / Average Loss (over 14 days)

Interpretation:
- RSI > 70 = Overbought (potential sell)
- RSI < 30 = Oversold (potential buy)
- RSI 30-70 = Neutral
```

**Bollinger Bands:**
```
BB_Middle = 20-day SMA
BB_Upper = Middle + (2 × 20-day Standard Deviation)
BB_Lower = Middle - (2 × 20-day Standard Deviation)

Interpretation:
- Price near upper band = Expensive/overbought
- Price near lower band = Cheap/oversold
- Band width = Volatility measure
```

**ATR (Average True Range):**
```
True Range = MAX(High-Low, |High-Previous Close|, |Low-Previous Close|)
ATR_14 = 14-day average of True Range

Usage: Used to set stop-loss levels based on volatility
Stop Loss = Entry Price - (2 × ATR_14)
```

**OBV (On-Balance Volume):**
```
If Close > Previous Close: OBV = Previous OBV + Volume
If Close < Previous Close: OBV = Previous OBV - Volume
If Close = Previous Close: OBV = Previous OBV

Interpretation:
- Rising OBV = Accumulation (bullish)
- Falling OBV = Distribution (bearish)
```

**ADX (Average Directional Index):**
```
ADX measures trend strength (0-100)
- ADX < 20 = Weak/no trend
- ADX 20-40 = Moderate trend
- ADX > 40 = Strong trend
```

---

### ✅ **Options Flow Data**
**Source:** `options_flow_indicators` table from Polygon.io
**Usage:** Detect institutional/smart money activity

**Put/Call Ratio:**
```
Put/Call Ratio = Total Put Volume / Total Call Volume

Interpretation:
- Ratio > 1.2 = Bearish (more puts = fear)
- Ratio < 0.8 = Bullish (more calls = greed)
- Ratio 0.8-1.2 = Neutral

5-day MA smooths out noise
Percentile shows if current ratio is extreme vs history
```

**Smart Money Index:**
```
Smart Money Index = (Call Volume at Ask - Put Volume at Ask) / Total Volume

Interpretation:
- Positive SMI = Bullish aggression (buying calls, selling puts)
- Negative SMI = Bearish aggression (buying puts, selling calls)
- > 0.1 = Strong bullish signal
- < -0.1 = Strong bearish signal
```

**Open Interest (OI) Momentum:**
```
OI Momentum = (Call OI Change + Put OI Change) / Previous Total OI

Interpretation:
- Positive = New positions opening (trend continuation)
- Negative = Positions closing (trend reversal)
```

**Unusual Activity Score:**
```
Unusual Activity = Volume / Average Volume (30-day)

Score > 2.0 = Unusual activity detected
- High call volume + low put/call ratio = Bullish whale activity
- High put volume + high put/call ratio = Bearish hedge fund activity
```

**IV Rank (Implied Volatility Rank):**
```
IV Rank = (Current IV - 52-week IV Low) / (52-week IV High - 52-week IV Low) × 100

Interpretation:
- IV Rank > 75 = Expensive options, expect volatility
- IV Rank < 25 = Cheap options, low volatility expected
```

**IV Skew:**
```
IV Skew = Put IV - Call IV

Interpretation:
- Positive skew = Puts more expensive (fear premium)
- Negative skew = Calls more expensive (speculation)
```

**Delta-Weighted Volume:**
```
Delta-Weighted Volume = Σ(Contract Delta × Volume)

Interpretation:
- Positive = Net bullish positioning
- Negative = Net bearish positioning
```

**Gamma Exposure (GEX):**
```
Gamma Exposure = Σ(Contract Gamma × Open Interest × Spot Price²)

Interpretation:
- High positive GEX = Market makers pin price (low volatility)
- Negative GEX = Market makers amplify moves (high volatility)
```

**Max Pain Distance:**
```
Max Pain = Strike price where total option value is minimum
Max Pain Distance = (Current Price - Max Pain) / Current Price

Interpretation:
- Price tends to gravitate toward max pain at expiration
- Large distance = potential mean reversion
```

**Flow Signal (Composite):**
```
Flow Signal = BULLISH, BEARISH, or NEUTRAL

Scoring Algorithm:
1. Put/Call Ratio: >1.2 = -2, <0.8 = +2
2. Smart Money Index: >0.1 = +1, <-0.1 = -1
3. OI Momentum: Positive = +1, Negative = -1
4. Unusual Activity: High = 2× weight

Final Score:
- Score ≥ 2 = BULLISH
- Score ≤ -2 = BEARISH
- Score -1 to +1 = NEUTRAL
```

---

### ✅ **Volume Analysis**
**Source:** Daily volume from `stock_prices`
**Usage:** Confirm price moves

**Math:**
```
Volume MA 20 = 20-day average volume
Volume Ratio = Today's Volume / Volume MA 20

Interpretation:
- Volume Ratio > 1.5 = High volume (strong move)
- Volume Ratio < 0.5 = Low volume (weak move)
- Price up + high volume = Strong bullish
- Price up + low volume = Weak rally (suspect)
```

---

### ✅ **Volatility Measures**
**Source:** Calculated from daily returns
**Usage:** Risk management, position sizing

**Math:**
```
10-Day Volatility = Standard Deviation of (Daily Returns over 10 days)

Example:
If 10-day volatility = 2.5%
  → High volatility = wider stops, smaller positions
If 10-day volatility = 0.5%
  → Low volatility = tighter stops, larger positions
```

---

### ✅ **Support & Resistance Levels**
**Source:** Historical price data
**Usage:** Entry/exit trigger points

**Math:**
```
Support Level = MIN(Low prices) over last 20 days
Resistance Level = MAX(High prices) over last 20 days

Breakout Detection:
- Current Price > Resistance × 1.01 = Breakout (BUY signal)
- Current Price < Support × 0.99 = Breakdown (SELL signal)

Support Reclaim:
- Was below support recently
- Now above support
- → BUY signal (bounce trade)
```

---

### ❌ **NOT CURRENTLY USED (But Mentioned in Comments)**

1. **Economic Calendar Data**
   - You have FRED data (unemployment, GDP, inflation)
   - Currently **NOT** being joined into CatBoost features
   - Would need to add LEFT JOIN to economic_calendar table

2. **Market Regime Detection (Bull/Bear Market)**
   - Not explicitly calculated
   - Implicitly detected via trend_alignment score
   - Could add: "Market Regime = BULL if SMA_50 > SMA_200, else BEAR"

3. **News Sentiment**
   - Not collected or used
   - Would require API like NewsAPI, AlphaVantage, or Finnhub

4. **Sector Rotation**
   - You have 11 sector ETFs (XLF, XLE, XLK, etc.)
   - Not currently comparing sector performance
   - Could add: "Strongest Sector = ETF with highest 20-day return"

5. **Correlation Analysis**
   - Not tracking SPY correlation for individual tickers
   - Could help identify hedges

6. **Short Interest Data**
   - Not collected
   - Requires separate data source (Fintel, S3 Partners)

---

## 2. CATBOOST STRATEGY & MATH

### Training Approach

**Prediction Target:**
```
Future Return = (Close[+5 days] - Close[today]) / Close[today]

Binary Classification:
- UP (1) if Future Return > 2%
- DOWN (0) if Future Return ≤ 2%

Regression:
- Predict exact expected return %
```

**Feature Engineering (35+ features):**
```
Base Features (13):
- volume, sma_20, sma_50, sma_200, ema_12, ema_26
- macd, macd_signal, macd_histogram, rsi_14
- bb_upper, bb_middle, bb_lower, atr_14, obv, adx

Options Features (13):
- put_call_ratio, put_call_ratio_ma5, put_call_ratio_percentile
- smart_money_index, oi_momentum, unusual_activity_score
- iv_rank, iv_skew, delta_weighted_volume, gamma_exposure
- max_pain_distance, flow_bullish (encoded), flow_bearish (encoded)

Derived Features (11):
- price_change_1d, price_change_5d, price_change_10d
- volume_ma_20, volume_ratio
- volatility_10d
- distance_sma_20, distance_sma_50, distance_sma_200
- trend_alignment (0-2 score)
- high_low_range
- days_above_sma_20, days_above_sma_50
```

**Model Training:**
```python
CatBoost Classification:
- Predicts: UP (1) or DOWN (0)
- Output: Confidence score 0-100%

CatBoost Regression:
- Predicts: Expected return %
- Output: -10% to +10% (or more)

Combined Prediction:
confidence = direction_model.predict_proba()[1]  # Probability of UP
expected_return = return_model.predict()

If confidence > 60% AND expected_return > 2%:
  → STRONG BUY
If confidence < 40%:
  → SKIP (cash on sidelines)
```

---

## 3. ENTRY SIGNALS (6 TYPES)

### 1. Support Reclaim
```
Conditions:
1. Recent low < support level (was below)
2. Current price > support level (now above)
3. RSI < 50 (not overbought)

Math:
Support = MIN(Low) over last 20 days
Was Below = Any close in last 5 days < Support × 0.99
Now Above = Current Price > Support × 1.01

Base Confidence: 60%
Bonus: +10% if ML model also predicts UP
```

### 2. Breakout High
```
Conditions:
1. Current price > resistance level
2. Volume > 1.5× average
3. Not overbought (RSI < 75)

Math:
Resistance = MAX(High) over last 20 days
Breakout = Current Price > Resistance × 1.01
Volume Confirm = Today's Volume > Volume MA × 1.5

Base Confidence: 65%
Bonus: +15% if ML confidence > 70%
```

### 3. Oversold Bounce
```
Conditions:
1. RSI < 30 (oversold)
2. MACD histogram turning positive (momentum shift)
3. Price near Bollinger lower band

Math:
Oversold = RSI < 30
MACD Crossover = MACD Histogram > 0 (after being negative)
Near BB Lower = (Close - BB_Lower) / BB_Lower < 2%

Base Confidence: 55%
Bonus: +20% if options flow is BULLISH
```

### 4. Momentum Entry
```
Conditions:
1. RSI 50-70 (strong but not overbought)
2. MACD > Signal (bullish crossover)
3. Options flow = BULLISH

Math:
Momentum Strength = (RSI - 50) / 20  # 0-1 scale
MACD Bullish = MACD - Signal > 0
Flow Bullish = Smart Money Index > 0.1 AND Put/Call < 1.0

Base Confidence: 70%
Bonus: +10% if trend_alignment = 2
```

### 5. ML Prediction Entry
```
Conditions:
1. CatBoost direction model > 70% confidence
2. CatBoost return model > 3% expected return
3. No conflicting technical signals

Math:
ML Confidence = direction_model.predict_proba()[1]
Expected Return = return_model.predict()

If ML Confidence > 70% AND Expected Return > 3%:
  Base Confidence = ML Confidence (70-100%)
```

### 6. Options Flow Entry
```
Conditions:
1. Flow signal = BULLISH
2. Unusual activity score > 2.0
3. IV Rank < 50 (options not too expensive)

Math:
Flow Score = Put/Call score + SMI score + OI score
Unusual = Volume / Avg Volume > 2.0
Cheap Options = IV Rank < 50

Base Confidence: 60%
Bonus: +15% if also has technical breakout
```

---

## 4. EXIT SIGNALS (7 TYPES)

### 1. Stop Loss
```
Math:
Stop Loss = Entry Price × (1 - stop_loss_pct)
Default: 8% below entry

If Current Price ≤ Stop Loss:
  → Exit immediately (limit losses)
```

### 2. Take Profit
```
Math:
Take Profit = Entry Price × (1 + take_profit_pct)
Default: 15% above entry

If Current Price ≥ Take Profit:
  → Exit immediately (lock in gains)
```

### 3. Trailing Stop
```
Math:
Trailing Stop = MAX(Highest Price Since Entry) × (1 - 0.05)
  = Follows price up, never goes down

Example:
Entry: $100
Price goes to $120 → Trailing stop = $114 (5% below $120)
Price drops to $115 → Still hold
Price drops to $113 → Exit (hit trailing stop)
```

### 4. Overbought Exit
```
Conditions:
1. RSI > 75
2. Price > Bollinger upper band
3. Negative divergence (price up, RSI down)

Math:
Overbought = RSI > 75
Above BB = Close > BB_Upper
Divergence = New Price High BUT RSI < Previous RSI High

→ Exit before reversal
```

### 5. Momentum Loss
```
Conditions:
1. MACD crosses below signal (bearish crossover)
2. Volume declining
3. Trend alignment drops (SMA_20 crosses below SMA_50)

Math:
MACD Bearish = MACD - Signal < 0 (was positive)
Volume Drop = Volume < Volume MA × 0.75
Trend Break = SMA_20 < SMA_50 (was above)

→ Exit when trend weakens
```

### 6. Options Flow Reversal
```
Conditions:
1. Flow signal flips from BULLISH → BEARISH
2. Put/Call ratio spikes > 1.5
3. Smart Money Index turns negative

Math:
Flow Flip = Was BULLISH, now BEARISH
PC Spike = Put/Call Ratio > 1.5 (extreme fear)
SMI Bearish = Smart Money Index < -0.1

→ Exit when institutions sell
```

### 7. Max Holding Period
```
Math:
Days Held = Current Date - Entry Date

If Days Held > max_holding_days (default 60):
  → Exit (prevent dead capital)

Even if not profitable, free up capital for better opportunities
```

---

## 5. POSITION SIZING & RISK MANAGEMENT

**Capital Allocation:**
```
Position Size = Total Capital × position_size_pct / Current Price
Default: 10% of capital per position
Max Positions: 5 concurrent trades

Example:
$100,000 capital → $10,000 per trade
SPY at $500 → Buy 20 shares
```

**Risk Per Trade:**
```
Risk Amount = Position Size × stop_loss_pct
Max Risk: 0.8% of capital per trade (8% stop × 10% position = 0.8%)

Example:
$10,000 position × 8% stop = $800 max loss
$800 / $100,000 = 0.8% of total capital at risk
```

**Cash on Sidelines:**
```
If ML Confidence < min_confidence_threshold:
  → Skip trade, keep cash

Example:
If min_confidence = 60%:
  Signal has 55% confidence → SKIP (not confident enough)
  Signal has 65% confidence → TAKE (confident enough)

Rejection Rate tracks % of signals skipped
```

---

## 6. PERFORMANCE METRICS

**Win Rate:**
```
Win Rate = Winning Trades / Total Trades × 100%
Target: > 55%
```

**Profit Factor:**
```
Profit Factor = Total Profit from Winners / Total Loss from Losers
Target: > 1.5 (make $1.50 for every $1 lost)
```

**Sharpe Ratio:**
```
Sharpe = (Average Return - Risk Free Rate) / Standard Deviation of Returns
Target: > 1.0 (good risk-adjusted returns)
```

**Sortino Ratio:**
```
Sortino = (Average Return - Risk Free Rate) / Downside Deviation
Similar to Sharpe but only penalizes downside volatility
Target: > 1.5
```

**Max Drawdown:**
```
Max Drawdown = Largest peak-to-trough decline in equity
Max Drawdown = (Peak Value - Trough Value) / Peak Value

Example:
Peak: $120,000
Trough: $100,000
Max Drawdown = ($120k - $100k) / $120k = 16.67%

Target: < 20%
```

---

## 7. WHAT'S MISSING (Potential Improvements)

1. **Economic Data Integration**
   - GDP, unemployment, CPI, Fed rate changes
   - JOIN economic_calendar to features

2. **Market Regime Detection**
   - Explicit bull/bear market classifier
   - Add: market_regime = "BULL" if SMA_50 > SMA_200 else "BEAR"

3. **News Sentiment**
   - Positive/negative news scoring
   - Requires NewsAPI integration

4. **Sector Rotation**
   - Track which sectors are outperforming
   - Overweight strongest sectors

5. **Correlation Analysis**
   - SPY correlation for each ticker
   - Hedge with negatively correlated assets

6. **Short Interest**
   - Days to cover, short interest %
   - Identify short squeeze candidates

7. **Earnings Calendar**
   - Avoid holding through earnings
   - Or trade earnings volatility explicitly

8. **Multi-Timeframe Analysis**
   - Currently only daily data
   - Could add weekly/monthly trends

---

## Summary

**Your strategy currently uses:**
✅ Daily OHLC data
✅ Short/medium/long-term moving averages
✅ Technical indicators (MACD, RSI, Bollinger Bands, ATR)
✅ Volume analysis
✅ Options flow (put/call ratio, smart money, unusual activity)
✅ Volatility measures
✅ Support/resistance levels
✅ 35+ engineered features
✅ CatBoost ML for prediction

**Your strategy does NOT use:**
❌ Market regime (bull/bear) detection
❌ Economic calendar data
❌ News sentiment
❌ Sector rotation signals
❌ Short interest data

**Current indicator-only test result: -17.33% loss**
→ Shows technical indicators alone aren't enough
→ Need ML confidence filtering to improve win rate
→ Next step: Run full CatBoost training

---

**Want to add any of the missing features? Let me know!**
