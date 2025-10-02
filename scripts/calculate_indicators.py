"""Calculate technical indicators for stored price data."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analysis.indicators import TechnicalIndicators
from src.config.tickers import TICKER_SYMBOLS
from src.data.storage.market_data_db import MarketDataDB

# Use configured tickers
DEFAULT_TICKERS = TICKER_SYMBOLS


def calculate_and_store_indicators(tickers: list[str]) -> None:
    """
    Calculate technical indicators and store in database.

    Args:
        tickers: List of ticker symbols
    """
    print(f"\n{'='*60}")
    print(f"Calculating Technical Indicators for {len(tickers)} tickers")
    print(f"{'='*60}\n")

    with TechnicalIndicators() as calc:
        total_records = 0

        for ticker in tickers:
            try:
                print(f"[{ticker}] Calculating indicators...", end=" ")

                # Calculate all indicators
                indicators = calc.calculate_all_indicators(ticker)

                if not indicators.empty:
                    # Store in database
                    count = calc.db.insert_indicators(ticker, indicators)
                    total_records += count
                    print(f"✓ {count} records")
                else:
                    print("⚠ No data available")

            except Exception as e:
                print(f"✗ Error: {e}")

        print(f"\n{'='*60}")
        print(f"✓ Indicators calculation complete:")
        print(f"  Total records stored: {total_records:,}")
        print(f"{'='*60}\n")


def show_indicator_examples(symbol: str = "SPY") -> None:
    """
    Display example indicator calculations for a symbol.

    Args:
        symbol: Stock symbol to display (default SPY)
    """
    print(f"\n{'='*60}")
    print(f"Technical Indicators Example: {symbol}")
    print(f"{'='*60}\n")

    with TechnicalIndicators() as calc:
        # Get all indicators
        indicators = calc.calculate_all_indicators(symbol)

        if indicators.empty:
            print(f"⚠ No data available for {symbol}")
            return

        # Show latest 10 rows
        print("Latest 10 Days:\n")
        print(indicators[
            [
                "close",
                "sma_20",
                "sma_50",
                "rsi_14",
                "macd",
                "signal",
                "histogram",
            ]
        ].tail(10).to_string())

        # Show current values
        latest = indicators.iloc[-1]
        print(f"\n\nCurrent Indicators ({latest.name.date()}):")
        print(f"{'='*60}")
        print(f"  Price (Close):     ${latest['close']:.2f}")
        print(f"\n  Moving Averages:")
        print(f"    SMA 20:          ${latest['sma_20']:.2f}")
        print(f"    SMA 50:          ${latest['sma_50']:.2f}")
        print(f"    SMA 200:         ${latest['sma_200']:.2f}")
        print(f"    EMA 12:          ${latest['ema_12']:.2f}")
        print(f"    EMA 26:          ${latest['ema_26']:.2f}")
        print(f"\n  Momentum Indicators:")
        print(f"    RSI (14):        {latest['rsi_14']:.2f}")
        print(f"    MACD:            {latest['macd']:.4f}")
        print(f"    MACD Signal:     {latest['signal']:.4f}")
        print(f"    MACD Histogram:  {latest['histogram']:.4f}")
        print(f"\n  Bollinger Bands:")
        print(f"    Upper:           ${latest['upper']:.2f}")
        print(f"    Middle:          ${latest['middle']:.2f}")
        print(f"    Lower:           ${latest['lower']:.2f}")
        print(f"\n  Volatility:")
        print(f"    ATR (14):        ${latest['atr_14']:.2f}")
        print(f"\n  Stochastic:")
        print(f"    %K:              {latest['k']:.2f}")
        print(f"    %D:              {latest['d']:.2f}")
        print(f"\n  Volume:")
        print(f"    OBV:             {latest['obv']:,.0f}")

        # Trading signals
        print(f"\n\n{'='*60}")
        print("Trading Signals:")
        print(f"{'='*60}")

        # Trend
        if latest['close'] > latest['sma_50'] > latest['sma_200']:
            print("  📈 Uptrend: Price > SMA50 > SMA200")
        elif latest['close'] < latest['sma_50'] < latest['sma_200']:
            print("  📉 Downtrend: Price < SMA50 < SMA200")
        else:
            print("  ➡️  Mixed trend")

        # RSI
        if latest['rsi_14'] > 70:
            print("  ⚠️  RSI Overbought (>70)")
        elif latest['rsi_14'] < 30:
            print("  ⚠️  RSI Oversold (<30)")
        else:
            print(f"  ✓ RSI Neutral ({latest['rsi_14']:.1f})")

        # MACD
        if latest['macd'] > latest['signal']:
            print("  ✓ MACD Bullish (MACD > Signal)")
        else:
            print("  ⚠️  MACD Bearish (MACD < Signal)")

        # Bollinger Bands
        bb_position = (
            (latest['close'] - latest['lower']) / (latest['upper'] - latest['lower'])
        ) * 100
        print(f"  📊 Bollinger Band Position: {bb_position:.1f}%")

        print(f"{'='*60}\n")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Calculate technical indicators")
    parser.add_argument(
        "--tickers",
        type=str,
        help="Comma-separated list of tickers (default: major ETFs)",
    )
    parser.add_argument(
        "--example",
        type=str,
        help="Show indicator examples for a specific ticker",
    )
    parser.add_argument(
        "--store",
        action="store_true",
        help="Calculate and store indicators in database",
    )

    args = parser.parse_args()

    # Show example
    if args.example:
        show_indicator_examples(args.example)
        return

    # Calculate and store
    if args.store or not args.example:
        if args.tickers:
            tickers = args.tickers.split(",")
            print(f"\nUsing custom tickers: {', '.join(tickers)}")
        else:
            tickers = DEFAULT_TICKERS
            print(f"\nUsing default {len(tickers)} major ETFs/indices")

        calculate_and_store_indicators(tickers)

    # Always show example at the end
    if args.store:
        print("\n" + "="*60)
        print("Quick Preview:")
        print("="*60)
        show_indicator_examples("SPY")


if __name__ == "__main__":
    main()
