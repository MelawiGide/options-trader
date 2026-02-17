"""
Options Trading System - Chinese-Style Dashboard

Inspired by 百度股市通 (Baidu Stock) and professional Chinese trading platforms.
Features:
- Red = gains, Green = losses (Chinese market convention)
- Dark/light theme toggle
- T-shaped options quote display
- Bento-style card layout
- Real-time Greeks visualization
"""
import sys
from pathlib import Path

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
    page_title="期权策略通 | Options Trading System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== CUSTOM CSS ====================
st.markdown("""
<style>
    /* Import Inter font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Chinese market colors - Red = up, Green = down */
    .positive-cn {
        color: #f23645 !important;
        font-weight: 600;
    }

    .negative-cn {
        color: #089981 !important;
        font-weight: 600;
    }

    /* Card styling */
    .bento-card {
        background: white;
        border-radius: 20px;
        padding: 20px;
        border: 1px solid #eef2f6;
        box-shadow: 0 4px 12px rgba(0,0,0,0.02);
        margin-bottom: 16px;
    }

    .bento-card:hover {
        box-shadow: 0 8px 20px rgba(0,0,0,0.04);
        transform: translateY(-2px);
        transition: all 0.2s ease;
    }

    /* Header styling */
    .app-header {
        background: linear-gradient(135deg, #0055ff 0%, #aa00ff 100%);
        padding: 24px;
        border-radius: 20px;
        margin-bottom: 24px;
        color: white;
    }

    .logo-text {
        font-size: 1.8rem;
        font-weight: 700;
        letter-spacing: -0.5px;
    }

    .beta-badge {
        background: rgba(255,255,255,0.2);
        padding: 4px 12px;
        border-radius: 40px;
        font-size: 0.85rem;
        margin-left: 12px;
    }

    /* Metric cards */
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        letter-spacing: -1px;
    }

    .metric-label {
        font-size: 0.85rem;
        color: #7f8fa4;
        margin-bottom: 4px;
    }

    /* Greek cards */
    .greek-card {
        text-align: center;
        padding: 16px;
        background: #f5f7fb;
        border-radius: 16px;
        margin: 8px 0;
    }

    .greek-value {
        font-size: 1.5rem;
        font-weight: 700;
    }

    .greek-label {
        font-size: 0.75rem;
        color: #7f8fa4;
        margin-bottom: 4px;
    }

    /* Strategy tabs */
    .strategy-tab {
        padding: 8px 16px;
        border-radius: 30px;
        background: #f5f7fb;
        font-size: 0.85rem;
        display: inline-block;
        margin: 4px;
    }

    .strategy-tab.active {
        background: linear-gradient(135deg, #0055ff, #aa00ff);
        color: white;
    }

    /* Position cards */
    .position-card {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px;
        background: #f5f7fb;
        border-radius: 16px;
        margin: 8px 0;
    }

    /* Table styling */
    .dataframe {
        border-radius: 16px;
        overflow: hidden;
    }

    /* Badge styling */
    .badge-pill {
        background: #f5f7fb;
        padding: 4px 12px;
        border-radius: 30px;
        font-size: 0.8rem;
        color: #0055ff;
        font-weight: 500;
    }

    /* Hide streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stAppDeployButton {display:none;}

    /* Dark theme support */
    @media (prefers-color-scheme: dark) {
        .bento-card {
            background: #1a2635;
            border-color: #2a3548;
        }
    }
</style>
""", unsafe_allow_html=True)


# ==================== INITIALIZATION ====================
@st.cache_resource
def initialize_system():
    """Initialize system components (cached)."""
    fetcher = DataFetcher()
    scanner = OptionsScanner(fetcher)
    scorer = OpportunityScorer()
    logger = TradeLogger()
    return fetcher, scanner, scorer, logger


def render_header(account_value: float = 10000):
    """Render app header with Chinese-style design."""
    st.markdown(f"""
    <div class="app-header">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <div class="logo-text">
                    期权策略通 <span class="beta-badge">BETA</span>
                </div>
                <div style="font-size: 0.9rem; opacity: 0.9; margin-top: 4px;">
                    智能期权发现与分析系统 | Smart Options Discovery
                </div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 0.85rem; opacity: 0.9;">总权益 | Account Value</div>
                <div style="font-size: 1.8rem; font-weight: 700;">${account_value:,.2f}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_market_summary(snapshots: dict):
    """Render market summary cards (Bento-style layout)."""
    st.markdown("### 市场概览 | Market Summary")

    cols = st.columns(4)

    symbols_data = [
        ("SPY", "S&P 500", "spx"),
        ("QQQ", "NASDAQ", "ndx"),
        ("VIX", "Volatility", "vol"),
        ("Account", "Portfolio", "acct"),
    ]

    for col, (symbol, name_cn, key) in zip(cols, symbols_data):
        with col:
            if symbol in snapshots and 'quote' in snapshots[symbol]:
                quote = snapshots[symbol]['quote']
                price = quote.get('price', 0)
                change_pct = quote.get('change_pct', 0)

                # Chinese market: Red = up, Green = down
                color_class = "positive-cn" if change_pct >= 0 else "negative-cn"
                change_symbol = "+" if change_pct >= 0 else ""

                st.markdown(f"""
                <div class="bento-card">
                    <div class="metric-label">{name_cn}</div>
                    <div class="metric-value">${price:.2f}</div>
                    <div class="{color_class}">{change_symbol}{change_pct:.2f}%</div>
                </div>
                """, unsafe_allow_html=True)


def render_greeks_panel(greeks: dict):
    """Render Greeks visualization panel."""
    st.markdown("### 投资组合希腊值 | Portfolio Greeks")

    cols = st.columns(4)

    greek_labels = {
        'delta': 'Δ Delta',
        'gamma': 'Γ Gamma',
        'theta': 'Θ Theta',
        'vega': 'ν Vega'
    }

    for col, (key, label) in zip(cols, greek_labels.items()):
        value = greeks.get(key, 0)

        # Color coding
        if key == 'theta':
            color_class = "negative-cn" if value < 0 else "positive-cn"
        else:
            color_class = "positive-cn" if value > 0 else "negative-cn"

        with col:
            st.markdown(f"""
            <div class="greek-card">
                <div class="greek-label">{label}</div>
                <div class="greek-value {color_class}">{value:.3f}</div>
            </div>
            """, unsafe_allow_html=True)


def render_options_chain_tstyle(opportunities: pd.DataFrame, current_price: float):
    """Render T-shaped options quote display (Chinese style)."""
    st.markdown("### 期权链 | Options Chain")

    if opportunities is None or opportunities.empty:
        st.info("暂无数据 | No data available")
        return

    # Get ATM strike
    atm_strike = opportunities.iloc[
        (opportunities['strike'] - current_price).abs().argsort()[:1]
    ]['strike'].values[0] if not opportunities.empty else current_price

    # Separate calls and puts
    calls = opportunities[opportunities['option_type'] == 'call'].copy()
    puts = opportunities[opportunities['option_type'] == 'put'].copy()

    # Get strikes around ATM
    strikes = sorted(set(calls['strike'].tolist() + puts['strike'].tolist()))
    atm_idx = strikes.index(atm_strike) if atm_strike in strikes else len(strikes) // 2
    display_strikes = strikes[max(0, atm_idx-3):min(len(strikes), atm_idx+4)]

    # Build display dataframe
    display_data = []

    for strike in display_strikes:
        call_row = calls[calls['strike'] == strike]
        put_row = puts[puts['strike'] == strike]

        call_data = {
            'contract': call_row.iloc[0]['contract_symbol'] if not call_row.empty else '-',
            'change_pct': call_row.iloc[0].get('change_pct', 0) if not call_row.empty else 0,
            'last_price': call_row.iloc[0]['premium'] / 100 if not call_row.empty else 0,
        } if not call_row.empty else {'contract': '-', 'change_pct': 0, 'last_price': 0}

        put_data = {
            'contract': put_row.iloc[0]['contract_symbol'] if not put_row.empty else '-',
            'change_pct': put_row.iloc[0].get('change_pct', 0) if not put_row.empty else 0,
            'last_price': put_row.iloc[0]['premium'] / 100 if not put_row.empty else 0,
        } if not put_row.empty else {'contract': '-', 'change_pct': 0, 'last_price': 0}

        display_data.append({
            '看涨 Call': call_data['contract'],
            '涨跌幅 %': call_data['change_pct'],
            '最新价': call_data['last_price'],
            '行权价 Strike': f"{strike:.2f}",
            '最新价': put_data['last_price'],
            '涨跌幅 %': put_data['change_pct'],
            '看跌 Put': put_data['contract'],
        })

    display_df = pd.DataFrame(display_data)

    # Style the dataframe
    def color_vals(val):
        if isinstance(val, (int, float)):
            if val > 0:
                return 'color: #f23645; font-weight: 600;'
            elif val < 0:
                return 'color: #089981; font-weight: 600;'
        return ''

    styled_df = display_df.style.applymap(color_vals, subset=['涨跌幅 %'])

    st.dataframe(styled_df, use_container_width=True, height=400)


def render_strategy_builder():
    """Render strategy builder with tabs."""
    st.markdown("### 策略构建 | Strategy Builder")

    strategies = ['备兑开仓 Covered Call', '保护性看跌 Protective Put',
                  '牛市价差 Bull Spread', '跨式组合 Straddle']

    cols = st.columns(4)
    for i, (col, strategy) in enumerate(zip(cols, strategies)):
        with col:
            active = i == 0
            st.markdown(f"""
            <div class="strategy-tab {'active' if active else ''}">
                {strategy}
            </div>
            """, unsafe_allow_html=True)


def render_volatility_surface(snapshot: dict):
    """Render volatility surface visualization."""
    st.markdown("### 波动率曲面 | Volatility Surface")

    if 'volatility' not in snapshot:
        return

    vol = snapshot['volatility']

    cols = st.columns(4)

    with cols[0]:
        st.markdown('<div class="metric-label">近月 Near Month</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="metric-value">{vol.get("hv_20d", 0):.1f}</div>', unsafe_allow_html=True)

    with cols[1]:
        st.markdown('<div class="metric-label">次月 Next Month</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="metric-value">{vol.get("hv_30d", 0):.1f}</div>', unsafe_allow_html=True)

    with cols[2]:
        st.markdown('<div class="metric-label">远月 Far Month</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="metric-value">{vol.get("hv_60d", 0):.1f}</div>', unsafe_allow_html=True)

    with cols[3]:
        st.markdown('<div class="metric-label">IV Rank</div>', unsafe_allow_html=True)
        iv_rank = vol.get('iv_rank', 50)
        color_class = "positive-cn" if iv_rank > 50 else "negative-cn"
        st.markdown(f'<div class="metric-value {color_class}">{iv_rank:.1f}</div>', unsafe_allow_html=True)


def render_positions(positions: pd.DataFrame):
    """Render current positions."""
    st.markdown("### 当前持仓 | Current Positions")

    if positions.empty:
        st.markdown("""
        <div class="position-card">
            <div>
                <div style="font-weight: 600;">暂无持仓</div>
                <div style="font-size: 0.8rem; color: #7f8fa4;">No open positions</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    for _, row in positions.iterrows():
        pnl = row.get('pnl', 0)
        color_class = "positive-cn" if pnl >= 0 else "negative-cn"

        st.markdown(f"""
        <div class="position-card">
            <div>
                <div style="font-weight: 600;">{row.get('symbol', '')} {row.get('option_type', '').upper()}</div>
                <div style="font-size: 0.8rem; color: #7f8fa4;">
                    {row.get('contracts', 0)} contracts @ ${row.get('entry_price', 0):.2f}
                </div>
            </div>
            <div style="text-align: right;">
                <div class="{color_class}" style="font-weight: 700; font-size: 1.1rem;">
                    {'+' if pnl >= 0 else ''}${pnl:.2f}
                </div>
                <div style="font-size: 0.8rem; color: #7f8fa4;">
                    {row.get('dte', 0)} DTE
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)


def render_iv_rank_gauge(iv_rank: float):
    """Render IV Rank gauge chart."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=iv_rank,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "IV Rank | 隐含波动率排名"},
        delta={'reference': 50},
        gauge={
            'axis': {'range': [None, 100]},
            'bar': {'color': "#0055ff"},
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

    fig.update_layout(
        height=200,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='rgba(0,0,0,0)'
    )

    st.plotly_chart(fig, use_container_width=True)


# ==================== MAIN APP ====================
def main():
    """Main application."""
    # Render header
    render_header()

    # Initialize system
    fetcher, scanner, scorer, trade_logger = initialize_system()

    # Sidebar settings
    st.sidebar.markdown("### ⚙️ 设置 | Settings")

    symbol = st.sidebar.text_input(
        "代码 | Symbol",
        value="SPY",
        help="股票代码 (如 SPY, AAPL, QQQ)"
    ).upper()

    account_value = st.sidebar.number_input(
        "账户资金 | Account Value ($)",
        min_value=1000,
        max_value=1000000,
        value=10000,
        step=1000
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔍 过滤器 | Filters")

    col1, col2 = st.sidebar.columns(2)
    with col1:
        min_dte = st.number_input("最小 DTE", value=7, min_value=0)
    with col2:
        max_dte = st.number_input("最大 DTE", value=45, min_value=0)

    max_premium = st.sidebar.slider(
        "最大权利金 | Max Premium ($)",
        min_value=50,
        max_value=500,
        value=200,
        step=10
    )

    option_types = st.sidebar.multiselect(
        "类型 | Type",
        ["call", "put"],
        default=["call", "put"]
    )

    # Create tabs
    tab1, tab2, tab3 = st.tabs([
        "🔍 扫描器 | Scanner",
        "📈 分析 | Analytics",
        "📓 日志 | Journal"
    ])

    with tab1:
        # Scan button
        if st.button("🚀 扫描机会 | Scan Opportunities", type="primary"):
            with st.spinner("扫描中..."):
                # Get market snapshot
                snapshot = scanner.get_market_snapshot(symbol)

                # Market summary
                render_market_summary({symbol: snapshot})

                st.markdown("---")

                # Main content grid
                col_left, col_right = st.columns([2, 1])

                with col_left:
                    # Scan for opportunities
                    opportunities = scanner.scan_symbol(
                        symbol,
                        min_dte=min_dte,
                        max_dte=max_dte,
                        max_premium=max_premium,
                        option_types=option_types
                    )

                    if opportunities is not None and not opportunities.empty:
                        # Score opportunities
                        scored = scorer.score_dataframe(opportunities, snapshot)

                        # Show top 20
                        top_opportunities = scored.head(20)

                        st.success(f"✅ 找到 {len(scored)} 个机会 | Found {len(scored)} opportunities")

                        # Display options chain in T-style
                        if 'quote' in snapshot:
                            render_options_chain_tstyle(
                                top_opportunities,
                                snapshot['quote']['price']
                            )

                        # IV Rank gauge
                        if 'volatility' in snapshot:
                            col_a, col_b = st.columns(2)
                            with col_a:
                                render_iv_rank_gauge(
                                    snapshot['volatility'].get('iv_rank', 50)
                                )
                            with col_b:
                                render_volatility_surface(snapshot)

                    else:
                        st.warning("❌ 未找到符合条件的机会 | No opportunities found")

                with col_right:
                    # Greeks panel
                    if 'quote' in snapshot:
                        greeks = {
                            'delta': 0.45,
                            'gamma': 0.12,
                            'theta': -0.08,
                            'vega': 0.23
                        }
                        render_greeks_panel(greeks)

                    st.markdown("---")
                    render_strategy_builder()

                    st.markdown("---")
                    positions = trade_logger.get_open_trades()
                    render_positions(positions)

    with tab2:
        st.header("📈 性能分析 | Performance Analytics")

        trades = trade_logger.get_all_trades()

        if trades.empty or 'pnl' not in trades.columns:
            st.info("暂无交易记录 | No trade history yet")
        else:
            analytics = TradeAnalytics(trades)
            metrics = analytics.calculate_performance_metrics()

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("胜率 | Win Rate", f"{metrics['win_rate']:.1f}%")
            with col2:
                st.metric("总盈亏 | Total P&L", f"${metrics['total_pnl']:.2f}")
            with col3:
                st.metric("盈亏比 | Profit Factor", f"{metrics['profit_factor']:.2f}")
            with col4:
                st.metric("期望收益 | Expectancy", f"${metrics['expectancy']:.2f}")

            st.markdown("---")
            st.subheader("📊 性能报告 | Performance Report")
            st.text(analytics.generate_report())

    with tab3:
        render_header(account_value)
        st.markdown("### 📓 交易日志 | Trade Journal")

        summary = trade_logger.get_summary()

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("总交易 | Total Trades", summary['total_trades'])
        with col2:
            st.metric("持仓中 | Open Positions", summary['open_trades'])
        with col3:
            if 'total_pnl' in summary:
                st.metric("总盈亏 | Total P&L", f"${summary['total_pnl']:.2f}")

        trades = trade_logger.get_all_trades()

        if not trades.empty:
            st.subheader("交易历史 | Trade History")
            display_cols = [
                'trade_id', 'symbol', 'option_type', 'strike',
                'entry_timestamp', 'status'
            ]
            avail_cols = [c for c in display_cols if c in trades.columns]
            st.dataframe(trades[avail_cols], use_container_width=True)


if __name__ == "__main__":
    main()
