"""
Manual trade entry for trade journal.

Allows you to record executed trades from your broker for performance tracking.

Usage:
    python scripts/add_trade.py                    # Interactive mode
    python scripts/add_trade.py --batch            # Batch entry mode
"""

import argparse
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.storage.market_data_db import MarketDataDB


def add_trade_interactive():
    """Interactive single trade entry."""
    print("=" * 70)
    print("ADD TRADE TO JOURNAL")
    print("=" * 70)
    print()

    # Get trade details
    date_str = input("Trade date (YYYY-MM-DD) [today]: ").strip()
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    action = input("Action (BUY/SELL): ").strip().upper()
    while action not in ["BUY", "SELL"]:
        print("! Invalid action. Enter BUY or SELL")
        action = input("Action (BUY/SELL): ").strip().upper()

    symbol = input("Symbol: ").strip().upper()

    quantity_str = input("Quantity: ").strip()
    try:
        quantity = int(quantity_str)
    except ValueError:
        print("! Invalid quantity")
        return

    price_str = input("Price executed: ").strip()
    try:
        price = float(price_str)
    except ValueError:
        print("! Invalid price")
        return

    # Calculate total
    total = quantity * price

    # Get strategy (optional)
    strategy = input("Strategy [trend_2x]: ").strip() or "trend_2x"

    # Get reason (optional)
    reason = input("Reason (optional): ").strip() or None

    # Confirm
    print()
    print("-" * 70)
    print(f"Date:     {date_str}")
    print(f"Action:   {action}")
    print(f"Symbol:   {symbol}")
    print(f"Quantity: {quantity}")
    print(f"Price:    ${price:.2f}")
    print(f"Total:    ${total:.2f}")
    print(f"Strategy: {strategy}")
    if reason:
        print(f"Reason:   {reason}")
    print("-" * 70)
    print()

    confirm = input("Save this trade? (y/n): ").strip().lower()
    if confirm != 'y':
        print("! Trade not saved")
        return

    # Save to database
    with MarketDataDB() as db:
        db.conn.execute("""
            INSERT INTO trade_journal (
                trade_date, symbol, action, quantity, price,
                total_value, strategy, reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, [
            date_str, symbol, action, quantity, price,
            total, strategy, reason
        ])

    print()
    print("OK Trade saved to journal!")
    print()


def add_trades_batch():
    """Batch trade entry mode."""
    print("=" * 70)
    print("BATCH TRADE ENTRY")
    print("=" * 70)
    print()
    print("Enter trades one per line in format:")
    print("  DATE,ACTION,SYMBOL,QUANTITY,PRICE")
    print()
    print("Example:")
    print("  2025-10-02,SELL,UPS,20,85.79")
    print("  2025-10-02,BUY,ELV,4,340.365")
    print()
    print("Enter blank line when done")
    print()

    trades = []
    while True:
        line = input().strip()
        if not line:
            break

        parts = [p.strip() for p in line.split(',')]
        if len(parts) != 5:
            print(f"! Invalid format: {line}")
            continue

        try:
            date_str, action, symbol, quantity_str, price_str = parts
            quantity = int(quantity_str)
            price = float(price_str)
            total = quantity * price

            trades.append({
                'date': date_str,
                'action': action.upper(),
                'symbol': symbol.upper(),
                'quantity': quantity,
                'price': price,
                'total': total
            })

        except ValueError as e:
            print(f"! Parse error: {line} ({e})")
            continue

    if not trades:
        print("! No trades entered")
        return

    # Show summary
    print()
    print("-" * 70)
    print(f"SUMMARY: {len(trades)} trades")
    print("-" * 70)
    for i, trade in enumerate(trades, 1):
        print(f"{i}. {trade['date']} {trade['action']:4} {trade['symbol']:6} "
              f"{trade['quantity']:>4} @ ${trade['price']:.2f} = ${trade['total']:.2f}")
    print("-" * 70)
    print()

    confirm = input(f"Save {len(trades)} trades? (y/n): ").strip().lower()
    if confirm != 'y':
        print("! Trades not saved")
        return

    # Save all trades
    with MarketDataDB() as db:
        for trade in trades:
            db.conn.execute("""
                INSERT INTO trade_journal (
                    trade_date, symbol, action, quantity, price,
                    total_value, strategy, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, [
                trade['date'], trade['symbol'], trade['action'],
                trade['quantity'], trade['price'], trade['total'],
                'trend_2x'
            ])

    print()
    print(f"OK Saved {len(trades)} trades to journal!")
    print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Add trades to trade journal")
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Batch entry mode (CSV format)"
    )
    parser.add_argument(
        "--quick",
        nargs=5,
        metavar=("DATE", "ACTION", "SYMBOL", "QTY", "PRICE"),
        help="Quick add: DATE ACTION SYMBOL QTY PRICE"
    )

    args = parser.parse_args()

    if args.quick:
        # Quick mode
        date_str, action, symbol, qty_str, price_str = args.quick

        try:
            quantity = int(qty_str)
            price = float(price_str)
            total = quantity * price

            with MarketDataDB() as db:
                db.conn.execute("""
                    INSERT INTO trade_journal (
                        trade_date, symbol, action, quantity, price,
                        total_value, strategy, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, [
                    date_str, action.upper(), symbol.upper(),
                    quantity, price, total, 'trend_2x'
                ])

            print(f"OK Added: {date_str} {action.upper()} {symbol.upper()} "
                  f"{quantity} @ ${price:.2f} = ${total:.2f}")

        except Exception as e:
            print(f"! Error: {e}")
            return 1

    elif args.batch:
        add_trades_batch()
    else:
        add_trade_interactive()

    return 0


if __name__ == "__main__":
    sys.exit(main())
