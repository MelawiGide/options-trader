"""
Options scanner - find high-probability opportunities.

This is where we put it all together:
1. Fetch data
2. Calculate volatility metrics
3. Filter based on criteria
4. Return ranked opportunities
"""
import pandas as pd
from typing import List, Dict, Any, Optional
import logging

from core.data_fetcher import DataFetcher
from core.options_chain import OptionsChain
from core.volatility import VolatilityCalculator
from config import scanning_config

logger = logging.getLogger(__name__)


class OptionsScanner:
    """
    Scan options chains for high-probability opportunities.

    This is your main tool for finding trades.
    """

    def __init__(self, data_fetcher: Optional[DataFetcher] = None):
        self.fetcher = data_fetcher or DataFetcher()
        self.config = scanning_config

    def scan_symbol(self, symbol: str,
                    min_dte: int = None,
                    max_dte: int = None,
                    max_premium: float = None,
                    option_types: List[str] = None) -> Optional[pd.DataFrame]:
        """
        Scan a single symbol for options opportunities.

        Args:
            symbol: Stock symbol to scan
            min_dte: Minimum days to expiration
            max_dte: Maximum days to expiration
            max_premium: Maximum premium cost
            option_types: List of types ('call', 'put', or both)

        Returns:
            DataFrame with filtered opportunities
        """
        # Use config defaults if not specified
        min_dte = min_dte or self.config.dte_range[0]
        max_dte = max_dte or self.config.dte_range[1]
        max_premium = max_premium or self.config.max_premium
        option_types = option_types or ['call', 'put']

        logger.info(f"Scanning {symbol} for opportunities...")

        # Step 1: Fetch options chain
        raw_chain = self.fetcher.get_options_chain(symbol)
        if raw_chain is None or raw_chain.empty:
            logger.warning(f"No options data available for {symbol}")
            return None

        # Step 2: Process options chain
        try:
            chain = OptionsChain(raw_chain)
        except Exception as e:
            logger.error(f"Error processing options chain for {symbol}: {e}")
            return None

        # Step 3: Apply filters
        filtered = chain.filter_by_dte(min_dte, max_dte)
        filtered = filtered.filter_by_premium(max_premium)

        # Combine type filters
        if len(option_types) == 1:
            filtered = filtered.filter_by_type(option_types[0])

        # Filter by volume and OI
        filtered = filtered.filter_by_volume(self.config.min_volume)
        filtered = filtered.filter_by_oi(self.config.min_open_interest)

        # Get the final DataFrame
        opportunities = filtered.to_dataframe()

        if opportunities.empty:
            logger.info(f"No opportunities found for {symbol} with current filters")
            return None

        logger.info(f"Found {len(opportunities)} opportunities for {symbol}")

        # Add symbol column
        opportunities['symbol'] = symbol

        return opportunities.sort_values('dte')

    def scan_multiple_symbols(self, symbols: List[str],
                              **kwargs) -> pd.DataFrame:
        """
        Scan multiple symbols for opportunities.

        Args:
            symbols: List of symbols to scan
            **kwargs: Filter parameters (same as scan_symbol)

        Returns:
            Combined DataFrame with all opportunities
        """
        all_opportunities = []

        for symbol in symbols:
            try:
                opportunities = self.scan_symbol(symbol, **kwargs)
                if opportunities is not None and not opportunities.empty:
                    all_opportunities.append(opportunities)
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
                continue

        if not all_opportunities:
            logger.info("No opportunities found across all symbols")
            return pd.DataFrame()

        # Combine all results
        combined = pd.concat(all_opportunities, ignore_index=True)

        logger.info(f"Total opportunities found: {len(combined)}")
        return combined

    def get_market_snapshot(self, symbol: str) -> Dict[str, Any]:
        """
        Get a complete market snapshot for analysis.

        Includes:
        - Current quote
        - Volatility metrics
        - Recent price action
        """
        snapshot = {'symbol': symbol}

        # Get current quote
        quote = self.fetcher.get_quote(symbol)
        if quote:
            snapshot['quote'] = quote

        # Get historical data for volatility
        hist = self.fetcher.get_historical_data(symbol, period="1y")
        if hist is not None:
            vol_calc = VolatilityCalculator(hist)
            snapshot['volatility'] = vol_calc.get_volatility_summary()

        return snapshot

    def find_liquidity_anomalies(self, symbol: str,
                                 min_ratio: float = 2.0) -> Optional[pd.DataFrame]:
        """
        Find options with unusual volume relative to open interest.

        High volume/OI ratio can indicate:
        - Increased interest in a strike
        - Potential insider activity
        - Momentum plays

        Args:
            symbol: Stock symbol
            min_ratio: Minimum volume/OI ratio

        Returns:
            DataFrame with unusual activity
        """
        raw_chain = self.fetcher.get_options_chain(symbol)
        if raw_chain is None:
            return None

        chain = OptionsChain(raw_chain)
        df = chain.to_dataframe()

        # Calculate volume/OI ratio (already done in OptionsChain)
        anomalies = df[df['liquidity_ratio'] >= min_ratio].copy()

        if anomalies.empty:
            return None

        # Sort by ratio
        anomalies = anomalies.sort_values('liquidity_ratio', ascending=False)

        logger.info(f"Found {len(anomalies)} liquidity anomalies for {symbol}")
        return anomalies

    def filter_by_iv_rank(self, opportunities: pd.DataFrame,
                          iv_rank: float,
                          snapshot: Dict[str, Any]) -> pd.DataFrame:
        """
        Filter opportunities by IV rank threshold.

        Args:
            opportunities: DataFrame from scan_symbol
            iv_rank: Minimum IV rank required
            snapshot: Market snapshot with volatility data

        Returns:
            Filtered DataFrame
        """
        if 'volatility' not in snapshot:
            logger.warning("No volatility data in snapshot")
            return opportunities

        current_iv_rank = snapshot['volatility'].get('iv_rank', 0)

        if current_iv_rank < iv_rank:
            logger.info(f"IV rank ({current_iv_rank:.1f}) below threshold ({iv_rank})")
            return pd.DataFrame()

        return opportunities

    def get_near_the_money(self, symbol: str,
                           underlying_price: float,
                           pct_range: float = 0.10) -> Optional[pd.DataFrame]:
        """
        Get options near the money.

        Args:
            symbol: Stock symbol
            underlying_price: Current stock price
            pct_range: Percentage range around stock price (default 10%)

        Returns:
            DataFrame with near-the-money options
        """
        raw_chain = self.fetcher.get_options_chain(symbol)
        if raw_chain is None:
            return None

        chain = OptionsChain(raw_chain)
        df = chain.to_dataframe()

        # Filter by strike range
        lower_strike = underlying_price * (1 - pct_range)
        upper_strike = underlying_price * (1 + pct_range)

        ntm = df[
            (df['strike'] >= lower_strike) &
            (df['strike'] <= upper_strike)
        ].copy()

        logger.info(f"Found {len(ntm)} near-the-money options for {symbol}")
        return ntm
