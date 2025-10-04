"""Run strategy backtest and compare different approaches."""

import sys
from datetime import datetime, timedelta, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from src.config.tickers import TIER_2_STOCKS
from src.backtest.strategy_backtest import StrategyBacktest

console = Console()


def main():
    """Run backtest comparison."""
    console.print("\n[bold cyan]PORTFOLIO REBALANCING STRATEGY BACKTEST[/bold cyan]")
    console.print()

    # Setup
    initial_capital = 30000.0
    end_date = date.today()
    start_date = end_date - timedelta(days=365)  # 1 year backtest

    watchlist = [t.symbol for t in TIER_2_STOCKS[:20]]

    console.print(f"[bold]Test Period:[/bold] {start_date} to {end_date}")
    console.print(f"[bold]Initial Capital:[/bold] ${initial_capital:,.2f}")
    console.print(f"[bold]Watchlist:[/bold] {len(watchlist)} stocks")
    console.print()
    console.print("[dim]Running backtest... this may take a few minutes[/dim]")
    console.print()

    # Run backtest
    backtest = StrategyBacktest(initial_capital=initial_capital)

    try:
        results = backtest.compare_strategies(start_date, end_date, watchlist)

        # Display results
        console.print("[bold white]STRATEGY COMPARISON RESULTS[/bold white]")
        console.print()

        results_table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
        results_table.add_column("Strategy", style="bold white", width=25)
        results_table.add_column("Final Value", justify="right", width=15)
        results_table.add_column("Return %", justify="right", width=12)
        results_table.add_column("vs SPY", justify="right", width=12)
        results_table.add_column("Max DD", justify="right", width=10)
        results_table.add_column("Sharpe", justify="right", width=10)
        results_table.add_column("Trades", justify="right", width=8)

        strategies = [
            ("Buy & Hold", results["buy_and_hold"]),
            ("Monthly (No Margin)", results["monthly_no_margin"]),
            ("Weekly (No Margin)", results["weekly_no_margin"]),
            ("Monthly (With Margin)", results["monthly_with_margin"]),
        ]

        best_return = max(s[1]["total_return_pct"] for s in strategies)

        for strategy_name, result in strategies:
            final_value = result["final_value"]
            total_return = result["total_return_pct"]
            alpha = result["alpha"]
            max_dd = result["max_drawdown_pct"]
            sharpe = result["sharpe_ratio"]
            trades = result["total_trades"]

            # Color coding
            return_color = "green" if total_return > 0 else "red"
            alpha_color = "green" if alpha > 0 else "red"
            sharpe_color = "green" if sharpe > 1.0 else "yellow" if sharpe > 0.5 else "red"

            # Highlight best strategy
            style = "bold" if total_return == best_return else ""

            results_table.add_row(
                strategy_name,
                f"[{return_color}]${final_value:,.2f}[/{return_color}]",
                f"[{return_color}]{total_return:+.2f}%[/{return_color}]",
                f"[{alpha_color}]{alpha:+.2f}%[/{alpha_color}]",
                f"{max_dd:.2f}%",
                f"[{sharpe_color}]{sharpe:.2f}[/{sharpe_color}]",
                f"{trades}",
                style=style
            )

        console.print(results_table)
        console.print()

        # Detailed stats for best strategy
        best_strategy_name, best_result = max(
            strategies, key=lambda x: x[1]["total_return_pct"]
        )

        console.print(f"[bold green]BEST STRATEGY: {best_strategy_name}[/bold green]")
        console.print()

        detail_table = Table(show_header=False, box=box.SIMPLE)
        detail_table.add_column("Metric", style="bold white", width=25)
        detail_table.add_column("Value", width=20)

        detail_table.add_row("Initial Capital", f"${best_result['initial_capital']:,.2f}")
        detail_table.add_row("Final Value", f"${best_result['final_value']:,.2f}")
        detail_table.add_row("Total Gain", f"${best_result['final_value'] - best_result['initial_capital']:,.2f}")
        detail_table.add_row("Total Return", f"{best_result['total_return_pct']:+.2f}%")
        detail_table.add_row("SPY Return", f"{best_result['spy_return_pct']:+.2f}%")
        detail_table.add_row("Alpha (Excess Return)", f"{best_result['alpha']:+.2f}%")
        detail_table.add_row("Max Drawdown", f"{best_result['max_drawdown_pct']:.2f}%")
        detail_table.add_row("Sharpe Ratio", f"{best_result['sharpe_ratio']:.2f}")
        detail_table.add_row("Total Trades", f"{best_result['total_trades']}")
        detail_table.add_row("Win Rate", f"{best_result['win_rate_pct']:.1f}%")
        detail_table.add_row("Avg Holding Days", f"{best_result['avg_holding_days']:.0f}")
        detail_table.add_row("Rebalances", f"{best_result['rebalance_count']}")

        console.print(detail_table)
        console.print()

        # Recent trades
        console.print("[bold white]RECENT TRADES (Last 10)[/bold white]")
        console.print()

        if best_result["trades"]:
            trades_table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
            trades_table.add_column("Date", width=12)
            trades_table.add_column("Action", width=6)
            trades_table.add_column("Symbol", width=8)
            trades_table.add_column("Qty", justify="right", width=6)
            trades_table.add_column("Price", justify="right", width=10)
            trades_table.add_column("Value", justify="right", width=12)
            trades_table.add_column("Reason", width=35)

            for trade in best_result["trades"][-10:]:
                action_color = "green" if trade["action"] == "BUY" else "red"

                trades_table.add_row(
                    str(trade["date"]),
                    f"[{action_color}]{trade['action']}[/{action_color}]",
                    trade["symbol"],
                    f"{trade['quantity']}",
                    f"${trade['price']:.2f}",
                    f"${trade['value']:,.2f}",
                    trade["reason"][:33]
                )

            console.print(trades_table)
        else:
            console.print("[dim]No trades executed[/dim]")

        console.print()

        # Recommendations
        console.print("[bold yellow]RECOMMENDATIONS[/bold yellow]")
        console.print()

        if best_result["alpha"] > 5:
            console.print("[green]✓ Strategy shows strong alpha - consider implementing live[/green]")
        elif best_result["alpha"] > 0:
            console.print("[yellow]⚠ Strategy shows positive alpha but modest - monitor and optimize[/yellow]")
        else:
            console.print("[red]✗ Strategy underperforms SPY - needs optimization or avoid[/red]")

        if best_result["sharpe_ratio"] > 1.5:
            console.print("[green]✓ Excellent risk-adjusted returns (Sharpe > 1.5)[/green]")
        elif best_result["sharpe_ratio"] > 1.0:
            console.print("[yellow]⚠ Good risk-adjusted returns (Sharpe > 1.0)[/yellow]")
        else:
            console.print("[red]✗ Poor risk-adjusted returns - too volatile[/red]")

        if best_result["win_rate_pct"] > 60:
            console.print("[green]✓ Strong win rate (>{60}%)[/green]")
        elif best_result["win_rate_pct"] > 50:
            console.print("[yellow]⚠ Acceptable win rate (>50%)[/yellow]")
        else:
            console.print("[red]✗ Low win rate (<50%) - improve entry/exit logic[/red]")

        console.print()
        console.print("[bold cyan]" + "=" * 80 + "[/bold cyan]")
        console.print()

    except Exception as e:
        console.print(f"[red]Error running backtest: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")


if __name__ == "__main__":
    main()
