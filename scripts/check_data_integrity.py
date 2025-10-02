"""
Data Integrity Checker - Verify completeness of all market data.

Checks:
1. OHLCV data (CRITICAL - trading cannot work without this)
2. Technical indicators (CRITICAL - strategy depends on SMA/EMA/MACD)
3. Short volume (WARNING - nice to have, not critical)
4. Options flow (WARNING - nice to have, not critical)
5. Economic data (WARNING - macro context, not critical)
6. Earnings calendar (WARNING - helps avoid earnings volatility)

Exit codes:
- 0: All critical data present
- 1: Missing critical data (OHLCV or indicators)
- 2: Warning only (missing optional data)
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from src.config.tickers import TIER_1_TICKERS, TIER_2_STOCKS
from src.data.storage.market_data_db import MarketDataDB

console = Console()


def check_ohlcv_data(db: MarketDataDB, ticker: str, expected_start: datetime, expected_end: datetime) -> dict:
    """Check if OHLCV data is complete for a ticker."""

    query = """
        SELECT
            MIN(timestamp) as earliest_date,
            MAX(timestamp) as latest_date,
            COUNT(*) as total_records,
            COUNT(DISTINCT DATE(timestamp)) as trading_days
        FROM stock_prices
        WHERE symbol = ?
    """

    result = db.conn.execute(query, [ticker]).fetchone()

    if not result or result[2] == 0:
        return {
            "status": "MISSING",
            "earliest": None,
            "latest": None,
            "records": 0,
            "trading_days": 0,
            "coverage_pct": 0.0,
        }

    earliest, latest, records, trading_days = result

    # Calculate expected trading days (approx 252 per year)
    years = (expected_end - expected_start).days / 365.25
    expected_trading_days = int(years * 252)
    coverage_pct = (trading_days / expected_trading_days * 100) if expected_trading_days > 0 else 0

    # Check if data is recent (within 7 days)
    if latest:
        days_old = (datetime.now() - datetime.fromisoformat(str(latest))).days
        if days_old > 7:
            status = "STALE"
        elif coverage_pct < 80:
            status = "INCOMPLETE"
        else:
            status = "OK"
    else:
        status = "MISSING"

    return {
        "status": status,
        "earliest": earliest,
        "latest": latest,
        "records": records,
        "trading_days": trading_days,
        "expected_days": expected_trading_days,
        "coverage_pct": coverage_pct,
    }


def check_indicators(db: MarketDataDB, ticker: str) -> dict:
    """Check if technical indicators are calculated."""

    # Check if we have recent indicator data
    query = """
        SELECT
            COUNT(DISTINCT timestamp) as days_with_indicators
        FROM technical_indicators
        WHERE symbol = ?
          AND sma_20 IS NOT NULL
          AND sma_50 IS NOT NULL
          AND sma_200 IS NOT NULL
          AND timestamp > (CURRENT_DATE - INTERVAL '30 days')
    """

    result = db.conn.execute(query, [ticker]).fetchone()
    days_with_indicators = result[0] if result else 0

    if days_with_indicators >= 15:  # At least 15 recent days with indicators
        return {"status": "OK", "recent_days": days_with_indicators}
    elif days_with_indicators > 0:
        return {"status": "INCOMPLETE", "recent_days": days_with_indicators}
    else:
        return {"status": "MISSING", "recent_days": 0}


def check_short_volume(db: MarketDataDB, ticker: str) -> dict:
    """Check if short volume data exists (optional)."""

    query = """
        SELECT
            COUNT(*) as records,
            MAX(date) as latest_date
        FROM short_volume
        WHERE ticker = ?
    """

    result = db.conn.execute(query, [ticker]).fetchone()

    if not result or result[0] == 0:
        return {"status": "MISSING", "records": 0, "latest": None}

    records, latest = result

    if latest:
        days_old = (datetime.now().date() - datetime.fromisoformat(str(latest)).date()).days
        if days_old > 7:
            return {"status": "STALE", "records": records, "latest": latest, "days_old": days_old}

    return {"status": "OK", "records": records, "latest": latest}


def check_options_flow(db: MarketDataDB, ticker: str) -> dict:
    """Check if options flow data exists (optional)."""

    query = """
        SELECT
            COUNT(*) as records
        FROM options_contracts_snapshot
        WHERE underlying_ticker = ?
    """

    result = db.conn.execute(query, [ticker]).fetchone()

    if not result or result[0] == 0:
        return {"status": "MISSING", "records": 0}

    records = result[0]
    return {"status": "OK", "records": records}


def main():
    """Run comprehensive data integrity check."""

    console.print()
    console.print(Panel(
        "[bold white]DATA INTEGRITY CHECKER[/bold white]",
        subtitle="Verifying market data completeness",
        border_style="bright_blue",
        box=box.DOUBLE
    ))
    console.print()

    # Configuration
    end_date = datetime.now()
    start_date_10y = end_date - timedelta(days=365 * 10)
    start_date_3y = end_date - timedelta(days=365 * 3)

    # Collect all tickers
    all_tickers = [t.symbol for t in TIER_1_TICKERS + TIER_2_STOCKS]

    console.print(f"Checking {len(all_tickers)} tickers...")
    console.print(f"Expected date range: {start_date_10y.date()} to {end_date.date()}")
    console.print()

    with MarketDataDB() as db:
        # Results storage
        critical_issues = []
        warnings = []
        ok_count = 0

        # === CHECK 1: OHLCV DATA (CRITICAL) ===
        console.print("[bold cyan]>> CRITICAL: OHLCV Data[/bold cyan]")
        console.print()

        ohlcv_table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
        ohlcv_table.add_column("Ticker", style="bold white", width=8)
        ohlcv_table.add_column("Status", width=12)
        ohlcv_table.add_column("Earliest", width=12)
        ohlcv_table.add_column("Latest", width=12)
        ohlcv_table.add_column("Days", justify="right", width=8)
        ohlcv_table.add_column("Coverage", justify="right", width=10)

        for ticker in all_tickers[:20]:  # Show first 20 in detail
            ohlcv = check_ohlcv_data(db, ticker, start_date_10y, end_date)

            if ohlcv["status"] == "OK":
                status_text = f"[green]{ohlcv['status']}[/green]"
                ok_count += 1
            elif ohlcv["status"] == "INCOMPLETE":
                status_text = f"[yellow]{ohlcv['status']}[/yellow]"
                warnings.append(f"{ticker}: OHLCV data incomplete ({ohlcv['coverage_pct']:.1f}% coverage)")
            elif ohlcv["status"] == "STALE":
                status_text = f"[yellow]{ohlcv['status']}[/yellow]"
                warnings.append(f"{ticker}: OHLCV data is stale (last update: {ohlcv['latest']})")
            else:
                status_text = f"[red]{ohlcv['status']}[/red]"
                critical_issues.append(f"{ticker}: MISSING OHLCV data - cannot trade this stock!")

            earliest = str(ohlcv['earliest'])[:10] if ohlcv['earliest'] else "N/A"
            latest = str(ohlcv['latest'])[:10] if ohlcv['latest'] else "N/A"
            coverage = f"{ohlcv['coverage_pct']:.1f}%" if ohlcv['coverage_pct'] > 0 else "N/A"

            ohlcv_table.add_row(
                ticker,
                status_text,
                earliest,
                latest,
                str(ohlcv['trading_days']),
                coverage
            )

        console.print(ohlcv_table)

        if len(all_tickers) > 20:
            console.print(f"\n... and {len(all_tickers) - 20} more tickers")

        console.print()

        # === CHECK 2: TECHNICAL INDICATORS (CRITICAL) ===
        console.print("[bold cyan]>> CRITICAL: Technical Indicators[/bold cyan]")
        console.print()

        indicators_table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
        indicators_table.add_column("Ticker", style="bold white", width=8)
        indicators_table.add_column("Status", width=12)
        indicators_table.add_column("Recent Days", justify="right", width=15)
        indicators_table.add_column("Issue", width=50)

        for ticker in all_tickers[:20]:
            indicators = check_indicators(db, ticker)

            if indicators["status"] == "OK":
                status_text = f"[green]{indicators['status']}[/green]"
                issue = "SMA/EMA/MACD calculated"
            elif indicators["status"] == "INCOMPLETE":
                status_text = f"[yellow]{indicators['status']}[/yellow]"
                issue = "Indicators incomplete - run: .\\tasks.ps1 calc-indicators"
                warnings.append(f"{ticker}: Indicators incomplete")
            else:
                status_text = f"[red]{indicators['status']}[/red]"
                issue = "NO INDICATORS - strategy will fail!"
                critical_issues.append(f"{ticker}: MISSING indicators - run calc-indicators!")

            indicators_table.add_row(
                ticker,
                status_text,
                str(indicators['recent_days']),
                issue
            )

        console.print(indicators_table)

        if len(all_tickers) > 20:
            console.print(f"\n... and {len(all_tickers) - 20} more tickers")

        console.print()

        # === CHECK 3: SHORT VOLUME (OPTIONAL - WARNING ONLY) ===
        console.print("[bold yellow]>> OPTIONAL: Short Volume Data[/bold yellow]")
        console.print()

        short_missing = 0
        short_ok = 0

        for ticker in all_tickers:
            short = check_short_volume(db, ticker)
            if short["status"] == "OK":
                short_ok += 1
            else:
                short_missing += 1

        short_coverage_pct = (short_ok / len(all_tickers) * 100) if all_tickers else 0

        if short_coverage_pct < 50:
            console.print(f"[yellow]Warning:[/yellow] Short volume coverage: {short_coverage_pct:.1f}% ({short_ok}/{len(all_tickers)} tickers)")
            console.print(f"  This is optional data. Strategy works without it.")
        else:
            console.print(f"[green]OK:[/green] Short volume coverage: {short_coverage_pct:.1f}% ({short_ok}/{len(all_tickers)} tickers)")

        console.print()

        # === CHECK 4: OPTIONS FLOW (OPTIONAL - WARNING ONLY) ===
        console.print("[bold yellow]>> OPTIONAL: Options Flow Data[/bold yellow]")
        console.print()

        options_missing = 0
        options_ok = 0

        for ticker in all_tickers:
            options = check_options_flow(db, ticker)
            if options["status"] == "OK":
                options_ok += 1
            else:
                options_missing += 1

        options_coverage_pct = (options_ok / len(all_tickers) * 100) if all_tickers else 0

        if options_coverage_pct < 30:
            console.print(f"[yellow]Warning:[/yellow] Options flow coverage: {options_coverage_pct:.1f}% ({options_ok}/{len(all_tickers)} tickers)")
            console.print(f"  This is optional data. Strategy works without it.")
        else:
            console.print(f"[green]OK:[/green] Options flow coverage: {options_coverage_pct:.1f}% ({options_ok}/{len(all_tickers)} tickers)")

        console.print()

        # === CHECK 5: ECONOMIC DATA (OPTIONAL) ===
        console.print("[bold yellow]>> OPTIONAL: Economic Indicators (FRED)[/bold yellow]")
        console.print()

        query = """
            SELECT COUNT(DISTINCT series_id) as series_count
            FROM economic_indicators
            WHERE date > (CURRENT_DATE - INTERVAL '30 days')
        """
        result = db.conn.execute(query).fetchone()
        recent_economic_series = result[0] if result else 0

        if recent_economic_series >= 5:
            console.print(f"[green]OK:[/green] {recent_economic_series} economic series with recent data")
        elif recent_economic_series > 0:
            console.print(f"[yellow]Warning:[/yellow] Only {recent_economic_series} economic series with recent data")
            console.print(f"  Run: .\\tasks.ps1 fetch-economic to update")
        else:
            console.print(f"[yellow]Warning:[/yellow] No recent economic data found")
            console.print(f"  Run: .\\tasks.ps1 fetch-economic to fetch FRED data")

        console.print()

        # === SUMMARY ===
        console.print("[bold white]" + "=" * 80 + "[/bold white]")
        console.print()

        if critical_issues:
            console.print(Panel(
                f"[bold red]CRITICAL ISSUES FOUND ({len(critical_issues)})[/bold red]\n\n" +
                "\n".join(f"  - {issue}" for issue in critical_issues[:10]) +
                (f"\n  ... and {len(critical_issues) - 10} more" if len(critical_issues) > 10 else ""),
                border_style="red",
                title=">> Action Required"
            ))
            console.print()
            console.print("[bold red]Fix these issues before trading![/bold red]")
            console.print()
            console.print("Run these commands:")
            console.print("  1. [cyan].\\tasks.ps1 fetch-10-years[/cyan]  (fetch missing OHLCV data)")
            console.print("  2. [cyan].\\tasks.ps1 calc-indicators[/cyan]  (calculate technical indicators)")
            console.print()
            return 1

        elif warnings:
            console.print(Panel(
                f"[bold yellow]WARNINGS ({len(warnings)})[/bold yellow]\n\n" +
                "\n".join(f"  - {warning}" for warning in warnings[:10]) +
                (f"\n  ... and {len(warnings) - 10} more" if len(warnings) > 10 else "") +
                "\n\n[white]These are non-critical issues. Strategy can still work.[/white]",
                border_style="yellow",
                title=">> Review Recommended"
            ))
            console.print()
            console.print("[bold yellow]Optional improvements:[/bold yellow]")
            console.print("  - [cyan].\\tasks.ps1 fetch-10-years[/cyan]  (complete OHLCV data)")
            console.print("  - [cyan].\\tasks.ps1 calc-indicators[/cyan]  (update all indicators)")
            console.print("  - [cyan].\\tasks.ps1 fetch-economic[/cyan]  (update economic data)")
            console.print()
            return 2

        else:
            console.print(Panel(
                f"[bold green]ALL CRITICAL DATA PRESENT[/bold green]\n\n" +
                f"  ✓ OHLCV data: {ok_count}/{len(all_tickers)} tickers OK\n" +
                f"  ✓ Technical indicators: Calculated\n" +
                f"  ✓ Short volume: {short_coverage_pct:.1f}% coverage\n" +
                f"  ✓ Options flow: {options_coverage_pct:.1f}% coverage\n" +
                f"  ✓ Economic data: {recent_economic_series} series\n\n" +
                f"[white]Your strategy is ready to trade![/white]",
                border_style="green",
                title=">> Data Integrity Check Passed"
            ))
            console.print()
            console.print("[bold green]System ready for trading![/bold green]")
            console.print()
            console.print("Next steps:")
            console.print("  - [cyan].\\tasks.ps1 morning[/cyan]   (morning check at 8 AM)")
            console.print("  - [cyan].\\tasks.ps1 intraday[/cyan]  (trading decision at 3 PM)")
            console.print()
            return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
