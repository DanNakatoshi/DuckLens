"""Display console charts for a ticker."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel

from src.data.storage.duckdb_manager import DuckDBManager
from src.utils.console_charts import plot_price_chart, plot_indicator_line


def main():
    """Show charts for a ticker."""
    console = Console()

    # Get ticker from command line or default to AAPL
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 90

    console.print(f"\n[cyan]Loading chart for {ticker} ({days} days)...[/cyan]\n")

    db = DuckDBManager()

    # Get price data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    query = """
        SELECT
            sp.timestamp::DATE as date,
            sp.close,
            ti.sma_20,
            ti.sma_50,
            ti.sma_200,
            ti.rsi_14,
            ti.macd,
            sp.volume
        FROM stock_prices sp
        LEFT JOIN technical_indicators ti
            ON sp.symbol = ti.symbol
            AND sp.timestamp::DATE = ti.timestamp::DATE
        WHERE sp.symbol = ?
            AND sp.timestamp >= ?
            AND sp.timestamp <= ?
        ORDER BY sp.timestamp
    """

    with db.get_connection() as conn:
        results = conn.execute(query, [ticker, start_date, end_date]).fetchall()

    if not results:
        console.print(f"[red]No data found for {ticker}[/red]")
        return

    # Extract data
    dates = [r[0] for r in results]
    prices = [float(r[1]) for r in results]
    sma_20 = [float(r[2]) if r[2] else None for r in results]
    sma_50 = [float(r[3]) if r[3] else None for r in results]
    sma_200 = [float(r[4]) if r[4] else None for r in results]
    rsi = [float(r[5]) if r[5] else None for r in results]
    macd = [float(r[6]) if r[6] else None for r in results]
    volumes = [float(r[7]) if r[7] else 0 for r in results]

    # Filter out None values for SMAs
    sma_20_clean = [s for s in sma_20 if s is not None]
    sma_50_clean = [s for s in sma_50 if s is not None]
    sma_200_clean = [s for s in sma_200 if s is not None]

    # Align SMAs with prices (pad with prices if needed)
    def pad_sma(sma_list: list, target_len: int) -> list[float] | None:
        if not sma_list:
            return None
        if len(sma_list) < target_len:
            # Pad at beginning with first value
            padding = [sma_list[0]] * (target_len - len(sma_list))
            return padding + sma_list
        return sma_list

    sma_20_padded = pad_sma(sma_20_clean, len(prices))
    sma_50_padded = pad_sma(sma_50_clean, len(prices))
    sma_200_padded = pad_sma(sma_200_clean, len(prices))

    # Plot price chart
    price_chart = plot_price_chart(
        dates=dates,
        prices=prices,
        sma_20=sma_20_padded,
        sma_50=sma_50_padded,
        sma_200=sma_200_padded,
        title=f"{ticker} Price Chart",
        height=15,
        width=100,
    )

    console.print(Panel(price_chart, title=f"[bold cyan]{ticker} - Price & Moving Averages[/bold cyan]"))

    # Plot RSI if available
    rsi_clean = [r for r in rsi if r is not None]
    if rsi_clean:
        rsi_chart = plot_indicator_line(
            values=rsi_clean,
            title=f"{ticker} RSI (14-day)",
            threshold_upper=70.0,
            threshold_lower=30.0,
            height=8,
        )
        console.print(Panel(rsi_chart, title="[bold yellow]RSI Indicator[/bold yellow]"))

    # Plot MACD if available
    macd_clean = [m for m in macd if m is not None]
    if macd_clean:
        macd_chart = plot_indicator_line(
            values=macd_clean,
            title=f"{ticker} MACD",
            height=8,
        )
        console.print(Panel(macd_chart, title="[bold magenta]MACD Indicator[/bold magenta]"))

    # Current values
    console.print("\n[bold green]Current Values:[/bold green]")
    console.print(f"  Price:   ${prices[-1]:.2f}")
    if sma_20_padded:
        console.print(f"  SMA 20:  ${sma_20_padded[-1]:.2f}")
    if sma_50_padded:
        console.print(f"  SMA 50:  ${sma_50_padded[-1]:.2f}")
    if sma_200_padded:
        console.print(f"  SMA 200: ${sma_200_padded[-1]:.2f}")
    if rsi_clean:
        console.print(f"  RSI:     {rsi_clean[-1]:.1f}")
    if macd_clean:
        console.print(f"  MACD:    {macd_clean[-1]:.2f}")

    console.print()


if __name__ == "__main__":
    main()
