"""Import your E*TRADE portfolio into DuckLens."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.portfolio.portfolio_manager import PortfolioManager


def main():
    """Import portfolio from E*TRADE data."""
    print("\n" + "=" * 70)
    print("IMPORT PORTFOLIO FROM E*TRADE")
    print("=" * 70 + "\n")

    # Your current E*TRADE positions
    positions = [
        {"symbol": "UNH", "quantity": 5, "price_paid": 309.416},
        {"symbol": "BABA", "quantity": 20, "price_paid": 179.47},
        {"symbol": "COP", "quantity": 20, "price_paid": 123.6585},
        {"symbol": "UPS", "quantity": 20, "price_paid": 153.4},
        {"symbol": "BTC", "quantity": 100, "price_paid": 50.519},
        {"symbol": "IREN", "quantity": 100, "price_paid": 44.675},
        {"symbol": "ETH", "quantity": 100, "price_paid": 39.1546},
        {"symbol": "INTC", "quantity": 50, "price_paid": 34.795},
        {"symbol": "CSIQ", "quantity": 266, "price_paid": 19.6339},
        {"symbol": "EPSM", "quantity": 30, "price_paid": 37.91},
        {"symbol": "OPEN", "quantity": 400, "price_paid": 8.3299},
        {"symbol": "NEON", "quantity": 220, "price_paid": 4.32691},
    ]

    cash = 772.45

    # Import
    pm = PortfolioManager()
    portfolio = pm.import_from_etrade(positions, cash)

    # Summary
    total_invested = sum(
        pos["quantity"] * pos["price_paid"] for pos in positions
    )

    print(f"Imported {len(positions)} positions")
    print(f"Total invested: ${total_invested:,.2f}")
    print(f"Cash: ${cash:,.2f}")
    print(f"Total portfolio value (at cost): ${total_invested + cash:,.2f}\n")

    print("Portfolio saved to: data/portfolio.json\n")
    print("Run 'python scripts/portfolio_review.py' for daily review\n")

    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
