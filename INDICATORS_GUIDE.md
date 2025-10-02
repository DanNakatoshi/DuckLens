# Technical Indicators Guide

Calculate technical indicators from your stored price data - **no API calls needed**!

## Quick Start

### Calculate All Indicators

Calculate and store indicators for all your tickers:

```powershell
.\tasks.ps1 calc-indicators
```

This calculates:
- **Moving Averages**: SMA (20, 50, 200), EMA (12, 26)
- **MACD**: Line, Signal, Histogram
- **RSI**: 14-period Relative Strength Index
- **Bollinger Bands**: Upper, Middle, Lower
- **ATR**: 14-period Average True Range
- **Stochastic**: %K and %D
- **OBV**: On-Balance Volume

### View Indicators for a Ticker

See latest indicators with trading signals:

```powershell
.\tasks.ps1 show-indicators
```

### Run Tests

```powershell
.\tasks.ps1 test-indicators
```

## Python Usage

### Calculate Individual Indicators

```python
from src.analysis.indicators import TechnicalIndicators

with TechnicalIndicators() as calc:
    # Simple Moving Average
    sma_50 = calc.calculate_sma("SPY", window=50)

    # Exponential Moving Average
    ema_20 = calc.calculate_ema("SPY", window=20)

    # MACD
    macd = calc.calculate_macd("SPY", short_window=12, long_window=26, signal_window=9)

    # RSI
    rsi = calc.calculate_rsi("SPY", window=14)

    # Bollinger Bands
    bb = calc.calculate_bollinger_bands("SPY", window=20, num_std=2.0)

    # ATR
    atr = calc.calculate_atr("SPY", window=14)

    # Stochastic Oscillator
    stoch = calc.calculate_stochastic("SPY", k_window=14, d_window=3)

    # On-Balance Volume
    obv = calc.calculate_obv("SPY")
```

### Calculate All Indicators at Once

```python
from src.analysis.indicators import TechnicalIndicators

with TechnicalIndicators() as calc:
    # Returns DataFrame with all indicators
    indicators = calc.calculate_all_indicators("SPY")

    print(indicators.tail())
    print(f"\nLatest RSI: {indicators['rsi_14'].iloc[-1]:.2f}")
```

### With Date Filtering

```python
from datetime import datetime, timedelta

end_date = datetime.now()
start_date = end_date - timedelta(days=90)  # Last 90 days

with TechnicalIndicators() as calc:
    sma = calc.calculate_sma("SPY", window=20, start_date=start_date, end_date=end_date)
```

## Available Indicators

### 1. Simple Moving Average (SMA)

```python
sma = calc.calculate_sma(
    symbol="SPY",
    window=50,  # Number of periods
    price_column="close"  # or "open", "high", "low"
)
```

**Use Cases:**
- Identify trend direction
- Support/resistance levels
- Crossover signals (SMA50 crosses SMA200)

### 2. Exponential Moving Average (EMA)

```python
ema = calc.calculate_ema(
    symbol="SPY",
    window=20,
    price_column="close"
)
```

**Use Cases:**
- React faster to price changes than SMA
- EMA crossover strategies
- Dynamic support/resistance

### 3. MACD (Moving Average Convergence Divergence)

```python
macd = calc.calculate_macd(
    symbol="SPY",
    short_window=12,
    long_window=26,
    signal_window=9
)
# Returns: macd, signal, histogram
```

**Use Cases:**
- Trend strength and direction
- Signal line crossovers (buy/sell signals)
- Divergence detection

**Signals:**
- MACD > Signal = Bullish
- MACD < Signal = Bearish
- Histogram increasing = Momentum growing

### 4. RSI (Relative Strength Index)

```python
rsi = calc.calculate_rsi(
    symbol="SPY",
    window=14
)
# Returns: 0-100 scale
```

**Use Cases:**
- Overbought/oversold conditions
- Divergence analysis
- Trend strength

**Signals:**
- RSI > 70 = Overbought (potential sell)
- RSI < 30 = Oversold (potential buy)
- RSI 50 = Neutral

### 5. Bollinger Bands

```python
bb = calc.calculate_bollinger_bands(
    symbol="SPY",
    window=20,
    num_std=2.0  # Standard deviations
)
# Returns: upper, middle, lower
```

**Use Cases:**
- Volatility analysis
- Price reversal signals
- Breakout detection

**Signals:**
- Price touching upper band = Overbought
- Price touching lower band = Oversold
- Squeeze (narrow bands) = Low volatility, potential breakout

### 6. ATR (Average True Range)

```python
atr = calc.calculate_atr(
    symbol="SPY",
    window=14
)
```

**Use Cases:**
- Volatility measurement
- Stop-loss placement
- Position sizing

### 7. Stochastic Oscillator

```python
stoch = calc.calculate_stochastic(
    symbol="SPY",
    k_window=14,
    d_window=3
)
# Returns: k, d
```

**Use Cases:**
- Momentum analysis
- Overbought/oversold detection
- Divergence signals

**Signals:**
- %K > 80 = Overbought
- %K < 20 = Oversold
- %K crosses %D = Trading signal

### 8. OBV (On-Balance Volume)

```python
obv = calc.calculate_obv(symbol="SPY")
```

**Use Cases:**
- Confirm price trends with volume
- Divergence detection
- Accumulation/distribution

## Trading Signal Examples

### Trend Identification

```python
indicators = calc.calculate_all_indicators("SPY")
latest = indicators.iloc[-1]

if latest['close'] > latest['sma_50'] > latest['sma_200']:
    print("Strong Uptrend")
elif latest['close'] < latest['sma_50'] < latest['sma_200']:
    print("Strong Downtrend")
```

### Overbought/Oversold

```python
if latest['rsi_14'] > 70:
    print("Overbought - Consider taking profits")
elif latest['rsi_14'] < 30:
    print("Oversold - Consider buying opportunity")
```

### MACD Crossover

```python
if latest['macd'] > latest['signal'] and latest['histogram'] > 0:
    print("Bullish MACD signal")
```

### Bollinger Band Squeeze

```python
band_width = (latest['upper'] - latest['lower']) / latest['middle']
if band_width < 0.10:  # 10% of price
    print("Bollinger Band Squeeze - Breakout expected")
```

## Storing Indicators

Indicators are automatically stored in the `technical_indicators` table when you run:

```powershell
.\tasks.ps1 calc-indicators
```

You can query them directly:

```python
import duckdb

conn = duckdb.connect('./data/ducklens.db')

# Get latest indicators for all symbols
df = conn.execute("""
    SELECT
        symbol,
        timestamp,
        close,
        sma_50,
        rsi_14,
        macd,
        macd_signal
    FROM (
        SELECT
            symbol,
            timestamp,
            close,
            sma_50,
            rsi_14,
            macd,
            macd_signal,
            ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY timestamp DESC) as rn
        FROM technical_indicators
    )
    WHERE rn = 1
    ORDER BY symbol
""").fetchdf()

print(df)
```

## Command Reference

```powershell
# Calculate and store all indicators
.\tasks.ps1 calc-indicators

# Show example indicators for SPY
.\tasks.ps1 show-indicators

# Run indicator tests
.\tasks.ps1 test-indicators

# Custom ticker
poetry run python scripts/calculate_indicators.py --example AAPL

# Calculate for custom list
poetry run python scripts/calculate_indicators.py --tickers AAPL,MSFT,GOOGL --store
```

## Performance Notes

- **No API calls needed** - All calculations use stored price data
- **Fast** - Calculate indicators for 19 tickers in < 10 seconds
- **Flexible** - Adjust windows, parameters instantly
- **Storage** - Pre-calculated indicators stored for quick access

## Indicator Combinations

### Golden Cross Strategy

```python
# SMA50 crosses above SMA200 = Bullish
indicators = calc.calculate_all_indicators("SPY")

# Check for recent cross
if (indicators['sma_50'].iloc[-1] > indicators['sma_200'].iloc[-1] and
    indicators['sma_50'].iloc[-2] < indicators['sma_200'].iloc[-2]):
    print("Golden Cross detected!")
```

### RSI + MACD Confirmation

```python
latest = indicators.iloc[-1]

if latest['rsi_14'] < 30 and latest['macd'] > latest['signal']:
    print("Oversold with bullish MACD - Strong buy signal")
```

### Bollinger + RSI Reversal

```python
if latest['close'] < latest['lower'] and latest['rsi_14'] < 30:
    print("Price at lower BB and oversold - Reversal likely")
```

## Files Created

- `src/analysis/indicators.py` - Technical indicators calculator
- `src/analysis/__init__.py` - Module init
- `scripts/calculate_indicators.py` - CLI tool
- `tests/unit/test_indicators.py` - Comprehensive tests
- `tasks.ps1` - Added 3 new commands

## Next Steps

1. Calculate indicators for your data:
   ```powershell
   .\tasks.ps1 calc-indicators
   ```

2. View latest signals:
   ```powershell
   .\tasks.ps1 show-indicators
   ```

3. Build trading strategies using these indicators!
