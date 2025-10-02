"""Daily portfolio review - Shows BUY/SELL/HOLD recommendations for your positions."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.tickers import TICKER_METADATA_MAP
from src.data.storage.market_data_db import MarketDataDB
from src.models.enhanced_detector import EnhancedTrendDetector
from src.models.trend_detector import TradingSignal
from src.portfolio.portfolio_manager import PortfolioManager


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
    return (result[0], float(result[1])) if result else (None, None)


def check_vxx_protection(db: MarketDataDB) -> tuple[bool, float]:
    """Check if VXX is spiking (market crash warning)."""
    query = """
        SELECT close, sma_20
        FROM stock_prices sp
        LEFT JOIN technical_indicators ti ON sp.symbol = ti.symbol
            AND DATE(sp.timestamp) = DATE(ti.timestamp)
        WHERE sp.symbol = 'VXX'
        ORDER BY sp.timestamp DESC
        LIMIT 1
    """
    result = db.conn.execute(query).fetchone()

    if result:
        vxx_price = float(result[0])
        vxx_sma = float(result[1]) if result[1] else vxx_price

        # VXX > 50 or > 2x SMA_20 = crash warning
        is_spiking = vxx_price > 50 or vxx_price > (vxx_sma * 2)
        return is_spiking, vxx_price

    return False, 0.0


def main():
    """Daily portfolio review."""
    print("=" * 100)
    print("DAILY PORTFOLIO REVIEW")
    print("=" * 100)
    print()

    # Load portfolio
    pm = PortfolioManager()
    portfolio = pm.load_portfolio()

    if not portfolio.positions and portfolio.cash == 0:
        print("No portfolio found. Run 'python scripts/import_portfolio.py' first.\n")
        return

    # Get current prices
    db = MarketDataDB()
    detector = EnhancedTrendDetector(
        db=db,
        min_confidence=0.75,
        confirmation_days=1,
        long_only=True,
        log_trades=True,  # Enable trade logging
        block_earnings_window=3,  # Block trades 3 days before earnings
        volume_spike_threshold=3.0,  # 3x volume = spike
    )

    # Check crash protection
    vxx_warning, vxx_price = check_vxx_protection(db)

    if vxx_warning:
        print("=" * 100)
        print("WARNING: MARKET CRASH PROTECTION TRIGGERED")
        print("=" * 100)
        print(f"VXX Price: ${vxx_price:.2f} - ELEVATED VOLATILITY!")
        print("Recommendation: EXIT ALL POSITIONS or BUY VXX as hedge")
        print("=" * 100)
        print()

    # Portfolio summary
    current_prices = {}
    position_values = []
    total_cost = 0.0
    total_value = 0.0
    total_gain = 0.0

    print(f"Cash: ${portfolio.cash:,.2f}")
    print()

    # Analyze each position
    sell_signals = []
    hold_signals = []
    add_signals = []

    for symbol, position in sorted(portfolio.positions.items()):
        date, price = get_latest_price(db, symbol)

        if price is None:
            print(f"{symbol}: NO DATA (fetch data for this ticker)")
            continue

        current_prices[symbol] = price

        # Calculate P&L
        cost_basis = position.quantity * position.price_paid
        current_value = position.quantity * price
        gain_loss = current_value - cost_basis
        gain_loss_pct = (gain_loss / cost_basis) * 100

        total_cost += cost_basis
        total_value += current_value
        total_gain += gain_loss

        # Get signal
        signal_data = detector.generate_signal(symbol, date, price)

        # Categorize
        if signal_data.signal == TradingSignal.SELL:
            sell_signals.append(
                (symbol, position, price, gain_loss, gain_loss_pct, signal_data)
            )
        elif signal_data.signal == TradingSignal.BUY and signal_data.confidence >= 0.75:
            add_signals.append(
                (symbol, position, price, gain_loss, gain_loss_pct, signal_data)
            )
        else:
            hold_signals.append(
                (symbol, position, price, gain_loss, gain_loss_pct, signal_data)
            )

    # Summary stats
    total_portfolio_value = portfolio.cash + total_value
    total_return_pct = (total_gain / total_cost) * 100 if total_cost > 0 else 0

    print(f"{'='*100}")
    print("PORTFOLIO SUMMARY")
    print(f"{'='*100}")
    print(f"Total Cost Basis:    ${total_cost:,.2f}")
    print(f"Current Value:       ${total_value:,.2f}")
    print(f"Cash:                ${portfolio.cash:,.2f}")
    print(f"Total Portfolio:     ${total_portfolio_value:,.2f}")
    print(f"Total Gain/Loss:     ${total_gain:,.2f} ({total_return_pct:+.2f}%)")
    print()

    # SELL recommendations
    if sell_signals or vxx_warning:
        print(f"{'='*100}")
        print("SELL SIGNALS - EXIT THESE POSITIONS")
        print(f"{'='*100}")
        print()

        if vxx_warning:
            print("*** CRASH WARNING: VXX SPIKING - Consider selling ALL positions ***\n")

        for symbol, pos, price, gain, gain_pct, signal in sell_signals:
            metadata = TICKER_METADATA_MAP.get(symbol)
            print(f"{symbol:<8} | Qty: {pos.quantity:>6} | Price: ${price:>8.2f} | "
                  f"Gain: ${gain:>10.2f} ({gain_pct:+.2f}%)")
            print(f"  Name: {metadata.name if metadata else 'N/A'}")
            print(f"  Reason: {signal.reasoning}")
            print(f"  ACTION: SELL - Death cross or trend reversal")
            print()

        if not sell_signals and vxx_warning:
            print("No death cross signals yet, but VXX warning active.")
            print("Consider selling to protect profits.\n")

    # ADD/HOLD recommendations
    if add_signals:
        print(f"{'='*100}")
        print("ADD TO POSITION - Strong uptrends, consider adding more")
        print(f"{'='*100}")
        print()

        for symbol, pos, price, gain, gain_pct, signal in add_signals:
            metadata = TICKER_METADATA_MAP.get(symbol)
            print(f"{symbol:<8} | Qty: {pos.quantity:>6} | Price: ${price:>8.2f} | "
                  f"Gain: ${gain:>10.2f} ({gain_pct:+.2f}%)")
            print(f"  Confidence: {signal.confidence:.0%} | Trend: {signal.trend.value}")
            print(f"  ACTION: Consider adding more (trend still strong)")
            print()

    # HOLD positions
    if hold_signals:
        print(f"{'='*100}")
        print(f"HOLD - Keep these positions ({len(hold_signals)} tickers)")
        print(f"{'='*100}")
        print()

        for symbol, pos, price, gain, gain_pct, signal in hold_signals:
            status = "WINNING" if gain > 0 else "LOSING"
            print(f"{symbol:<8} | Qty: {pos.quantity:>6} | Price: ${price:>8.2f} | "
                  f"Gain: ${gain:>10.2f} ({gain_pct:+.2f}%) | {status}")

        print()

    # Action summary
    print(f"{'='*100}")
    print("ACTION SUMMARY")
    print(f"{'='*100}")
    print(f"Positions to SELL:  {len(sell_signals)}")
    print(f"Positions to ADD:   {len(add_signals)}")
    print(f"Positions to HOLD:  {len(hold_signals)}")

    if vxx_warning:
        print(f"\n*** VXX WARNING: ${vxx_price:.2f} - Market volatility elevated ***")

    print()
    print("Run 'python scripts/watchlist_signals.py' to see new buy opportunities")
    print(f"{'='*100}\n")


if __name__ == "__main__":
    main()
