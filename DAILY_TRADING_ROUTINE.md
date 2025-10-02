# Daily Trading Routine - 3 PM Decision Framework

## Overview

Your optimal trading time is **3 PM ET** because:
- ✓ You've seen morning price action (9:30 AM - 12 PM)
- ✓ You've seen noon volatility (12 PM - 2 PM)
- ✓ You have 1 hour before close to execute (3 PM - 4 PM)
- ✓ Avoid last-minute pump/dump in final 15 minutes

This guide gives you a **simple 3-command daily routine** to make informed decisions.

---

## 📋 **Your Daily Trading Routine**

### **Morning (8 AM - 9:30 AM) - Pre-Market Check**

```powershell
.\tasks.ps1 morning
```

**What it shows:**
- ✓ Your holdings status (based on yesterday's close)
- ✓ Any sell signals on your positions
- ✓ New buy opportunities on watchlist
- ✓ Today's game plan

**Time required:** 5 minutes

**What to do:**
1. Read the report over coffee
2. Note any sell signals (you'll verify at 3 PM)
3. Note buy candidates (you'll check entry at 3 PM)
4. Go about your day

**Example output:**
```
SECTION 1: YOUR HOLDINGS
Ticker   Qty    Cost       Close      P&L          Signal       Status
UPS      20     $153.40    $84.38     -$1,380 (-45%) SELL        SELL TODAY?
NVDA     10     $450.20    $625.50    +$1,753 (+39%) DONT_TRADE  WINNING

! SELL SIGNALS: 1 stock to review today
  - UPS: Death cross signal - check at 3 PM

SECTION 2: WATCHLIST
Ticker   Close      Signal    Confidence  Opportunity
GOOGL    $175.20    BUY       85%         Golden cross + RSI healthy

SECTION 3: TODAY'S GAME PLAN
1. REVIEW SELL SIGNALS (1 stock)
   - UPS: Check intraday price action at 3 PM

2. WATCH BUY CANDIDATES (1 stock)
   - GOOGL: Golden cross + RSI healthy
     Entry: $175.20 (wait for dip or confirm strength)
```

---

### **3 PM (Decision Time) - Intraday Monitor**

```powershell
.\tasks.ps1 intraday
```

**What it shows:**
- ✓ Real-time prices (15-min delayed)
- ✓ Intraday movement (% change from open/close)
- ✓ Updated buy/sell signals
- ✓ Recommended actions (BUY/SELL/HOLD/WAIT)

**Time required:** 10-15 minutes

**What to do:**
1. Review holdings - any sell signals?
2. Check watchlist - any good buy entries?
3. Make final decision
4. Execute trades on E*TRADE

**Example output:**
```
SECTION 1: YOUR HOLDINGS - Sell Check
Ticker   Current    Change%   Intraday   Signal       Action     Reason
UPS      $84.38     -0.5%     +0.2%      SELL         SELL       Strategy says SELL: Death cross confirmed
NVDA     $628.20    +0.4%     +1.2%      DONT_TRADE   HOLD       No signal, holding (up 0.4% today)

! SELL SIGNALS: 1 stock
  - UPS: Strategy says SELL: Death cross confirmed

SECTION 2: WATCHLIST - Buy Opportunities
Ticker   Current    Change%   Intraday   Signal       Action     Reason
GOOGL    $173.50    -1.0%     -0.8%      BUY          BUY        BUY signal + down 1.0% - good entry

SECTION 3: 3 PM TRADING DECISION SUMMARY
SELL (1 stock):
  -> UPS @ $84.38  (Strategy says SELL: Death cross confirmed)

BUY (1 stock):
  -> GOOGL @ $173.50  (BUY signal + down 1.0% - good entry)
```

**Decision matrix:**

| Situation | Action | Reason |
|-----------|--------|--------|
| SELL signal + holding stock | **SELL** | Exit on death cross |
| BUY signal + stock down 1-3% | **BUY** | Good entry on dip |
| BUY signal + stock up >2% | **WAIT** | Don't chase, wait for pullback |
| No signal + stock down >5% | **WATCH** | Possible breakdown or opportunity |
| No signal + stock flat | **PASS** | No action needed |

---

### **After Hours (After 4 PM) - Update Portfolio**

```powershell
.\tasks.ps1 update-daily
```

**What it does:**
1. Fetches today's closing data
2. Calculates updated signals
3. Shows portfolio P&L
4. **Asks you to record any trades you made**

**Time required:** 5 minutes

**What to do:**
1. When prompted "Do you have portfolio changes?" → **y**
2. Select trade type:
   - **1** = BUY (add shares)
   - **2** = SELL (remove shares)
   - **3** = Update cash
3. Enter details (ticker, quantity, price)
4. System logs the trade automatically

**Example:**
```
Do you have any portfolio changes to record? (y/n): y

What type of change?
  1. BUY (add shares)
  2. SELL (remove shares)
  3. Update cash
  4. Done

Choice: 2
Ticker symbol: UPS
Quantity to sell: 20
Sale price per share: 84.38
Notes (optional): Sold on death cross signal

OK Sold 20 shares of UPS @ $84.38 (Proceeds: $1,687.60)

What type of change?
  1. BUY (add shares)
  2. SELL (remove shares)
  3. Update cash
  4. Done

Choice: 1
Ticker symbol: GOOGL
Quantity: 10
Price paid per share: 173.50
Notes (optional): Bought on golden cross + dip

OK Added 10 shares of GOOGL @ $173.50
```

---

## 🕐 **Complete Daily Schedule**

| Time | Command | Purpose | Duration |
|------|---------|---------|----------|
| **8-9 AM** | `.\tasks.ps1 morning` | Pre-market check, plan the day | 5 min |
| **12-1 PM** | *(Optional)* Quick price check on E*TRADE | See if anything crazy happened | 2 min |
| **3 PM** | `.\tasks.ps1 intraday` | Make final buy/sell decisions | 10-15 min |
| **3:15-3:45 PM** | Execute trades on E*TRADE | Buy/sell based on signals | 5-10 min |
| **After 4 PM** | `.\tasks.ps1 update-daily` | Record trades, update portfolio | 5 min |

**Total time:** 25-35 minutes per day

---

## 🎯 **Decision Rules (Keep It Simple)**

### **When to SELL:**

1. ✅ **Death cross signal** (SMA_50 < SMA_200) → SELL immediately
2. ✅ **Down >10% from entry** → SELL (stop loss)
3. ⚠️ **VXX > 50** → Consider selling 50% (crash warning)

### **When to BUY:**

1. ✅ **Golden cross signal** (SMA: 20>50>200) + confidence >75%
2. ✅ **Stock down 1-3% intraday** (buy the dip)
3. ✅ **RSI 40-75** (healthy range, not overbought)
4. ❌ **Don't buy if stock up >2% today** (wait for pullback)

### **When to HOLD:**

1. ✅ **No signal** → Do nothing
2. ✅ **Winning position** (up >10%) with no sell signal → Let it run
3. ✅ **Losing position** but no death cross yet → Be patient

### **When to WAIT:**

1. ⏸️ **Buy signal but stock rallying hard** (>2% up) → Wait for pullback
2. ⏸️ **3 days before earnings** → Don't enter new positions
3. ⏸️ **Volume >3x average** → Unusual activity, wait to understand

---

## 💡 **Pro Tips**

### **Avoid Emotional Trading:**
- ✓ Stick to the signals - don't override based on "gut feeling"
- ✓ If signal says SELL, sell (even if you like the stock)
- ✓ If signal says WAIT, wait (even if you want to buy)

### **Position Sizing:**
- Start with **10-20 shares per stock** (~$1,000-2,000 per position)
- Max **5-8 positions** at once (diversification)
- Keep **25-50% cash** (for opportunities)

### **Don't Chase:**
- If you miss a 3 PM entry, **wait for next day**
- Better to miss a trade than buy at the top

### **Use Limit Orders:**
- Don't use market orders (you'll get bad fills)
- Set limit at current price or $0.05-0.10 below
- Example: Stock at $173.50 → Set limit buy at $173.45

---

## 📱 **Quick Reference Card** (Print This)

```
MORNING (8 AM):
  .\tasks.ps1 morning
  → Read report, note sells/buys

3 PM (DECISION TIME):
  .\tasks.ps1 intraday
  → Check real-time prices
  → SELL on death cross
  → BUY on golden cross + dip
  → Execute trades on E*TRADE

AFTER HOURS (4+ PM):
  .\tasks.ps1 update-daily
  → Record today's trades
  → See updated portfolio

WEEKLY (Sunday):
  .\tasks.ps1 backtest-10-years
  → Review long-term performance
  → Identify new top performers
```

---

## ❓ **FAQ**

**Q: What if I can't trade at 3 PM?**
A: Set price alerts on E*TRADE. If buy signal hits your target, place limit order for next day.

**Q: What if market is crazy volatile?**
A: Check VXX. If VXX > 50, sit in cash. Don't trade during crashes.

**Q: How many trades per week is normal?**
A: 1-3 trades per week. You're trend-following (300-500 day holds), not day trading.

**Q: Should I use stop losses?**
A: Yes! Death cross IS your stop loss. Exit when SMA_50 < SMA_200.

**Q: What if I disagree with a signal?**
A: The strategy has 94% win rate. Trust the system. Override at your own risk.

**Q: Can I check more than 3 PM?**
A: Yes, but don't overtrade. More checking = more emotional decisions.

---

## 🚀 **Get Started Today**

**Right now, run:**
```powershell
.\tasks.ps1 morning
```

**Then set a calendar reminder for 3 PM:**
```powershell
.\tasks.ps1 intraday
```

**That's it! Two commands = informed trading decisions.**

---

## 📊 **Track Your Progress**

After 1 month, run:
```powershell
.\tasks.ps1 analyze-trades
```

This shows:
- Win rate (should be 70-90%)
- Average hold time (should be 200-500 days)
- Best/worst trades
- What's working, what's not

**Adjust strategy based on data, not emotions!**
