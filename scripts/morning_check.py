"""
Morning Check - Pre-market analysis at 9 AM before market opens.

Shows:
- What happened overnight (pre-market movers)
- Earnings reports today
- Your holdings status from yesterday's close
- Watchlist opportunities for today
"""

import sys
import json
from datetime import datetime, date as date_type, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from src.config.tickers import TIER_2_STOCKS
from src.data.storage.market_data_db import MarketDataDB
from src.models.enhanced_detector import EnhancedTrendDetector
from src.models.trend_detector import TradingSignal
from src.portfolio.portfolio_manager import PortfolioManager
from src.models.market_regime import RegimeDetector
from src.models.earnings_filter import EarningsFilter
from src.models.entry_quality import EntryQualityScorer
from src.models.relative_strength import RelativeStrengthAnalyzer
from src.models.financial_calendar import FinancialCalendar, EventImpact
from src.analysis.portfolio_analyzer import PortfolioAnalyzer
from src.allocation.position_sizer import PositionSizer
from src.tracking.signal_tracker import SignalTracker

load_dotenv()

# Initialize rich console
console = Console()


def get_yesterday_close(ticker: str, db: MarketDataDB) -> tuple:
    """Get yesterday's closing price and signal."""
    query = """
        SELECT close, timestamp
        FROM stock_prices
        WHERE symbol = ?
        ORDER BY timestamp DESC
        LIMIT 1
    """
    result = db.conn.execute(query, [ticker]).fetchone()

    if result:
        return float(result[0]), result[1]
    return None, None


def get_market_direction(db: MarketDataDB, detector: EnhancedTrendDetector) -> dict:
    """Check overall market direction (SPY/QQQ trends)."""
    market_status = {}

    for ticker in ["SPY", "QQQ"]:
        price, date = get_yesterday_close(ticker, db)
        if price and date:
            signal = detector.generate_signal(ticker, date, price)
            market_status[ticker] = {
                "price": price,
                "signal": signal.signal,
                "confidence": signal.confidence,
                "reasoning": signal.reasoning,
            }

    return market_status


def calculate_risk_reward(ticker: str, current_price: float, db: MarketDataDB) -> dict:
    """Calculate risk/reward ratio based on recent support/resistance levels."""
    try:
        # Get last 60 days of price data to identify support/resistance
        query = """
            SELECT high, low, close
            FROM stock_prices
            WHERE symbol = ?
            ORDER BY timestamp DESC
            LIMIT 60
        """
        results = db.conn.execute(query, [ticker]).fetchall()

        if len(results) < 20:
            return {"risk_reward_ratio": None, "support": None, "resistance": None}

        highs = [float(r[0]) for r in results]
        lows = [float(r[1]) for r in results]

        # Resistance: 90th percentile of recent highs (strong overhead)
        resistance = sorted(highs)[int(len(highs) * 0.9)]

        # Support: 10th percentile of recent lows (strong floor)
        support = sorted(lows)[int(len(lows) * 0.1)]

        # Risk: distance to support (how much we could lose)
        risk = current_price - support

        # Reward: distance to resistance (how much we could gain)
        reward = resistance - current_price

        # Risk/Reward ratio (higher is better)
        if risk > 0:
            risk_reward_ratio = reward / risk
        else:
            risk_reward_ratio = 0

        return {
            "risk_reward_ratio": risk_reward_ratio,
            "support": support,
            "resistance": resistance,
            "upside_pct": (reward / current_price) * 100,
            "downside_pct": (risk / current_price) * 100,
        }

    except Exception as e:
        return {"risk_reward_ratio": None, "support": None, "resistance": None}


def main():
    """Morning check - run before market open."""

    # Header
    console.print()
    title = Text("MORNING CHECK", style="bold white on blue")
    subtitle = Text(f"Pre-Market Analysis - {datetime.now().strftime('%Y-%m-%d %I:%M %p ET')}", style="cyan")
    console.print(Panel(title, subtitle=subtitle, border_style="bright_blue", box=box.DOUBLE))

    current_hour = datetime.now().hour

    if current_hour >= 16:
        console.print(">> [yellow]AFTER MARKET CLOSE[/yellow]")
        console.print("   This is for morning pre-market check (before 9:30 AM)")
        console.print("   For intraday decisions, use: [cyan].\\tasks.ps1 intraday[/cyan]\n")
    elif 9 <= current_hour < 16:
        console.print(">> [yellow]MARKET IS OPEN[/yellow]")
        console.print("   For real-time 3 PM decisions, use: [cyan].\\tasks.ps1 intraday[/cyan]\n")
    else:
        console.print(">> [green]PRE-MARKET:[/green] Good time to review overnight changes\n")

    # Initialize
    db = MarketDataDB()
    detector = EnhancedTrendDetector(
        db=db,
        min_confidence=0.75,
        confirmation_days=1,
        long_only=True,
        log_trades=False,
        block_earnings_window=3,
        volume_spike_threshold=3.0,
    )
    portfolio_manager = PortfolioManager()
    portfolio = portfolio_manager.load_portfolio()

    # Section -1: ACCOUNT BALANCE
    console.print("\n[bold bright_white]>> ACCOUNT SUMMARY[/bold bright_white]", style="on blue")

    try:
        balance = db.conn.execute("""
            SELECT cash_balance, portfolio_value, total_value,
                   margin_used, margin_available, buying_power
            FROM account_balance
            ORDER BY balance_date DESC
            LIMIT 1
        """).fetchone()

        if balance:
            cash, portfolio_val, total, margin_used, margin_avail, buying_power = balance

            # Calculate percentages
            cash_pct = (cash / total * 100) if total > 0 else 0

            # Determine margin risk
            margin_pct = (margin_used / total * 100) if margin_used > 0 and total > 0 else 0
            if margin_pct > 50:
                risk_level = "HIGH RISK"
                risk_color = "red"
            elif margin_pct > 25:
                risk_level = "MODERATE"
                risk_color = "yellow"
            elif margin_pct > 0:
                risk_level = "LOW RISK"
                risk_color = "green"
            else:
                risk_level = "NO MARGIN"
                risk_color = "bright_green"

            balance_table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
            balance_table.add_column("Metric", style="bold white", width=20)
            balance_table.add_column("Amount", justify="right", style="bright_white", width=15)
            balance_table.add_column("Details", style="cyan", width=40)

            balance_table.add_row(
                "Cash Balance",
                f"${cash:,.2f}",
                f"{cash_pct:.1f}% of total"
            )
            balance_table.add_row(
                "Portfolio Value",
                f"${portfolio_val:,.2f}",
                f"{100 - cash_pct:.1f}% of total"
            )
            balance_table.add_row(
                "Total Account Value",
                f"${total:,.2f}",
                f"Path to $1M: {(total / 1_000_000 * 100):.1f}%"
            )
            balance_table.add_row(
                "Buying Power",
                f"${buying_power:,.2f}",
                f"Cash + Margin Available"
            )
            balance_table.add_row(
                "Margin Risk",
                f"[{risk_color}]{risk_level}[/{risk_color}]",
                f"Using ${margin_used:,.2f} ({margin_pct:.1f}% of account)"
            )

            console.print(balance_table)
        else:
            console.print("[yellow]No account balance data found[/yellow]")
            console.print("[dim]Run: .\\tasks.ps1 update-cash[/dim]")
    except Exception as e:
        console.print(f"[red]Error loading account balance: {e}[/red]")

    # Section 0: MARKET DIRECTION
    console.print("\n[bold bright_white]>> MARKET DIRECTION[/bold bright_white]", style="on blue")

    # Get regime info first (needed for VIX in market strength indicators)
    regime_detector = RegimeDetector(db)
    regime_info = regime_detector.detect_regime()

    market_status = get_market_direction(db, detector)

    if market_status:
        market_table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
        market_table.add_column("Index", style="bold white", width=8)
        market_table.add_column("Price", justify="right", style="bright_white", width=12)
        market_table.add_column("Signal", width=12)
        market_table.add_column("Confidence", justify="right", width=12)
        market_table.add_column("Trend", width=50)

        for ticker, status in market_status.items():
            # Color code signals
            if status['signal'] == TradingSignal.BUY:
                signal_text = f"[bold green]{status['signal'].value}[/bold green]"
            elif status['signal'] == TradingSignal.SELL:
                signal_text = f"[bold red]{status['signal'].value}[/bold red]"
            else:
                signal_text = f"[yellow]{status['signal'].value}[/yellow]"

            market_table.add_row(
                ticker,
                f"${status['price']:.2f}",
                signal_text,
                f"{status['confidence']:.0%}",
                status['reasoning'][:48]
            )

        console.print(market_table)

        # Add market strength indicators
        console.print()
        strength_table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
        strength_table.add_column("Indicator", style="bold white", width=25)
        strength_table.add_column("Value", justify="right", style="bright_white", width=15)
        strength_table.add_column("Status", width=30)

        # Get SPY volume
        spy_volume = db.conn.execute("""
            SELECT volume
            FROM stock_prices
            WHERE symbol = 'SPY'
            ORDER BY timestamp DESC
            LIMIT 1
        """).fetchone()

        if spy_volume:
            vol_millions = float(spy_volume[0]) / 1_000_000
            # Get 20-day avg volume
            avg_vol = db.conn.execute("""
                SELECT AVG(volume)
                FROM stock_prices
                WHERE symbol = 'SPY'
                AND timestamp >= (SELECT MAX(timestamp) FROM stock_prices WHERE symbol = 'SPY') - INTERVAL '20 days'
            """).fetchone()

            if avg_vol and avg_vol[0]:
                avg_vol_millions = float(avg_vol[0]) / 1_000_000
                vol_ratio = vol_millions / avg_vol_millions
                vol_status = "[green]Above average[/green]" if vol_ratio > 1.1 else "[yellow]Normal[/yellow]" if vol_ratio > 0.9 else "[red]Below average[/red]"
                strength_table.add_row(
                    "SPY Volume",
                    f"{vol_millions:.1f}M",
                    f"{vol_status} ({vol_ratio:.1f}x avg)"
                )

        # Get VIX from regime info (already calculated)
        vix = regime_info.get('vix', 0)
        if vix:
            vix_color = "green" if vix < 15 else "yellow" if vix < 20 else "red"
            vix_status = "Low fear" if vix < 15 else "Moderate fear" if vix < 20 else "High fear" if vix < 30 else "Extreme fear"
            strength_table.add_row(
                "VIX (Fear Index)",
                f"{vix:.2f}",
                f"[{vix_color}]{vix_status}[/{vix_color}]"
            )

        # Market breadth - % of stocks above 50 SMA
        breadth = db.conn.execute("""
            WITH latest AS (
                SELECT
                    sp.symbol,
                    sp.close,
                    ti.sma_50
                FROM stock_prices sp
                LEFT JOIN technical_indicators ti
                    ON sp.symbol = ti.symbol
                    AND sp.timestamp = ti.timestamp
                WHERE sp.symbol IN (SELECT symbol FROM ticker_metadata WHERE category IN ('Index', 'Sector ETF'))
                AND sp.timestamp = (SELECT MAX(timestamp) FROM stock_prices WHERE symbol = sp.symbol)
            )
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN close > sma_50 THEN 1 ELSE 0 END) as above_sma
            FROM latest
            WHERE sma_50 IS NOT NULL
        """).fetchone()

        if breadth and breadth[0] > 0:
            total_stocks = breadth[0]
            above_sma = breadth[1] or 0
            breadth_pct = (above_sma / total_stocks) * 100
            breadth_color = "green" if breadth_pct > 70 else "yellow" if breadth_pct > 50 else "red"
            breadth_status = "Strong" if breadth_pct > 70 else "Neutral" if breadth_pct > 50 else "Weak"
            strength_table.add_row(
                "Market Breadth",
                f"{breadth_pct:.1f}%",
                f"[{breadth_color}]{breadth_status}[/{breadth_color}] ({int(above_sma)}/{total_stocks} stocks)"
            )

        console.print(strength_table)
        console.print()

        # Determine overall market condition
        spy_signal = market_status.get("SPY", {}).get("signal", TradingSignal.DONT_TRADE)
        qqq_signal = market_status.get("QQQ", {}).get("signal", TradingSignal.DONT_TRADE)

        if spy_signal == TradingSignal.BUY and qqq_signal == TradingSignal.BUY:
            console.print(Panel(">> [bold green]BULLISH[/bold green] - Good time to buy stocks", border_style="green"))
        elif spy_signal == TradingSignal.SELL or qqq_signal == TradingSignal.SELL:
            console.print(Panel(">> [bold red]BEARISH[/bold red] - Avoid new buys, consider taking profits", border_style="red"))
        else:
            console.print(Panel(">> [bold yellow]NEUTRAL[/bold yellow] - Be selective with new positions", border_style="yellow"))

    # MARKET REGIME (NEW!)
    console.print("\n[bold bright_white]>> MARKET REGIME & STRATEGY PARAMETERS[/bold bright_white]", style="on blue")

    # regime_detector and regime_info already initialized above in MARKET DIRECTION section
    regime_color = regime_detector.get_regime_color(regime_info["regime"])
    avoid_trading = regime_detector.should_avoid_new_positions(regime_info["regime"], regime_info["vix"])

    regime_table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
    regime_table.add_column("Metric", style="bold white")
    regime_table.add_column("Value", style="bright_white")
    regime_table.add_column("Recommendation", style="yellow")

    regime_table.add_row(
        "Market Regime",
        f"[{regime_color}]{regime_info['regime'].value}[/{regime_color}]",
        regime_info["reasoning"]
    )
    # Safe division for SPY vs SMA200
    spy_vs_sma = "N/A"
    if regime_info['spy_sma_200'] and regime_info['spy_sma_200'] > 0:
        spy_vs_sma = f"{((regime_info['spy_price'] - regime_info['spy_sma_200']) / regime_info['spy_sma_200'] * 100):+.1f}%"

    regime_table.add_row(
        "SPY vs 200 SMA",
        f"${regime_info['spy_price']:.2f} vs ${regime_info['spy_sma_200']:.2f}",
        spy_vs_sma
    )
    regime_table.add_row(
        "VIX Level",
        f"{regime_info['vix']:.1f}",
        "Low volatility" if regime_info['vix'] < 20 else "High volatility" if regime_info['vix'] > 25 else "Moderate volatility"
    )
    regime_table.add_row(
        "Min Confidence",
        f"{regime_info['confidence_threshold']:.0%}",
        "Higher threshold = more selective" if regime_info['confidence_threshold'] > 0.75 else "Standard threshold"
    )
    regime_table.add_row(
        "Max Leverage",
        f"{regime_info['max_leverage']:.1f}x",
        "Conservative" if regime_info['max_leverage'] < 2.0 else "Aggressive"
    )
    regime_table.add_row(
        "Position Sizing",
        regime_info["position_sizing"],
        ""
    )

    console.print(regime_table)

    if avoid_trading:
        console.print(Panel(
            "[bold red]⚠️  EXTREME CONDITIONS - AVOID NEW POSITIONS[/bold red]\n"
            "Current market environment is too risky for new long entries.\n"
            "Consider cash preservation or wait for regime change.",
            border_style="red",
            title="[bold]Trading Alert[/bold]"
        ))

    # FINANCIAL CALENDAR - Upcoming Events
    console.print("\n[bold bright_white]>> UPCOMING MARKET EVENTS (14 Days)[/bold bright_white]", style="on blue")

    upcoming_events = FinancialCalendar.get_upcoming_events(days_ahead=14)

    if upcoming_events:
        calendar_table = Table(show_header=True, header_style="bold yellow", box=box.ROUNDED)
        calendar_table.add_column("Date", style="bold white")
        calendar_table.add_column("Days", justify="right", style="cyan")
        calendar_table.add_column("Event", style="bright_white")
        calendar_table.add_column("Impact", justify="center")
        calendar_table.add_column("Trading Recommendation", style="yellow")

        for event in upcoming_events:
            # Color code by impact
            if event["impact"] == EventImpact.EXTREME:
                impact_color = "bold red"
                impact_text = "🔴 EXTREME"
            elif event["impact"] == EventImpact.HIGH:
                impact_color = "red"
                impact_text = "🟠 HIGH"
            elif event["impact"] == EventImpact.MEDIUM:
                impact_color = "yellow"
                impact_text = "🟡 MEDIUM"
            else:
                impact_color = "green"
                impact_text = "🟢 LOW"

            # Trading rec
            if event["impact"] == EventImpact.EXTREME:
                rec = "AVOID ALL TRADING"
            elif event["impact"] == EventImpact.HIGH:
                rec = "Avoid new positions"
            elif event["impact"] == EventImpact.MEDIUM:
                rec = "Be cautious"
            else:
                rec = "Monitor only"

            calendar_table.add_row(
                event["date"].strftime("%Y-%m-%d (%a)"),
                f"{event['days_until']} days",
                event["name"],
                f"[{impact_color}]{impact_text}[/{impact_color}]",
                rec
            )

        console.print(calendar_table)

        # Check if today has event proximity risk
        event_check = FinancialCalendar.check_event_proximity(
            target_date=datetime.now().date(),
            lookback_days=1,
            lookahead_days=0
        )

        if event_check["has_event"]:
            console.print(Panel(
                f"[bold red]⚠️  {event_check['event_type'].value} IN {abs(event_check['days_until'])} DAY(S)[/bold red]\n"
                f"{event_check['recommendation']}\n"
                f"Event Date: {event_check['event_date'].strftime('%Y-%m-%d')}\n"
                f"Confidence Penalty: {event_check['confidence_adjustment']:.0%}",
                border_style="red",
                title="[bold]Calendar Risk Alert[/bold]"
            ))
    else:
        console.print("[dim]No major market events in next 14 days[/dim]")

    # Section 1: PORTFOLIO STATUS
    print("=" * 100)
    print("SECTION 1: YOUR HOLDINGS - Status from Yesterday's Close")
    print("=" * 100)
    print()

    if portfolio.positions:
        print(f"{'Ticker':<8} {'Qty':<6} {'Cost':<10} {'Close':<10} {'P&L':<12} {'Signal':<12} {'Date':<12} {'Status':<15}")
        print("-" * 110)

        watch_today = []
        consider_selling = []

        for ticker, pos in sorted(portfolio.positions.items()):
            close_price, close_date = get_yesterday_close(ticker, db)

            if close_price and close_date:
                signal = detector.generate_signal(ticker, close_date, close_price)

                position_value = pos.quantity * close_price
                gain = position_value - (pos.quantity * pos.price_paid)
                gain_pct = (gain / (pos.quantity * pos.price_paid)) * 100

                # Format date
                if isinstance(close_date, date_type):
                    signal_date = close_date.strftime("%Y-%m-%d")
                else:
                    signal_date = close_date.date().strftime("%Y-%m-%d")

                status = "HOLD"
                if signal.signal == TradingSignal.SELL:
                    status = "SELL TODAY?"
                    consider_selling.append((ticker, signal_date))
                elif gain_pct < -5:
                    status = "WATCH (down)"
                    watch_today.append(ticker)
                elif gain_pct > 10:
                    status = "WINNING"

                print(
                    f"{ticker:<8} "
                    f"{pos.quantity:<6} "
                    f"${pos.price_paid:<9.2f} "
                    f"${close_price:<9.2f} "
                    f"${gain:>7.2f} ({gain_pct:>5.1f}%) "
                    f"{signal.signal.value:<12} "
                    f"{signal_date:<12} "
                    f"{status:<15}"
                )
            else:
                print(f"{ticker:<8} {pos.quantity:<6} NO DATA")

        print()

        if consider_selling:
            print(f"! SELL SIGNALS: {len(consider_selling)} stocks to review today")
            for ticker, signal_date in consider_selling:
                print(f"  - {ticker}: Signal appeared on {signal_date} - Check at 3 PM if persists")
            print()

        if watch_today:
            print(f"! WATCH LIST: {len(watch_today)} stocks with losses")
            for ticker in watch_today:
                print(f"  - {ticker}: Monitor for stop loss triggers")
            print()

        if not consider_selling and not watch_today:
            print("OK Portfolio looks good - all holdings stable")
            print()
    else:
        print("No holdings in portfolio")
        print("Run: .\\tasks.ps1 import-portfolio\n")

    # Section 2: WATCHLIST SIGNALS
    console.print("\n[bold bright_white]>> WATCHLIST - New Opportunities[/bold bright_white]", style="on blue")

    buy_candidates = []

    # Check watchlist stocks
    watchlist_tickers = [t.symbol for t in TIER_2_STOCKS[:20]]

    for ticker in sorted(watchlist_tickers):
        # Skip if we already own
        if ticker in portfolio.positions:
            continue

        close_price, close_date = get_yesterday_close(ticker, db)

        if close_price and close_date:
            signal = detector.generate_signal(ticker, close_date, close_price)

            # Format date
            if isinstance(close_date, date_type):
                signal_date = close_date.strftime("%Y-%m-%d")
            else:
                signal_date = close_date.date().strftime("%Y-%m-%d")

            if signal.signal == TradingSignal.BUY:
                # Calculate risk/reward
                rr_data = calculate_risk_reward(ticker, close_price, db)
                rr_ratio = rr_data.get("risk_reward_ratio", 0) or 0
                upside = rr_data.get("upside_pct", 0) or 0
                downside = rr_data.get("downside_pct", 0) or 0
                support = rr_data.get("support", close_price * 0.95)
                resistance = rr_data.get("resistance", close_price * 1.05)

                # NEW: Check earnings proximity
                days_until_earnings = signal.days_until_earnings if hasattr(signal, 'days_until_earnings') else None
                earnings_check = EarningsFilter.check_earnings_proximity(days_until_earnings)

                # NEW: Score entry quality
                entry_quality = EntryQualityScorer.score_entry(close_price, support, resistance)

                # NEW: Calculate Relative Strength vs SPY
                rs_analyzer = RelativeStrengthAnalyzer(db)
                rs_data = rs_analyzer.calculate_relative_strength(ticker, benchmark="SPY", days=60, date=close_date)

                # Check calendar event proximity
                calendar_check = FinancialCalendar.check_event_proximity(
                    target_date=close_date if isinstance(close_date, date_type) else close_date.date(),
                    lookback_days=1,
                    lookahead_days=0
                )

                # Adjust confidence with all factors
                adjusted_confidence = signal.confidence
                adjusted_confidence += earnings_check["confidence_adjustment"]
                adjusted_confidence += entry_quality["confidence_adjustment"]
                adjusted_confidence += rs_data["confidence_adjustment"]
                adjusted_confidence += calendar_check["confidence_adjustment"]  # Calendar events

                # Clamp between 0 and 1
                adjusted_confidence = max(0.0, min(1.0, adjusted_confidence))

                # Skip if RS is very weak (severe underperformance)
                if rs_data["strength"] in ["VERY_WEAK", "WEAK"]:
                    continue  # Don't trade stocks badly lagging the market

                # Combined score: adjusted_confidence × risk/reward ratio
                # Cap R/R at 5 to avoid extreme outliers
                capped_rr = min(rr_ratio, 5.0)
                score = adjusted_confidence * capped_rr

                # Skip if earnings blocks the trade
                if earnings_check["action"] == "BLOCK":
                    continue

                buy_candidates.append({
                    "ticker": ticker,
                    "price": close_price,
                    "confidence": signal.confidence,
                    "adjusted_confidence": adjusted_confidence,
                    "reasoning": signal.reasoning,
                    "signal_date": signal_date,
                    "rr_ratio": rr_ratio,
                    "upside": upside,
                    "downside": downside,
                    "score": score,
                    "entry_quality": entry_quality["quality"],
                    "earnings_action": earnings_check["action"],
                    "earnings_window": EarningsFilter.get_earnings_window_description(days_until_earnings),
                    "rs_strength": rs_data["strength"],
                    "rs_ratio": rs_data["rs_ratio"],
                    "ticker_return": rs_data["ticker_return"],
                    "spy_return": rs_data["benchmark_return"],
                    "calendar_event": calendar_check["event_type"].value if calendar_check["has_event"] else None,
                    "calendar_impact": calendar_check["impact"].value if calendar_check["has_event"] else None,
                    # Confidence breakdown for debugging
                    "conf_breakdown": {
                        "base": signal.confidence,
                        "earnings_adj": earnings_check["confidence_adjustment"],
                        "entry_adj": entry_quality["confidence_adjustment"],
                        "rs_adj": rs_data["confidence_adjustment"],
                        "calendar_adj": calendar_check["confidence_adjustment"],
                    }
                })

    # Rank by score (highest first)
    buy_candidates.sort(key=lambda x: x["score"], reverse=True)

    # Save morning signals (buy candidates + holdings) to temp log for intraday tracking
    temp_log_path = Path(__file__).parent.parent / "data" / "morning_signals.json"
    temp_log_path.parent.mkdir(exist_ok=True)

    # Build holdings signals
    holdings_signals = []
    for ticker, pos in sorted(portfolio.positions.items()):
        close_price, close_date = get_yesterday_close(ticker, db)
        if close_price and close_date:
            signal = detector.generate_signal(ticker, close_date, close_price)
            if isinstance(close_date, date_type):
                signal_date = close_date.strftime("%Y-%m-%d")
            else:
                signal_date = close_date.date().strftime("%Y-%m-%d")

            holdings_signals.append({
                "ticker": ticker,
                "signal": signal.signal.value,
                "signal_date": signal_date,
                "price": close_price,
                "confidence": signal.confidence,
            })

    morning_log = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "time": datetime.now().strftime("%H:%M:%S"),
        "buy_candidates": [
            {
                "ticker": c["ticker"],
                "price": c["price"],
                "confidence": c["confidence"],
                "adjusted_confidence": c["adjusted_confidence"],
                "score": c["score"],
                "rr_ratio": c.get("rr_ratio"),
                "entry_quality": c.get("entry_quality"),
                "rs_strength": c.get("rs_strength"),
                "upside": c.get("upside"),
                "downside": c.get("downside"),
            }
            for c in buy_candidates
        ],
        "holdings": holdings_signals
    }

    with open(temp_log_path, "w") as f:
        json.dump(morning_log, f, indent=2)

    if buy_candidates:
        console.print("\n[bold cyan]TOP BUY OPPORTUNITIES (Ranked by Adjusted Score)[/bold cyan]")

        for i, candidate in enumerate(buy_candidates[:10], 1):  # Show top 10
            rr_display = f"{candidate['rr_ratio']:.1f}" if candidate['rr_ratio'] else "N/A"

            # Color code entry quality
            quality_colors = {
                "EXCELLENT": "bold green",
                "GOOD": "green",
                "FAIR": "yellow",
                "POOR": "red"
            }
            quality_color = quality_colors.get(candidate['entry_quality'], "white")

            # Color code RS strength
            rs_colors = {
                "VERY_STRONG": "bold green",
                "STRONG": "green",
                "ABOVE_AVERAGE": "cyan",
                "NEUTRAL": "yellow",
                "WEAK": "orange",
                "VERY_WEAK": "red"
            }
            rs_color = rs_colors.get(candidate['rs_strength'], "white")

            console.print(f"\n[bold white]{i}. {candidate['ticker']}[/bold white] @ ${candidate['price']:.2f}")
            console.print(f"   Score: [bold cyan]{candidate['score']:.2f}[/bold cyan] | "
                         f"Conf: {candidate['confidence']:.0%} → [{quality_color}]{candidate['adjusted_confidence']:.0%}[/{quality_color}] | "
                         f"R/R: {rr_display}:1")

            # Confidence breakdown
            breakdown = candidate.get('conf_breakdown', {})
            if breakdown:
                console.print(f"   [dim]Confidence Details:[/dim]")
                console.print(f"      Base: {breakdown['base']:.0%}")

                if breakdown.get('earnings_adj', 0) != 0:
                    adj_color = "green" if breakdown['earnings_adj'] > 0 else "red"
                    console.print(f"      Earnings: [{adj_color}]{breakdown['earnings_adj']:+.0%}[/{adj_color}]")

                if breakdown.get('entry_adj', 0) != 0:
                    adj_color = "green" if breakdown['entry_adj'] > 0 else "red"
                    console.print(f"      Entry Quality: [{adj_color}]{breakdown['entry_adj']:+.0%}[/{adj_color}]")

                if breakdown.get('rs_adj', 0) != 0:
                    adj_color = "green" if breakdown['rs_adj'] > 0 else "red"
                    console.print(f"      Rel. Strength: [{adj_color}]{breakdown['rs_adj']:+.0%}[/{adj_color}]")

                if breakdown.get('calendar_adj', 0) != 0:
                    console.print(f"      [red]Calendar Event: {breakdown['calendar_adj']:+.0%}[/red]")

                console.print(f"      [bold]Total: {candidate['adjusted_confidence']:.0%}[/bold]")

            console.print(f"   Entry: [{quality_color}]{candidate['entry_quality']}[/{quality_color}] | "
                         f"Earnings: {candidate['earnings_window']}")
            console.print(f"   Relative Strength: [{rs_color}]{candidate['rs_strength']}[/{rs_color}] "
                         f"({candidate['ticker']} {candidate['ticker_return']:+.1%} vs SPY {candidate['spy_return']:+.1%})")

            # Position sizing recommendation
            if candidate['score'] >= 3.5:
                console.print(f"   [bold green]>> STRONG BUY:[/bold green] Consider 30-40% of available capital (2x leverage)")
            elif candidate['score'] >= 2.5:
                console.print(f"   [bold green]>> GOOD BUY:[/bold green] Consider 20-30% of available capital")
            elif candidate['score'] >= 1.5:
                console.print(f"   [yellow]>> WATCH:[/yellow] Wait for better entry or start small (10-15%)")
            else:
                console.print(f"   [yellow]>> CAUTION:[/yellow] Low score - monitor for confirmation")

            if candidate['earnings_action'] == "CAUTION":
                console.print(f"   [yellow]⚠️  Earnings proximity - reduce position size by 50%[/yellow]")
    else:
        print("No buy signals on watchlist - sit tight today")

    print()

    # NEW SECTION: PORTFOLIO OPTIMIZATION
    if portfolio.positions:
        console.print("\n[bold bright_white]>> PORTFOLIO OPTIMIZATION - Rebalancing Opportunities[/bold bright_white]", style="on blue")

        try:
            # Get current account balance
            balance = db.conn.execute("""
                SELECT cash_balance, portfolio_value, total_value,
                       margin_used, margin_available, buying_power
                FROM account_balance
                ORDER BY balance_date DESC
                LIMIT 1
            """).fetchone()

            if balance:
                cash, portfolio_val, total, margin_used, margin_avail, buying_power = balance
                cash = float(cash)
                total = float(total)
                margin_used = float(margin_used)
                margin_avail = float(margin_avail)

                # Initialize analyzers
                analyzer = PortfolioAnalyzer()
                sizer = PositionSizer(total, cash, margin_avail, margin_used)

                # Get portfolio health score
                health = analyzer.get_portfolio_health_score()

                # Display portfolio health
                health_table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
                health_table.add_column("Metric", style="bold white", width=20)
                health_table.add_column("Value", style="bright_white", width=15)
                health_table.add_column("Assessment", style="yellow", width=50)

                grade_color = "green" if health["grade"] in ["A", "B"] else "yellow" if health["grade"] == "C" else "red"
                health_table.add_row(
                    "Portfolio Health",
                    f"[{grade_color}]{health['grade']} ({health['score']:.0f}/100)[/{grade_color}]",
                    f"Average alpha: {health['avg_alpha']:+.1f}% vs SPY"
                )
                health_table.add_row(
                    "Signal Strength",
                    f"{health['avg_signal_strength']:.0f}/100",
                    f"{health['num_underperformers']}/{health['num_positions']} positions underperforming"
                )

                console.print(health_table)

                if health["issues"]:
                    console.print("\n[yellow]⚠️  Issues Detected:[/yellow]")
                    for issue in health["issues"]:
                        console.print(f"   • {issue}")

                # Generate swap recommendations
                watchlist_symbols = [t.symbol for t in TIER_2_STOCKS[:20]]
                swaps = analyzer.generate_swap_recommendations(watchlist_symbols, max_recommendations=3)

                if swaps:
                    console.print("\n[bold yellow]🔄 REBALANCING RECOMMENDATIONS[/bold yellow]")

                    for i, swap in enumerate(swaps, 1):
                        console.print(f"\n[bold white]Recommendation #{i}:[/bold white]")

                        # Create swap table
                        swap_table = Table(show_header=True, header_style="bold", box=box.SIMPLE)
                        swap_table.add_column("", style="bold", width=12)
                        swap_table.add_column("Symbol", width=8)
                        swap_table.add_column("Value/Price", justify="right", width=15)
                        swap_table.add_column("Signal", justify="center", width=15)
                        swap_table.add_column("Reason", width=45)

                        swap_table.add_row(
                            "[red]REDUCE[/red]",
                            f"[red]{swap['reduce_symbol']}[/red]",
                            f"[red]${swap['reduce_value']:,.2f}[/red]",
                            f"[red]{swap['reduce_strength']:.0f}/100[/red]",
                            f"[red]{swap['reduce_reason'][:43]}[/red]"
                        )
                        swap_table.add_row(
                            "[green]INCREASE[/green]",
                            f"[green]{swap['increase_symbol']}[/green]",
                            f"[green]${swap['increase_price']:.2f}[/green]",
                            f"[green]{swap['increase_strength']:.0f}/100[/green]",
                            f"[green]{swap['increase_reason'][:43]}[/green]"
                        )

                        console.print(swap_table)

                        # Calculate position size for new position
                        position_calc = sizer.calculate_position_size(
                            signal_strength=swap['increase_strength'],
                            risk_level=swap['risk_level'],
                            price=swap['increase_price'],
                            use_margin=False  # Conservative default
                        )

                        improvement_color = "green" if swap['expected_gain'] > 20 else "yellow"
                        console.print(f"\n   [cyan]Expected Improvement:[/cyan] [{improvement_color}]+{swap['expected_gain']:.0f} points[/{improvement_color}]")
                        console.print(f"   [cyan]Risk Level:[/cyan] {swap['risk_level']}")
                        console.print(f"   [cyan]Suggested Size:[/cyan] {position_calc['quantity']} shares (${position_calc['position_value']:,.2f}, {position_calc['allocation_pct']:.1f}% of portfolio)")

                        if position_calc['use_margin']:
                            console.print(f"   [yellow]⚠️  Uses Margin:[/yellow] ${position_calc['margin_needed']:,.2f}")

                        # Record this as a signal for tracking
                        with SignalTracker() as tracker:
                            tracker.record_signal(
                                symbol=swap['increase_symbol'],
                                signal_type="BUY",
                                signal_source="morning_check_rebalancing",
                                signal_strength=swap['increase_strength'],
                                confidence_level=swap['risk_level'],
                                price_at_signal=swap['increase_price'],
                                suggested_action="SWAP",
                                suggested_quantity=position_calc['quantity'],
                                suggested_allocation_pct=position_calc['allocation_pct'],
                                use_margin=position_calc['use_margin'],
                                margin_requirement=position_calc.get('margin_needed', 0),
                                risk_level=swap['risk_level'],
                                notes=f"Swap from {swap['reduce_symbol']} - {swap['increase_reason']}"
                            )
                else:
                    console.print("\n[green]✓ No rebalancing needed - portfolio is well optimized[/green]")

        except Exception as e:
            console.print(f"[red]Error analyzing portfolio: {e}[/red]")
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")

    print()

    # Section 3: MORNING SUMMARY
    console.print("\n[bold bright_white]>> TODAY'S GAME PLAN[/bold bright_white]", style="on blue")
    console.print()

    summary_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    summary_table.add_column("Category", style="bold cyan", width=20)
    summary_table.add_column("Count", style="bright_white", width=15)

    summary_table.add_row("Portfolio Holdings", f"{len(portfolio.positions)}")
    summary_table.add_row("  - Need attention", f"[yellow]{len(consider_selling) + len(watch_today)}[/yellow]")
    summary_table.add_row("  - Stable", f"[green]{len(portfolio.positions) - len(consider_selling) - len(watch_today)}[/green]")
    summary_table.add_row("", "")
    summary_table.add_row("Watchlist", "")
    summary_table.add_row("  - Buy candidates", f"[green]{len(buy_candidates)}[/green]")

    console.print(summary_table)
    console.print()

    console.print("[bold yellow]ACTIONS FOR TODAY:[/bold yellow]")
    console.print("[dim]" + "─" * 80 + "[/dim]")

    if consider_selling:
        console.print(f"\n[bold red]1. REVIEW SELL SIGNALS[/bold red] ([yellow]{len(consider_selling)} stocks[/yellow])")
        for ticker, signal_date in consider_selling:
            console.print(f"   • [red]{ticker}[/red]: Signal on {signal_date} - Check intraday at 3 PM")

    if buy_candidates:
        console.print(f"\n[bold green]2. TOP BUY CANDIDATES[/bold green] ([cyan]Ranked by Score - {len(buy_candidates)} total[/cyan])")
        for i, candidate in enumerate(buy_candidates[:5], 1):  # Top 5
            console.print(f"\n   [bold white]#{i} {candidate['ticker']}[/bold white] - Score: [bold cyan]{candidate['score']:.2f}[/bold cyan]")
            console.print(f"      Price: [bright_white]${candidate['price']:.2f}[/bright_white] | "
                         f"Confidence: {candidate['confidence']:.0%} | R/R: {candidate['rr_ratio']:.1f}")
            console.print(f"      Upside: [green]+{candidate['upside']:.1f}%[/green] | "
                         f"Risk: [red]-{candidate['downside']:.1f}%[/red]")
            console.print(f"      Signal: [dim]{candidate['signal_date']}[/dim] - {candidate['reasoning'][:60]}")

            # Position sizing recommendation based on score
            if candidate['score'] >= 3.0:
                console.print(f"      [bold green]→ STRONG BUY:[/bold green] Consider 30-40% of available capital")
            elif candidate['score'] >= 2.0:
                console.print(f"      [green]→ GOOD BUY:[/green] Consider 20-30% of available capital")
            else:
                console.print(f"      [yellow]→ WATCH:[/yellow] Wait for better setup or start small (10-15%)")

    if watch_today:
        console.print(f"\n[bold yellow]3. MONITOR LOSERS[/bold yellow] ([yellow]{len(watch_today)} stocks[/yellow])")
        for ticker in watch_today:
            console.print(f"   • [yellow]{ticker}[/yellow]: Watch for further weakness or reversal")

    if not consider_selling and not buy_candidates and not watch_today:
        console.print("\n[bold green]! NO IMMEDIATE ACTION NEEDED[/bold green]")
        console.print("  [dim]- Portfolio is stable[/dim]")
        console.print("  [dim]- No strong buy signals[/dim]")
        console.print("  [dim]- Check again at 3 PM for intraday opportunities[/dim]")

    console.print()
    console.print("[bold cyan]NEXT STEPS:[/bold cyan]")
    console.print("[dim]" + "─" * 80 + "[/dim]")
    console.print()
    console.print("[bold white]1.[/bold white] [cyan]Morning (now):[/cyan] Review this report")
    console.print("[bold white]2.[/bold white] [cyan]12 PM - 1 PM:[/cyan] Quick check - any big moves?")
    console.print("[bold white]3.[/bold white] [cyan]3 PM:[/cyan] Final decision")
    console.print("   [dim].\\tasks.ps1 intraday[/dim]")
    console.print("[bold white]4.[/bold white] [cyan]After hours:[/cyan] Update portfolio")
    console.print("   [dim].\\tasks.ps1 update-daily[/dim]")
    console.print()
    console.print(f"[dim]Report generated: {datetime.now().strftime('%I:%M %p ET')}[/dim]")
    console.print(f"[dim]Data: Yesterday's closing prices[/dim]")
    console.print("[dim]" + "=" * 80 + "[/dim]")
    console.print()


if __name__ == "__main__":
    main()
