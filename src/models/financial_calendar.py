"""
Financial Calendar - Track market-wide and stock-specific events.

Provides:
- FOMC meeting dates (hardcoded annual schedule)
- Major economic releases (CPI, NFP, GDP)
- Event risk assessment for trading decisions
"""

from datetime import datetime, date, timedelta
from enum import Enum
from typing import Literal


class EventImpact(Enum):
    """Impact level of calendar events on market."""
    EXTREME = "EXTREME"  # Avoid all trading (FOMC)
    HIGH = "HIGH"        # Avoid new positions (CPI, NFP)
    MEDIUM = "MEDIUM"    # Be cautious (Retail Sales)
    LOW = "LOW"          # Monitor only


class EventType(Enum):
    """Type of calendar event."""
    FOMC = "FOMC"
    CPI = "CPI"
    NFP = "NFP"
    GDP = "GDP"
    PCE = "PCE"
    RETAIL_SALES = "RETAIL_SALES"
    EARNINGS = "EARNINGS"
    JOBLESS_CLAIMS = "JOBLESS_CLAIMS"


class FinancialCalendar:
    """
    Financial calendar for avoiding trading around major events.

    High-impact events can cause:
    - Gap openings
    - Increased volatility
    - Invalidated technical signals
    - Stop loss hunting
    """

    # 2025 FOMC Meeting Dates (from federalreserve.gov)
    # Format: (year, month, day)
    FOMC_DATES_2025 = [
        (2025, 1, 29),   # January
        (2025, 3, 19),   # March
        (2025, 5, 7),    # May
        (2025, 6, 18),   # June
        (2025, 7, 30),   # July
        (2025, 9, 17),   # September
        (2025, 10, 29),  # October
        (2025, 12, 10),  # December
    ]

    # 2026 FOMC Dates (update when published)
    FOMC_DATES_2026 = [
        (2026, 1, 28),
        (2026, 3, 18),
        (2026, 4, 29),
        (2026, 6, 17),
        (2026, 7, 29),
        (2026, 9, 16),
        (2026, 11, 4),
        (2026, 12, 16),
    ]

    @staticmethod
    def get_fomc_dates(year: int) -> list[date]:
        """Get FOMC meeting dates for given year."""
        if year == 2025:
            return [date(*d) for d in FinancialCalendar.FOMC_DATES_2025]
        elif year == 2026:
            return [date(*d) for d in FinancialCalendar.FOMC_DATES_2026]
        else:
            return []

    @staticmethod
    def get_next_cpi_date(from_date: date | None = None) -> date:
        """
        CPI is released around 13th of each month for previous month's data.

        Actual dates vary slightly, but typically:
        - 2nd Tuesday or Wednesday of the month
        - Around 8:30 AM ET
        """
        if from_date is None:
            from_date = date.today()

        # Start with next month
        if from_date.day >= 13:
            next_month = from_date.month + 1
            next_year = from_date.year
            if next_month > 12:
                next_month = 1
                next_year += 1
        else:
            next_month = from_date.month
            next_year = from_date.year

        # CPI typically on 13th (adjust to nearest weekday if weekend)
        cpi_date = date(next_year, next_month, 13)

        # If weekend, move to Tuesday
        if cpi_date.weekday() == 5:  # Saturday
            cpi_date += timedelta(days=2)
        elif cpi_date.weekday() == 6:  # Sunday
            cpi_date += timedelta(days=1)

        return cpi_date

    @staticmethod
    def get_next_nfp_date(from_date: date | None = None) -> date:
        """
        NFP (Nonfarm Payrolls) is first Friday of each month.
        Released at 8:30 AM ET.
        """
        if from_date is None:
            from_date = date.today()

        # Start with next month
        next_month = from_date.month + 1
        next_year = from_date.year
        if next_month > 12:
            next_month = 1
            next_year += 1

        # Find first Friday of next month
        first_day = date(next_year, next_month, 1)
        days_until_friday = (4 - first_day.weekday()) % 7
        if days_until_friday == 0 and first_day.weekday() != 4:
            days_until_friday = 7

        nfp_date = first_day + timedelta(days=days_until_friday)

        # If somehow we're past NFP this month, try this month's first Friday
        if from_date.month == next_month and from_date > nfp_date:
            return FinancialCalendar.get_next_nfp_date(nfp_date)

        return nfp_date

    @staticmethod
    def check_event_proximity(
        target_date: date | None = None,
        lookback_days: int = 1,
        lookahead_days: int = 0,
    ) -> dict:
        """
        Check if target_date is near any major market events.

        Args:
            target_date: Date to check (default: today)
            lookback_days: How many days BEFORE event to avoid (default: 1)
            lookahead_days: How many days AFTER event to avoid (default: 0)

        Returns:
            {
                "has_event": bool,
                "event_type": EventType or None,
                "event_date": date or None,
                "days_until": int,
                "impact": EventImpact,
                "recommendation": str,
                "confidence_adjustment": float  # -0.30 to 0.0
            }
        """
        if target_date is None:
            target_date = date.today()

        # Convert datetime to date if needed
        if isinstance(target_date, datetime):
            target_date = target_date.date()

        # Check FOMC (highest impact)
        fomc_dates = FinancialCalendar.get_fomc_dates(target_date.year)
        for fomc_date in fomc_dates:
            days_diff = (fomc_date - target_date).days

            # Check if within danger window
            if -lookahead_days <= days_diff <= lookback_days:
                return {
                    "has_event": True,
                    "event_type": EventType.FOMC,
                    "event_date": fomc_date,
                    "days_until": days_diff,
                    "impact": EventImpact.EXTREME,
                    "recommendation": "AVOID ALL TRADING - Wait for FOMC decision and market reaction",
                    "confidence_adjustment": -0.30,  # Kill confidence
                }

        # Check CPI (high impact)
        next_cpi = FinancialCalendar.get_next_cpi_date(target_date)
        days_until_cpi = (next_cpi - target_date).days

        if -lookahead_days <= days_until_cpi <= lookback_days:
            return {
                "has_event": True,
                "event_type": EventType.CPI,
                "event_date": next_cpi,
                "days_until": days_until_cpi,
                "impact": EventImpact.HIGH,
                "recommendation": "AVOID NEW POSITIONS - High volatility expected",
                "confidence_adjustment": -0.20,
            }

        # Check NFP (high impact)
        next_nfp = FinancialCalendar.get_next_nfp_date(target_date)
        days_until_nfp = (next_nfp - target_date).days

        if -lookahead_days <= days_until_nfp <= lookback_days:
            return {
                "has_event": True,
                "event_type": EventType.NFP,
                "event_date": next_nfp,
                "days_until": days_until_nfp,
                "impact": EventImpact.HIGH,
                "recommendation": "AVOID NEW POSITIONS - Jobs report volatility",
                "confidence_adjustment": -0.20,
            }

        # No major events nearby
        return {
            "has_event": False,
            "event_type": None,
            "event_date": None,
            "days_until": None,
            "impact": EventImpact.LOW,
            "recommendation": "CLEAR - No major events nearby",
            "confidence_adjustment": 0.0,
        }

    @staticmethod
    def get_upcoming_events(days_ahead: int = 14) -> list[dict]:
        """
        Get all upcoming events in next N days.

        Returns list of event dicts sorted by date.
        """
        today = date.today()
        end_date = today + timedelta(days=days_ahead)

        events = []

        # Add FOMC dates
        fomc_dates = FinancialCalendar.get_fomc_dates(today.year)
        for fomc_date in fomc_dates:
            if today <= fomc_date <= end_date:
                events.append({
                    "date": fomc_date,
                    "type": EventType.FOMC,
                    "name": "FOMC Meeting",
                    "impact": EventImpact.EXTREME,
                    "days_until": (fomc_date - today).days,
                })

        # Add CPI
        next_cpi = FinancialCalendar.get_next_cpi_date(today)
        if today <= next_cpi <= end_date:
            events.append({
                "date": next_cpi,
                "type": EventType.CPI,
                "name": "CPI Release",
                "impact": EventImpact.HIGH,
                "days_until": (next_cpi - today).days,
            })

        # Add NFP
        next_nfp = FinancialCalendar.get_next_nfp_date(today)
        if today <= next_nfp <= end_date:
            events.append({
                "date": next_nfp,
                "type": EventType.NFP,
                "name": "Jobs Report (NFP)",
                "impact": EventImpact.HIGH,
                "days_until": (next_nfp - today).days,
            })

        # Sort by date
        events.sort(key=lambda x: x["date"])

        return events
