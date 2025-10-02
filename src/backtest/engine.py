"""
Backtesting engine for trading strategies.

Simulates trading over historical data with:
- Position management
- P&L tracking
- Performance metrics (win rate, Sharpe ratio, drawdown)
- Trade history
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal

import pandas as pd

from src.data.storage.market_data_db import MarketDataDB
from src.ml.catboost_model import CatBoostTrainer
from src.models.trading_strategy import (
    EntryReason,
    ExitReason,
    Position,
    Trade,
    TradingStrategy,
)


@dataclass
class BacktestConfig:
    """Configuration for backtesting."""

    starting_capital: Decimal = Decimal("100000")  # $100k starting capital
    position_size_pct: float = 0.1  # 10% of capital per position
    max_positions: int = 5  # Max concurrent positions
    commission_pct: float = 0.001  # 0.1% commission per trade

    # Strategy parameters
    stop_loss_pct: float = 0.08  # 8% stop loss
    take_profit_pct: float = 0.15  # 15% take profit
    max_holding_days: int = 60  # 60 days max hold
    min_ml_confidence: float = 0.6  # Minimum ML confidence to trade


@dataclass
class BacktestResults:
    """Results from backtesting."""

    start_date: datetime
    end_date: datetime
    starting_capital: Decimal
    ending_capital: Decimal
    total_return: float
    total_return_pct: float

    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float

    avg_profit: Decimal
    avg_loss: Decimal
    profit_factor: float  # Gross profit / Gross loss

    max_drawdown: float
    max_drawdown_date: datetime | None

    sharpe_ratio: float
    sortino_ratio: float

    avg_holding_days: float
    total_commission: Decimal

    trades: list[Trade]


class BacktestEngine:
    """
    Backtesting engine for trading strategies.

    Simulates trading over historical data with realistic constraints:
    - Limited capital
    - Position sizing
    - Commission costs
    - Slippage (optional)
    """

    def __init__(
        self,
        db: MarketDataDB,
        config: BacktestConfig,
        strategy: TradingStrategy | None = None,
        ml_trainer: CatBoostTrainer | None = None,
    ):
        """
        Initialize backtest engine.

        Args:
            db: Database connection
            config: Backtest configuration
            strategy: Trading strategy (optional, will create if None)
            ml_trainer: ML trainer with loaded models (optional)
        """
        self.db = db
        self.config = config
        self.ml_trainer = ml_trainer

        if strategy is None:
            self.strategy = TradingStrategy(
                db=db,
                stop_loss_pct=config.stop_loss_pct,
                take_profit_pct=config.take_profit_pct,
                max_holding_days=config.max_holding_days,
            )
        else:
            self.strategy = strategy

        # State
        self.cash = config.starting_capital
        self.positions: dict[str, Position] = {}
        self.trades: list[Trade] = []
        self.equity_curve: list[tuple[datetime, Decimal]] = []
        self.commission_paid = Decimal("0")

    def get_ml_prediction(self, ticker: str, date: datetime) -> tuple[int, float, float] | None:
        """
        Get ML model prediction for ticker on date.

        Args:
            ticker: Stock ticker
            date: Date

        Returns:
            Tuple of (direction, confidence, expected_return) or None
        """
        if self.ml_trainer is None or self.ml_trainer.direction_model is None:
            return None

        # Prepare features for this date
        df = self.ml_trainer.prepare_features(
            ticker, date - timedelta(days=100), date  # Need history for features
        )

        if df.empty:
            return None

        # Get latest row
        latest = df.iloc[-1:]

        # Get feature columns
        exclude_cols = [
            "symbol",
            "date",
            "open",
            "high",
            "low",
            "close",
            "future_close",
            "target_return",
            "target_direction",
            "flow_signal",
        ]
        feature_cols = [col for col in df.columns if col not in exclude_cols]
        X = latest[feature_cols].fillna(0)

        try:
            return self.ml_trainer.predict(X)
        except Exception as e:
            print(f"Warning: ML prediction failed for {ticker} on {date}: {e}")
            return None

    def get_current_price(self, ticker: str, date: datetime) -> Decimal | None:
        """Get closing price for ticker on date."""
        query = """
            SELECT close
            FROM stock_prices
            WHERE symbol = ? AND DATE(timestamp) = DATE(?)
        """
        result = self.db.conn.execute(query, [ticker, date]).fetchone()
        return Decimal(str(result[0])) if result and result[0] else None

    def can_open_position(self, price: Decimal) -> bool:
        """Check if we can open a new position."""
        # Check position limit
        if len(self.positions) >= self.config.max_positions:
            return False

        # Check if we have enough cash
        position_value = price * Decimal(100)  # Assume 100 shares
        commission = position_value * Decimal(str(self.config.commission_pct))

        return self.cash >= (position_value + commission)

    def open_position(
        self,
        ticker: str,
        date: datetime,
        price: Decimal,
        entry_reason: EntryReason,
        stop_loss: Decimal,
        take_profit: Decimal,
    ) -> bool:
        """
        Open a new position.

        Args:
            ticker: Stock ticker
            date: Entry date
            price: Entry price
            entry_reason: Reason for entry
            stop_loss: Stop loss price
            take_profit: Take profit price

        Returns:
            True if position opened successfully
        """
        if ticker in self.positions:
            return False  # Already have position

        if not self.can_open_position(price):
            return False  # Can't afford

        # Calculate position size
        position_value = self.cash * Decimal(str(self.config.position_size_pct))
        shares = int(position_value / price)

        if shares == 0:
            return False

        # Calculate costs
        total_cost = price * Decimal(shares)
        commission = total_cost * Decimal(str(self.config.commission_pct))

        # Deduct from cash
        self.cash -= total_cost + commission
        self.commission_paid += commission

        # Create position
        position = Position(
            ticker=ticker,
            entry_date=date,
            entry_price=price,
            entry_reason=entry_reason,
            shares=shares,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        self.positions[ticker] = position

        return True

    def close_position(
        self, ticker: str, date: datetime, price: Decimal, exit_reason: ExitReason
    ) -> Trade | None:
        """
        Close an open position.

        Args:
            ticker: Stock ticker
            date: Exit date
            price: Exit price
            exit_reason: Reason for exit

        Returns:
            Completed Trade object
        """
        if ticker not in self.positions:
            return None

        position = self.positions[ticker]

        # Calculate proceeds
        proceeds = price * Decimal(position.shares)
        commission = proceeds * Decimal(str(self.config.commission_pct))

        # Add to cash
        self.cash += proceeds - commission
        self.commission_paid += commission

        # Calculate P&L
        cost_basis = position.entry_price * Decimal(position.shares)
        profit_loss = proceeds - cost_basis - commission * 2  # Entry + exit commission
        profit_pct = float((profit_loss / cost_basis) * 100)

        holding_days = (date - position.entry_date).days

        # Create trade record
        trade = Trade(
            ticker=ticker,
            entry_date=position.entry_date,
            exit_date=date,
            entry_price=position.entry_price,
            exit_price=price,
            shares=position.shares,
            entry_reason=position.entry_reason,
            exit_reason=exit_reason,
            profit_loss=profit_loss,
            profit_pct=profit_pct,
            holding_days=holding_days,
            confidence=0.5,  # TODO: Store confidence from entry signal
        )

        self.trades.append(trade)

        # Remove position
        del self.positions[ticker]

        return trade

    def get_portfolio_value(self, date: datetime) -> Decimal:
        """Calculate total portfolio value (cash + positions)."""
        portfolio_value = self.cash

        for ticker, position in self.positions.items():
            current_price = self.get_current_price(ticker, date)
            if current_price:
                portfolio_value += current_price * Decimal(position.shares)

        return portfolio_value

    def run(self, tickers: list[str], start_date: datetime, end_date: datetime) -> BacktestResults:
        """
        Run backtest over date range.

        Args:
            tickers: List of tickers to trade
            start_date: Backtest start date
            end_date: Backtest end date

        Returns:
            BacktestResults with performance metrics
        """
        print(f"\n{'='*60}")
        print(f"BACKTESTING")
        print(f"{'='*60}")
        print(f"Tickers: {len(tickers)}")
        print(f"Period: {start_date.date()} to {end_date.date()}")
        print(f"Starting Capital: ${self.config.starting_capital:,.2f}")
        print(f"Position Size: {self.config.position_size_pct:.1%}")
        print(f"Max Positions: {self.config.max_positions}")
        print(f"{'='*60}\n")

        # Get all trading days
        trading_days_query = """
            SELECT DISTINCT DATE(timestamp) as date
            FROM stock_prices
            WHERE DATE(timestamp) >= DATE(?)
              AND DATE(timestamp) <= DATE(?)
            ORDER BY date
        """

        trading_days = [
            datetime.fromisoformat(row[0])
            for row in self.db.conn.execute(trading_days_query, [start_date, end_date]).fetchall()
        ]

        print(f"Trading days: {len(trading_days)}")

        # Simulate trading day by day
        for day_idx, date in enumerate(trading_days):
            if day_idx % 50 == 0:
                progress = (day_idx / len(trading_days)) * 100
                portfolio_value = self.get_portfolio_value(date)
                print(
                    f"Progress: {progress:5.1f}% | Date: {date.date()} | "
                    f"Portfolio: ${portfolio_value:,.2f} | "
                    f"Positions: {len(self.positions)} | Trades: {len(self.trades)}"
                )

            # Track equity curve
            portfolio_value = self.get_portfolio_value(date)
            self.equity_curve.append((date, portfolio_value))

            # Check existing positions for exits
            positions_to_close = []
            for ticker, position in self.positions.items():
                current_price = self.get_current_price(ticker, date)
                if not current_price:
                    continue

                # Get ML prediction
                ml_prediction = self.get_ml_prediction(ticker, date)
                ml_confidence = ml_prediction[1] if ml_prediction else None

                # Check for sell signal
                sell_signal = self.strategy.generate_sell_signal(
                    position, ticker, date, current_price, ml_confidence
                )

                if sell_signal:
                    positions_to_close.append((ticker, current_price, sell_signal.exit_reason))

            # Close positions
            for ticker, price, exit_reason in positions_to_close:
                trade = self.close_position(ticker, date, price, exit_reason)
                if trade:
                    result = "WIN" if trade.profit_loss > 0 else "LOSS"
                    print(
                        f"  {result} | {ticker} | {trade.entry_reason.value} -> "
                        f"{trade.exit_reason.value} | "
                        f"${trade.entry_price:.2f} -> ${trade.exit_price:.2f} | "
                        f"P&L: ${trade.profit_loss:,.2f} ({trade.profit_pct:+.1f}%) | "
                        f"{trade.holding_days}d"
                    )

            # Look for new entry signals
            if len(self.positions) < self.config.max_positions:
                for ticker in tickers:
                    # Skip if already have position
                    if ticker in self.positions:
                        continue

                    current_price = self.get_current_price(ticker, date)
                    if not current_price:
                        continue

                    # Get ML prediction
                    ml_prediction = self.get_ml_prediction(ticker, date)
                    if ml_prediction:
                        direction, confidence, expected_return = ml_prediction

                        # Skip if confidence too low
                        if confidence < self.config.min_ml_confidence:
                            continue

                        # Skip if prediction is DOWN
                        if direction == 0:
                            continue
                    else:
                        confidence = None

                    # Check for buy signal
                    buy_signal = self.strategy.generate_buy_signal(
                        ticker, date, current_price, confidence
                    )

                    if buy_signal:
                        opened = self.open_position(
                            ticker,
                            date,
                            current_price,
                            buy_signal.entry_reason,
                            buy_signal.stop_loss,
                            buy_signal.take_profit,
                        )

                        if opened:
                            print(
                                f"  ENTRY | {ticker} | {buy_signal.entry_reason.value} | "
                                f"${current_price:.2f} | "
                                f"SL: ${buy_signal.stop_loss:.2f} | "
                                f"TP: ${buy_signal.take_profit:.2f} | "
                                f"Conf: {buy_signal.confidence:.2f}"
                            )

        # Close any remaining positions at end
        for ticker in list(self.positions.keys()):
            final_price = self.get_current_price(ticker, end_date)
            if final_price:
                self.close_position(ticker, end_date, final_price, ExitReason.TIME_EXIT)

        # Calculate results
        return self._calculate_results(start_date, end_date)

    def _calculate_results(self, start_date: datetime, end_date: datetime) -> BacktestResults:
        """Calculate backtest performance metrics."""
        ending_capital = self.get_portfolio_value(end_date)
        total_return = ending_capital - self.config.starting_capital
        total_return_pct = float((total_return / self.config.starting_capital) * 100)

        # Win rate
        winning_trades = [t for t in self.trades if t.profit_loss > 0]
        losing_trades = [t for t in self.trades if t.profit_loss <= 0]

        win_rate = len(winning_trades) / len(self.trades) if self.trades else 0.0

        # Average profit/loss
        avg_profit = (
            sum(t.profit_loss for t in winning_trades) / len(winning_trades)
            if winning_trades
            else Decimal("0")
        )
        avg_loss = (
            sum(t.profit_loss for t in losing_trades) / len(losing_trades)
            if losing_trades
            else Decimal("0")
        )

        # Profit factor
        gross_profit = sum(t.profit_loss for t in winning_trades)
        gross_loss = abs(sum(t.profit_loss for t in losing_trades))
        profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else 0.0

        # Max drawdown
        max_drawdown, max_dd_date = self._calculate_max_drawdown()

        # Sharpe and Sortino ratios
        sharpe_ratio = self._calculate_sharpe_ratio()
        sortino_ratio = self._calculate_sortino_ratio()

        # Average holding period
        avg_holding_days = (
            sum(t.holding_days for t in self.trades) / len(self.trades) if self.trades else 0.0
        )

        return BacktestResults(
            start_date=start_date,
            end_date=end_date,
            starting_capital=self.config.starting_capital,
            ending_capital=ending_capital,
            total_return=float(total_return),
            total_return_pct=total_return_pct,
            total_trades=len(self.trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            avg_profit=avg_profit,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            max_drawdown_date=max_dd_date,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            avg_holding_days=avg_holding_days,
            total_commission=self.commission_paid,
            trades=self.trades,
        )

    def _calculate_max_drawdown(self) -> tuple[float, datetime | None]:
        """Calculate maximum drawdown from equity curve."""
        if not self.equity_curve:
            return 0.0, None

        max_dd = 0.0
        max_dd_date = None
        peak = self.equity_curve[0][1]

        for date, value in self.equity_curve:
            if value > peak:
                peak = value

            drawdown = float((peak - value) / peak)

            if drawdown > max_dd:
                max_dd = drawdown
                max_dd_date = date

        return max_dd, max_dd_date

    def _calculate_sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio from equity curve."""
        if len(self.equity_curve) < 2:
            return 0.0

        # Calculate daily returns
        returns = []
        for i in range(1, len(self.equity_curve)):
            prev_value = float(self.equity_curve[i - 1][1])
            curr_value = float(self.equity_curve[i][1])
            daily_return = (curr_value - prev_value) / prev_value
            returns.append(daily_return)

        if not returns:
            return 0.0

        # Annualized
        avg_return = sum(returns) / len(returns) * 252  # 252 trading days
        std_return = pd.Series(returns).std() * (252**0.5)

        if std_return == 0:
            return 0.0

        sharpe = (avg_return - risk_free_rate) / std_return

        return float(sharpe)

    def _calculate_sortino_ratio(self, risk_free_rate: float = 0.02) -> float:
        """Calculate Sortino ratio (only downside deviation)."""
        if len(self.equity_curve) < 2:
            return 0.0

        # Calculate daily returns
        returns = []
        for i in range(1, len(self.equity_curve)):
            prev_value = float(self.equity_curve[i - 1][1])
            curr_value = float(self.equity_curve[i][1])
            daily_return = (curr_value - prev_value) / prev_value
            returns.append(daily_return)

        if not returns:
            return 0.0

        # Downside deviation
        downside_returns = [r for r in returns if r < 0]
        if not downside_returns:
            return float("inf")

        avg_return = sum(returns) / len(returns) * 252
        downside_std = pd.Series(downside_returns).std() * (252**0.5)

        if downside_std == 0:
            return 0.0

        sortino = (avg_return - risk_free_rate) / downside_std

        return float(sortino)
