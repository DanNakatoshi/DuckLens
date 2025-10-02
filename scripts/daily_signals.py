"""
Daily signal checker for all watchlist tickers.

Run at end of day to see:
- Which tickers have BUY signals (entry opportunities)
- Which tickers have SELL signals (profit take or cut loss)
- Which tickers are HOLD (stay in position or wait)
"""

import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.config.tickers import TICKER_SYMBOLS
from src.data.storage.market_data_db import MarketDataDB
from src.models.trend_detector import TradingSignal, TrendDetector


def get_latest_price(db: MarketDataDB, ticker: str) -> tuple[datetime, Decimal] | None:
    """Get the latest price and date for a ticker."""
    query = """
    SELECT timestamp, close
    FROM stock_prices
    WHERE symbol = ?
    ORDER BY timestamp DESC
    LIMIT 1
    """
    result = db.conn.execute(query, [ticker]).fetchone()

    if result:
        date = datetime.fromisoformat(str(result[0]))
        price = Decimal(str(result[1]))
        return date, price

    return None


def main():
    print("=" * 100)
    print("DAILY TRADING SIGNALS - ALL WATCHLIST TICKERS")
    print("=" * 100)

    db = MarketDataDB()

    # Initialize trend detector
    detector = TrendDetector(
        db=db,
        min_confidence=0.6,
        block_high_impact_events=True,
        min_adx=0,
        confirmation_days=1,
        long_only=True,
    )

    # Get signals for all tickers
    buy_signals = []
    sell_signals = []
    hold_signals = []
    no_data = []

    print("\nScanning all tickers...\n")

    for ticker in TICKER_SYMBOLS:
        # Get latest price
        latest = get_latest_price(db, ticker)

        if not latest:
            no_data.append(ticker)
            continue

        date, price = latest

        # Generate signal
        signal = detector.generate_signal(ticker, date, price)

        if not signal:
            no_data.append(ticker)
            continue

        # Categorize signal
        if signal.signal == TradingSignal.BUY:
            buy_signals.append((ticker, signal, price, date))
        elif signal.signal == TradingSignal.SELL:
            sell_signals.append((ticker, signal, price, date))
        else:
            hold_signals.append((ticker, signal, price, date))

    # Display results
    print("=" * 100)
    print(f"RESULTS (as of latest data)")
    print("=" * 100)
    print(
        f"\nBUY Signals: {len(buy_signals)} | "
        f"SELL Signals: {len(sell_signals)} | "
        f"HOLD: {len(hold_signals)} | "
        f"No Data: {len(no_data)}\n"
    )

    # BUY SIGNALS (Entry opportunities)
    if buy_signals:
        print("=" * 100)
        print("BUY SIGNALS - ENTRY OPPORTUNITIES")
        print("=" * 100)

        for ticker, signal, price, date in buy_signals:
            print(f"\n{ticker:6s} | ${price:>8.2f} | {date.strftime('%Y-%m-%d')}")
            print(f"  Confidence: {signal.confidence:.0%}")
            print(f"  Trend: {signal.trend.value}")

            # Parse reasoning for key info
            reasoning_lines = signal.reasoning.split("\n")
            print(f"  Reason: {reasoning_lines[0]}")

            # Show key indicators
            for line in reasoning_lines:
                if "SMA:" in line or "MACD:" in line or "RSI:" in line:
                    print(f"  {line}")

    # SELL SIGNALS (Exit positions - take profit or cut loss)
    if sell_signals:
        print("\n" + "=" * 100)
        print("SELL SIGNALS - EXIT POSITIONS")
        print("=" * 100)

        for ticker, signal, price, date in sell_signals:
            print(f"\n{ticker:6s} | ${price:>8.2f} | {date.strftime('%Y-%m-%d')}")
            print(f"  Confidence: {signal.confidence:.0%}")
            print(f"  Trend: {signal.trend.value}")

            # Parse reasoning for key info
            reasoning_lines = signal.reasoning.split("\n")
            print(f"  Reason: {reasoning_lines[0]}")

            # Check if death cross
            if "DEATH CROSS" in signal.reasoning:
                print("  [WARNING] Death Cross detected - Major trend reversal!")

    # HOLD SIGNALS (Wait or stay in position)
    print("\n" + "=" * 100)
    print(f"HOLD SIGNALS ({len(hold_signals)} tickers)")
    print("=" * 100)

    # Group by trend
    bullish_holds = [s for s in hold_signals if s[1].trend.value == "BULLISH"]
    bearish_holds = [s for s in hold_signals if s[1].trend.value == "BEARISH"]
    neutral_holds = [s for s in hold_signals if s[1].trend.value == "NEUTRAL"]

    if bullish_holds:
        print(f"\nBULLISH TREND (Stay Long): {len(bullish_holds)} tickers")
        print("-" * 50)
        for ticker, signal, price, date in bullish_holds[:10]:  # Show first 10
            print(f"  {ticker:6s} | ${price:>8.2f} | {signal.reasoning.split(chr(10))[0]}")
        if len(bullish_holds) > 10:
            print(f"  ... and {len(bullish_holds) - 10} more")

    if bearish_holds:
        print(f"\nBEARISH TREND (Wait for BUY): {len(bearish_holds)} tickers")
        print("-" * 50)
        for ticker, signal, price, date in bearish_holds[:10]:
            print(f"  {ticker:6s} | ${price:>8.2f} | {signal.reasoning.split(chr(10))[0]}")
        if len(bearish_holds) > 10:
            print(f"  ... and {len(bearish_holds) - 10} more")

    if neutral_holds:
        print(f"\nNEUTRAL TREND (No Clear Direction): {len(neutral_holds)} tickers")
        print("-" * 50)
        for ticker, signal, price, date in neutral_holds[:10]:
            print(f"  {ticker:6s} | ${price:>8.2f} | {signal.reasoning.split(chr(10))[0]}")
        if len(neutral_holds) > 10:
            print(f"  ... and {len(neutral_holds) - 10} more")

    # No data tickers
    if no_data:
        print(f"\n" + "=" * 100)
        print(f"NO DATA: {len(no_data)} tickers")
        print("=" * 100)
        print(", ".join(no_data))
        print("\nRun: .\\tasks.ps1 fetch-historical to get data for these tickers")

    # Summary recommendation
    print("\n" + "=" * 100)
    print("ACTION ITEMS")
    print("=" * 100)

    if buy_signals:
        print(f"\n[ENTRY] {len(buy_signals)} ticker(s) showing BUY signals:")
        for ticker, _, price, _ in buy_signals:
            print(f"  - {ticker} @ ${price:.2f}")
        print("  -> Consider entering long positions")

    if sell_signals:
        print(f"\n[EXIT] {len(sell_signals)} ticker(s) showing SELL signals:")
        for ticker, _, price, _ in sell_signals:
            print(f"  - {ticker} @ ${price:.2f}")
        print("  -> Consider closing positions (profit take or cut loss)")

    if bullish_holds:
        print(f"\n[HOLD] {len(bullish_holds)} ticker(s) in bullish trend:")
        print("  -> Stay in positions, trend is still strong")

    if not buy_signals and not sell_signals:
        print("\n[NO ACTION] No entry or exit signals today.")
        print("  -> Wait for clearer signals")

    print("\n" + "=" * 100 + "\n")


if __name__ == "__main__":
    main()
