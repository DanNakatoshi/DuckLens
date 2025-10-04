"""
Alpha Vantage Earnings Calendar Collector.

Free tier: 25 API calls/day
API Docs: https://www.alphavantage.co/documentation/#earnings-calendar
"""

import os
from datetime import datetime, timedelta
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential


class AlphaVantageEarnings:
    """Collect earnings dates from Alpha Vantage API."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Alpha Vantage earnings collector.

        Args:
            api_key: Alpha Vantage API key (or set ALPHA_VANTAGE_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("ALPHA_VANTAGE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ALPHA_VANTAGE_API_KEY required. Get free key at: "
                "https://www.alphavantage.co/support/#api-key"
            )

        self.base_url = "https://www.alphavantage.co/query"
        self.client = httpx.Client(timeout=30)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.client.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def get_earnings_calendar(self, symbol: Optional[str] = None, horizon: str = "3month") -> list[dict]:
        """
        Get earnings calendar for symbol or all upcoming earnings.

        Args:
            symbol: Ticker symbol (optional - if None, gets all upcoming earnings)
            horizon: Time horizon - "3month" (default), "6month", or "12month"

        Returns:
            List of earnings events:
            [
                {
                    "symbol": "AAPL",
                    "name": "Apple Inc",
                    "reportDate": "2024-01-25",
                    "fiscalDateEnding": "2023-12-31",
                    "estimate": "2.10",
                    "currency": "USD"
                },
                ...
            ]
        """
        params = {
            "function": "EARNINGS_CALENDAR",
            "horizon": horizon,
            "apikey": self.api_key,
        }

        if symbol:
            params["symbol"] = symbol

        response = self.client.get(self.base_url, params=params)
        response.raise_for_status()

        # Alpha Vantage returns CSV for earnings calendar
        csv_data = response.text

        if "Error Message" in csv_data or "Invalid API call" in csv_data:
            raise Exception(f"API Error: {csv_data[:200]}")

        # Parse CSV
        earnings = []
        lines = csv_data.strip().split("\n")

        if len(lines) < 2:
            return []

        headers = lines[0].split(",")

        for line in lines[1:]:
            values = line.split(",")
            if len(values) >= len(headers):
                event = dict(zip(headers, values))
                earnings.append(event)

        return earnings

    def get_next_earnings(self, symbol: str) -> Optional[dict]:
        """
        Get next earnings date for a specific symbol.

        Args:
            symbol: Ticker symbol (e.g., "AAPL")

        Returns:
            {
                "symbol": "AAPL",
                "report_date": "2024-01-25",
                "days_until": 5,
                "fiscal_ending": "2023-12-31",
                "estimate": "2.10"
            }
            or None if no upcoming earnings found
        """
        try:
            all_earnings = self.get_earnings_calendar(symbol=symbol, horizon="3month")

            if not all_earnings:
                return None

            # Find next upcoming earnings (report date in future)
            today = datetime.now().date()
            upcoming = []

            for event in all_earnings:
                try:
                    report_date_str = event.get("reportDate", "")
                    if not report_date_str:
                        continue

                    report_date = datetime.strptime(report_date_str, "%Y-%m-%d").date()

                    if report_date >= today:
                        days_until = (report_date - today).days
                        upcoming.append({
                            "symbol": symbol,
                            "report_date": report_date_str,
                            "days_until": days_until,
                            "fiscal_ending": event.get("fiscalDateEnding", ""),
                            "estimate": event.get("estimate", ""),
                        })
                except (ValueError, KeyError):
                    continue

            if not upcoming:
                return None

            # Return the soonest earnings
            return min(upcoming, key=lambda x: x["days_until"])

        except Exception as e:
            print(f"Warning: Could not fetch earnings for {symbol}: {e}")
            return None

    def get_multiple_earnings(self, symbols: list[str], delay: float = 13.0) -> dict[str, dict]:
        """
        Get earnings for multiple symbols (rate-limited for free tier).

        Args:
            symbols: List of ticker symbols
            delay: Delay between requests in seconds (default: 13s for 25 calls/day)

        Returns:
            Dict of symbol -> earnings info
            {
                "AAPL": {"report_date": "2024-01-25", "days_until": 5, ...},
                "GOOGL": {"report_date": "2024-02-01", "days_until": 12, ...},
                ...
            }
        """
        import time

        results = {}

        for i, symbol in enumerate(symbols):
            try:
                earnings = self.get_next_earnings(symbol)
                if earnings:
                    results[symbol] = earnings

                # Rate limiting - free tier allows ~5 requests/minute
                # To be safe: 25 calls/day = ~13 seconds between calls
                if i < len(symbols) - 1:
                    print(f"  [{symbol}] OK - waiting {delay}s for rate limit...")
                    time.sleep(delay)
                else:
                    print(f"  [{symbol}] OK")

            except Exception as e:
                print(f"  [{symbol}] Error: {e}")
                continue

        return results

    def batch_fetch_watchlist(self, symbols: list[str], batch_size: int = 20) -> dict[str, dict]:
        """
        Fetch earnings for watchlist in batches (respects daily limit).

        Free tier: 25 calls/day
        Recommended: Fetch 20 tickers per day, save 5 calls for other uses

        Args:
            symbols: List of ticker symbols
            batch_size: Max tickers to fetch per run (default: 20)

        Returns:
            Dict of symbol -> earnings info
        """
        limited_symbols = symbols[:batch_size]

        print(f"\nFetching earnings for {len(limited_symbols)} tickers")
        print(f"(Limited to {batch_size} per day for free tier)")
        print("This will take ~4-5 minutes with rate limiting...\n")

        return self.get_multiple_earnings(limited_symbols, delay=13.0)
