"""
Volatility calculations and analysis.

Volatility is THE most important factor in options pricing.
This module calculates:
- Historical Volatility (HV) - realized price movement
- Implied Volatility (IV) - market's expectation of future movement
- IV Rank - where current IV sits relative to historical range
- IV Percentile - how often IV has been lower
- Expected Move - price range expected by market
"""
import pandas as pd
import numpy as np
from typing import Optional, Tuple
from datetime import datetime, timedelta
import logging

from scipy import stats

logger = logging.getLogger(__name__)


class VolatilityCalculator:
    """
    Calculate all volatility metrics for options analysis.

    Why these metrics matter:
    - HV: What actually happened
    - IV: What the market expects will happen
    - IV Rank: Is IV high or low relative to history?
    - IV Percentile: How rare is current IV?
    - Expected Move: How much does the market expect price to move?
    """

    def __init__(self, historical_data: pd.DataFrame):
        """
        Initialize with historical price data.

        Args:
            historical_data: DataFrame from get_historical_data()
                             Must have 'Close' column and datetime index
        """
        if historical_data is None or historical_data.empty:
            raise ValueError("Cannot calculate volatility without historical data")

        if 'Close' not in historical_data.columns:
            raise ValueError("Historical data must have 'Close' column")

        self.data = historical_data.copy()
        self.data['returns'] = np.log(self.data['Close'] / self.data['Close'].shift(1))

        logger.info(f"VolatilityCalculator initialized with {len(self.data)} days of data")

    def calculate_historical_volatility(self, period: int = 30,
                                        annualize: bool = True) -> float:
        """
        Calculate historical volatility (realized volatility).

        HV is the standard deviation of returns.

        Args:
            period: Lookback period in days (default: 30)
            annualize: Convert to annualized volatility (default: True)

        Returns:
            Historical volatility as a percentage
        """
        if len(self.data) < period:
            logger.warning(f"Not enough data for {period}-day HV calculation")
            period = len(self.data) - 1

        # Get recent returns
        recent_returns = self.data['returns'].iloc[-period:].dropna()

        # Calculate standard deviation
        hv = recent_returns.std()

        # Annualize (trading days per year = 252)
        if annualize:
            hv = hv * np.sqrt(252)

        return float(hv * 100)  # Return as percentage

    def calculate_iv_rank(self, current_iv: float,
                          lookback_period: int = 50,
                          data_points: int = 252) -> Tuple[float, float]:
        """
        Calculate IV Rank and IV Percentile.

        IV Rank = (Current IV - 52w Low) / (52w High - 52w Low) * 100
        IV Percentile = % of days IV has been lower than current

        Args:
            current_iv: Current implied volatility (as percentage, e.g., 25.5)
            lookback_period: Rolling window for high/low calculation
            data_points: Total lookback period for percentile

        Returns:
            (iv_rank, iv_percentile) as tuple
        """
        # Calculate rolling HV as proxy for historical IV
        # Note: In production, you'd have historical IV data from options chain
        self.data['rolling_hv'] = self.data['returns'].rolling(
            window=lookback_period
        ).std() * np.sqrt(252) * 100

        # Get the last data_points of rolling HV
        hv_history = self.data['rolling_hv'].iloc[-data_points:].dropna()

        if hv_history.empty:
            logger.warning("Not enough historical data for IV rank")
            return (50.0, 50.0)  # Default to middle

        iv_low = hv_history.min()
        iv_high = hv_history.max()

        # Calculate IV Rank
        if iv_high == iv_low:
            iv_rank = 50.0
        else:
            iv_rank = ((current_iv - iv_low) / (iv_high - iv_low)) * 100

        # Calculate IV Percentile
        iv_percentile = (hv_history < current_iv).sum() / len(hv_history) * 100

        return (
            float(np.clip(iv_rank, 0, 100)),
            float(np.clip(iv_percentile, 0, 100))
        )

    def calculate_expected_move(self, current_price: float,
                                iv: float,
                                dte: int) -> Tuple[float, float, float]:
        """
        Calculate expected move based on IV.

        This is the price range the market expects with ~68% confidence
        (one standard deviation).

        Formula: Price * IV * sqrt(DTE / 365)

        Args:
            current_price: Current stock price
            iv: Implied volatility (as percentage, e.g., 25.5)
            dte: Days to expiration

        Returns:
            (expected_move, lower_bound, upper_bound)
        """
        if dte <= 0:
            return (0.0, current_price, current_price)

        # Calculate expected move
        expected_move = current_price * (iv / 100) * np.sqrt(dte / 365)

        lower_bound = current_price - expected_move
        upper_bound = current_price + expected_move

        return (
            float(expected_move),
            float(lower_bound),
            float(upper_bound)
        )

    def calculate_hv_for_periods(self, periods: list = [20, 30, 60]) -> dict:
        """
        Calculate HV for multiple lookback periods.

        Returns:
            Dict with period as key, HV as value
        """
        return {
            f'{p}d_hv': self.calculate_historical_volatility(period=p)
            for p in periods
            if len(self.data) >= p
        }

    def get_volatility_regime(self) -> str:
        """
        Determine current volatility regime.

        Returns:
            'low', 'normal', or 'high'
        """
        hv_30d = self.calculate_historical_volatility(period=30)

        # Simple classification (can be refined)
        if hv_30d < 15:
            return 'low'
        elif hv_30d < 30:
            return 'normal'
        else:
            return 'high'

    def is_iv_expensive(self, current_iv: float,
                        lookback_period: int = 50) -> Tuple[bool, str]:
        """
        Determine if current IV is expensive relative to history.

        Returns:
            (is_expensive, reason)
        """
        iv_rank, iv_percentile = self.calculate_iv_rank(
            current_iv,
            lookback_period=lookback_period
        )

        if iv_rank > 75:
            return True, f"IV Rank is {iv_rank:.1f} - IV is very high"
        elif iv_rank > 50:
            return False, f"IV Rank is {iv_rank:.1f} - IV is elevated"
        else:
            return False, f"IV Rank is {iv_rank:.1f} - IV is relatively low"

    def calculate_iv_percentile_from_history(self,
                                              historical_iv: pd.Series,
                                              current_iv: float) -> float:
        """
        Calculate IV percentile from historical IV data.

        Use this if you have actual historical IV (better than HV proxy).

        Args:
            historical_iv: Series of historical IV values
            current_iv: Current IV value

        Returns:
            IV percentile (0-100)
        """
        if historical_iv.empty:
            return 50.0

        percentile = (historical_iv < current_iv).sum() / len(historical_iv) * 100
        return float(np.clip(percentile, 0, 100))

    def get_volatility_summary(self, current_iv: Optional[float] = None) -> dict:
        """
        Get comprehensive volatility summary.

        Args:
            current_iv: Current IV (optional)

        Returns:
            Dict with all volatility metrics
        """
        summary = {
            'hv_20d': self.calculate_historical_volatility(period=20),
            'hv_30d': self.calculate_historical_volatility(period=30),
            'hv_60d': self.calculate_historical_volatility(period=60),
            'volatility_regime': self.get_volatility_regime(),
        }

        if current_iv is not None:
            iv_rank, iv_pct = self.calculate_iv_rank(current_iv)
            summary.update({
                'current_iv': current_iv,
                'iv_rank': iv_rank,
                'iv_percentile': iv_pct,
            })

            is_expensive, reason = self.is_iv_expensive(current_iv)
            summary['iv_expensive'] = is_expensive
            summary['iv_analysis'] = reason

        return summary
