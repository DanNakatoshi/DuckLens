"""Portfolio management system with position tracking and daily recommendations."""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Position:
    """Represents a stock position."""

    symbol: str
    quantity: int
    price_paid: float
    purchase_date: str
    notes: str = ""

    @property
    def cost_basis(self) -> float:
        """Total cost of position."""
        return self.quantity * self.price_paid


@dataclass
class Portfolio:
    """Portfolio with positions and cash."""

    cash: float
    positions: dict[str, Position]
    last_updated: str

    def add_position(
        self, symbol: str, quantity: int, price_paid: float, notes: str = ""
    ):
        """Add or update a position."""
        if symbol in self.positions:
            # Update existing position (average cost)
            old_pos = self.positions[symbol]
            total_qty = old_pos.quantity + quantity
            total_cost = (old_pos.quantity * old_pos.price_paid) + (
                quantity * price_paid
            )
            avg_price = total_cost / total_qty

            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=total_qty,
                price_paid=avg_price,
                purchase_date=old_pos.purchase_date,
                notes=f"{old_pos.notes}; Added {quantity} @ ${price_paid:.2f}",
            )
        else:
            # New position
            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                price_paid=price_paid,
                purchase_date=datetime.now().strftime("%Y-%m-%d"),
                notes=notes,
            )

        # Deduct from cash
        self.cash -= quantity * price_paid
        self.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def remove_position(self, symbol: str, quantity: Optional[int] = None):
        """Sell position (partial or full)."""
        if symbol not in self.positions:
            raise ValueError(f"No position found for {symbol}")

        pos = self.positions[symbol]

        if quantity is None or quantity >= pos.quantity:
            # Sell entire position
            del self.positions[symbol]
        else:
            # Partial sell
            pos.quantity -= quantity

        self.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position by symbol."""
        return self.positions.get(symbol)

    def total_invested(self) -> float:
        """Total amount invested in positions."""
        return sum(pos.cost_basis for pos in self.positions.values())

    def total_value_at_prices(self, prices: dict[str, float]) -> float:
        """Calculate total portfolio value at given prices."""
        position_value = sum(
            pos.quantity * prices.get(pos.symbol, pos.price_paid)
            for pos in self.positions.values()
        )
        return self.cash + position_value


class PortfolioManager:
    """Manage portfolio persistence and operations."""

    def __init__(self, portfolio_file: str = "data/portfolio.json"):
        self.portfolio_file = Path(portfolio_file)
        self.portfolio_file.parent.mkdir(parents=True, exist_ok=True)

    def load_portfolio(self) -> Portfolio:
        """Load portfolio from file."""
        if not self.portfolio_file.exists():
            # Create default portfolio
            return Portfolio(cash=0.0, positions={}, last_updated=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        with open(self.portfolio_file, "r") as f:
            data = json.load(f)

        positions = {
            symbol: Position(**pos_data) for symbol, pos_data in data["positions"].items()
        }

        return Portfolio(
            cash=data["cash"],
            positions=positions,
            last_updated=data["last_updated"],
        )

    def save_portfolio(self, portfolio: Portfolio):
        """Save portfolio to file."""
        data = {
            "cash": portfolio.cash,
            "positions": {
                symbol: asdict(pos) for symbol, pos in portfolio.positions.items()
            },
            "last_updated": portfolio.last_updated,
        }

        with open(self.portfolio_file, "w") as f:
            json.dump(data, f, indent=2)

    def import_from_etrade(self, positions_data: list[dict], cash: float):
        """
        Import positions from E*TRADE export.

        Args:
            positions_data: List of dicts with keys: symbol, quantity, price_paid
            cash: Cash balance
        """
        portfolio = Portfolio(
            cash=cash,
            positions={},
            last_updated=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        for pos_data in positions_data:
            portfolio.positions[pos_data["symbol"]] = Position(
                symbol=pos_data["symbol"],
                quantity=pos_data["quantity"],
                price_paid=pos_data["price_paid"],
                purchase_date=pos_data.get("purchase_date", datetime.now().strftime("%Y-%m-%d")),
                notes=pos_data.get("notes", "Imported from E*TRADE"),
            )

        self.save_portfolio(portfolio)
        return portfolio
