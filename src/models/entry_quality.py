"""Entry quality scoring based on support/resistance positioning."""


class EntryQualityScorer:
    """Score entry quality based on price position relative to support/resistance."""

    @staticmethod
    def score_entry(
        current_price: float, support: float, resistance: float
    ) -> dict:
        """
        Score entry quality based on support/resistance positioning.

        Args:
            current_price: Current stock price
            support: Support level (recent lows)
            resistance: Resistance level (recent highs)

        Returns:
            {
                "quality": str,  # "EXCELLENT", "GOOD", "FAIR", "POOR"
                "confidence_adjustment": float,  # -0.20 to +0.20
                "position_in_range": float,  # 0.0 to 1.0
                "risk_reward_quality": float,  # Risk/reward based on positioning
                "reasoning": str
            }

        Quality Levels:
            EXCELLENT (0-25% of range): Near support, great R/R
            GOOD (25-50% of range): Below midpoint, good R/R
            FAIR (50-75% of range): Above midpoint, acceptable R/R
            POOR (75-100% of range): Near resistance, poor R/R
        """
        if support >= resistance or support <= 0:
            return {
                "quality": "UNKNOWN",
                "confidence_adjustment": 0.0,
                "position_in_range": 0.5,
                "risk_reward_quality": 1.0,
                "reasoning": "Invalid support/resistance levels",
            }

        # Calculate position in range (0.0 = at support, 1.0 = at resistance)
        range_size = resistance - support
        position_in_range = (current_price - support) / range_size

        # Clamp to 0-1 range (price might be outside S/R levels)
        position_in_range = max(0.0, min(1.0, position_in_range))

        # Calculate risk/reward based on position
        # Risk = distance to support, Reward = distance to resistance
        distance_to_support = current_price - support
        distance_to_resistance = resistance - current_price

        if distance_to_support > 0:
            risk_reward_ratio = distance_to_resistance / distance_to_support
        else:
            risk_reward_ratio = 999.0  # At or below support = excellent R/R

        # Score the entry
        if position_in_range < 0.25:
            # Near support - EXCELLENT entry
            quality = "EXCELLENT"
            confidence_adj = +0.20
            reasoning = (
                f"Price near support (bottom {position_in_range*100:.0f}% of range). "
                f"R/R ratio: {risk_reward_ratio:.2f}:1. Great entry point!"
            )
        elif position_in_range < 0.50:
            # Below midpoint - GOOD entry
            quality = "GOOD"
            confidence_adj = +0.10
            reasoning = (
                f"Price below midpoint ({position_in_range*100:.0f}% of range). "
                f"R/R ratio: {risk_reward_ratio:.2f}:1. Good entry point."
            )
        elif position_in_range < 0.75:
            # Above midpoint - FAIR entry
            quality = "FAIR"
            confidence_adj = 0.0
            reasoning = (
                f"Price above midpoint ({position_in_range*100:.0f}% of range). "
                f"R/R ratio: {risk_reward_ratio:.2f}:1. Acceptable entry."
            )
        else:
            # Near resistance - POOR entry
            quality = "POOR"
            confidence_adj = -0.20
            reasoning = (
                f"Price near resistance (top {position_in_range*100:.0f}% of range). "
                f"R/R ratio: {risk_reward_ratio:.2f}:1. Poor entry - likely to pull back."
            )

        return {
            "quality": quality,
            "confidence_adjustment": confidence_adj,
            "position_in_range": position_in_range,
            "risk_reward_quality": risk_reward_ratio,
            "reasoning": reasoning,
        }

    @staticmethod
    def get_stop_loss_suggestion(
        current_price: float, support: float, position_in_range: float
    ) -> dict:
        """
        Suggest stop loss based on support level and position.

        Args:
            current_price: Current price
            support: Support level
            position_in_range: Position in S/R range (0.0 to 1.0)

        Returns:
            {
                "stop_loss": float,
                "stop_loss_pct": float,
                "reasoning": str
            }
        """
        # Stop loss slightly below support (1-2%)
        if position_in_range < 0.5:
            # Near support - tighter stop (1% below support)
            stop_loss = support * 0.99
            reasoning = "Tight stop 1% below support (near support entry)"
        else:
            # Away from support - wider stop (2% below support)
            stop_loss = support * 0.98
            reasoning = "Stop 2% below support (cushion for volatility)"

        stop_loss_pct = ((stop_loss - current_price) / current_price) * 100

        return {
            "stop_loss": stop_loss,
            "stop_loss_pct": stop_loss_pct,
            "reasoning": reasoning,
        }

    @staticmethod
    def get_target_suggestion(
        current_price: float, resistance: float, position_in_range: float
    ) -> dict:
        """
        Suggest profit target based on resistance level.

        Args:
            current_price: Current price
            resistance: Resistance level
            position_in_range: Position in S/R range (0.0 to 1.0)

        Returns:
            {
                "target": float,
                "target_pct": float,
                "reasoning": str
            }
        """
        if position_in_range < 0.3:
            # Near support - target resistance
            target = resistance
            reasoning = "Target resistance (full range potential)"
        elif position_in_range < 0.6:
            # Mid-range - target 80% to resistance
            target = current_price + (resistance - current_price) * 0.8
            reasoning = "Target 80% to resistance (partial range)"
        else:
            # Near resistance - conservative target
            target = resistance * 0.98
            reasoning = "Conservative target near resistance"

        target_pct = ((target - current_price) / current_price) * 100

        return {
            "target": target,
            "target_pct": target_pct,
            "reasoning": reasoning,
        }

    @staticmethod
    def should_wait_for_pullback(
        position_in_range: float, quality: str
    ) -> dict:
        """
        Determine if it's better to wait for a pullback before entering.

        Args:
            position_in_range: Position in S/R range
            quality: Entry quality ("EXCELLENT", "GOOD", "FAIR", "POOR")

        Returns:
            {
                "wait": bool,
                "reasoning": str
            }
        """
        if quality == "POOR" or position_in_range > 0.80:
            return {
                "wait": True,
                "reasoning": "Price near resistance - wait for pullback to support/midpoint",
            }
        elif quality == "FAIR" and position_in_range > 0.65:
            return {
                "wait": True,
                "reasoning": "Price extended - consider waiting for better entry",
            }
        else:
            return {
                "wait": False,
                "reasoning": "Entry point acceptable - OK to enter",
            }
