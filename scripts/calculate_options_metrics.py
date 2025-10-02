"""
Calculate options flow indicators for CatBoost feature engineering.

This script processes raw options flow data and calculates derived metrics
like P/C ratio moving averages, smart money index, IV rank, etc.

Usage:
    python scripts/calculate_options_metrics.py [--ticker TICKER] [--days DAYS]
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
from dotenv import load_dotenv

load_dotenv()

from src.analysis.options_indicators import OptionsFlowAnalyzer
from src.config.tickers import TICKER_SYMBOLS
from src.data.storage.market_data_db import MarketDataDB


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Calculate options flow indicators for CatBoost"
    )
    parser.add_argument(
        "--ticker", type=str, help="Specific ticker to calculate (default: all tickers)"
    )
    parser.add_argument(
        "--days",
        type=int,
        help="Number of days to process (default: all available data)",
    )
    parser.add_argument(
        "--start-date", type=str, help="Start date in YYYY-MM-DD format"
    )
    parser.add_argument(
        "--end-date", type=str, help="End date in YYYY-MM-DD format (default: today)"
    )
    parser.add_argument(
        "--show-signals",
        action="store_true",
        help="Display flow signals after calculation",
    )
    return parser.parse_args()


def calculate_indicators(
    tickers: list[str],
    start_date: datetime | None,
    end_date: datetime | None,
    show_signals: bool = False,
) -> None:
    """
    Calculate options indicators for tickers.

    Args:
        tickers: List of ticker symbols
        start_date: Start date for calculation
        end_date: End date for calculation
        show_signals: Whether to display flow signals
    """
    print("📊 Options Flow Indicators Calculator")
    print("=" * 60)
    print(f"Tickers: {len(tickers)}")
    if start_date:
        print(f"Start date: {start_date.date()}")
    if end_date:
        print(f"End date: {end_date.date()}")
    print("=" * 60)

    with MarketDataDB() as db, OptionsFlowAnalyzer(db) as analyzer:
        total_indicators = 0
        ticker_summaries = []

        for ticker_idx, ticker in enumerate(tickers, 1):
            print(f"\n[{ticker_idx}/{len(tickers)}] {ticker}...", end=" ", flush=True)

            try:
                # Calculate indicators
                indicators = analyzer.calculate_all_indicators(
                    ticker=ticker, start_date=start_date, end_date=end_date
                )

                if not indicators:
                    print("No flow data available")
                    continue

                # Store in database
                count = db.insert_options_flow_indicators(indicators)
                total_indicators += count

                # Get latest signal for summary
                latest = indicators[-1]
                ticker_summaries.append(
                    {
                        "ticker": ticker,
                        "date": latest.date,
                        "signal": latest.flow_signal,
                        "pc_ratio": float(latest.put_call_ratio),
                        "unusual": float(latest.unusual_activity_score),
                        "iv_rank": float(latest.iv_rank) if latest.iv_rank else None,
                    }
                )

                print(f"✓ {count} indicators calculated")

            except Exception as e:
                print(f"✗ Error: {str(e)[:40]}")
                continue

        # Print summary
        print(f"\n{'=' * 60}")
        print(f"✅ Calculation Complete")
        print(f"\n📈 Total indicators calculated: {total_indicators:,}")

        if show_signals and ticker_summaries:
            print(f"\n📊 Latest Flow Signals:")
            print(f"\n{'Ticker':<8} {'Date':<12} {'Signal':<10} {'P/C':<8} {'Unusual':<10} {'IV Rank'}")
            print("-" * 70)

            # Sort by signal (BULLISH first)
            ticker_summaries.sort(key=lambda x: (x["signal"] != "BULLISH", x["ticker"]))

            for summary in ticker_summaries:
                pc_str = f"{summary['pc_ratio']:.2f}"
                unusual_str = f"{summary['unusual']:.0f}"
                iv_rank_str = f"{summary['iv_rank']:.0f}" if summary["iv_rank"] else "N/A"

                # Color-code signals
                signal = summary["signal"]
                if signal == "BULLISH":
                    signal_str = f"{signal} 📈"
                elif signal == "BEARISH":
                    signal_str = f"{signal} 📉"
                else:
                    signal_str = f"{signal} ➡️"

                print(
                    f"{summary['ticker']:<8} {summary['date']!s:<12} {signal_str:<13} "
                    f"{pc_str:<8} {unusual_str:<10} {iv_rank_str}"
                )

        print(f"\n{'=' * 60}")
        print("✓ Done!")
        print("=" * 60)


def main():
    """Main entry point."""
    args = parse_args()

    # Determine date range
    end_date = None
    if args.end_date:
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d")

    start_date = None
    if args.start_date:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
    elif args.days:
        end_date = end_date or datetime.now()
        start_date = end_date - timedelta(days=args.days)

    # Determine tickers
    if args.ticker:
        tickers = [args.ticker.upper()]
    else:
        tickers = TICKER_SYMBOLS

    # Calculate indicators
    calculate_indicators(tickers, start_date, end_date, args.show_signals)


if __name__ == "__main__":
    main()
