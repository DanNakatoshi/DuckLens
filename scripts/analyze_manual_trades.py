"""Analyze manual trade journal - Track your progress to $1M."""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.storage.market_data_db import MarketDataDB


def main():
    """Analyze manual trade journal for performance insights."""
    print("\n=== TRADE JOURNAL ANALYSIS ===")
    print("Analyze past trades to see what worked and what didn't")
    print("Learn from wins, losses, earnings trades, and volume spikes\n")

    with MarketDataDB() as db:
        # Get all trades
        trades = db.conn.execute("""
            SELECT id, trade_date, symbol, action, quantity, price,
                   total_value, strategy, reason, created_at
            FROM trade_journal
            ORDER BY trade_date DESC, created_at DESC
        """).fetchall()

        if not trades:
            print("No trades in journal yet.")
            print("\nAdd trades with: .\\tasks.ps1 add-trade\n")
            return

        print("=" * 100)
        print("TRADE JOURNAL ENTRIES")
        print("=" * 100)
        print()
        print(f"{'Date':<12} {'Action':<6} {'Ticker':<8} {'Qty':<6} {'Price':<12} "
              f"{'Total':<14} {'Strategy':<15} {'Reason':<30}")
        print("-" * 100)

        # Display all trades
        buys = []
        sells = []

        for trade in trades:
            trade_id, trade_date, symbol, action, qty, price, total, strategy, reason, created = trade

            # Convert to float for calculations
            qty = int(qty)
            price = float(price)
            total = float(total)

            if action == "BUY":
                buys.append({
                    'date': trade_date,
                    'symbol': symbol,
                    'qty': qty,
                    'price': price,
                    'total': total,
                    'strategy': strategy,
                    'reason': reason
                })
            else:
                sells.append({
                    'date': trade_date,
                    'symbol': symbol,
                    'qty': qty,
                    'price': price,
                    'total': total,
                    'strategy': strategy,
                    'reason': reason
                })

            reason_short = (reason[:27] + "...") if reason and len(reason) > 30 else (reason or "")

            print(f"{trade_date:<12} {action:<6} {symbol:<8} {qty:<6} "
                  f"${price:<11.2f} ${total:<13,.2f} {strategy or '':<15} {reason_short:<30}")

        print()

        # Calculate summary statistics
        total_trades = len(trades)
        total_buys = len(buys)
        total_sells = len(sells)

        # Calculate totals
        buy_total = sum(b['total'] for b in buys)
        sell_total = sum(s['total'] for s in sells)

        print("=" * 100)
        print("TRADING SUMMARY")
        print("=" * 100)
        print()
        print(f"Total Trades:          {total_trades}")
        print(f"  - Buys:              {total_buys} trades (${buy_total:,.2f} invested)")
        print(f"  - Sells:             {total_sells} trades (${sell_total:,.2f} received)")
        print()

        # Calculate realized P&L (matched trades)
        realized_pnl = []
        remaining_buys = buys.copy()

        for sell in sells:
            # Find matching buys for this symbol (FIFO)
            sell_qty = sell['qty']
            sell_price = sell['price']
            sell_date = sell['date']
            symbol = sell['symbol']

            for buy in remaining_buys[:]:
                if buy['symbol'] != symbol:
                    continue

                # Match quantities (FIFO)
                qty_matched = min(sell_qty, buy['qty'])

                # Calculate P&L
                cost_basis = qty_matched * buy['price']
                proceeds = qty_matched * sell_price
                pnl = proceeds - cost_basis
                pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0

                # Calculate holding period
                buy_date = datetime.strptime(buy['date'], "%Y-%m-%d") if isinstance(buy['date'], str) else buy['date']
                sell_date_dt = datetime.strptime(sell_date, "%Y-%m-%d") if isinstance(sell_date, str) else sell_date
                holding_days = (sell_date_dt - buy_date).days

                realized_pnl.append({
                    'symbol': symbol,
                    'buy_date': buy['date'],
                    'sell_date': sell_date,
                    'qty': qty_matched,
                    'buy_price': buy['price'],
                    'sell_price': sell_price,
                    'cost_basis': cost_basis,
                    'proceeds': proceeds,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'holding_days': holding_days,
                    'strategy': buy.get('strategy', 'N/A'),
                    'reason': sell.get('reason', 'N/A')
                })

                # Reduce quantities
                sell_qty -= qty_matched
                buy['qty'] -= qty_matched

                if buy['qty'] == 0:
                    remaining_buys.remove(buy)

                if sell_qty == 0:
                    break

        if realized_pnl:
            print("=" * 100)
            print("REALIZED GAINS/LOSSES (Closed Positions)")
            print("=" * 100)
            print()
            print(f"{'Symbol':<8} {'Buy Date':<12} {'Sell Date':<12} {'Qty':<6} "
                  f"{'Buy $':<10} {'Sell $':<10} {'P&L':<12} {'%':<10} {'Days':<6} {'Result':<10}")
            print("-" * 100)

            wins = []
            losses = []

            for trade in realized_pnl:
                result = "WIN" if trade['pnl'] > 0 else "LOSS" if trade['pnl'] < 0 else "BREAK-EVEN"
                result_color = "+" if trade['pnl'] > 0 else "-"

                if trade['pnl'] > 0:
                    wins.append(trade)
                elif trade['pnl'] < 0:
                    losses.append(trade)

                print(f"{trade['symbol']:<8} {trade['buy_date']:<12} {trade['sell_date']:<12} "
                      f"{trade['qty']:<6} ${trade['buy_price']:<9.2f} ${trade['sell_price']:<9.2f} "
                      f"${trade['pnl']:<11,.2f} {trade['pnl_pct']:>8.2f}% {trade['holding_days']:<6} {result:<10}")

            print()

            # Win/Loss statistics
            total_realized = len(realized_pnl)
            total_wins = len(wins)
            total_losses = len(losses)
            win_rate = (total_wins / total_realized * 100) if total_realized > 0 else 0

            total_profit = sum(w['pnl'] for w in wins)
            total_loss = sum(abs(l['pnl']) for l in losses)
            net_pnl = total_profit - total_loss

            avg_win = (total_profit / total_wins) if total_wins > 0 else 0
            avg_loss = (total_loss / total_losses) if total_losses > 0 else 0

            avg_win_pct = (sum(w['pnl_pct'] for w in wins) / total_wins) if total_wins > 0 else 0
            avg_loss_pct = (sum(abs(l['pnl_pct']) for l in losses) / total_losses) if total_losses > 0 else 0

            profit_factor = (total_profit / total_loss) if total_loss > 0 else 0

            avg_hold_wins = (sum(w['holding_days'] for w in wins) / total_wins) if total_wins > 0 else 0
            avg_hold_losses = (sum(l['holding_days'] for l in losses) / total_losses) if total_losses > 0 else 0

            print("=" * 100)
            print("PERFORMANCE METRICS")
            print("=" * 100)
            print()
            print(f"Total Closed Trades:   {total_realized}")
            print(f"  - Wins:              {total_wins} ({win_rate:.1f}%)")
            print(f"  - Losses:            {total_losses} ({100 - win_rate:.1f}%)")
            print()
            print(f"Total Profit:          ${total_profit:,.2f}")
            print(f"Total Loss:            ${total_loss:,.2f}")
            print(f"Net P&L:               ${net_pnl:,.2f}")
            print()
            print(f"Average Win:           ${avg_win:,.2f} ({avg_win_pct:+.2f}%)")
            print(f"Average Loss:          ${avg_loss:,.2f} ({avg_loss_pct:+.2f}%)")
            print(f"Profit Factor:         {profit_factor:.2f}")
            print()
            print(f"Avg Hold (Wins):       {avg_hold_wins:.1f} days")
            print(f"Avg Hold (Losses):     {avg_hold_losses:.1f} days")
            print()

            # Best and worst trades
            if wins:
                best_trade = max(wins, key=lambda x: x['pnl_pct'])
                print(f"Best Trade:            {best_trade['symbol']} - "
                      f"${best_trade['pnl']:,.2f} ({best_trade['pnl_pct']:+.2f}%) "
                      f"on {best_trade['sell_date']}")

            if losses:
                worst_trade = min(losses, key=lambda x: x['pnl_pct'])
                print(f"Worst Trade:           {worst_trade['symbol']} - "
                      f"${worst_trade['pnl']:,.2f} ({worst_trade['pnl_pct']:+.2f}%) "
                      f"on {worst_trade['sell_date']}")

            print()

        # Open positions (remaining buys)
        if remaining_buys:
            print("=" * 100)
            print("OPEN POSITIONS (Unrealized)")
            print("=" * 100)
            print()
            print(f"{'Symbol':<8} {'Buy Date':<12} {'Qty':<6} {'Buy Price':<12} "
                  f"{'Cost Basis':<14} {'Strategy':<15}")
            print("-" * 100)

            total_open_cost = 0

            for buy in remaining_buys:
                cost = buy['qty'] * buy['price']
                total_open_cost += cost

                print(f"{buy['symbol']:<8} {buy['date']:<12} {buy['qty']:<6} "
                      f"${buy['price']:<11.2f} ${cost:<13,.2f} {buy.get('strategy', 'N/A'):<15}")

            print()
            print(f"Total Open Positions:  ${total_open_cost:,.2f}")
            print()

        # Get latest account balance for context
        try:
            balance = db.conn.execute("""
                SELECT cash_balance, total_value, balance_date
                FROM account_balance
                ORDER BY balance_date DESC
                LIMIT 1
            """).fetchone()

            if balance:
                cash, total_value, bal_date = balance
                cash = float(cash)
                total_value = float(total_value)

                print("=" * 100)
                print("ACCOUNT PROGRESS")
                print("=" * 100)
                print()
                print(f"Account Value:         ${total_value:,.2f} (as of {bal_date})")
                print(f"Cash Available:        ${cash:,.2f}")
                print(f"Progress to $1M:       {(total_value / 1_000_000 * 100):.2f}%")
                print(f"Remaining:             ${1_000_000 - total_value:,.2f}")
                print()

                # Calculate required return
                if total_value > 0:
                    required_return = ((1_000_000 / total_value) - 1) * 100
                    print(f"Required Return:       {required_return:,.1f}% to reach $1M")
                    print()
        except Exception:
            pass

        print("=" * 100)
        print("\nDone!")
        print("=" * 100 + "\n")


if __name__ == "__main__":
    main()
