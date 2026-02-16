#!/usr/bin/env python3
"""
Options Trading System - Demo

This script demonstrates the complete workflow:
1. Fetch data
2. Scan for opportunities
3. Score and rank
4. Calculate risk
5. Generate trade signals
6. Log trades

Run this to verify everything works.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.data_fetcher import DataFetcher
from core.options_chain import OptionsChain
from core.volatility import VolatilityCalculator
from analysis.scanner import OptionsScanner
from analysis.scoring import OpportunityScorer
from analysis.risk import RiskCalculator
from strategies.single_leg import SingleLegStrategy
from journal.trade_logger import TradeLogger
from config import scanning_config, risk_config

import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║     OPTIONS TRADING SYSTEM - DEMO                       ║
╚══════════════════════════════════════════════════════════╝
    """)

    # Configuration
    SYMBOL = "SPY"  # S&P 500 ETF - very liquid
    ACCOUNT_VALUE = 10000  # $10k account
    MAX_PREMIUM = 200  # Max $200 per trade

    print(f"\n📊 SCANNING: {SYMBOL}")
    print(f"💰 Account Value: ${ACCOUNT_VALUE:,.2f}")
    print(f"💵 Max Premium: ${MAX_PREMIUM:.2f}")
    print("-" * 60)

    # Step 1: Initialize components
    print("\n[1/7] Initializing system...")
    fetcher = DataFetcher()
    scanner = OptionsScanner(fetcher)
    scorer = OpportunityScorer()
    risk_calc = RiskCalculator(ACCOUNT_VALUE)
    strategy = SingleLegStrategy()
    journal = TradeLogger()

    # Step 2: Get market snapshot
    print("[2/7] Fetching market data...")
    snapshot = scanner.get_market_snapshot(SYMBOL)

    if 'quote' in snapshot:
        quote = snapshot['quote']
        print(f"  ✅ {SYMBOL} Price: ${quote['price']:.2f} ({quote['change_pct']:+.2f}%)")

    if 'volatility' in snapshot:
        vol = snapshot['volatility']
        print(f"  ✅ 30-Day HV: {vol['hv_30d']:.2f}%")
        print(f"  ✅ Volatility Regime: {vol['volatility_regime']}")

    # Step 3: Scan for opportunities
    print(f"\n[3/7] Scanning for opportunities...")
    opportunities = scanner.scan_symbol(
        SYMBOL,
        min_dte=7,
        max_dte=45,
        max_premium=MAX_PREMIUM
    )

    if opportunities is None or opportunities.empty:
        print("  ❌ No opportunities found. Try adjusting filters.")
        return

    print(f"  ✅ Found {len(opportunities)} opportunities")

    # Step 4: Score opportunities
    print(f"\n[4/7] Scoring opportunities...")
    scored = scorer.score_dataframe(opportunities, snapshot)

    # Get top 5
    top_opportunities = scored.head(5)
    print(f"  ✅ Top 5 opportunities scored")

    # Step 5: Display top opportunities
    print(f"\n[5/7] Top Opportunities:")
    print("-" * 60)

    for idx, row in top_opportunities.head(3).iterrows():
        option_type = row['option_type'].upper()
        strike = row['strike']
        dte = row['dte']
        premium = row['premium']
        iv = row.get('iv', 0) * 100 if row.get('iv', 0) < 1 else row.get('iv', 0)
        score = row['total_score']
        grade = row['grade']

        print(f"\n  {grade} - {option_type} ${strike:.2f}")
        print(f"    DTE: {dte}d | Premium: ${premium:.2f} | IV: {iv:.1f}%")
        print(f"    Score: {score:.1f}/100")

    # Step 6: Generate trade signal
    print(f"\n[6/7] Generating trade signal...")

    data = {
        'opportunities': opportunities,
        'snapshot': snapshot
    }

    signal = strategy.get_entry_signal(data)

    if signal:
        print("  ✅ Trade Signal Generated")
        print("\n" + strategy.explain(signal))
    else:
        print("  ❌ No trade signal generated")

    # Step 7: Risk analysis
    if signal:
        print(f"\n[7/7] Risk Analysis:")
        print("-" * 60)

        premium = signal['premium']
        trade = {
            'premium': premium,
            'contracts': 1,
            'option_type': signal['option_type']
        }

        risk_report = risk_calc.generate_risk_report(trade)
        print(risk_report)

    # Summary
    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    print("\nNext Steps:")
    print("  1. Review the scored opportunities")
    print("  2. Analyze the risk report")
    print("  3. Modify filters in config.py")
    print("  4. Run again with different symbols")
    print("\nTo build the UI: python3 -m streamlit run ui/app.py")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        print("\nTroubleshooting:")
        print("  • Check internet connection")
        print("  • Verify dependencies are installed")
        print("  • Try a different symbol (e.g., 'AAPL', 'QQQ')")
