"""Console chart utilities for displaying price data in terminal."""

from datetime import datetime
from typing import Any

try:
    import asciichartpy as asciichart
    ASCIICHART_AVAILABLE = True
except ImportError:
    ASCIICHART_AVAILABLE = False

try:
    import plotille
    PLOTILLE_AVAILABLE = True
except ImportError:
    PLOTILLE_AVAILABLE = False


def plot_price_chart(
    dates: list[datetime],
    prices: list[float],
    sma_20: list[float] | None = None,
    sma_50: list[float] | None = None,
    sma_200: list[float] | None = None,
    title: str = "Price Chart",
    height: int = 15,
    width: int = 80,
) -> str:
    """
    Generate ASCII price chart with SMAs.

    Args:
        dates: List of dates
        prices: List of closing prices
        sma_20: Optional 20-day SMA
        sma_50: Optional 50-day SMA
        sma_200: Optional 200-day SMA
        title: Chart title
        height: Chart height in lines
        width: Chart width in characters

    Returns:
        ASCII chart as string
    """
    if not prices:
        return "No data to plot"

    if ASCIICHART_AVAILABLE:
        return _plot_asciichart(dates, prices, sma_20, sma_50, sma_200, title, height)
    elif PLOTILLE_AVAILABLE:
        return _plot_plotille(dates, prices, sma_20, sma_50, sma_200, title, height, width)
    else:
        return _plot_simple_sparkline(prices, title)


def _plot_asciichart(
    dates: list[datetime],
    prices: list[float],
    sma_20: list[float] | None,
    sma_50: list[float] | None,
    sma_200: list[float] | None,
    title: str,
    height: int,
) -> str:
    """Plot using asciichartpy (simpler, cleaner output)."""
    lines = [title, "=" * len(title), ""]

    # Configure chart
    config: dict[str, Any] = {
        "height": height,
        "format": "{:8.2f}",
    }

    # Plot price
    chart = asciichart.plot(prices, config)
    lines.append(chart)

    # Add legend
    legend_parts = [f"Close (${prices[-1]:.2f})"]
    if sma_20:
        legend_parts.append(f"SMA20 (${sma_20[-1]:.2f})")
    if sma_50:
        legend_parts.append(f"SMA50 (${sma_50[-1]:.2f})")
    if sma_200:
        legend_parts.append(f"SMA200 (${sma_200[-1]:.2f})")

    lines.append("")
    lines.append(" | ".join(legend_parts))
    lines.append(f"Period: {dates[0].strftime('%Y-%m-%d')} to {dates[-1].strftime('%Y-%m-%d')}")

    return "\n".join(lines)


def _plot_plotille(
    dates: list[datetime],
    prices: list[float],
    sma_20: list[float] | None,
    sma_50: list[float] | None,
    sma_200: list[float] | None,
    title: str,
    height: int,
    width: int,
) -> str:
    """Plot using plotille (more features, multi-line support)."""
    fig = plotille.Figure()
    fig.width = width
    fig.height = height
    fig.set_x_limits(min_=0, max_=len(prices) - 1)
    fig.set_y_limits(min_=min(prices) * 0.95, max_=max(prices) * 1.05)

    # Add price line
    x_values = list(range(len(prices)))
    fig.plot(x_values, prices, lc="cyan", label="Close")

    # Add SMAs
    if sma_20 and len(sma_20) == len(prices):
        fig.plot(x_values, sma_20, lc="yellow", label="SMA20")
    if sma_50 and len(sma_50) == len(prices):
        fig.plot(x_values, sma_50, lc="magenta", label="SMA50")
    if sma_200 and len(sma_200) == len(prices):
        fig.plot(x_values, sma_200, lc="blue", label="SMA200")

    chart = fig.show(legend=True)

    lines = [title, "=" * len(title), "", chart, ""]
    lines.append(f"Period: {dates[0].strftime('%Y-%m-%d')} to {dates[-1].strftime('%Y-%m-%d')}")

    return "\n".join(lines)


def _plot_simple_sparkline(prices: list[float], title: str) -> str:
    """Fallback: Simple sparkline using Unicode block characters."""
    if not prices:
        return "No data"

    # Normalize prices to 0-7 range for block characters
    min_price = min(prices)
    max_price = max(prices)
    price_range = max_price - min_price

    if price_range == 0:
        normalized = [4] * len(prices)
    else:
        normalized = [int(((p - min_price) / price_range) * 7) for p in prices]

    # Unicode block characters (8 levels)
    blocks = [" ", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]

    sparkline = "".join(blocks[n] for n in normalized)

    lines = [
        title,
        "=" * len(title),
        "",
        sparkline,
        "",
        f"Range: ${min_price:.2f} - ${max_price:.2f}",
        f"Current: ${prices[-1]:.2f}",
    ]

    return "\n".join(lines)


def plot_volume_bars(volumes: list[float], max_bars: int = 50) -> str:
    """
    Plot volume bars using Unicode characters.

    Args:
        volumes: List of volume values
        max_bars: Maximum number of bars to show

    Returns:
        ASCII volume chart
    """
    if not volumes:
        return "No volume data"

    # Take last N bars
    volumes = volumes[-max_bars:]

    # Normalize to 0-20 range
    max_vol = max(volumes)
    if max_vol == 0:
        normalized = [0] * len(volumes)
    else:
        normalized = [int((v / max_vol) * 20) for v in volumes]

    # Create vertical bars
    lines = []
    for i in range(20, -1, -1):
        line = ""
        for n in normalized:
            if n >= i:
                line += "█"
            else:
                line += " "
        lines.append(line)

    # Add baseline
    lines.append("─" * len(volumes))

    # Add volume scale
    lines.append(f"Max: {max_vol:,.0f}")

    return "\n".join(lines)


def plot_indicator_line(
    values: list[float],
    title: str = "Indicator",
    threshold_upper: float | None = None,
    threshold_lower: float | None = None,
    height: int = 10,
) -> str:
    """
    Plot a single indicator (RSI, MACD, etc).

    Args:
        values: Indicator values
        title: Chart title
        threshold_upper: Upper threshold line (e.g., RSI 70)
        threshold_lower: Lower threshold line (e.g., RSI 30)
        height: Chart height

    Returns:
        ASCII chart
    """
    if not values:
        return f"{title}: No data"

    if ASCIICHART_AVAILABLE:
        config: dict[str, Any] = {
            "height": height,
            "format": "{:6.1f}",
        }
        chart = asciichart.plot(values, config)

        lines = [title, "=" * len(title), "", chart, ""]
        lines.append(f"Current: {values[-1]:.2f}")

        if threshold_upper:
            lines.append(f"Overbought: >{threshold_upper:.0f}")
        if threshold_lower:
            lines.append(f"Oversold: <{threshold_lower:.0f}")

        return "\n".join(lines)
    else:
        return _plot_simple_sparkline(values, title)
