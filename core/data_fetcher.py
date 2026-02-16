"""
Data fetcher for market data.

This module abstracts multiple data sources and provides a unified interface.
Currently supports:
- Yahoo Finance (free, no API key needed)

Planned support:
- Polygon.io (paid, high quality)
- IEX Cloud (paid, reliable)
- Finnhub (freemium)
"""
import time
from typing import Optional, List, Dict, Any
import logging

import yfinance as yf
import pandas as pd

from config import data_config
from .cache import CacheManager

logger = logging.getLogger(__name__)


class DataFetchError(Exception):
    """Custom exception for data fetch failures."""
    pass


class DataFetcher:
    """
    Unified data fetching interface with caching and error handling.

    Design principles:
    1. Fail gracefully - return None or empty DataFrame on error
    2. Log everything - help debug issues
    3. Cache aggressively - reduce API calls
    4. Retry with backoff - handle transient failures
    """

    def __init__(self, cache_manager: Optional[CacheManager] = None):
        self.cache = cache_manager or CacheManager()
        self.config = data_config

    def _retry_with_backoff(self, func, *args, max_retries: int = None,
                            **kwargs) -> Any:
        """
        Retry function with exponential backoff.

        Network requests fail. This handles transient failures.
        """
        max_retries = max_retries or self.config.max_retries
        base_delay = 1.0

        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed after {max_retries} attempts: {e}")
                    raise DataFetchError(f"Max retries exceeded: {e}")

                delay = base_delay * (2 ** attempt)
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                time.sleep(delay)

    def get_quote(self, symbol: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get current quote for a symbol.

        Returns:
            Dict with: price, change, change_pct, volume, etc.
            None if fetch fails
        """
        # Check cache first
        if use_cache:
            cached = self.cache.get(symbol, 'quote')
            if cached is not None:
                return cached

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            # Extract relevant fields
            quote = {
                'symbol': symbol,
                'price': info.get('currentPrice') or info.get('regularMarketPrice'),
                'change': info.get('regularMarketChange'),
                'change_pct': info.get('regularMarketChangePercent'),
                'volume': info.get('regularMarketVolume'),
                'avg_volume': info.get('averageVolume'),
                'market_cap': info.get('marketCap'),
                '52w_high': info.get('fiftyTwoWeekHigh'),
                '52w_low': info.get('fiftyTwoWeekLow'),
                'sector': info.get('sector'),
                'industry': info.get('industry'),
                'timestamp': pd.Timestamp.now()
            }

            # Cache for 1 minute
            if use_cache:
                self.cache.set(symbol, 'quote', quote, ttl_seconds=60)

            return quote

        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return None

    def get_historical_data(self, symbol: str, period: str = "1y",
                            use_cache: bool = True) -> Optional[pd.DataFrame]:
        """
        Get historical price data.

        Args:
            symbol: Stock symbol
            period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max
        """
        if use_cache:
            cached = self.cache.get(symbol, 'history', period=period)
            if cached is not None:
                return cached

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period)

            if df.empty:
                logger.warning(f"No historical data for {symbol}")
                return None

            # Cache for 1 hour (historical data changes slowly)
            if use_cache:
                self.cache.set(symbol, 'history', df, ttl_seconds=3600, period=period)

            return df

        except Exception as e:
            logger.error(f"Error fetching history for {symbol}: {e}")
            return None

    def get_options_chain(self, symbol: str, use_cache: bool = True) -> Optional[pd.DataFrame]:
        """
        Get complete options chain for a symbol.

        Returns DataFrame with all expirations and strikes combined.
        """
        if use_cache:
            cached = self.cache.get(symbol, 'chain')
            if cached is not None:
                return cached

        try:
            ticker = yf.Ticker(symbol)

            # Get all expirations
            expirations = ticker.options

            if not expirations:
                logger.warning(f"No options available for {symbol}")
                return None

            all_calls = []
            all_puts = []

            for expiry in expirations:
                try:
                    opt = ticker.option_chain(expiry)

                    # Add expiration date
                    calls = opt.calls.copy()
                    calls['expiration'] = expiry
                    calls['option_type'] = 'call'

                    puts = opt.puts.copy()
                    puts['expiration'] = expiry
                    puts['option_type'] = 'put'

                    all_calls.append(calls)
                    all_puts.append(puts)

                except Exception as e:
                    logger.warning(f"Error fetching chain for {symbol} expiry {expiry}: {e}")
                    continue

            # Combine all data
            if not all_calls and not all_puts:
                return None

            df = pd.concat(all_calls + all_puts, ignore_index=True)

            # Convert expiration to datetime
            df['expiration'] = pd.to_datetime(df['expiration'])

            # Calculate days to expiration
            df['dte'] = (df['expiration'] - pd.Timestamp.now()).dt.days

            # Filter out expired options
            df = df[df['dte'] > 0].copy()

            # Cache for 30 seconds (options prices change frequently)
            if use_cache:
                self.cache.set(symbol, 'chain', df, ttl_seconds=30)

            logger.info(f"Fetched options chain for {symbol}: {len(df)} contracts")
            return df

        except Exception as e:
            logger.error(f"Error fetching options chain for {symbol}: {e}")
            return None

    def get_options_by_expiry(self, symbol: str, expiry: str) -> Optional[Dict[str, pd.DataFrame]]:
        """
        Get options chain for a specific expiration.

        Returns:
            {'calls': DataFrame, 'puts': DataFrame}
        """
        try:
            ticker = yf.Ticker(symbol)
            chain = ticker.option_chain(expiry)

            return {
                'calls': chain.calls,
                'puts': chain.puts
            }

        except Exception as e:
            logger.error(f"Error fetching options for {symbol} expiry {expiry}: {e}")
            return None

    def get_implied_volatility(self, symbol: str) -> Optional[float]:
        """
        Get current 30-day implied volatility.

        Note: yfinance doesn't provide IV directly. This is a placeholder
        that will be implemented in the volatility module.
        """
        # This will be calculated in VolatilityCalculator
        return None

    def get_company_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get detailed company information."""
        try:
            ticker = yf.Ticker(symbol)
            return ticker.info
        except Exception as e:
            logger.error(f"Error fetching company info for {symbol}: {e}")
            return None
