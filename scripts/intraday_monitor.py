"""
Intraday Monitor - Real-time stock analysis for 3 PM trading decisions.

Shows:
- Current price vs yesterday close
- Intraday trend (up/down from open)
- Buy/Sell signals from your strategy
- Recommended action for 3 PM

Uses Polygon.io's 15-minute delayed free tier data.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from src.config.tickers import TIER_2_STOCKS
from src.data.collectors.polygon_collector import PolygonCollector
from src.data.storage.market_data_db import MarketDataDB
from src.models.enhanced_detector import EnhancedTrendDetector
from src.models.trend_detector import TradingSignal
from src.portfolio.portfolio_manager import PortfolioManager

load_dotenv()


def get_market_direction_intraday(collector: PolygonCollector, db: MarketDataDB, detector: EnhancedTrendDetector) -> dict:
    """Check market direction using intraday SPY/QQQ data."""
    market_status = {}

    for ticker in ["SPY", "QQQ"]:
        snapshot = get_intraday_snapshot(ticker, collector)
        if snapshot:
            signal = detector.generate_signal(ticker, datetime.now(), snapshot["current"])
            market_status[ticker] = {
                "price": snapshot["current"],
                "change_from_close": snapshot["change_from_close"],
                "signal": signal.signal,
                "confidence": signal.confidence,
            }

    return market_status


def get_intraday_snapshot(ticker: str, collector: PolygonCollector) -> dict:
    """Get current intraday price snapshot (15-min delayed)."""
    try:
        # Get previous close first
        prev_close_response = collector.client.get_previous_close_agg(ticker)

        if not prev_close_response or len(prev_close_response) == 0:
            return None

        prev_close = float(prev_close_response[0].close)

        # Get current snapshot (15-min delayed on free tier)
        snapshot = collector.client.get_snapshot_ticker("stocks", ticker)

        if not snapshot or not snapshot.day:
            return None

        current_price = float(snapshot.day.close)
        open_price = float(snapshot.day.open)
        high = float(snapshot.day.high)
        low = float(snapshot.day.low)
        volume = int(snapshot.day.volume)

        # Calculate intraday metrics
        change_from_close = ((current_price / prev_close) - 1) * 100
        change_from_open = ((current_price / open_price) - 1) * 100
        daily_range = ((high - low) / low) * 100

        return {
            "ticker": ticker,
            "current": current_price,
            "open": open_price,
            "high": high,
            "low": low,
            "prev_close": prev_close,
            "volume": volume,
            "change_from_close": change_from_close,
            "change_from_open": change_from_open,
            "daily_range": daily_range,
            "timestamp": datetime.now(),
        }

    except Exception as e:
        print(f"  ERROR fetching {ticker}: {e}")
        return None


def analyze_intraday_action(ticker: str, intraday_data: dict, db: MarketDataDB, detector: EnhancedTrendDetector, portfolio_manager: PortfolioManager) -> dict:
    """Analyze what action to take at 3 PM."""

    # Get current signal from strategy
    current_price = intraday_data["current"]
    today = datetime.now()

    signal = detector.generate_signal(ticker, today, current_price)

    # Check if we already own it
    portfolio = portfolio_manager.load_portfolio()
    position = portfolio.positions.get(ticker)

    # Determine recommendation
    recommendation = "HOLD"
    reason = ""

    if position:
        # We own it - should we sell?
        if signal.signal == TradingSignal.SELL:
            recommendation = "SELL"
            reason = f"Strategy says SELL: {signal.reasoning[:60]}"
        elif intraday_data["change_from_close"] < -5:
            recommendation = "WATCH"
            reason = f"Down {intraday_data['change_from_close']:.1f}% today - monitor for stop loss"
        else:
            recommendation = "HOLD"
            reason = f"No signal, holding (up {intraday_data['change_from_close']:.1f}% today)"
    else:
        # We don't own it - should we buy?
        if signal.signal == TradingSignal.BUY:
            if intraday_data["change_from_close"] > 2:
                recommendation = "WAIT"
                reason = f"Up {intraday_data['change_from_close']:.1f}% - wait for pullback"
            elif intraday_data["change_from_close"] < -3:
                recommendation = "BUY"
                reason = f"BUY signal + down {abs(intraday_data['change_from_close']):.1f}% - good entry"
            else:
                recommendation = "BUY"
                reason = f"BUY signal: {signal.reasoning[:60]}"
        elif intraday_data["change_from_close"] < -5:
            recommendation = "WATCH"
            reason = f"Down {abs(intraday_data['change_from_close']):.1f}% - check for reversal"
        else:
            recommendation = "PASS"
            reason = "No signal"

    # Get signal date (today for intraday)
    signal_date = intraday_data["timestamp"].strftime("%Y-%m-%d")

    return {
        "ticker": ticker,
        "recommendation": recommendation,
        "reason": reason,
        "signal": signal.signal.value,
        "signal_date": signal_date,
        "confidence": signal.confidence,
        "owns_it": position is not None,
        "intraday": intraday_data,
    }


def main():
    """Main entry point - run at 3 PM to decide what to trade."""

    current_time = datetime.now()
    market_hour = current_time.hour

    print("=" * 100)
    print(f"INTRADAY MONITOR - 3 PM TRADING DECISION")
    print("=" * 100)
    print(f"Time: {current_time.strftime('%Y-%m-%d %I:%M %p ET')}")

    # Check market hours
    if market_hour < 9 or market_hour >= 16:
        print("\n! MARKET IS CLOSED (9:30 AM - 4:00 PM ET)")
        print("  This tool is for intraday monitoring during market hours")
        print("  Data shown is from previous close\n")
    elif market_hour >= 15:
        print("\n-> GOOD TIMING! 3 PM is ideal for final trading decisions")
        print("   You've seen morning + noon price action\n")
    else:
        print(f"\n-> Current time: {current_time.strftime('%I:%M %p')}")
        print("   Recommended usage: 3 PM for final decisions\n")

    print("=" * 100)
    print()

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

    # Section 0: MARKET DIRECTION
    print("=" * 100)
    print("MARKET DIRECTION - Real-Time Trend (15-min delayed)")
    print("=" * 100)
    print()

    with PolygonCollector() as collector:
        market_status = get_market_direction_intraday(collector, db, detector)

        if market_status:
            print(f"{'Index':<8} {'Price':<12} {'Today%':<10} {'Signal':<12} {'Confidence':<12}")
            print("-" * 60)

            for ticker, status in market_status.items():
                print(
                    f"{ticker:<8} "
                    f"${status['price']:<11.2f} "
                    f"{status['change_from_close']:>+6.2f}%  "
                    f"{status['signal'].value:<12} "
                    f"{status['confidence']:<11.0%}"
                )

            print()

            # Determine overall market condition
            spy_signal = market_status.get("SPY", {}).get("signal", TradingSignal.DONT_TRADE)
            qqq_signal = market_status.get("QQQ", {}).get("signal", TradingSignal.DONT_TRADE)

            if spy_signal == TradingSignal.BUY and qqq_signal == TradingSignal.BUY:
                print("*** MARKET CONDITION: BULLISH - Good environment for buys ***")
            elif spy_signal == TradingSignal.SELL or qqq_signal == TradingSignal.SELL:
                print("!!! MARKET CONDITION: BEARISH - High risk, avoid new buys !!!")
            else:
                print("--- MARKET CONDITION: NEUTRAL - Be selective ---")

            print()

    print("=" * 100)
    print()

    # Section 1: PORTFOLIO HOLDINGS - Check if we should SELL
    print("=" * 100)
    print("SECTION 1: YOUR HOLDINGS - Sell Check")
    print("=" * 100)
    print()

    portfolio = portfolio_manager.load_portfolio()

    if portfolio.positions:
        print(f"{'Ticker':<8} {'Current':<10} {'Change%':<10} {'Intraday':<10} {'Signal':<12} {'Date':<12} {'Action':<10} {'Reason':<40}")
        print("-" * 115)

        holding_actions = []

        with PolygonCollector() as collector:
            for ticker in sorted(portfolio.positions.keys()):
                intraday = get_intraday_snapshot(ticker, collector)

                if intraday:
                    analysis = analyze_intraday_action(ticker, intraday, db, detector, portfolio_manager)
                    holding_actions.append(analysis)

                    print(
                        f"{ticker:<8} "
                        f"${intraday['current']:<9.2f} "
                        f"{intraday['change_from_close']:>+6.2f}%   "
                        f"{intraday['change_from_open']:>+6.2f}%   "
                        f"{analysis['signal']:<12} "
                        f"{analysis['signal_date']:<12} "
                        f"{analysis['recommendation']:<10} "
                        f"{analysis['reason']:<40}"
                    )
                else:
                    print(f"{ticker:<8} NO DATA - Check manually")

        # Summary of holding actions
        sell_now = [a for a in holding_actions if a["recommendation"] == "SELL"]
        watch_list = [a for a in holding_actions if a["recommendation"] == "WATCH"]

        print()
        if sell_now:
            print(f"! SELL SIGNALS: {len(sell_now)} stocks")
            for a in sell_now:
                print(f"  - {a['ticker']}: {a['reason']}")

        if watch_list:
            print(f"! WATCH LIST: {len(watch_list)} stocks")
            for a in watch_list:
                print(f"  - {a['ticker']}: {a['reason']}")

        if not sell_now and not watch_list:
            print("OK All holdings look good - no action needed")
    else:
        print("No holdings in portfolio")
        print("Run: .\\tasks.ps1 import-portfolio to import your positions\n")

    print()

    # Section 2: WATCHLIST - Check if we should BUY
    print("=" * 100)
    print("SECTION 2: WATCHLIST - Buy Opportunities")
    print("=" * 100)
    print()

    print(f"{'Ticker':<8} {'Current':<10} {'Change%':<10} {'Intraday':<10} {'Signal':<12} {'Action':<10} {'Reason':<50}")
    print("-" * 100)

    buy_opportunities = []

    with PolygonCollector() as collector:
        # Check top watchlist stocks (limit to 20 for speed)
        watchlist_tickers = [t.symbol for t in TIER_2_STOCKS[:20]]

        for ticker in sorted(watchlist_tickers):
            # Skip if we already own it
            if ticker in portfolio.positions:
                continue

            intraday = get_intraday_snapshot(ticker, collector)

            if intraday:
                analysis = analyze_intraday_action(ticker, intraday, db, detector, portfolio_manager)

                # Only show if there's potential action
                if analysis["recommendation"] in ["BUY", "WATCH"]:
                    buy_opportunities.append(analysis)

                    print(
                        f"{ticker:<8} "
                        f"${intraday['current']:<9.2f} "
                        f"{intraday['change_from_close']:>+6.2f}%   "
                        f"{intraday['change_from_open']:>+6.2f}%   "
                        f"{analysis['signal']:<12} "
                        f"{analysis['recommendation']:<10} "
                        f"{analysis['reason']:<50}"
                    )

    if not buy_opportunities:
        print("No buy opportunities at this time")

    print()

    # Section 3: SUMMARY - Final 3 PM Decision
    print("=" * 100)
    print("SECTION 3: 3 PM TRADING DECISION SUMMARY")
    print("=" * 100)
    print()

    buy_now = [a for a in buy_opportunities if a["recommendation"] == "BUY"]

    if sell_now:
        print(f"SELL ({len(sell_now)} stocks):")
        for a in sell_now:
            print(f"  -> {a['ticker']:<8} @ ${a['intraday']['current']:.2f}  ({a['reason']})")
        print()

    if buy_now:
        print(f"BUY ({len(buy_now)} stocks):")
        for a in buy_now:
            print(f"  -> {a['ticker']:<8} @ ${a['intraday']['current']:.2f}  ({a['reason']})")
        print()

    if not sell_now and not buy_now:
        print("NO ACTION NEEDED TODAY")
        print("  - No strong sell signals on holdings")
        print("  - No strong buy signals on watchlist")
        print()

    print("=" * 100)
    print("NEXT STEPS:")
    print("=" * 100)
    print()

    if sell_now or buy_now:
        print("1. Review the signals above")
        print("2. Check E*TRADE to execute trades")
        print("3. After trading, update portfolio:")
        print("   .\\tasks.ps1 update-daily")
        print("   (will ask you to record trades)")
    else:
        print("1. No trades needed today - sit tight")
        print("2. Run again tomorrow at 3 PM")
        print("3. Or check real-time: .\\tasks.ps1 intraday")

    print()
    print(f"Last updated: {datetime.now().strftime('%I:%M %p ET')}")
    print("Data: 15-minute delayed (Polygon.io free tier)")
    print("=" * 100)
    print()


if __name__ == "__main__":
    main()
