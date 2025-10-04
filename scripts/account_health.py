"""
Account Health Dashboard.

Shows comprehensive account status: cash, margin, portfolio value, and risk metrics.

Usage:
    python scripts/account_health.py
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.storage.market_data_db import MarketDataDB


def main():
    """Display account health dashboard."""
    with MarketDataDB() as db:
        # Get latest balance
        balance = db.conn.execute("""
            SELECT balance_date, cash_balance, portfolio_value, total_value,
                   margin_used, margin_available, buying_power, notes
            FROM account_balance
            ORDER BY balance_date DESC
            LIMIT 1
        """).fetchone()

        if not balance:
            print("=" * 70)
            print("NO BALANCE DATA")
            print("=" * 70)
            print()
            print("! No balance records found")
            print()
            print("To add your balance:")
            print("  python scripts/update_cash.py")
            print()
            return 1

        date, cash, portfolio, total, margin_used, margin_avail, buying_power, notes = balance

        # Calculate metrics
        cash_pct = (cash / total * 100) if total > 0 else 0
        portfolio_pct = (portfolio / total * 100) if total > 0 else 0
        margin_pct = (margin_used / total * 100) if total > 0 and margin_used > 0 else 0

        # Determine risk level
        if margin_pct > 50:
            risk_level = "HIGH RISK"
            risk_color = "🔴"
        elif margin_pct > 25:
            risk_level = "MODERATE"
            risk_color = "🟡"
        elif margin_pct > 0:
            risk_level = "LOW RISK"
            risk_color = "🟢"
        else:
            risk_level = "NO MARGIN"
            risk_color = "✓"

        # Display dashboard
        print("=" * 70)
        print("ACCOUNT HEALTH DASHBOARD")
        print("=" * 70)
        print()
        print(f"Date: {date}")
        if notes:
            print(f"Notes: {notes}")
        print()

        # Account Value Section
        print("ACCOUNT VALUE")
        print("-" * 70)
        print(f"Cash Balance:      ${cash:>12,.2f}  ({cash_pct:>5.1f}%)")
        print(f"Portfolio Value:   ${portfolio:>12,.2f}  ({portfolio_pct:>5.1f}%)")
        print(f"{'─' * 70}")
        print(f"Total Value:       ${total:>12,.2f}  (100.0%)")
        print()

        # Margin Section
        print("MARGIN & BUYING POWER")
        print("-" * 70)
        print(f"Margin Used:       ${margin_used:>12,.2f}  ({margin_pct:>5.1f}% of total)")
        print(f"Margin Available:  ${margin_avail:>12,.2f}")
        print(f"Buying Power:      ${buying_power:>12,.2f}")
        print()

        # Risk Assessment
        print("RISK ASSESSMENT")
        print("-" * 70)
        print(f"Risk Level: {risk_color} {risk_level}")
        print()

        if margin_pct > 50:
            print("⚠ WARNING: High margin usage detected!")
            print("  - Margin over 50% is very risky")
            print("  - Consider closing positions or adding cash")
            print("  - Market downturn could trigger margin call")
        elif margin_pct > 25:
            print("! Moderate margin usage")
            print("  - Monitor positions closely")
            print("  - Have cash ready for potential margin requirements")
        elif margin_pct > 0:
            print("✓ Low margin usage (safe range)")
            print("  - Current leverage is manageable")
        else:
            print("✓ No margin used (safest)")
            print("  - Cash account or fully paid positions")

        print()

        # Path to $1M
        goal = 1_000_000
        remaining = goal - total
        progress_pct = (total / goal * 100)

        print("PATH TO $1,000,000")
        print("-" * 70)
        print(f"Current:    ${total:>12,.2f}")
        print(f"Goal:       ${goal:>12,.2f}")
        print(f"Remaining:  ${remaining:>12,.2f}")
        print(f"Progress:   {progress_pct:>5.1f}%")
        print()

        # Progress bar
        bar_width = 50
        filled = int(bar_width * progress_pct / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        print(f"[{bar}] {progress_pct:.1f}%")
        print()

        # Historical comparison
        history = db.conn.execute("""
            SELECT balance_date, total_value
            FROM account_balance
            WHERE balance_date < ?
            ORDER BY balance_date DESC
            LIMIT 1
        """, [date]).fetchone()

        if history:
            prev_date, prev_total = history
            change = total - prev_total
            change_pct = (change / prev_total * 100) if prev_total > 0 else 0

            print("PERFORMANCE")
            print("-" * 70)
            print(f"Previous ({prev_date}): ${prev_total:,.2f}")
            print(f"Change:                  ${change:+,.2f} ({change_pct:+.1f}%)")
            print()

        print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
