"""
Single-leg options strategies.

Simple directional trades:
- Long Call: Profit when stock goes up
- Long Put: Profit when stock goes down

These are the building blocks. Master these first.
"""
from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

from .base import BaseStrategy

logger = logging.getLogger(__name__)


class SingleLegStrategy(BaseStrategy):
    """
    Long call and long put strategies.

    When to use Long Calls:
    - Bullish on the stock
    - Expecting upward movement
    - IV is low (options are cheap)

    When to use Long Puts:
  - Bearish on the stock
    - Expecting downward movement
    - IV is low (options are cheap)
    """

    def __init__(self):
        super().__init__("Single Leg")
        self.description = "Long calls and long puts for directional trades"

    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market data and find single-leg opportunities.

        Args:
            data: Dict with 'opportunities' DataFrame and 'snapshot'

        Returns:
            Dict with analysis results
        """
        opportunities = data.get('opportunities')
        snapshot = data.get('snapshot', {})

        if opportunities is None or opportunities.empty:
            return {'signals': [], 'count': 0}

        signals = []

        # Analyze each opportunity
        for _, row in opportunities.iterrows():
            signal = self._evaluate_opportunity(row, snapshot)
            if signal:
                signals.append(signal)

        return {
            'signals': signals,
            'count': len(signals)
        }

    def get_entry_signal(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate entry signal for best opportunity.

        Returns the single best opportunity based on scoring.
        """
        analysis = self.analyze(data)

        if not analysis['signals']:
            return None

        # Return the best signal (you could sort by score first)
        return analysis['signals'][0]

    def get_exit_signal(self, position: Dict[str, Any],
                       current_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate exit signal for existing position.

        Exit conditions:
        1. Profit target reached (e.g., +50%)
        2. Stop loss hit (e.g., -50%)
        3. Time decay accelerating (close before expiration)
        4. Thesis no longer valid
        """
        entry_price = position.get('entry_price', 0)
        current_price = position.get('current_price', 0)
        dte = position.get('dte', 0)
        contracts = position.get('contracts', 1)

        if entry_price == 0 or current_price == 0:
            return None

        # Calculate P&L percentage
        pnl_pct = ((current_price - entry_price) / entry_price) * 100

        # Profit target (e.g., up 50%)
        if pnl_pct >= 50:
            return {
                'action': 'sell',
                'reason': f'Profit target reached: +{pnl_pct:.1f}%',
                'pnl': current_price * contracts * 100 - entry_price * contracts * 100
            }

        # Stop loss (e.g., down 50%)
        if pnl_pct <= -50:
            return {
                'action': 'sell',
                'reason': f'Stop loss hit: {pnl_pct:.1f}%',
                'pnl': current_price * contracts * 100 - entry_price * contracts * 100
            }

        # Time decay - close before expiration
        if dte <= 3 and pnl_pct < 20:
            return {
                'action': 'sell',
                'reason': f'Closing before expiration: {dte} DTE remaining',
                'pnl': current_price * contracts * 100 - entry_price * contracts * 100
            }

        # No exit signal
        return None

    def _evaluate_opportunity(self, row: pd.Series,
                             snapshot: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Evaluate a single option opportunity.

        Returns a signal if it meets criteria, None otherwise.
        """
        symbol = row.get('symbol')
        option_type = row.get('option_type')
        premium = row.get('premium', 0)
        dte = row.get('dte', 0)
        iv = row.get('iv', 0)
        volume = row.get('volume', 0)
        oi = row.get('open_interest', 0)

        # Basic filters
        if premium > 200:  # Too expensive
            return None

        if dte < 7 or dte > 45:  # Time range
            return None

        if volume < 100 or oi < 100:  # Liquidity
            return None

        # Check IV (prefer lower IV for buying options)
        iv_rank = snapshot.get('volatility', {}).get('iv_rank', 50)

        # Get current quote for context
        quote = snapshot.get('quote', {})
        current_price = quote.get('price', 0)

        if current_price == 0:
            return None

        # Determine bullish/bearish bias
        # This is simplified - you'd use trend analysis here
        change_pct = quote.get('change_pct', 0)

        # Generate signal based on option type and conditions
        signal = {
            'symbol': symbol,
            'action': 'buy',
            'option_type': option_type,
            'strike': row.get('strike'),
            'expiration': row.get('expiration'),
            'dte': dte,
            'premium': premium,
            'contracts': 1,  # Risk calculator would adjust this
            'current_price': current_price,
            'iv': iv * 100 if iv < 1 else iv,
            'iv_rank': iv_rank,
            'volume': volume,
            'open_interest': oi,
            'timestamp': datetime.now()
        }

        # Add reasoning
        signal['reasoning'] = self._generate_reasoning(signal, snapshot)

        return signal

    def _generate_reasoning(self, signal: Dict[str, Any],
                           snapshot: Dict[str, Any]) -> str:
        """
        Generate human-readable explanation for the trade.
        """
        symbol = signal['symbol']
        option_type = signal['option_type'].upper()
        strike = signal['strike']
        dte = signal['dte']
        premium = signal['premium']
        iv_rank = signal['iv_rank']

        quote = snapshot.get('quote', {})
        price = quote.get('price', 0)
        change = quote.get('change_pct', 0)

        reasoning = f"""
TRADE SIGNAL: {option_type} {symbol}
{'=' * 50}

Option Details:
  Strike: ${strike:.2f}
  Expiration: {dte} days
  Premium: ${premium:.2f}
  Current Stock Price: ${price:.2f}

Market Context:
  IV Rank: {iv_rank:.1f}
  Daily Change: {change:+.2f}%

Why This Trade:
"""

        # Add specific reasoning
        if iv_rank < 30:
            reasoning += f"  • IV Rank ({iv_rank:.1f}) is LOW - options are relatively cheap\n"
        elif iv_rank < 50:
            reasoning += f"  • IV Rank ({iv_rank:.1f}) is NORMAL - fairly priced options\n"
        else:
            reasoning += f"  • IV Rank ({iv_rank:.1f}) is HIGH - expensive, ensure thesis is strong\n"

        if option_type == 'CALL':
            if change > 0:
                reasoning += f"  • Stock is UP {change:+.1f}% today - momentum play\n"
            else:
                reasoning += f"  • Buying on dip - contrarian play\n"
        else:  # PUT
            if change < 0:
                reasoning += f"  • Stock is DOWN {change:+.1f}% today - momentum play\n"
            else:
                reasoning += f"  • Buying puts into strength - contrarian play\n"

        # Risk warning
        reasoning += f"\nRISK REMINDER:\n"
        reasoning += f"  • Max loss: ${premium * 100:.2f} (100% of premium)\n"
        reasoning += f"  • Options expire worthless if stock doesn't move\n"
        reasoning += f"  • Consider selling if profit target (+50%) or stop loss (-50%) is hit\n"

        return reasoning

    def explain(self, signal: Dict[str, Any]) -> str:
        """Return the reasoning for a signal."""
        return signal.get('reasoning', 'No reasoning available.')
