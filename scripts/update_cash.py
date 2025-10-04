"""
Update account cash balance and margin information.

Track your account health: cash, portfolio value, margin usage.

Usage:
    python scripts/update_cash.py                     # Interactive mode
    python scripts/update_cash.py --cash 875.54       # Quick update
    python scripts/update_cash.py --show              # Show current balance
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.storage.market_data_db import MarketDataDB


def show_current_balance():
    """Display current account balance."""
    with MarketDataDB() as db:
        result = db.conn.execute("""
            SELECT balance_date, cash_balance, portfolio_value, total_value,
                   margin_used, margin_available, buying_power
            FROM account_balance
            ORDER BY balance_date DESC
            LIMIT 1
        """).fetchone()

        if not result:
            print("! No balance records found")
            print()
            print("Run: python scripts/update_cash.py")
            return

        date, cash, portfolio, total, margin_used, margin_avail, buying_power = result

        print("=" * 70)
        print("ACCOUNT BALANCE")
        print("=" * 70)
        print()
        print(f"As of: {date}")
        print()
        print(f"Cash Balance:      ${cash:,.2f}")
        print(f"Portfolio Value:   ${portfolio:,.2f}")
        print(f"Total Value:       ${total:,.2f}")
        print()
        print(f"Margin Used:       ${margin_used:,.2f}")
        print(f"Margin Available:  ${margin_avail:,.2f}")
        print(f"Buying Power:      ${buying_power:,.2f}")
        print()

        # Calculate health metrics
        if total > 0:
            cash_pct = (cash / total) * 100
            margin_pct = (margin_used / total) * 100 if margin_used > 0 else 0

            print("Account Health:")
            print(f"  Cash %:    {cash_pct:.1f}%")
            print(f"  Margin %:  {margin_pct:.1f}%", end="")

            if margin_pct > 50:
                print("  [HIGH RISK]")
            elif margin_pct > 25:
                print("  [MODERATE RISK]")
            elif margin_pct > 0:
                print("  [LOW RISK]")
            else:
                print("  [NO MARGIN]")

        print()
        print("=" * 70)


def update_balance_interactive():
    """Interactive balance update."""
    print("=" * 70)
    print("UPDATE ACCOUNT BALANCE")
    print("=" * 70)
    print()

    # Show current balance first
    with MarketDataDB() as db:
        current = db.conn.execute("""
            SELECT balance_date, cash_balance, portfolio_value, total_value,
                   margin_used, margin_available
            FROM account_balance
            ORDER BY balance_date DESC
            LIMIT 1
        """).fetchone()

        if current:
            prev_date, prev_cash, prev_portfolio, prev_total, prev_margin_used, prev_margin_avail = current
            print("CURRENT BALANCE:")
            print(f"  Date:              {prev_date}")
            print(f"  Cash:              ${float(prev_cash):,.2f}")
            print(f"  Portfolio:         ${float(prev_portfolio):,.2f}")
            print(f"  Total:             ${float(prev_total):,.2f}")
            print(f"  Margin Used:       ${float(prev_margin_used):,.2f}")
            print(f"  Margin Available:  ${float(prev_margin_avail):,.2f}")
            print()
            print("-" * 70)
            print()
        else:
            print("No previous balance found - this is your first entry")
            print()

        # Show cash transaction history
        history = db.conn.execute("""
            SELECT balance_date, cash_balance, total_value
            FROM account_balance
            ORDER BY balance_date DESC
            LIMIT 10
        """).fetchall()

        if len(history) > 1:
            print("RECENT CASH HISTORY:")
            print(f"  {'Date':<12} {'Cash':<15} {'Total Value':<15} {'Cash Change':<15}")
            print(f"  {'-'*12} {'-'*15} {'-'*15} {'-'*15}")

            prev_cash_hist = None
            for i, (date, cash, total) in enumerate(history):
                cash_val = float(cash)
                total_val = float(total)

                if prev_cash_hist is not None:
                    change = cash_val - prev_cash_hist
                    change_str = f"${change:+,.2f}"
                else:
                    change_str = ""

                print(f"  {date}   ${cash_val:>12,.2f}  ${total_val:>12,.2f}  {change_str:>13}")
                prev_cash_hist = cash_val

            print()
            print("-" * 70)
            print()

    # Get date
    date_str = input("Date (YYYY-MM-DD) [today]: ").strip()
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    print()
    print("Enter new balance (or type 'c' to cancel):")
    print()

    # Get cash balance
    cash_str = input("Cash balance: $").strip()
    if cash_str.lower() == 'c':
        print("! Cancelled")
        return

    try:
        cash = float(cash_str.replace(',', ''))
    except ValueError:
        print("! Invalid cash amount")
        return

    # Get portfolio value (optional)
    portfolio_str = input("Portfolio value [0 or press Enter]: $").strip()
    if portfolio_str.lower() == 'c':
        print("! Cancelled")
        return
    portfolio = float(portfolio_str.replace(',', '')) if portfolio_str else 0

    # Calculate total
    total = cash + portfolio

    # Auto-calculate margin available (E*TRADE: 2x cash balance)
    margin_avail = cash * 2
    print()
    print(f"Margin Available (auto-calculated): ${margin_avail:,.2f}")
    print("  (E*TRADE provides 2x your cash balance as margin)")
    print()

    # Get margin used (optional)
    margin_used_str = input("Margin currently used [0 or press Enter]: $").strip()
    if margin_used_str.lower() == 'c':
        print("! Cancelled")
        return
    margin_used = float(margin_used_str.replace(',', '')) if margin_used_str else 0

    buying_power = cash + margin_avail

    # Get notes (optional)
    notes = input("Notes [press Enter to skip]: ").strip() or None

    # Show summary
    print()
    print("=" * 70)
    print("NEW BALANCE SUMMARY")
    print("=" * 70)
    print(f"Date:              {date_str}")
    print(f"Cash:              ${cash:,.2f}")
    print(f"Portfolio:         ${portfolio:,.2f}")
    print(f"Total Value:       ${total:,.2f}")
    print()
    print(f"Margin Used:       ${margin_used:,.2f}")
    print(f"Margin Available:  ${margin_avail:,.2f}")
    print(f"Buying Power:      ${buying_power:,.2f}")
    if notes:
        print(f"Notes:             {notes}")
    print("=" * 70)
    print()

    # Show change from previous
    if current:
        cash_change = cash - float(prev_cash)
        total_change = total - float(prev_total)
        total_change_pct = (total_change / float(prev_total) * 100) if float(prev_total) > 0 else 0

        print("CHANGE FROM PREVIOUS:")
        print(f"  Cash:              ${cash_change:+,.2f}")
        print(f"  Total Value:       ${total_change:+,.2f} ({total_change_pct:+.2f}%)")
        print()

        if cash_change > 0 and total_change > cash_change:
            print("  >> DEPOSIT + GAINS")
        elif cash_change > 0:
            print("  >> DEPOSIT (or portfolio loss offset by deposit)")
        elif cash_change < 0 and total_change < cash_change:
            print("  >> WITHDRAWAL + LOSS")
        elif cash_change < 0:
            print("  >> WITHDRAWAL (or portfolio gain offset by withdrawal)")
        elif total_change > 0:
            print("  >> GAINS")
        elif total_change < 0:
            print("  >> LOSS")
        else:
            print("  >> NO CHANGE")
        print()

    # Calculate health
    if total > 0:
        margin_pct = (margin_used / total) * 100 if margin_used > 0 else 0
        print(f"Margin Usage: {margin_pct:.1f}%", end="")
        if margin_pct > 50:
            print("  ! HIGH RISK - Consider reducing margin")
        elif margin_pct > 25:
            print("  ! Moderate risk")
        elif margin_pct > 0:
            print("  OK Low risk")
        else:
            print("  OK No margin (safest)")
        print()

    print("-" * 70)
    confirm = input("Save this balance? (y/n): ").strip().lower()
    if confirm != 'y':
        print("! Balance not saved")
        return

    # Save to database
    with MarketDataDB() as db:
        # Get SPY price for market comparison
        spy_price = None
        spy_return = None
        account_return = None

        try:
            # Get SPY price on this date
            spy_result = db.conn.execute("""
                SELECT close FROM stock_prices
                WHERE symbol = 'SPY' AND DATE(timestamp) = ?
                ORDER BY timestamp DESC LIMIT 1
            """, [date_str]).fetchone()

            if spy_result:
                spy_price = float(spy_result[0])

            # Calculate returns vs first balance entry
            first_balance = db.conn.execute("""
                SELECT total_value, balance_date, spy_price
                FROM account_balance
                ORDER BY balance_date ASC
                LIMIT 1
            """).fetchone()

            if first_balance:
                first_total = float(first_balance[0])
                account_return = ((total - first_total) / first_total) * 100 if first_total > 0 else 0

                if first_balance[2] and spy_price:
                    first_spy = float(first_balance[2])
                    spy_return = ((spy_price - first_spy) / first_spy) * 100 if first_spy > 0 else 0

        except Exception as e:
            print(f"! Warning: Could not calculate market comparison: {e}")

        # Delete existing record for this date
        db.conn.execute("DELETE FROM account_balance WHERE balance_date = ?", [date_str])
        # Insert new record
        db.conn.execute("""
            INSERT INTO account_balance (
                balance_date, cash_balance, portfolio_value, total_value,
                margin_used, margin_available, buying_power,
                spy_price, spy_return_pct, account_return_pct, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            date_str, cash, portfolio, total,
            margin_used, margin_avail, buying_power,
            spy_price, spy_return, account_return, notes
        ])

    print()
    print("OK Balance updated!")
    print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Update account cash balance")
    parser.add_argument(
        "--show",
        action="store_true",
        help="Show current balance"
    )
    parser.add_argument(
        "--cash",
        type=float,
        help="Cash balance"
    )
    parser.add_argument(
        "--portfolio",
        type=float,
        default=0,
        help="Portfolio value (default: 0)"
    )
    parser.add_argument(
        "--margin-used",
        type=float,
        default=0,
        help="Margin used (default: 0)"
    )
    parser.add_argument(
        "--margin-available",
        type=float,
        default=0,
        help="Margin available (default: 0)"
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Date (YYYY-MM-DD, default: today)"
    )

    args = parser.parse_args()

    if args.show:
        show_current_balance()
    elif args.cash is not None:
        # Quick mode
        date_str = args.date or datetime.now().strftime("%Y-%m-%d")
        total = args.cash + args.portfolio

        # Auto-calculate margin if not provided (E*TRADE: 2x cash)
        if args.margin_available == 0:
            margin_avail = args.cash * 2
        else:
            margin_avail = args.margin_available

        buying_power = args.cash + margin_avail

        with MarketDataDB() as db:
            # Get SPY price for market comparison
            spy_price = None
            spy_return = None
            account_return = None

            try:
                spy_result = db.conn.execute("""
                    SELECT close FROM stock_prices
                    WHERE symbol = 'SPY' AND DATE(timestamp) = ?
                    ORDER BY timestamp DESC LIMIT 1
                """, [date_str]).fetchone()

                if spy_result:
                    spy_price = float(spy_result[0])

                first_balance = db.conn.execute("""
                    SELECT total_value, balance_date, spy_price
                    FROM account_balance
                    ORDER BY balance_date ASC
                    LIMIT 1
                """).fetchone()

                if first_balance:
                    first_total = float(first_balance[0])
                    account_return = ((total - first_total) / first_total) * 100 if first_total > 0 else 0

                    if first_balance[2] and spy_price:
                        first_spy = float(first_balance[2])
                        spy_return = ((spy_price - first_spy) / first_spy) * 100 if first_spy > 0 else 0

            except Exception:
                pass

            # Delete existing record for this date
            db.conn.execute("DELETE FROM account_balance WHERE balance_date = ?", [date_str])
            # Insert new record
            db.conn.execute("""
                INSERT INTO account_balance (
                    balance_date, cash_balance, portfolio_value, total_value,
                    margin_used, margin_available, buying_power,
                    spy_price, spy_return_pct, account_return_pct
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                date_str, args.cash, args.portfolio, total,
                args.margin_used, margin_avail, buying_power,
                spy_price, spy_return, account_return
            ])

        print(f"OK Updated: ${args.cash:,.2f} cash, ${total:,.2f} total")
        if args.margin_used > 0:
            margin_pct = (args.margin_used / total) * 100
            print(f"   Margin: ${args.margin_used:,.2f} ({margin_pct:.1f}%)")
    else:
        update_balance_interactive()

    return 0


if __name__ == "__main__":
    sys.exit(main())
