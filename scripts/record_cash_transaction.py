"""
Record cash deposits and withdrawals.

Works like a real brokerage account:
- Deposit: Add cash to account
- Withdrawal: Remove cash from account
- View transaction history
- Edit or delete past transactions
- Portfolio value is calculated automatically from holdings
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.storage.market_data_db import MarketDataDB
from src.portfolio.portfolio_manager import PortfolioManager


def view_all_transactions():
    """View all cash transaction history."""
    print("=" * 70)
    print("CASH TRANSACTION HISTORY")
    print("=" * 70)
    print()

    with MarketDataDB() as db:
        transactions = db.conn.execute("""
            SELECT balance_date, cash_balance, portfolio_value, total_value,
                   margin_available, buying_power, notes
            FROM account_balance
            ORDER BY balance_date DESC
        """).fetchall()

        if not transactions:
            print("No transactions found")
            print()
            return

        print(f"Total transactions: {len(transactions)}")
        print()
        print(f"{'#':<4} {'Date':<12} {'Cash':<15} {'Portfolio':<15} {'Total':<15} {'Notes':<30}")
        print(f"{'-'*4} {'-'*12} {'-'*15} {'-'*15} {'-'*15} {'-'*30}")

        prev_cash = None
        for i, (date, cash, portfolio, total, margin_avail, buying_power, notes) in enumerate(transactions, 1):
            cash_val = float(cash)
            portfolio_val = float(portfolio)
            total_val = float(total)

            # Calculate change from previous
            if prev_cash is not None:
                change = cash_val - prev_cash
                if change > 0:
                    change_str = f"+${change:,.2f}"
                elif change < 0:
                    change_str = f"-${abs(change):,.2f}"
                else:
                    change_str = ""
            else:
                change_str = ""

            notes_str = (notes[:27] + "...") if notes and len(notes) > 30 else (notes or "")

            print(f"{i:<4} {date}   ${cash_val:>12,.2f}  ${portfolio_val:>12,.2f}  "
                  f"${total_val:>12,.2f}  {notes_str:<30}")

            if change_str:
                print(f"     {'':12}  {change_str:>14}")

            prev_cash = cash_val

        print()
        print("=" * 70)


def edit_transaction():
    """Edit a past transaction."""
    print("=" * 70)
    print("EDIT PAST TRANSACTION")
    print("=" * 70)
    print()

    with MarketDataDB() as db:
        transactions = db.conn.execute("""
            SELECT balance_date, cash_balance, portfolio_value, total_value, notes
            FROM account_balance
            ORDER BY balance_date DESC
            LIMIT 20
        """).fetchall()

        if not transactions:
            print("No transactions found")
            print()
            return

        print("RECENT TRANSACTIONS (last 20):")
        print()
        print(f"{'#':<4} {'Date':<12} {'Cash':<15} {'Portfolio':<15} {'Total':<15} {'Notes':<30}")
        print(f"{'-'*4} {'-'*12} {'-'*15} {'-'*15} {'-'*15} {'-'*30}")

        for i, (date, cash, portfolio, total, notes) in enumerate(transactions, 1):
            cash_val = float(cash)
            portfolio_val = float(portfolio)
            total_val = float(total)
            notes_str = (notes[:27] + "...") if notes and len(notes) > 30 else (notes or "")

            print(f"{i:<4} {date}   ${cash_val:>12,.2f}  ${portfolio_val:>12,.2f}  "
                  f"${total_val:>12,.2f}  {notes_str:<30}")

        print()
        print("-" * 70)
        print()

        # Select transaction
        choice = input("Enter transaction # to edit [or 'c' to cancel]: ").strip()

        if choice.lower() == 'c':
            print("! Cancelled")
            return

        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(transactions):
                print("! Invalid transaction number")
                return

            selected = transactions[idx]
            date, cash, portfolio, total, notes = selected
            cash = float(cash)
            portfolio = float(portfolio)

            print()
            print(f"EDITING TRANSACTION: {date}")
            print(f"  Current Cash:      ${cash:,.2f}")
            print(f"  Current Portfolio: ${portfolio:,.2f} (auto-calculated)")
            print(f"  Current Notes:     {notes or '(none)'}")
            print()

            # Edit cash
            new_cash_str = input(f"New cash balance [${cash:,.2f}]: $").strip()
            if new_cash_str.lower() == 'c':
                print("! Cancelled")
                return

            if new_cash_str:
                new_cash = float(new_cash_str.replace(',', ''))
            else:
                new_cash = cash

            # Edit notes
            new_notes = input(f"New notes [{notes or '(none)'}]: ").strip()
            if new_notes.lower() == 'c':
                print("! Cancelled")
                return

            if not new_notes:
                new_notes = notes

            # Recalculate portfolio value for this date
            portfolio_value = get_current_portfolio_value()
            total_value = new_cash + portfolio_value
            margin_avail = new_cash * 2
            buying_power = new_cash + margin_avail

            # Show summary
            print()
            print("=" * 70)
            print("UPDATED TRANSACTION")
            print("=" * 70)
            print(f"Date:              {date}")
            print(f"Cash:              ${new_cash:,.2f} (was ${cash:,.2f})")
            print(f"Portfolio:         ${portfolio_value:,.2f} (auto-calculated)")
            print(f"Total:             ${total_value:,.2f}")
            print(f"Notes:             {new_notes}")
            print("=" * 70)
            print()

            confirm = input("Save changes? (y/n): ").strip().lower()
            if confirm != 'y':
                print("! Changes not saved")
                return

            # Update database
            db.conn.execute("""
                UPDATE account_balance
                SET cash_balance = ?,
                    portfolio_value = ?,
                    total_value = ?,
                    margin_available = ?,
                    buying_power = ?,
                    notes = ?
                WHERE balance_date = ?
            """, [new_cash, portfolio_value, total_value, margin_avail, buying_power, new_notes, date])

            print()
            print("OK Transaction updated!")
            print()

        except ValueError:
            print("! Invalid input")
            return
        except Exception as e:
            print(f"! Error: {e}")
            return


def delete_transaction():
    """Delete a past transaction."""
    print("=" * 70)
    print("DELETE PAST TRANSACTION")
    print("=" * 70)
    print()

    with MarketDataDB() as db:
        transactions = db.conn.execute("""
            SELECT balance_date, cash_balance, portfolio_value, total_value, notes
            FROM account_balance
            ORDER BY balance_date DESC
            LIMIT 20
        """).fetchall()

        if not transactions:
            print("No transactions found")
            print()
            return

        print("RECENT TRANSACTIONS (last 20):")
        print()
        print(f"{'#':<4} {'Date':<12} {'Cash':<15} {'Portfolio':<15} {'Total':<15} {'Notes':<30}")
        print(f"{'-'*4} {'-'*12} {'-'*15} {'-'*15} {'-'*15} {'-'*30}")

        for i, (date, cash, portfolio, total, notes) in enumerate(transactions, 1):
            cash_val = float(cash)
            portfolio_val = float(portfolio)
            total_val = float(total)
            notes_str = (notes[:27] + "...") if notes and len(notes) > 30 else (notes or "")

            print(f"{i:<4} {date}   ${cash_val:>12,.2f}  ${portfolio_val:>12,.2f}  "
                  f"${total_val:>12,.2f}  {notes_str:<30}")

        print()
        print("-" * 70)
        print()

        # Select transaction
        choice = input("Enter transaction # to DELETE [or 'c' to cancel]: ").strip()

        if choice.lower() == 'c':
            print("! Cancelled")
            return

        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(transactions):
                print("! Invalid transaction number")
                return

            selected = transactions[idx]
            date, cash, portfolio, total, notes = selected

            print()
            print(f"DELETE TRANSACTION: {date}")
            print(f"  Cash:      ${float(cash):,.2f}")
            print(f"  Portfolio: ${float(portfolio):,.2f}")
            print(f"  Total:     ${float(total):,.2f}")
            print(f"  Notes:     {notes or '(none)'}")
            print()
            print("! WARNING: This cannot be undone!")
            print()

            confirm = input("Are you sure you want to delete this? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("! Transaction not deleted")
                return

            # Delete from database
            db.conn.execute("DELETE FROM account_balance WHERE balance_date = ?", [date])

            print()
            print("OK Transaction deleted!")
            print()

        except ValueError:
            print("! Invalid input")
            return
        except Exception as e:
            print(f"! Error: {e}")
            return


def get_current_portfolio_value():
    """Calculate current portfolio value from holdings."""
    portfolio_manager = PortfolioManager()
    portfolio = portfolio_manager.load_portfolio()

    if not portfolio.positions:
        return 0.0

    # Get latest prices for all holdings
    total_value = 0.0
    with MarketDataDB() as db:
        for ticker, position in portfolio.positions.items():
            result = db.conn.execute("""
                SELECT close FROM stock_prices
                WHERE symbol = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, [ticker]).fetchone()

            if result:
                price = float(result[0])
                total_value += position.quantity * price

    return total_value


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
            print("Record your first deposit with:")
            print("  python scripts/record_cash_transaction.py --deposit 1000")
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


def record_transaction_interactive():
    """Interactive transaction recording."""
    print("=" * 70)
    print("RECORD CASH TRANSACTION")
    print("=" * 70)
    print()

    # Show current balance
    with MarketDataDB() as db:
        current = db.conn.execute("""
            SELECT balance_date, cash_balance, portfolio_value, total_value
            FROM account_balance
            ORDER BY balance_date DESC
            LIMIT 1
        """).fetchone()

        if current:
            prev_date, prev_cash, prev_portfolio, prev_total = current
            prev_cash = float(prev_cash)
            prev_portfolio = float(prev_portfolio)
            prev_total = float(prev_total)

            print("CURRENT BALANCE:")
            print(f"  Date:              {prev_date}")
            print(f"  Cash:              ${prev_cash:,.2f}")
            print(f"  Portfolio:         ${prev_portfolio:,.2f} (auto-calculated from holdings)")
            print(f"  Total:             ${prev_total:,.2f}")
            print()
        else:
            print("No previous balance found - this is your first transaction")
            print()
            prev_date = None
            prev_cash = 0.0
            prev_portfolio = 0.0
            prev_total = 0.0

        # Show recent transaction history
        history = db.conn.execute("""
            SELECT balance_date, cash_balance, total_value, notes
            FROM account_balance
            ORDER BY balance_date DESC
            LIMIT 5
        """).fetchall()

        if len(history) > 1:
            print("RECENT TRANSACTIONS:")
            print(f"  {'Date':<12} {'Cash':<15} {'Total':<15} {'Notes':<30}")
            print(f"  {'-'*12} {'-'*15} {'-'*15} {'-'*30}")

            for date, cash, total, notes in history:
                cash_val = float(cash)
                total_val = float(total)
                notes_str = (notes[:27] + "...") if notes and len(notes) > 30 else (notes or "")
                print(f"  {date}   ${cash_val:>12,.2f}  ${total_val:>12,.2f}  {notes_str}")

            print()

        print("-" * 70)
        print()

    # Transaction type
    print("SELECT TRANSACTION TYPE:")
    print()
    print("  1. Deposit   - Add cash to account")
    print("  2. Withdraw  - Remove cash from account")
    print()

    choice = input("Enter choice (1 or 2) [or 'c' to cancel]: ").strip()

    if choice.lower() == 'c':
        print("! Cancelled")
        return

    if choice == '1':
        transaction_type = "DEPOSIT"
        print()
        print(">> DEPOSIT CASH")
        print()
        amount_str = input("Amount to deposit: $").strip()
    elif choice == '2':
        transaction_type = "WITHDRAWAL"
        print()
        print(">> WITHDRAW CASH")
        print()
        amount_str = input("Amount to withdraw: $").strip()
    else:
        print("! Invalid choice - must be 1 or 2")
        return

    if amount_str.lower() == 'c':
        print("! Cancelled")
        return

    try:
        amount = float(amount_str.replace(',', ''))
        if amount <= 0:
            print("! Amount must be greater than 0")
            return
    except ValueError:
        print("! Invalid amount - must be a number")
        return

    # Get date
    print()
    date_str = input("Transaction date (YYYY-MM-DD) [today]: ").strip()
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    # Calculate new cash balance
    if transaction_type == "DEPOSIT":
        new_cash = prev_cash + amount
    else:
        new_cash = prev_cash - amount
        if new_cash < 0:
            print(f"! Warning: Cash balance will be negative (${new_cash:,.2f})")
            confirm = input("Continue? (y/n): ").strip().lower()
            if confirm != 'y':
                print("! Cancelled")
                return

    # Get current portfolio value from holdings
    portfolio_value = get_current_portfolio_value()

    # Calculate totals
    total = new_cash + portfolio_value
    margin_avail = new_cash * 2  # E*TRADE: 2x cash
    buying_power = new_cash + margin_avail

    # Notes
    default_note = f"{transaction_type}: ${amount:,.2f}"
    notes = input(f"Notes [{default_note}]: ").strip() or default_note

    # Show summary
    print()
    print("=" * 70)
    print("TRANSACTION SUMMARY")
    print("=" * 70)
    print(f"Date:              {date_str}")
    print(f"Type:              {transaction_type}")
    print(f"Amount:            ${amount:,.2f}")
    print()
    print("NEW BALANCE:")
    print(f"  Cash:            ${new_cash:,.2f} (was ${prev_cash:,.2f})")
    print(f"  Portfolio:       ${portfolio_value:,.2f} (auto-calculated)")
    print(f"  Total:           ${total:,.2f}")
    print()
    print(f"  Margin Avail:    ${margin_avail:,.2f}")
    print(f"  Buying Power:    ${buying_power:,.2f}")
    print()
    print(f"Notes:             {notes}")
    print("=" * 70)
    print()

    # Show change
    cash_change = new_cash - prev_cash
    total_change = total - prev_total
    total_change_pct = (total_change / prev_total * 100) if prev_total > 0 else 0

    print("CHANGE:")
    print(f"  Cash:            ${cash_change:+,.2f}")
    print(f"  Total:           ${total_change:+,.2f} ({total_change_pct:+.2f}%)")
    print()

    confirm = input("Save this transaction? (y/n): ").strip().lower()
    if confirm != 'y':
        print("! Transaction not saved")
        return

    # Save to database
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
            date_str, new_cash, portfolio_value, total,
            0, margin_avail, buying_power,
            spy_price, spy_return, account_return, notes
        ])

    print()
    print("OK Transaction recorded!")
    print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Record cash deposits and withdrawals")
    parser.add_argument(
        "--show",
        action="store_true",
        help="Show current balance"
    )
    parser.add_argument(
        "--deposit",
        type=float,
        help="Deposit amount"
    )
    parser.add_argument(
        "--withdrawal",
        type=float,
        help="Withdrawal amount"
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Date (YYYY-MM-DD, default: today)"
    )
    parser.add_argument(
        "--note",
        type=str,
        help="Transaction note"
    )

    parser.add_argument(
        "--history",
        action="store_true",
        help="View all transaction history"
    )
    parser.add_argument(
        "--edit",
        action="store_true",
        help="Edit a past transaction"
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete a past transaction"
    )

    args = parser.parse_args()

    if args.show:
        show_current_balance()
    elif args.history:
        view_all_transactions()
    elif args.edit:
        edit_transaction()
    elif args.delete:
        delete_transaction()
    elif args.deposit is not None or args.withdrawal is not None:
        # Quick mode
        date_str = args.date or datetime.now().strftime("%Y-%m-%d")

        # Get current balance
        with MarketDataDB() as db:
            current = db.conn.execute("""
                SELECT cash_balance FROM account_balance
                ORDER BY balance_date DESC LIMIT 1
            """).fetchone()

            prev_cash = float(current[0]) if current else 0

        # Calculate new cash
        if args.deposit:
            new_cash = prev_cash + args.deposit
            transaction_type = "DEPOSIT"
            amount = args.deposit
        else:
            new_cash = prev_cash - args.withdrawal
            transaction_type = "WITHDRAWAL"
            amount = args.withdrawal

        # Get portfolio value
        portfolio_value = get_current_portfolio_value()
        total = new_cash + portfolio_value
        margin_avail = new_cash * 2
        buying_power = new_cash + margin_avail

        # Notes
        notes = args.note or f"{transaction_type}: ${amount:,.2f}"

        # Save
        with MarketDataDB() as db:
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

            db.conn.execute("DELETE FROM account_balance WHERE balance_date = ?", [date_str])
            db.conn.execute("""
                INSERT INTO account_balance (
                    balance_date, cash_balance, portfolio_value, total_value,
                    margin_used, margin_available, buying_power,
                    spy_price, spy_return_pct, account_return_pct, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                date_str, new_cash, portfolio_value, total,
                0, margin_avail, buying_power,
                spy_price, spy_return, account_return, notes
            ])

        print(f"OK {transaction_type}: ${amount:,.2f}")
        print(f"   New cash: ${new_cash:,.2f}, Total: ${total:,.2f}")
    else:
        # Interactive menu
        while True:
            print("=" * 70)
            print("CASH TRANSACTION MENU")
            print("=" * 70)
            print()
            print("  1. Record new transaction (Deposit/Withdraw)")
            print("  2. View transaction history")
            print("  3. Edit past transaction")
            print("  4. Delete past transaction")
            print("  5. Show current balance")
            print("  0. Exit")
            print()

            choice = input("Enter choice: ").strip()

            if choice == '1':
                record_transaction_interactive()
            elif choice == '2':
                view_all_transactions()
            elif choice == '3':
                edit_transaction()
            elif choice == '4':
                delete_transaction()
            elif choice == '5':
                show_current_balance()
            elif choice == '0':
                print("Goodbye!")
                break
            else:
                print("! Invalid choice")
                print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
