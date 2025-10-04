# DuckLens Development Tasks
# Run with: .\tasks.ps1 <command>

param(
    [Parameter(Position=0)]
    [ValidateSet("test", "lint", "format", "type-check", "all", "install", "fetch-polygon", "check-duckdb", "test-polygon", "fetch-historical", "fetch-10-years", "update-daily", "db-stats", "calc-indicators", "show-indicators", "test-indicators", "fetch-economic", "list-economic", "test-fred", "build-calendar", "fetch-options-flow", "calc-options-metrics", "show-options-flow", "test-options-flow", "test-aggregates", "test-contract", "test-indicators-only", "train-backtest", "train-verbose", "optimize", "backtest-trend-spy", "daily-signals", "watchlist", "backtest-all", "backtest-10-years", "portfolio", "import-portfolio", "analyze-trades", "morning", "intraday", "intraday-plus", "market-check", "calc-1m", "check-data", "401k", "chart", "fetch-earnings", "add-trade", "update-cash", "account-health", "track-performance")]
    [string]$Command = "all",

    [Parameter(Position=1, ValueFromRemainingArguments=$true)]
    $RemainingArgs
)

# Create alias for Poetry if needed
if (-not (Get-Command poetry -ErrorAction SilentlyContinue)) {
    Set-Alias -Name poetry -Value "$env:APPDATA\Python\Python311\Scripts\poetry.exe"
}

function Run-Tests {
    Write-Host "`n=== Running Tests ===" -ForegroundColor Cyan
    poetry run pytest tests/ -v --cov=src --cov-report=term-missing
}

function Run-Lint {
    Write-Host "`n=== Running Ruff Linter ===" -ForegroundColor Cyan
    poetry run ruff check src/ tests/
}

function Run-Format {
    Write-Host "`n=== Formatting Code with Black ===" -ForegroundColor Cyan
    poetry run black src/ tests/
}

function Run-TypeCheck {
    Write-Host "`n=== Type Checking with MyPy ===" -ForegroundColor Cyan
    poetry run mypy src/
}

function Run-Install {
    Write-Host "`n=== Installing Dependencies ===" -ForegroundColor Cyan
    poetry install --no-root
}

function Run-FetchPolygon {
    Write-Host "`n=== Fetching Data from Polygon.io ===" -ForegroundColor Cyan
    poetry run python scripts/test_polygon_connection.py
}

function Run-CheckDuckDB {
    Write-Host "`n=== Checking DuckDB Database ===" -ForegroundColor Cyan
    poetry run python -c "import duckdb; conn = duckdb.connect('./data/ducklens.db'); print('Tables:', conn.execute('SHOW TABLES').fetchall()); conn.close()"
}

function Run-TestPolygon {
    Write-Host "`n=== Running Polygon Collector Tests ===" -ForegroundColor Cyan
    poetry run pytest tests/unit/test_polygon_options.py -v --cov=src.data.collectors.polygon_options_collector --cov-report=term-missing
}

function Run-FetchHistorical {
    Write-Host "`n=== Fetching 5 Years of Historical Market Data ===" -ForegroundColor Cyan
    Write-Host "This will fetch OHLCV + short data for major ETFs/indices" -ForegroundColor Yellow
    Write-Host "This may take 10-30 minutes depending on API rate limits..." -ForegroundColor Yellow
    poetry run python scripts/fetch_historical_data.py
}

function Run-Fetch10Years {
    Write-Host "`n=== Fetching 10 YEARS of Historical Data - ALL TICKERS ===" -ForegroundColor Cyan
    Write-Host "This will fetch 10 years of OHLCV data for all watchlist stocks" -ForegroundColor Yellow
    Write-Host "And calculate all technical indicators automatically" -ForegroundColor Yellow
    Write-Host "This may take 30-60 minutes depending on API rate limits..." -ForegroundColor Yellow
    Write-Host ""
    poetry run python scripts/fetch_10_years_all.py
}

function Run-UpdateDaily {
    Write-Host "`n=== Running Daily Market Data Update ===" -ForegroundColor Cyan
    Write-Host "Best to run after market hours (after 4 PM ET)" -ForegroundColor Yellow
    poetry run python scripts/update_daily_data.py
}

function Run-DBStats {
    Write-Host "`n=== Database Statistics ===" -ForegroundColor Cyan
    poetry run python -c "from src.data.storage.market_data_db import MarketDataDB; db = MarketDataDB(); print('Available Tables:'); tables = db.conn.execute('SHOW TABLES').fetchall(); [print(f'  - {t[0]}') for t in tables]; print(); stats = db.get_table_stats(); import json; print('Table Statistics:'); print(json.dumps(stats, indent=2, default=str)); db.close()"
}

function Run-CalcIndicators {
    Write-Host "`n=== Calculating Technical Indicators ===" -ForegroundColor Cyan
    Write-Host "Calculating SMA, EMA, MACD, RSI, Bollinger Bands, etc." -ForegroundColor Yellow
    poetry run python scripts/calculate_indicators.py --store
}

function Run-ShowIndicators {
    Write-Host "`n=== Displaying Technical Indicators ===" -ForegroundColor Cyan
    poetry run python scripts/calculate_indicators.py --example SPY
}

function Run-TestIndicators {
    Write-Host "`n=== Running Indicators Tests ===" -ForegroundColor Cyan
    poetry run pytest tests/unit/test_indicators.py -v --cov=src.analysis.indicators --cov-report=term-missing
}

function Run-FetchEconomic {
    Write-Host "`n=== Fetching Economic Indicators (FRED) ===" -ForegroundColor Cyan
    Write-Host "Fetching Fed rates, CPI, unemployment, GDP, etc." -ForegroundColor Yellow
    Write-Host "Default: 5 years of data for all 23 indicators" -ForegroundColor Yellow
    poetry run python scripts/fetch_economic_data.py
}

function Run-ListEconomic {
    Write-Host "`n=== Available Economic Indicators ===" -ForegroundColor Cyan
    poetry run python scripts/fetch_economic_data.py --list-series
}

function Run-TestFRED {
    Write-Host "`n=== Running FRED Collector Tests ===" -ForegroundColor Cyan
    poetry run pytest tests/unit/test_fred_collector.py -v --cov=src.data.collectors.fred_collector --cov-report=term-missing
}

function Run-BuildCalendar {
    Write-Host "`n=== Building Economic Calendar ===" -ForegroundColor Cyan
    Write-Host "Creating calendar events from FRED indicator releases" -ForegroundColor Yellow
    Write-Host "This builds a historical record of CPI, NFP, GDP, FOMC events" -ForegroundColor Yellow
    poetry run python scripts/build_economic_calendar.py
}

function Run-FetchOptionsFlow {
    Write-Host "`n=== Fetching Options Flow Data ===" -ForegroundColor Cyan
    Write-Host "Fetching options chain snapshots for all tickers" -ForegroundColor Yellow
    Write-Host "Default: 2 years of data (Polygon Options Starter plan limit)" -ForegroundColor Yellow
    Write-Host "This may take 30-60 minutes..." -ForegroundColor Yellow
    poetry run python scripts/fetch_options_flow.py
}

function Run-CalcOptionsMetrics {
    Write-Host "`n=== Calculating Options Flow Indicators ===" -ForegroundColor Cyan
    Write-Host "Calculating P/C ratio, smart money index, IV rank, etc." -ForegroundColor Yellow
    poetry run python scripts/calculate_options_metrics.py
}

function Run-ShowOptionsFlow {
    Write-Host "`n=== Current Options Flow Signals ===" -ForegroundColor Cyan
    poetry run python scripts/calculate_options_metrics.py --days 1 --show-signals
}

function Run-TestOptionsFlow {
    Write-Host "`n=== Running Options Flow Tests ===" -ForegroundColor Cyan
    poetry run pytest tests/unit/test_options_flow.py -v --cov=src.data.collectors.polygon_options_flow --cov-report=term-missing
}

function Run-TestAggregates {
    Write-Host "`n=== Testing Options Aggregates Approach ===" -ForegroundColor Cyan
    Write-Host "Verifying key strikes, contract lookup, and aggregates fetch" -ForegroundColor Yellow
    poetry run python scripts/test_aggregates_approach.py
}

function Run-TestContractSearch {
    Write-Host "`n=== Testing Contract Search ===" -ForegroundColor Cyan
    poetry run python scripts/test_contract_search.py
}

function Run-TestIndicatorsOnly {
    Write-Host "`n=== Test Strategy with Indicators ONLY (No ML) ===" -ForegroundColor Cyan
    Write-Host "Quick test using only technical indicators" -ForegroundColor Yellow
    Write-Host "Works with your 34 ETFs (SPY, QQQ, GLD, TLT, etc.)" -ForegroundColor Yellow
    Write-Host "No ML training required - fast validation!" -ForegroundColor Yellow
    poetry run python scripts/test_strategy_indicators_only.py
}

function Run-TrainBacktest {
    Write-Host "`n=== Train CatBoost & Run Backtest ===" -ForegroundColor Cyan
    Write-Host "Training ML model and backtesting strategy" -ForegroundColor Yellow
    Write-Host "Default: 3 years training, 2 years backtest" -ForegroundColor Yellow
    poetry run python scripts/train_and_backtest.py
}

function Run-TrainVerbose {
    Write-Host "`n=== Train CatBoost & Run Backtest (VERBOSE) ===" -ForegroundColor Cyan
    Write-Host "Includes detailed reasoning for every buy/sell decision" -ForegroundColor Yellow
    Write-Host "Logs cash-on-sidelines periods when confidence is low" -ForegroundColor Yellow
    Write-Host "Output saved to trade_reasoning.log" -ForegroundColor Yellow
    poetry run python scripts/train_and_backtest_verbose.py
}

function Run-Optimize {
    Write-Host "`n=== Optimize Strategy Hyperparameters ===" -ForegroundColor Cyan
    Write-Host "Testing multiple configurations to find best strategy" -ForegroundColor Yellow
    Write-Host "This will take several hours..." -ForegroundColor Yellow
    poetry run python scripts/optimize_strategy.py
}

function Run-BacktestTrendSpy {
    Write-Host "`n=== Backtest Trend-Change Strategy: SPY ONLY ===" -ForegroundColor Cyan
    Write-Host "Simplified strategy: BUY/SELL/DON'T TRADE based on trend changes" -ForegroundColor Yellow
    Write-Host "Blocks trading on high-impact economic event days" -ForegroundColor Yellow
    Write-Host "Default: 5 years of SPY data (2020-2025)" -ForegroundColor Yellow
    poetry run python scripts/backtest_trend_spy.py --verbose
}

function Run-DailySignals {
    Write-Host "`n=== Daily Trading Signals - ETF Watchlist ===" -ForegroundColor Cyan
    Write-Host "Checking BUY/SELL/HOLD signals for all 34 ETFs" -ForegroundColor Yellow
    Write-Host "For STOCKS watchlist, use: .\tasks.ps1 watchlist" -ForegroundColor Yellow
    poetry run python scripts/daily_signals.py
}

function Run-Watchlist {
    Write-Host "`n=== TRADING WATCHLIST - All Stocks ===" -ForegroundColor Cyan
    Write-Host "Daily BUY/SELL/HOLD signals for individual stocks" -ForegroundColor Yellow
    Write-Host "Run this at end of day to find trading opportunities" -ForegroundColor Yellow
    Write-Host ""
    poetry run python scripts/watchlist_signals.py
}

function Run-BacktestAll {
    Write-Host "`n=== Backtest 2x Leverage Strategy - All Tickers ===" -ForegroundColor Cyan
    Write-Host "Testing 2x leverage strategy across entire watchlist" -ForegroundColor Yellow
    Write-Host ""
    poetry run python scripts/backtest_all_watchlist.py
}

function Run-Backtest10Years {
    Write-Host "`n=== Backtest 2x Leverage Strategy - 10 YEARS ===" -ForegroundColor Cyan
    Write-Host "Testing 2x leverage strategy across 10 years of data" -ForegroundColor Yellow
    Write-Host "Shows detailed stats: trades, win rate, avg hold time, etc." -ForegroundColor Yellow
    Write-Host ""
    poetry run python scripts/backtest_10_years_all.py
}

function Run-Portfolio {
    Write-Host "`n=== DAILY PORTFOLIO REVIEW ===" -ForegroundColor Cyan
    Write-Host "Review your positions with BUY/SELL/HOLD recommendations" -ForegroundColor Yellow
    Write-Host "Shows P&L, signals, and VXX crash protection" -ForegroundColor Yellow
    Write-Host ""
    poetry run python scripts/portfolio_review.py
}

function Run-ImportPortfolio {
    Write-Host "`n=== Import Portfolio from E*TRADE ===" -ForegroundColor Cyan
    Write-Host "Import your current positions and cash" -ForegroundColor Yellow
    Write-Host ""
    poetry run python scripts/import_portfolio.py
}

function Run-AnalyzeTrades {
    Write-Host "`n=== TRADE JOURNAL ANALYSIS ===" -ForegroundColor Cyan
    Write-Host "Analyze past trades to see what worked and what didn't" -ForegroundColor Yellow
    Write-Host "Learn from wins, losses, and track progress to 1M" -ForegroundColor Yellow
    Write-Host ""
    poetry run python scripts/analyze_manual_trades.py
}

function Run-Morning {
    Write-Host "`n=== MORNING CHECK - Pre-Market Analysis ===" -ForegroundColor Cyan
    Write-Host "Run BEFORE market open (before 9:30 AM)" -ForegroundColor Yellow
    Write-Host "Shows: Holdings status, watchlist opportunities, today's game plan" -ForegroundColor Yellow
    Write-Host ""
    poetry run python scripts/morning_check.py
}

function Run-Intraday {
    Write-Host "`n=== INTRADAY MONITOR - 3 PM Trading Decision ===" -ForegroundColor Cyan
    Write-Host "Run at 3 PM for final buy/sell decisions" -ForegroundColor Yellow
    Write-Host "Shows: Real-time prices, intraday movement, recommended actions" -ForegroundColor Yellow
    Write-Host "Data: 15-minute delayed (Polygon.io free tier)" -ForegroundColor Yellow
    Write-Host ""
    poetry run python scripts/intraday_monitor.py
}

function Run-IntradayPlus {
    Write-Host "`n=== INTRADAY MONITOR ENHANCED - 3 PM Trading Decision ===" -ForegroundColor Cyan
    Write-Host "Enhanced version with Rich formatting and color" -ForegroundColor Green
    Write-Host "Shows: Morning BUY signals update, holdings check, new opportunities" -ForegroundColor Green
    Write-Host "Data: 15-minute delayed with full Phase 1 analysis" -ForegroundColor Yellow
    Write-Host ""
    poetry run python scripts/intraday_monitor_enhanced.py
}

function Run-MarketCheck {
    Write-Host "`n=== UNIFIED MARKET CHECK - Smart All-Day Monitor ===" -ForegroundColor Cyan
    Write-Host "REPLACES: morning + intraday scripts - now unified!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Features:" -ForegroundColor Yellow
    Write-Host "  - Auto-detects market status (pre-market, open, after-hours)" -ForegroundColor White
    Write-Host "  - Live prices during market hours (15-min delayed)" -ForegroundColor White
    Write-Host "  - Static data when market is closed" -ForegroundColor White
    Write-Host "  - Auto-refresh option with --live flag" -ForegroundColor White
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  Static mode:  .\tasks.ps1 market-check" -ForegroundColor Cyan
    Write-Host "  Live mode:    .\tasks.ps1 market-check --live" -ForegroundColor Cyan
    Write-Host "  Custom rate:  .\tasks.ps1 market-check --live --interval 300 (5 min)" -ForegroundColor Cyan
    Write-Host ""

    # Pass through any arguments (--live, --interval, etc.)
    if ($RemainingArgs) {
        poetry run python scripts/market_check.py $RemainingArgs
    } else {
        poetry run python scripts/market_check.py
    }
}

function Run-Calc1M {
    Write-Host "`n=== TIME TO $1,000,000 CALCULATOR ===" -ForegroundColor Cyan
    Write-Host "Calculate how long to reach $1M from $30K" -ForegroundColor Yellow
    Write-Host "Shows: Different scenarios, milestones, and success factors" -ForegroundColor Yellow
    Write-Host ""
    poetry run python scripts/calculate_time_to_1m.py
}

function Run-CheckData {
    Write-Host "`n=== DATA INTEGRITY CHECKER ===" -ForegroundColor Cyan
    Write-Host "Verify completeness of all market data" -ForegroundColor Yellow
    Write-Host "Checks: OHLCV, indicators, short volume, options, economic data" -ForegroundColor Yellow
    Write-Host ""
    poetry run python scripts/check_data_integrity.py
}

function Run-401k {
    Write-Host "`n=== FIDELITY 401K - SIMPLE REBALANCING GUIDE ===" -ForegroundColor Cyan
    Write-Host "Opening simple guide for your 401k..." -ForegroundColor Yellow
    Write-Host ""
    Start-Process "FIDELITY_401K_SIMPLE_GUIDE.md"
}

function Run-Chart {
    Write-Host "`n=== SHOW PRICE CHART ===" -ForegroundColor Cyan
    Write-Host "Display console chart for a ticker" -ForegroundColor Yellow
    Write-Host "Usage: .\tasks.ps1 chart AAPL 90" -ForegroundColor Yellow
    Write-Host ""

    $ticker = if ($RemainingArgs -and $RemainingArgs[0]) { $RemainingArgs[0] } else { "AAPL" }
    $days = if ($RemainingArgs -and $RemainingArgs[1]) { $RemainingArgs[1] } else { 90 }

    poetry run python scripts/show_chart.py $ticker $days
}

function Run-FetchEarnings {
    Write-Host "`n=== FETCH EARNINGS CALENDAR (AUTO-RETRY) ===" -ForegroundColor Cyan
    Write-Host "Fetch earnings dates with automatic retry until complete" -ForegroundColor Yellow
    Write-Host "Auto-detects best API: Finnhub (60/min) or Alpha Vantage (25/day)" -ForegroundColor Yellow
    Write-Host "Will retry up to 3 times if data is incomplete" -ForegroundColor Green
    Write-Host ""
    poetry run python scripts/fetch_earnings_retry.py
}

function Run-AddTrade {
    Write-Host "`n=== ADD TRADE TO JOURNAL ===" -ForegroundColor Cyan
    Write-Host "Record executed trades for performance tracking" -ForegroundColor Yellow
    Write-Host ""
    poetry run python scripts/add_trade.py
}

function Run-UpdateCash {
    Write-Host "`n=== RECORD CASH TRANSACTION ===" -ForegroundColor Cyan
    Write-Host "Deposit or withdraw cash (portfolio calculated automatically)" -ForegroundColor Yellow
    Write-Host ""
    poetry run python scripts/record_cash_transaction.py
}

function Run-AccountHealth {
    Write-Host "`n=== ACCOUNT HEALTH DASHBOARD ===" -ForegroundColor Cyan
    Write-Host "View account status, margin risk, and progress to $1M" -ForegroundColor Yellow
    Write-Host ""
    poetry run python scripts/account_health.py
}

function Run-TrackPerformance {
    Write-Host "`n=== PERFORMANCE TRACKING ===" -ForegroundColor Cyan
    Write-Host "Track your journey to $1M vs market (SPY)" -ForegroundColor Yellow
    Write-Host ""
    poetry run python scripts/track_performance.py
}

function Run-All {
    Run-Format
    Run-Lint
    Run-TypeCheck
    Run-Tests
}

switch ($Command) {
    "test" { Run-Tests }
    "lint" { Run-Lint }
    "format" { Run-Format }
    "type-check" { Run-TypeCheck }
    "install" { Run-Install }
    "fetch-polygon" { Run-FetchPolygon }
    "check-duckdb" { Run-CheckDuckDB }
    "test-polygon" { Run-TestPolygon }
    "fetch-historical" { Run-FetchHistorical }
    "fetch-10-years" { Run-Fetch10Years }
    "update-daily" { Run-UpdateDaily }
    "db-stats" { Run-DBStats }
    "calc-indicators" { Run-CalcIndicators }
    "show-indicators" { Run-ShowIndicators }
    "test-indicators" { Run-TestIndicators }
    "fetch-economic" { Run-FetchEconomic }
    "list-economic" { Run-ListEconomic }
    "test-fred" { Run-TestFRED }
    "build-calendar" { Run-BuildCalendar }
    "fetch-options-flow" { Run-FetchOptionsFlow }
    "calc-options-metrics" { Run-CalcOptionsMetrics }
    "show-options-flow" { Run-ShowOptionsFlow }
    "test-options-flow" { Run-TestOptionsFlow }
    "test-aggregates" { Run-TestAggregates }
    "test-contract" { Run-TestContractSearch }
    "test-indicators-only" { Run-TestIndicatorsOnly }
    "train-backtest" { Run-TrainBacktest }
    "train-verbose" { Run-TrainVerbose }
    "optimize" { Run-Optimize }
    "backtest-trend-spy" { Run-BacktestTrendSpy }
    "daily-signals" { Run-DailySignals }
    "watchlist" { Run-Watchlist }
    "backtest-all" { Run-BacktestAll }
    "backtest-10-years" { Run-Backtest10Years }
    "portfolio" { Run-Portfolio }
    "import-portfolio" { Run-ImportPortfolio }
    "analyze-trades" { Run-AnalyzeTrades }
    "morning" { Run-Morning }
    "intraday" { Run-Intraday }
    "intraday-plus" { Run-IntradayPlus }
    "market-check" { Run-MarketCheck }
    "calc-1m" { Run-Calc1M }
    "check-data" { Run-CheckData }
    "401k" { Run-401k }
    "chart" { Run-Chart }
    "fetch-earnings" { Run-FetchEarnings }
    "add-trade" { Run-AddTrade }
    "update-cash" { Run-UpdateCash }
    "account-health" { Run-AccountHealth }
    "track-performance" { Run-TrackPerformance }
    "all" { Run-All }
}

Write-Host "`nDone!" -ForegroundColor Green
