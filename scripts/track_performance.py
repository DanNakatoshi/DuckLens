"""
Track account performance vs market and path to $1M.

Shows:
- Balance history over time
- Performance vs SPY (market benchmark)
- Monthly/weekly progress tracking
- Alpha generation (beating the market)
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from src.data.storage.market_data_db import MarketDataDB

console = Console()


def main():
    """Show performance tracking dashboard."""

    console.print()
    console.print(Panel("[bold cyan]PERFORMANCE TRACKING - Journey to $1M[/bold cyan]", border_style="cyan", box=box.DOUBLE))
    console.print()

    with MarketDataDB() as db:
        # Get all balance history
        balances = db.conn.execute("""
            SELECT balance_date, total_value, cash_balance, portfolio_value,
                   spy_price, spy_return_pct, account_return_pct, notes
            FROM account_balance
            ORDER BY balance_date ASC
        """).fetchall()

        if not balances:
            console.print("[yellow]No balance history found[/yellow]")
            console.print("[dim]Add balances with: .\\tasks.ps1 update-cash[/dim]")
            console.print()
            return

        # Convert to list of dicts
        history = []
        for row in balances:
            date, total, cash, portfolio, spy_price, spy_return, acc_return, notes = row
            # Convert date to string if it's a date object
            if hasattr(date, 'strftime'):
                date_str = date.strftime("%Y-%m-%d")
            else:
                date_str = str(date)

            history.append({
                'date': date_str,
                'total': float(total),
                'cash': float(cash),
                'portfolio': float(portfolio),
                'spy_price': float(spy_price) if spy_price else None,
                'spy_return': float(spy_return) if spy_return else None,
                'account_return': float(acc_return) if acc_return else None,
                'notes': notes
            })

        # Summary stats
        first = history[0]
        latest = history[-1]

        days_tracked = (datetime.strptime(latest['date'], "%Y-%m-%d") -
                       datetime.strptime(first['date'], "%Y-%m-%d")).days

        total_return = ((latest['total'] - first['total']) / first['total'] * 100) if first['total'] > 0 else 0

        # Calculate alpha (excess return over SPY)
        alpha = None
        if latest['spy_return'] is not None and latest['account_return'] is not None:
            alpha = latest['account_return'] - latest['spy_return']

        console.print("[bold cyan]>> PERFORMANCE SUMMARY[/bold cyan]")
        console.print()

        summary_table = Table(show_header=False, box=box.ROUNDED, border_style="bright_blue")
        summary_table.add_column("Metric", style="bold white", width=30)
        summary_table.add_column("Value", style="bright_white", width=25)

        summary_table.add_row("Tracking Period", f"{days_tracked} days ({days_tracked/30:.1f} months)")
        summary_table.add_row("Start Date", first['date'])
        summary_table.add_row("Latest Date", latest['date'])
        summary_table.add_row("", "")
        summary_table.add_row("Starting Balance", f"${first['total']:,.2f}")
        summary_table.add_row("Current Balance", f"[bold green]${latest['total']:,.2f}[/bold green]")
        summary_table.add_row("Gain/Loss", f"[{'green' if total_return >= 0 else 'red'}]{total_return:+.2f}%[/{'green' if total_return >= 0 else 'red'}]")

        if alpha is not None:
            alpha_color = "green" if alpha > 0 else "red"
            summary_table.add_row("", "")
            summary_table.add_row("Your Return", f"[bold]{latest['account_return']:+.2f}%[/bold]")
            summary_table.add_row("SPY Return", f"{latest['spy_return']:+.2f}%")
            summary_table.add_row("Alpha (Excess Return)", f"[bold {alpha_color}]{alpha:+.2f}%[/bold {alpha_color}]")

            if alpha > 0:
                summary_table.add_row("Status", "[bold green]BEATING THE MARKET[/bold green]")
            else:
                summary_table.add_row("Status", "[bold red]UNDERPERFORMING SPY[/bold red]")

        console.print(summary_table)
        console.print()

        # Balance history table
        console.print("[bold cyan]>> BALANCE HISTORY[/bold cyan]")
        console.print()

        history_table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
        history_table.add_column("Date", style="white", width=12)
        history_table.add_column("Total Value", justify="right", style="bright_white", width=15)
        history_table.add_column("Change", justify="right", width=12)
        history_table.add_column("Account %", justify="right", width=12)
        history_table.add_column("SPY %", justify="right", width=12)
        history_table.add_column("Alpha", justify="right", width=12)
        history_table.add_column("Notes", style="dim", width=30)

        prev_total = None
        for entry in history:
            # Calculate change from previous entry
            change_str = ""
            if prev_total:
                change_pct = ((entry['total'] - prev_total) / prev_total * 100)
                change_color = "green" if change_pct >= 0 else "red"
                change_str = f"[{change_color}]{change_pct:+.2f}%[/{change_color}]"

            acc_return_str = f"{entry['account_return']:+.2f}%" if entry['account_return'] is not None else "N/A"
            spy_return_str = f"{entry['spy_return']:+.2f}%" if entry['spy_return'] is not None else "N/A"

            alpha_str = ""
            if entry['account_return'] is not None and entry['spy_return'] is not None:
                alpha_val = entry['account_return'] - entry['spy_return']
                alpha_color = "green" if alpha_val > 0 else "red"
                alpha_str = f"[{alpha_color}]{alpha_val:+.2f}%[/{alpha_color}]"
            else:
                alpha_str = "N/A"

            notes_short = (entry['notes'][:27] + "...") if entry['notes'] and len(entry['notes']) > 30 else (entry['notes'] or "")

            history_table.add_row(
                entry['date'],
                f"${entry['total']:,.2f}",
                change_str,
                acc_return_str,
                spy_return_str,
                alpha_str,
                notes_short
            )

            prev_total = entry['total']

        console.print(history_table)
        console.print()

        # Monthly/Weekly tracking
        console.print("[bold cyan]>> TIME-BASED TRACKING[/bold cyan]")
        console.print()

        # Calculate weekly returns (if we have enough data)
        if days_tracked >= 7:
            # Get entries from last 7, 14, 30, 60, 90 days
            today = datetime.strptime(latest['date'], "%Y-%m-%d")

            timeframes = [
                ('1 Week', 7),
                ('2 Weeks', 14),
                ('1 Month', 30),
                ('2 Months', 60),
                ('3 Months', 90)
            ]

            timeframe_table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
            timeframe_table.add_column("Period", style="white", width=15)
            timeframe_table.add_column("Account Return", justify="right", width=18)
            timeframe_table.add_column("SPY Return", justify="right", width=18)
            timeframe_table.add_column("Alpha", justify="right", width=15)
            timeframe_table.add_column("Status", width=20)

            for period_name, days_back in timeframes:
                target_date = today - timedelta(days=days_back)

                # Find closest balance entry to this date
                closest = None
                min_diff = float('inf')

                for entry in history:
                    entry_date = datetime.strptime(entry['date'], "%Y-%m-%d")
                    diff = abs((entry_date - target_date).days)
                    if diff < min_diff:
                        min_diff = diff
                        closest = entry

                if closest and min_diff <= 7:  # Only if within 7 days
                    account_gain = ((latest['total'] - closest['total']) / closest['total'] * 100) if closest['total'] > 0 else 0

                    spy_gain = None
                    period_alpha = None

                    if closest['spy_price'] and latest['spy_price']:
                        spy_gain = ((latest['spy_price'] - closest['spy_price']) / closest['spy_price'] * 100)
                        period_alpha = account_gain - spy_gain

                    acc_color = "green" if account_gain >= 0 else "red"
                    spy_str = f"{spy_gain:+.2f}%" if spy_gain is not None else "N/A"

                    alpha_str = ""
                    status_str = ""
                    if period_alpha is not None:
                        alpha_color = "green" if period_alpha > 0 else "red"
                        alpha_str = f"[{alpha_color}]{period_alpha:+.2f}%[/{alpha_color}]"
                        status_str = f"[bold {alpha_color}]{'BEATING' if period_alpha > 0 else 'LAGGING'}[/bold {alpha_color}]"
                    else:
                        alpha_str = "N/A"
                        status_str = ""

                    timeframe_table.add_row(
                        period_name,
                        f"[{acc_color}]{account_gain:+.2f}%[/{acc_color}]",
                        spy_str,
                        alpha_str,
                        status_str
                    )

            console.print(timeframe_table)
            console.print()

        # Progress to $1M
        target = 1_000_000
        progress_pct = (latest['total'] / target * 100)
        remaining = target - latest['total']

        console.print("[bold cyan]>> PATH TO $1M[/bold cyan]")
        console.print()

        # Calculate required return
        if latest['total'] > 0:
            required_return = ((target / latest['total']) - 1) * 100

            # Estimate time to $1M based on current performance
            if days_tracked >= 30 and total_return > 0:
                # Annualized return
                annual_return = (total_return / days_tracked * 365)

                import math
                if annual_return > 0:
                    years_to_1m = math.log(target / latest['total']) / math.log(1 + (annual_return / 100))
                else:
                    years_to_1m = None
            else:
                annual_return = None
                years_to_1m = None

            progress_table = Table(show_header=False, box=box.ROUNDED, border_style="bright_green")
            progress_table.add_column("Metric", style="bold white", width=30)
            progress_table.add_column("Value", style="bright_white", width=25)

            progress_table.add_row("Current Balance", f"[bold green]${latest['total']:,.2f}[/bold green]")
            progress_table.add_row("Target", f"[bold yellow]${target:,.2f}[/bold yellow]")
            progress_table.add_row("Remaining", f"${remaining:,.2f}")
            progress_table.add_row("Progress", f"[bold cyan]{progress_pct:.2f}%[/bold cyan]")
            progress_table.add_row("Required Return", f"{required_return:,.1f}%")

            if annual_return is not None:
                progress_table.add_row("", "")
                progress_table.add_row("Your Annualized Return", f"[bold]{annual_return:+.2f}%[/bold]")

                if years_to_1m is not None and years_to_1m > 0:
                    progress_table.add_row("Est. Time to $1M", f"[bold yellow]{years_to_1m:.1f} years[/bold yellow]")

                    # Compare to baseline (50% annual)
                    baseline_years = math.log(target / latest['total']) / math.log(1.5)
                    if years_to_1m < baseline_years:
                        progress_table.add_row("Status", "[bold green]AHEAD OF SCHEDULE[/bold green]")
                    else:
                        progress_table.add_row("Status", "[bold yellow]ON TRACK (50% baseline)[/bold yellow]")

            console.print(progress_table)
            console.print()

        # Recommendations
        console.print("[bold cyan]>> TRACKING RECOMMENDATIONS[/bold cyan]")
        console.print()

        if len(history) == 1:
            console.print("[yellow]! Add more balance snapshots to see trends[/yellow]")
            console.print()
            console.print("  Recommended frequency:")
            console.print("  - [bold]Weekly:[/bold] Every Friday after market close")
            console.print("  - [bold]Monthly:[/bold] Last trading day of each month")
            console.print("  - [bold]After major trades:[/bold] When you make significant position changes")
            console.print()
        elif days_tracked < 30:
            console.print("[yellow]! You're just getting started - keep tracking![/yellow]")
            console.print()
            console.print("  Come back in 30 days to see meaningful trends")
            console.print()
        else:
            # Give specific feedback
            if alpha and alpha > 5:
                console.print("[bold green]EXCELLENT! You're significantly beating the market (+{:.1f}%)[/bold green]".format(alpha))
                console.print("  >> Keep doing what you're working!")
            elif alpha and alpha > 0:
                console.print("[green]GOOD! You're beating the market (+{:.1f}%)[/green]".format(alpha))
                console.print("  >> Continue following your strategy")
            elif alpha and alpha > -5:
                console.print("[yellow]CLOSE! You're slightly behind SPY ({:.1f}%)[/yellow]".format(alpha))
                console.print("  >> Review your trades - are you cutting losses fast enough?")
            elif alpha:
                console.print("[red]ATTENTION! You're significantly behind SPY ({:.1f}%)[/red]".format(alpha))
                console.print("  >> Review strategy execution:")
                console.print("     - Are you following the signals?")
                console.print("     - Are you using 2x leverage on high-confidence setups?")
                console.print("     - Are you cutting losses fast (death cross = sell)?")

            console.print()

        console.print("=" * 100)
        console.print()
        console.print("[dim]Tip: Update your balance weekly or monthly to track progress[/dim]")
        console.print("[dim]     Run: .\\tasks.ps1 update-cash[/dim]")
        console.print()


if __name__ == "__main__":
    main()
