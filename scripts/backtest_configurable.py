"""
Configurable Backtest Engine

Features:
- YAML-based strategy configuration
- Market regime adaptation (BULLISH/NEUTRAL/BEARISH)
- Momentum and breakout filters (leading indicators)
- Trailing stops
- VIX-based position sizing
- Easy customization for different market conditions
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
    leverage_used: float
    highest_price: float  # Track for trailing stop


@dataclass
class Trade:
    symbol: str
    entry_date: datetime
    exit_date: datetime
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    pnl_pct: float
    confidence: float
    leverage_used: float
    reason: str
    regime: str


class ConfigurableBacktest:
    """Market-adaptive backtest engine with configurable parameters."""

    def __init__(self, config_path: str = "config/backtest_strategy.yaml"):
        """Initialize backtest with config file."""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.db = MarketDataDB()

        # Parse dates
        self.start_date = datetime.strptime(self.config['start_date'], '%Y-%m-%d')
        self.end_date = datetime.strptime(self.config['end_date'], '%Y-%m-%d')

        # Portfolio settings
        self.initial_capital = self.config['initial_capital']
        self.target_capital = self.config['target_capital']
        self.max_positions = self.config['max_positions']
        self.commission = self.config['commission']
        self.slippage = self.config['slippage']

        # Portfolio state
        self.cash = self.initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.equity_curve = []

        # Detectors
        self.detector = None
        self.regime_detector = None

        # Current regime
        self.current_regime = "NEUTRAL"
        self.current_vix = 20.0

    def get_regime_params(self) -> dict:
        """Get parameters for current market regime."""
        # Ensure regime is a string
        regime_str = str(self.current_regime).split('.')[-1]  # Handle enum like MarketRegime.NEUTRAL
        regime_key = f"{regime_str.lower()}_regime"
        return self.config.get(regime_key, self.config['neutral_regime'])

    def get_momentum_score(self, symbol: str, current_date: datetime, current_price: float) -> float:
        """
        Calculate momentum score using leading indicators.

        Returns score 0-1 (1 = strongest momentum)
        """
        score = 0.0
        checks = 0

        # 1. Price vs 20-day MA
        ma_20_query = self.db.conn.execute("""
            SELECT AVG(close) as ma_20
            FROM stock_prices
            WHERE symbol = ?
            AND DATE(timestamp) BETWEEN DATE(?) - INTERVAL '20 days' AND DATE(?)
        """, [symbol, current_date, current_date]).fetchone()

        if ma_20_query and ma_20_query[0]:
            ma_20 = float(ma_20_query[0])
            price_strength = (current_price - ma_20) / ma_20

            if price_strength >= self.config.get('min_price_strength', 0.05):
                score += 1
            checks += 1

        # 2. Volume ratio (current vs 20-day average)
        vol_query = self.db.conn.execute("""
            SELECT
                (SELECT volume FROM stock_prices
                 WHERE symbol = ? AND DATE(timestamp) = DATE(?)
                 ORDER BY timestamp DESC LIMIT 1) as current_vol,
                AVG(volume) as avg_vol
            FROM stock_prices
            WHERE symbol = ?
            AND DATE(timestamp) BETWEEN DATE(?) - INTERVAL '20 days' AND DATE(?)
        """, [symbol, current_date, symbol, current_date, current_date]).fetchone()

        if vol_query and vol_query[0] and vol_query[1]:
            vol_ratio = float(vol_query[0]) / float(vol_query[1])
            min_vol_ratio = self.config.get('min_volume_ratio', 1.2)

            if vol_ratio >= min_vol_ratio:
                score += 1
            checks += 1

        # 3. Breakout filter (NEW - price at/near highs)
        if self.config.get('breakout_mode', True):
            breakout_period = self.config.get('breakout_period', 126)
            high_query = self.db.conn.execute("""
                SELECT MAX(high) as period_high
                FROM stock_prices
                WHERE symbol = ?
                AND DATE(timestamp) BETWEEN DATE(?) - INTERVAL ? DAY AND DATE(?)
            """, [symbol, current_date, breakout_period, current_date]).fetchone()

            if high_query and high_query[0]:
                period_high = float(high_query[0])
                # Within 2% of period high = breakout
                if current_price >= period_high * 0.98:
                    score += 1
                checks += 1

        return score / checks if checks > 0 else 0.0

    def get_vix(self, date: datetime) -> float:
        """Get VIX value for date."""
        result = self.db.conn.execute("""
            SELECT close FROM stock_prices
            WHERE symbol = 'VIX'
            AND DATE(timestamp) = DATE(?)
            ORDER BY timestamp DESC LIMIT 1
        """, [date]).fetchone()

        return float(result[0]) if result else 20.0

    def update_market_regime(self, current_date: datetime):
        """Update current market regime and VIX."""
        # Get VIX
        self.current_vix = self.get_vix(current_date)

        # Get regime from detector
        regime_info = self.regime_detector.detect_regime()
        if isinstance(regime_info, dict):
            self.current_regime = regime_info.get('regime', 'NEUTRAL')
        elif hasattr(regime_info, 'regime'):
            # Handle MarketRegime enum
            regime_val = regime_info.regime
            if hasattr(regime_val, 'value'):
                self.current_regime = regime_val.value
            elif hasattr(regime_val, 'name'):
                self.current_regime = regime_val.name
            else:
                self.current_regime = str(regime_val).split('.')[-1]
        else:
            self.current_regime = 'NEUTRAL'

    def get_position_size(self, confidence: float, current_price: float) -> int:
        """Calculate position size based on regime and confidence."""
        params = self.get_regime_params()
        portfolio_value = self.get_portfolio_value()

        # Base position size (Kelly Criterion)
        kelly_fraction = max(0.1, confidence - 0.5)
        max_position_pct = 0.15
        position_pct = min(kelly_fraction, max_position_pct)

        # Apply leverage based on confidence and regime
        if confidence >= 0.85:
            leverage = params['max_leverage']
        else:
            leverage = params['min_leverage']

        # Reduce leverage if VIX is high
        if self.current_vix > 30:
            leverage *= 0.5

        position_value = portfolio_value * position_pct * leverage
        shares = int(position_value / current_price)

        return shares

    def get_stop_loss(self, entry_price: float) -> float:
        """Get stop-loss price for regime."""
        params = self.get_regime_params()
        stop_pct = params['stop_loss_pct']
        return entry_price * (1 - stop_pct)

    def get_take_profit(self, entry_price: float) -> float:
        """Get take-profit price for regime."""
        params = self.get_regime_params()
        tp_pct = params['take_profit_pct']
        return entry_price * (1 + tp_pct)

    def update_trailing_stops(self, current_date: datetime):
        """Update trailing stops for all positions."""
        if not self.config.get('trailing_stop_enabled', True):
            return

        activation_pct = self.config.get('trailing_stop_activation', 0.10)
        trail_distance = self.config.get('trailing_stop_distance', 0.05)

        for symbol, pos in self.positions.items():
            current_price = self.get_current_price(symbol, current_date)
            if current_price <= 0:
                continue

            # Update highest price
            if current_price > pos.highest_price:
                pos.highest_price = current_price

            # Check if we should activate trailing stop
            profit_pct = (pos.highest_price - pos.entry_price) / pos.entry_price

            if profit_pct >= activation_pct:
                # Activate/update trailing stop
                new_trailing_stop = pos.highest_price * (1 - trail_distance)

                # Only move stop up, never down
                if pos.trailing_stop is None or new_trailing_stop > pos.trailing_stop:
                    pos.trailing_stop = new_trailing_stop

    def check_exits(self, current_date: datetime) -> List[Tuple[str, float, str]]:
        """Check stop-loss, take-profit, and trailing stops."""
        exits = []

        for symbol, pos in list(self.positions.items()):
            current_price = self.get_current_price(symbol, current_date)
            if current_price <= 0:
                continue

            # Check trailing stop first (highest priority)
            if pos.trailing_stop and current_price <= pos.trailing_stop:
                exits.append((symbol, current_price, 'trailing_stop'))
            # Check stop-loss
            elif current_price <= pos.stop_loss:
                exits.append((symbol, current_price, 'stop_loss'))
            # Check take-profit
            elif current_price >= pos.take_profit:
                exits.append((symbol, current_price, 'take_profit'))

        return exits

    def open_position(self, symbol: str, date: datetime, price: float, confidence: float) -> bool:
        """Open new position."""
        if symbol in self.positions:
            return False

        shares = self.get_position_size(confidence, price)
        if shares == 0:
            return False

        cost_basis = shares * price
        total_cost = cost_basis * (1 + self.commission + self.slippage)

        if total_cost > self.cash:
            return False

        # Calculate stops
        stop_loss = self.get_stop_loss(price)
        take_profit = self.get_take_profit(price)

        # Get leverage used
        params = self.get_regime_params()
        leverage = params['max_leverage'] if confidence >= 0.85 else params['min_leverage']

        # Create position
        self.positions[symbol] = Position(
            symbol=symbol,
            entry_date=date,
            entry_price=price,
            quantity=shares,
            stop_loss=stop_loss,
            take_profit=take_profit,
            trailing_stop=None,
            confidence=confidence,
            leverage_used=leverage,
            highest_price=price,
        )

        self.cash -= total_cost
        return True

    def close_position(self, symbol: str, date: datetime, price: float, reason: str):
        """Close position and record trade."""
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]
        proceeds = pos.quantity * price
        net_proceeds = proceeds * (1 - self.commission - self.slippage)

        pnl = net_proceeds - (pos.quantity * pos.entry_price * (1 + self.commission + self.slippage))
        pnl_pct = pnl / (pos.quantity * pos.entry_price)

        # Record trade
        self.trades.append(Trade(
            symbol=symbol,
            entry_date=pos.entry_date,
            exit_date=date,
            entry_price=pos.entry_price,
            exit_price=price,
            quantity=pos.quantity,
            pnl=pnl,
            pnl_pct=pnl_pct,
            confidence=pos.confidence,
            leverage_used=pos.leverage_used,
            reason=reason,
            regime=self.current_regime,
        ))

        self.cash += net_proceeds
        del self.positions[symbol]

    def get_current_price(self, symbol: str, date: Optional[datetime] = None) -> float:
        """Get price without future data leakage."""
        if date is None:
            date = datetime.now()

        result = self.db.conn.execute("""
            SELECT close FROM stock_prices
            WHERE symbol = ?
            AND DATE(timestamp) = DATE(?)
            ORDER BY timestamp DESC LIMIT 1
        """, [symbol, date]).fetchone()

        return float(result[0]) if result else 0.0

    def get_portfolio_value(self) -> float:
        """Calculate total portfolio value."""
        positions_value = sum(
            pos.quantity * self.get_current_price(pos.symbol)
            for pos in self.positions.values()
        )
        return self.cash + positions_value

    def should_trade_in_regime(self, confidence: float) -> bool:
        """Check if we should trade given current regime and confidence."""
        params = self.get_regime_params()

        # Check confidence threshold for regime
        if confidence < params['min_confidence']:
            return False

        # Check VIX filter
        if self.config.get('block_high_vix_trades', True):
            max_vix = self.config.get('max_vix_for_entry', 35)
            if self.current_vix > max_vix:
                return False

        return True

    def run(self):
        """Run the backtest."""
        print("=" * 80)
        print("CONFIGURABLE BACKTEST ENGINE")
        print("=" * 80)
        print(f"Config: {Path(sys.argv[1] if len(sys.argv) > 1 else 'config/backtest_strategy.yaml').name}")
        print(f"Start Date: {self.start_date.date()}")
        print(f"End Date: {self.end_date.date()}")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        print(f"Target Capital: ${self.target_capital:,.2f}")
        print(f"Max Positions: {self.max_positions}")
        print(f"Momentum Filter: {'ON' if self.config.get('use_momentum_filter') else 'OFF'}")
        print(f"Regime Adaptation: {'ON' if self.config.get('adapt_to_regime') else 'OFF'}")
        print("=" * 80)
        print()

        current_date = self.start_date
        days_processed = 0
        target_reached_date = None

        tickers = [t.symbol if hasattr(t, 'symbol') else t for t in TIER_2_STOCKS[:30]]

        while current_date <= self.end_date:
            # Initialize detectors
            self.detector = EnhancedTrendDetector(
                db=self.db,
                min_confidence=self.config['min_confidence'],
                confirmation_days=self.config['confirmation_days'],
                long_only=True,
                log_trades=False,
            )
            self.regime_detector = RegimeDetector(self.db)

            # Update market regime
            self.update_market_regime(current_date)

            # Update trailing stops
            self.update_trailing_stops(current_date)

            # Check exits
            exits = self.check_exits(current_date)
            for symbol, price, reason in exits:
                self.close_position(symbol, current_date, price, reason)
                print(f"[{current_date.date()}] CLOSED {symbol} @ ${price:.2f} - {reason}")

            # Scan for new signals
            signals = []
            for ticker in tickers:
                if ticker in self.positions:
                    # Check if signal changed to exit
                    price = self.get_current_price(ticker, current_date)
                    if price > 0:
                        signal = self.detector.generate_signal(ticker, current_date, price)
                        if signal and signal.signal.value in ['SELL', 'DONT_TRADE']:
                            self.close_position(ticker, current_date, price, 'signal_exit')
                            print(f"[{current_date.date()}] CLOSED {ticker} @ ${price:.2f} - signal exit")
                    continue

                price = self.get_current_price(ticker, current_date)
                if price <= 0:
                    continue

                signal = self.detector.generate_signal(ticker, current_date, price)
                if not signal or signal.signal.value != 'BUY':
                    continue

                # Check regime-based confidence threshold
                if not self.should_trade_in_regime(signal.confidence):
                    continue

                # Apply momentum filter
                if self.config.get('use_momentum_filter', True):
                    momentum_score = self.get_momentum_score(ticker, current_date, price)
                    if momentum_score < 0.5:  # Need at least 50% momentum score
                        continue

                signals.append((ticker, price, signal.confidence))

            # Sort by confidence
            signals.sort(key=lambda x: x[2], reverse=True)

            # Open positions
            for ticker, price, confidence in signals[:self.max_positions]:
                if len(self.positions) >= self.max_positions:
                    break

                opened = self.open_position(ticker, current_date, price, confidence)
                if opened:
                    regime_tag = f"[{self.current_regime}]"
                    print(f"[{current_date.date()}] {regime_tag} OPENED {ticker} @ ${price:.2f} (Conf: {confidence:.0%})")

            # Track equity
            portfolio_value = self.get_portfolio_value()
            self.equity_curve.append((current_date, portfolio_value))

            # Check target
            if portfolio_value >= self.target_capital and target_reached_date is None:
                target_reached_date = current_date
                print()
                print("=" * 80)
                print(f"TARGET REACHED: ${portfolio_value:,.2f} on {current_date.date()}")
                print("=" * 80)
                print()

            # Monthly summary
            if self.config.get('print_monthly_summary', True) and days_processed % 30 == 0:
                regime_display = str(self.current_regime).split('.')[-1]
                print(f"[{current_date.date()}] Portfolio: ${portfolio_value:,.2f} | Positions: {len(self.positions)} | Cash: ${self.cash:,.2f} | Regime: {regime_display} | VIX: {self.current_vix:.1f}")

            current_date += timedelta(days=1)
            days_processed += 1

        return self.generate_report(target_reached_date)

    def generate_report(self, target_reached_date: Optional[datetime]) -> Dict:
        """Generate performance report."""
        final_value = self.get_portfolio_value()
        total_return = ((final_value - self.initial_capital) / self.initial_capital) * 100

        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl < 0]

        win_rate = (len(winning_trades) / len(self.trades) * 100) if self.trades else 0
        avg_win = sum(t.pnl for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t.pnl for t in losing_trades) / len(losing_trades) if losing_trades else 0

        total_wins = sum(t.pnl for t in winning_trades)
        total_losses = abs(sum(t.pnl for t in losing_trades))
        profit_factor = total_wins / total_losses if total_losses > 0 else 0

        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from rich.text import Text
        from rich import box

        console = Console()

        # Calculate SPY benchmark (find closest dates)
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
            print(f"\n[DEBUG] SPY: ${spy_start[0]:.2f} -> ${spy_end[0]:.2f} = {spy_return:+.2f}%")
        else:
            print(f"\n[DEBUG] SPY data not found for {self.start_date} to {self.end_date}")

        console.print()

        # Main results table
        results_table = Table(title="BACKTEST RESULTS", box=box.DOUBLE, show_header=True, header_style="bold cyan")
        results_table.add_column("Metric", style="cyan", width=25)
        results_table.add_column("Value", style="white", width=30)
        results_table.add_column("vs SPY", style="yellow", width=20)

        # Color code the return
        return_color = "green" if total_return > 0 else "red"
        spy_color = "green" if spy_return > 0 else "red"
        vs_spy = total_return - spy_return
        vs_spy_color = "green" if vs_spy > 0 else "red"

        results_table.add_row("Initial Capital", f"${self.initial_capital:,.2f}", "")
        results_table.add_row("Final Value", f"${final_value:,.2f}", "")
        results_table.add_row("Total Return", f"[{return_color}]{total_return:+.2f}%[/{return_color}]",
                             f"[{spy_color}]SPY: {spy_return:+.2f}%[/{spy_color}]")
        results_table.add_row("Alpha (vs SPY)", f"[{vs_spy_color}]{vs_spy:+.2f}%[/{vs_spy_color}]",
                             "UNDERPERFORM" if vs_spy < 0 else "OUTPERFORM")

        target_status = "[green]REACHED[/green]" if target_reached_date else "[red]NOT REACHED[/red]"
        results_table.add_row("Target ($1M)", target_status, "")

        console.print(results_table)

        # Trade stats table
        trade_table = Table(title="TRADE STATISTICS", box=box.ROUNDED, show_header=True, header_style="bold magenta")
        trade_table.add_column("Metric", style="magenta")
        trade_table.add_column("Value", style="white")
        trade_table.add_column("Quality", style="yellow")

        pf_quality = "Excellent" if profit_factor > 2 else "Good" if profit_factor > 1.5 else "Weak" if profit_factor > 1 else "LOSING"
        pf_color = "green" if profit_factor > 1.5 else "yellow" if profit_factor > 1 else "red"

        wr_quality = "Excellent" if win_rate > 60 else "Good" if win_rate > 50 else "Weak" if win_rate > 45 else "BAD"
        wr_color = "green" if win_rate > 50 else "yellow" if win_rate > 45 else "red"

        trade_table.add_row("Total Trades", str(len(self.trades)), f"{len(self.trades)//365} trades/year")
        trade_table.add_row("Win Rate", f"[{wr_color}]{win_rate:.1f}%[/{wr_color}]", wr_quality)
        trade_table.add_row("Winning Trades", f"[green]{len(winning_trades)}[/green]", f"${avg_win:,.2f} avg")
        trade_table.add_row("Losing Trades", f"[red]{len(losing_trades)}[/red]", f"${avg_loss:,.2f} avg")
        trade_table.add_row("Profit Factor", f"[{pf_color}]{profit_factor:.2f}[/{pf_color}]", pf_quality)

        console.print(trade_table)

        # Regime breakdown
        regime_table = Table(title="PERFORMANCE BY REGIME", box=box.SIMPLE, show_header=True, header_style="bold blue")
        regime_table.add_column("Regime", style="blue", width=12)
        regime_table.add_column("Trades", justify="right", width=10)
        regime_table.add_column("Win Rate", justify="right", width=12)
        regime_table.add_column("P&L", justify="right", width=15)
        regime_table.add_column("Assessment", style="yellow", width=20)

        for regime in ['BULLISH', 'NEUTRAL', 'BEARISH']:
            regime_trades = [t for t in self.trades if t.regime == regime]
            if regime_trades:
                regime_pnl = sum(t.pnl for t in regime_trades)
                regime_wins = len([t for t in regime_trades if t.pnl > 0])
                regime_wr = regime_wins / len(regime_trades) * 100

                pnl_color = "green" if regime_pnl > 0 else "red"
                wr_color = "green" if regime_wr > 50 else "yellow" if regime_wr > 45 else "red"
                assessment = "Working" if regime_pnl > 0 and regime_wr > 50 else "Weak" if regime_pnl > 0 or regime_wr > 45 else "BROKEN"

                regime_table.add_row(
                    regime,
                    str(len(regime_trades)),
                    f"[{wr_color}]{regime_wr:.1f}%[/{wr_color}]",
                    f"[{pnl_color}]${regime_pnl:+,.2f}[/{pnl_color}]",
                    assessment
                )

        console.print(regime_table)

        # Diagnostic message
        if total_return < spy_return:
            console.print()
            console.print(Panel.fit(
                f"[bold red]WARNING: STRATEGY UNDERPERFORMING SPY BY {abs(vs_spy):.1f}%[/bold red]\n\n"
                f"[yellow]Root Causes:[/yellow]\n"
                f"  • Win Rate: [red]{win_rate:.1f}%[/red] (need >50%)\n"
                f"  • Profit Factor: [red]{profit_factor:.2f}[/red] (need >1.5)\n"
                f"  • Over-trading: {len(self.trades)} trades = high costs\n\n"
                f"[cyan]Solutions:[/cyan]\n"
                f"  1. [bold]Just buy & hold SPY[/bold] - beats this strategy\n"
                f"  2. Enable CatBoost ML - improve signal quality\n"
                f"  3. Only trade BULLISH regime - avoid chop\n"
                f"  4. Increase min_confidence to 0.85+ - fewer, better trades",
                title="DIAGNOSTIC",
                border_style="red"
            ))

        console.print()

        return {
            'final_value': final_value,
            'total_return': total_return,
            'target_reached': target_reached_date is not None,
            'total_trades': len(self.trades),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
        }


if __name__ == "__main__":
    config_file = sys.argv[1] if len(sys.argv) > 1 else "config/backtest_strategy.yaml"

    try:
        backtest = ConfigurableBacktest(config_file)
        backtest.run()
    except KeyboardInterrupt:
        print("\n\nBacktest stopped by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
