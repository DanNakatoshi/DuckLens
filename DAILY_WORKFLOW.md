# DuckLens - Daily Trading Workflow

## 🚀 Quick Start with Unified Market Check

### Interactive Menu (Easiest)
```powershell
.\menu.ps1
```
Then select:
- **Option 1**: Market Check (Static) - For snapshots
- **Option 2**: Market Check LIVE - For real-time monitoring

---

## 📅 Daily Workflow

### Morning Routine (Before 9:30 AM)

```powershell
# 1. Get pre-market analysis
.\tasks.ps1 market-check
```

**What you'll see:**
- Account summary (cash, portfolio, margin risk)
- Market direction (SPY/QQQ signals)
- Holdings analysis with P/L
- Top buy opportunities
- Stocks to watch/sell today
- Today's game plan

### During Market Hours (9:30 AM - 4:00 PM)

```powershell
# 2. Monitor with live updates (auto-refresh every 60 seconds)
.\tasks.ps1 market-check --live
```

**What you'll see:**
- 🟢 **LIVE** prices (15-min delayed from Polygon.io)
- Signal change alerts (e.g., "⚠️ CHANGED: SELL→HOLD")
- Real-time P/L on holdings
- Updated buy opportunities
- Market condition changes

**To stop:** Press `Ctrl+C`

### End of Day (After 4:00 PM)

```powershell
# 3. Update market data
.\tasks.ps1 update-daily

# 4. Review final positions
.\tasks.ps1 market-check

# 5. Record any executed trades
.\tasks.ps1 add-trade

# 6. Update cash if you deposited/withdrew
.\tasks.ps1 update-cash
```

---

## 📊 Portfolio Management

### Account Health
```powershell
# View margin risk, progress to $1M
.\tasks.ps1 account-health
```

### Performance Tracking
```powershell
# Compare your returns vs SPY
.\tasks.ps1 track-performance
```

### Trade Analysis
```powershell
# Learn from past trades
.\tasks.ps1 analyze-trades
```

---

## 🔧 Advanced Usage

### Custom Refresh Interval
```powershell
# Refresh every 5 minutes (300 seconds)
.\tasks.ps1 market-check --live --interval 300
```

### Weekend Analysis
```powershell
# Review Friday's close, plan for Monday
.\tasks.ps1 market-check
```

### Chart Viewing
```powershell
# View any ticker's chart
.\tasks.ps1 chart AAPL 90
```

---

## 📈 Data Management

### Initial Setup (One Time)
```powershell
# Fetch 10 years of historical data
.\tasks.ps1 fetch-10-years

# Fetch earnings calendar
.\tasks.ps1 fetch-earnings

# Calculate technical indicators
.\tasks.ps1 calc-indicators
```

### Daily Maintenance
```powershell
# Update all data (run after 4 PM)
.\tasks.ps1 update-daily
```

### Data Verification
```powershell
# Check data integrity
.\tasks.ps1 check-data

# View database stats
.\tasks.ps1 db-stats
```

---

## 🎯 Market Check Features

### Auto-Detection
The unified market check automatically detects:
- **PRE_MARKET** (before 9:30 AM) → Shows yesterday's close
- **MARKET_OPEN** (9:30 AM - 4 PM) → Shows live prices
- **AFTER_HOURS** (after 4 PM) → Shows today's close
- **WEEKEND** → Shows Friday's close

### Data Sources
- **LIVE Mode**: Polygon.io API (15-min delayed)
- **Static Mode**: DuckDB database (historical)

### Signal Tracking
- Compares morning signals with current signals
- Alerts on changes: `⚠️ CHANGED: BUY→SELL - SELL NOW!`
- Educational tips on why signals change

---

## 🔍 Understanding Signals

### Signal Types
- **BUY** 🟢 - Strong uptrend, good entry point
- **SELL** 🔴 - Downtrend detected, exit position
- **HOLD** 🟡 - Neutral, wait for better setup
- **DONT_TRADE** ⚪ - Earnings/events soon, avoid

### Signal Changes
Signals can change intraday based on:
- Price crossing moving averages (SMA 20/50)
- MACD momentum shifts
- Volume spikes
- RSI overbought/oversold levels

**Learn more:** [docs/UNDERSTANDING_SIGNAL_CHANGES.md](docs/UNDERSTANDING_SIGNAL_CHANGES.md)

---

## 📚 Documentation

- **[Unified Market Check Guide](docs/UNIFIED_MARKET_CHECK.md)** - Complete feature documentation
- **[Migration Guide](docs/MIGRATION_TO_UNIFIED.md)** - Transition from old scripts
- **[Signal Changes Explained](docs/UNDERSTANDING_SIGNAL_CHANGES.md)** - Why signals change

---

## ⚡ Command Cheat Sheet

### Daily Essentials
| Command | Description | When to Run |
|---------|-------------|-------------|
| `.\tasks.ps1 market-check` | Market snapshot | Anytime |
| `.\tasks.ps1 market-check --live` | Live monitoring | During market hours |
| `.\tasks.ps1 update-daily` | Data update | After 4 PM |
| `.\tasks.ps1 add-trade` | Log trades | After execution |

### Analysis Tools
| Command | Description |
|---------|-------------|
| `.\tasks.ps1 account-health` | Account dashboard |
| `.\tasks.ps1 track-performance` | Performance vs SPY |
| `.\tasks.ps1 analyze-trades` | Trade journal analysis |
| `.\tasks.ps1 watchlist` | All watchlist signals |

### Data Management
| Command | Description |
|---------|-------------|
| `.\tasks.ps1 check-data` | Verify data integrity |
| `.\tasks.ps1 db-stats` | Database statistics |
| `.\tasks.ps1 calc-indicators` | Update indicators |

---

## 🎮 Interactive Menu

For the easiest experience, use the interactive menu:

```powershell
.\menu.ps1
```

**Features:**
- Numbered options (just type 1, 2, 3, etc.)
- Organized by category
- Helpful descriptions
- Press any key to continue after each command

---

## 💡 Tips

1. **Morning Routine**
   - Run market check before 9:30 AM
   - Review sell signals and buy opportunities
   - Plan your trades for the day

2. **Intraday Monitoring**
   - Use live mode during market hours
   - Watch for signal changes
   - Execute trades based on latest data

3. **End of Day**
   - Update all data after 4 PM
   - Record executed trades
   - Review performance vs plan

4. **Weekend**
   - Review weekly performance
   - Plan strategy for Monday
   - Check for upcoming earnings

---

## 🚨 Important Notes

- **Live data** has a 15-minute delay (Polygon.io free tier)
- **Signal changes** are normal - price discovery happens intraday
- **Respect new signals** even if they differ from morning
- **Use caution** when SELL→HOLD (bounce may be temporary)

---

**Status**: ✅ Production Ready
**Last Updated**: 2025-10-03
**Unified Script**: [scripts/market_check.py](scripts/market_check.py)
