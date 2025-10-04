"""
Fetch earnings with automatic retry for incomplete data.

This wrapper script runs fetch_earnings.py repeatedly until all tickers
have earnings data, handling API failures and incomplete fetches gracefully.

Usage:
    python scripts/fetch_earnings_retry.py                    # Auto-retry until complete
    python scripts/fetch_earnings_retry.py --max-attempts 5   # Limit retry attempts
    python scripts/fetch_earnings_retry.py --days-ahead 60    # Pass through args
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.tickers import TIER_2_STOCKS
from src.data.storage.market_data_db import MarketDataDB


def get_tickers_with_earnings() -> set[str]:
    """Get set of tickers that have earnings data in database (read-only)."""
    import duckdb
    from pathlib import Path

    db_path = Path(__file__).parent.parent / "data" / "ducklens.db"

    # Use read-only connection to avoid locking issues
    conn = duckdb.connect(str(db_path), read_only=True)
    result = conn.execute("""
        SELECT DISTINCT symbol
        FROM earnings
        WHERE earnings_date >= CURRENT_DATE
    """).fetchall()
    conn.close()

    return {row[0] for row in result}


def get_watchlist_symbols() -> set[str]:
    """Get all watchlist symbols."""
    return {t.symbol for t in TIER_2_STOCKS}


def run_fetch_earnings(args_list: list[str]) -> tuple[bool, int]:
    """
    Run fetch_earnings.py script using poetry run.

    Returns:
        (success, fetched_count)
    """
    try:
        root_dir = Path(__file__).parent.parent

        # Use sys.executable to run fetch_earnings.py in the same Python environment
        # This works whether called directly or via poetry run
        cmd = [sys.executable, str(root_dir / "scripts" / "fetch_earnings.py")] + args_list

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=root_dir
        )

        # Parse output to get fetched count
        fetched_count = 0
        for line in result.stdout.split("\n"):
            if "RESULTS: Fetched" in line:
                # Extract number from "RESULTS: Fetched 45 earnings dates"
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "Fetched" and i + 1 < len(parts):
                        try:
                            fetched_count = int(parts[i + 1])
                        except ValueError:
                            pass
                        break

        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        return (result.returncode == 0, fetched_count)

    except Exception as e:
        print(f"! Error running fetch_earnings.py: {e}")
        return (False, 0)


def main():
    """Fetch earnings with automatic retry until complete."""
    parser = argparse.ArgumentParser(
        description="Fetch earnings with auto-retry until complete"
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="Maximum retry attempts (default: 3)"
    )
    parser.add_argument(
        "--retry-delay",
        type=int,
        default=30,
        help="Seconds to wait between retries (default: 30)"
    )
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=0.80,
        help="Minimum coverage percentage to consider complete (default: 80%%)"
    )

    # Pass-through arguments for fetch_earnings.py
    parser.add_argument("--source", choices=["auto", "finnhub", "alphavantage"], default="auto")
    parser.add_argument("--days-ahead", type=int, default=90)
    parser.add_argument("--include-historical", action="store_true")
    parser.add_argument("--limit", type=int, default=25)

    args = parser.parse_args()

    print("=" * 70)
    print("FETCH EARNINGS WITH AUTO-RETRY")
    print("=" * 70)
    print()

    # Get total watchlist count
    watchlist_symbols = get_watchlist_symbols()
    total_tickers = len(watchlist_symbols)
    min_required = int(total_tickers * args.min_coverage)

    print(f"Watchlist: {total_tickers} tickers")
    print(f"Target: {min_required}+ tickers ({args.min_coverage:.0%} coverage)")
    print(f"Max attempts: {args.max_attempts}")
    print()

    # Build pass-through args
    fetch_args = [
        "--source", args.source,
        "--days-ahead", str(args.days_ahead),
    ]
    if args.include_historical:
        fetch_args.append("--include-historical")
    if args.source == "alphavantage":
        fetch_args.extend(["--limit", str(args.limit)])

    # Retry loop
    attempt = 0
    while attempt < args.max_attempts:
        attempt += 1

        print(f"{'=' * 70}")
        print(f"ATTEMPT {attempt}/{args.max_attempts}")
        print(f"{'=' * 70}")
        print()

        # Run fetch
        success, fetched_count = run_fetch_earnings(fetch_args)

        if not success:
            print()
            print(f"⚠ Fetch failed on attempt {attempt}")
            if attempt < args.max_attempts:
                print(f"   Retrying in {args.retry_delay} seconds...")
                time.sleep(args.retry_delay)
            continue

        # Check coverage (read-only, no lock)
        tickers_with_earnings = get_tickers_with_earnings()
        coverage_count = len(tickers_with_earnings)
        coverage_pct = coverage_count / total_tickers

        print()
        print("=" * 70)
        print(f"COVERAGE CHECK")
        print("=" * 70)
        print(f"Tickers with earnings: {coverage_count}/{total_tickers} ({coverage_pct:.1%})")
        print()

        # Check if we're done
        if coverage_count >= min_required:
            print("OK SUCCESS! Earnings data is complete")
            print()

            # Show missing tickers (if any)
            missing = watchlist_symbols - tickers_with_earnings
            if missing:
                print(f"! Missing earnings for {len(missing)} tickers:")
                for ticker in sorted(missing):
                    print(f"   - {ticker}")
                print()
                print("These tickers may not have announced earnings yet.")

            print("=" * 70)
            return 0

        # Not complete - check if we should retry
        missing = watchlist_symbols - tickers_with_earnings
        print(f"! Incomplete: Missing {len(missing)} tickers")
        print()

        if attempt < args.max_attempts:
            print(f"Missing tickers: {', '.join(sorted(list(missing)[:10]))}" +
                  (f" and {len(missing) - 10} more..." if len(missing) > 10 else ""))
            print()
            print(f"Retrying in {args.retry_delay} seconds...")
            print()
            time.sleep(args.retry_delay)
        else:
            print(f"! Reached max attempts ({args.max_attempts})")
            print()
            print("Missing tickers:")
            for ticker in sorted(missing):
                print(f"   - {ticker}")
            print()
            print("Options:")
            print(f"  1. Run again: python scripts/fetch_earnings_retry.py")
            print(f"  2. Increase attempts: python scripts/fetch_earnings_retry.py --max-attempts 5")
            print(f"  3. Try alternate API: python scripts/fetch_earnings_retry.py --source alphavantage")
            print()
            return 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
