# DuckLens - Interactive Menu System

function Show-Menu {
    Clear-Host
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host "                         DUCKLENS                               " -ForegroundColor Cyan
    Write-Host "                  Trading Strategy System                       " -ForegroundColor Cyan
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host ""

    Write-Host "DAILY TRADING WORKFLOW" -ForegroundColor Yellow
    Write-Host "  1  Morning Check      - Pre-market analysis and buy signals" -ForegroundColor White
    Write-Host "  2  Intraday Monitor   - 3 PM check for buy/sell decisions" -ForegroundColor White
    Write-Host "  3  Update Daily       - End-of-day data update and portfolio stats" -ForegroundColor White
    Write-Host ""

    Write-Host "PORTFOLIO AND ANALYSIS" -ForegroundColor Yellow
    Write-Host "  4  Portfolio Status   - View current holdings and performance" -ForegroundColor White
    Write-Host "  5  Watchlist          - View all watchlist signals" -ForegroundColor White
    Write-Host "  6  Calculate to 1M    - Timeline to reach 1 million dollars" -ForegroundColor White
    Write-Host "  7  401k Guide         - Fidelity retirement rebalancing guide" -ForegroundColor White
    Write-Host "  8  Show Chart         - Display price chart for any ticker" -ForegroundColor White
    Write-Host ""

    Write-Host "DATA MANAGEMENT" -ForegroundColor Yellow
    Write-Host "  9  Check Data         - Verify data integrity" -ForegroundColor White
    Write-Host " 10  Database Stats     - View all tables and record counts" -ForegroundColor White
    Write-Host " 11  Fetch 10 Years     - Download 10 years of historical data" -ForegroundColor White
    Write-Host " 12  Calculate Indicators - Update technical indicators" -ForegroundColor White
    Write-Host ""

    Write-Host "BACKTESTING AND RESEARCH" -ForegroundColor Yellow
    Write-Host " 13  Backtest 10 Years  - Test strategy on all tickers" -ForegroundColor White
    Write-Host " 14  Backtest SPY       - Test trend detector on SPY" -ForegroundColor White
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
            Write-Host "`n>> Running Morning Check..." -ForegroundColor Green
            & .\tasks.ps1 morning
        }
        "2" {
            Write-Host "`n>> Running Intraday Monitor..." -ForegroundColor Green
            & .\tasks.ps1 intraday
        }
        "3" {
            Write-Host "`n>> Running Daily Update..." -ForegroundColor Green
            & .\tasks.ps1 update-daily
        }
        "4" {
            Write-Host "`n>> Showing Portfolio..." -ForegroundColor Green
            & .\tasks.ps1 portfolio
        }
        "5" {
            Write-Host "`n>> Showing Watchlist..." -ForegroundColor Green
            & .\tasks.ps1 watchlist
        }
        "6" {
            Write-Host "`n>> Calculating Timeline to 1M..." -ForegroundColor Green
            & .\tasks.ps1 calc-1m
        }
        "7" {
            Write-Host "`n>> Opening 401k Guide..." -ForegroundColor Green
            & .\tasks.ps1 401k
        }
        "8" {
            $ticker = Read-Host "Enter ticker (default: AAPL)"
            if ([string]::IsNullOrWhiteSpace($ticker)) { $ticker = "AAPL" }
            $days = Read-Host "Enter days (default: 90)"
            if ([string]::IsNullOrWhiteSpace($days)) { $days = "90" }
            Write-Host "`n>> Showing Chart for $ticker..." -ForegroundColor Green
            & .\tasks.ps1 chart $ticker $days
        }
        "9" {
            Write-Host "`n>> Checking Data Integrity..." -ForegroundColor Green
            & .\tasks.ps1 check-data
        }
        "10" {
            Write-Host "`n>> Showing Database Stats..." -ForegroundColor Green
            & .\tasks.ps1 db-stats
        }
        "11" {
            Write-Host "`n>> Fetching 10 Years Data..." -ForegroundColor Green
            & .\tasks.ps1 fetch-10-years
        }
        "12" {
            Write-Host "`n>> Calculating Indicators..." -ForegroundColor Green
            & .\tasks.ps1 calc-indicators
        }
        "13" {
            Write-Host "`n>> Running 10-Year Backtest..." -ForegroundColor Green
            & .\tasks.ps1 backtest-10-years
        }
        "14" {
            Write-Host "`n>> Running SPY Backtest..." -ForegroundColor Green
            & .\tasks.ps1 backtest-trend-spy
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
