"""Analyze past trades - See what worked and what didn't."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.trade_journal import TradeJournal


def main():
    """Analyze trade journal for insights."""
    print("\n" + "=" * 100)
    print("TRADE PERFORMANCE ANALYSIS")
    print("=" * 100 + "\n")

    journal = TradeJournal()
    trades = journal.load_trades()

    if not trades:
        print("No trades logged yet.")
        print("\nStart trading with the enhanced detector to build your trade history.")
        print("Run: python scripts/portfolio_review.py\n")
        return

    # Overall performance
    stats = journal.analyze_performance()

    print("OVERALL PERFORMANCE")
    print("=" * 100)
    print(f"Total Trades:        {stats['total_trades']}")

    if stats['total_trades'] == 0:
        print("\nNo completed trades yet (only open positions or signals without entry/exit).")
        print("Trades need both entry and exit to appear in analysis.")
        return

    print(f"Winning Trades:      {stats['winning_trades']} ({stats['win_rate']:.1f}%)")
    print(f"Losing Trades:       {stats['losing_trades']}")
    print(f"Profit Factor:       {stats['profit_factor']:.2f}")
    print(f"Average Hold:        {stats['avg_holding_days']:.0f} days")
    print()
    print(f"Total Profit:        ${stats['total_profit']:,.2f}")
    print(f"Total Loss:          ${stats['total_loss']:,.2f}")
    print(f"Net Profit:          ${stats['net_profit']:,.2f}")
    print(f"Average Win:         ${stats['avg_win']:,.2f}")
    print(f"Average Loss:        ${stats['avg_loss']:,.2f}")
    print()

    # Best and worst trades
    print("BEST TRADE:")
    best = stats['best_trade']
    print(f"  {best['symbol']}: {best['profit_pct']:+.2f}%")
    print(f"  Entry: {best['entry_date']} → Exit: {best['exit_date']}")
    print()

    print("WORST TRADE:")
    worst = stats['worst_trade']
    print(f"  {worst['symbol']}: {worst['profit_pct']:+.2f}%")
    print(f"  Entry: {worst['entry_date']} → Exit: {worst['exit_date']}")
    print()

    # Trades near earnings
    earnings_trades = journal.get_trades_near_earnings()
    if earnings_trades:
        print("=" * 100)
        print(f"TRADES NEAR EARNINGS ({len(earnings_trades)} trades)")
        print("=" * 100)
        print("\nThese trades happened within 7 days of earnings:")
        print()

        for trade in earnings_trades[:10]:  # Show first 10
            direction = trade['direction']
            symbol = trade['symbol']
            days = trade.get('days_until_earnings', 'N/A')
            profit = trade.get('profit_loss_pct', 0)

            print(f"  {symbol:<8} | {direction:<4} | {days} days to earnings | "
                  f"P&L: {profit:+.2f}% | Date: {trade['trade_date']}")

        print()
        print("Analysis: Did earnings cause unexpected moves? Should we widen the block window?")
        print()

    # Volume spike trades
    volume_trades = journal.get_trades_with_volume_spike()
    if volume_trades:
        print("=" * 100)
        print(f"TRADES WITH VOLUME SPIKES ({len(volume_trades)} trades)")
        print("=" * 100)
        print("\nThese trades happened during unusual volume:")
        print()

        for trade in volume_trades[:10]:
            direction = trade['direction']
            symbol = trade['symbol']
            volume = trade.get('volume', 0)
            volume_avg = trade.get('volume_avg', 1)
            volume_ratio = volume / volume_avg if volume_avg > 0 else 0
            profit = trade.get('profit_loss_pct', 0)

            print(f"  {symbol:<8} | {direction:<4} | Volume: {volume_ratio:.1f}x avg | "
                  f"P&L: {profit:+.2f}% | Date: {trade['trade_date']}")

        print()
        print("Analysis: Are volume spikes good or bad? Do they predict big moves or whipsaws?")
        print()

    # Trade breakdown by signal type
    print("=" * 100)
    print("TRADES BY SIGNAL TYPE")
    print("=" * 100)
    print()

    signal_types = {}
    for trade in trades:
        sig_type = trade.get('signal_type', 'UNKNOWN')
        if sig_type not in signal_types:
            signal_types[sig_type] = []
        signal_types[sig_type].append(trade)

    for sig_type, sig_trades in sorted(signal_types.items()):
        # Count buys vs sells
        buys = [t for t in sig_trades if t['direction'] == 'BUY']
        sells = [t for t in sig_trades if t['direction'] == 'SELL']

        print(f"{sig_type:<20} | Total: {len(sig_trades):<4} | "
              f"Buys: {len(buys):<4} | Sells: {len(sells):<4}")

    print()

    # Market regime analysis
    print("=" * 100)
    print("TRADES BY MARKET REGIME")
    print("=" * 100)
    print()

    regime_trades = {}
    for trade in trades:
        regime = trade.get('market_regime', 'UNKNOWN')
        if regime not in regime_trades:
            regime_trades[regime] = []
        regime_trades[regime].append(trade)

    for regime, reg_trades in sorted(regime_trades.items()):
        print(f"{regime:<15} | {len(reg_trades)} trades")

    print()
    print("Analysis: Do you perform better in NORMAL vs VOLATILE markets?")
    print()

    # Trading mistakes to learn from
    completed = journal.get_completed_trades()
    if completed:
        print("=" * 100)
        print("LEARNING OPPORTUNITIES - Trades to Review")
        print("=" * 100)
        print()

        # Quick exits (held < 30 days)
        quick_exits = [t for t in completed if t.get('holding_days', 999) < 30]
        if quick_exits:
            print(f"QUICK EXITS ({len(quick_exits)} trades held < 30 days):")
            for trade in quick_exits[:5]:
                symbol = trade['symbol']
                days = trade.get('holding_days', 0)
                profit = trade.get('profit_loss_pct', 0)
                print(f"  {symbol:<8} | Held {days} days | P&L: {profit:+.2f}%")

            print("  → Review: Did you exit too early? Was it a whipsaw?")
            print()

        # Big losses (> 10%)
        big_losses = [t for t in completed if t.get('profit_loss_pct', 0) < -10]
        if big_losses:
            print(f"BIG LOSSES ({len(big_losses)} trades with >10% loss):")
            for trade in big_losses[:5]:
                symbol = trade['symbol']
                loss = trade.get('profit_loss_pct', 0)
                entry = trade.get('entry_date')
                exit_date = trade['trade_date']
                print(f"  {symbol:<8} | {loss:+.2f}% | {entry} → {exit_date}")

            print("  → Review: What went wrong? Death cross too slow? News event?")
            print()

    print("=" * 100)
    print("\nRun this script regularly to learn from your trades and improve your strategy.")
    print("=" * 100 + "\n")


if __name__ == "__main__":
    main()
