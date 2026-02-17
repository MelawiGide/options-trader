#!/usr/bin/env python3
"""
Multi-Symbol Options Scanner

Scan multiple symbols for opportunities at once.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.data_fetcher import DataFetcher
from analysis.scanner import OptionsScanner
from analysis.scoring import OpportunityScorer
from strategies.single_leg import SingleLegStrategy
import pandas as pd

# Default watchlist - EDIT THIS
DEFAULT_WATCHLIST = [
    "SPY",    # S&P 500 ETF
    "QQQ",    # NASDAQ ETF
    "AAPL",   # Apple
    "TSLA",   # Tesla
    "NVDA",   # NVIDIA
    "AMD",    # AMD
    "META",   # Meta
    "GOOGL",  # Google
    "AMZN",   # Amazon
    "MSFT",   # Microsoft
]

def scan_watchlist(symbols=None, max_premium=200, min_dte=7, max_dte=45, top_n=5):
    """
    Scan multiple symbols for opportunities.

    Args:
        symbols: List of symbols to scan (uses DEFAULT_WATCHLIST if None)
        max_premium: Maximum premium per contract
        min_dte: Minimum days to expiration
        max_dte: Maximum days to expiration
        top_n: Number of top opportunities to show per symbol
    """
    if symbols is None:
        symbols = DEFAULT_WATCHLIST

    print(f"""
╔══════════════════════════════════════════════════════════╗
║     MULTI-SYMBOL OPTIONS SCANNER                         ║
╚══════════════════════════════════════════════════════════╝

Scanning {len(symbols)} symbols...
Filter: {min_dte}-{max_dte} DTE, ${max_premium} max premium
    """)

    # Initialize
    fetcher = DataFetcher()
    scanner = OptionsScanner(fetcher)
    scorer = OpportunityScorer()
    strategy = SingleLegStrategy()

    all_opportunities = []

    for symbol in symbols:
        print(f"\n{'='*60}")
        print(f"📊 SCANNING: {symbol}")
        print(f"{'='*60}")

        try:
            # Get market snapshot
            snapshot = scanner.get_market_snapshot(symbol)

            if 'quote' in snapshot:
                quote = snapshot['quote']
                print(f"Price: ${quote['price']:.2f} ({quote['change_pct']:+.2f}%)")

            # Scan for opportunities
            opportunities = scanner.scan_symbol(
                symbol,
                min_dte=min_dte,
                max_dte=max_dte,
                max_premium=max_premium,
                option_types=['call', 'put']
            )

            if opportunities is None or opportunities.empty:
                print("❌ No opportunities found with current filters")
                continue

            # Score opportunities
            scored = scorer.score_dataframe(opportunities, snapshot)

            # Get top opportunities
            top = scored.head(top_n)

            print(f"\n✅ Found {len(scored)} opportunities (showing top {top_n}):")
            print(f"{'-'*60}")

            for idx, row in top.iterrows():
                option_type = row['option_type'].upper()
                strike = row['strike']
                dte = row['dte']
                premium = row['premium']
                score = row['total_score']
                grade = row['grade']

                print(f"  {grade} - {option_type} ${strike:.2f} | {dte}d | ${premium:.2f} | Score: {score:.0f}/100")

            # Add to combined list
            all_opportunities.append(scored)

        except Exception as e:
            print(f"❌ Error scanning {symbol}: {e}")
            continue

    # Combine and show overall best
    if all_opportunities:
        print(f"\n\n{'='*60}")
        print("🏆 TOP OPPORTUNITIES ACROSS ALL SYMBOLS")
        print(f"{'='*60}\n")

        combined = pd.concat(all_opportunities, ignore_index=True)
        combined = combined.sort_values('total_score', ascending=False)

        top_overall = combined.head(10)

        for idx, row in top_overall.iterrows():
            option_type = row['option_type'].upper()
            symbol = row['symbol']
            strike = row['strike']
            dte = row['dte']
            premium = row['premium']
            score = row['total_score']
            grade = row['grade']

            print(f"  {grade} - {symbol} {option_type} ${strike:.2f} | {dte}d | ${premium:.2f} | Score: {score:.0f}/100")

        print(f"\n{'='*60}")
        print(f"Total opportunities across all symbols: {len(combined)}")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scan multiple symbols for options opportunities")
    parser.add_argument("--symbols", nargs="+", help="Symbols to scan (space-separated)", default=None)
    parser.add_argument("--max-premium", type=float, default=200, help="Max premium per contract")
    parser.add_argument("--min-dte", type=int, default=7, help="Minimum days to expiration")
    parser.add_argument("--max-dte", type=int, default=45, help="Maximum days to expiration")
    parser.add_argument("--top", type=int, default=5, help="Top N to show per symbol")

    args = parser.parse_args()

    try:
        scan_watchlist(
            symbols=args.symbols,
            max_premium=args.max_premium,
            min_dte=args.min_dte,
            max_dte=args.max_dte,
            top_n=args.top
        )
    except KeyboardInterrupt:
        print("\n\nScanning interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
