"""Daily watchlist - Show BUY/SELL/HOLD signals for all tradeable stocks.

This is your end-of-day scanner. Only trade when signals are clear and confident.
Remember: It's better NOT to trade than to force a bad entry.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.tickers import TRADING_WATCHLIST, TICKER_METADATA_MAP
from src.data.storage.market_data_db import MarketDataDB
from src.models.trend_detector import TrendDetector, TradingSignal


def get_latest_price(db: MarketDataDB, ticker: str):
    """Get latest price for ticker."""
    query = """
        SELECT DATE(timestamp) as date, close
        FROM stock_prices
        WHERE symbol = ?
        ORDER BY timestamp DESC
        LIMIT 1
    """
    result = db.conn.execute(query, [ticker]).fetchone()
    return (result[0], float(result[1])) if result else None


def main():
    """Show daily signals for all watchlist stocks."""
    print("=" * 100)
    print("TRADING WATCHLIST - DAILY SIGNALS")
    print("=" * 100)
    print("\nRule #1: Only trade when you see a clear BUY signal with confidence >= 75%")
    print("Rule #2: If confidence < 75% or mixed signals -> DON'T TRADE")
    print("Rule #3: Better to miss a trade than to force a bad entry\n")

    db = MarketDataDB()

    # Initialize trend detector with strict requirements
    detector = TrendDetector(
        db=db,
        min_confidence=0.75,  # Higher threshold for quality
        block_high_impact_events=True,
        min_adx=0,
        confirmation_days=1,
        long_only=True,
    )

    # Scan watchlist
    buy_signals = []
    sell_signals = []
    hold_signals = []
    no_data = []

    for ticker in TRADING_WATCHLIST:
        latest = get_latest_price(db, ticker)
        if not latest:
            no_data.append(ticker)
            continue

        date, price = latest
        signal = detector.generate_signal(ticker, date, price)

        metadata = TICKER_METADATA_MAP.get(ticker)

        if signal.signal == TradingSignal.BUY:
            buy_signals.append((ticker, signal, price, date, metadata))
        elif signal.signal == TradingSignal.SELL:
            sell_signals.append((ticker, signal, price, date, metadata))
        else:
            hold_signals.append((ticker, signal, price, date, metadata))

    # Summary
    print("=" * 100)
    print(f"SCAN RESULTS (as of latest data)")
    print("=" * 100)
    print(f"\nBUY Signals: {len(buy_signals)} | SELL Signals: {len(sell_signals)} | "
          f"HOLD/WAIT: {len(hold_signals)} | No Data: {len(no_data)}\n")

    # === BUY SIGNALS (Entry Opportunities) ===
    if buy_signals:
        print("=" * 100)
        print("BUY SIGNALS - ENTRY OPPORTUNITIES (Trade These)")
        print("=" * 100)
        print()

        for ticker, signal, price, date, metadata in buy_signals:
            print(f"{ticker:<8} | ${price:>8.2f} | {date}")
            print(f"  Name: {metadata.name if metadata else 'N/A'}")
            print(f"  Confidence: {signal.confidence:.0%} | Trend: {signal.trend.value}")
            print(f"  Reason: {signal.reasoning}")
            print()

    # === SELL SIGNALS (Exit Positions) ===
    if sell_signals:
        print("=" * 100)
        print("SELL SIGNALS - EXIT POSITIONS")
        print("=" * 100)
        print()

        for ticker, signal, price, date, metadata in sell_signals:
            print(f"{ticker:<8} | ${price:>8.2f} | {date}")
            print(f"  Name: {metadata.name if metadata else 'N/A'}")
            print(f"  Reason: {signal.reasoning}")
            print()

    # === HOLD/WAIT (Don't Trade) ===
    if hold_signals:
        print("=" * 100)
        print(f"HOLD/WAIT - DON'T TRADE ({len(hold_signals)} tickers)")
        print("=" * 100)
        print("\nThese stocks don't meet entry criteria. Wait for clearer signals.\n")

        # Group by reason
        low_confidence = []
        bearish = []
        neutral = []

        for ticker, signal, price, date, metadata in hold_signals:
            if "LOW CONFIDENCE" in signal.reasoning:
                low_confidence.append((ticker, signal.confidence))
            elif "BEARISH" in signal.reasoning or "SHORT-TERM BEARISH" in signal.reasoning:
                bearish.append(ticker)
            else:
                neutral.append(ticker)

        if bearish:
            print(f"BEARISH TREND (Wait for reversal): {len(bearish)} tickers")
            print(f"  {', '.join(bearish)}\n")

        if low_confidence:
            print(f"LOW CONFIDENCE (Mixed signals): {len(low_confidence)} tickers")
            for ticker, conf in sorted(low_confidence, key=lambda x: x[1], reverse=True):
                print(f"  {ticker:<8} - Confidence: {conf:.0%}")
            print()

        if neutral:
            print(f"NEUTRAL (No clear direction): {len(neutral)} tickers")
            print(f"  {', '.join(neutral)}\n")

    # === No Data ===
    if no_data:
        print("=" * 100)
        print(f"NO DATA: {len(no_data)} tickers")
        print("=" * 100)
        print(f"{', '.join(no_data)}")
        print("\nRun: python scripts/fetch_new_stocks.py to get data\n")

    # === Action Items ===
    print("=" * 100)
    print("ACTION ITEMS")
    print("=" * 100)
    print()

    if buy_signals:
        print(f"[ENTRY OPPORTUNITIES] {len(buy_signals)} stock(s) showing BUY signals:\n")
        for ticker, signal, price, date, metadata in buy_signals:
            # Calculate suggested position size based on confidence
            confidence_pct = signal.confidence * 100
            suggested_leverage = "1.5x" if confidence_pct >= 75 else "1.0x"
            print(f"  -> {ticker:<8} @ ${price:>8.2f} - Confidence: {confidence_pct:.0f}% - Suggested leverage: {suggested_leverage}")
        print("\n  Recommended: Use 1.5x leverage for signals with confidence >= 75%\n")
    else:
        print("[NO ENTRY SIGNALS TODAY]\n")

    if sell_signals:
        print(f"[EXIT REQUIRED] {len(sell_signals)} stock(s) showing SELL signals:\n")
        for ticker, signal, price, date, metadata in sell_signals:
            print(f"  -> {ticker:<8} @ ${price:>8.2f} - CLOSE POSITION")
        print()

    if not buy_signals and not sell_signals:
        print("[NO ACTION] No clear entry or exit signals today.")
        print("\n  -> Wait for better opportunities. Don't force trades.")
        print("  -> Review HOLD/WAIT list for potential setups\n")

    print("=" * 100)
    print()


if __name__ == "__main__":
    main()
