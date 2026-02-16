"""
Trading strategies module.

This module contains all trading strategies.
Start simple, expand as you learn.
"""

from .base import BaseStrategy
from .single_leg import SingleLegStrategy

__all__ = [
    "BaseStrategy",
    "SingleLegStrategy",
]
