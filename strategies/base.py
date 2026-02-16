"""
Base strategy class.

All strategies inherit from this. It defines the interface
that all strategies must implement.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.

    This ensures all strategies have a consistent interface.
    """

    def __init__(self, name: str):
        self.name = name
        self.description = ""
        self.requires = []  # What data this strategy needs

    @abstractmethod
    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market data and generate trade signals.

        Args:
            data: Market data including quotes, options chains, volatility

        Returns:
            Dict with signals and recommendations
        """
        pass

    @abstractmethod
    def get_entry_signal(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate entry signal if conditions are met.

        Returns:
            None if no signal, or dict with trade details
        """
        pass

    @abstractmethod
    def get_exit_signal(self, position: Dict[str, Any],
                       current_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate exit signal for an existing position.

        Args:
            position: Current position details
            current_data: Current market data

        Returns:
            None if hold, or dict with exit recommendation
        """
        pass

    def explain(self, signal: Dict[str, Any]) -> str:
        """
        Generate a human-readable explanation for a signal.

        Args:
            signal: Signal dictionary

        Returns:
            Explanation string
        """
        return f"{self.name} signal generated"

    def validate_signal(self, signal: Dict[str, Any]) -> bool:
        """
        Validate that a signal has all required fields.

        Args:
            signal: Signal dictionary

        Returns:
            True if valid, False otherwise
        """
        required_fields = ['symbol', 'action', 'option_type', 'strike', 'expiration']
        return all(field in signal for field in required_fields)
