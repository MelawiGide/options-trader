"""
Opportunity scoring system.

Not all options are created equal. This module scores opportunities
based on multiple factors to help you make better decisions.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class OpportunityScorer:
    """
    Score options opportunities based on multiple factors.

    Scoring factors:
    1. Volatility (IV Rank)
    2. Liquidity (Volume, OI)
    3. Time to expiration (DTE)
    4. Premium affordability
    5. Risk/reward ratio
    """

    def __init__(self):
        self.weights = {
            'iv_rank': 0.25,      # Higher IV = more opportunity
            'liquidity': 0.20,    # Need to be able to enter/exit
            'dte': 0.15,          # Sweet spot for time decay
            'premium': 0.15,      # Lower premium = less risk
            'volume_surge': 0.15, # Unusual activity
            'trend': 0.10,        # Alignment with trend
        }

    def score_opportunity(self, row: pd.Series,
                          snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Score a single option opportunity.

        Args:
            row: Series representing a single option
            snapshot: Market snapshot with volatility data

        Returns:
            Dict with score and component scores
        """
        scores = {}

        # 1. IV Rank Score (0-100)
        scores['iv_rank_score'] = self._score_iv_rank(snapshot)

        # 2. Liquidity Score (0-100)
        scores['liquidity_score'] = self._score_liquidity(row)

        # 3. DTE Score (0-100)
        scores['dte_score'] = self._score_dte(row)

        # 4. Premium Score (0-100)
        scores['premium_score'] = self._score_premium(row)

        # 5. Volume Surge Score (0-100)
        scores['volume_surge_score'] = self._score_volume_surge(row)

        # 6. Trend Score (0-100) - placeholder for now
        scores['trend_score'] = 50.0  # Neutral default

        # Calculate weighted total score
        total_score = sum(
            scores[f'{k}_score'] * v
            for k, v in self.weights.items()
        )

        scores['total_score'] = total_score
        scores['grade'] = self._get_grade(total_score)

        return scores

    def _score_iv_rank(self, snapshot: Dict[str, Any]) -> float:
        """
        Score based on IV Rank.

        Higher IV Rank = better for selling options
        Lower IV Rank = better for buying options

        For our use case (buying options), we want:
        - Low IV Rank (underpriced options) = Good
        """
        if 'volatility' not in snapshot:
            return 50.0  # Neutral

        iv_rank = snapshot['volatility'].get('iv_rank', 50)

        # For buying options: lower IV is better
        # IV Rank < 30: Good score
        # IV Rank 30-50: Neutral
        # IV Rank > 50: Expensive

        if iv_rank < 30:
            return 80.0 + (30 - iv_rank)  # 80-100
        elif iv_rank < 50:
            return 70.0 - (iv_rank - 30)  # 50-70
        else:
            return max(10.0, 50.0 - (iv_rank - 50) * 0.5)  # 10-50

    def _score_liquidity(self, row: pd.Series) -> float:
        """
        Score based on liquidity.

        Need both volume and open interest.
        """
        volume = row.get('volume', 0)
        oi = row.get('open_interest', 0)

        # Minimum threshold check
        if volume < 100 or oi < 100:
            return 0.0  # Not liquid enough

        # Score increases with liquidity
        volume_score = min(100, volume / 100)  # Caps at 10,000 volume
        oi_score = min(100, oi / 100)  # Caps at 10,000 OI

        return (volume_score + oi_score) / 2

    def _score_dte(self, row: pd.Series) -> float:
        """
        Score based on days to expiration.

        Sweet spot: 7-30 days
        - Too short (<7): High theta decay
        - Too long (>45): Less gamma, more time risk
        """
        dte = row.get('dte', 0)

        if dte < 7:
            return 20.0  # Too short
        elif 7 <= dte <= 14:
            return 90.0  # Ideal for quick moves
        elif 14 < dte <= 30:
            return 100.0  # Sweet spot
        elif 30 < dte <= 45:
            return 70.0  # Good but less gamma
        else:
            return 40.0  # Too long

    def _score_premium(self, row: pd.Series) -> float:
        """
        Score based on premium cost.

        Lower premium = less risk, higher potential ROI.
        But too low might mean junk options.

        Sweet spot: $50-$150
        """
        premium = row.get('premium', 0)

        if premium < 20:
            return 30.0  # Too cheap, might be junk
        elif premium <= 100:
            return 100.0  # Ideal
        elif premium <= 200:
            return 70.0  # Acceptable
        else:
            return 30.0  # Too expensive

    def _score_volume_surge(self, row: pd.Series) -> float:
        """
        Score based on unusual volume activity.

        Volume/OI ratio > 1 = unusual activity
        """
        ratio = row.get('liquidity_ratio', 0)

        if ratio > 2:
            return 100.0  # Unusual activity
        elif ratio > 1:
            return 70.0  # Above normal
        elif ratio > 0.5:
            return 50.0  # Normal
        else:
            return 30.0  # Low activity

    def _get_grade(self, score: float) -> str:
        """Convert score to letter grade."""
        if score >= 85:
            return 'A'
        elif score >= 70:
            return 'B'
        elif score >= 55:
            return 'C'
        elif score >= 40:
            return 'D'
        else:
            return 'F'

    def score_dataframe(self, df: pd.DataFrame,
                        snapshot: Dict[str, Any]) -> pd.DataFrame:
        """
        Score all opportunities in a DataFrame.

        Args:
            df: Opportunities DataFrame
            snapshot: Market snapshot

        Returns:
            DataFrame with scores added
        """
        if df.empty:
            return df

        # Calculate scores for each row
        scores_list = []
        for _, row in df.iterrows():
            scores = self.score_opportunity(row, snapshot)
            scores_list.append(scores)

        # Create DataFrame from scores
        scores_df = pd.DataFrame(scores_list)

        # Combine with original data
        result = pd.concat([df.reset_index(drop=True), scores_df], axis=1)

        # Sort by total score
        result = result.sort_values('total_score', ascending=False)

        return result

    def get_top_opportunities(self, df: pd.DataFrame,
                              snapshot: Dict[str, Any],
                              top_n: int = 10) -> pd.DataFrame:
        """
        Get top N scored opportunities.

        Args:
            df: Opportunities DataFrame
            snapshot: Market snapshot
            top_n: Number of top opportunities to return

        Returns:
            Top opportunities as DataFrame
        """
        scored = self.score_dataframe(df, snapshot)
        return scored.head(top_n)
