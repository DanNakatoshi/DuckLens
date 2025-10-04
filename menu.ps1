# DuckLens - Interactive Menu System

function Show-Menu {
    Clear-Host
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host "                         DUCKLENS                               " -ForegroundColor Cyan
    Write-Host "                  Trading Strategy System                       " -ForegroundColor Cyan
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host ""

    Write-Host "DAILY TRADING WORKFLOW" -ForegroundColor Yellow
    Write-Host "  1  Live Market Check  - Real-time: VIX, holdings, watchlist, unusual activity" -ForegroundColor Green
    Write-Host "  2  Update Daily       - End-of-day data update and portfolio stats" -ForegroundColor White
    Write-Host ""

    Write-Host "PORTFOLIO AND ANALYSIS" -ForegroundColor Yellow
    Write-Host "  3  Portfolio Status   - View current holdings and performance" -ForegroundColor White
    Write-Host "  4  Watchlist          - View all watchlist signals" -ForegroundColor White
    Write-Host "  5  Calculate to 1M    - Timeline to reach 1 million dollars" -ForegroundColor White
    Write-Host "  6  401k Guide         - Fidelity retirement rebalancing guide" -ForegroundColor White
    Write-Host "  7  Show Chart         - Display price chart for any ticker" -ForegroundColor White
    Write-Host ""

    Write-Host "DATA MANAGEMENT" -ForegroundColor Yellow
    Write-Host "  8  Check Data         - Verify data integrity" -ForegroundColor White
    Write-Host "  9  Database Stats     - View all tables and record counts" -ForegroundColor White
    Write-Host " 10  Fetch 10 Years     - Download 10 years of historical data" -ForegroundColor White
    Write-Host " 11  Calculate Indicators - Update technical indicators" -ForegroundColor White
    Write-Host ""

    Write-Host "BACKTESTING AND RESEARCH" -ForegroundColor Yellow
    Write-Host " 12  Backtest 10 Years  - Test strategy on all tickers" -ForegroundColor White
    Write-Host " 13  Backtest SPY       - Test trend detector on SPY" -ForegroundColor White
    Write-Host " 14  Backtest Custom    - Configurable strategy (edit YAML config)" -ForegroundColor Green
    Write-Host " 15  Analyze Trades     - Review historical trade performance" -ForegroundColor White
    Write-Host ""

    Write-Host "SETUP AND MAINTENANCE" -ForegroundColor Yellow
    Write-Host " 16  Install            - Install dependencies" -ForegroundColor White
    Write-Host " 17  Format Code        - Run ruff formatter" -ForegroundColor White
    Write-Host " 18  Type Check         - Run mypy type checker" -ForegroundColor White
    Write-Host ""

    Write-Host "  0  Exit" -ForegroundColor Red
    Write-Host ""
}

function Run-Command {
    param([string]$choice)

    switch ($choice) {
        "1" {
            Write-Host "`n================================================================" -ForegroundColor Green
            Write-Host "LIVE MARKET CHECK - Real-Time Updates" -ForegroundColor Green
            Write-Host "================================================================" -ForegroundColor Green
            Write-Host ""
            Write-Host "Features:" -ForegroundColor Yellow
            Write-Host "  * VIX Fear Index with 1D/7D/14D trends" -ForegroundColor White
            Write-Host "  * Live holdings with updated signals" -ForegroundColor White
            Write-Host "  * Watchlist tracking (pre-open opportunities)" -ForegroundColor White
            Write-Host "  * Unusual activity & volume spikes" -ForegroundColor White
            Write-Host "  * Auto-refresh every 30 seconds during market hours" -ForegroundColor White
            Write-Host ""
            Write-Host "Starting live monitor..." -ForegroundColor Cyan
            Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
            Write-Host ""
            python scripts/market_check.py --live
        }
        "2" {
            Write-Host "`n>> Running Daily Update..." -ForegroundColor Green
            & .\tasks.ps1 update-daily
        }
        "3" {
            Write-Host "`n>> Showing Portfolio..." -ForegroundColor Green
            & .\tasks.ps1 portfolio
        }
        "4" {
            Write-Host "`n>> Showing Watchlist..." -ForegroundColor Green
            & .\tasks.ps1 watchlist
        }
        "5" {
            Write-Host "`n>> Calculating Timeline to 1M..." -ForegroundColor Green
            & .\tasks.ps1 calc-1m
        }
        "6" {
            Write-Host "`n>> Opening 401k Guide..." -ForegroundColor Green
            & .\tasks.ps1 401k
        }
        "7" {
            $ticker = Read-Host "Enter ticker (default: AAPL)"
            if ([string]::IsNullOrWhiteSpace($ticker)) { $ticker = "AAPL" }
            $days = Read-Host "Enter days (default: 90)"
            if ([string]::IsNullOrWhiteSpace($days)) { $days = "90" }
            Write-Host "`n>> Showing Chart for $ticker..." -ForegroundColor Green
            & .\tasks.ps1 chart $ticker $days
        }
        "8" {
            Write-Host "`n>> Checking Data Integrity..." -ForegroundColor Green
            & .\tasks.ps1 check-data
        }
        "9" {
            Write-Host "`n>> Showing Database Stats..." -ForegroundColor Green
            & .\tasks.ps1 db-stats
        }
        "10" {
            Write-Host "`n>> Fetching 10 Years Data..." -ForegroundColor Green
            & .\tasks.ps1 fetch-10-years
        }
        "11" {
            Write-Host "`n>> Calculating Indicators..." -ForegroundColor Green
            & .\tasks.ps1 calc-indicators
        }
        "12" {
            Write-Host "`n>> Running 10-Year Backtest..." -ForegroundColor Green
            & .\tasks.ps1 backtest-10-years
        }
        "13" {
            Write-Host "`n>> Running SPY Backtest..." -ForegroundColor Green
            & .\tasks.ps1 backtest-trend-spy
        }
        "14" {
            Write-Host "`n================================================================" -ForegroundColor Green
            Write-Host "CONFIGURABLE BACKTEST ENGINE" -ForegroundColor Green
            Write-Host "================================================================" -ForegroundColor Green
            Write-Host ""
            Write-Host "Customize your strategy in: config\backtest_strategy.yaml" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "Features:" -ForegroundColor Yellow
            Write-Host "  * Market regime adaptation (BULLISH/NEUTRAL/BEARISH)" -ForegroundColor White
            Write-Host "  * Momentum & breakout filters (leading indicators)" -ForegroundColor White
            Write-Host "  * Trailing stops & dynamic position sizing" -ForegroundColor White
            Write-Host "  * VIX-based risk management" -ForegroundColor White
            Write-Host "  * No future data leakage (walk-forward)" -ForegroundColor White
            Write-Host ""
            Write-Host "Edit config file to customize stops, targets, filters, etc." -ForegroundColor Yellow
            Write-Host ""
            python scripts/backtest_configurable.py
        }
        "15" {
            Write-Host "`n>> Analyzing Trades..." -ForegroundColor Green
            & .\tasks.ps1 analyze-trades
        }
        "16" {
            Write-Host "`n>> Installing Dependencies..." -ForegroundColor Green
            & .\tasks.ps1 install
        }
        "17" {
            Write-Host "`n>> Formatting Code..." -ForegroundColor Green
            & .\tasks.ps1 format
        }
        "18" {
            Write-Host "`n>> Running Type Check..." -ForegroundColor Green
            & .\tasks.ps1 type-check
        }
        "0" {
            Write-Host "`nGoodbye!" -ForegroundColor Cyan
            exit
        }
        default {
            Write-Host "`nInvalid choice. Please try again." -ForegroundColor Red
            Start-Sleep -Seconds 2
            return
        }
    }

    Write-Host "`n" -NoNewline
    Write-Host "Press any key to continue..." -ForegroundColor Gray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

# Main loop
while ($true) {
    Show-Menu
    $choice = Read-Host "Enter your choice (0-18)"
    Run-Command -choice $choice
}
