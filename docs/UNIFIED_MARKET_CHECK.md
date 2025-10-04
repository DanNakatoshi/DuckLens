# Unified Market Check - Smart All-Day Monitor

## Overview

The **Unified Market Check** (`market_check.py`) replaces both `morning_check.py` and `intraday_monitor_enhanced.py` with a single intelligent script that adapts to market conditions.

## Key Features

### 🎯 Smart Market Detection
- **Auto-detects market status**: Pre-market, Market Open, After-Hours, Weekend
- **Intelligent data sourcing**:
  - Live prices (15-min delayed) during market hours via Polygon.io
  - Historical prices from database when market is closed
- **Clear status indicators**: Shows exactly what data you're seeing

### 🔄 Auto-Refresh Mode
- **Live mode**: `--live` flag enables automatic refresh during market hours
- **Configurable interval**: Default 60 seconds, customizable with `--interval`
- **Smart behavior**: Only refreshes when market is open, static otherwise

### 📊 Comprehensive Analysis

All sections shared between morning and intraday checks:

1. **Account Summary**
   - Cash balance, portfolio value, total account value
   - Buying power and margin risk analysis
   - Progress tracking toward $1M goal

2. **Market Direction**
   - SPY and QQQ signals with confidence scores
   - VIX fear index
   - Market condition (BULLISH/BEARISH/NEUTRAL)
   - Live price indicators during market hours

3. **Holdings Analysis**
   - Current positions with P/L
   - Signal change tracking (morning vs current)
   - Action recommendations (SELL NOW, HOLD, WATCH)
   - Live price updates during market hours

4. **Watchlist - New Opportunities**
   - Top 10 buy candidates ranked by composite score
   - Earnings safety check
   - Relative strength vs SPY
   - Entry quality scoring

5. **Portfolio Optimization**
   - Portfolio health score (0-100)
   - Rebalancing recommendations
   - Underperformer alerts

6. **Today's Game Plan**
   - Summary of actions needed
   - Sell signals requiring attention
   - Stocks to monitor closely
   - Strong buy opportunities

## Usage

### Basic Usage (Static Mode)
```powershell
# Single snapshot - no refresh
.\tasks.ps1 market-check
```

### Live Mode (During Market Hours)
```powershell
# Auto-refresh every 60 seconds
.\tasks.ps1 market-check --live

# Auto-refresh every 5 minutes
.\tasks.ps1 market-check --live --interval 300
```

### Direct Python Usage
```powershell
# Static mode
python scripts/market_check.py

# Live mode with default 60s interval
python scripts/market_check.py --live

# Live mode with custom interval
python scripts/market_check.py --live --interval 120
```

## When to Use

### Pre-Market (Before 9:30 AM)
- Run in **static mode** for morning planning
- Shows yesterday's close prices
- Plan your trading day

### During Market Hours (9:30 AM - 4:00 PM)
- Run in **live mode** for real-time tracking
- Prices update automatically every 60 seconds (or custom interval)
- Shows "LIVE (15m delay)" indicator for real-time data
- Perfect for monitoring positions and finding entries

### After Hours (After 4:00 PM)
- Run in **static mode** for end-of-day review
- Shows today's 4 PM close prices
- Review performance and plan for tomorrow

### Weekend
- Static mode only (market closed)
- Shows last Friday's close
- Good for weekly review and strategy planning

## Signal Change Tracking

The unified script automatically tracks signal changes between morning and current signals:

- **⚠️ CHANGED: BUY→SELL** - Immediate sell alert
- **⚠️ CHANGED: SELL→HOLD** - Caution, bounce may be temporary
- **Consistent signals** - More confidence in the trade

### Why Signals Change
During market hours, signals can change due to:
- Price movement crossing key levels (SMA 20/50)
- MACD momentum shifts
- Volume spikes indicating reversals
- RSI entering overbought/oversold territory

## Data Sources

### Live Data (Market Hours)
- **Source**: Polygon.io API
- **Delay**: 15 minutes (free tier)
- **Update**: Every 1-5 minutes (configurable)
- **Indicator**: Green "LIVE (15m delay)" or green dot "●"

### Historical Data (Outside Market Hours)
- **Source**: DuckDB database
- **Data**: Previous close prices
- **Indicator**: "DB" or no live marker

## Advantages Over Separate Scripts

### ✅ Code Efficiency
- **~70% less code duplication**
- Single source of truth for all sections
- Easier to maintain and update

### ✅ Smart Behavior
- Automatically adapts to market conditions
- No need to remember which script to run when
- Intelligent data source switching

### ✅ Consistent Experience
- Same interface morning, intraday, and after-hours
- Unified formatting with Rich tables and panels
- Clear visual indicators for data freshness

### ✅ Flexible Usage
- Can run once for quick check
- Can auto-refresh for continuous monitoring
- Customizable refresh rate for your workflow

## Migration from Old Scripts

### Replace This:
```powershell
# Old workflow
.\tasks.ps1 morning          # Before market open
.\tasks.ps1 intraday-plus    # At 3 PM
```

### With This:
```powershell
# New unified workflow
.\tasks.ps1 market-check               # Pre-market planning (static)
.\tasks.ps1 market-check --live        # During market hours (live)
.\tasks.ps1 market-check               # After hours review (static)
```

## Technical Details

### Market Hours Detection
```python
class MarketStatus:
    @staticmethod
    def get_status() -> dict:
        # Returns:
        # - is_open: bool
        # - status: PRE_MARKET | MARKET_OPEN | AFTER_HOURS | WEEKEND
        # - should_refresh: bool
        # - data_source: description
```

### Smart Price Fetching
```python
def get_price_data(ticker, market_status, db, collector=None):
    if market_status["is_open"] and collector:
        # Try Polygon API for live data
        # Return with is_live=True

    # Fallback to database
    # Return with is_live=False
```

### Auto-Refresh Loop
```python
def generate_market_check(auto_refresh=False, refresh_interval=60):
    while True:
        # Generate full report

        if auto_refresh and market_status["should_refresh"]:
            time.sleep(refresh_interval)
            continue
        else:
            break  # Exit after one run
```

## Best Practices

1. **Morning (Pre-Market)**
   - Run once in static mode
   - Review sell signals from yesterday
   - Identify strong buy opportunities
   - Plan your trading day

2. **During Market Hours**
   - Run with `--live` flag
   - Keep running in background
   - Monitor for signal changes
   - Watch for new entries

3. **Afternoon (3 PM)**
   - Check for any signal changes
   - Execute planned trades
   - Look for late-day opportunities

4. **After Hours**
   - Run once in static mode
   - Review day's performance
   - Update trade journal
   - Plan for tomorrow

## Troubleshooting

### No Live Data During Market Hours
- **Issue**: Shows "DB" instead of "LIVE"
- **Cause**: Polygon API connection issue
- **Fix**: Check internet connection, verify API key in `.env`

### Auto-Refresh Not Working
- **Issue**: Script exits immediately
- **Cause**: Market is closed (should_refresh=False)
- **Expected**: Auto-refresh only works during market hours

### Signal Changes Confusing
- **Issue**: Morning SELL now shows HOLD
- **Explanation**: Price bounced, but use caution - weakness still present
- **Action**: Monitor closely, respect new signal but consider original thesis

## Future Enhancements

Potential additions for Phase 2:
- [ ] Email/SMS alerts for signal changes
- [ ] Price alerts for key levels
- [ ] Trade execution integration
- [ ] Performance analytics dashboard
- [ ] Multi-timeframe analysis (1min, 5min, daily)

---

**Status**: ✅ Production Ready
**Last Updated**: 2025-10-03
**Replaces**: `morning_check.py`, `intraday_monitor_enhanced.py`
