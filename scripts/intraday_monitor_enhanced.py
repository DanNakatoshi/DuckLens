"""
Intraday Monitor (Enhanced) - Real-time stock analysis for 3 PM trading decisions.

Shows:
- Morning BUY signals with updated intraday stats
- Current holdings sell check
- New buy opportunities that emerged today
- Rich formatted with colors and tables

Uses Polygon.io's 15-minute delayed free tier data.
"""

import sys
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from src.config.tickers import TIER_2_STOCKS
from src.data.collectors.polygon_collector import PolygonCollector
from src.data.storage.market_data_db import MarketDataDB
from src.models.enhanced_detector import EnhancedTrendDetector
from src.models.earnings_filter import EarningsFilter
from src.models.entry_quality import EntryQualityScorer
from src.models.market_regime import RegimeDetector
from src.models.relative_strength import RelativeStrengthAnalyzer
from src.models.trend_detector import TradingSignal
from src.portfolio.portfolio_manager import PortfolioManager
from src.analysis.portfolio_analyzer import PortfolioAnalyzer
from src.allocation.position_sizer import PositionSizer
from src.tracking.signal_tracker import SignalTracker
from rich import box

load_dotenv()
console = Console()


def get_intraday_snapshot(ticker: str, collector: PolygonCollector) -> dict:
    """Get current intraday price snapshot (15-min delayed)."""
    try:
        url = f"/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}"
        response = collector.client.get(url)
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "OK" or not data.get("ticker"):
            return None

        ticker_data = data["ticker"]
        if not ticker_data.get("day") or not ticker_data.get("prevDay"):
            return None

        day_data = ticker_data["day"]
        prev_day_data = ticker_data["prevDay"]

        current_price = float(day_data["c"])
        open_price = float(day_data["o"])
        high = float(day_data["h"])
        low = float(day_data["l"])
        volume = int(day_data["v"])
        prev_close = float(prev_day_data["c"])

        change_from_close = float(ticker_data.get("todaysChangePerc", ((current_price / prev_close) - 1) * 100))
        change_from_open = ((current_price / open_price) - 1) * 100 if open_price > 0 else 0

        return {
            "ticker": ticker,
            "current": current_price,
            "open": open_price,
            "high": high,
            "low": low,
            "prev_close": prev_close,
            "volume": volume,
            "change_from_close": change_from_close,
            "change_from_open": change_from_open,
            "timestamp": datetime.now(),
        }
    except Exception as e:
        console.print(f"[red]ERROR {ticker}: {e}[/red]")
        return None


def get_morning_buy_candidates(db: MarketDataDB, detector: EnhancedTrendDetector) -> dict:
    """Get tickers with BUY signals from this morning's saved log."""
    today = datetime.now().date()

    # Read from morning signals JSON log
    temp_log_path = Path(__file__).parent.parent / "data" / "morning_signals.json"

    try:
        if not temp_log_path.exists():
            console.print(f"[dim]No morning signals log found at {temp_log_path}[/dim]")
            return {}

        with open(temp_log_path, "r") as f:
            morning_log = json.load(f)

        # Check if log is from today
        log_date = datetime.strptime(morning_log["date"], "%Y-%m-%d").date()

        if log_date != today:
            console.print(f"[yellow]Morning signals log is from {log_date}, not today ({today})[/yellow]")
            console.print("[dim]Run morning check first: .\\tasks.ps1 morning[/dim]")
            return {}

        # Return dict with ticker -> morning_data mapping
        return {
            c["ticker"]: c
            for c in morning_log["buy_candidates"]
        }

    except Exception as e:
        console.print(f"[red]Error reading morning signals: {e}[/red]")
        return {}


def analyze_with_all_factors(
    ticker: str,
    current_price: float,
    db: MarketDataDB,
    detector: EnhancedTrendDetector,
    rs_analyzer: RelativeStrengthAnalyzer,
) -> dict:
    """Run full analysis with all Phase 1 improvements."""
    today = datetime.now()

    # Get base signal
    signal = detector.generate_signal(ticker, today, current_price)

    # Get all enhancement factors
    # Relative Strength
    rs_data = rs_analyzer.calculate_relative_strength(ticker, "SPY", 60, today)

    # Entry Quality (calculate support/resistance from recent price action)
    # Use 20-day high/low as resistance/support
    query = """
        SELECT MAX(high) as resistance, MIN(low) as support
        FROM stock_prices
        WHERE symbol = ?
        AND timestamp >= CURRENT_DATE - INTERVAL 20 DAYS
    """
    result = db.conn.execute(query, [ticker]).fetchone()

    if result and result[0] and result[1]:
        resistance, support = float(result[0]), float(result[1])
        entry_quality = EntryQualityScorer.score_entry(current_price, support, resistance)
    else:
        entry_quality = {"quality": "UNKNOWN", "confidence_adjustment": 0.0, "reasoning": "No price data"}

    # Earnings proximity
    try:
        query_earnings = """
            SELECT earnings_date
            FROM earnings
            WHERE symbol = ?
            AND earnings_date >= ?
            ORDER BY earnings_date
            LIMIT 1
        """
        earnings_result = db.conn.execute(query_earnings, [ticker, today]).fetchone()

        if earnings_result:
            earnings_date = datetime.strptime(earnings_result[0], "%Y-%m-%d")
            days_until = (earnings_date - today).days
        else:
            days_until = None
    except Exception:
        # Earnings table doesn't exist or other error
        days_until = None

    earnings_check = EarningsFilter.check_earnings_proximity(days_until)

    # Adjust confidence
    adjusted_conf = signal.confidence
    adjusted_conf += rs_data.get("confidence_adjustment", 0.0)
    adjusted_conf += entry_quality.get("confidence_adjustment", 0.0)
    adjusted_conf += earnings_check.get("confidence_adjustment", 0.0)
    adjusted_conf = max(0.0, min(1.0, adjusted_conf))

    return {
        "signal": signal.signal.value,
        "base_confidence": signal.confidence,
        "adjusted_confidence": adjusted_conf,
        "rs_strength": rs_data.get("strength", "UNKNOWN"),
        "rs_ratio": rs_data.get("rs_ratio", 0.0),
        "entry_quality": entry_quality.get("quality", "UNKNOWN"),
        "earnings_action": earnings_check.get("action", "ALLOW"),
        "days_until_earnings": days_until,
    }


def main():
    """Main entry point - Enhanced 3 PM decision tool."""

    current_time = datetime.now()

    # Header
    console.print()
    console.print(Panel.fit(
        f"[bold cyan]INTRADAY MONITOR - 3 PM TRADING DECISION[/bold cyan]\n"
        f"[yellow]Time: {current_time.strftime('%Y-%m-%d %I:%M %p ET')}[/yellow]\n"
        f"Data: 15-minute delayed (Polygon.io)",
        border_style="cyan"
    ))
    console.print()

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
    rs_analyzer = RelativeStrengthAnalyzer(db)
    regime_detector = RegimeDetector(db)

    # Get market regime
    regime_info = regime_detector.detect_regime()

    console.print(f"[bold]MARKET REGIME:[/bold] {regime_info['regime'].value}")
    console.print(f"Confidence Threshold: {regime_info['confidence_threshold']:.0%} | Max Leverage: {regime_info['max_leverage']:.1f}x")
    console.print()

    # Section -1: ACCOUNT BALANCE
    console.print("\n[bold bright_white]>> ACCOUNT SUMMARY[/bold bright_white]", style="on blue")
    console.print()

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

            balance_table = Table(show_header=True, header_style="bold cyan")
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

    console.print()

    # Section 0: MARKET DIRECTION
    console.print("\n[bold bright_white]>> MARKET DIRECTION[/bold bright_white]", style="on blue")
    console.print()

    market_table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
    market_table.add_column("Index", style="bold white", width=8)
    market_table.add_column("Price", justify="right", style="bright_white", width=12)
    market_table.add_column("Today %", justify="right", width=12)
    market_table.add_column("Signal", width=12)
    market_table.add_column("Confidence", justify="right", width=12)
    market_table.add_column("Trend", width=50)

    with PolygonCollector() as collector:
        for index_ticker in ["SPY", "QQQ"]:
            snapshot = get_intraday_snapshot(index_ticker, collector)
            if snapshot:
                signal = detector.generate_signal(index_ticker, datetime.now(), snapshot["current"])

                # Color code the change
                change_pct = snapshot["change_from_close"]
                if change_pct > 0:
                    change_color = "green"
                    change_str = f"+{change_pct:.2f}%"
                else:
                    change_color = "red"
                    change_str = f"{change_pct:.2f}%"

                # Color code signal
                if signal.signal == TradingSignal.BUY:
                    signal_text = f"[bold green]{signal.signal.value}[/bold green]"
                elif signal.signal == TradingSignal.SELL:
                    signal_text = f"[bold red]{signal.signal.value}[/bold red]"
                else:
                    signal_text = f"[yellow]{signal.signal.value}[/yellow]"

                market_table.add_row(
                    index_ticker,
                    f"${snapshot['current']:.2f}",
                    f"[{change_color}]{change_str}[/{change_color}]",
                    signal_text,
                    f"{signal.confidence:.0%}",
                    signal.reasoning[:48] if hasattr(signal, 'reasoning') else ""
                )

    console.print(market_table)

    # Add market strength indicators (matching morning check)
    console.print()
    strength_table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
    strength_table.add_column("Indicator", style="bold white", width=25)
    strength_table.add_column("Value", justify="right", style="bright_white", width=15)
    strength_table.add_column("Status", width=30)

    # Get real-time SPY volume
    with PolygonCollector() as collector:
        spy_snapshot = get_intraday_snapshot("SPY", collector)
        if spy_snapshot and spy_snapshot.get("volume"):
            vol_millions = spy_snapshot["volume"] / 1_000_000
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
                    "SPY Volume (Today)",
                    f"{vol_millions:.1f}M",
                    f"{vol_status} ({vol_ratio:.1f}x avg)"
                )

    # Get VIX from regime info
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

    # Market condition panel
    # Determine from the snapshots we already fetched
    spy_signal = None
    qqq_signal = None
    with PolygonCollector() as collector:
        spy_snap = get_intraday_snapshot("SPY", collector)
        qqq_snap = get_intraday_snapshot("QQQ", collector)
        if spy_snap:
            spy_signal = detector.generate_signal("SPY", datetime.now(), spy_snap["current"]).signal
        if qqq_snap:
            qqq_signal = detector.generate_signal("QQQ", datetime.now(), qqq_snap["current"]).signal

    if spy_signal == TradingSignal.BUY and qqq_signal == TradingSignal.BUY:
        console.print(Panel(">> [bold green]BULLISH[/bold green] - Good time to buy stocks", border_style="green"))
    elif spy_signal == TradingSignal.SELL or qqq_signal == TradingSignal.SELL:
        console.print(Panel(">> [bold red]BEARISH[/bold red] - Avoid new buys, consider taking profits", border_style="red"))
    else:
        console.print(Panel(">> [bold yellow]NEUTRAL[/bold yellow] - Be selective with new positions", border_style="yellow"))

    console.print()

    # Section 1: MORNING BUY SIGNALS - Status Update
    console.print("\n[bold bright_white]>> MORNING BUY SIGNALS - Status Update[/bold bright_white]", style="on blue")
    console.print()

    morning_buys = get_morning_buy_candidates(db, detector)

    if morning_buys:
        tickers_list = ', '.join(morning_buys.keys())
        console.print(f"Found {len(morning_buys)} morning BUY signal(s): {tickers_list}")
        console.print()

        morning_table = Table(show_header=True, header_style="bold yellow", expand=True)
        morning_table.add_column("Ticker", style="bold", width=8)
        morning_table.add_column("Morning $", justify="right", width=10)
        morning_table.add_column("Now $", justify="right", width=10)
        morning_table.add_column("Change%", justify="right", width=10)
        morning_table.add_column("Intraday%", justify="right", width=10)
        morning_table.add_column("Signal", justify="center", width=12)
        morning_table.add_column("Conf", justify="right", width=8)
        morning_table.add_column("RS", justify="center", width=12)
        morning_table.add_column("Entry", justify="center", width=10)
        morning_table.add_column("Decision", style="bold", width=15)

        with PolygonCollector() as collector:
            for ticker, morning_data in sorted(morning_buys.items()):
                snapshot = get_intraday_snapshot(ticker, collector)

                if not snapshot:
                    morning_table.add_row(
                        ticker,
                        f"${morning_data['price']:.2f}",
                        "[red]NO DATA[/red]",
                        "", "", "", "", "", "", ""
                    )
                    continue

                # Analyze with all factors
                analysis = analyze_with_all_factors(
                    ticker, snapshot["current"], db, detector, rs_analyzer
                )

                # Color code changes
                change_close = snapshot["change_from_close"]
                change_open = snapshot["change_from_open"]

                close_color = "green" if change_close > 0 else "red"
                open_color = "green" if change_open > 0 else "red"

                close_str = f"[{close_color}]{change_close:+.1f}%[/{close_color}]"
                open_str = f"[{open_color}]{change_open:+.1f}%[/{open_color}]"

                # Signal status
                current_signal = analysis["signal"]
                if current_signal == "BUY":
                    signal_color = "green"
                    decision = "✓ STILL BUY"
                    decision_color = "bold green"
                else:
                    signal_color = "yellow"
                    decision = "⚠ SIGNAL LOST"
                    decision_color = "bold yellow"

                # RS color
                rs_strength = analysis["rs_strength"]
                if rs_strength in ["VERY_STRONG", "STRONG"]:
                    rs_color = "green"
                elif rs_strength in ["ABOVE_AVERAGE"]:
                    rs_color = "cyan"
                elif rs_strength == "NEUTRAL":
                    rs_color = "yellow"
                else:
                    rs_color = "red"

                # Entry color
                entry_q = analysis["entry_quality"]
                if entry_q in ["EXCELLENT", "GOOD"]:
                    entry_color = "green"
                elif entry_q == "FAIR":
                    entry_color = "yellow"
                else:
                    entry_color = "red"

                morning_table.add_row(
                    ticker,
                    f"${morning_data['price']:.2f}",
                    f"${snapshot['current']:.2f}",
                    close_str,
                    open_str,
                    f"[{signal_color}]{current_signal}[/{signal_color}]",
                    f"{analysis['adjusted_confidence']:.0%}",
                    f"[{rs_color}]{rs_strength}[/{rs_color}]",
                    f"[{entry_color}]{entry_q}[/{entry_color}]",
                    f"[{decision_color}]{decision}[/{decision_color}]"
                )

        console.print(morning_table)
    else:
        console.print("[dim]No morning BUY signals found (check trade_log)[/dim]")

    console.print()

    # Section 2: PORTFOLIO HOLDINGS
    console.print("\n[bold bright_white]>> YOUR HOLDINGS - Sell Check[/bold bright_white]", style="on blue")
    console.print()

    portfolio = portfolio_manager.load_portfolio()

    # Get morning holdings signals
    morning_holdings = {}
    if morning_buys:  # morning_buys is the full log
        temp_log_path = Path(__file__).parent.parent / "data" / "morning_signals.json"
        try:
            with open(temp_log_path, "r") as f:
                morning_log = json.load(f)
                morning_holdings = {
                    h["ticker"]: h
                    for h in morning_log.get("holdings", [])
                }
        except Exception:
            pass

    if portfolio.positions:
        holdings_table = Table(show_header=True, header_style="bold magenta")
        holdings_table.add_column("Ticker", style="bold", width=8)
        holdings_table.add_column("Price", justify="right", width=10)
        holdings_table.add_column("Change%", justify="right", width=10)
        holdings_table.add_column("Signal", justify="center", width=12)
        holdings_table.add_column("Since", justify="center", width=12)
        holdings_table.add_column("Action", style="bold", width=20)

        with PolygonCollector() as collector:
            for ticker in sorted(portfolio.positions.keys()):
                snapshot = get_intraday_snapshot(ticker, collector)

                if snapshot:
                    signal = detector.generate_signal(ticker, datetime.now(), snapshot["current"])

                    change_pct = snapshot["change_from_close"]
                    change_color = "green" if change_pct > 0 else "red"
                    change_str = f"[{change_color}]{change_pct:+.1f}%[/{change_color}]"

                    # Check morning signal
                    morning_signal = None
                    signal_date = "Today"
                    if ticker in morning_holdings:
                        morning_signal = morning_holdings[ticker]["signal"]
                        signal_date = morning_holdings[ticker].get("signal_date", "Unknown")

                    # Determine action with clear signal change tracking
                    current_signal = signal.signal.value
                    action = ""
                    signal_display = current_signal

                    # Check if signal changed from morning
                    if morning_signal and morning_signal != current_signal:
                        # Signal changed - highlight this
                        if current_signal == "SELL":
                            action = f"[bold red]⚠️ SIGNAL CHANGED: {morning_signal} → SELL - SELL NOW![/bold red]"
                            signal_display = f"[bold red]{current_signal}[/bold red]"
                        elif morning_signal == "SELL" and current_signal != "SELL":
                            action = f"[bold yellow]⚠️ SIGNAL CHANGED: SELL → {current_signal} - CAUTION![/bold yellow]"
                            signal_display = f"[yellow]{current_signal}[/yellow]"
                        else:
                            action = f"[yellow]Changed: {morning_signal} → {current_signal}[/yellow]"
                            signal_display = f"[yellow]{current_signal}[/yellow]"
                    else:
                        # Signal consistent
                        if current_signal == "SELL":
                            action = "[bold red]SELL NOW[/bold red]"
                            signal_display = f"[bold red]{current_signal}[/bold red]"
                        elif current_signal == "BUY":
                            action = "[green]HOLD (BUY signal)[/green]"
                            signal_display = f"[green]{current_signal}[/green]"
                        elif change_pct < -5:
                            action = "[yellow]⚠️ WATCH (down >5%)[/yellow]"
                            signal_display = f"[yellow]{current_signal}[/yellow]"
                        else:
                            action = "[dim]HOLD[/dim]"

                    holdings_table.add_row(
                        ticker,
                        f"${snapshot['current']:.2f}",
                        change_str,
                        signal_display,
                        signal_date,
                        action
                    )

        console.print(holdings_table)

        # Add explanation for signal changes
        console.print()
        console.print("[bold cyan]💡 Understanding Signal Changes:[/bold cyan]")
        console.print("[dim]Signals can change intraday based on:[/dim]")
        console.print("[dim]  • Price movement crossing key levels (SMA 20/50)[/dim]")
        console.print("[dim]  • MACD momentum shift[/dim]")
        console.print("[dim]  • Volume spikes indicating reversal[/dim]")
        console.print("[dim]  • RSI entering overbought/oversold territory[/dim]")
        console.print()
        console.print("[bold yellow]⚠️ If morning SELL → intraday HOLD/BUY:[/bold yellow]")
        console.print("[dim]  Price may have bounced, but use caution - original weakness still present[/dim]")
        console.print()
        console.print("[bold red]⚠️ If morning BUY/HOLD → intraday SELL:[/bold red]")
        console.print("[dim]  Trend weakened during the day - respect the new signal![/dim]")
    else:
        console.print("[dim]No holdings in portfolio[/dim]")

    console.print()

    # Section 3: NEW BUY OPPORTUNITIES
    console.print("\n[bold bright_white]>> NEW BUY OPPORTUNITIES (Today)[/bold bright_white]", style="on blue")
    console.print()

    new_buys = []

    with PolygonCollector() as collector:
        for ticker_obj in TIER_2_STOCKS:
            ticker = ticker_obj.symbol

            # Skip if already in morning buys or holdings
            if ticker in morning_buys or ticker in portfolio.positions:
                continue

            snapshot = get_intraday_snapshot(ticker, collector)
            if not snapshot:
                continue

            # Quick signal check
            signal = detector.generate_signal(ticker, datetime.now(), snapshot["current"])

            if signal.signal == TradingSignal.BUY:
                analysis = analyze_with_all_factors(
                    ticker, snapshot["current"], db, detector, rs_analyzer
                )

                # Filter out weak signals
                if analysis["earnings_action"] == "BLOCK":
                    continue
                if analysis["rs_strength"] in ["WEAK", "VERY_WEAK"]:
                    continue

                new_buys.append({
                    "ticker": ticker,
                    "snapshot": snapshot,
                    "analysis": analysis
                })

    if new_buys:
        console.print(f"[bold green]Found {len(new_buys)} NEW buy signal(s) today![/bold green]")
        console.print()

        new_table = Table(show_header=True, header_style="bold green")
        new_table.add_column("Ticker", style="bold")
        new_table.add_column("Price", justify="right")
        new_table.add_column("Change%", justify="right")
        new_table.add_column("Conf", justify="right")
        new_table.add_column("RS", justify="center")
        new_table.add_column("Entry", justify="center")

        for opp in sorted(new_buys, key=lambda x: x["analysis"]["adjusted_confidence"], reverse=True):
            ticker = opp["ticker"]
            snap = opp["snapshot"]
            analysis = opp["analysis"]

            change_pct = snap["change_from_close"]
            change_color = "green" if change_pct > 0 else "red"

            rs_strength = analysis["rs_strength"]
            rs_color = "green" if rs_strength in ["VERY_STRONG", "STRONG"] else "cyan"

            entry_q = analysis["entry_quality"]
            entry_color = "green" if entry_q in ["EXCELLENT", "GOOD"] else "yellow"

            new_table.add_row(
                ticker,
                f"${snap['current']:.2f}",
                f"[{change_color}]{change_pct:+.1f}%[/{change_color}]",
                f"{analysis['adjusted_confidence']:.0%}",
                f"[{rs_color}]{rs_strength}[/{rs_color}]",
                f"[{entry_color}]{entry_q}[/{entry_color}]"
            )

        console.print(new_table)
    else:
        console.print("[dim]No new buy signals today[/dim]")

    console.print()

    # PORTFOLIO REBALANCING ALERTS
    if portfolio.positions:
        console.print("\n[bold bright_white]>> PORTFOLIO REBALANCING ALERTS[/bold bright_white]", style="on blue")
        console.print()

        try:
            # Get current account balance
            balance = db.conn.execute("""
                SELECT cash_balance, portfolio_value, total_value,
                       margin_used, margin_available
                FROM account_balance
                ORDER BY balance_date DESC
                LIMIT 1
            """).fetchone()

            if balance:
                cash, portfolio_val, total, margin_used, margin_avail = balance
                cash = float(cash)
                total = float(total)
                margin_used = float(margin_used)
                margin_avail = float(margin_avail)

                # Initialize analyzers
                analyzer = PortfolioAnalyzer()

                # Check for underperformers (quick check)
                underperformers = analyzer.find_underperformers(min_alpha=-3.0, max_signal_strength=45)

                if underperformers:
                    console.print(f"[yellow]⚠️  {len(underperformers)} position(s) flagged for review:[/yellow]")
                    console.print()

                    alert_table = Table(show_header=True, header_style="bold yellow")
                    alert_table.add_column("Symbol", style="bold")
                    alert_table.add_column("Value", justify="right")
                    alert_table.add_column("Alpha", justify="right")
                    alert_table.add_column("Signal", justify="center")
                    alert_table.add_column("Action", style="yellow")

                    for u in underperformers[:5]:  # Top 5 worst
                        alpha_color = "red" if u["alpha"] < -5 else "yellow"
                        signal_color = "red" if u["signal_strength"] < 40 else "yellow"

                        alert_table.add_row(
                            u["symbol"],
                            f"${u['position_value']:,.2f}",
                            f"[{alpha_color}]{u['alpha']:+.1f}%[/{alpha_color}]",
                            f"[{signal_color}]{u['signal_strength']:.0f}/100[/{signal_color}]",
                            "Consider reducing"
                        )

                    console.print(alert_table)
                    console.print()
                    console.print("[dim]Review full optimization in morning check for swap recommendations[/dim]")
                else:
                    console.print("[green]✓ All positions performing well - no alerts[/green]")

                console.print()

        except Exception as e:
            console.print(f"[red]Error checking portfolio: {e}[/red]")
            console.print()

    # Final Summary
    console.print("\n[bold bright_white]>> FINAL DECISION[/bold bright_white]", style="on blue")
    console.print()

    if morning_buys:
        console.print(f"[bold yellow]→ Review {len(morning_buys)} morning BUY signal(s) above for status changes[/bold yellow]")

    if new_buys:
        console.print(f"[bold green]→ Consider {len(new_buys)} NEW buy opportunit(ies) that emerged today[/bold green]")

    if not morning_buys and not new_buys:
        console.print("[bold green]→ No action needed - hold current positions[/bold green]")

    console.print()
    console.print(f"[dim]Last updated: {current_time.strftime('%I:%M %p ET')} | Data: 15-min delayed (Polygon.io)[/dim]")
    console.print("[dim]" + "=" * 80 + "[/dim]")
    console.print()


if __name__ == "__main__":
    main()

