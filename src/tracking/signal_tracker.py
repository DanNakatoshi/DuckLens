"""Track trading signals and their outcomes."""

from datetime import datetime, date
from typing import Optional

from src.data.storage.market_data_db import MarketDataDB


class SignalTracker:
    """Track all trading signals and analyze their performance."""

    def __init__(self):
        """Initialize signal tracker."""
        self.db = None

    def __enter__(self):
        """Context manager entry."""
        self.db = MarketDataDB()
        return self

    def __exit__(self, *args):
        """Context manager exit."""
        if self.db:
            self.db.close()

    def record_signal(
        self,
        symbol: str,
        signal_type: str,  # BUY, SELL, HOLD
        signal_source: str,  # morning_check, intraday_monitor
        signal_strength: float = None,
        confidence_level: str = None,  # HIGH, MEDIUM, LOW
        price_at_signal: float = None,
        target_entry: float = None,
        target_exit: float = None,
        stop_loss: float = None,
        rsi_value: float = None,
        macd_value: float = None,
        volume_ratio: float = None,
        trend_direction: str = None,
        current_position_size: float = 0.0,
        suggested_action: str = None,  # ENTER, ADD, REDUCE, EXIT, HOLD
        suggested_quantity: int = None,
        suggested_allocation_pct: float = None,
        use_margin: bool = False,
        margin_requirement: float = None,
        risk_level: str = None,  # HIGH, MEDIUM, LOW
        notes: str = None,
        signal_date: date = None,
        signal_time: datetime = None,
    ) -> int:
        """
        Record a trading signal to the database.

        Returns:
            Signal ID
        """
        if signal_date is None:
            signal_date = datetime.now().date()
        if signal_time is None:
            signal_time = datetime.now()

        with MarketDataDB() as db:
            result = db.conn.execute(
                """
                INSERT INTO trading_signals (
                    signal_date, signal_time, symbol, signal_type, signal_source,
                    signal_strength, confidence_level,
                    price_at_signal, target_entry, target_exit, stop_loss,
                    rsi_value, macd_value, volume_ratio, trend_direction,
                    current_position_size, suggested_action, suggested_quantity,
                    suggested_allocation_pct, use_margin, margin_requirement,
                    risk_level, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
            """,
                [
                    signal_date,
                    signal_time,
                    symbol,
                    signal_type,
                    signal_source,
                    signal_strength,
                    confidence_level,
                    price_at_signal,
                    target_entry,
                    target_exit,
                    stop_loss,
                    rsi_value,
                    macd_value,
                    volume_ratio,
                    trend_direction,
                    current_position_size,
                    suggested_action,
                    suggested_quantity,
                    suggested_allocation_pct,
                    use_margin,
                    margin_requirement,
                    risk_level,
                    notes,
                ],
            ).fetchone()

            return result[0] if result else None

    def mark_signal_taken(
        self,
        signal_id: int,
        actual_entry_price: float,
        actual_quantity: int,
        actual_entry_date: date = None,
    ):
        """Mark a signal as acted upon."""
        if actual_entry_date is None:
            actual_entry_date = datetime.now().date()

        with MarketDataDB() as db:
            db.conn.execute(
                """
                UPDATE trading_signals
                SET action_taken = TRUE,
                    actual_entry_date = ?,
                    actual_entry_price = ?,
                    actual_quantity = ?
                WHERE id = ?
            """,
                [actual_entry_date, actual_entry_price, actual_quantity, signal_id],
            )

    def update_signal_outcome(
        self,
        signal_id: int,
        actual_profit: float = None,
        days_held: int = None,
        outcome: str = None,  # WIN, LOSS, BREAKEVEN, MISSED
        max_profit_potential: float = None,
    ):
        """Update the outcome of a signal after time has passed."""
        with MarketDataDB() as db:
            db.conn.execute(
                """
                UPDATE trading_signals
                SET actual_profit = ?,
                    days_held = ?,
                    outcome = ?,
                    max_profit_potential = ?
                WHERE id = ?
            """,
                [actual_profit, days_held, outcome, max_profit_potential, signal_id],
            )

    def get_signal_win_rate(
        self, lookback_days: int = 90, signal_source: str = None
    ) -> dict:
        """
        Calculate signal performance metrics.

        Args:
            lookback_days: Number of days to look back
            signal_source: Filter by source (morning_check, intraday_monitor)

        Returns:
            Dict with win rate, avg profit, missed opportunities
        """
        with MarketDataDB() as db:
            # Build query
            query = """
                SELECT
                    COUNT(*) as total_signals,
                    SUM(CASE WHEN action_taken = TRUE THEN 1 ELSE 0 END) as signals_taken,
                    SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN outcome = 'LOSS' THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN outcome = 'MISSED' THEN 1 ELSE 0 END) as missed,
                    AVG(CASE WHEN outcome = 'WIN' THEN actual_profit END) as avg_win,
                    AVG(CASE WHEN outcome = 'LOSS' THEN actual_profit END) as avg_loss,
                    SUM(actual_profit) as total_profit,
                    AVG(max_profit_potential) as avg_max_potential
                FROM trading_signals
                WHERE signal_date >= CURRENT_DATE - INTERVAL '{} days'
            """.format(
                lookback_days
            )

            if signal_source:
                query += f" AND signal_source = '{signal_source}'"

            result = db.conn.execute(query).fetchone()

            if not result:
                return {}

            (
                total_signals,
                signals_taken,
                wins,
                losses,
                missed,
                avg_win,
                avg_loss,
                total_profit,
                avg_max_potential,
            ) = result

            # Calculate metrics
            win_rate = (wins / signals_taken * 100) if signals_taken > 0 else 0
            profit_factor = (
                abs(avg_win * wins / (avg_loss * losses))
                if losses > 0 and avg_loss
                else 0
            )
            action_rate = (signals_taken / total_signals * 100) if total_signals > 0 else 0

            return {
                "total_signals": total_signals or 0,
                "signals_taken": signals_taken or 0,
                "action_rate_pct": action_rate,
                "wins": wins or 0,
                "losses": losses or 0,
                "missed": missed or 0,
                "win_rate_pct": win_rate,
                "avg_win": float(avg_win) if avg_win else 0,
                "avg_loss": float(avg_loss) if avg_loss else 0,
                "total_profit": float(total_profit) if total_profit else 0,
                "profit_factor": profit_factor,
                "avg_max_potential": float(avg_max_potential) if avg_max_potential else 0,
            }

    def get_recent_signals(
        self, limit: int = 20, signal_source: str = None, action_taken: bool = None
    ) -> list:
        """Get recent signals with optional filters."""
        with MarketDataDB() as db:
            query = """
                SELECT
                    id, signal_date, signal_time, symbol, signal_type,
                    signal_source, signal_strength, confidence_level,
                    price_at_signal, suggested_action, suggested_quantity,
                    use_margin, risk_level, action_taken, outcome, notes
                FROM trading_signals
                WHERE 1=1
            """

            if signal_source:
                query += f" AND signal_source = '{signal_source}'"

            if action_taken is not None:
                query += f" AND action_taken = {action_taken}"

            query += " ORDER BY signal_time DESC LIMIT ?"

            results = db.conn.execute(query, [limit]).fetchall()

            signals = []
            for row in results:
                signals.append(
                    {
                        "id": row[0],
                        "signal_date": row[1],
                        "signal_time": row[2],
                        "symbol": row[3],
                        "signal_type": row[4],
                        "signal_source": row[5],
                        "signal_strength": float(row[6]) if row[6] else None,
                        "confidence_level": row[7],
                        "price_at_signal": float(row[8]) if row[8] else None,
                        "suggested_action": row[9],
                        "suggested_quantity": row[10],
                        "use_margin": row[11],
                        "risk_level": row[12],
                        "action_taken": row[13],
                        "outcome": row[14],
                        "notes": row[15],
                    }
                )

            return signals

    def analyze_missed_opportunities(self, lookback_days: int = 90) -> list:
        """
        Analyze signals that were not acted upon.

        Returns list of missed opportunities with what would have happened.
        """
        with MarketDataDB() as db:
            query = """
                SELECT
                    s.id, s.signal_date, s.symbol, s.signal_type,
                    s.price_at_signal, s.target_exit, s.signal_strength,
                    s.max_profit_potential, s.notes
                FROM trading_signals s
                WHERE s.action_taken = FALSE
                AND s.signal_date >= CURRENT_DATE - INTERVAL '{} days'
                AND s.max_profit_potential IS NOT NULL
                ORDER BY s.max_profit_potential DESC
                LIMIT 10
            """.format(
                lookback_days
            )

            results = db.conn.execute(query).fetchall()

            missed = []
            for row in results:
                missed.append(
                    {
                        "id": row[0],
                        "signal_date": row[1],
                        "symbol": row[2],
                        "signal_type": row[3],
                        "price_at_signal": float(row[4]) if row[4] else None,
                        "target_exit": float(row[5]) if row[5] else None,
                        "signal_strength": float(row[6]) if row[6] else None,
                        "max_profit_potential": float(row[7]) if row[7] else None,
                        "notes": row[8],
                    }
                )

            return missed
