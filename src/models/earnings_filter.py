"""Earnings proximity filter - Avoid trading around earnings announcements."""

from datetime import datetime


class EarningsFilter:
    """Filter trades based on proximity to earnings announcements."""

    @staticmethod
    def check_earnings_proximity(days_until_earnings: int | None) -> dict:
        """
        Adjust confidence based on earnings proximity.

        Args:
            days_until_earnings: Days until earnings (negative = after earnings)

        Returns:
            {
                "action": "ALLOW" | "BLOCK" | "CAUTION",
                "confidence_adjustment": float (-0.20 to +0.10),
                "reasoning": str,
                "position_size_modifier": float (0.5 to 1.5)
            }

        Rules:
            Before Earnings:
                - 0-2 days: BLOCK (too risky - earnings surprise)
                - 3-5 days: -20% confidence (very elevated risk)
                - 6-10 days: -10% confidence (elevated risk)
                - 11-21 days: -5% confidence (minor risk)
                - > 21 days: No adjustment

            After Earnings:
                - 1 day after: +10% confidence (earnings relief rally opportunity)
                - 2-3 days after: +5% confidence (post-earnings momentum)
                - > 3 days after: No adjustment
        """
        if days_until_earnings is None:
            return {
                "action": "ALLOW",
                "confidence_adjustment": 0.0,
                "reasoning": "No earnings data available",
                "position_size_modifier": 1.0,
            }

        # After earnings (negative values)
        if days_until_earnings < 0:
            days_after = abs(days_until_earnings)

            if days_after == 1:
                return {
                    "action": "ALLOW",
                    "confidence_adjustment": +0.10,
                    "reasoning": f"1 day after earnings - potential relief rally",
                    "position_size_modifier": 1.2,  # Slightly larger positions
                }
            elif 2 <= days_after <= 3:
                return {
                    "action": "ALLOW",
                    "confidence_adjustment": +0.05,
                    "reasoning": f"{days_after} days after earnings - post-earnings momentum",
                    "position_size_modifier": 1.1,
                }
            else:
                return {
                    "action": "ALLOW",
                    "confidence_adjustment": 0.0,
                    "reasoning": f"{days_after} days after earnings - normal conditions",
                    "position_size_modifier": 1.0,
                }

        # Before earnings (positive values)
        if days_until_earnings == 0:
            return {
                "action": "BLOCK",
                "confidence_adjustment": -999.0,  # Effective block
                "reasoning": "Earnings TODAY - extreme risk, avoid trading",
                "position_size_modifier": 0.0,
            }
        elif days_until_earnings <= 2:
            return {
                "action": "BLOCK",
                "confidence_adjustment": -999.0,
                "reasoning": f"{days_until_earnings} days until earnings - too risky",
                "position_size_modifier": 0.0,
            }
        elif days_until_earnings <= 5:
            return {
                "action": "CAUTION",
                "confidence_adjustment": -0.20,
                "reasoning": f"{days_until_earnings} days until earnings - high risk window",
                "position_size_modifier": 0.5,  # Half-size positions only
            }
        elif days_until_earnings <= 10:
            return {
                "action": "CAUTION",
                "confidence_adjustment": -0.10,
                "reasoning": f"{days_until_earnings} days until earnings - elevated risk",
                "position_size_modifier": 0.7,
            }
        elif days_until_earnings <= 21:
            return {
                "action": "ALLOW",
                "confidence_adjustment": -0.05,
                "reasoning": f"{days_until_earnings} days until earnings - minor risk",
                "position_size_modifier": 0.9,
            }
        else:
            return {
                "action": "ALLOW",
                "confidence_adjustment": 0.0,
                "reasoning": f"{days_until_earnings} days until earnings - normal conditions",
                "position_size_modifier": 1.0,
            }

    @staticmethod
    def get_earnings_window_description(days_until_earnings: int | None) -> str:
        """
        Get human-readable description of earnings timing.

        Args:
            days_until_earnings: Days until earnings (negative = after)

        Returns:
            Description string for display
        """
        if days_until_earnings is None:
            return "Unknown"

        if days_until_earnings < 0:
            days_after = abs(days_until_earnings)
            if days_after == 1:
                return "1 day after earnings ✓"
            else:
                return f"{days_after} days after earnings"
        elif days_until_earnings == 0:
            return "EARNINGS TODAY ⚠️"
        elif days_until_earnings <= 2:
            return f"{days_until_earnings} days to earnings ⚠️ DANGER ZONE"
        elif days_until_earnings <= 5:
            return f"{days_until_earnings} days to earnings ⚠️ HIGH RISK"
        elif days_until_earnings <= 10:
            return f"{days_until_earnings} days to earnings ⚡ CAUTION"
        else:
            return f"{days_until_earnings} days to earnings"

    @staticmethod
    def is_earnings_safe_zone(days_until_earnings: int | None) -> bool:
        """
        Quick check if it's safe to trade (earnings > 10 days away or 4+ days after).

        Args:
            days_until_earnings: Days until earnings

        Returns:
            True if safe to trade, False if in danger zone
        """
        if days_until_earnings is None:
            return True  # Unknown = assume safe

        if days_until_earnings < 0:
            # After earnings - safe after 4+ days
            return abs(days_until_earnings) >= 4

        # Before earnings - safe if 11+ days away
        return days_until_earnings > 10
