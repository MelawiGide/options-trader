"""
Options Trading System - Streamlit Dashboard

A clean, interactive UI for scanning and analyzing options opportunities.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import logging

from core.data_fetcher import DataFetcher
from core.options_chain import OptionsChain
from core.volatility import VolatilityCalculator
from analysis.scanner import OptionsScanner
from analysis.scoring import OpportunityScorer
from analysis.risk import RiskCalculator
from strategies.single_leg import SingleLegStrategy
from journal.trade_logger import TradeLogger
from journal.analytics import TradeAnalytics
from config import scanning_config, risk_config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="Options Trading System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .grade-A { color: #00cc00; font-weight: bold; }
    .grade-B { color: #00cc00; }
    .grade-C { color: #ff9900; }
    .grade-D { color: #ff6600; }
    .grade-F { color: #ff0000; font-weight: bold; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def initialize_system():
    """Initialize system components (cached)."""
    fetcher = DataFetcher()
    scanner = OptionsScanner(fetcher)
    scorer = OpportunityScorer()
    logger = TradeLogger()
    return fetcher, scanner, scorer, logger


def render_header():
    """Render page header."""
    st.markdown('<h1 class="main-header">📊 Options Trading System</h1>', unsafe_allow_html=True)
    st.markdown("---")


def render_sidebar():
    """Render sidebar with controls."""
    st.sidebar.header("⚙️ Settings")

    # Symbol input
    symbol = st.sidebar.text_input(
        "Symbol",
        value="SPY",
        help="Stock symbol to scan (e.g., SPY, AAPL, QQQ)"
    ).upper()

    # Account settings
    st.sidebar.subheader("💰 Account")
    account_value = st.sidebar.number_input(
        "Account Value ($)",
        min_value=1000,
        max_value=1000000,
        value=10000,
        step=1000
    )

    # Scan filters
    st.sidebar.subheader("🔍 Filters")

    col1, col2 = st.sidebar.columns(2)
    with col1:
        min_dte = st.number_input("Min DTE", value=7, min_value=0, max_value=365)
    with col2:
        max_dte = st.number_input("Max DTE", value=45, min_value=0, max_value=365)

    max_premium = st.sidebar.slider(
        "Max Premium ($)",
        min_value=50,
        max_value=500,
        value=200,
        step=10
    )

    option_types = st.sidebar.multiselect(
        "Option Types",
        ["call", "put"],
        default=["call", "put"]
    )

    # Risk settings
    st.sidebar.subheader("⚠️ Risk")
    max_portfolio_risk = st.sidebar.slider(
        "Max Risk per Trade (%)",
        min_value=1,
        max_value=10,
        value=2
    )

    return {
        'symbol': symbol,
        'account_value': account_value,
        'min_dte': min_dte,
        'max_dte': max_dte,
        'max_premium': max_premium,
        'option_types': option_types,
        'max_portfolio_risk': max_portfolio_risk / 100
    }


def render_metrics(snapshot):
    """Render key metrics."""
    if not snapshot:
        return

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if 'quote' in snapshot:
            quote = snapshot['quote']
            st.metric(
                quote['symbol'],
                f"${quote['price']:.2f}",
                f"{quote['change_pct']:+.2f}%"
            )

    with col2:
        if 'volatility' in snapshot:
            vol = snapshot['volatility']
            st.metric("30-Day HV", f"{vol['hv_30d']:.2f}%")

    with col3:
        if 'volatility' in snapshot:
            vol = snapshot['volatility']
            st.metric("IV Rank", f"{vol.get('iv_rank', 0):.1f}")

    with col4:
        if 'volatility' in snapshot:
            vol = snapshot['volatility']
            regime = vol.get('volatility_regime', 'unknown').upper()
            st.metric("Volatility Regime", regime)


def render_opportunities_table(opportunities):
    """Render opportunities table with styling."""
    if opportunities is None or opportunities.empty:
        st.info("No opportunities found. Try adjusting filters.")
        return

    # Format for display
    display_cols = [
        'symbol', 'option_type', 'strike', 'dte', 'premium',
        'iv', 'volume', 'open_interest', 'total_score', 'grade'
    ]

    # Only keep columns that exist
    avail_cols = [c for c in display_cols if c in opportunities.columns]
    df_display = opportunities[avail_cols].copy()

    # Format columns
    if 'strike' in df_display.columns:
        df_display['strike'] = df_display['strike'].apply(lambda x: f"${x:.2f}")
    if 'premium' in df_display.columns:
        df_display['premium'] = df_display['premium'].apply(lambda x: f"${x:.2f}")
    if 'iv' in df_display.columns:
        df_display['iv'] = df_display['iv'].apply(lambda x: f"{x:.1f}%" if x > 0 else "N/A")
    if 'total_score' in df_display.columns:
        df_display['total_score'] = df_display['total_score'].apply(lambda x: f"{x:.0f}/100")

    # Rename for display
    df_display = df_display.rename(columns={
        'symbol': 'Symbol',
        'option_type': 'Type',
        'strike': 'Strike',
        'dte': 'DTE',
        'premium': 'Premium',
        'iv': 'IV',
        'volume': 'Volume',
        'open_interest': 'OI',
        'total_score': 'Score',
        'grade': 'Grade'
    })

    st.dataframe(
        df_display,
        use_container_width=True,
        height=400
    )


def render_volatility_chart(snapshot):
    """Render volatility chart."""
    if 'volatility' not in snapshot:
        return

    vol = snapshot['volatility']

    # Create gauge chart for IV Rank
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = vol.get('iv_rank', 50),
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "IV Rank"},
        delta = {'reference': 50},
        gauge = {
            'axis': {'range': [None, 100]},
            'bar': {'color': "#1f77b4"},
            'steps': [
                {'range': [0, 25], 'color': "#e6f2ff"},
                {'range': [25, 50], 'color': "#cce6ff"},
                {'range': [50, 75], 'color': "#99ccff"},
                {'range': [75, 100], 'color': "#66b3ff"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 75
            }
        }
    ))

    st.plotly_chart(fig, use_container_width=True)


def render_trade_journal():
    """Render trade journal section."""
    st.header("📓 Trade Journal")

    logger = TradeLogger()

    # Summary metrics
    summary = logger.get_summary()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Trades", summary['total_trades'])
    with col2:
        st.metric("Open Positions", summary['open_trades'])
    with col3:
        if 'total_pnl' in summary:
            st.metric("Total P&L", f"${summary['total_pnl']:.2f}")
        else:
            st.metric("Total P&L", "N/A")

    # Trade history
    trades = logger.get_all_trades()

    if not trades.empty:
        st.subheader("Trade History")

        # Format for display
        display_df = trades[[
            'trade_id', 'symbol', 'option_type', 'strike',
            'entry_timestamp', 'status'
        ]].copy() if all(c in trades.columns for c in [
            'trade_id', 'symbol', 'option_type', 'strike',
            'entry_timestamp', 'status'
        ]) else trades

        st.dataframe(display_df, use_container_width=True)


def main():
    """Main app function."""
    render_header()

    # Get settings from sidebar
    settings = render_sidebar()

    # Initialize system
    fetcher, scanner, scorer, trade_logger = initialize_system()

    # Create tabs
    tab1, tab2, tab3 = st.tabs(["🔍 Scanner", "📈 Analytics", "📓 Journal"])

    with tab1:
        st.header("Options Scanner")

        # Scan button
        if st.button("🚀 Scan for Opportunities", type="primary"):
            with st.spinner("Scanning..."):
                # Get market snapshot
                snapshot = scanner.get_market_snapshot(settings['symbol'])

                # Display metrics
                render_metrics(snapshot)

                st.markdown("---")

                # Scan for opportunities
                opportunities = scanner.scan_symbol(
                    settings['symbol'],
                    min_dte=settings['min_dte'],
                    max_dte=settings['max_dte'],
                    max_premium=settings['max_premium'],
                    option_types=settings['option_types']
                )

                if opportunities is not None and not opportunities.empty:
                    # Score opportunities
                    scored = scorer.score_dataframe(opportunities, snapshot)

                    # Show top 20
                    top_opportunities = scored.head(20)

                    st.success(f"Found {len(scored)} opportunities (showing top 20)")

                    # Render table
                    render_opportunities_table(top_opportunities)

                    # Volatility chart
                    col1, col2 = st.columns(2)
                    with col1:
                        render_volatility_chart(snapshot)
                    with col2:
                        if 'quote' in snapshot and 'volatility' in snapshot:
                            quote = snapshot['quote']
                            vol = snapshot['volatility']
                            st.info(f"""
**Market Analysis:**

**Symbol:** {quote['symbol']}
**Price:** ${quote['price']:.2f}
**Change:** {quote['change_pct']:+.2f}%

**Volatility:**
- 30-Day HV: {vol['hv_30d']:.2f}%
- IV Rank: {vol.get('iv_rank', 0):.1f}
- Regime: {vol.get('volatility_regime', 'unknown').upper()}
                            """)
                else:
                    st.warning("No opportunities found with current filters.")
                    st.info("Try adjusting the filters in the sidebar:")
                    st.markdown("""
                    - Increase DTE range
                    - Increase max premium
                    - Change option types
                    """)

    with tab2:
        st.header("Performance Analytics")

        trades = trade_logger.get_all_trades()

        if trades.empty or 'pnl' not in trades.columns:
            st.info("No closed trades to analyze yet. Start trading to see analytics!")
        else:
            analytics = TradeAnalytics(trades)

            # Metrics
            metrics = analytics.calculate_performance_metrics()

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Win Rate", f"{metrics['win_rate']:.1f}%")
            with col2:
                st.metric("Total P&L", f"${metrics['total_pnl']:.2f}")
            with col3:
                st.metric("Profit Factor", f"{metrics['profit_factor']:.2f}")
            with col4:
                st.metric("Expectancy", f"${metrics['expectancy']:.2f}")

            # Performance report
            st.subheader("Performance Report")
            st.text(analytics.generate_report())

            # Performance by strategy
            st.subheader("Performance by Strategy")
            strategy_perf = analytics.performance_by_strategy()
            if not strategy_perf.empty:
                st.dataframe(strategy_perf, use_container_width=True)

    with tab3:
        render_trade_journal()


if __name__ == "__main__":
    main()
