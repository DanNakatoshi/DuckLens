"""
Migrate account_balance table to add SPY tracking columns.

Adds:
- spy_price: SPY price on balance date
- spy_return_pct: SPY return since first entry
- account_return_pct: Account return since first entry
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.storage.market_data_db import MarketDataDB


def main():
    """Add new columns to account_balance table."""
    print("\n" + "=" * 70)
    print("MIGRATE ACCOUNT_BALANCE TABLE")
    print("=" * 70)
    print()

    with MarketDataDB() as db:
        # Check if columns already exist
        columns_exist = False
        try:
            db.conn.execute("SELECT spy_price FROM account_balance LIMIT 1")
            columns_exist = True
            print("Columns already exist - checking if data needs to be populated...")
            print()
        except Exception:
            pass  # Columns don't exist, proceed with migration

        if not columns_exist:
            print("Adding new columns to account_balance table...")
            print()

            # Add new columns
            try:
                db.conn.execute("""
                    ALTER TABLE account_balance
                    ADD COLUMN spy_price DECIMAL(18, 4)
                """)
                print("OK Added spy_price column")
            except Exception as e:
                print(f"! spy_price column may already exist: {e}")

            try:
                db.conn.execute("""
                    ALTER TABLE account_balance
                    ADD COLUMN spy_return_pct DECIMAL(10, 4)
                """)
                print("OK Added spy_return_pct column")
            except Exception as e:
                print(f"! spy_return_pct column may already exist: {e}")

            try:
                db.conn.execute("""
                    ALTER TABLE account_balance
                    ADD COLUMN account_return_pct DECIMAL(10, 4)
                """)
                print("OK Added account_return_pct column")
            except Exception as e:
                print(f"! account_return_pct column may already exist: {e}")

            print()
            print("=" * 70)
            print()

        # Now populate SPY prices for existing records
        print("Populating SPY prices for existing records...")
        print()

        balances = db.conn.execute("""
            SELECT balance_date, total_value
            FROM account_balance
            ORDER BY balance_date ASC
        """).fetchall()

        if not balances:
            print("No existing balance records found")
            return

        first_total = float(balances[0][1])
        first_spy = None

        for balance_date, total_value in balances:
            total_value = float(total_value)

            # Get SPY price on this date
            spy_result = db.conn.execute("""
                SELECT close FROM stock_prices
                WHERE symbol = 'SPY' AND DATE(timestamp) = ?
                ORDER BY timestamp DESC LIMIT 1
            """, [balance_date]).fetchone()

            spy_price = float(spy_result[0]) if spy_result else None

            if spy_price and first_spy is None:
                first_spy = spy_price

            # Calculate returns
            account_return = None
            spy_return = None

            if first_total > 0:
                account_return = ((total_value - first_total) / first_total) * 100

            if first_spy and spy_price:
                spy_return = ((spy_price - first_spy) / first_spy) * 100

            # Update record
            db.conn.execute("""
                UPDATE account_balance
                SET spy_price = ?,
                    spy_return_pct = ?,
                    account_return_pct = ?
                WHERE balance_date = ?
            """, [spy_price, spy_return, account_return, balance_date])

            spy_str = f"${spy_price:.2f}" if spy_price else "$0.00"
            ret_str = f"{account_return:+.2f}%" if account_return is not None else "0.00%"
            print(f"OK Updated {balance_date}: SPY={spy_str}, Account Return={ret_str}")

        print()
        print("=" * 70)
        print()
        print("Migration complete!")
        print()


if __name__ == "__main__":
    main()
