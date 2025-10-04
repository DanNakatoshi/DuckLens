"""DuckDB storage manager for market data."""

from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

from src.config.settings import settings
from src.models.schemas import (
    EconomicIndicator,
    PolygonShortInterest,
    PolygonShortVolume,
    StockPrice,
)


class MarketDataDB:
    """Manager for storing and retrieving market data in DuckDB."""

    def __init__(self, db_path: str | None = None):
        """Initialize database connection."""
        self.db_path = db_path or settings.duckdb_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(self.db_path)
        self._create_tables()

    def __enter__(self) -> "MarketDataDB":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def _create_tables(self) -> None:
        """Create tables if they don't exist."""
        # Stock prices table (OHLCV data)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_prices (
                symbol VARCHAR NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                open DECIMAL(18, 4) NOT NULL,
                high DECIMAL(18, 4) NOT NULL,
                low DECIMAL(18, 4) NOT NULL,
                close DECIMAL(18, 4) NOT NULL,
                volume BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (symbol, timestamp)
            )
        """
        )

        # Short interest table (bi-monthly)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS short_interest (
                ticker VARCHAR NOT NULL,
                settlement_date DATE NOT NULL,
                short_interest BIGINT,
                avg_daily_volume BIGINT,
                days_to_cover DECIMAL(10, 2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (ticker, settlement_date)
            )
        """
        )

        # Short volume table (daily)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS short_volume (
                ticker VARCHAR NOT NULL,
                date DATE NOT NULL,
                short_volume BIGINT,
                total_volume BIGINT,
                short_volume_ratio DECIMAL(6, 2),
                exempt_volume BIGINT,
                non_exempt_volume BIGINT,
                adf_short_volume BIGINT,
                adf_short_volume_exempt BIGINT,
                nasdaq_carteret_short_volume BIGINT,
                nasdaq_carteret_short_volume_exempt BIGINT,
                nasdaq_chicago_short_volume BIGINT,
                nasdaq_chicago_short_volume_exempt BIGINT,
                nyse_short_volume BIGINT,
                nyse_short_volume_exempt BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (ticker, date)
            )
        """
        )

        # Ticker metadata table (for feature engineering)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ticker_metadata (
                symbol VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                category VARCHAR NOT NULL,
                sub_category VARCHAR NOT NULL,
                weight DECIMAL(3, 2) NOT NULL,
                inverse BOOLEAN DEFAULT FALSE,
                description VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Technical indicators table (pre-calculated for faster access)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS technical_indicators (
                symbol VARCHAR NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                sma_20 DECIMAL(18, 4),
                sma_50 DECIMAL(18, 4),
                sma_200 DECIMAL(18, 4),
                ema_12 DECIMAL(18, 4),
                ema_26 DECIMAL(18, 4),
                macd DECIMAL(18, 4),
                macd_signal DECIMAL(18, 4),
                macd_histogram DECIMAL(18, 4),
                rsi_14 DECIMAL(10, 2),
                bb_middle DECIMAL(18, 4),
                bb_upper DECIMAL(18, 4),
                bb_lower DECIMAL(18, 4),
                atr_14 DECIMAL(18, 4),
                stoch_k DECIMAL(10, 2),
                stoch_d DECIMAL(10, 2),
                obv BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (symbol, timestamp)
            )
        """
        )

        # Economic indicators table (FRED data)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS economic_indicators (
                series_id VARCHAR NOT NULL,
                indicator_name VARCHAR NOT NULL,
                date DATE NOT NULL,
                value DECIMAL(18, 6),
                units VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (series_id, date)
            )
        """
        )

        # Economic calendar table (event releases)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS economic_calendar (
                event_id VARCHAR PRIMARY KEY,
                event_type VARCHAR NOT NULL,
                event_name VARCHAR NOT NULL,
                release_date TIMESTAMP NOT NULL,
                actual_value DECIMAL(18, 6),
                forecast_value DECIMAL(18, 6),
                previous_value DECIMAL(18, 6),
                surprise DECIMAL(18, 6),
                impact VARCHAR NOT NULL,
                description VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Earnings calendar table (company earnings dates)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS earnings (
                symbol VARCHAR NOT NULL,
                earnings_date DATE NOT NULL,
                fiscal_ending DATE,
                estimate DECIMAL(10, 2),
                reported DECIMAL(10, 2),
                surprise DECIMAL(10, 2),
                source VARCHAR DEFAULT 'alpha_vantage',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (symbol, earnings_date)
            )
        """
        )

        # Trade journal table (manual trade tracking)
        self.conn.execute(
            """
            CREATE SEQUENCE IF NOT EXISTS trade_journal_seq START 1
        """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trade_journal (
                id INTEGER PRIMARY KEY DEFAULT nextval('trade_journal_seq'),
                trade_date DATE NOT NULL,
                symbol VARCHAR NOT NULL,
                action VARCHAR NOT NULL,
                quantity INTEGER NOT NULL,
                price DECIMAL(18, 4) NOT NULL,
                total_value DECIMAL(18, 2) NOT NULL,
                strategy VARCHAR DEFAULT 'trend_2x',
                reason VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Account balance tracking (cash + margin)
        self.conn.execute(
            """
            CREATE SEQUENCE IF NOT EXISTS account_balance_seq START 1
        """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS account_balance (
                id INTEGER PRIMARY KEY DEFAULT nextval('account_balance_seq'),
                balance_date DATE NOT NULL,
                cash_balance DECIMAL(18, 2) NOT NULL,
                portfolio_value DECIMAL(18, 2) DEFAULT 0,
                total_value DECIMAL(18, 2) NOT NULL,
                margin_used DECIMAL(18, 2) DEFAULT 0,
                margin_available DECIMAL(18, 2) DEFAULT 0,
                buying_power DECIMAL(18, 2) DEFAULT 0,
                spy_price DECIMAL(18, 4),
                spy_return_pct DECIMAL(10, 4),
                account_return_pct DECIMAL(10, 4),
                notes VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(balance_date)
            )
        """
        )

        # Options flow daily aggregates table (for CatBoost features)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS options_flow_daily (
                ticker VARCHAR NOT NULL,
                date DATE NOT NULL,
                total_call_volume BIGINT NOT NULL,
                total_put_volume BIGINT NOT NULL,
                put_call_ratio DECIMAL(10, 4) NOT NULL,
                total_call_oi BIGINT NOT NULL,
                total_put_oi BIGINT NOT NULL,
                call_oi_change BIGINT DEFAULT 0,
                put_oi_change BIGINT DEFAULT 0,
                avg_call_iv DECIMAL(10, 6),
                avg_put_iv DECIMAL(10, 6),
                iv_rank DECIMAL(6, 2),
                net_delta DECIMAL(18, 6),
                net_gamma DECIMAL(18, 6),
                net_theta DECIMAL(18, 6),
                net_vega DECIMAL(18, 6),
                unusual_call_contracts INTEGER DEFAULT 0,
                unusual_put_contracts INTEGER DEFAULT 0,
                call_volume_at_ask BIGINT DEFAULT 0,
                put_volume_at_ask BIGINT DEFAULT 0,
                max_pain_price DECIMAL(12, 2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (ticker, date)
            )
        """
        )

        # Options flow indicators table (derived CatBoost features)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS options_flow_indicators (
                ticker VARCHAR NOT NULL,
                date DATE NOT NULL,
                put_call_ratio DECIMAL(10, 4) NOT NULL,
                put_call_ratio_ma5 DECIMAL(10, 4),
                put_call_ratio_percentile DECIMAL(6, 2),
                smart_money_index DECIMAL(10, 6),
                oi_momentum DECIMAL(10, 6),
                unusual_activity_score DECIMAL(10, 2),
                iv_rank DECIMAL(6, 2),
                iv_skew DECIMAL(10, 6),
                delta_weighted_volume DECIMAL(18, 6),
                gamma_exposure DECIMAL(18, 6),
                max_pain_distance DECIMAL(10, 6),
                high_oi_call_strike DECIMAL(12, 2),
                high_oi_put_strike DECIMAL(12, 2),
                days_to_nearest_expiry INTEGER,
                flow_signal VARCHAR NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (ticker, date)
            )
        """
        )

        # Options contracts snapshot table (individual contracts for detailed analysis)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS options_contracts_snapshot (
                contract_ticker VARCHAR NOT NULL,
                underlying_ticker VARCHAR NOT NULL,
                strike_price DECIMAL(12, 2) NOT NULL,
                expiration_date DATE NOT NULL,
                contract_type VARCHAR NOT NULL,
                snapshot_date DATE NOT NULL,
                last_price DECIMAL(12, 4),
                volume BIGINT,
                open_interest BIGINT,
                delta DECIMAL(10, 6),
                gamma DECIMAL(10, 6),
                theta DECIMAL(10, 6),
                vega DECIMAL(10, 6),
                implied_volatility DECIMAL(10, 6),
                bid DECIMAL(12, 4),
                ask DECIMAL(12, 4),
                bid_size INTEGER,
                ask_size INTEGER,
                break_even_price DECIMAL(12, 2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (contract_ticker, snapshot_date)
            )
        """
        )

        # Trading signals table (track all buy/sell signals and outcomes)
        self.conn.execute(
            """
            CREATE SEQUENCE IF NOT EXISTS trading_signals_seq START 1
        """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trading_signals (
                id INTEGER PRIMARY KEY DEFAULT nextval('trading_signals_seq'),
                signal_date DATE NOT NULL,
                signal_time TIMESTAMP NOT NULL,
                symbol VARCHAR(10) NOT NULL,
                signal_type VARCHAR(10) NOT NULL,
                signal_source VARCHAR(50) NOT NULL,

                signal_strength DECIMAL(5, 2),
                confidence_level VARCHAR(20),

                price_at_signal DECIMAL(18, 4),
                target_entry DECIMAL(18, 4),
                target_exit DECIMAL(18, 4),
                stop_loss DECIMAL(18, 4),

                rsi_value DECIMAL(10, 2),
                macd_value DECIMAL(10, 4),
                volume_ratio DECIMAL(10, 2),
                trend_direction VARCHAR(10),

                current_position_size DECIMAL(18, 2),
                suggested_action VARCHAR(50),
                suggested_quantity INTEGER,
                suggested_allocation_pct DECIMAL(5, 2),

                use_margin BOOLEAN DEFAULT FALSE,
                margin_requirement DECIMAL(18, 2),
                risk_level VARCHAR(20),

                action_taken BOOLEAN DEFAULT FALSE,
                actual_entry_date DATE,
                actual_entry_price DECIMAL(18, 4),
                actual_quantity INTEGER,

                max_profit_potential DECIMAL(18, 2),
                actual_profit DECIMAL(18, 2),
                days_held INTEGER,
                outcome VARCHAR(20),

                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Portfolio rebalancing recommendations table
        self.conn.execute(
            """
            CREATE SEQUENCE IF NOT EXISTS rebalancing_recommendations_seq START 1
        """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rebalancing_recommendations (
                id INTEGER PRIMARY KEY DEFAULT nextval('rebalancing_recommendations_seq'),
                recommendation_date TIMESTAMP NOT NULL,

                total_portfolio_value DECIMAL(18, 2),
                cash_available DECIMAL(18, 2),
                margin_available DECIMAL(18, 2),

                action_type VARCHAR(20),
                symbol_to_reduce VARCHAR(10),
                symbol_to_increase VARCHAR(10),

                reduce_quantity INTEGER,
                increase_quantity INTEGER,
                reduce_reason TEXT,
                increase_reason TEXT,

                expected_improvement_pct DECIMAL(10, 2),
                risk_score DECIMAL(5, 2),

                executed BOOLEAN DEFAULT FALSE,
                execution_date TIMESTAMP,
                actual_improvement_pct DECIMAL(10, 2),

                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Create indexes for better query performance
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_stock_prices_symbol ON stock_prices(symbol)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_stock_prices_timestamp ON stock_prices(timestamp)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_short_interest_ticker ON short_interest(ticker)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_short_volume_ticker ON short_volume(ticker)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_technical_indicators_symbol ON technical_indicators(symbol)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_economic_indicators_series ON economic_indicators(series_id)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_economic_indicators_date ON economic_indicators(date)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_economic_calendar_type ON economic_calendar(event_type)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_economic_calendar_date ON economic_calendar(release_date)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_options_flow_ticker ON options_flow_daily(ticker)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_options_flow_date ON options_flow_daily(date)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_options_indicators_ticker ON options_flow_indicators(ticker)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_options_indicators_date ON options_flow_indicators(date)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_options_contracts_underlying ON options_contracts_snapshot(underlying_ticker)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_options_contracts_date ON options_contracts_snapshot(snapshot_date)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_options_contracts_expiry ON options_contracts_snapshot(expiration_date)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_trading_signals_symbol ON trading_signals(symbol)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_trading_signals_date ON trading_signals(signal_date)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_trading_signals_source ON trading_signals(signal_source)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rebalancing_date ON rebalancing_recommendations(recommendation_date)"
        )

        # Sync ticker metadata on init
        self._sync_ticker_metadata()

    def _sync_ticker_metadata(self) -> None:
        """Sync ticker metadata from configuration to database."""
        try:
            from src.config.tickers import TIER_1_TICKERS

            data = [
                (
                    t.symbol,
                    t.name,
                    t.category,
                    t.sub_category,
                    t.weight,
                    t.inverse,
                    t.description,
                )
                for t in TIER_1_TICKERS
            ]

            self.conn.executemany(
                """
                INSERT OR REPLACE INTO ticker_metadata
                (symbol, name, category, sub_category, weight, inverse, description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                data,
            )
        except ImportError:
            pass  # Tickers module not available yet

    def insert_stock_prices(self, prices: list[StockPrice]) -> int:
        """
        Insert or update stock prices.

        Args:
            prices: List of StockPrice objects

        Returns:
            Number of rows inserted/updated
        """
        if not prices:
            return 0

        data = [
            (
                p.symbol,
                p.timestamp,
                float(p.open),
                float(p.high),
                float(p.low),
                float(p.close),
                p.volume,
            )
            for p in prices
        ]

        # Use INSERT OR REPLACE to handle duplicates
        self.conn.executemany(
            """
            INSERT OR REPLACE INTO stock_prices
            (symbol, timestamp, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            data,
        )

        return len(data)

    def insert_short_interest(self, short_data: list[PolygonShortInterest]) -> int:
        """
        Insert or update short interest data.

        Args:
            short_data: List of PolygonShortInterest objects

        Returns:
            Number of rows inserted/updated
        """
        if not short_data:
            return 0

        data = [
            (
                d.ticker,
                d.settlement_date,
                d.short_interest,
                d.avg_daily_volume,
                d.days_to_cover,
            )
            for d in short_data
        ]

        self.conn.executemany(
            """
            INSERT OR REPLACE INTO short_interest
            (ticker, settlement_date, short_interest, avg_daily_volume, days_to_cover)
            VALUES (?, ?, ?, ?, ?)
        """,
            data,
        )

        return len(data)

    def insert_short_volume(self, short_data: list[PolygonShortVolume]) -> int:
        """
        Insert or update short volume data.

        Args:
            short_data: List of PolygonShortVolume objects

        Returns:
            Number of rows inserted/updated
        """
        if not short_data:
            return 0

        data = [
            (
                d.ticker,
                d.date,
                d.short_volume,
                d.total_volume,
                d.short_volume_ratio,
                d.exempt_volume,
                d.non_exempt_volume,
                d.adf_short_volume,
                d.adf_short_volume_exempt,
                d.nasdaq_carteret_short_volume,
                d.nasdaq_carteret_short_volume_exempt,
                d.nasdaq_chicago_short_volume,
                d.nasdaq_chicago_short_volume_exempt,
                d.nyse_short_volume,
                d.nyse_short_volume_exempt,
            )
            for d in short_data
        ]

        self.conn.executemany(
            """
            INSERT OR REPLACE INTO short_volume
            (ticker, date, short_volume, total_volume, short_volume_ratio,
             exempt_volume, non_exempt_volume, adf_short_volume, adf_short_volume_exempt,
             nasdaq_carteret_short_volume, nasdaq_carteret_short_volume_exempt,
             nasdaq_chicago_short_volume, nasdaq_chicago_short_volume_exempt,
             nyse_short_volume, nyse_short_volume_exempt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            data,
        )

        return len(data)

    def insert_indicators(self, symbol: str, indicators_df) -> int:
        """
        Insert or update technical indicators.

        Args:
            symbol: Stock symbol
            indicators_df: DataFrame with indicators (from TechnicalIndicators.calculate_all_indicators)

        Returns:
            Number of rows inserted/updated
        """
        if indicators_df.empty:
            return 0

        # Prepare data for insertion
        data = []
        for timestamp, row in indicators_df.iterrows():
            data.append(
                (
                    symbol,
                    timestamp,
                    float(row.get("sma_20")) if pd.notna(row.get("sma_20")) else None,
                    float(row.get("sma_50")) if pd.notna(row.get("sma_50")) else None,
                    float(row.get("sma_200")) if pd.notna(row.get("sma_200")) else None,
                    float(row.get("ema_12")) if pd.notna(row.get("ema_12")) else None,
                    float(row.get("ema_26")) if pd.notna(row.get("ema_26")) else None,
                    float(row.get("macd")) if pd.notna(row.get("macd")) else None,
                    float(row.get("signal")) if pd.notna(row.get("signal")) else None,
                    float(row.get("histogram")) if pd.notna(row.get("histogram")) else None,
                    float(row.get("rsi_14")) if pd.notna(row.get("rsi_14")) else None,
                    float(row.get("middle")) if pd.notna(row.get("middle")) else None,
                    float(row.get("upper")) if pd.notna(row.get("upper")) else None,
                    float(row.get("lower")) if pd.notna(row.get("lower")) else None,
                    float(row.get("atr_14")) if pd.notna(row.get("atr_14")) else None,
                    float(row.get("k")) if pd.notna(row.get("k")) else None,
                    float(row.get("d")) if pd.notna(row.get("d")) else None,
                    int(row.get("obv")) if pd.notna(row.get("obv")) else None,
                )
            )

        self.conn.executemany(
            """
            INSERT OR REPLACE INTO technical_indicators
            (symbol, timestamp, sma_20, sma_50, sma_200, ema_12, ema_26,
             macd, macd_signal, macd_histogram, rsi_14,
             bb_middle, bb_upper, bb_lower, atr_14, stoch_k, stoch_d, obv)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            data,
        )

        return len(data)

    def insert_economic_indicators(self, indicators: list) -> int:
        """
        Insert or update economic indicators from FRED.

        Args:
            indicators: List of EconomicIndicator objects

        Returns:
            Number of rows inserted/updated
        """
        if not indicators:
            return 0

        data = [
            (
                ind.series_id,
                ind.indicator_name,
                ind.date,
                float(ind.value) if ind.value is not None else None,
                ind.units,
            )
            for ind in indicators
        ]

        self.conn.executemany(
            """
            INSERT OR REPLACE INTO economic_indicators
            (series_id, indicator_name, date, value, units)
            VALUES (?, ?, ?, ?, ?)
        """,
            data,
        )

        return len(data)

    def insert_earnings(self, earnings_list: list[dict]) -> int:
        """
        Insert or update earnings dates.

        Args:
            earnings_list: List of earnings dicts from Alpha Vantage:
                [
                    {
                        "symbol": "AAPL",
                        "earnings_date": "2024-01-25",
                        "fiscal_ending": "2023-12-31",
                        "estimate": "2.10"
                    },
                    ...
                ]

        Returns:
            Number of rows inserted/updated
        """
        if not earnings_list:
            return 0

        data = []
        for earn in earnings_list:
            # Skip if missing required fields
            if not earn.get("symbol") or not earn.get("earnings_date"):
                continue

            # Handle both "earnings_date" and "report_date" keys
            earnings_date = earn.get("earnings_date") or earn.get("report_date")

            data.append((
                earn["symbol"],
                earnings_date,
                earn.get("fiscal_ending"),
                float(earn.get("estimate")) if earn.get("estimate") and earn.get("estimate") != "" else None,
            ))

        if not data:
            return 0

        self.conn.executemany(
            """
            INSERT OR REPLACE INTO earnings
            (symbol, earnings_date, fiscal_ending, estimate)
            VALUES (?, ?, ?, ?)
        """,
            data,
        )

        return len(data)

    def get_next_earnings(self, symbol: str) -> tuple[str, int] | None:
        """
        Get next earnings date for a symbol.

        Args:
            symbol: Ticker symbol

        Returns:
            (earnings_date_str, days_until) or None
        """
        from datetime import date

        today = date.today()

        result = self.conn.execute(
            """
            SELECT earnings_date
            FROM earnings
            WHERE symbol = ?
            AND earnings_date >= ?
            ORDER BY earnings_date
            LIMIT 1
        """,
            [symbol, today],
        ).fetchone()

        if not result:
            return None

        earnings_date = result[0]
        days_until = (earnings_date - today).days

        return (earnings_date.strftime("%Y-%m-%d"), days_until)

    def insert_calendar_events(self, events: list) -> int:
        """
        Insert or update economic calendar events.

        Args:
            events: List of EconomicCalendarEvent objects

        Returns:
            Number of rows inserted/updated
        """
        if not events:
            return 0

        data = [
            (
                event.event_id,
                event.event_type,
                event.event_name,
                event.release_date,
                float(event.actual_value) if event.actual_value is not None else None,
                float(event.forecast_value) if event.forecast_value is not None else None,
                float(event.previous_value) if event.previous_value is not None else None,
                float(event.surprise) if event.surprise is not None else None,
                event.impact,
                event.description,
            )
            for event in events
        ]

        self.conn.executemany(
            """
            INSERT OR REPLACE INTO economic_calendar
            (event_id, event_type, event_name, release_date, actual_value,
             forecast_value, previous_value, surprise, impact, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            data,
        )

        return len(data)

    def insert_options_flow_daily(self, flow_data: list) -> int:
        """
        Insert or update daily options flow aggregates.

        Args:
            flow_data: List of OptionsFlowDaily objects

        Returns:
            Number of rows inserted/updated
        """
        if not flow_data:
            return 0

        data = [
            (
                flow.ticker,
                flow.date,
                flow.total_call_volume,
                flow.total_put_volume,
                float(flow.put_call_ratio),
                flow.total_call_oi,
                flow.total_put_oi,
                flow.call_oi_change,
                flow.put_oi_change,
                float(flow.avg_call_iv) if flow.avg_call_iv is not None else None,
                float(flow.avg_put_iv) if flow.avg_put_iv is not None else None,
                float(flow.iv_rank) if flow.iv_rank is not None else None,
                float(flow.net_delta) if flow.net_delta is not None else None,
                float(flow.net_gamma) if flow.net_gamma is not None else None,
                float(flow.net_theta) if flow.net_theta is not None else None,
                float(flow.net_vega) if flow.net_vega is not None else None,
                flow.unusual_call_contracts,
                flow.unusual_put_contracts,
                flow.call_volume_at_ask,
                flow.put_volume_at_ask,
                float(flow.max_pain_price) if flow.max_pain_price is not None else None,
            )
            for flow in flow_data
        ]

        self.conn.executemany(
            """
            INSERT OR REPLACE INTO options_flow_daily
            (ticker, date, total_call_volume, total_put_volume, put_call_ratio,
             total_call_oi, total_put_oi, call_oi_change, put_oi_change,
             avg_call_iv, avg_put_iv, iv_rank, net_delta, net_gamma, net_theta, net_vega,
             unusual_call_contracts, unusual_put_contracts, call_volume_at_ask,
             put_volume_at_ask, max_pain_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            data,
        )

        return len(data)

    def insert_options_flow_indicators(self, indicators: list) -> int:
        """
        Insert or update options flow indicators for CatBoost.

        Args:
            indicators: List of OptionsFlowIndicators objects

        Returns:
            Number of rows inserted/updated
        """
        if not indicators:
            return 0

        data = [
            (
                ind.ticker,
                ind.date,
                float(ind.put_call_ratio),
                float(ind.put_call_ratio_ma5) if ind.put_call_ratio_ma5 is not None else None,
                (
                    float(ind.put_call_ratio_percentile)
                    if ind.put_call_ratio_percentile is not None
                    else None
                ),
                float(ind.smart_money_index) if ind.smart_money_index is not None else None,
                float(ind.oi_momentum) if ind.oi_momentum is not None else None,
                float(ind.unusual_activity_score),
                float(ind.iv_rank) if ind.iv_rank is not None else None,
                float(ind.iv_skew) if ind.iv_skew is not None else None,
                float(ind.delta_weighted_volume) if ind.delta_weighted_volume is not None else None,
                float(ind.gamma_exposure) if ind.gamma_exposure is not None else None,
                float(ind.max_pain_distance) if ind.max_pain_distance is not None else None,
                float(ind.high_oi_call_strike) if ind.high_oi_call_strike is not None else None,
                float(ind.high_oi_put_strike) if ind.high_oi_put_strike is not None else None,
                ind.days_to_nearest_expiry,
                ind.flow_signal,
            )
            for ind in indicators
        ]

        self.conn.executemany(
            """
            INSERT OR REPLACE INTO options_flow_indicators
            (ticker, date, put_call_ratio, put_call_ratio_ma5, put_call_ratio_percentile,
             smart_money_index, oi_momentum, unusual_activity_score, iv_rank, iv_skew,
             delta_weighted_volume, gamma_exposure, max_pain_distance,
             high_oi_call_strike, high_oi_put_strike, days_to_nearest_expiry, flow_signal)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            data,
        )

        return len(data)

    def insert_options_contracts(self, contracts: list) -> int:
        """
        Insert or update options contracts snapshots.

        Args:
            contracts: List of OptionsChainContract objects

        Returns:
            Number of rows inserted/updated
        """
        if not contracts:
            return 0

        data = [
            (
                c.ticker,
                c.underlying_ticker,
                float(c.strike_price),
                c.expiration_date,
                c.contract_type,
                c.snapshot_time.date(),  # Use date part for snapshot_date
                float(c.last_price) if c.last_price is not None else None,
                c.volume,
                c.open_interest,
                float(c.delta) if c.delta is not None else None,
                float(c.gamma) if c.gamma is not None else None,
                float(c.theta) if c.theta is not None else None,
                float(c.vega) if c.vega is not None else None,
                float(c.implied_volatility) if c.implied_volatility is not None else None,
                float(c.bid) if c.bid is not None else None,
                float(c.ask) if c.ask is not None else None,
                c.bid_size,
                c.ask_size,
                float(c.break_even_price) if c.break_even_price is not None else None,
            )
            for c in contracts
        ]

        self.conn.executemany(
            """
            INSERT OR REPLACE INTO options_contracts_snapshot
            (contract_ticker, underlying_ticker, strike_price, expiration_date,
             contract_type, snapshot_date, last_price, volume, open_interest,
             delta, gamma, theta, vega, implied_volatility, bid, ask,
             bid_size, ask_size, break_even_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            data,
        )

        return len(data)

    def get_stock_prices(
        self,
        symbol: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict]:
        """
        Retrieve stock prices for a symbol.

        Args:
            symbol: Stock symbol
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of price records as dictionaries
        """
        query = "SELECT * FROM stock_prices WHERE symbol = ?"
        params = [symbol]

        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)

        query += " ORDER BY timestamp"

        return self.conn.execute(query, params).fetchdf().to_dict("records")

    def get_latest_date(self, symbol: str) -> datetime | None:
        """
        Get the latest date for which we have data for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Latest timestamp or None if no data exists
        """
        result = self.conn.execute(
            "SELECT MAX(timestamp) as max_date FROM stock_prices WHERE symbol = ?",
            [symbol],
        ).fetchone()

        return result[0] if result and result[0] else None

    def get_latest_economic_date(self, series_id: str | None = None) -> datetime | None:
        """
        Get the latest date for which we have economic indicator data.

        Args:
            series_id: FRED series ID (if None, returns latest across all series)

        Returns:
            Latest date or None if no data exists
        """
        if series_id:
            result = self.conn.execute(
                "SELECT MAX(date) as max_date FROM economic_indicators WHERE series_id = ?",
                [series_id],
            ).fetchone()
        else:
            result = self.conn.execute(
                "SELECT MAX(date) as max_date FROM economic_indicators"
            ).fetchone()

        return result[0] if result and result[0] else None

    def get_economic_indicators(
        self,
        series_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict]:
        """
        Retrieve economic indicators.

        Args:
            series_id: Optional FRED series ID to filter by
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of economic indicator records
        """
        query = "SELECT * FROM economic_indicators WHERE 1=1"
        params = []

        if series_id:
            query += " AND series_id = ?"
            params.append(series_id)

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)

        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date DESC"

        result = self.conn.execute(query, params).fetchall()
        columns = [desc[0] for desc in self.conn.description]

        return [dict(zip(columns, row)) for row in result]

    def get_table_stats(self) -> dict:
        """Get statistics about stored data."""
        stats = {}

        # Stock prices stats
        result = self.conn.execute(
            """
            SELECT
                COUNT(*) as total_rows,
                COUNT(DISTINCT symbol) as unique_symbols,
                MIN(timestamp) as earliest_date,
                MAX(timestamp) as latest_date
            FROM stock_prices
        """
        ).fetchone()

        stats["stock_prices"] = {
            "total_rows": result[0],
            "unique_symbols": result[1],
            "earliest_date": result[2],
            "latest_date": result[3],
        }

        # Short interest stats
        result = self.conn.execute(
            """
            SELECT
                COUNT(*) as total_rows,
                COUNT(DISTINCT ticker) as unique_tickers,
                MIN(settlement_date) as earliest_date,
                MAX(settlement_date) as latest_date
            FROM short_interest
        """
        ).fetchone()

        stats["short_interest"] = {
            "total_rows": result[0],
            "unique_tickers": result[1],
            "earliest_date": result[2],
            "latest_date": result[3],
        }

        # Short volume stats
        result = self.conn.execute(
            """
            SELECT
                COUNT(*) as total_rows,
                COUNT(DISTINCT ticker) as unique_tickers,
                MIN(date) as earliest_date,
                MAX(date) as latest_date
            FROM short_volume
        """
        ).fetchone()

        stats["short_volume"] = {
            "total_rows": result[0],
            "unique_tickers": result[1],
            "earliest_date": result[2],
            "latest_date": result[3],
        }

        # Economic indicators stats
        result = self.conn.execute(
            """
            SELECT
                COUNT(*) as total_rows,
                COUNT(DISTINCT series_id) as unique_series,
                MIN(date) as earliest_date,
                MAX(date) as latest_date
            FROM economic_indicators
        """
        ).fetchone()

        stats["economic_indicators"] = {
            "total_rows": result[0],
            "unique_series": result[1],
            "earliest_date": result[2],
            "latest_date": result[3],
        }

        return stats
