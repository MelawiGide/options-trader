"""
Configuration settings for the Options Trading System.

Centralized config makes it easy to modify behavior without touching core logic.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class DataConfig:
    """Data source configuration."""
    primary_source: str = "yahoo"  # yahoo, polygon, iex, finnhub
    cache_ttl: int = 300  # Cache time-to-live in seconds (5 min default)
    max_retries: int = 3
    timeout: int = 30
    use_cache: bool = True

    # API Keys (optional - for paid services)
    polygon_api_key: Optional[str] = os.getenv("POLYGON_API_KEY")
    iex_api_key: Optional[str] = os.getenv("IEX_API_KEY")
    finnhub_api_key: Optional[str] = os.getenv("FINNHUB_API_KEY")


@dataclass
class ScanningConfig:
    """Options scanning parameters."""
    min_iv_rank: float = 30.0  # Minimum IV rank to consider
    max_iv_rank: float = 100.0  # No upper limit (high IV = opportunity)
    min_volume: int = 100  # Minimum option volume
    min_open_interest: int = 100  # Minimum open interest
    max_premium: float = 200.0  # User's max premium per trade
    dte_range: tuple = (0, 45)  # Days to expiration range (0-45 days)
    min_liquidity_ratio: float = 0.3  # Volume/OI ratio threshold


@dataclass
class RiskConfig:
    """Risk management parameters."""
    max_portfolio_risk: float = 0.02  # 2% of account per trade
    max_position_size: float = 0.10  # 10% of account max in one position
    max_sector_exposure: float = 0.30  # 30% max per sector
    stop_loss_pct: float = 0.50  # 50% loss triggers exit
    profit_target_pct: float = 0.50  # 50% gain triggers take profit


@dataclass
class UIConfig:
    """User interface settings."""
    theme: str = "dark"
    refresh_interval: int = 60  # Auto-refresh every 60 seconds
    max_display_results: int = 50  # Don't overwhelm with results
    show_advanced: bool = False  # Hide advanced features by default


@dataclass
class Paths:
    """File system paths."""
    base_dir: Path = Path(__file__).parent
    data_dir: Path = Path(__file__).parent / "data"
    journal_dir: Path = Path(__file__).parent / "journal" / "logs"
    cache_dir: Path = Path(__file__).parent / ".cache"

    def __post_init__(self):
        # Create directories if they don't exist
        self.data_dir.mkdir(exist_ok=True)
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(exist_ok=True)


# Global config instances
data_config = DataConfig()
scanning_config = ScanningConfig()
risk_config = RiskConfig()
ui_config = UIConfig()
paths = Paths()
