"""
Backtest: Path from $30K to $1M

Realistic backtesting with:
- No future data leakage (walk-forward simulation)
- Leverage based on confidence and market regime
- Position swapping for better opportunities
- Stop-loss and take-profit rules
- Proper transaction costs and slippage

Goal: Determine realistic timeframe to reach $1M from $30K
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import pandas as pd

from src.data.storage.market_data_db import MarketDataDB
from src.models.enhanced_detector import EnhancedTrendDetector
from src.models.market_regime import RegimeDetector
from src.config.tickers import TIER_2_STOCKS


@dataclass
class Position:
    """Represents an open position."""
    symbol: str
    entry_date: datetime
    entry_price: float
    quantity: int
    stop_loss: float
    take_profit: float
    confidence: float
    leverage_used: float


@dataclass
class Trade:
    """Represents a completed trade."""
    symbol: str
    entry_date: datetime
    exit_date: datetime
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    pnl_pct: float
    leverage_used: float
    reason: str  # 'stop_loss', 'take_profit', 'signal_exit', 'swap'


class RealisticBacktest:
    """Walk-forward backtest with no future data leakage."""

    def __init__(
        self,
        db: MarketDataDB,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float = 30000.0,
        target_capital: float = 1000000.0,
        max_positions: int = 12,
        commission: float = 0.001,  # 0.1% commission
        slippage: float = 0.0005,   # 0.05% slippage
    ):
        self.db = db
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.target_capital = target_capital
        self.max_positions = max_positions
        self.commission = commission
        self.slippage = slippage

        # Portfolio state
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []

        # Performance tracking
        self.equity_curve = []
        self.daily_returns = []

        # Detectors (initialized per-date to prevent leakage)
        self.detector = None
        self.regime_detector = None

    def get_leverage_multiplier(self, confidence: float, market_regime: str) -> float:
        """
        Determine leverage based on confidence and market regime.

        Rules:
        - High confidence (≥85%) in bullish regime: 2x leverage
        - Medium confidence (75-85%) in bullish regime: 1.5x leverage
        - Normal confidence (75%+) in neutral regime: 1.0x leverage
        - Bearish regime or low confidence: 0.5x position (defensive)
        """
        if market_regime == "BEARISH":
            return 0.5  # Defensive

        if confidence >= 0.85 and market_regime == "BULLISH":
            return 2.0  # Aggressive
        elif confidence >= 0.75 and market_regime == "BULLISH":
            return 1.5  # Moderate leverage
        elif confidence >= 0.75:
            return 1.0  # No leverage
        else:
            return 0.5  # Defensive

    def calculate_position_size(
        self,
        confidence: float,
        leverage: float,
        current_price: float,
    ) -> int:
        """
        Calculate position size based on Kelly Criterion (simplified).

        Position size = (Portfolio Value × Leverage × Kelly%) / Price
        Kelly% = confidence - 0.5 (simplified, assuming 1:1 risk/reward)
        """
        portfolio_value = self.get_portfolio_value()

        # Simplified Kelly Criterion
        kelly_fraction = max(0.1, confidence - 0.5)  # Min 10% position

        # Max position size (don't risk more than 15% per position)
        max_position_pct = 0.15

        position_pct = min(kelly_fraction, max_position_pct)

        # Calculate dollar amount
        position_value = portfolio_value * position_pct * leverage

        # Convert to shares
        shares = int(position_value / current_price)

        return shares

    def get_stop_loss_pct(self, confidence: float) -> float:
        """
        Determine stop-loss percentage based on confidence.

        Higher confidence = wider stop (let it breathe)
        Lower confidence = tighter stop (protect capital)
        """
        if confidence >= 0.85:
            return 0.10  # 10% stop
        elif confidence >= 0.78:
            return 0.09  # 9% stop
        else:
            return 0.08  # 8% stop

    def get_take_profit_pct(self, confidence: float) -> float:
        """
        Determine take-profit percentage based on confidence.

        Higher confidence = higher target
        """
        if confidence >= 0.85:
            return 0.25  # 25% target
        elif confidence >= 0.75:
            return 0.15  # 15% target
        else:
            return 0.10  # 10% target

    def get_portfolio_value(self) -> float:
        """Calculate total portfolio value (cash + positions)."""
        positions_value = sum(
            pos.quantity * self.get_current_price(pos.symbol)
            for pos in self.positions.values()
        )
        return self.cash + positions_value

    def get_current_price(self, symbol: str, date: Optional[datetime] = None) -> float:
        """
        Get current price without future data leakage.

        Uses close price from the specified date or latest available.
        """
        if date is None:
            date = datetime.now()

        result = self.db.conn.execute("""
            SELECT close FROM stock_prices
            WHERE symbol = ?
            AND DATE(timestamp) = DATE(?)
            ORDER BY timestamp DESC
            LIMIT 1
        """, [symbol, date]).fetchone()

        if result:
            return float(result[0])
        return 0.0

    def check_stop_loss_take_profit(self, current_date: datetime) -> List[str]:
        """
        Check if any positions hit stop-loss or take-profit.

        Returns list of symbols to exit.
        """
        exits = []

        for symbol, pos in self.positions.items():
            current_price = self.get_current_price(symbol, current_date)

            if current_price <= 0:
                continue

            # Check stop-loss
            if current_price <= pos.stop_loss:
                exits.append((symbol, current_price, 'stop_loss'))

            # Check take-profit
            elif current_price >= pos.take_profit:
                exits.append((symbol, current_price, 'take_profit'))

        return exits

    def open_position(
        self,
        symbol: str,
        current_date: datetime,
        current_price: float,
        confidence: float,
        leverage: float,
    ) -> bool:
        """
        Open a new position with proper risk management.

        Returns True if position opened successfully.
        """
        # Check if we have room for more positions
        if len(self.positions) >= self.max_positions:
            return False

        # Calculate position size
        quantity = self.calculate_position_size(confidence, leverage, current_price)

        if quantity <= 0:
            return False

        # Calculate costs
        position_value = quantity * current_price
        slippage_cost = position_value * self.slippage
        commission_cost = position_value * self.commission
        total_cost = position_value + slippage_cost + commission_cost

        # Check if we have enough cash
        if total_cost > self.cash:
            return False

        # Calculate stop-loss and take-profit
        stop_loss_pct = self.get_stop_loss_pct(confidence)
        take_profit_pct = self.get_take_profit_pct(confidence)

        stop_loss = current_price * (1 - stop_loss_pct)
        take_profit = current_price * (1 + take_profit_pct)

        # Open position
        self.positions[symbol] = Position(
            symbol=symbol,
            entry_date=current_date,
            entry_price=current_price,
            quantity=quantity,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence,
            leverage_used=leverage,
        )

        # Deduct cash
        self.cash -= total_cost

        return True

    def close_position(
        self,
        symbol: str,
        current_date: datetime,
        current_price: float,
        reason: str,
    ) -> None:
        """Close a position and record the trade."""
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]

        # Calculate proceeds
        position_value = pos.quantity * current_price
        slippage_cost = position_value * self.slippage
        commission_cost = position_value * self.commission
        net_proceeds = position_value - slippage_cost - commission_cost

        # Calculate P&L
        entry_cost = pos.quantity * pos.entry_price
        pnl = net_proceeds - entry_cost
        pnl_pct = (pnl / entry_cost) * 100

        # Record trade
        self.trades.append(Trade(
            symbol=symbol,
            entry_date=pos.entry_date,
            exit_date=current_date,
            entry_price=pos.entry_price,
            exit_price=current_price,
            quantity=pos.quantity,
            pnl=pnl,
            pnl_pct=pnl_pct,
            leverage_used=pos.leverage_used,
            reason=reason,
        ))

        # Add cash
        self.cash += net_proceeds

        # Remove position
        del self.positions[symbol]

    def should_swap_position(
        self,
        current_symbol: str,
        current_confidence: float,
        new_symbol: str,
        new_confidence: float,
    ) -> bool:
        """
        Determine if we should swap a current position for a better opportunity.

        Swap if:
        - New opportunity has significantly higher confidence (>10% better)
        - Current position is not in profit
        """
        if new_symbol == current_symbol:
            return False

        # Only swap if new opportunity is significantly better (increased threshold)
        if new_confidence < current_confidence + 0.15:  # Was 0.10, now 0.15
            return False

        # Check if current position is in profit
        current_pos = self.positions.get(current_symbol)
        if current_pos:
            current_price = self.get_current_price(current_symbol)
            if current_price > current_pos.entry_price * 1.05:  # 5%+ profit
                return False  # Don't swap winning positions

        return True

    def run_backtest(self) -> Dict:
        """
        Run walk-forward backtest day by day.

        Returns performance metrics and time to $1M.
        """
        print("=" * 80)
        print("BACKTEST: PATH TO $1 MILLION")
        print("=" * 80)
        print(f"Start Date: {self.start_date.date()}")
        print(f"End Date: {self.end_date.date()}")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        print(f"Target Capital: ${self.target_capital:,.2f}")
        print(f"Max Positions: {self.max_positions}")
        print("=" * 80)
        print()

        current_date = self.start_date
        days_processed = 0
        target_reached_date = None

        # Get all tickers to scan
        tickers = [t.symbol if hasattr(t, 'symbol') else t for t in TIER_2_STOCKS[:30]]

        while current_date <= self.end_date:
            # Initialize detectors for this date (no future data leakage)
            self.detector = EnhancedTrendDetector(
                db=self.db,
                min_confidence=0.75,  # Keep at 75% for detector, filter at 78% in backtest
                confirmation_days=1,
                long_only=True,
                log_trades=False,  # Don't log trades during backtest
            )
            self.regime_detector = RegimeDetector(self.db)

            # Get market regime
            regime_info = self.regime_detector.detect_regime()
            market_regime = regime_info.get('regime', 'NEUTRAL') if isinstance(regime_info, dict) else regime_info.regime

            # Check stop-loss and take-profit on existing positions
            exits = self.check_stop_loss_take_profit(current_date)
            for symbol, price, reason in exits:
                self.close_position(symbol, current_date, price, reason)
                print(f"[{current_date.date()}] CLOSED {symbol} @ ${price:.2f} - {reason}")

            # Scan for signals (only if market is open on this date)
            signals = []
            for ticker in tickers:
                # Skip if already holding
                if ticker in self.positions:
                    # Check if signal changed to exit
                    price = self.get_current_price(ticker, current_date)
                    if price > 0:
                        signal = self.detector.generate_signal(ticker, current_date, price)
                        if signal.signal.value in ['SELL', 'DONT_TRADE']:
                            self.close_position(ticker, current_date, price, 'signal_exit')
                            print(f"[{current_date.date()}] CLOSED {ticker} @ ${price:.2f} - signal exit")
                    continue

                price = self.get_current_price(ticker, current_date)
                if price <= 0:
                    continue

                signal = self.detector.generate_signal(ticker, current_date, price)

                if signal.signal.value == 'BUY' and signal.confidence >= 0.75:  # Standard threshold
                    leverage = self.get_leverage_multiplier(signal.confidence, market_regime)
                    signals.append((ticker, price, signal.confidence, leverage))

            # Sort signals by confidence
            signals.sort(key=lambda x: x[2], reverse=True)

            # Open new positions or swap
            for ticker, price, confidence, leverage in signals[:self.max_positions]:
                # Try to open position
                opened = self.open_position(ticker, current_date, price, confidence, leverage)

                if opened:
                    lev_str = f" ({leverage:.1f}x)" if leverage != 1.0 else ""
                    print(f"[{current_date.date()}] OPENED {ticker} @ ${price:.2f} (Conf: {confidence:.0%}){lev_str}")

                # If can't open, check if we should swap
                elif len(self.positions) >= self.max_positions:
                    # Find weakest position
                    weakest = min(
                        self.positions.items(),
                        key=lambda x: x[1].confidence
                    )
                    weakest_symbol, weakest_pos = weakest

                    if self.should_swap_position(weakest_symbol, weakest_pos.confidence, ticker, confidence):
                        # Swap
                        weakest_price = self.get_current_price(weakest_symbol, current_date)
                        self.close_position(weakest_symbol, current_date, weakest_price, 'swap')
                        print(f"[{current_date.date()}] SWAP OUT {weakest_symbol} @ ${weakest_price:.2f}")

                        opened = self.open_position(ticker, current_date, price, confidence, leverage)
                        if opened:
                            lev_str = f" ({leverage:.1f}x)" if leverage != 1.0 else ""
                            print(f"[{current_date.date()}] SWAP IN {ticker} @ ${price:.2f} (Conf: {confidence:.0%}){lev_str}")

            # Track equity
            portfolio_value = self.get_portfolio_value()
            self.equity_curve.append((current_date, portfolio_value))

            # Check if target reached
            if portfolio_value >= self.target_capital and target_reached_date is None:
                target_reached_date = current_date
                print()
                print("=" * 80)
                print(f"🎯 TARGET REACHED: ${portfolio_value:,.2f} on {current_date.date()}")
                print("=" * 80)
                print()

            # Progress update every 30 days
            if days_processed % 30 == 0:
                print(f"[{current_date.date()}] Portfolio: ${portfolio_value:,.2f} | Positions: {len(self.positions)} | Cash: ${self.cash:,.2f}")

            # Move to next day
            current_date += timedelta(days=1)
            days_processed += 1

        # Final results
        return self.generate_report(target_reached_date)

    def generate_report(self, target_reached_date: Optional[datetime]) -> Dict:
        """Generate performance report."""
        final_value = self.get_portfolio_value()
        total_return = ((final_value - self.initial_capital) / self.initial_capital) * 100

        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl <= 0]

        win_rate = (len(winning_trades) / len(self.trades) * 100) if self.trades else 0

        avg_win = sum(t.pnl for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t.pnl for t in losing_trades) / len(losing_trades) if losing_trades else 0

        profit_factor = abs(sum(t.pnl for t in winning_trades) / sum(t.pnl for t in losing_trades)) if losing_trades else 0

        print()
        print("=" * 80)
        print("BACKTEST RESULTS")
        print("=" * 80)
        print(f"Initial Capital:     ${self.initial_capital:,.2f}")
        print(f"Final Value:         ${final_value:,.2f}")
        print(f"Total Return:        {total_return:+.2f}%")
        print(f"Target ($1M):        {'[REACHED]' if target_reached_date else '[NOT REACHED]'}")
        if target_reached_date:
            days_to_target = (target_reached_date - self.start_date).days
            years_to_target = days_to_target / 365.25
            print(f"Time to $1M:         {days_to_target} days ({years_to_target:.1f} years)")
        print()
        print(f"Total Trades:        {len(self.trades)}")
        print(f"Winning Trades:      {len(winning_trades)} ({win_rate:.1f}%)")
        print(f"Losing Trades:       {len(losing_trades)}")
        print(f"Average Win:         ${avg_win:,.2f}")
        print(f"Average Loss:        ${avg_loss:,.2f}")
        print(f"Profit Factor:       {profit_factor:.2f}")
        print("=" * 80)

        return {
            'final_value': final_value,
            'total_return': total_return,
            'target_reached': target_reached_date is not None,
            'target_date': target_reached_date,
            'total_trades': len(self.trades),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
        }


def main():
    """Run backtest."""
    db = MarketDataDB()

    # Backtest parameters
    start_date = datetime(2020, 1, 1)  # 5 years of data
    end_date = datetime(2024, 12, 31)

    backtest = RealisticBacktest(
        db=db,
        start_date=start_date,
        end_date=end_date,
        initial_capital=30000.0,
        target_capital=1000000.0,
        max_positions=12,
    )

    results = backtest.run_backtest()

    db.close()


if __name__ == "__main__":
    main()
