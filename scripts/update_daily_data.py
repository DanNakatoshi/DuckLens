"""Daily update script to fetch latest market data after market hours."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from src.config.tickers import TICKER_SYMBOLS
from src.data.collectors.fred_collector import FREDCollector
from src.data.collectors.polygon_collector import PolygonCollector
from src.data.storage.market_data_db import MarketDataDB
from src.portfolio.portfolio_manager import PortfolioManager
from src.models.enhanced_detector import EnhancedTrendDetector
from src.models.trend_detector import TradingSignal

# Use configured tickers
DEFAULT_TICKERS = TICKER_SYMBOLS


def update_ohlcv_data(tickers: list[str], days_back: int = 5) -> None:
    """
    Update OHLCV data for specified tickers.

    Args:
        tickers: List of ticker symbols
        days_back: Number of days to look back (to catch any missed days)
    """
    print(f"\n{'='*60}")
    print(f"Updating OHLCV data for {len(tickers)} tickers")
    print(f"Checking last {days_back} days for any gaps")
    print(f"{'='*60}\n")

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    with PolygonCollector() as collector, MarketDataDB() as db:
        total_new_records = 0
        updated_tickers = []

        for ticker in tickers:
            try:
                print(f"[{ticker}] Updating...", end=" ")

                # Fetch last few days to catch any gaps
                prices = collector.get_stock_prices(ticker, start_date, end_date)

                if prices:
                    count = db.insert_stock_prices(prices)
                    if count > 0:
                        total_new_records += count
                        updated_tickers.append(ticker)
                        latest_date = prices[-1].timestamp.date()
                        print(f"OK {count} records (latest: {latest_date})")
                    else:
                        print("OK Already up to date")
                else:
                    print("! No new data")

            except Exception as e:
                print(f"X Error: {e}")

        print(f"\n{'='*60}")
        print(f"OK OHLCV Update complete:")
        print(f"  Total new records: {total_new_records}")
        print(f"  Updated tickers: {len(updated_tickers)}")
        if updated_tickers:
            print(f"  {', '.join(updated_tickers)}")
        print(f"{'='*60}\n")


def update_short_interest(tickers: list[str]) -> None:
    """
    Update short interest data (bi-monthly).

    Args:
        tickers: List of ticker symbols
    """
    print(f"\n{'='*60}")
    print(f"Updating short interest (bi-monthly)")
    print(f"{'='*60}\n")

    with PolygonCollector() as collector, MarketDataDB() as db:
        total_new_records = 0

        for ticker in tickers:
            try:
                print(f"  {ticker}...", end=" ")

                # Fetch latest short interest (limit to last few records)
                response = collector.get_short_interest(
                    ticker=ticker, limit=5, sort="settlement_date.desc"
                )

                if response.results:
                    count = db.insert_short_interest(response.results)
                    total_new_records += count
                    if count > 0:
                        print(f"OK {count} new records")
                    else:
                        print("OK Up to date")
                else:
                    print("! No data")

            except Exception as e:
                print(f"X Error: {e}")

        print(f"\n  Total new short interest records: {total_new_records}")


def update_short_volume(tickers: list[str], days_back: int = 5) -> None:
    """
    Update short volume data (daily).

    Args:
        tickers: List of ticker symbols
        days_back: Number of days to check
    """
    print(f"\n{'='*60}")
    print(f"Updating short volume (daily)")
    print(f"{'='*60}\n")

    with PolygonCollector() as collector, MarketDataDB() as db:
        total_new_records = 0
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        for ticker in tickers:
            try:
                print(f"  {ticker}...", end=" ")
                ticker_count = 0

                # Check last few days
                current_date = start_date
                while current_date <= end_date:
                    date_str = current_date.strftime("%Y-%m-%d")

                    try:
                        response = collector.get_short_volume(
                            ticker=ticker, date=date_str, limit=1
                        )

                        if response.results:
                            count = db.insert_short_volume(response.results)
                            ticker_count += count
                    except Exception:
                        pass  # Date might not have data yet

                    current_date += timedelta(days=1)

                total_new_records += ticker_count
                if ticker_count > 0:
                    print(f"OK {ticker_count} new records")
                else:
                    print("OK Up to date")

            except Exception as e:
                print(f"X Error: {e}")

        print(f"\n  Total new short volume records: {total_new_records}")


def update_economic_indicators(days_back: int = 30) -> None:
    """
    Update economic indicators from FRED.

    Args:
        days_back: Number of days to look back (default 30 for monthly indicators)
    """
    import os

    print(f"\n{'='*60}")
    print(f"Updating economic indicators (FRED)")
    print(f"{'='*60}\n")

    # Check if FRED API key is configured
    if not os.getenv("FRED_API_KEY"):
        print("! FRED_API_KEY not configured - skipping economic data update")
        print("  To enable: Add FRED_API_KEY to your .env file")
        print("  Get free API key: https://fred.stlouisfed.org/")
        print(f"{'='*60}\n")
        return

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    try:
        collector = FREDCollector()
    except Exception as e:
        print(f"! Could not initialize FRED collector: {e}")
        print(f"{'='*60}\n")
        return

    with MarketDataDB() as db:
        total_new_records = 0
        updated_series = []

        print(f"Checking {len(collector.ECONOMIC_SERIES)} indicators...\n")

        for series_id, name in collector.ECONOMIC_SERIES.items():
            try:
                print(f"  {series_id:<15} {name[:35]:<35}", end=" ")

                # Check latest data in DB
                latest_date = db.get_latest_economic_date(series_id)

                if latest_date:
                    # Fetch only new data since latest date
                    fetch_start = datetime.combine(latest_date, datetime.min.time()) + timedelta(days=1)
                    if fetch_start >= end_date:
                        print("OK Up to date")
                        continue
                else:
                    # No existing data, fetch from start_date
                    fetch_start = start_date

                indicators = collector.get_economic_indicator(
                    series_id=series_id,
                    start_date=fetch_start,
                    end_date=end_date,
                )

                if indicators:
                    count = db.insert_economic_indicators(indicators)
                    if count > 0:
                        total_new_records += count
                        updated_series.append(series_id)
                        print(f"OK {count} new obs")
                    else:
                        print("OK Up to date")
                else:
                    print("! No data")

            except Exception as e:
                print(f"X Error: {str(e)[:30]}")
                continue

        print(f"\n{'='*60}")
        print(f"OK Economic indicators update complete:")
        print(f"  Total new observations: {total_new_records}")
        print(f"  Updated series: {len(updated_series)}")
        if updated_series and len(updated_series) <= 10:
            print(f"  {', '.join(updated_series)}")
        print(f"{'='*60}\n")


def show_watchlist_signals():
    """Show watchlist signals after data update."""
    print(f"\n{'='*60}")
    print("WATCHLIST SIGNALS (Today)")
    print(f"{'='*60}\n")

    from src.config.tickers import TIER_2_STOCKS

    with MarketDataDB() as db:
        detector = EnhancedTrendDetector(
            db=db,
            min_confidence=0.75,
            confirmation_days=1,
            long_only=True,
            log_trades=False,  # Don't log from watchlist
            block_earnings_window=3,
            volume_spike_threshold=3.0,
        )

        today = datetime.now()
        buy_signals = []
        sell_signals = []

        for ticker_meta in TIER_2_STOCKS:
            ticker = ticker_meta.symbol
            try:
                # Get latest price
                result = db.conn.execute(
                    """
                    SELECT close, timestamp
                    FROM stock_prices
                    WHERE symbol = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                    """,
                    [ticker]
                ).fetchone()

                if not result:
                    continue

                price, timestamp = result
                signal = detector.generate_signal(ticker, timestamp, price)

                if signal.signal == TradingSignal.BUY:
                    buy_signals.append({
                        'ticker': ticker,
                        'price': price,
                        'confidence': signal.confidence,
                        'reasoning': signal.reasoning
                    })
                elif signal.signal == TradingSignal.SELL:
                    sell_signals.append({
                        'ticker': ticker,
                        'price': price,
                        'confidence': signal.confidence,
                        'reasoning': signal.reasoning
                    })

            except Exception as e:
                continue

        if buy_signals:
            print(f"BUY SIGNALS ({len(buy_signals)}):")
            for s in buy_signals:
                print(f"  {s['ticker']:<6} ${s['price']:>8.2f}  ({s['confidence']:.0%} conf)")
                print(f"         {s['reasoning']}")
            print()

        if sell_signals:
            print(f"SELL SIGNALS ({len(sell_signals)}):")
            for s in sell_signals:
                print(f"  {s['ticker']:<6} ${s['price']:>8.2f}  ({s['confidence']:.0%} conf)")
                print(f"         {s['reasoning']}")
            print()

        if not buy_signals and not sell_signals:
            print("No strong signals today")
            print()


def show_portfolio_stats():
    """Show portfolio stats and recommendations."""
    print(f"\n{'='*60}")
    print("PORTFOLIO REVIEW")
    print(f"{'='*60}\n")

    manager = PortfolioManager()
    portfolio = manager.load_portfolio()

    if not portfolio.positions:
        print("No positions in portfolio")
        print("Run: .\\tasks.ps1 import-portfolio to import your positions")
        print()
        return

    with MarketDataDB() as db:
        detector = EnhancedTrendDetector(
            db=db,
            min_confidence=0.75,
            confirmation_days=1,
            long_only=True,
            log_trades=True,
            block_earnings_window=3,
            volume_spike_threshold=3.0,
        )

        total_value = portfolio.cash
        total_gain = 0.0
        winning_positions = []
        losing_positions = []
        recommendations = []

        print(f"Cash: ${portfolio.cash:,.2f}\n")
        print(f"{'Ticker':<8} {'Qty':<6} {'Cost':<10} {'Current':<10} {'P&L':<12} {'Signal':<10}")
        print("-" * 60)

        for ticker, pos in portfolio.positions.items():
            try:
                # Get current price
                result = db.conn.execute(
                    """
                    SELECT close, timestamp
                    FROM stock_prices
                    WHERE symbol = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                    """,
                    [ticker]
                ).fetchone()

                if not result:
                    current_price = pos.price_paid
                    signal_str = "NO DATA"
                else:
                    current_price, timestamp = result
                    signal = detector.generate_signal(ticker, timestamp, current_price)
                    signal_str = signal.signal.value

                position_value = pos.quantity * current_price
                gain = position_value - (pos.quantity * pos.price_paid)
                gain_pct = (gain / (pos.quantity * pos.price_paid)) * 100

                total_value += position_value
                total_gain += gain

                # Track wins vs losses
                if gain >= 0:
                    winning_positions.append((ticker, gain, gain_pct))
                else:
                    losing_positions.append((ticker, gain, gain_pct))

                print(f"{ticker:<8} {pos.quantity:<6} ${pos.price_paid:<9.2f} ${current_price:<9.2f} ${gain:>7.2f} ({gain_pct:>5.1f}%) {signal_str:<10}")

                if signal_str == "SELL":
                    recommendations.append(f"Consider SELL {ticker} (current signal: SELL)")

            except Exception as e:
                print(f"{ticker:<8} {pos.quantity:<6} ${pos.price_paid:<9.2f} ERROR")

        total_gain_pct = (total_gain / (total_value - total_gain - portfolio.cash)) * 100 if (total_value - total_gain - portfolio.cash) > 0 else 0

        print("-" * 60)
        print(f"Total Value: ${total_value:,.2f}")
        print(f"Total P&L:   ${total_gain:,.2f} ({total_gain_pct:.2f}%)")

        # Show win/loss breakdown
        total_wins = sum(g for _, g, _ in winning_positions)
        total_losses = sum(g for _, g, _ in losing_positions)
        print(f"\nWinners: {len(winning_positions)} positions (+${total_wins:,.2f})")
        print(f"Losers:  {len(losing_positions)} positions (${total_losses:,.2f})")

        if losing_positions:
            print(f"\nBIGGEST LOSSES (Cut Loss Review):")
            # Sort by $ loss (most negative first)
            for ticker, loss, loss_pct in sorted(losing_positions, key=lambda x: x[1])[:5]:
                print(f"  {ticker:<8} ${loss:>8.2f} ({loss_pct:>6.1f}%)")
        print()

        if recommendations:
            print("RECOMMENDATIONS:")
            for rec in recommendations:
                print(f"  - {rec}")
            print()


def update_portfolio_interactive():
    """Ask user if they have portfolio changes to update."""
    print(f"\n{'='*60}")
    print("PORTFOLIO UPDATE")
    print(f"{'='*60}\n")

    manager = PortfolioManager()
    portfolio = manager.load_portfolio()

    print("Do you have any portfolio changes to record? (y/n): ", end="")
    response = input().strip().lower()

    if response != 'y':
        print("Skipping portfolio update\n")
        return

    while True:
        print("\nWhat type of change?")
        print("  1. BUY (add shares)")
        print("  2. SELL (remove shares)")
        print("  3. Update cash")
        print("  4. Done")
        print("\nChoice: ", end="")

        choice = input().strip()

        if choice == '1':
            # BUY
            ticker = input("Ticker symbol: ").strip().upper()
            qty = int(input("Quantity: ").strip())
            price = float(input("Price paid per share: ").strip())
            notes = input("Notes (optional): ").strip()

            portfolio.add_position(ticker, qty, price, notes or "")
            manager.save_portfolio(portfolio)
            print(f"OK Added {qty} shares of {ticker} @ ${price:.2f}")

        elif choice == '2':
            # SELL
            ticker = input("Ticker symbol: ").strip().upper()
            qty = int(input("Quantity to sell: ").strip())
            price = float(input("Sale price per share: ").strip())
            notes = input("Notes (optional): ").strip()

            # Add proceeds to cash
            proceeds = qty * price
            portfolio.cash += proceeds
            portfolio.remove_position(ticker, qty)
            manager.save_portfolio(portfolio)
            print(f"OK Sold {qty} shares of {ticker} @ ${price:.2f} (Proceeds: ${proceeds:.2f})")

        elif choice == '3':
            # Update cash
            amount = float(input("New cash balance: ").strip())
            old_cash = portfolio.cash
            portfolio.cash = amount
            manager.save_portfolio(portfolio)
            print(f"OK Updated cash: ${old_cash:.2f} -> ${amount:.2f}")

        elif choice == '4':
            print("Portfolio update complete\n")
            break
        else:
            print("Invalid choice")


def print_update_summary():
    """Print summary of database contents after update."""
    print(f"\n{'='*60}")
    print("DATABASE SUMMARY")
    print(f"{'='*60}\n")

    with MarketDataDB() as db:
        stats = db.get_table_stats()

        for table_name, table_stats in stats.items():
            print(f"{table_name.upper().replace('_', ' ')}:")
            print(f"  Total Records: {table_stats['total_rows']:,}")
            print(f"  Unique Symbols: {table_stats.get('unique_symbols') or table_stats.get('unique_tickers')}")
            if table_stats['earliest_date']:
                print(f"  Date Range: {table_stats['earliest_date']} to {table_stats['latest_date']}")
            print()


def main():
    """Main entry point for daily updates."""
    print("\n" + "=" * 60)
    print("DAILY MARKET DATA UPDATE")
    print(f"Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Check if market hours (optional - can always run after hours)
    current_hour = datetime.now().hour
    if 9 <= current_hour < 16:
        print("\n! Warning: Market is currently open (9 AM - 4 PM ET)")
        print("  This script is designed to run after market hours.")
        print("  Continue anyway? (y/n): ", end="")
        if input().lower() != "y":
            print("Aborted.")
            return

    # Allow custom ticker list via command line
    if len(sys.argv) > 1:
        tickers = sys.argv[1].split(",")
        print(f"\nUsing custom tickers: {', '.join(tickers)}")
    else:
        tickers = DEFAULT_TICKERS
        print(f"\nUpdating {len(tickers)} tickers")

    # Update OHLCV data (check last 5 days for gaps)
    update_ohlcv_data(tickers, days_back=5)

    # Update short data
    update_short_interest(tickers)
    update_short_volume(tickers, days_back=5)

    # Update economic indicators (check last 30 days for monthly releases)
    update_economic_indicators(days_back=30)

    # Calculate technical indicators (SMA, RSI, MACD, etc.)
    print(f"\n{'='*60}")
    print("Calculating Technical Indicators")
    print(f"{'='*60}\n")

    try:
        import subprocess
        result = subprocess.run(
            ["python", "scripts/calculate_indicators.py", "--store"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        if result.returncode == 0:
            print("OK Indicators calculated successfully")
        else:
            print(f"! Warning: Indicator calculation had issues")
            if result.stderr:
                print(f"  {result.stderr[:200]}")
    except Exception as e:
        print(f"! Could not calculate indicators: {e}")

    print(f"{'='*60}\n")

    # Show watchlist signals
    show_watchlist_signals()

    # Show portfolio stats
    show_portfolio_stats()

    # Ask for portfolio updates
    update_portfolio_interactive()

    # Print summary
    print_update_summary()

    # Show upcoming calendar events
    print("\n" + "=" * 60)
    print("UPCOMING MARKET EVENTS (Next 14 Days)")
    print("=" * 60 + "\n")

    try:
        from src.models.financial_calendar import FinancialCalendar, EventImpact

        upcoming = FinancialCalendar.get_upcoming_events(days_ahead=14)

        if upcoming:
            print(f"{'Date':<18} {'Days':<8} {'Event':<25} {'Impact':<12}")
            print("-" * 65)

            for event in upcoming:
                impact_icon = {
                    EventImpact.EXTREME: "🔴",
                    EventImpact.HIGH: "🟠",
                    EventImpact.MEDIUM: "🟡",
                    EventImpact.LOW: "🟢"
                }.get(event["impact"], "⚪")

                print(
                    f"{event['date'].strftime('%Y-%m-%d (%a)'):<18} "
                    f"{event['days_until']:>2} days   "
                    f"{event['name']:<25} "
                    f"{impact_icon} {event['impact'].value:<12}"
                )

            # Check if any events tomorrow
            tomorrow_events = [e for e in upcoming if e["days_until"] == 1]
            if tomorrow_events:
                print("\n⚠️  WARNING: High-impact event TOMORROW!")
                for e in tomorrow_events:
                    print(f"   {e['name']} - Avoid new positions")
        else:
            print("✓ No major market events in next 14 days")

        print()
    except Exception as e:
        print(f"! Could not load calendar: {e}\n")

    print("=" * 60)
    print("OK Daily update complete!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
