"""
Morning Check - Pre-market analysis at 9 AM before market opens.

Shows:
- What happened overnight (pre-market movers)
- Earnings reports today
- Your holdings status from yesterday's close
- Watchlist opportunities for today
"""

import sys
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

    # Section 0: MARKET DIRECTION
    console.print("\n[bold bright_white]>> MARKET DIRECTION[/bold bright_white]", style="on blue")

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

        # Determine overall market condition
        spy_signal = market_status.get("SPY", {}).get("signal", TradingSignal.DONT_TRADE)
        qqq_signal = market_status.get("QQQ", {}).get("signal", TradingSignal.DONT_TRADE)

        if spy_signal == TradingSignal.BUY and qqq_signal == TradingSignal.BUY:
            console.print(Panel(">> [bold green]BULLISH[/bold green] - Good time to buy stocks", border_style="green"))
        elif spy_signal == TradingSignal.SELL or qqq_signal == TradingSignal.SELL:
            console.print(Panel(">> [bold red]BEARISH[/bold red] - Avoid new buys, consider taking profits", border_style="red"))
        else:
            console.print(Panel(">> [bold yellow]NEUTRAL[/bold yellow] - Be selective with new positions", border_style="yellow"))

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
    print("=" * 100)
    print("SECTION 2: WATCHLIST - New Opportunities (Ranked by Score)")
    print("=" * 100)
    print()

    print(f"{'Ticker':<8} {'Close':<10} {'Signal':<12} {'Date':<12} {'Conf':<7} {'R/R':<7} {'Score':<7} {'Upside':<8} {'Risk':<8} {'Opportunity':<30}")
    print("-" * 120)

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

                # Combined score: confidence × risk/reward ratio
                # Cap R/R at 5 to avoid extreme outliers
                capped_rr = min(rr_ratio, 5.0)
                score = signal.confidence * capped_rr

                buy_candidates.append({
                    "ticker": ticker,
                    "price": close_price,
                    "confidence": signal.confidence,
                    "reasoning": signal.reasoning,
                    "signal_date": signal_date,
                    "rr_ratio": rr_ratio,
                    "upside": upside,
                    "downside": downside,
                    "score": score,
                })

    # Rank by score (highest first)
    buy_candidates.sort(key=lambda x: x["score"], reverse=True)

    if buy_candidates:
        for candidate in buy_candidates:
            rr_display = f"{candidate['rr_ratio']:.1f}" if candidate['rr_ratio'] else "N/A"
            upside_display = f"+{candidate['upside']:.1f}%" if candidate['upside'] else "N/A"
            downside_display = f"-{candidate['downside']:.1f}%" if candidate['downside'] else "N/A"

            print(
                f"{candidate['ticker']:<8} "
                f"${candidate['price']:<9.2f} "
                f"BUY          "
                f"{candidate['signal_date']:<12} "
                f"{candidate['confidence']:<6.0%} "
                f"{rr_display:<7} "
                f"{candidate['score']:<6.2f} "
                f"{upside_display:<8} "
                f"{downside_display:<8} "
                f"{candidate['reasoning'][:28]}"
            )
    else:
        print("No buy signals on watchlist - sit tight today")

    print()

    # Section 3: MORNING SUMMARY
    print("=" * 100)
    print("SECTION 3: TODAY'S GAME PLAN")
    print("=" * 100)
    print()

    print(f"Portfolio Holdings:  {len(portfolio.positions)}")
    print(f"  - Need attention:  {len(consider_selling) + len(watch_today)}")
    print(f"  - Stable:          {len(portfolio.positions) - len(consider_selling) - len(watch_today)}")
    print()
    print(f"Watchlist:")
    print(f"  - Buy candidates:  {len(buy_candidates)}")
    print()

    print("ACTIONS FOR TODAY:")
    print("-" * 100)

    if consider_selling:
        print(f"\n1. REVIEW SELL SIGNALS ({len(consider_selling)} stocks)")
        for ticker, signal_date in consider_selling:
            print(f"   - {ticker}: Signal on {signal_date} - Check intraday at 3 PM")

    if buy_candidates:
        print(f"\n2. TOP BUY CANDIDATES - RANKED BY SCORE ({len(buy_candidates)} total)")
        for i, candidate in enumerate(buy_candidates[:5], 1):  # Top 5
            print(f"\n   #{i} {candidate['ticker']} - Score: {candidate['score']:.2f}")
            print(f"      Price: ${candidate['price']:.2f} | Confidence: {candidate['confidence']:.0%} | R/R: {candidate['rr_ratio']:.1f}")
            print(f"      Upside: +{candidate['upside']:.1f}% | Risk: -{candidate['downside']:.1f}%")
            print(f"      Signal: {candidate['signal_date']} - {candidate['reasoning'][:60]}")

            # Position sizing recommendation based on score
            if candidate['score'] >= 3.0:
                print(f"      -> STRONG BUY: Consider 30-40% of available capital")
            elif candidate['score'] >= 2.0:
                print(f"      -> GOOD BUY: Consider 20-30% of available capital")
            else:
                print(f"      -> WATCH: Wait for better setup or start small (10-15%)")

    if watch_today:
        print(f"\n3. MONITOR LOSERS ({len(watch_today)} stocks)")
        for ticker in watch_today:
            print(f"   - {ticker}: Watch for further weakness or reversal")

    if not consider_selling and not buy_candidates and not watch_today:
        print("\n! NO IMMEDIATE ACTION NEEDED")
        print("  - Portfolio is stable")
        print("  - No strong buy signals")
        print("  - Check again at 3 PM for intraday opportunities")

    print()
    print("=" * 100)
    print("NEXT STEPS:")
    print("=" * 100)
    print()
    print("1. Morning (now): Review this report")
    print("2. 12 PM - 1 PM: Quick check - any big moves?")
    print("3. 3 PM: Final decision")
    print("   .\\tasks.ps1 intraday")
    print("4. After hours: Update portfolio")
    print("   .\\tasks.ps1 update-daily")
    print()
    print(f"Report generated: {datetime.now().strftime('%I:%M %p ET')}")
    print("Data: Yesterday's closing prices")
    print("=" * 100)
    print()


if __name__ == "__main__":
    main()
