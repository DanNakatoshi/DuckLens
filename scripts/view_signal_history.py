"""View trading signal history and performance."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from src.tracking.signal_tracker import SignalTracker

console = Console()


def main():
    """Display signal tracking history and performance metrics."""
    console.print("\n[bold cyan]TRADING SIGNAL HISTORY & PERFORMANCE[/bold cyan]")
    console.print()

    with SignalTracker() as tracker:
        # Get performance metrics
        stats_90d = tracker.get_signal_win_rate(lookback_days=90)
        stats_30d = tracker.get_signal_win_rate(lookback_days=30)

        # Morning check stats
        morning_stats = tracker.get_signal_win_rate(
            lookback_days=90, signal_source="morning_check"
        )

        # Intraday stats
        intraday_stats = tracker.get_signal_win_rate(
            lookback_days=90, signal_source="intraday_monitor"
        )

        # Performance summary
        console.print("[bold white]PERFORMANCE SUMMARY (Last 90 Days)[/bold white]")
        console.print()

        perf_table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
        perf_table.add_column("Metric", style="bold white", width=25)
        perf_table.add_column("90 Days", justify="right", width=15)
        perf_table.add_column("30 Days", justify="right", width=15)

        perf_table.add_row(
            "Total Signals",
            f"{stats_90d.get('total_signals', 0)}",
            f"{stats_30d.get('total_signals', 0)}"
        )
        perf_table.add_row(
            "Signals Taken",
            f"{stats_90d.get('signals_taken', 0)}",
            f"{stats_30d.get('signals_taken', 0)}"
        )

        action_rate_90 = stats_90d.get('action_rate_pct', 0)
        action_rate_30 = stats_30d.get('action_rate_pct', 0)
        perf_table.add_row(
            "Action Rate",
            f"{action_rate_90:.1f}%",
            f"{action_rate_30:.1f}%"
        )

        win_rate_90 = stats_90d.get('win_rate_pct', 0)
        win_rate_30 = stats_30d.get('win_rate_pct', 0)
        win_color_90 = "green" if win_rate_90 > 60 else "yellow" if win_rate_90 > 50 else "red"
        win_color_30 = "green" if win_rate_30 > 60 else "yellow" if win_rate_30 > 50 else "red"

        perf_table.add_row(
            "Win Rate",
            f"[{win_color_90}]{win_rate_90:.1f}%[/{win_color_90}]",
            f"[{win_color_30}]{win_rate_30:.1f}%[/{win_color_30}]"
        )

        profit_90 = stats_90d.get('total_profit', 0)
        profit_30 = stats_30d.get('total_profit', 0)
        profit_color_90 = "green" if profit_90 > 0 else "red"
        profit_color_30 = "green" if profit_30 > 0 else "red"

        perf_table.add_row(
            "Total P&L",
            f"[{profit_color_90}]${profit_90:,.2f}[/{profit_color_90}]",
            f"[{profit_color_30}]${profit_30:,.2f}[/{profit_color_30}]"
        )

        avg_win = stats_90d.get('avg_win', 0)
        avg_loss = stats_90d.get('avg_loss', 0)
        perf_table.add_row(
            "Avg Win / Loss",
            f"[green]${avg_win:,.2f}[/green] / [red]${abs(avg_loss):,.2f}[/red]",
            "-"
        )

        profit_factor = stats_90d.get('profit_factor', 0)
        pf_color = "green" if profit_factor > 1.5 else "yellow" if profit_factor > 1.0 else "red"
        perf_table.add_row(
            "Profit Factor",
            f"[{pf_color}]{profit_factor:.2f}[/{pf_color}]",
            "-"
        )

        console.print(perf_table)
        console.print()

        # Source breakdown
        console.print("[bold white]BY SOURCE[/bold white]")
        console.print()

        source_table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
        source_table.add_column("Source", style="bold white", width=20)
        source_table.add_column("Signals", justify="right", width=10)
        source_table.add_column("Taken", justify="right", width=10)
        source_table.add_column("Win Rate", justify="right", width=12)
        source_table.add_column("Total P&L", justify="right", width=15)

        for source_name, source_stats in [
            ("Morning Check", morning_stats),
            ("Intraday Monitor", intraday_stats),
        ]:
            signals = source_stats.get('total_signals', 0)
            taken = source_stats.get('signals_taken', 0)
            win_rate = source_stats.get('win_rate_pct', 0)
            profit = source_stats.get('total_profit', 0)

            win_color = "green" if win_rate > 60 else "yellow" if win_rate > 50 else "red"
            profit_color = "green" if profit > 0 else "red"

            source_table.add_row(
                source_name,
                f"{signals}",
                f"{taken}",
                f"[{win_color}]{win_rate:.1f}%[/{win_color}]" if taken > 0 else "-",
                f"[{profit_color}]${profit:,.2f}[/{profit_color}]" if taken > 0 else "-"
            )

        console.print(source_table)
        console.print()

        # Recent signals
        console.print("[bold white]RECENT SIGNALS (Last 20)[/bold white]")
        console.print()

        recent = tracker.get_recent_signals(limit=20)

        if recent:
            recent_table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
            recent_table.add_column("Date", width=12)
            recent_table.add_column("Symbol", width=8)
            recent_table.add_column("Type", width=6)
            recent_table.add_column("Source", width=20)
            recent_table.add_column("Strength", justify="center", width=10)
            recent_table.add_column("Action", width=10)
            recent_table.add_column("Outcome", width=12)

            for sig in recent:
                signal_type = sig['signal_type']
                type_color = "green" if signal_type == "BUY" else "red" if signal_type == "SELL" else "yellow"

                strength = sig['signal_strength']
                strength_str = f"{strength:.0f}" if strength else "-"

                action_str = "[green]✓ Taken[/green]" if sig['action_taken'] else "[dim]Not taken[/dim]"

                outcome = sig['outcome'] or "-"
                outcome_color = "green" if outcome == "WIN" else "red" if outcome == "LOSS" else "yellow"

                recent_table.add_row(
                    str(sig['signal_date']),
                    sig['symbol'],
                    f"[{type_color}]{signal_type}[/{type_color}]",
                    sig['signal_source'],
                    strength_str,
                    action_str,
                    f"[{outcome_color}]{outcome}[/{outcome_color}]" if outcome != "-" else outcome
                )

            console.print(recent_table)
        else:
            console.print("[dim]No signals recorded yet[/dim]")

        console.print()

        # Missed opportunities
        console.print("[bold yellow]MISSED OPPORTUNITIES (Top 10)[/bold yellow]")
        console.print()

        missed = tracker.analyze_missed_opportunities(lookback_days=90)

        if missed:
            missed_table = Table(show_header=True, header_style="bold yellow", box=box.SIMPLE)
            missed_table.add_column("Date", width=12)
            missed_table.add_column("Symbol", width=8)
            missed_table.add_column("Type", width=6)
            missed_table.add_column("Price", justify="right", width=10)
            missed_table.add_column("Strength", justify="center", width=10)
            missed_table.add_column("Max Profit", justify="right", width=12)

            for m in missed:
                signal_type = m['signal_type']
                type_color = "green" if signal_type == "BUY" else "red"

                max_profit = m.get('max_profit_potential', 0) or 0
                profit_color = "green" if max_profit > 0 else "red"

                missed_table.add_row(
                    str(m['signal_date']),
                    m['symbol'],
                    f"[{type_color}]{signal_type}[/{type_color}]",
                    f"${m['price_at_signal']:.2f}" if m['price_at_signal'] else "-",
                    f"{m['signal_strength']:.0f}" if m['signal_strength'] else "-",
                    f"[{profit_color}]${max_profit:,.2f}[/{profit_color}]"
                )

            console.print(missed_table)
            console.print()
            console.print("[dim]Note: Max profit shows what could have been gained if signal was taken[/dim]")
        else:
            console.print("[dim]No missed opportunities data available yet[/dim]")

        console.print()

    console.print("[bold cyan]" + "=" * 80 + "[/bold cyan]")
    console.print()


if __name__ == "__main__":
    main()
