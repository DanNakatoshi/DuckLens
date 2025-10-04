"""Position sizing and cash allocation logic."""

from typing import Optional


class PositionSizer:
    """Calculate optimal position sizes based on capital and risk management rules."""

    def __init__(
        self,
        total_capital: float,
        cash_balance: float,
        margin_available: float,
        current_margin_used: float = 0.0,
    ):
        """
        Initialize position sizer.

        Args:
            total_capital: Total account value (cash + positions)
            cash_balance: Available cash
            margin_available: Total margin available (typically 2x cash for E*TRADE)
            current_margin_used: Currently used margin
        """
        self.total_capital = total_capital
        self.cash_balance = cash_balance
        self.margin_available = margin_available
        self.current_margin_used = current_margin_used
        self.margin_remaining = margin_available - current_margin_used

    def calculate_position_size(
        self,
        signal_strength: float,
        risk_level: str,
        price: float,
        use_margin: bool = False,
    ) -> dict:
        """
        Calculate optimal position size based on signal strength and risk.

        Args:
            signal_strength: Signal strength (0-100)
            risk_level: HIGH, MEDIUM, LOW
            price: Current stock price
            use_margin: Whether margin can be used

        Returns:
            Dict with position size, quantity, allocation %, and risk metrics
        """
        # Determine base allocation percentage based on signal strength
        if signal_strength >= 80:
            base_allocation = 0.20  # 20% for very high confidence
        elif signal_strength >= 70:
            base_allocation = 0.15  # 15% for high confidence
        elif signal_strength >= 60:
            base_allocation = 0.10  # 10% for medium confidence
        elif signal_strength >= 50:
            base_allocation = 0.05  # 5% for lower confidence
        else:
            base_allocation = 0.03  # 3% for weak signals

        # Adjust for risk level
        risk_multiplier = {"LOW": 1.2, "MEDIUM": 1.0, "HIGH": 0.7}
        allocation_pct = base_allocation * risk_multiplier.get(risk_level, 1.0)

        # Calculate position value based on total capital
        position_value = self.total_capital * allocation_pct

        # Determine if we can use margin
        can_use_margin = use_margin and self._should_use_margin(signal_strength)

        if can_use_margin:
            # Can use margin - check if we have enough
            available_buying_power = self.cash_balance + self.margin_remaining
            position_value = min(position_value, available_buying_power)

            # Calculate margin needed
            margin_needed = max(0, position_value - self.cash_balance)
        else:
            # Cash only - limit to available cash
            position_value = min(position_value, self.cash_balance)
            margin_needed = 0

        # Calculate quantity
        quantity = int(position_value / price) if price > 0 else 0
        actual_position_value = quantity * price

        # Recalculate actual margin needed
        if can_use_margin:
            margin_needed = max(0, actual_position_value - self.cash_balance)
        else:
            margin_needed = 0

        return {
            "position_value": actual_position_value,
            "quantity": quantity,
            "allocation_pct": (actual_position_value / self.total_capital * 100)
            if self.total_capital > 0
            else 0,
            "use_margin": can_use_margin and margin_needed > 0,
            "margin_needed": margin_needed,
            "cash_needed": actual_position_value - margin_needed,
            "price": price,
        }

    def _should_use_margin(self, signal_strength: float) -> bool:
        """
        Determine if margin should be used based on conservative rules.

        Conservative margin rules:
        - Only use for HIGH confidence signals (>75)
        - Never exceed 25% of total portfolio in margin
        - Must maintain 30% cash reserve
        """
        # Rule 1: Only high confidence signals
        if signal_strength < 75:
            return False

        # Rule 2: Check current margin usage
        current_margin_pct = (
            (self.current_margin_used / self.total_capital * 100)
            if self.total_capital > 0
            else 0
        )
        if current_margin_pct >= 25:
            return False

        # Rule 3: Maintain cash reserve
        cash_pct = (
            (self.cash_balance / self.total_capital * 100)
            if self.total_capital > 0
            else 0
        )
        if cash_pct < 30:
            return False

        return True

    def get_max_position_value(self, use_margin: bool = False) -> float:
        """
        Calculate maximum position value available.

        Args:
            use_margin: Whether to include margin in calculation

        Returns:
            Maximum position value in dollars
        """
        if use_margin:
            return self.cash_balance + self.margin_remaining
        else:
            return self.cash_balance

    def calculate_diversification_limit(self, num_positions: int) -> float:
        """
        Calculate max allocation per position based on diversification.

        Args:
            num_positions: Number of positions in portfolio

        Returns:
            Maximum allocation percentage per position
        """
        # Minimum 5 positions for diversification
        if num_positions < 5:
            return 0.20  # 20% max per position

        # As portfolio grows, limit concentration
        return min(0.25, 1.0 / num_positions * 1.5)

    def validate_position(
        self, position_value: float, use_margin: bool = False
    ) -> tuple[bool, str]:
        """
        Validate if a position can be opened.

        Returns:
            (is_valid, reason)
        """
        if use_margin:
            # Check if we have enough buying power
            available = self.cash_balance + self.margin_remaining
            if position_value > available:
                return (
                    False,
                    f"Insufficient buying power. Need ${position_value:,.2f}, have ${available:,.2f}",
                )

            # Check margin limits
            margin_needed = position_value - self.cash_balance
            new_margin_total = self.current_margin_used + margin_needed
            margin_pct = (
                (new_margin_total / self.total_capital * 100)
                if self.total_capital > 0
                else 0
            )

            if margin_pct > 25:
                return (
                    False,
                    f"Would exceed 25% margin limit ({margin_pct:.1f}%)",
                )
        else:
            # Cash only
            if position_value > self.cash_balance:
                return (
                    False,
                    f"Insufficient cash. Need ${position_value:,.2f}, have ${self.cash_balance:,.2f}",
                )

        return (True, "OK")

    def get_recommended_allocation(
        self, signal_strength: float, confidence_level: str
    ) -> str:
        """
        Get human-readable allocation recommendation.

        Args:
            signal_strength: Signal strength (0-100)
            confidence_level: HIGH, MEDIUM, LOW

        Returns:
            Recommendation string
        """
        allocation = self.calculate_position_size(signal_strength, confidence_level, 1.0)
        allocation_pct = allocation["allocation_pct"]

        if allocation_pct >= 15:
            return f"LARGE position ({allocation_pct:.0f}% of portfolio)"
        elif allocation_pct >= 10:
            return f"MEDIUM position ({allocation_pct:.0f}% of portfolio)"
        elif allocation_pct >= 5:
            return f"SMALL position ({allocation_pct:.0f}% of portfolio)"
        else:
            return f"MINIMAL position ({allocation_pct:.0f}% of portfolio)"
