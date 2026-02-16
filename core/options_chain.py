"""
Options chain processing and normalization.

Raw options data is messy. This module:
1. Normalizes column names and data types
2. Filters to relevant contracts
3. Adds derived fields
4. Validates data quality
"""
import pandas as pd
import numpy as np
from typing import Optional, List, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class OptionsChain:
    """
    Processed options chain with filtering and analysis capabilities.

    This is your clean, reliable data source for options analysis.
    """

    def __init__(self, raw_data: pd.DataFrame):
        """
        Initialize with raw options data from DataFetcher.

        Args:
            raw_data: DataFrame from get_options_chain()
        """
        if raw_data is None or raw_data.empty:
            raise ValueError("Cannot initialize OptionsChain with empty data")

        self.raw_data = raw_data.copy()
        self.processed = self._process()

    def _process(self) -> pd.DataFrame:
        """
        Process and normalize the raw options data.

        Returns:
            Clean DataFrame with standardized columns
        """
        df = self.raw_data.copy()

        # Standardize column names (yfinance uses specific naming)
        column_mapping = {
            'strike': 'strike',
            'lastPrice': 'mid_price',  # Using lastPrice as mid price estimate
            'bid': 'bid',
            'ask': 'ask',
            'volume': 'volume',
            'openInterest': 'open_interest',
            'impliedVolatility': 'iv',
            'inTheMoney': 'itm',
            'contractSymbol': 'contract_symbol',
            'lastTradeDate': 'last_trade_date'
        }

        # Rename columns that exist
        rename_map = {k: v for k, v in column_mapping.items() if k in df.columns}
        df = df.rename(columns=rename_map)

        # Keep only columns we need
        cols_to_keep = ['expiration', 'dte', 'option_type']
        cols_to_keep.extend([v for k, v in column_mapping.items() if k in df.columns])
        df = df[[c for c in cols_to_keep if c in df.columns]].copy()

        # Data type conversions
        df['strike'] = df['strike'].astype(float)
        df['dte'] = df['dte'].astype(int)

        # Calculate mid price if bid/ask available
        if 'bid' in df.columns and 'ask' in df.columns:
            df['mid_price'] = (df['bid'] + df['ask']) / 2
            # Fill NaN mid_prices with lastPrice
            df['mid_price'] = df['mid_price'].fillna(df.get('lastPrice', df['mid_price']))

        # Convert IV to percentage (0-100 scale)
        if 'iv' in df.columns:
            df['iv_pct'] = df['iv'] * 100
        else:
            df['iv_pct'] = np.nan

        # Add premium (cost to buy) - using ask price
        if 'ask' in df.columns:
            df['premium'] = df['ask'] * 100  # Convert to dollar amount
        else:
            df['premium'] = df['mid_price'] * 100

        # Filter out zero or negative prices
        df = df[df['premium'] > 0].copy()

        # Calculate liquidity ratio (only if open_interest column exists)
        if 'open_interest' in df.columns:
            df['liquidity_ratio'] = np.where(
                df['open_interest'] > 0,
                df['volume'] / df['open_interest'],
                np.nan
            )
        else:
            df['liquidity_ratio'] = np.nan

        logger.info(f"Processed options chain: {len(df)} contracts")
        return df

    def filter_by_dte(self, min_dte: int = 0, max_dte: int = 45) -> 'OptionsChain':
        """Filter by days to expiration."""
        mask = (self.processed['dte'] >= min_dte) & (self.processed['dte'] <= max_dte)
        return OptionsChain(self.processed[mask])

    def filter_by_premium(self, max_premium: float = 200.0) -> 'OptionsChain':
        """Filter by maximum premium cost."""
        mask = self.processed['premium'] <= max_premium
        return OptionsChain(self.processed[mask])

    def filter_by_volume(self, min_volume: int = 100) -> 'OptionsChain':
        """Filter by minimum volume."""
        if 'volume' not in self.processed.columns:
            # Skip filtering if column doesn't exist
            return OptionsChain(self.processed)
        mask = self.processed['volume'] >= min_volume
        return OptionsChain(self.processed[mask])

    def filter_by_oi(self, min_oi: int = 100) -> 'OptionsChain':
        """Filter by minimum open interest."""
        if 'open_interest' not in self.processed.columns:
            # Skip filtering if column doesn't exist
            return OptionsChain(self.processed)
        mask = self.processed['open_interest'] >= min_oi
        return OptionsChain(self.processed[mask])

    def filter_by_type(self, option_type: str = 'call') -> 'OptionsChain':
        """Filter by option type (call or put)."""
        mask = self.processed['option_type'] == option_type.lower()
        return OptionsChain(self.processed[mask])

    def filter_by_moneyness(self, relation: str = 'itm') -> 'OptionsChain':
        """
        Filter by moneyness.

        Note: This requires underlying price which we don't have here.
        You'll need to filter at a higher level.
        """
        # Placeholder - requires underlying price
        raise NotImplementedError("Moneyness filtering requires underlying price")

    def get_expirations(self) -> List[datetime]:
        """Get list of unique expiration dates."""
        return sorted(self.processed['expiration'].unique())

    def get_strikes(self) -> List[float]:
        """Get sorted list of unique strike prices."""
        return sorted(self.processed['strike'].unique())

    def to_dataframe(self) -> pd.DataFrame:
        """Return the processed DataFrame."""
        return self.processed.copy()

    def summary(self) -> dict:
        """Get summary statistics."""
        return {
            'total_contracts': len(self.processed),
            'calls': len(self.processed[self.processed['option_type'] == 'call']),
            'puts': len(self.processed[self.processed['option_type'] == 'put']),
            'expirations': self.processed['expiration'].nunique(),
            'dte_range': (
                int(self.processed['dte'].min()),
                int(self.processed['dte'].max())
            ),
            'strike_range': (
                float(self.processed['strike'].min()),
                float(self.processed['strike'].max())
            ),
            'avg_volume': float(self.processed['volume'].mean()),
            'avg_oi': float(self.processed['open_interest'].mean()),
        }

    def find_atm(self, underlying_price: float, option_type: str = 'call') -> pd.Series:
        """
        Find at-the-money option for given underlying price.

        Returns the option with strike closest to underlying price.
        """
        filtered = self.processed[
            (self.processed['option_type'] == option_type) &
            (self.processed['dte'] > 0)
        ].copy()

        if filtered.empty:
            return None

        filtered['distance'] = abs(filtered['strike'] - underlying_price)
        atm_idx = filtered['distance'].idxmin()

        return filtered.loc[atm_idx]
