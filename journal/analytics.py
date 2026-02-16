"""
Trade analytics - analyze your performance.

Learn from your trades. What works? What doesn't?
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class TradeAnalytics:
    """
    Analyze trade history and generate insights.

    Metrics tracked:
    - Win rate
    - Average win/loss
    - Profit factor
    - Best and worst trades
    - Performance by strategy
    - Performance by day of week
    - Performance by holding period
    """

    def __init__(self, trades_df: pd.DataFrame):
        """
        Initialize with trades DataFrame.

        Args:
            trades_df: DataFrame from TradeLogger.get_all_trades()
        """
        self.df = trades_df.copy()
        self.df['entry_timestamp'] = pd.to_datetime(self.df['entry_timestamp'])

        if 'exit_timestamp' in self.df.columns:
            self.df['exit_timestamp'] = pd.to_datetime(self.df['exit_timestamp'])

        logger.info(f"TradeAnalytics initialized with {len(self.df)} trades")

    def calculate_performance_metrics(self) -> Dict[str, Any]:
        """
        Calculate core performance metrics.

        Returns:
            Dict with all key metrics
        """
        closed = self.df[self.df['status'] == 'closed'].copy()

        if closed.empty or 'pnl' not in closed.columns:
            return {
                'total_trades': len(self.df),
                'closed_trades': 0,
                'message': 'No closed trades with P&L data'
            }

        # Basic stats
        total_trades = len(closed)
        wins = (closed['pnl'] > 0).sum()
        losses = (closed['pnl'] <= 0).sum()
        win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0

        # P&L stats
        total_pnl = closed['pnl'].sum()
        avg_pnl = closed['pnl'].mean()
        avg_win = closed[closed['pnl'] > 0]['pnl'].mean() if wins > 0 else 0
        avg_loss = closed[closed['pnl'] <= 0]['pnl'].mean() if losses > 0 else 0

        # Profit factor (gross wins / gross losses)
        gross_wins = closed[closed['pnl'] > 0]['pnl'].sum()
        gross_losses = abs(closed[closed['pnl'] <= 0]['pnl'].sum())
        profit_factor = gross_wins / gross_losses if gross_losses > 0 else 0

        # Best/worst trades
        best_trade = closed['pnl'].max()
        worst_trade = closed['pnl'].min()

        # Expectancy (avg win * win_rate) - (avg_loss * loss_rate)
        win_rate_decimal = wins / total_trades
        loss_rate_decimal = losses / total_trades
        expectancy = (avg_win * win_rate_decimal) - (abs(avg_loss) * loss_rate_decimal)

        return {
            'total_trades': total_trades,
            'wins': int(wins),
            'losses': int(losses),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'best_trade': best_trade,
            'worst_trade': worst_trade,
            'expectancy': expectancy,
        }

    def performance_by_strategy(self) -> pd.DataFrame:
        """Analyze performance by strategy type."""
        closed = self.df[self.df['status'] == 'closed'].copy()

        if closed.empty or 'pnl' not in closed.columns:
            return pd.DataFrame()

        # Group by option_type (call/put)
        if 'option_type' in closed.columns:
            return closed.groupby('option_type')['pnl'].agg([
                ('trades', 'count'),
                ('total_pnl', 'sum'),
                ('avg_pnl', 'mean'),
                ('win_rate', lambda x: (x > 0).sum() / len(x) * 100)
        ]).round(2)

        return pd.DataFrame()

    def performance_by_day_of_week(self) -> pd.DataFrame:
        """Analyze performance by day of week entered."""
        closed = self.df[self.df['status'] == 'closed'].copy()

        if closed.empty or 'pnl' not in closed.columns:
            return pd.DataFrame()

        closed['day_of_week'] = closed['entry_timestamp'].dt.day_name()

        return closed.groupby('day_of_week')['pnl'].agg([
            ('trades', 'count'),
            ('total_pnl', 'sum'),
            ('avg_pnl', 'mean'),
            ('win_rate', lambda x: (x > 0).sum() / len(x) * 100)
        ]).round(2)

    def performance_by_dte(self) -> pd.DataFrame:
        """Analyze performance by days to expiration."""
        closed = self.df[self.df['status'] == 'closed'].copy()

        if closed.empty or 'pnl' not in closed.columns or 'dte' not in closed.columns:
            return pd.DataFrame()

        # Create DTE buckets
        closed['dte_bucket'] = pd.cut(
            closed['dte'],
            bins=[0, 7, 14, 30, 45, 999],
            labels=['0-7d', '8-14d', '15-30d', '31-45d', '45d+']
        )

        return closed.groupby('dte_bucket')['pnl'].agg([
            ('trades', 'count'),
            ('total_pnl', 'sum'),
            ('avg_pnl', 'mean'),
            ('win_rate', lambda x: (x > 0).sum() / len(x) * 100)
        ]).round(2)

    def get_losing_trades(self, top_n: int = 10) -> pd.DataFrame:
        """Get worst performing trades for analysis."""
        closed = self.df[self.df['status'] == 'closed'].copy()

        if closed.empty or 'pnl' not in closed.columns:
            return pd.DataFrame()

        return closed.nsmallest(top_n, 'pnl')

    def get_winning_trades(self, top_n: int = 10) -> pd.DataFrame:
        """Get best performing trades for analysis."""
        closed = self.df[self.df['status'] == 'closed'].copy()

        if closed.empty or 'pnl' not in closed.columns:
            return pd.DataFrame()

        return closed.nlargest(top_n, 'pnl')

    def calculate_streaks(self) -> Dict[str, Any]:
        """Calculate winning and losing streaks."""
        closed = self.df[self.df['status'] == 'closed'].copy()

        if closed.empty or 'pnl' not in closed.columns:
            return {}

        # Sort by entry date
        closed = closed.sort_values('entry_timestamp')

        # Mark wins and losses
        closed['is_win'] = closed['pnl'] > 0

        # Calculate streaks
        current_streak = 0
        max_win_streak = 0
        max_lose_streak = 0
        streak_type = None  # 'win' or 'loss'

        for _, row in closed.iterrows():
            if row['is_win']:
                if streak_type == 'win':
                    current_streak += 1
                else:
                    current_streak = 1
                    streak_type = 'win'
                max_win_streak = max(max_win_streak, current_streak)
            else:
                if streak_type == 'loss':
                    current_streak += 1
                else:
                    current_streak = 1
                    streak_type = 'loss'
                max_lose_streak = max(max_lose_streak, current_streak)

        return {
            'max_win_streak': max_win_streak,
            'max_lose_streak': max_lose_streak,
        }

    def generate_report(self) -> str:
        """Generate a comprehensive performance report."""
        metrics = self.calculate_performance_metrics()

        if 'message' in metrics:
            return metrics['message']

        streaks = self.calculate_streaks()

        report = f"""
PERFORMANCE REPORT
{'=' * 60}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

OVERALL METRICS
{'=' * 60}
Total Trades: {metrics['total_trades']}
Wins: {metrics['wins']}  |  Losses: {metrics['losses']}
Win Rate: {metrics['win_rate']:.1f}%

P&L SUMMARY
{'=' * 60}
Total P&L: ${metrics['total_pnl']:,.2f}
Avg P&L: ${metrics['avg_pnl']:.2f}
Avg Win: ${metrics['avg_win']:.2f}  |  Avg Loss: ${metrics['avg_loss']:.2f}
Best Trade: ${metrics['best_trade']:.2f}  |  Worst Trade: ${metrics['worst_trade']:.2f}

RISK METRICS
{'=' * 60}
Profit Factor: {metrics['profit_factor']:.2f}
Expectancy: ${metrics['expectancy']:.2f} per trade

STREAKS
{'=' * 60}
Max Win Streak: {streaks['max_win_streak']}
Max Losing Streak: {streaks['max_lose_streak']}

{'=' * 60}
"""

        return report
