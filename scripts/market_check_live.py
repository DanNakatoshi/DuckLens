"""
Enhanced market check with selective live updates.

Only updates dynamic sections (prices, timestamps) without redrawing static content.
"""

import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from rich.console import Console
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich import box

from scripts.market_check import (
    MarketStatus,
    get_price_data,
)
from src.data.storage.market_data_db import MarketDataDB
from src.data.collectors.polygon_collector import PolygonCollector
from src.models.enhanced_detector import EnhancedTrendDetector
from src.portfolio.portfolio_manager import PortfolioManager
from src.config.tickers import TIER_2_STOCKS

load_dotenv()
console = Console()


def build_header_panel(market_status, current_time):
    """Build header with timestamp (updates frequently)."""
    status_color = "green" if market_status["is_open"] else "yellow"
    status_icon = "[LIVE]" if market_status["is_open"] else ""
    mode = "LIVE MODE" if market_status["is_open"] else "STATIC MODE"

    return Panel.fit(
        f"[bold cyan]MARKET CHECK - {mode} {status_icon}[/bold cyan]\n"
        f"[{status_color}]Market Status: {market_status['status']}[/{status_color}]\n"
        f"[dim]Time: {current_time.strftime('%Y-%m-%d %I:%M:%S %p ET')}[/dim]\n"
        f"[dim]Data Source: {market_status['data_source']}[/dim]",
        border_style=status_color
    )


def build_indices_table(db, market_status):
    """Build market indices table (updates frequently)."""
    indices_table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
    indices_table.add_column("Index", style="bold white", width=8)
    indices_table.add_column("Price", justify="right", style="bright_white", width=12)
    indices_table.add_column("Change %", justify="right", width=15)
    indices_table.add_column("Signal", width=12)
    indices_table.add_column("Confidence", justify="right", width=15)
    indices_table.add_column("Update", style="dim", width=20)

    detector = EnhancedTrendDetector(db=db, min_confidence=0.75)
    collector = PolygonCollector() if market_status["is_open"] else None

    for symbol in ["SPY", "QQQ"]:
        price_data = get_price_data(symbol, market_status, db, collector)

        if price_data:
            current_price = price_data["price"]
            timestamp = price_data["timestamp"]

            # Get previous day close for comparison
            prev_close = db.conn.execute("""
                SELECT close
                FROM stock_prices
                WHERE symbol = ?
                AND DATE(timestamp) = DATE(?) - INTERVAL '1 day'
                ORDER BY timestamp DESC
                LIMIT 1
            """, [symbol, timestamp]).fetchone()

            change_pct = 0
            if prev_close:
                prev = float(prev_close[0])
                change_pct = ((current_price - prev) / prev * 100) if prev > 0 else 0

            signal = detector.generate_signal(symbol, timestamp, current_price)

            change_color = "green" if change_pct >= 0 else "red"
            signal_display = f"[yellow]{signal.signal.value}[/yellow]"
            conf_display = f"{signal.confidence:.0%}"

            update_status = "LIVE (15m delay)" if price_data["is_live"] else "Database"

            indices_table.add_row(
                symbol,
                f"${current_price:.2f}",
                f"[{change_color}]{change_pct:+.2f}%[/{change_color}]",
                signal_display,
                conf_display,
                update_status
            )

    if collector:
        collector.client.close()

    return indices_table


def build_holdings_table(db, market_status, detector, portfolio):
    """Build holdings table (updates frequently)."""
    if not portfolio.positions:
        return Panel("[yellow]No holdings to display[/yellow]")

    holdings_table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
    holdings_table.add_column("Symbol", style="bold white", width=8)
    holdings_table.add_column("Qty", justify="right", width=6)
    holdings_table.add_column("Current", justify="right", style="bright_white", width=12)
    holdings_table.add_column("P/L $", justify="right", width=12)
    holdings_table.add_column("P/L %", justify="right", width=10)

    collector = PolygonCollector() if market_status["is_open"] else None

    for symbol, position in portfolio.positions.items():
        price_data = get_price_data(symbol, market_status, db, collector)

        if price_data:
            current_price = price_data["price"]
            pl_dollars = (current_price - position.price_paid) * position.quantity
            pl_pct = ((current_price - position.price_paid) / position.price_paid * 100) if position.price_paid > 0 else 0

            pl_color = "green" if pl_dollars >= 0 else "red"
            update_suffix = " [green](LIVE)[/green]" if price_data["is_live"] else ""

            holdings_table.add_row(
                symbol,
                str(position.quantity),
                f"${current_price:.2f}{update_suffix}",
                f"[{pl_color}]${pl_dollars:+,.2f}[/{pl_color}]",
                f"[{pl_color}]{pl_pct:+.1f}%[/{pl_color}]"
            )

    if collector:
        collector.client.close()

    return holdings_table


def generate_live_display():
    """Generate market check with selective live updates."""
    # Create layout
    layout = Layout()

    layout.split_column(
        Layout(name="header", size=7),
        Layout(name="indices", size=10),
        Layout(name="holdings", size=20),
        Layout(name="footer", size=3)
    )

    # Initialize
    db = MarketDataDB()
    detector = EnhancedTrendDetector(db=db, min_confidence=0.75)
    portfolio_manager = PortfolioManager()
    portfolio = portfolio_manager.load_portfolio()

    def generate():
        """Generator for live updates."""
        while True:
            current_time = datetime.now()
            market_status = MarketStatus.get_status()

            # Update dynamic sections only
            layout["header"].update(build_header_panel(market_status, current_time))
            layout["indices"].update(
                Panel(
                    build_indices_table(db, market_status),
                    title="[bold bright_white]MARKET INDICES[/bold bright_white]",
                    border_style="blue"
                )
            )
            layout["holdings"].update(
                Panel(
                    build_holdings_table(db, market_status, detector, portfolio),
                    title="[bold bright_white]HOLDINGS[/bold bright_white]",
                    border_style="blue"
                )
            )

            # Countdown footer
            if market_status["is_open"]:
                layout["footer"].update(
                    Panel(
                        "[dim]Live updates every 60s | Press Ctrl+C to stop[/dim]",
                        border_style="dim"
                    )
                )
            else:
                layout["footer"].update(
                    Panel(
                        "[yellow]Market closed - no live updates[/yellow]",
                        border_style="yellow"
                    )
                )

            yield layout

            # Wait before next update
            if market_status["is_open"]:
                time.sleep(60)
            else:
                break

    # Run live display
    try:
        with Live(generate(), console=console, refresh_per_second=1, screen=True):
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Live display stopped[/yellow]")

    db.close()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Live Market Check with Selective Updates")
    args = parser.parse_args()

    try:
        generate_live_display()
    except KeyboardInterrupt:
        console.print("\n[yellow]Market check stopped[/yellow]")
        return 0

    return 0


if __name__ == "__main__":
    exit(main())
