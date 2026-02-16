"""
Trade logger - keep a record of all trades.

You can't improve what you don't measure.
This module tracks every trade for analysis and learning.
"""
import json
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

from config import paths

logger = logging.getLogger(__name__)


class TradeLogger:
    """
    Log and manage trade history.

    Trades are stored as JSON for persistence and loaded as DataFrames for analysis.
    """

    def __init__(self, journal_file: Optional[Path] = None):
        """
        Initialize trade logger.

        Args:
            journal_file: Path to journal file (uses default if not provided)
        """
        self.journal_file = journal_file or (paths.journal_dir / "trades.json")
        self.trades = self._load_trades()

        logger.info(f"TradeLogger initialized with {len(self.trades)} historical trades")

    def _load_trades(self) -> List[Dict[str, Any]]:
        """Load trades from disk."""
        if not self.journal_file.exists():
            return []

        try:
            with open(self.journal_file, 'r') as f:
                trades = json.load(f)
            logger.info(f"Loaded {len(trades)} trades from {self.journal_file}")
            return trades
        except Exception as e:
            logger.error(f"Error loading trades: {e}")
            return []

    def _save_trades(self) -> None:
        """Save trades to disk."""
        try:
            self.journal_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.journal_file, 'w') as f:
                json.dump(self.trades, f, indent=2, default=str)
            logger.debug(f"Saved {len(self.trades)} trades to {self.journal_file}")
        except Exception as e:
            logger.error(f"Error saving trades: {e}")

    def log_entry(self, trade: Dict[str, Any]) -> str:
        """
        Log a new trade entry.

        Args:
            trade: Trade dictionary with all relevant details

        Returns:
            Trade ID (timestamp-based)
        """
        trade_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        entry = {
            'trade_id': trade_id,
            'entry_timestamp': datetime.now().isoformat(),
            'status': 'open',
            **trade
        }

        self.trades.append(entry)
        self._save_trades()

        logger.info(f"Logged trade entry: {trade_id}")
        return trade_id

    def log_exit(self, trade_id: str, exit_details: Dict[str, Any]) -> None:
        """
        Log trade exit.

        Args:
            trade_id: Trade ID from log_entry
            exit_details: Exit price, timestamp, reason, etc.
        """
        for trade in self.trades:
            if trade.get('trade_id') == trade_id:
                trade.update({
                    'status': 'closed',
                    'exit_timestamp': datetime.now().isoformat(),
                    **exit_details
                })
                self._save_trades()
                logger.info(f"Logged trade exit: {trade_id}")
                return

        logger.warning(f"Trade {trade_id} not found for exit")

    def get_open_trades(self) -> pd.DataFrame:
        """Get all open positions as DataFrame."""
        open_trades = [t for t in self.trades if t.get('status') == 'open']
        return pd.DataFrame(open_trades)

    def get_closed_trades(self) -> pd.DataFrame:
        """Get all closed trades as DataFrame."""
        closed_trades = [t for t in self.trades if t.get('status') == 'closed']
        return pd.DataFrame(closed_trades)

    def get_all_trades(self) -> pd.DataFrame:
        """Get all trades as DataFrame."""
        return pd.DataFrame(self.trades)

    def get_trade(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific trade by ID."""
        for trade in self.trades:
            if trade.get('trade_id') == trade_id:
                return trade
        return None

    def update_trade(self, trade_id: str, updates: Dict[str, Any]) -> None:
        """Update an existing trade."""
        for trade in self.trades:
            if trade.get('trade_id') == trade_id:
                trade.update(updates)
                self._save_trades()
                logger.info(f"Updated trade: {trade_id}")
                return
        logger.warning(f"Trade {trade_id} not found for update")

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        if not self.trades:
            return {
                'total_trades': 0,
                'open_trades': 0,
                'closed_trades': 0
            }

        df = pd.DataFrame(self.trades)

        summary = {
            'total_trades': len(df),
            'open_trades': len(df[df['status'] == 'open']),
            'closed_trades': len(df[df['status'] == 'closed']),
        }

        # Add P&L for closed trades
        closed = df[df['status'] == 'closed']
        if not closed.empty and 'pnl' in closed.columns:
            summary['total_pnl'] = closed['pnl'].sum()
            summary['avg_pnl'] = closed['pnl'].mean()
            summary['win_rate'] = (closed['pnl'] > 0).sum() / len(closed) * 100
            summary['wins'] = (closed['pnl'] > 0).sum()
            summary['losses'] = (closed['pnl'] <= 0).sum()

        return summary

    def export_to_csv(self, output_path: Optional[Path] = None) -> None:
        """Export trades to CSV for analysis in Excel/Sheets."""
        output_path = output_path or (paths.journal_dir / "trades_export.csv")
        df = self.get_all_trades()
        df.to_csv(output_path, index=False)
        logger.info(f"Exported trades to {output_path}")
