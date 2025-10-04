"""
Finnhub Earnings Calendar Collector.

Free tier: 60 API calls/minute (MUCH better than Alpha Vantage's 25/day!)
API Docs: https://finnhub.io/docs/api/earnings-calendar
"""

import os
from datetime import datetime, timedelta
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential


class FinnhubEarnings:
    """Collect earnings dates from Finnhub API."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Finnhub earnings collector.

        Args:
            api_key: Finnhub API key (or set FINNHUB_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("FINNHUB_API_KEY")
        if not self.api_key:
            raise ValueError(
                "FINNHUB_API_KEY required. Get free key at: "
                "https://finnhub.io/register"
            )

        self.base_url = "https://finnhub.io/api/v1"
        self.client = httpx.Client(timeout=30)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.client.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def get_earnings_calendar(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> list[dict]:
        """
        Get earnings calendar for a date range or specific symbol.

        Args:
            from_date: Start date (YYYY-MM-DD) - defaults to today
            to_date: End date (YYYY-MM-DD) - defaults to 30 days from now
            symbol: Filter by ticker symbol (optional)

        Returns:
            List of earnings events:
            [
                {
                    "date": "2024-01-25",
                    "epsActual": 2.18,
                    "epsEstimate": 2.10,
                    "hour": "amc",  # bmo=before market, amc=after market, dmh=during market
                    "quarter": 1,
                    "revenueActual": 119575000000,
                    "revenueEstimate": 117910000000,
                    "symbol": "AAPL",
                    "year": 2024
                },
                ...
            ]
        """
        if not from_date:
            from_date = datetime.now().strftime("%Y-%m-%d")

        if not to_date:
            to_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")

        params = {
            "from": from_date,
            "to": to_date,
            "token": self.api_key,
        }

        if symbol:
            params["symbol"] = symbol

        url = f"{self.base_url}/calendar/earnings"
        response = self.client.get(url, params=params)
        response.raise_for_status()

        data = response.json()

        if "error" in data:
            raise Exception(f"API Error: {data['error']}")

        return data.get("earningsCalendar", [])

    def get_next_earnings(self, symbol: str, days_ahead: int = 90) -> Optional[dict]:
        """
        Get next earnings date for a specific symbol.

        Args:
            symbol: Ticker symbol (e.g., "AAPL")
            days_ahead: Days ahead to search (default: 90)

        Returns:
            {
                "symbol": "AAPL",
                "report_date": "2024-01-25",
                "days_until": 5,
                "estimate": 2.10,
                "hour": "amc",
                "quarter": 1,
                "year": 2024
            }
            or None if no upcoming earnings found
        """
        try:
            # Get earnings for specified date range
            to_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
            earnings = self.get_earnings_calendar(symbol=symbol, to_date=to_date)

            if not earnings:
                return None

            # Find next upcoming earnings
            today = datetime.now().date()
            upcoming = []

            for event in earnings:
                try:
                    report_date_str = event.get("date", "")
                    if not report_date_str:
                        continue

                    report_date = datetime.strptime(report_date_str, "%Y-%m-%d").date()

                    if report_date >= today:
                        days_until = (report_date - today).days
                        upcoming.append({
                            "symbol": symbol,
                            "report_date": report_date_str,
                            "days_until": days_until,
                            "estimate": event.get("epsEstimate"),
                            "hour": event.get("hour", "unknown"),
                            "quarter": event.get("quarter"),
                            "year": event.get("year"),
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

    def get_multiple_earnings(
        self,
        symbols: list[str],
        delay: float = 1.1,
        days_ahead: int = 90,
        include_historical: bool = False
    ) -> dict[str, dict]:
        """
        Get earnings for multiple symbols (rate-limited for free tier).

        Args:
            symbols: List of ticker symbols
            delay: Delay between requests in seconds (default: 1.1s for 60/min limit)
            days_ahead: Days ahead to fetch (default: 90)
            include_historical: Also fetch past 365 days

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
                earnings = self.get_next_earnings(symbol, days_ahead=days_ahead)
                if earnings:
                    results[symbol] = earnings

                # If include_historical, also fetch past earnings (for backtesting)
                if include_historical:
                    # Store historical separately to avoid overwriting
                    pass  # TODO: Implement if needed for backtest

                # Rate limiting - free tier allows 60 requests/minute
                # Use 1.1 second delay to be safe (54 calls/minute)
                if i < len(symbols) - 1:
                    time.sleep(delay)

            except Exception as e:
                print(f"  [{symbol}] Error: {e}")
                continue

        return results

    def batch_fetch_watchlist(
        self,
        symbols: list[str],
        days_ahead: int = 90,
        include_historical: bool = False
    ) -> dict[str, dict]:
        """
        Fetch earnings for entire watchlist (Finnhub free tier is generous!).

        Free tier: 60 calls/minute
        Can fetch ~62 tickers in ~70 seconds

        Args:
            symbols: List of ticker symbols
            days_ahead: Days ahead to fetch (default: 90 = ~1 quarter)
            include_historical: Also fetch past 365 days for backtesting

        Returns:
            Dict of symbol -> earnings info
        """
        print(f"\nFetching earnings for {len(symbols)} tickers from Finnhub")
        print(f"Date range: Next {days_ahead} days" + (" + past 365 days" if include_historical else ""))
        print(f"Rate limit: 60 calls/minute (much better than Alpha Vantage!)")
        print(f"Estimated time: ~{len(symbols) * 1.1 / 60:.1f} minutes\n")

        return self.get_multiple_earnings(
            symbols,
            delay=1.1,
            days_ahead=days_ahead,
            include_historical=include_historical
        )
