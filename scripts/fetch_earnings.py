"""
Fetch earnings dates for watchlist tickers.

Supports DUAL sources (auto-selects best available):
- Finnhub (PRIMARY): 60 calls/minute - FAST! All 62 tickers in ~2 minutes
- Alpha Vantage (FALLBACK): 25 calls/day - Slow but works

Smart Fetching Strategy:
- Default: Next 90 days only (confirmed earnings, saves API calls)
- Optional: Add --include-historical for backtest validation (past 365 days)
- Avoids: Estimated dates beyond 90 days (low accuracy, wastes calls)

Usage:
    python scripts/fetch_earnings.py                              # Next 90 days (recommended)
    python scripts/fetch_earnings.py --days-ahead 60              # Next 60 days only
    python scripts/fetch_earnings.py --include-historical         # Next 90 + past 365 days
    python scripts/fetch_earnings.py --source finnhub             # Force Finnhub
    python scripts/fetch_earnings.py --source alphavantage        # Force Alpha Vantage
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.config.tickers import TIER_2_STOCKS
from src.data.collectors.finnhub_earnings import FinnhubEarnings
from src.data.collectors.alpha_vantage_earnings import AlphaVantageEarnings
from src.data.storage.market_data_db import MarketDataDB


def fetch_with_finnhub(symbols: list[str], days_ahead: int = 90, include_historical: bool = False) -> dict:
    """Fetch earnings using Finnhub (fast, 60/min)."""
    print("Using: Finnhub API (60 calls/minute)")
    print(f"Date range: Next {days_ahead} days" + (" + past 365 days" if include_historical else ""))
    print(f"Estimated time: ~{len(symbols) * 1.1 / 60:.1f} minutes")
    print()

    with FinnhubEarnings() as collector:
        return collector.batch_fetch_watchlist(
            symbols,
            days_ahead=days_ahead,
            include_historical=include_historical
        )


def fetch_with_alpha_vantage(symbols: list[str], limit: int = 25) -> dict:
    """Fetch earnings using Alpha Vantage (slow, 25/day)."""
    limited_symbols = symbols[:limit]

    print("Using: Alpha Vantage API (25 calls/day limit)")
    print(f"Fetching {len(limited_symbols)} tickers (limited to {limit})")
    print(f"Estimated time: ~{len(limited_symbols) * 13 // 60} minutes")
    print()

    with AlphaVantageEarnings() as collector:
        return collector.get_multiple_earnings(limited_symbols, delay=13.0)


def main():
    """Fetch earnings dates for watchlist tickers."""
    parser = argparse.ArgumentParser(description="Fetch earnings dates (Finnhub or Alpha Vantage)")
    parser.add_argument(
        "--source",
        choices=["auto", "finnhub", "alphavantage"],
        default="auto",
        help="API source (default: auto-detect)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Max tickers for Alpha Vantage (default: 25)"
    )
    parser.add_argument(
        "--days-ahead",
        type=int,
        default=90,
        help="Days ahead to fetch (default: 90 = ~1 quarter, confirmed dates only)"
    )
    parser.add_argument(
        "--include-historical",
        action="store_true",
        help="Also fetch past year of earnings for backtest validation"
    )
    args = parser.parse_args()

    print("=" * 70)
    print("FETCH EARNINGS DATES")
    print("=" * 70)
    print()

    # Get watchlist symbols
    watchlist = [t.symbol for t in TIER_2_STOCKS]
    print(f"Watchlist: {len(watchlist)} tickers")
    print()

    # Determine which API to use
    has_finnhub = os.getenv("FINNHUB_API_KEY")
    has_alphavantage = os.getenv("ALPHA_VANTAGE_API_KEY")

    if args.source == "auto":
        # Auto-select: Prefer Finnhub (faster)
        if has_finnhub:
            source = "finnhub"
        elif has_alphavantage:
            source = "alphavantage"
        else:
            print("! ERROR: No API keys configured")
            print()
            print("Setup Instructions:")
            print("1. Get FREE API key from:")
            print("   - Finnhub (recommended): https://finnhub.io/register")
            print("   - Alpha Vantage: https://www.alphavantage.co/support/#api-key")
            print()
            print("2. Add to .env file:")
            print("   FINNHUB_API_KEY=your_key_here")
            print("   # OR")
            print("   ALPHA_VANTAGE_API_KEY=your_key_here")
            print()
            return 1
    else:
        source = args.source

    # Fetch earnings
    try:
        if source == "finnhub":
            if not has_finnhub:
                raise ValueError("FINNHUB_API_KEY not configured")
            results = fetch_with_finnhub(
                watchlist,
                days_ahead=args.days_ahead,
                include_historical=args.include_historical
            )

        else:  # alphavantage
            if not has_alphavantage:
                raise ValueError("ALPHA_VANTAGE_API_KEY not configured")
            results = fetch_with_alpha_vantage(watchlist, limit=args.limit)

        print()
        print("=" * 70)
        print(f"RESULTS: Fetched {len(results)} earnings dates")
        print("=" * 70)
        print()

        if results:
            # Convert to list format for database
            earnings_list = []
            for symbol, data in results.items():
                earnings_list.append({
                    "symbol": symbol,
                    "earnings_date": data["report_date"],
                    "fiscal_ending": data.get("fiscal_ending"),
                    "estimate": data.get("estimate"),
                })

            # Save to database
            with MarketDataDB() as db:
                count = db.insert_earnings(earnings_list)
                print(f"OK Saved {count} earnings dates to database")

            # Show upcoming earnings
            print()
            print("UPCOMING EARNINGS (Next 30 Days):")
            print("-" * 70)
            print(f"{'Symbol':<10} {'Earnings Date':<15} {'Days Until':<12} {'Estimate':<10}")
            print("-" * 70)

            # Filter and sort upcoming earnings
            upcoming = []
            for earn in earnings_list:
                symbol_data = results[earn["symbol"]]
                days = symbol_data.get("days_until", 999)

                if days <= 30:
                    upcoming.append({
                        "symbol": earn["symbol"],
                        "date": earn["earnings_date"],
                        "days": days,
                        "estimate": symbol_data.get("estimate", "N/A")
                    })

            upcoming.sort(key=lambda x: x["days"])

            for item in upcoming:
                estimate_str = f"${item['estimate']}" if isinstance(item['estimate'], (int, float)) else item['estimate']

                print(
                    f"{item['symbol']:<10} "
                    f"{item['date']:<15} "
                    f"{item['days']:>2} days      "
                    f"{estimate_str}"
                )

            if not upcoming:
                print("No earnings in next 30 days for fetched tickers")

        else:
            print("! No earnings data fetched")
            print(f"  Check your {source.upper()}_API_KEY in .env file")

    except ValueError as e:
        print(f"! Error: {e}")
        print()
        print("Setup Instructions:")
        print("1. Get free API key:")
        if "FINNHUB" in str(e):
            print("   https://finnhub.io/register")
            print("2. Add to .env file:")
            print("   FINNHUB_API_KEY=your_key_here")
        else:
            print("   https://www.alphavantage.co/support/#api-key")
            print("2. Add to .env file:")
            print("   ALPHA_VANTAGE_API_KEY=your_key_here")
        print()
        return 1

    except Exception as e:
        print(f"! Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print()
    print("=" * 70)
    print("OK Earnings fetch complete!")
    print("=" * 70)
    print()
    print("Next steps:")
    print("  - Run weekly: python scripts/fetch_earnings.py")
    print("  - For backtest: python scripts/fetch_earnings.py --include-historical")
    print("  - Shorter range: python scripts/fetch_earnings.py --days-ahead 60")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
