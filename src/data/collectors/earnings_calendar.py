"""Earnings calendar collector using Polygon API."""

import os
from datetime import datetime, timedelta
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential


class EarningsCalendar:
    """Collect earnings dates from Polygon."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("POLYGON_API_KEY")
        if not self.api_key:
            raise ValueError("POLYGON_API_KEY required")

        self.base_url = "https://api.polygon.io"
        self.client = httpx.Client(timeout=30)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.client.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def get_next_earnings(self, ticker: str) -> Optional[dict]:
        """
        Get next earnings date for a ticker.

        Returns:
            {
                "ticker": "AAPL",
                "fiscal_quarter": "Q1",
                "fiscal_year": 2024,
                "report_date": "2024-01-25",
                "days_until": 5
            }
        """
        url = f"{self.base_url}/vX/reference/financials"
        params = {
            "ticker": ticker,
            "limit": 1,
            "sort": "period_of_report_date",
            "order": "desc",
            "apiKey": self.api_key,
        }

        response = self.client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        if not data.get("results"):
            return None

        # Polygon doesn't directly give earnings dates, but we can estimate
        # Most companies report earnings 1-2 weeks after quarter end
        latest = data["results"][0]

        # Try to get actual earnings date from company facts endpoint
        try:
            url_facts = f"{self.base_url}/v3/reference/tickers/{ticker}"
            params_facts = {"apiKey": self.api_key}

            response_facts = self.client.get(url_facts, params=params_facts)
            response_facts.raise_for_status()
            facts_data = response_facts.json()

            # Polygon doesn't have earnings calendar in free tier
            # We'll need to use a different approach
            return self._estimate_earnings_from_quarter(ticker, latest)

        except Exception:
            return self._estimate_earnings_from_quarter(ticker, latest)

    def _estimate_earnings_from_quarter(self, ticker: str, financial_data: dict) -> Optional[dict]:
        """
        Estimate next earnings based on quarterly pattern.

        Most companies report:
        - Q1 (Jan-Mar): Mid-April to early May
        - Q2 (Apr-Jun): Mid-July to early August
        - Q3 (Jul-Sep): Mid-October to early November
        - Q4 (Oct-Dec): Mid-January to early February
        """
        # This is a simplified version - in production you'd want actual earnings dates
        # For now, return None (we'll add a better source later)
        return None

    def days_until_earnings(self, ticker: str) -> Optional[int]:
        """
        Calculate days until next earnings.

        Returns:
            Number of days until next earnings, or None if unknown
        """
        earnings = self.get_next_earnings(ticker)
        if not earnings:
            return None

        report_date = datetime.fromisoformat(earnings["report_date"])
        today = datetime.now()
        days = (report_date - today).days

        return max(0, days)


# For now, use a simple earnings calendar based on typical patterns
# In production, you'd subscribe to an earnings calendar API
class SimpleEarningsCalendar:
    """
    Simple earnings calendar using quarterly patterns.

    This is a placeholder - ideally you'd use:
    - Alpha Vantage Earnings Calendar (free)
    - FMP Earnings Calendar
    - Nasdaq Earnings Calendar scraper
    """

    EARNINGS_CACHE = {}  # Cache earnings dates

    @staticmethod
    def is_earnings_week(ticker: str, date: datetime) -> bool:
        """
        Check if given date is within 3 days of earnings.

        Returns:
            True if within earnings week (avoid trading)
        """
        # This is a simplified check
        # In production, fetch actual earnings calendar

        # For now, assume earnings happen:
        # - Mid-quarter months (Jan, Apr, Jul, Oct)
        # - Around days 15-25 of the month

        month = date.month
        day = date.day

        # Earnings months (typically)
        earnings_months = [1, 4, 7, 10]  # Jan, Apr, Jul, Oct

        if month in earnings_months and 12 <= day <= 28:
            return True  # Likely earnings week

        return False

    @staticmethod
    def days_until_next_earnings(ticker: str, current_date: datetime) -> Optional[int]:
        """
        Estimate days until next earnings.

        Returns:
            Estimated days, or None if not near earnings
        """
        # Convert to datetime if date object
        if hasattr(current_date, 'date'):
            # It's a datetime, convert to date for comparison
            current_dt = current_date
        else:
            # It's a date, convert to datetime
            from datetime import time
            current_dt = datetime.combine(current_date, time.min)

        # Simple quarterly pattern
        current_month = current_dt.month
        current_day = current_dt.day

        earnings_months = [1, 4, 7, 10]

        # Find next earnings month
        next_earnings_month = None
        for month in earnings_months:
            if month > current_month or (month == current_month and current_day < 15):
                next_earnings_month = month
                break

        if not next_earnings_month:
            next_earnings_month = earnings_months[0]  # Wrap to next year

        # Estimate earnings date (15th of earnings month)
        if next_earnings_month > current_month:
            earnings_date = datetime(current_dt.year, next_earnings_month, 15)
        else:
            earnings_date = datetime(current_dt.year + 1, next_earnings_month, 15)

        days = (earnings_date - current_dt).days

        return days if days < 45 else None  # Only return if within ~6 weeks
