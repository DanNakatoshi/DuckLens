# Backtest: $30K to $1M Path

## Overview

This backtest simulates realistic trading from $30,000 to $1,000,000 using the Enhanced Trend Detector with proper risk management, leverage, and NO FUTURE DATA LEAKAGE.

## Key Features

### 1. **No Future Data Leakage (Walk-Forward Simulation)**
- Processes data day-by-day in chronological order
- Detectors initialized per-date using only historical data
- Signals generated using data available up to that specific date
- No peeking ahead or using future information

### 2. **Realistic Transaction Costs**
- **Commission**: 0.1% per trade (both entry and exit)
- **Slippage**: 0.05% (market impact)
- Costs deducted from both buying and selling

### 3. **Dynamic Leverage Based on Confidence & Market Regime**

| Confidence | Market Regime | Leverage | Description |
|-----------|---------------|----------|-------------|
| ≥85% | BULLISH | **2.0x** | Aggressive - high confidence opportunities |
| 75-85% | BULLISH | **1.5x** | Moderate leverage |
| ≥75% | NEUTRAL | **1.0x** | No leverage - standard position |
| Any | BEARISH | **0.5x** | Defensive - reduce exposure |

### 4. **Position Sizing (Kelly Criterion)**

Position size = (Portfolio Value × Leverage × Kelly%) / Price

- **Kelly% = confidence - 0.5** (simplified)
- **Maximum position**: 15% of portfolio value
- **Minimum position**: 10% of portfolio value

### 5. **Stop-Loss & Take-Profit Rules**

#### Stop-Loss (confidence-based):
- **High confidence (≥85%)**: 8% stop-loss (wider stop)
- **Medium confidence (75-85%)**: 6% stop-loss
- **Lower confidence**: 4% stop-loss (tighter protection)

#### Take-Profit (confidence-based):
- **High confidence (≥85%)**: 25% target
- **Medium confidence (75-85%)**: 15% target
- **Lower confidence**: 10% target

### 6. **Position Swapping Logic**

Swap positions when:
- **New opportunity has >10% higher confidence** than weakest position
- **Current position is NOT in profit** (>5%)
- **Portfolio is at max positions** (12 positions)

**Why swap?**
- Constantly upgrade to best opportunities
- Don't swap winning positions
- Cut underperformers for better setups

### 7. **Exit Triggers**

Positions are closed when:
1. **Stop-loss hit** (price drops below stop)
2. **Take-profit hit** (price reaches target)
3. **Signal exit** (trend detector changes to SELL/DONT_TRADE)
4. **Position swap** (better opportunity identified)

## Backtest Parameters

```python
Initial Capital:  $30,000
Target Capital:   $1,000,000
Max Positions:    12
Commission:       0.1%
Slippage:         0.05%
Date Range:       2020-01-01 to 2024-12-31
Tickers:          Top 30 from TIER_2_STOCKS
```

## Performance Metrics

The backtest tracks:

### Returns
- Total return %
- Time to reach $1M target
- Equity curve (daily portfolio value)

### Trading Stats
- Total number of trades
- Win rate (% profitable trades)
- Average win $ and %
- Average loss $ and %
- Profit factor (total wins / total losses)

### Risk Metrics
- Maximum drawdown
- Sharpe ratio (if implemented)
- Average leverage used

## How to Run

```bash
# Run the backtest
python scripts/backtest_to_1m.py

# View results in terminal
# Results are also saved to backtest_output.log
```

## Example Output

```
================================================================================
BACKTEST: PATH TO $1 MILLION
================================================================================
Start Date: 2020-01-01
End Date: 2024-12-31
Initial Capital: $30,000.00
Target Capital: $1,000,000.00
Max Positions: 12
================================================================================

[2020-01-02] OPENED GOOGL @ $135.20 (Conf: 85%) (2.0x)
[2020-01-02] OPENED TSLA @ $86.05 (Conf: 80%) (1.5x)
[2020-01-02] Portfolio: $29,850.00 | Positions: 2 | Cash: $5,120.00

[2020-02-15] CLOSED TSLA @ $160.50 - take_profit (+86.5%)
[2020-02-15] SWAP OUT BABA @ $210.00
[2020-02-15] SWAP IN NVDA @ $305.00 (Conf: 88%) (2.0x)

...

================================================================================
🎯 TARGET REACHED: $1,012,450.00 on 2023-05-15
================================================================================

BACKTEST RESULTS
================================================================================
Initial Capital:     $30,000.00
Final Value:         $1,012,450.00
Total Return:        +3,274.83%
Target ($1M):        ✓ REACHED
Time to $1M:         1,230 days (3.4 years)

Total Trades:        245
Winning Trades:      165 (67.3%)
Losing Trades:       80
Average Win:         $8,450.00
Average Loss:        -$2,120.00
Profit Factor:       3.98
================================================================================
```

## Safety Features

### No Look-Ahead Bias
- All signals generated using historical data only
- Stop-loss/take-profit based on entry conditions, not future knowledge
- Market regime detected using past data

### Realistic Constraints
- Transaction costs included
- Slippage modeled
- Cash constraints enforced
- Position limits respected

### Risk Management
- Stop-losses on every position
- Position sizing based on confidence
- Leverage reduced in unfavorable conditions
- Maximum position size limits

## Strategy Rules

### Entry Conditions
1. Signal must be BUY with ≥75% confidence
2. Available cash to open position
3. Room for position (< 12 positions)
4. Market regime considered for leverage

### Exit Conditions
1. Stop-loss hit (forced exit)
2. Take-profit hit (forced exit)
3. Signal changes to SELL/DONT_TRADE
4. Better opportunity available (swap)

### Position Management
- Monitor all positions daily
- Recalculate signals daily
- Check for better opportunities
- Apply stop-loss and take-profit rules

## Interpreting Results

### Time to $1M
- **< 3 years**: Aggressive strategy working well
- **3-5 years**: Realistic timeframe with moderate risk
- **> 5 years**: Conservative approach or challenging market
- **Target not reached**: Strategy needs refinement

### Win Rate
- **> 60%**: Good trend-following system
- **50-60%**: Acceptable if profit factor > 2
- **< 50%**: Need better signals or risk management

### Profit Factor
- **> 2.0**: Excellent risk/reward
- **1.5-2.0**: Good profitability
- **< 1.5**: Marginal profitability

## Next Steps

After running the backtest:

1. **Analyze trades** - Which trades were most profitable?
2. **Review exits** - Were stops too tight/wide?
3. **Adjust parameters** - Test different leverage levels
4. **Optimize** - Find best confidence thresholds
5. **Validate** - Run on different time periods

## Disclaimers

- Past performance does not guarantee future results
- Backtest includes realistic costs but cannot model all market conditions
- Real-world slippage and commissions may vary
- Market conditions change over time
- Use results as guidance, not guarantee
