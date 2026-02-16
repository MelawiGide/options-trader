# Options Trading System 📊

An intelligent options trading discovery and analysis system built in Python.

## Features

- 🔍 **Options Scanner** - Scan and filter options chains
- 📈 **Volatility Analysis** - IV Rank, Historical Volatility, Expected Move
- 🎯 **Opportunity Scoring** - Rank opportunities A-F
- ⚠️ **Risk Calculator** - Position sizing and risk management
- 📓 **Trade Journal** - Track every trade
- 🚀 **Web Dashboard** - Interactive Streamlit UI

## Quick Start

### Installation

```bash
# Install dependencies
pip3 install -r requirements.txt
```

### Run the Demo

```bash
python3 demo.py
```

### Launch the Dashboard

```bash
streamlit run ui/app.py
```

Then open http://localhost:8501 in your browser.

## Project Structure

```
options-trader/
├── core/           # Data layer (fetching, caching, volatility)
├── analysis/       # Scanner, scoring, risk calculator
├── strategies/     # Trading strategies (single-leg, spreads)
├── journal/        # Trade logging and analytics
├── ui/             # Streamlit dashboard
└── config.py       # Configuration settings
```

## Configuration

Edit `config.py` to adjust:
- Scan filters (DTE, premium, volume)
- Risk parameters
- Cache settings
- UI preferences

## Usage

### Command Line

```python
from core.data_fetcher import DataFetcher
from analysis.scanner import OptionsScanner
from analysis.scoring import OpportunityScorer

# Initialize
fetcher = DataFetcher()
scanner = OptionsScanner(fetcher)
scorer = OpportunityScorer()

# Scan for opportunities
opportunities = scanner.scan_symbol("SPY", max_premium=200)

# Score opportunities
snapshot = scanner.get_market_snapshot("SPY")
scored = scorer.score_dataframe(opportunities, snapshot)
```

### Web Dashboard

1. Enter a symbol (SPY, AAPL, QQQ, etc.)
2. Adjust filters in sidebar
3. Click "Scan for Opportunities"
4. Review scored opportunities

## Disclaimer

**⚠️ WARNING:** This software is for educational purposes only. Options trading involves substantial risk of loss. Past performance does not guarantee future results.

**Never trade with money you cannot afford to lose.**

## License

MIT License - See LICENSE file for details

## Author

Built with ❤️ by MelawiGide
