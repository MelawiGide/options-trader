"""
Risk calculator and position sizing.

This is the most important module for long-term survival.
Options trading without proper risk management is gambling.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import logging

from config import risk_config

logger = logging.getLogger(__name__)


@dataclass
class TradeRisk:
    """Risk metrics for a trade."""
    max_loss: float
    max_gain: float
    break_even: float
    risk_reward_ratio: float
    position_size: float
    account_risk_pct: float
    probability_of_profit: Optional[float] = None
    recommended: bool = True
    warnings: List[str] = None


class RiskCalculator:
    """
    Calculate risk metrics and position sizing.

    Core principles:
    1. Never risk more than X% of account on one trade
    2. Size positions based on account value and risk
    3. Calculate max loss scenarios
    4. Warn about risky trades
    """

    def __init__(self, account_value: float, config: risk_config = None):
        """
        Initialize with account value.

        Args:
            account_value: Total account value in dollars
            config: Risk configuration (uses default if not provided)
        """
        self.account_value = account_value
        self.config = config or risk_config

        logger.info(f"RiskCalculator initialized with ${account_value:,.2f} account")

    def calculate_long_option_risk(self, premium: float,
                                    contracts: int = 1) -> TradeRisk:
        """
        Calculate risk for a long option (call or put).

        Max loss: Premium paid (can lose 100%)
        Max gain: Theoretically unlimited (calls) or strike price (puts)

        Args:
            premium: Premium per contract (in dollars)
            contracts: Number of contracts

        Returns:
            TradeRisk object with all risk metrics
        """
        total_premium = premium * contracts * 100  # Options are for 100 shares

        # Max loss is the premium paid (100% loss possible)
        max_loss = total_premium

        # Max gain is theoretically unlimited for calls
        # For puts, max gain is (strike * 100 * contracts) - premium
        # We'll conservatively estimate 3x premium for now
        max_gain = total_premium * 3  # Conservative estimate

        # Break-even: Premium paid (for long options)
        break_even = premium

        # Risk/reward ratio
        rr_ratio = max_loss / max_gain if max_gain > 0 else 0

        # Position sizing based on account risk
        max_risk_amount = self.account_value * self.config.max_portfolio_risk
        recommended_contracts = int(max_risk_amount / (premium * 100))
        recommended_contracts = max(1, recommended_contracts)

        # Account risk percentage
        account_risk_pct = (total_premium / self.account_value) * 100

        # Warnings
        warnings = []
        recommended = True

        if account_risk_pct > self.config.max_portfolio_risk * 100:
            warnings.append(
                f"Position risk ({account_risk_pct:.1f}%) exceeds max ({self.config.max_portfolio_risk * 100:.1f}%)"
            )
            recommended = False

        if premium > self.config.max_premium:
            warnings.append(f"Premium ${premium:.2f} exceeds max ${self.config.max_premium:.2f}")

        return TradeRisk(
            max_loss=max_loss,
            max_gain=max_gain,
            break_even=break_even,
            risk_reward_ratio=rr_ratio,
            position_size=recommended_contracts,
            account_risk_pct=account_risk_pct,
            recommended=recommended,
            warnings=warnings if warnings else None
        )

    def calculate_position_size(self, entry_price: float,
                                stop_loss_price: float,
                                risk_per_trade_pct: float = None) -> int:
        """
        Calculate position size based on risk parameters.

        Args:
            entry_price: Entry price per share
            stop_loss_price: Stop loss price per share
            risk_per_trade_pct: Risk percentage (uses config default if None)

        Returns:
            Number of shares to trade
        """
        risk_per_trade_pct = risk_per_trade_pct or self.config.max_portfolio_risk

        risk_amount_per_share = abs(entry_price - stop_loss_price)
        total_risk_amount = self.account_value * risk_per_trade_pct

        if risk_amount_per_share == 0:
            return 0

        shares = int(total_risk_amount / risk_amount_per_share)

        logger.info(
            f"Position size: {shares} shares at ${entry_price:.2f}, "
            f"stop at ${stop_loss_price:.2f}, risk ${total_risk_amount:.2f}"
        )

        return shares

    def check_portfolio_heat(self, current_positions: List[Dict[str, Any]],
                             new_symbol: str) -> Dict[str, Any]:
        """
        Check if adding a new position would overexpose the portfolio.

        Checks:
        1. Total exposure
        2. Sector exposure
        3. Correlation risk

        Args:
            current_positions: List of current positions
            new_symbol: Symbol of new potential trade

        Returns:
            Dict with warnings and recommendations
        """
        result = {
            'can_add': True,
            'warnings': [],
            'current_exposure': 0.0,
            'sector_exposure': {}
        }

        if not current_positions:
            return result

        # Calculate current exposure
        total_value = sum(p.get('value', 0) for p in current_positions)
        current_exposure_pct = (total_value / self.account_value) * 100
        result['current_exposure'] = current_exposure_pct

        # Check sector exposure (would need sector data)
        # This is a placeholder for sector-based risk management

        if current_exposure_pct > 80:
            result['warnings'].append(
                f"Portfolio is {current_exposure_pct:.1f}% invested. "
                "Consider reducing exposure."
            )
            result['can_add'] = False

        return result

    def estimate_probability_of_profit(self, option_type: str,
                                      current_price: float,
                                      strike: float,
                                      iv: float,
                                      dte: int) -> float:
        """
        Estimate probability of profit using simple approximation.

        This is a simplified calculation. For accurate POP, use Black-Scholes.

        Args:
            option_type: 'call' or 'put'
            current_price: Current stock price
            strike: Strike price
            iv: Implied volatility (as percentage)
            dte: Days to expiration

        Returns:
            Estimated probability of profit (0-100)
        """
        # Expected move
        expected_move = current_price * (iv / 100) * np.sqrt(dte / 365)

        # For calls: prob(stock > strike at expiration)
        # For puts: prob(stock < strike at expiration)

        # Simplified: use distance from strike as proxy
        if option_type == 'call':
            distance = (strike - current_price) / current_price
        else:
            distance = (current_price - strike) / current_price

        # Rough approximation using normal distribution
        # This is NOT accurate - use proper Black-Scholes in production
        if distance < 0:
            # ITM: higher probability
            pop = 50 + abs(distance) * 100
        else:
            # OTM: lower probability based on expected move
            pop = max(10, 50 - (distance / expected_move) * 50)

        return float(np.clip(pop, 5, 95))

    def calculate_greeks_exposure(self, positions: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Calculate total portfolio Greeks exposure.

        Args:
            positions: List of positions with Greeks

        Returns:
            Dict with total delta, gamma, theta, vega
        """
        total_greeks = {
            'delta': 0.0,
            'gamma': 0.0,
            'theta': 0.0,
            'vega': 0.0
        }

        for pos in positions:
            contracts = pos.get('contracts', 1)
            for greek in total_greeks.keys():
                total_greeks[greek] += pos.get(greek, 0) * contracts

        return total_greeks

    def generate_risk_report(self, trade: Dict[str, Any]) -> str:
        """
        Generate a human-readable risk report for a trade.

        Args:
            trade: Trade dictionary with option details

        Returns:
            Formatted risk report string
        """
        premium = trade.get('premium', 0)
        contracts = trade.get('contracts', 1)
        option_type = trade.get('option_type', 'call')

        risk = self.calculate_long_option_risk(premium, contracts)

        report = f"""
RISK ANALYSIS
{'=' * 50}
Trade: {contracts}x {option_type.upper()} @ ${premium:.2f}

Position Size:
  Max Loss: ${risk.max_loss:,.2f}
  Max Gain (est): ${risk.max_gain:,.2f}
  Risk/Reward Ratio: 1:{1/risk.risk_reward_ratio:.1f if risk.risk_reward_ratio > 0 else 0}

Account Risk:
  Position Risk: {risk.account_risk_pct:.2f}% of account
  Max Allowed: {self.config.max_portfolio_risk * 100:.1f}%
  Status: {'✅ WITHIN LIMITS' if risk.recommended else '⚠️ EXCEEDS LIMITS'}

Recommendations:
  Contracts: {risk.position_size}
"""

        if risk.warnings:
            report += "\n⚠️ WARNINGS:\n"
            for warning in risk.warnings:
                report += f"  - {warning}\n"

        return report
