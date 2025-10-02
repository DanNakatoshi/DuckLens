# Console Charts - Quick Reference

## Installation

```powershell
# Install chart dependencies
.\tasks.ps1 install
```

## Usage

### From Menu (Interactive)
```powershell
.\menu.ps1
# Choose option 8 - Show Chart
# Enter ticker when prompted (e.g., AAPL, TSLA, SPY)
# Enter days (default: 90)
```

### From Command Line
```powershell
# Default: AAPL, 90 days
.\tasks.ps1 chart

# Specific ticker
.\tasks.ps1 chart TSLA

# Custom period
.\tasks.ps1 chart GOOGL 180

# Short period
.\tasks.ps1 chart SPY 30
```

## What Gets Displayed

### 1. Price Chart with Moving Averages
- **Close price** (cyan line)
- **SMA 20** (yellow line) - Short-term trend
- **SMA 50** (magenta line) - Medium-term trend
- **SMA 200** (blue line) - Long-term trend

### 2. RSI Indicator
- Range: 0-100
- **> 70**: Overbought (potential sell signal)
- **< 30**: Oversold (potential buy signal)
- **40-60**: Neutral/healthy

### 3. MACD Indicator
- **Positive**: Bullish momentum
- **Negative**: Bearish momentum
- Crossovers signal potential trend changes

### 4. Current Values
- Latest price and all indicator values
- Quick reference for decision making

## Reading the Charts

### Golden Cross (Bullish)
```
SMA 20 crosses ABOVE SMA 50
SMA 50 crosses ABOVE SMA 200
```
→ Strong buy signal (what the strategy looks for!)

### Death Cross (Bearish)
```
SMA 50 crosses BELOW SMA 200
```
→ Exit signal (triggers 2x leverage exit)

## Examples

### Check market leaders before trading
```powershell
.\tasks.ps1 chart SPY 90   # S&P 500
.\tasks.ps1 chart QQQ 90   # Nasdaq
.\tasks.ps1 chart DIA 90   # Dow Jones
```

### Analyze buy signals from morning check
```powershell
# Morning check shows AAPL has BUY signal
.\tasks.ps1 chart AAPL 180  # View 6-month trend
```

### Compare tech stocks
```powershell
.\tasks.ps1 chart AAPL
.\tasks.ps1 chart MSFT
.\tasks.ps1 chart GOOGL
.\tasks.ps1 chart NVDA
```

### Monitor current holdings
```powershell
# For each ticker in your portfolio
.\tasks.ps1 chart TSLA
.\tasks.ps1 chart COIN
.\tasks.ps1 chart AMD
```

## Chart Libraries Used

1. **asciichartpy** - Primary chart engine (clean, fast)
2. **plotille** - Backup with multi-line support
3. **Fallback** - Unicode sparklines if libraries not installed

Charts will automatically use the best available library!
