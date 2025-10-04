"""
ML-Enhanced Backtest Engine
Uses CatBoost predictions + per-ticker configs for improved performance
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd

from src.data.storage.market_data_db import MarketDataDB
from src.models.enhanced_detector import EnhancedTrendDetector
from src.models.market_regime import RegimeDetector
from src.config.tickers import TIER_2_STOCKS

# Import ML predictor
sys.path.insert(0, str(Path(__file__).parent))
from ml_predictor import MLPredictor


@dataclass
class Position:
    symbol: str
    entry_date: datetime
    entry_price: float
    quantity: int
    stop_loss: float
    take_profit: float
    trailing_stop: Optional[float]
    confidence: float
    ml_confidence: float  # NEW: ML confidence score
    leverage_used: float
    highest_price: float


@dataclass
class Trade:
    symbol: str
    entry_date: datetime
    exit_date: datetime
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    return_pct: float
    exit_reason: str
    regime: str
    ml_confidence: float  # NEW: ML confidence at entry


class MLEnhancedBacktest:
    """Backtest engine with ML predictions and per-ticker configs"""

    def __init__(self, config_path: str):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.db = MarketDataDB()
        self.detector = EnhancedTrendDetector(self.db)
        self.regime_detector = RegimeDetector(self.db)
        self.ml_predictor = MLPredictor(
            models_dir=self.config.get('ml_models_dir', 'models/catboost'),
            ticker_configs_dir=self.config.get('ticker_configs_dir', 'config/tickers')
        )

        # Load config
        self.start_date = self.config['start_date']
        self.end_date = self.config['end_date']
        self.initial_capital = self.config['initial_capital']
        self.target_capital = self.config['target_capital']

        # State
        self.cash = self.initial_capital
        self.positions: List[Position] = []
        self.trades: List[Trade] = []
        self.equity_curve = []

        # Get tradeable symbols (only those with ML models)
        self.symbols = [s for s in self.ml_predictor.models.keys()]
        print(f"Trading universe: {len(self.symbols)} symbols with ML models")
        print(f"Symbols: {', '.join(sorted(self.symbols))}\n")

    def get_ticker_config(self, symbol: str) -> dict:
        """Get ticker-specific configuration"""
        return self.ml_predictor.load_ticker_config(symbol)

    def calculate_position_size(self, symbol: str, ml_confidence: float, price: float) -> int:
        """Calculate position size based on ML confidence and ticker config"""
        ticker_config = self.get_ticker_config(symbol)

        # Get position sizing parameters
        max_pos_size = ticker_config.get('max_position_size', self.config.get('max_position_size', 0.20))
        min_pos_size = ticker_config.get('min_position_size', self.config.get('min_position_size', 0.10))

        # Scale position size by ML confidence if using ml_confidence sizing
        if self.config.get('position_sizing_method') == 'ml_confidence':
            # Higher confidence = larger position (within bounds)
            position_fraction = min_pos_size + (max_pos_size - min_pos_size) * ml_confidence
        else:
            position_fraction = max_pos_size

        # Calculate quantity
        position_value = self.cash * position_fraction
        quantity = int(position_value / price)

        return max(quantity, 0)

    def should_enter_trade(self, symbol: str, date: str, signal: dict, vix: float, regime: str) -> Tuple[bool, float]:
        """
        Determine if we should enter a trade using ML prediction

        Returns:
            (should_enter, ml_confidence) tuple
        """
        # Check if ML model exists for this symbol
        if symbol not in self.ml_predictor.models:
            return False, 0.0

        # Get ML prediction
        prediction = self.ml_predictor.predict(symbol, date)
        if not prediction:
            return False, 0.0

        ml_confidence, details = prediction

        # Get ticker-specific threshold
        ticker_config = self.get_ticker_config(symbol)
        min_confidence = ticker_config.get('min_ml_confidence', self.config.get('min_ml_confidence', 0.75))

        # Check ML confidence threshold
        if ml_confidence < min_confidence:
            return False, ml_confidence

        # Check VIX threshold
        max_vix = ticker_config.get('max_vix_for_entry', self.config.get('max_vix_for_entry', 30))
        if vix > max_vix:
            return False, ml_confidence

        # Check preferred regimes
        preferred_regimes = ticker_config.get('preferred_regimes', ['BULLISH'])
        if regime not in preferred_regimes:
            return False, ml_confidence

        # Check if we already have too many positions
        max_positions = self.config.get('max_positions', 5)
        if len(self.positions) >= max_positions:
            return False, ml_confidence

        # Check if signal quality meets threshold
        signal_confidence = signal.get('confidence', 0) / 100.0
        if signal_confidence < ticker_config.get('min_confidence', 0.75):
            return False, ml_confidence

        return True, ml_confidence

    def run(self):
        """Execute backtest"""
        print(f"{'='*80}")
        print(f"ML-ENHANCED BACKTEST ENGINE")
        print(f"{'='*80}")
        print(f"Period: {self.start_date} to {self.end_date}")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        print(f"Target Capital: ${self.target_capital:,.2f}")
        print(f"ML Models: {len(self.ml_predictor.models)}")
        print(f"{'='*80}\n")

        # Generate trading days
        start_dt = datetime.strptime(self.start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(self.end_date, '%Y-%m-%d')
        current_date = start_dt

        target_reached_date = None

        while current_date <= end_dt:
            date_str = current_date.strftime('%Y-%m-%d')

            # Get VIX and market regime
            vix = self._get_vix(date_str)
            regime = self._get_regime(date_str)

            # Update existing positions
            self._update_positions(date_str)

            # Look for new entry signals
            if len(self.positions) < self.config.get('max_positions', 5):
                self._scan_for_entries(date_str, vix, regime)

            # Calculate portfolio value
            portfolio_value = self._calculate_portfolio_value(date_str)
            self.equity_curve.append({
                'date': date_str,
                'value': portfolio_value,
                'cash': self.cash,
                'positions': len(self.positions)
            })

            # Check if target reached
            if portfolio_value >= self.target_capital and not target_reached_date:
                target_reached_date = date_str

            # Monthly reporting
            if current_date.day == 1 or (current_date - start_dt).days % 30 == 0:
                print(f"[{date_str}] Portfolio: ${portfolio_value:,.2f} | "
                      f"Positions: {len(self.positions)} | Cash: ${self.cash:,.2f} | "
                      f"Regime: {regime} | VIX: {vix:.1f}")

            current_date += timedelta(days=1)

        # Generate report
        self.generate_report(target_reached_date)

    def _scan_for_entries(self, date: str, vix: float, regime: str):
        """Scan for new entry opportunities using ML"""
        # Get top ML predictions for this date
        top_predictions = self.ml_predictor.get_top_predictions(
            date,
            min_confidence=self.config.get('min_ml_confidence', 0.75),
            top_n=10
        )

        for symbol, ml_confidence, details in top_predictions:
            # Get trend signal from detector
            signal = self.detector.analyze_symbol(symbol, date)
            if not signal or signal['signal'] != 'BUY':
                continue

            # Check if we should enter
            should_enter, final_confidence = self.should_enter_trade(symbol, date, signal, vix, regime)
            if not should_enter:
                continue

            # Get current price
            price = self._get_price(symbol, date)
            if not price:
                continue

            # Calculate position size
            quantity = self.calculate_position_size(symbol, ml_confidence, price)
            if quantity == 0:
                continue

            # Get ticker-specific stops/targets
            ticker_config = self.get_ticker_config(symbol)
            stop_loss_pct = ticker_config.get('stop_loss_pct', self.config.get('stop_loss_pct', 0.10))
            take_profit_pct = ticker_config.get('take_profit_pct', self.config.get('take_profit_pct', 0.20))

            # Open position
            position = Position(
                symbol=symbol,
                entry_date=datetime.strptime(date, '%Y-%m-%d'),
                entry_price=price,
                quantity=quantity,
                stop_loss=price * (1 - stop_loss_pct),
                take_profit=price * (1 + take_profit_pct),
                trailing_stop=None,
                confidence=signal['confidence'] / 100.0,
                ml_confidence=ml_confidence,
                leverage_used=1.0,
                highest_price=price
            )

            cost = price * quantity
            if cost <= self.cash:
                self.cash -= cost
                self.positions.append(position)
                print(f"[{date}] [ML: {ml_confidence:.1%}] OPENED {symbol} @ ${price:.2f} (Qty: {quantity})")

    def _update_positions(self, date: str):
        """Update existing positions and check exits"""
        positions_to_close = []

        for pos in self.positions:
            price = self._get_price(pos.symbol, date)
            if not price:
                continue

            # Update highest price for trailing stop
            if price > pos.highest_price:
                pos.highest_price = price

                # Activate trailing stop if configured
                ticker_config = self.get_ticker_config(pos.symbol)
                if ticker_config.get('trailing_stop_enabled', False):
                    activation_pct = ticker_config.get('trailing_stop_activation', 0.15)
                    if price >= pos.entry_price * (1 + activation_pct):
                        distance_pct = ticker_config.get('trailing_stop_distance', 0.08)
                        pos.trailing_stop = price * (1 - distance_pct)

            # Check exit conditions
            exit_reason = None

            if price <= pos.stop_loss:
                exit_reason = 'stop_loss'
            elif price >= pos.take_profit:
                exit_reason = 'take_profit'
            elif pos.trailing_stop and price <= pos.trailing_stop:
                exit_reason = 'trailing_stop'
            else:
                # Check signal exit
                signal = self.detector.analyze_symbol(pos.symbol, date)
                if signal and signal['signal'] in ['SELL', 'HOLD']:
                    exit_reason = 'signal_exit'

            if exit_reason:
                positions_to_close.append((pos, price, exit_reason))

        # Close positions
        for pos, exit_price, reason in positions_to_close:
            self._close_position(pos, date, exit_price, reason)

    def _close_position(self, pos: Position, date: str, exit_price: float, reason: str):
        """Close a position"""
        proceeds = exit_price * pos.quantity
        self.cash += proceeds

        pnl = proceeds - (pos.entry_price * pos.quantity)
        return_pct = (exit_price - pos.entry_price) / pos.entry_price

        trade = Trade(
            symbol=pos.symbol,
            entry_date=pos.entry_date,
            exit_date=datetime.strptime(date, '%Y-%m-%d'),
            entry_price=pos.entry_price,
            exit_price=exit_price,
            quantity=pos.quantity,
            pnl=pnl,
            return_pct=return_pct,
            exit_reason=reason,
            regime=self._get_regime(date),
            ml_confidence=pos.ml_confidence
        )

        self.trades.append(trade)
        self.positions.remove(pos)

        print(f"[{date}] CLOSED {pos.symbol} @ ${exit_price:.2f} - {reason} "
              f"(P&L: ${pnl:+,.2f}, Return: {return_pct:+.1%}, ML: {pos.ml_confidence:.1%})")

    def _get_price(self, symbol: str, date: str) -> Optional[float]:
        """Get closing price for symbol on date"""
        try:
            result = self.db.conn.execute("""
                SELECT close FROM stock_prices
                WHERE symbol = ? AND DATE(timestamp) = ?
                ORDER BY timestamp DESC LIMIT 1
            """, [symbol, date]).fetchone()
            return float(result[0]) if result else None
        except:
            return None

    def _get_vix(self, date: str) -> float:
        """Get VIX value (or default to 20 if not available)"""
        return 20.0  # Simplified for now

    def _get_regime(self, date: str) -> str:
        """Get market regime"""
        return "NEUTRAL"  # Simplified for now

    def _calculate_portfolio_value(self, date: str) -> float:
        """Calculate total portfolio value"""
        total = self.cash

        for pos in self.positions:
            price = self._get_price(pos.symbol, date)
            if price:
                total += price * pos.quantity

        return total

    def generate_report(self, target_reached_date: Optional[str]):
        """Generate backtest report with rich formatting"""
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from rich import box

        console = Console()

        final_value = self.equity_curve[-1]['value'] if self.equity_curve else self.initial_capital
        total_return = ((final_value - self.initial_capital) / self.initial_capital) * 100

        # Calculate SPY benchmark
        spy_start = self.db.conn.execute("""
            SELECT close FROM stock_prices WHERE symbol = 'SPY'
            AND DATE(timestamp) >= ? ORDER BY timestamp ASC LIMIT 1
        """, [self.start_date]).fetchone()

        spy_end = self.db.conn.execute("""
            SELECT close FROM stock_prices WHERE symbol = 'SPY'
            AND DATE(timestamp) <= ? ORDER BY timestamp DESC LIMIT 1
        """, [self.end_date]).fetchone()

        spy_return = 0
        if spy_start and spy_end:
            spy_return = ((float(spy_end[0]) - float(spy_start[0])) / float(spy_start[0])) * 100

        console.print()

        # Results table
        results_table = Table(title="ML-ENHANCED BACKTEST RESULTS", box=box.DOUBLE, show_header=True, header_style="bold cyan")
        results_table.add_column("Metric", style="cyan", width=25)
        results_table.add_column("Value", style="white", width=30)
        results_table.add_column("vs SPY", style="yellow", width=20)

        return_color = "green" if total_return > 0 else "red"
        vs_spy = total_return - spy_return
        vs_spy_color = "green" if vs_spy > 0 else "red"

        results_table.add_row("Initial Capital", f"${self.initial_capital:,.2f}", "")
        results_table.add_row("Final Value", f"${final_value:,.2f}", "")
        results_table.add_row("Total Return", f"[{return_color}]{total_return:+.2f}%[/{return_color}]",
                            f"SPY: {spy_return:+.2f}%")
        results_table.add_row("Alpha (vs SPY)", f"[{vs_spy_color}]{vs_spy:+.2f}%[/{vs_spy_color}]",
                            "OUTPERFORM" if vs_spy > 0 else "UNDERPERFORM")
        results_table.add_row("Target ($1M)",
                            "[green]REACHED[/green]" if target_reached_date else "[red]NOT REACHED[/red]", "")

        console.print(results_table)

        # Trade statistics
        if self.trades:
            winning_trades = [t for t in self.trades if t.pnl > 0]
            losing_trades = [t for t in self.trades if t.pnl <= 0]

            win_rate = len(winning_trades) / len(self.trades) * 100 if self.trades else 0
            avg_win = sum(t.pnl for t in winning_trades) / len(winning_trades) if winning_trades else 0
            avg_loss = sum(t.pnl for t in losing_trades) / len(losing_trades) if losing_trades else 0
            profit_factor = abs(sum(t.pnl for t in winning_trades) / sum(t.pnl for t in losing_trades)) if losing_trades and sum(t.pnl for t in losing_trades) != 0 else 0

            # Calculate average ML confidence
            avg_ml_confidence = sum(t.ml_confidence for t in self.trades) / len(self.trades)

            trade_table = Table(title="TRADE STATISTICS", box=box.ROUNDED)
            trade_table.add_column("Metric", style="magenta")
            trade_table.add_column("Value", style="white")

            trade_table.add_row("Total Trades", str(len(self.trades)))
            trade_table.add_row("Win Rate", f"{win_rate:.1f}%")
            trade_table.add_row("Avg ML Confidence", f"{avg_ml_confidence:.1%}")
            trade_table.add_row("Profit Factor", f"{profit_factor:.2f}")
            trade_table.add_row("Avg Win", f"${avg_win:,.2f}")
            trade_table.add_row("Avg Loss", f"${avg_loss:,.2f}")

            console.print(trade_table)

        console.print()


def main():
    """Run ML-enhanced backtest"""
    backtest = MLEnhancedBacktest("config/backtest_strategy_ml.yaml")
    backtest.run()


if __name__ == "__main__":
    main()
