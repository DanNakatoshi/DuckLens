"""
Trading Pattern Analyzer
Identifies which patterns make the most money from backtest results
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from typing import List, Dict
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class TradePattern:
    """A trading pattern with performance metrics"""
    name: str
    description: str
    trades: List
    total_pnl: float
    avg_pnl: float
    win_rate: float
    profit_factor: float
    avg_duration_days: float
    best_trade: float
    worst_trade: float


class PatternAnalyzer:
    """Analyze trades to identify profitable patterns"""

    def __init__(self, trades: List):
        """
        Initialize with list of Trade objects

        Args:
            trades: List of Trade dataclass objects with fields:
                - symbol, entry_date, exit_date, entry_price, exit_price
                - pnl, return_pct, exit_reason, regime, ml_confidence
        """
        self.trades = trades
        self.patterns = []

    def analyze_all_patterns(self) -> List[TradePattern]:
        """Run all pattern analyses"""
        print("Analyzing trading patterns...\n")

        # Pattern 1: By ML Confidence Level
        self.patterns.extend(self._analyze_ml_confidence_patterns())

        # Pattern 2: By Market Regime
        self.patterns.extend(self._analyze_regime_patterns())

        # Pattern 3: By Exit Reason
        self.patterns.extend(self._analyze_exit_reason_patterns())

        # Pattern 4: By Stock/Sector
        self.patterns.extend(self._analyze_symbol_patterns())

        # Pattern 5: By Hold Duration
        self.patterns.extend(self._analyze_duration_patterns())

        # Pattern 6: By ML Confidence + Regime Combination
        self.patterns.extend(self._analyze_confidence_regime_patterns())

        # Pattern 7: By Entry Price Momentum
        self.patterns.extend(self._analyze_momentum_patterns())

        return self.patterns

    def _analyze_ml_confidence_patterns(self) -> List[TradePattern]:
        """Analyze by ML confidence buckets"""
        patterns = []

        buckets = [
            ("Very High Confidence", 0.85, 1.00),
            ("High Confidence", 0.75, 0.85),
            ("Medium Confidence", 0.65, 0.75),
            ("Low Confidence", 0.50, 0.65)
        ]

        for name, min_conf, max_conf in buckets:
            bucket_trades = [t for t in self.trades
                           if min_conf <= t.ml_confidence < max_conf]

            if bucket_trades:
                pattern = self._create_pattern(
                    name=f"ML {name} ({min_conf:.0%}-{max_conf:.0%})",
                    description=f"Trades with ML confidence between {min_conf:.0%} and {max_conf:.0%}",
                    trades=bucket_trades
                )
                patterns.append(pattern)

        return patterns

    def _analyze_regime_patterns(self) -> List[TradePattern]:
        """Analyze by market regime"""
        patterns = []

        for regime in ['BULLISH', 'NEUTRAL', 'BEARISH']:
            regime_trades = [t for t in self.trades if t.regime == regime]

            if regime_trades:
                pattern = self._create_pattern(
                    name=f"{regime} Regime",
                    description=f"Trades entered during {regime} market conditions",
                    trades=regime_trades
                )
                patterns.append(pattern)

        return patterns

    def _analyze_exit_reason_patterns(self) -> List[TradePattern]:
        """Analyze by how trades were exited"""
        patterns = []

        exit_reasons = {
            'take_profit': 'Hit Profit Target',
            'stop_loss': 'Hit Stop Loss',
            'trailing_stop': 'Trailing Stop Triggered',
            'signal_exit': 'Signal Reversal'
        }

        for reason_key, reason_name in exit_reasons.items():
            reason_trades = [t for t in self.trades if t.exit_reason == reason_key]

            if reason_trades:
                pattern = self._create_pattern(
                    name=f"Exit: {reason_name}",
                    description=f"Trades that exited via {reason_name.lower()}",
                    trades=reason_trades
                )
                patterns.append(pattern)

        return patterns

    def _analyze_symbol_patterns(self) -> List[TradePattern]:
        """Analyze by individual stocks (top 10 by trade count)"""
        patterns = []

        # Group by symbol
        symbol_trades = defaultdict(list)
        for trade in self.trades:
            symbol_trades[trade.symbol].append(trade)

        # Sort by trade count and take top 10
        top_symbols = sorted(symbol_trades.items(),
                           key=lambda x: len(x[1]),
                           reverse=True)[:10]

        for symbol, trades in top_symbols:
            pattern = self._create_pattern(
                name=f"Stock: {symbol}",
                description=f"All trades for {symbol}",
                trades=trades
            )
            patterns.append(pattern)

        return patterns

    def _analyze_duration_patterns(self) -> List[TradePattern]:
        """Analyze by how long trades were held"""
        patterns = []

        buckets = [
            ("Very Short Hold", 0, 3),      # 0-3 days
            ("Short Hold", 3, 7),           # 3-7 days
            ("Medium Hold", 7, 14),         # 1-2 weeks
            ("Long Hold", 14, 30),          # 2-4 weeks
            ("Very Long Hold", 30, 365)     # 1+ months
        ]

        for name, min_days, max_days in buckets:
            bucket_trades = []
            for t in self.trades:
                duration = (t.exit_date - t.entry_date).days
                if min_days <= duration < max_days:
                    bucket_trades.append(t)

            if bucket_trades:
                pattern = self._create_pattern(
                    name=f"{name} ({min_days}-{max_days} days)",
                    description=f"Trades held for {min_days}-{max_days} days",
                    trades=bucket_trades
                )
                patterns.append(pattern)

        return patterns

    def _analyze_confidence_regime_patterns(self) -> List[TradePattern]:
        """Analyze combinations of ML confidence and market regime"""
        patterns = []

        # High confidence in different regimes
        high_conf_trades = [t for t in self.trades if t.ml_confidence >= 0.75]

        for regime in ['BULLISH', 'NEUTRAL', 'BEARISH']:
            combo_trades = [t for t in high_conf_trades if t.regime == regime]

            if combo_trades:
                pattern = self._create_pattern(
                    name=f"High ML Confidence + {regime}",
                    description=f"ML confidence ≥75% during {regime} market",
                    trades=combo_trades
                )
                patterns.append(pattern)

        return patterns

    def _analyze_momentum_patterns(self) -> List[TradePattern]:
        """Analyze by entry price momentum (gain from entry)"""
        patterns = []

        # Calculate immediate momentum (% gain in first 3 days)
        for threshold in [0.02, 0.05, 0.10]:  # 2%, 5%, 10% initial gain
            momentum_trades = []
            for t in self.trades:
                # Approximate: if exit was profitable, assume good momentum
                if t.return_pct > threshold:
                    momentum_trades.append(t)

            if momentum_trades:
                pattern = self._create_pattern(
                    name=f"Strong Momentum (>{threshold:.0%} gain)",
                    description=f"Trades that gained more than {threshold:.0%}",
                    trades=momentum_trades
                )
                patterns.append(pattern)

        return patterns

    def _create_pattern(self, name: str, description: str, trades: List) -> TradePattern:
        """Create a TradePattern from a list of trades"""
        if not trades:
            return None

        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl <= 0]

        total_pnl = sum(t.pnl for t in trades)
        avg_pnl = total_pnl / len(trades)
        win_rate = len(winning_trades) / len(trades) * 100 if trades else 0

        total_wins = sum(t.pnl for t in winning_trades) if winning_trades else 0
        total_losses = abs(sum(t.pnl for t in losing_trades)) if losing_trades else 1
        profit_factor = total_wins / total_losses if total_losses > 0 else 0

        durations = [(t.exit_date - t.entry_date).days for t in trades]
        avg_duration = np.mean(durations) if durations else 0

        best_trade = max(t.pnl for t in trades) if trades else 0
        worst_trade = min(t.pnl for t in trades) if trades else 0

        return TradePattern(
            name=name,
            description=description,
            trades=trades,
            total_pnl=total_pnl,
            avg_pnl=avg_pnl,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_duration_days=avg_duration,
            best_trade=best_trade,
            worst_trade=worst_trade
        )

    def print_top_patterns(self, top_n: int = 10):
        """Print the most profitable patterns"""
        print(f"\n{'='*80}")
        print(f"TOP {top_n} MOST PROFITABLE PATTERNS")
        print(f"{'='*80}\n")

        # Sort by total PnL
        sorted_patterns = sorted(self.patterns, key=lambda p: p.total_pnl, reverse=True)

        print(f"{'Rank':<6} {'Pattern Name':<40} {'Total P&L':<15} {'Trades':<8} {'Win Rate':<10}")
        print("-" * 80)

        for i, pattern in enumerate(sorted_patterns[:top_n], 1):
            print(f"{i:<6} {pattern.name:<40} ${pattern.total_pnl:>12,.2f} {len(pattern.trades):>6} {pattern.win_rate:>8.1f}%")

        print("\n" + "="*80)
        print("DETAILED PATTERN ANALYSIS")
        print("="*80 + "\n")

        for i, pattern in enumerate(sorted_patterns[:top_n], 1):
            print(f"{i}. {pattern.name}")
            print(f"   {pattern.description}")
            print(f"   Total P&L: ${pattern.total_pnl:,.2f}")
            print(f"   Trades: {len(pattern.trades)}")
            print(f"   Avg P&L: ${pattern.avg_pnl:,.2f}")
            print(f"   Win Rate: {pattern.win_rate:.1f}%")
            print(f"   Profit Factor: {pattern.profit_factor:.2f}")
            print(f"   Avg Duration: {pattern.avg_duration_days:.1f} days")
            print(f"   Best Trade: ${pattern.best_trade:,.2f}")
            print(f"   Worst Trade: ${pattern.worst_trade:,.2f}")
            print()

    def get_best_pattern_recommendations(self) -> List[str]:
        """Get actionable recommendations based on pattern analysis"""
        recommendations = []

        # Sort by profit factor (quality over quantity)
        by_pf = sorted([p for p in self.patterns if len(p.trades) >= 10],
                       key=lambda p: p.profit_factor, reverse=True)

        if by_pf and by_pf[0].profit_factor > 1.5:
            recommendations.append(
                f"✓ BEST QUALITY PATTERN: '{by_pf[0].name}' - "
                f"Profit Factor {by_pf[0].profit_factor:.2f}, Win Rate {by_pf[0].win_rate:.1f}%"
            )

        # Sort by total PnL (most profitable)
        by_pnl = sorted(self.patterns, key=lambda p: p.total_pnl, reverse=True)

        if by_pnl and by_pnl[0].total_pnl > 0:
            recommendations.append(
                f"✓ MOST PROFITABLE PATTERN: '{by_pnl[0].name}' - "
                f"Total P&L ${by_pnl[0].total_pnl:,.2f} across {len(by_pnl[0].trades)} trades"
            )

        # Find patterns with high win rate
        high_wr = [p for p in self.patterns if len(p.trades) >= 10 and p.win_rate > 60]
        if high_wr:
            best_wr = max(high_wr, key=lambda p: p.win_rate)
            recommendations.append(
                f"✓ HIGHEST WIN RATE: '{best_wr.name}' - "
                f"{best_wr.win_rate:.1f}% win rate"
            )

        # Identify losing patterns to avoid
        losing = [p for p in self.patterns if p.total_pnl < 0 and len(p.trades) >= 10]
        if losing:
            worst = min(losing, key=lambda p: p.total_pnl)
            recommendations.append(
                f"✗ AVOID: '{worst.name}' - "
                f"Lost ${abs(worst.total_pnl):,.2f}, {worst.win_rate:.1f}% win rate"
            )

        return recommendations

    def save_pattern_results(self, output_file: str = "results/pattern_analysis.csv"):
        """Save pattern analysis to CSV"""
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        data = []
        for pattern in self.patterns:
            data.append({
                'Pattern': pattern.name,
                'Description': pattern.description,
                'Total_PnL': pattern.total_pnl,
                'Trades': len(pattern.trades),
                'Avg_PnL': pattern.avg_pnl,
                'Win_Rate': pattern.win_rate,
                'Profit_Factor': pattern.profit_factor,
                'Avg_Duration_Days': pattern.avg_duration_days,
                'Best_Trade': pattern.best_trade,
                'Worst_Trade': pattern.worst_trade
            })

        df = pd.DataFrame(data)
        df = df.sort_values('Total_PnL', ascending=False)
        df.to_csv(output_file, index=False)
        print(f"\nPattern analysis saved to: {output_file}")


def demo_with_sample_data():
    """Demo pattern analyzer with sample trade data"""
    from datetime import datetime, timedelta
    from dataclasses import dataclass

    @dataclass
    class Trade:
        symbol: str
        entry_date: datetime
        exit_date: datetime
        entry_price: float
        exit_price: float
        pnl: float
        return_pct: float
        exit_reason: str
        regime: str
        ml_confidence: float

    # Create sample trades
    np.random.seed(42)
    trades = []

    symbols = ['COP', 'INTC', 'UNH', 'NVDA', 'TSLA']
    regimes = ['BULLISH', 'NEUTRAL', 'BEARISH']
    exit_reasons = ['take_profit', 'stop_loss', 'signal_exit', 'trailing_stop']

    for i in range(100):
        entry_date = datetime(2024, 1, 1) + timedelta(days=np.random.randint(0, 300))
        duration = np.random.randint(1, 30)
        exit_date = entry_date + timedelta(days=duration)

        entry_price = 100.0
        return_pct = np.random.normal(0.05, 0.15)  # 5% avg, 15% std
        exit_price = entry_price * (1 + return_pct)
        pnl = (exit_price - entry_price) * 100

        trades.append(Trade(
            symbol=np.random.choice(symbols),
            entry_date=entry_date,
            exit_date=exit_date,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl=pnl,
            return_pct=return_pct,
            exit_reason=np.random.choice(exit_reasons),
            regime=np.random.choice(regimes),
            ml_confidence=np.random.uniform(0.60, 0.95)
        ))

    # Analyze patterns
    analyzer = PatternAnalyzer(trades)
    analyzer.analyze_all_patterns()
    analyzer.print_top_patterns(top_n=15)

    # Get recommendations
    print("\n" + "="*80)
    print("ACTIONABLE RECOMMENDATIONS")
    print("="*80)
    for rec in analyzer.get_best_pattern_recommendations():
        print(rec)
    print()

    # Save results
    analyzer.save_pattern_results()


if __name__ == "__main__":
    demo_with_sample_data()
