"""
Unified Market Check - Intelligent morning/intraday monitor.

Features:
- Auto-detects market status (pre-market, open, after-hours)
- Live price updates during market hours (refreshes every 1-5 min)
- Uses static data when market is closed
- Shares all common sections between morning and intraday
- 15-minute delayed live data from Polygon.io
"""

import sys
import time
from datetime import datetime, time as datetime_time, date as date_type
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from rich import box

from src.config.tickers import TIER_2_STOCKS
from src.data.collectors.polygon_collector import PolygonCollector
from src.data.storage.market_data_db import MarketDataDB
from src.models.enhanced_detector import EnhancedTrendDetector
from src.models.market_regime import RegimeDetector
from src.models.earnings_filter import EarningsFilter
from src.models.entry_quality import EntryQualityScorer
from src.models.relative_strength import RelativeStrengthAnalyzer
from src.models.financial_calendar import FinancialCalendar
from src.models.trend_detector import TradingSignal
from src.portfolio.portfolio_manager import PortfolioManager
from src.analysis.portfolio_analyzer import PortfolioAnalyzer
from src.allocation.position_sizer import PositionSizer
from src.tracking.signal_tracker import SignalTracker
from datetime import timedelta

load_dotenv()
console = Console()


class MarketStatus:
    """Detect current market status and trading hours."""

    @staticmethod
    def get_status() -> dict:
        """
        Get current market status.

        Returns:
            dict with:
            - is_open: bool
            - status: str (PRE_MARKET, MARKET_OPEN, AFTER_HOURS)
            - next_open: datetime
            - next_close: datetime
            - should_refresh: bool
        """
        now = datetime.now()
        current_time = now.time()

        # Market hours: 9:30 AM - 4:00 PM ET
        market_open = datetime_time(9, 30)
        market_close = datetime_time(16, 0)

        # Check if weekend
        is_weekend = now.weekday() >= 5  # Saturday = 5, Sunday = 6

        if is_weekend:
            return {
                "is_open": False,
                "status": "WEEKEND",
                "should_refresh": False,
                "data_source": "Last Friday's close",
            }

        # Check market hours
        if market_open <= current_time < market_close:
            return {
                "is_open": True,
                "status": "MARKET_OPEN",
                "should_refresh": True,
                "data_source": "Live prices (15-min delayed)",
            }
        elif current_time < market_open:
            return {
                "is_open": False,
                "status": "PRE_MARKET",
                "should_refresh": False,
                "data_source": "Yesterday's close",
            }
        else:
            return {
                "is_open": False,
                "status": "AFTER_HOURS",
                "should_refresh": False,
                "data_source": "Today's 4 PM close",
            }


def get_price_data(ticker: str, market_status: dict, db: MarketDataDB,
                   collector: Optional[PolygonCollector] = None) -> dict:
    """
    Get price data - live during market hours, historical otherwise.

    Args:
        ticker: Stock symbol
        market_status: Dict from MarketStatus.get_status()
        db: Database connection
        collector: Polygon collector (optional, for live data)

    Returns:
        dict with price, timestamp, is_live
    """
    if market_status["is_open"] and collector:
        # Get live data from Polygon
        try:
            url = f"/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}"
            response = collector.client.get(url)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "OK" and data.get("ticker"):
                ticker_data = data["ticker"]
                if ticker_data.get("day"):
                    day_data = ticker_data["day"]
                    prev_day = ticker_data.get("prevDay", {})

                    current_price = float(day_data["c"])
                    prev_close = float(prev_day.get("c", current_price))

                    # Use today's date at midnight for consistency with detector
                    from datetime import date
                    today_midnight = datetime.combine(date.today(), datetime.min.time())

                    return {
                        "price": current_price,
                        "prev_close": prev_close,
                        "change_pct": ((current_price - prev_close) / prev_close * 100) if prev_close > 0 else 0,
                        "volume": int(day_data.get("v", 0)),
                        "timestamp": today_midnight,
                        "is_live": True,
                    }
        except Exception:
            # Silently fall back to database
            pass

    # Fall back to database (historical)
    result = db.conn.execute("""
        SELECT close, timestamp, volume
        FROM stock_prices
        WHERE symbol = ?
        ORDER BY timestamp DESC
        LIMIT 2
    """, [ticker]).fetchall()

    if result and len(result) >= 2:
        current = result[0]
        previous = result[1]
        current_price = float(current[0])
        prev_price = float(previous[0])

        return {
            "price": current_price,
            "prev_close": prev_price,
            "change_pct": ((current_price - prev_price) / prev_price * 100) if prev_price > 0 else 0,
            "volume": int(current[2]) if current[2] else 0,
            "timestamp": current[1],
            "is_live": False,
        }

    return None


def build_live_sections(db, market_status, detector, portfolio, previous_signals=None, initial_watchlist=None):
    """Build sections that need live updates (prices, signals, watchlist).

    Args:
        db: Database connection
        market_status: Market status dict
        detector: Trend detector
        portfolio: Portfolio manager
        previous_signals: Previous signal states for change detection
        initial_watchlist: List of tickers from pre-open "New Opportunities" to track
    """
    from rich.console import Group
    from rich.text import Text

    sections = []
    current_time = datetime.now()
    current_signals = {}

    # Track initial watchlist if not provided
    if initial_watchlist is None:
        initial_watchlist = []

    # Header with timestamp
    status_color = "green" if market_status["is_open"] else "yellow"
    status_icon = "[LIVE]" if market_status["is_open"] else ""
    mode = "LIVE MODE" if market_status["is_open"] else "STATIC MODE"

    # Simple text header instead of Panel
    sections.append(Text(f"MARKET CHECK - {mode} {status_icon}", style=f"bold {status_color}"))
    sections.append(Text(f"Status: {market_status['status']}", style="dim"))
    sections.append(Text(f"Last Updated: {current_time.strftime('%I:%M:%S %p ET')} on {current_time.strftime('%Y-%m-%d')}", style="bold green"))
    sections.append(Text(f"Auto-refresh: Every 30s | Press Ctrl+C to stop", style="dim"))
    sections.append(Text(""))

    # Market indices with signal recalculation
    sections.append(Text(">> MARKET INDICES", style="bold white on blue"))
    sections.append(Text(""))
    indices_table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
    indices_table.add_column("Index", style="bold white", width=6)
    indices_table.add_column("Price", justify="right", style="bright_white", width=10)
    indices_table.add_column("Chg %", justify="right", width=10)
    indices_table.add_column("Signal", width=18)
    indices_table.add_column("Conf", justify="right", width=8)
    indices_table.add_column("Update", style="dim", width=18)

    collector = PolygonCollector() if market_status["is_open"] else None

    for symbol in ["SPY", "QQQ"]:
        price_data = get_price_data(symbol, market_status, db, collector)
        if price_data:
            current_price = price_data["price"]
            timestamp = price_data["timestamp"]

            prev_close = db.conn.execute("""
                SELECT close FROM stock_prices
                WHERE symbol = ? AND DATE(timestamp) = DATE(?) - INTERVAL '1 day'
                ORDER BY timestamp DESC LIMIT 1
            """, [symbol, timestamp]).fetchone()

            change_pct = 0
            if prev_close:
                prev = float(prev_close[0])
                change_pct = ((current_price - prev) / prev * 100) if prev > 0 else 0

            # Recalculate signal
            signal = detector.generate_signal(symbol, timestamp, current_price)
            current_signals[symbol] = signal.signal.value

            # Check for signal change
            signal_changed = ""
            if previous_signals and symbol in previous_signals:
                if previous_signals[symbol] != signal.signal.value:
                    signal_changed = f" [bold yellow]CHG[/bold yellow]"

            change_color = "green" if change_pct >= 0 else "red"
            signal_color = "green" if signal.signal.value == "BUY" else "red" if signal.signal.value == "SELL" else "yellow"
            update_status = "LIVE (15m delay)" if price_data["is_live"] else "Database"

            indices_table.add_row(
                symbol,
                f"${current_price:.2f}",
                f"[{change_color}]{change_pct:+.2f}%[/{change_color}]",
                f"[{signal_color}]{signal.signal.value}[/{signal_color}]{signal_changed}",
                f"{signal.confidence:.0%}",
                update_status
            )

    if collector:
        collector.client.close()

    sections.append(indices_table)
    sections.append(Text(""))

    # VIX Fear Index with Trend Analysis
    sections.append(Text(">> VIX FEAR INDEX - Hedging Alert", style="bold white on red"))
    sections.append(Text(""))

    vix_table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
    vix_table.add_column("Index", style="bold white", width=6)
    vix_table.add_column("Current", justify="right", style="bright_white", width=10)
    vix_table.add_column("Chg 1D", justify="right", width=10)
    vix_table.add_column("Chg 7D", justify="right", width=10)
    vix_table.add_column("Chg 14D", justify="right", width=10)
    vix_table.add_column("Status", width=25)
    vix_table.add_column("Action", width=30)

    # Get VIX data
    collector_vix = PolygonCollector() if market_status["is_open"] else None
    vix_data = get_price_data("VIX", market_status, db, collector_vix)

    if vix_data:
        vix_current = vix_data["price"]
        vix_timestamp = vix_data["timestamp"]

        # Get historical VIX values
        vix_1d = db.conn.execute("""
            SELECT close FROM stock_prices
            WHERE symbol = 'VIX' AND DATE(timestamp) = DATE(?) - INTERVAL '1 day'
            ORDER BY timestamp DESC LIMIT 1
        """, [vix_timestamp]).fetchone()

        vix_7d = db.conn.execute("""
            SELECT close FROM stock_prices
            WHERE symbol = 'VIX' AND DATE(timestamp) = DATE(?) - INTERVAL '7 days'
            ORDER BY timestamp DESC LIMIT 1
        """, [vix_timestamp]).fetchone()

        vix_14d = db.conn.execute("""
            SELECT close FROM stock_prices
            WHERE symbol = 'VIX' AND DATE(timestamp) = DATE(?) - INTERVAL '14 days'
            ORDER BY timestamp DESC LIMIT 1
        """, [vix_timestamp]).fetchone()

        # Calculate changes
        chg_1d = ((vix_current - float(vix_1d[0])) / float(vix_1d[0]) * 100) if vix_1d else 0
        chg_7d = ((vix_current - float(vix_7d[0])) / float(vix_7d[0]) * 100) if vix_7d else 0
        chg_14d = ((vix_current - float(vix_14d[0])) / float(vix_14d[0]) * 100) if vix_14d else 0

        # Determine status and action
        if vix_current >= 30:
            status = "[bold red]EXTREME FEAR[/bold red]"
            action = "[bold red]HEDGE NOW - Buy puts[/bold red]"
        elif vix_current >= 25:
            status = "[red]HIGH FEAR[/red]"
            action = "[red]Consider hedging[/red]"
        elif vix_current >= 20:
            status = "[yellow]ELEVATED FEAR[/yellow]"
            action = "[yellow]Watch closely[/yellow]"
        elif vix_current >= 15:
            status = "[green]NORMAL[/green]"
            action = "[green]No hedging needed[/green]"
        else:
            status = "[bright_green]LOW FEAR[/bright_green]"
            action = "[bright_green]Bullish environment[/bright_green]"

        # Alert on rapid VIX spike
        if chg_1d >= 15:
            action = "[bold red]⚠ SPIKE! HEDGE NOW[/bold red]"
        elif chg_7d >= 30:
            action = "[red]⚠ Rising fear - hedge soon[/red]"

        # Color coding for changes
        color_1d = "red" if chg_1d >= 10 else "yellow" if chg_1d >= 5 else "green"
        color_7d = "red" if chg_7d >= 20 else "yellow" if chg_7d >= 10 else "green"
        color_14d = "red" if chg_14d >= 30 else "yellow" if chg_14d >= 15 else "green"

        vix_table.add_row(
            "VIX",
            f"${vix_current:.2f}",
            f"[{color_1d}]{chg_1d:+.1f}%[/{color_1d}]",
            f"[{color_7d}]{chg_7d:+.1f}%[/{color_7d}]",
            f"[{color_14d}]{chg_14d:+.1f}%[/{color_14d}]",
            status,
            action
        )

    if collector_vix:
        collector_vix.client.close()

    sections.append(vix_table)
    sections.append(Text(""))

    # Holdings with live prices and recalculated signals
    if portfolio.positions:
        sections.append(Text(">> HOLDINGS (Live Prices + Signals)", style="bold white on blue"))
        sections.append(Text(""))
        holdings_table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
        holdings_table.add_column("Symbol", style="bold white", width=7)
        holdings_table.add_column("Qty", justify="right", width=5)
        holdings_table.add_column("Current", justify="right", style="bright_white", width=11)
        holdings_table.add_column("P/L $", justify="right", width=11)
        holdings_table.add_column("P/L %", justify="right", width=9)
        holdings_table.add_column("Signal", width=18)

        collector_h = PolygonCollector() if market_status["is_open"] else None

        for symbol, position in portfolio.positions.items():
            price_data = get_price_data(symbol, market_status, db, collector_h)
            if price_data:
                current_price = price_data["price"]
                timestamp = price_data["timestamp"]

                # Recalculate P/L
                pl_dollars = (current_price - position.price_paid) * position.quantity
                pl_pct = ((current_price - position.price_paid) / position.price_paid * 100) if position.price_paid > 0 else 0
                pl_color = "green" if pl_dollars >= 0 else "red"
                live_indicator = "[green]*[/green]" if price_data["is_live"] else "[dim]-[/dim]"

                # Recalculate signal
                signal = detector.generate_signal(symbol, timestamp, current_price)
                current_signals[f"holding_{symbol}"] = signal.signal.value

                # Check for signal change
                signal_changed = ""
                if previous_signals and f"holding_{symbol}" in previous_signals:
                    if previous_signals[f"holding_{symbol}"] != signal.signal.value:
                        signal_changed = f" [bold yellow]CHG[/bold yellow]"

                signal_color = "green" if signal.signal.value == "BUY" else "red" if signal.signal.value == "SELL" else "yellow"

                holdings_table.add_row(
                    f"{live_indicator} {symbol}",
                    str(position.quantity),
                    f"${current_price:.2f}",
                    f"[{pl_color}]${pl_dollars:+,.2f}[/{pl_color}]",
                    f"[{pl_color}]{pl_pct:+.1f}%[/{pl_color}]",
                    f"[{signal_color}]{signal.signal.value}[/{signal_color}]{signal_changed}"
                )

        if collector_h:
            collector_h.client.close()

        sections.append(holdings_table)

    # Watchlist with live signal updates - Track pre-open opportunities
    sections.append(Text(""))
    sections.append(Text(">> WATCHLIST - Tracking Pre-Open Opportunities", style="bold white on blue"))
    sections.append(Text(""))

    watchlist_table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
    watchlist_table.add_column("Rank", style="dim", width=5)
    watchlist_table.add_column("Symbol", style="bold white", width=7)
    watchlist_table.add_column("Price", justify="right", style="bright_white", width=10)
    watchlist_table.add_column("Signal", width=20)
    watchlist_table.add_column("Conf", justify="right", width=8)
    watchlist_table.add_column("Status", width=40)

    from src.config.tickers import TIER_2_STOCKS

    buy_candidates = []
    initial_watchlist_status = []  # Track status of pre-open tickers
    collector_w = PolygonCollector() if market_status["is_open"] else None

    # First, check all initial watchlist tickers (priority tracking)
    for ticker in initial_watchlist:
        if ticker in portfolio.positions:
            continue

        price_data = get_price_data(ticker, market_status, db, collector_w)
        if price_data:
            current_price = price_data["price"]
            timestamp = price_data["timestamp"]

            # Recalculate signal
            signal = detector.generate_signal(ticker, timestamp, current_price)

            # Track all initial watchlist tickers regardless of signal
            current_signals[f"watchlist_{ticker}"] = signal.signal.value

            # Determine status message
            status_msg = ""
            if signal.signal == TradingSignal.BUY and signal.confidence >= 0.75:
                # Still BUY
                if previous_signals and f"watchlist_{ticker}" in previous_signals:
                    if previous_signals[f"watchlist_{ticker}"] == "BUY":
                        status_msg = "[green]Still BUY ✓[/green]"
                    else:
                        status_msg = "[bold green]CHANGED → BUY![/bold green]"
                else:
                    status_msg = "[green]Still BUY ✓[/green]"

                reasoning = signal.reasoning.split('\n')[0] if signal.reasoning else "Trend confirmed"
                initial_watchlist_status.append({
                    "symbol": ticker,
                    "price": current_price,
                    "signal": signal.signal.value,
                    "confidence": signal.confidence,
                    "reasoning": reasoning,
                    "status": status_msg,
                    "is_initial": True,
                    "sort_priority": 1  # Highest priority
                })
            else:
                # Signal changed from BUY to something else
                if previous_signals and f"watchlist_{ticker}" in previous_signals:
                    if previous_signals[f"watchlist_{ticker}"] == "BUY":
                        status_msg = f"[red]CHANGED → {signal.signal.value}[/red]"
                    else:
                        status_msg = f"[yellow]{signal.signal.value}[/yellow]"
                else:
                    status_msg = f"[red]No longer BUY → {signal.signal.value}[/red]"

                initial_watchlist_status.append({
                    "symbol": ticker,
                    "price": current_price,
                    "signal": signal.signal.value,
                    "confidence": signal.confidence,
                    "reasoning": "Signal changed",
                    "status": status_msg,
                    "is_initial": True,
                    "sort_priority": 2  # Show after current BUYs
                })

    # Then scan for new BUY signals in the rest of the watchlist
    for ticker_meta in TIER_2_STOCKS[:30]:  # Check top 30
        ticker = ticker_meta.symbol if hasattr(ticker_meta, 'symbol') else ticker_meta

        # Skip if already checked in initial watchlist
        if ticker in initial_watchlist:
            continue

        # Skip if in holdings
        if ticker in portfolio.positions:
            continue

        price_data = get_price_data(ticker, market_status, db, collector_w)
        if price_data:
            current_price = price_data["price"]
            timestamp = price_data["timestamp"]

            # Recalculate signal
            signal = detector.generate_signal(ticker, timestamp, current_price)

            if signal.signal == TradingSignal.BUY and signal.confidence >= 0.75:
                current_signals[f"watchlist_{ticker}"] = signal.signal.value

                # Check if this is a new signal
                status_msg = ""
                if previous_signals and f"watchlist_{ticker}" in previous_signals:
                    status_msg = " [bold yellow]NEW![/bold yellow]"
                elif previous_signals:  # New signal that wasn't there before
                    status_msg = " [bold green]NEW SIGNAL![/bold green]"

                reasoning = signal.reasoning.split('\n')[0] if signal.reasoning else "Trend confirmed"

                buy_candidates.append({
                    "symbol": ticker,
                    "price": current_price,
                    "signal": signal.signal.value,
                    "confidence": signal.confidence,
                    "reasoning": reasoning,
                    "status": status_msg,
                    "is_initial": False,
                    "sort_priority": 3  # Lower priority than initial watchlist
                })

    if collector_w:
        collector_w.client.close()

    # Combine and sort: initial watchlist first, then by confidence
    all_candidates = initial_watchlist_status + buy_candidates
    all_candidates.sort(key=lambda x: (x["sort_priority"], -x["confidence"]))

    for i, candidate in enumerate(all_candidates[:15], 1):  # Show top 15
        conf_color = "green" if candidate["confidence"] >= 0.85 else "yellow"
        signal_color = "green" if candidate["signal"] == "BUY" else "red" if candidate["signal"] == "SELL" else "yellow"

        # Add indicator for pre-open tracked tickers
        symbol_display = f"[bold]{candidate['symbol']}[/bold]" if candidate["is_initial"] else candidate["symbol"]

        watchlist_table.add_row(
            f"#{i}",
            symbol_display,
            f"${candidate['price']:.2f}",
            f"[{signal_color}]{candidate['signal']}[/{signal_color}]",
            f"[{conf_color}]{candidate['confidence']:.0%}[/{conf_color}]",
            f"{candidate['status']}"
        )

    sections.append(watchlist_table)

    # Unusual Options & Volume Activity (short-term opportunities)
    sections.append(Text(""))
    sections.append(Text(">> UNUSUAL ACTIVITY - Short-Term Opportunities", style="bold white on red"))
    sections.append(Text(""))

    unusual_table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
    unusual_table.add_column("Rank", style="dim", width=5)
    unusual_table.add_column("Symbol", style="bold white", width=7)
    unusual_table.add_column("Price", justify="right", style="bright_white", width=10)
    unusual_table.add_column("Type", width=15)
    unusual_table.add_column("Conf", justify="right", width=8)
    unusual_table.add_column("Details", width=50)

    # Only scan for unusual activity during market hours
    if market_status["is_open"]:
        from src.models.unusual_activity_detector import UnusualActivityDetector

        try:
            activity_detector = UnusualActivityDetector(db=db)

            # Scan all watchlist tickers for unusual activity
            scan_tickers = [
                ticker_meta.symbol if hasattr(ticker_meta, 'symbol') else ticker_meta
                for ticker_meta in TIER_2_STOCKS[:30]
            ]

            unusual_signals = activity_detector.scan_watchlist(scan_tickers)

            # Show top 10 unusual activity signals
            for i, signal in enumerate(unusual_signals[:10], 1):
                conf_color = "green" if signal.confidence >= 0.75 else "yellow"

                # Type color coding
                type_colors = {
                    "unusual_calls": "green",
                    "unusual_puts": "red",
                    "volume_spike": "yellow",
                    "smart_money": "bright_green"
                }
                type_color = type_colors.get(signal.signal_type, "white")
                type_label = signal.signal_type.replace("_", " ").title()

                unusual_table.add_row(
                    f"#{i}",
                    signal.ticker,
                    f"${signal.current_price:.2f}",
                    f"[{type_color}]{type_label}[/{type_color}]",
                    f"[{conf_color}]{signal.confidence:.0%}[/{conf_color}]",
                    f"[dim]{signal.reason[:48]}[/dim]"
                )

            activity_detector.close()

        except Exception as e:
            # Show error but don't crash
            unusual_table.add_row("", "", "", f"[red]Error: {str(e)[:50]}[/red]", "", "")
    else:
        unusual_table.add_row("", "", "", "[dim]Market closed - no live data[/dim]", "", "")

    sections.append(unusual_table)

    return Group(*sections), current_signals


def generate_market_check(auto_refresh: bool = False, refresh_interval: int = 60):
    """
    Generate the unified market check report.

    Args:
        auto_refresh: If True, continuously refresh during market hours
        refresh_interval: Seconds between refreshes (default 60)
    """
    # Initialize once
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

    regime_detector = RegimeDetector(db)
    regime_info = regime_detector.detect_regime()

    portfolio_manager = PortfolioManager()
    portfolio = portfolio_manager.load_portfolio()

    current_time = datetime.now()
    market_status = MarketStatus.get_status()

    # Section 0: ACCOUNT SUMMARY
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
            cash = float(cash)
            portfolio_val = float(portfolio_val)
            total = float(total)
            margin_used = float(margin_used)

            cash_pct = (cash / total * 100) if total > 0 else 0
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

            balance_table.add_row("Cash Balance", f"${cash:,.2f}", f"{cash_pct:.1f}% of total")
            balance_table.add_row("Portfolio Value", f"${portfolio_val:,.2f}", f"{100 - cash_pct:.1f}% of total")
            balance_table.add_row("Total Account Value", f"${total:,.2f}", f"Path to $1M: {(total / 1_000_000 * 100):.1f}%")
            balance_table.add_row("Buying Power", f"${buying_power:,.2f}", "Cash + Margin Available")
            balance_table.add_row("Margin Risk", f"[{risk_color}]{risk_level}[/{risk_color}]",
                                 f"Using ${margin_used:,.2f} ({margin_pct:.1f}% of account)")

            console.print(balance_table)
        else:
            console.print("[yellow]No account balance data found[/yellow]")
            console.print("[dim]Run: .\\tasks.ps1 update-cash[/dim]")
    except Exception as e:
        console.print(f"[red]Error loading account balance: {e}[/red]")

    # Section 1: MARKET DIRECTION
    console.print("\n[bold bright_white]>> MARKET DIRECTION[/bold bright_white]", style="on blue")
    console.print()

    market_table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
    market_table.add_column("Index", style="bold white", width=8)
    market_table.add_column("Price", justify="right", style="bright_white", width=12)
    market_table.add_column("Change %", justify="right", width=12)
    market_table.add_column("Signal", width=12)
    market_table.add_column("Confidence", justify="right", width=12)
    market_table.add_column("Update", width=20)

    collector = PolygonCollector() if market_status["is_open"] else None

    for index_ticker in ["SPY", "QQQ"]:
        price_data = get_price_data(index_ticker, market_status, db, collector)

        if price_data:
            signal = detector.generate_signal(index_ticker, price_data["timestamp"], price_data["price"])

            change_pct = price_data["change_pct"]
            change_color = "green" if change_pct > 0 else "red"
            change_str = f"{change_pct:+.2f}%"

            if signal.signal == TradingSignal.BUY:
                signal_text = f"[bold green]{signal.signal.value}[/bold green]"
            elif signal.signal == TradingSignal.SELL:
                signal_text = f"[bold red]{signal.signal.value}[/bold red]"
            else:
                signal_text = f"[yellow]{signal.signal.value}[/yellow]"

            update_text = "[green]LIVE[/green]" if price_data["is_live"] else "[dim]DB[/dim]"
            if price_data["is_live"]:
                update_text += " [dim](15m delay)[/dim]"

            market_table.add_row(
                index_ticker,
                f"${price_data['price']:.2f}",
                f"[{change_color}]{change_str}[/{change_color}]",
                signal_text,
                f"{signal.confidence:.0%}",
                update_text
            )

    if collector:
        collector.client.close()

    console.print(market_table)

    # Add market strength indicators
    console.print()
    strength_table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
    strength_table.add_column("Indicator", style="bold white", width=25)
    strength_table.add_column("Value", justify="right", style="bright_white", width=15)
    strength_table.add_column("Status", width=30)

    # VIX with 4-week trend
    vix = regime_info.get('vix', 0)
    if vix:
        vix_color = "green" if vix < 15 else "yellow" if vix < 20 else "red"
        vix_status = "Low fear" if vix < 15 else "Moderate fear" if vix < 20 else "High fear" if vix < 30 else "Extreme fear"

        # Get VIX history for last 4 weeks
        four_weeks_ago = current_time.date() - timedelta(days=28)
        vix_history = db.conn.execute("""
            SELECT close, timestamp
            FROM stock_prices
            WHERE symbol = 'VIX'
            AND timestamp >= ?
            ORDER BY timestamp ASC
        """, [four_weeks_ago]).fetchall()

        trend_indicator = ""
        if vix_history and len(vix_history) >= 2:
            vix_4w_ago = float(vix_history[0][0])
            vix_change = vix - vix_4w_ago
            vix_change_pct = (vix_change / vix_4w_ago * 100) if vix_4w_ago > 0 else 0

            # Create mini trend chart
            if vix_change_pct > 20:
                trend_indicator = f" [red]UP +{vix_change_pct:.1f}% (4w)[/red]"
            elif vix_change_pct > 5:
                trend_indicator = f" [yellow]UP +{vix_change_pct:.1f}% (4w)[/yellow]"
            elif vix_change_pct < -20:
                trend_indicator = f" [green]DOWN {vix_change_pct:.1f}% (4w)[/green]"
            elif vix_change_pct < -5:
                trend_indicator = f" [green]DOWN {vix_change_pct:.1f}% (4w)[/green]"
            else:
                trend_indicator = f" [dim]FLAT {vix_change_pct:+.1f}% (4w)[/dim]"

        strength_table.add_row("VIX (Fear Index)", f"{vix:.2f}", f"[{vix_color}]{vix_status}[/{vix_color}]{trend_indicator}")

    console.print(strength_table)
    console.print()

    # Economic Calendar - Next 14 days
    console.print("[bold bright_white]>> UPCOMING ECONOMIC EVENTS (Next 14 Days)[/bold bright_white]")
    console.print()

    try:
        start_date = current_time.date()
        end_date = start_date + timedelta(days=14)

        events = db.conn.execute("""
            SELECT release_date, event_name, event_type, event_id
            FROM economic_calendar
            WHERE release_date BETWEEN ? AND ?
            ORDER BY release_date ASC
            LIMIT 10
        """, [start_date, end_date]).fetchall()

        if events:
            cal_table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
            cal_table.add_column("Date", style="bold white", width=12)
            cal_table.add_column("Event", style="white", width=50)
            cal_table.add_column("Type", width=20)

            for event in events:
                release_date, event_name, event_type, event_id = event
                # Determine impact based on event type
                high_impact = ["CPI", "FOMC", "GDP", "NFP", "UNEMPLOYMENT", "PCE"]
                impact_color = "red" if any(keyword in event_type.upper() for keyword in high_impact) else "yellow"

                cal_table.add_row(
                    str(release_date),
                    event_name[:48] if event_name else event_type,
                    f"[{impact_color}]{event_type}[/{impact_color}]"
                )

            console.print(cal_table)
        else:
            console.print("[dim]No major economic events in the next 14 days[/dim]")

        console.print()
    except Exception as e:
        console.print(f"[dim]Economic calendar unavailable: {e}[/dim]")
        console.print()

    # Market condition panel
    spy_price_data = get_price_data("SPY", market_status, db, PolygonCollector() if market_status["is_open"] else None)
    qqq_price_data = get_price_data("QQQ", market_status, db, PolygonCollector() if market_status["is_open"] else None)

    spy_signal = None
    qqq_signal = None

    if spy_price_data:
        spy_signal = detector.generate_signal("SPY", spy_price_data["timestamp"], spy_price_data["price"]).signal
    if qqq_price_data:
        qqq_signal = detector.generate_signal("QQQ", qqq_price_data["timestamp"], qqq_price_data["price"]).signal

    if spy_signal == TradingSignal.BUY and qqq_signal == TradingSignal.BUY:
        console.print(Panel(">> [bold green]BULLISH[/bold green] - Good time to buy stocks", border_style="green"))
    elif spy_signal == TradingSignal.SELL or qqq_signal == TradingSignal.SELL:
        console.print(Panel(">> [bold red]BEARISH[/bold red] - Avoid new buys, consider taking profits", border_style="red"))
    else:
        console.print(Panel(">> [bold yellow]NEUTRAL[/bold yellow] - Be selective with new positions", border_style="yellow"))

    console.print()

    # Section 2: HOLDINGS ANALYSIS
    console.print("\n[bold bright_white]>> HOLDINGS ANALYSIS[/bold bright_white]", style="on blue")
    console.print()

    if portfolio.positions:
        holdings_table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
        holdings_table.add_column("Symbol", style="bold white", width=8)
        holdings_table.add_column("Qty", justify="right", width=6)
        holdings_table.add_column("Avg Cost", justify="right", style="dim", width=10)
        holdings_table.add_column("Current", justify="right", style="bright_white", width=10)
        holdings_table.add_column("P/L $", justify="right", width=12)
        holdings_table.add_column("P/L %", justify="right", width=10)
        holdings_table.add_column("Signal", width=12)
        holdings_table.add_column("Action", width=35)

        consider_selling = []
        watch_today = []
        strong_holds = []

        collector_for_holdings = PolygonCollector() if market_status["is_open"] else None

        for symbol, position in portfolio.positions.items():
            price_data = get_price_data(symbol, market_status, db, collector_for_holdings)

            if price_data:
                current_price = price_data["price"]
                signal = detector.generate_signal(symbol, price_data["timestamp"], current_price)

                pl_dollars = (current_price - position.price_paid) * position.quantity
                pl_pct = ((current_price - position.price_paid) / position.price_paid * 100) if position.price_paid > 0 else 0

                pl_color = "green" if pl_dollars >= 0 else "red"
                pl_dollars_str = f"${pl_dollars:+,.2f}"
                pl_pct_str = f"{pl_pct:+.1f}%"

                # Determine signal display and action
                current_signal_str = signal.signal.value

                if signal.signal == TradingSignal.SELL:
                    signal_display = f"[bold red]{current_signal_str}[/bold red]"
                    action = "[bold red]SELL TODAY[/bold red]"
                    consider_selling.append((symbol, price_data["timestamp"].strftime("%Y-%m-%d")))

                elif signal.signal == TradingSignal.BUY:
                    signal_display = f"[green]{current_signal_str}[/green]"

                    if pl_pct > 10:
                        action = "[green]STRONG - Consider adding[/green]"
                        strong_holds.append(symbol)
                    else:
                        action = "[green]HOLD (BUY signal)[/green]"
                        strong_holds.append(symbol)

                else:  # HOLD or DONT_TRADE
                    signal_display = f"[yellow]{current_signal_str}[/yellow]"

                    if pl_pct < -5:
                        action = "[yellow]WATCH - Underwater[/yellow]"
                        watch_today.append(symbol)
                    else:
                        action = "[dim]Monitor[/dim]"

                live_indicator = "[green]*[/green]" if price_data["is_live"] else "[dim]-[/dim]"

                holdings_table.add_row(
                    f"{live_indicator} {symbol}",
                    str(position.quantity),
                    f"${position.price_paid:.2f}",
                    f"${current_price:.2f}",
                    f"[{pl_color}]{pl_dollars_str}[/{pl_color}]",
                    f"[{pl_color}]{pl_pct_str}[/{pl_color}]",
                    signal_display,
                    action
                )

        if collector_for_holdings:
            collector_for_holdings.client.close()

        console.print(holdings_table)

        # Note about live data if market is open
        if market_status["is_open"]:
            console.print()
            console.print("[dim]Note: Prices update live during market hours (15-min delayed)[/dim]")
    else:
        console.print("[yellow]No holdings to display[/yellow]")

    console.print()

    # Section 3: WATCHLIST - New Opportunities
    console.print("\n[bold bright_white]>> WATCHLIST - New Opportunities[/bold bright_white]", style="on blue")
    console.print()

    # Get buy signals
    today = current_time.date()
    buy_candidates = []

    # Use database data for watchlist to ensure we have technical indicators
    collector_for_watchlist = None  # Always use DB for watchlist for now

    checked_count = 0
    for ticker_meta in TIER_2_STOCKS:
        ticker = ticker_meta.symbol if hasattr(ticker_meta, 'symbol') else ticker_meta
        if ticker in portfolio.positions:
            continue  # Skip existing holdings

        price_data = get_price_data(ticker, market_status, db, collector_for_watchlist)

        if not price_data:
            continue  # Skip if no price data

        checked_count += 1
        signal = detector.generate_signal(ticker, price_data["timestamp"], price_data["price"])

        if signal.signal == TradingSignal.BUY and signal.confidence >= 0.75:
            # Simple score based on confidence
            composite_score = signal.confidence * 100

            # Extract reasoning (first line only for display)
            reasoning = signal.reasoning.split('\n')[0] if signal.reasoning else "Trend confirmed"

            buy_candidates.append({
                "symbol": ticker,
                "price": price_data["price"],
                "signal_date": price_data["timestamp"].strftime("%Y-%m-%d"),
                "confidence": signal.confidence,
                "composite_score": composite_score,
                "reasoning": reasoning,
                "is_live": price_data["is_live"],
            })

    if collector_for_watchlist:
        collector_for_watchlist.client.close()

    # Sort by composite score
    buy_candidates.sort(key=lambda x: x["composite_score"], reverse=True)

    if buy_candidates:
        watchlist_table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
        watchlist_table.add_column("Rank", style="bold yellow", width=6)
        watchlist_table.add_column("Symbol", style="bold white", width=8)
        watchlist_table.add_column("Price", justify="right", style="bright_white", width=12)
        watchlist_table.add_column("Conf%", justify="right", width=8)
        watchlist_table.add_column("Reason", width=50)

        for i, candidate in enumerate(buy_candidates[:10], 1):  # Top 10
            conf_color = "green" if candidate["confidence"] >= 0.85 else "yellow" if candidate["confidence"] >= 0.75 else "white"
            update_suffix = " [green](LIVE)[/green]" if candidate["is_live"] else ""

            # Truncate reasoning if too long
            reason = candidate["reasoning"][:48] + "..." if len(candidate["reasoning"]) > 50 else candidate["reasoning"]

            watchlist_table.add_row(
                f"#{i}",
                candidate["symbol"],
                f"${candidate['price']:.2f}{update_suffix}",
                f"[{conf_color}]{candidate['confidence']:.0%}[/{conf_color}]",
                f"[dim]{reason}[/dim]"
            )

        console.print(watchlist_table)

        # Show legend
        console.print()
        console.print("[dim]Signal Reasoning Legend:[/dim]")
        console.print("[dim]  - TREND CHANGE CONFIRMED: Price crossed above/below key moving averages[/dim]")
        console.print("[dim]  - VOLUME SPIKE: Unusually high volume detected (confidence reduced)[/dim]")
        console.print("[dim]  - EARNINGS SOON: Earnings within 3 days (trade blocked)[/dim]")
    else:
        console.print("[yellow]No strong buy candidates at the moment[/yellow]")

    console.print()

    # Section 4: PORTFOLIO OPTIMIZATION
    console.print("\n[bold bright_white]>> PORTFOLIO OPTIMIZATION[/bold bright_white]", style="on blue")
    console.print()

    try:
        analyzer = PortfolioAnalyzer()
        health_data = analyzer.get_portfolio_health_score()

        if isinstance(health_data, dict):
            health = health_data.get("score", 0)
            grade = health_data.get("grade", "N/A")
            issues = health_data.get("issues", [])

            health_color = "green" if health >= 80 else "yellow" if health >= 60 else "red"
            console.print(f"Portfolio Health: [{health_color}]{health:.0f}/100 (Grade: {grade})[/{health_color}]")

            if issues:
                console.print()
                console.print("[yellow]Issues Found:[/yellow]")
                for issue in issues:
                    console.print(f"  - {issue}")

            # Get rebalancing recommendations
            recommendations = analyzer.find_rebalancing_opportunities()

            if recommendations:
                console.print()
                console.print("[bold cyan]Rebalancing Recommendations:[/bold cyan]")
                console.print()

                rebal_table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
                rebal_table.add_column("Sell", style="red", width=8)
                rebal_table.add_column("Reason", style="dim", width=35)
                rebal_table.add_column("Buy", style="green", width=8)
                rebal_table.add_column("Reason", width=35)
                rebal_table.add_column("Gain", justify="right", width=8)

                for rec in recommendations:
                    rebal_table.add_row(
                        rec["reduce_symbol"],
                        rec["reduce_reason"][:33],
                        rec["increase_symbol"],
                        rec["increase_reason"][:33],
                        f"+{rec['expected_gain']:.0f}"
                    )

                console.print(rebal_table)
                console.print()
                console.print("[dim]Gain = Signal strength improvement (points)[/dim]")
            else:
                console.print()
                console.print("[green]Portfolio is well-balanced - no rebalancing needed[/green]")
        else:
            console.print("[yellow]Portfolio health data unavailable[/yellow]")

    except Exception as e:
        console.print(f"[dim]Portfolio optimization unavailable: {e}[/dim]")

    console.print()

    # Section 5: ACTIONS FOR TODAY
    console.print("\n[bold bright_white]>> TODAY'S GAME PLAN[/bold bright_white]", style="on blue")
    console.print()

    summary_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    summary_table.add_column("Category", style="bold cyan", width=20)
    summary_table.add_column("Count", style="bright_white", width=15)

    summary_table.add_row("Portfolio Holdings", f"{len(portfolio.positions)}")
    summary_table.add_row("  - Need attention", f"[yellow]{len(consider_selling) + len(watch_today)}[/yellow]")
    summary_table.add_row("  - Stable", f"[green]{len(portfolio.positions) - len(consider_selling) - len(watch_today)}[/green]")
    summary_table.add_row("New Opportunities", f"[green]{len(buy_candidates)}[/green]")
    summary_table.add_row("  - Strong buys (>85)", f"[bold green]{sum(1 for c in buy_candidates if c['composite_score'] >= 85)}[/bold green]")

    console.print(summary_table)
    console.print()

    # ACTIONS FOR TODAY
    console.print("[bold yellow]ACTIONS FOR TODAY:[/bold yellow]")
    console.print("[dim]" + "-" * 80 + "[/dim]")

    if consider_selling:
        console.print(f"\n[bold red]1. REVIEW SELL SIGNALS[/bold red] ([yellow]{len(consider_selling)} stocks[/yellow])")
        for ticker, signal_date in consider_selling:
            if market_status["is_open"]:
                console.print(f"   • [red]{ticker}[/red]: Signal on {signal_date} - [bold]SELL NOW[/bold]")
            else:
                console.print(f"   • [red]{ticker}[/red]: Signal on {signal_date} - Check at market open")
    else:
        console.print("\n[green]1. NO SELL SIGNALS[/green] - All holdings look stable")

    if watch_today:
        console.print(f"\n[bold yellow]2. MONITOR CLOSELY[/bold yellow] ([yellow]{len(watch_today)} stocks[/yellow])")
        for ticker in watch_today:
            console.print(f"   • [yellow]{ticker}[/yellow]: Watch for further weakness")
    else:
        console.print("\n[green]2. NO STOCKS NEED MONITORING[/green]")

    strong_buys = [c for c in buy_candidates if c["composite_score"] >= 85]
    if strong_buys:
        console.print(f"\n[bold green]3. STRONG BUY OPPORTUNITIES[/bold green] ([green]{len(strong_buys)} stocks[/green])")
        for candidate in strong_buys[:3]:  # Top 3
            console.print(f"   • [green]{candidate['symbol']}[/green] @ ${candidate['price']:.2f} (Score: {candidate['composite_score']:.0f})")
    else:
        console.print("\n[yellow]3. NO STRONG BUY SIGNALS[/yellow] - Wait for better setups")

    console.print()

    # NEXT STEPS
    if not market_status["is_open"]:
        console.print("[bold cyan]NEXT STEPS:[/bold cyan]")
        console.print("[dim]" + "-" * 80 + "[/dim]")
        console.print()

        if market_status["status"] == "PRE_MARKET":
            console.print("   [cyan]1.[/cyan] Market opens at 9:30 AM ET")
            console.print("   [cyan]2.[/cyan] Run with [bold]--live[/bold] flag for real-time updates during market hours")
            console.print("   [cyan]3.[/cyan] Execute sell orders for any confirmed sell signals")
        elif market_status["status"] == "AFTER_HOURS":
            console.print("   [cyan]1.[/cyan] Review today's performance")
            console.print("   [cyan]2.[/cyan] Plan for tomorrow's market open")
            console.print("   [cyan]3.[/cyan] Update watchlist for next trading day")
        else:  # Weekend
            console.print("   [cyan]1.[/cyan] Market closed for the weekend")
            console.print("   [cyan]2.[/cyan] Review weekly performance")
            console.print("   [cyan]3.[/cyan] Prepare strategy for Monday")

        console.print()

    # If live mode enabled and market is open, use Live display for price updates
    if auto_refresh and market_status["should_refresh"]:
        console.print()
        console.print("[bold green]Live Updates Active[/bold green] [dim]| Refreshing every 30s | Press Ctrl+C to stop[/dim]")
        console.print()

        # Extract initial watchlist tickers to track
        initial_watchlist_tickers = [c["symbol"] for c in buy_candidates[:10]]
        console.print(f"[dim]Tracking {len(initial_watchlist_tickers)} pre-open opportunities: {', '.join(initial_watchlist_tickers)}[/dim]")
        console.print()

        previous_signals = None

        try:
            # Initial render with watchlist tracking
            live_content, previous_signals = build_live_sections(
                db, market_status, detector, portfolio, previous_signals, initial_watchlist_tickers
            )

            with Live(live_content, console=console, refresh_per_second=0.5) as live:
                while True:
                    time.sleep(30)  # Update every 30 seconds

                    # Refresh market status
                    market_status = MarketStatus.get_status()
                    if not market_status["should_refresh"]:
                        console.print("\n[yellow]Market closed - stopping live updates[/yellow]")
                        break

                    # Update live sections with signal change detection
                    live_content, current_signals = build_live_sections(
                        db, market_status, detector, portfolio, previous_signals, initial_watchlist_tickers
                    )
                    live.update(live_content)

                    # Update previous signals for next iteration
                    previous_signals = current_signals

        except KeyboardInterrupt:
            console.print("\n[yellow]Live updates stopped by user[/yellow]")

    db.close()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Unified Market Check")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Enable auto-refresh during market hours (updates every 30 seconds)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Refresh interval in seconds (default: 30)"
    )

    args = parser.parse_args()

    try:
        generate_market_check(auto_refresh=args.live, refresh_interval=args.interval)
    except KeyboardInterrupt:
        console.print("\n[yellow]Market check stopped[/yellow]")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
