"""Trade journal - Log every trade with full context for later analysis."""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class TradeLog:
    """Complete record of a trade with all context."""

    # Trade basics
    symbol: str
    direction: str  # "BUY" or "SELL"
    quantity: int
    price: float
    trade_date: str
    trade_value: float

    # Strategy context
    signal_type: str  # "TREND_CHANGE", "DEATH_CROSS", "VOLUME_SPIKE", etc.
    confidence: float
    trend_state: str  # "BULLISH", "BEARISH", "NEUTRAL"

    # Technical indicators at trade time
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    volume: Optional[float] = None
    volume_avg: Optional[float] = None

    # Trade context
    days_until_earnings: Optional[int] = None
    vxx_level: Optional[float] = None
    market_regime: str = "NORMAL"  # "NORMAL", "CRASH", "RALLY"

    # For exits only
    entry_price: Optional[float] = None
    entry_date: Optional[str] = None
    holding_days: Optional[int] = None
    profit_loss: Optional[float] = None
    profit_loss_pct: Optional[float] = None

    # Analysis notes
    reasoning: str = ""
    notes: str = ""

    @property
    def trade_id(self) -> str:
        """Unique trade ID."""
        return f"{self.symbol}_{self.trade_date}_{self.direction}"


class TradeJournal:
    """Manage trade journal - log all trades with full context."""

    def __init__(self, journal_file: str = "data/trade_journal.json"):
        self.journal_file = Path(journal_file)
        self.journal_file.parent.mkdir(parents=True, exist_ok=True)

    def log_trade(self, trade: TradeLog):
        """Add a trade to the journal."""
        trades = self.load_trades()
        trades.append(asdict(trade))

        with open(self.journal_file, "w") as f:
            json.dump(trades, f, indent=2)

    def load_trades(self) -> list[dict]:
        """Load all trades from journal."""
        if not self.journal_file.exists():
            return []

        with open(self.journal_file, "r") as f:
            return json.load(f)

    def get_trades_for_symbol(self, symbol: str) -> list[dict]:
        """Get all trades for a specific symbol."""
        trades = self.load_trades()
        return [t for t in trades if t["symbol"] == symbol]

    def get_completed_trades(self) -> list[dict]:
        """Get all completed trades (pairs of BUY and SELL)."""
        trades = self.load_trades()
        completed = []

        # Group by symbol
        by_symbol = {}
        for trade in trades:
            symbol = trade["symbol"]
            if symbol not in by_symbol:
                by_symbol[symbol] = []
            by_symbol[symbol].append(trade)

        # Match buys with sells
        for symbol, symbol_trades in by_symbol.items():
            sells = [t for t in symbol_trades if t["direction"] == "SELL"]
            for sell in sells:
                # This sell has entry info embedded
                if sell.get("entry_price"):
                    completed.append(sell)

        return completed

    def analyze_performance(self) -> dict:
        """Analyze trade performance."""
        completed = self.get_completed_trades()

        if not completed:
            return {"total_trades": 0}

        # Calculate stats
        winning_trades = [t for t in completed if t.get("profit_loss", 0) > 0]
        losing_trades = [t for t in completed if t.get("profit_loss", 0) <= 0]

        total_profit = sum(t.get("profit_loss", 0) for t in winning_trades)
        total_loss = abs(sum(t.get("profit_loss", 0) for t in losing_trades))

        avg_win = total_profit / len(winning_trades) if winning_trades else 0
        avg_loss = total_loss / len(losing_trades) if losing_trades else 0

        avg_holding_days = sum(t.get("holding_days", 0) for t in completed) / len(completed)

        # Best and worst trades
        best_trade = max(completed, key=lambda t: t.get("profit_loss_pct", 0))
        worst_trade = min(completed, key=lambda t: t.get("profit_loss_pct", 0))

        return {
            "total_trades": len(completed),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": len(winning_trades) / len(completed) * 100,
            "total_profit": total_profit,
            "total_loss": total_loss,
            "net_profit": total_profit - total_loss,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": total_profit / total_loss if total_loss > 0 else float("inf"),
            "avg_holding_days": avg_holding_days,
            "best_trade": {
                "symbol": best_trade["symbol"],
                "profit_pct": best_trade.get("profit_loss_pct", 0),
                "entry_date": best_trade.get("entry_date"),
                "exit_date": best_trade["trade_date"],
            },
            "worst_trade": {
                "symbol": worst_trade["symbol"],
                "profit_pct": worst_trade.get("profit_loss_pct", 0),
                "entry_date": worst_trade.get("entry_date"),
                "exit_date": worst_trade["trade_date"],
            },
        }

    def get_trades_near_earnings(self) -> list[dict]:
        """Find trades made near earnings (to see if we should have avoided them)."""
        trades = self.load_trades()
        return [
            t for t in trades
            if t.get("days_until_earnings") is not None
            and t["days_until_earnings"] < 7
        ]

    def get_trades_with_volume_spike(self) -> list[dict]:
        """Find trades made during volume spikes."""
        trades = self.load_trades()
        return [
            t for t in trades
            if t.get("volume") and t.get("volume_avg")
            and t["volume"] > t["volume_avg"] * 3
        ]
