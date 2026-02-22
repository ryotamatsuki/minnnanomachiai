"""
Stats card component.
Displays metric cards with source citations.
"""

import streamlit as st


def stat_card(label: str, value: str, source: str = "", delta: str = "", is_estimate: bool = False):
    """
    Render a styled stat card.

    Args:
        label: Metric label
        value: Metric value
        source: Data source citation
        delta: Change indicator text
        is_estimate: Whether to show estimation badge
    """
    estimate_badge = '<span class="estimation-badge">推定</span>' if is_estimate else ""
    delta_html = f'<div style="color: {"#43e97b" if delta.startswith("+") else "#ff6464"}; font-size: 0.85rem;">{delta}</div>' if delta else ""

    st.markdown(f"""
    <div class="stat-card">
        <h3>{label} {estimate_badge}</h3>
        <div class="value">{value}</div>
        {delta_html}
        <div class="source">出典: {source}</div>
    </div>
    """, unsafe_allow_html=True)


def evidence_tag(evidence_id: str, source: str = ""):
    """Render an evidence ID tag."""
    st.markdown(
        f'<span class="evidence-tag">📎 {evidence_id}: {source}</span>',
        unsafe_allow_html=True,
    )


def hypothesis_box(text: str):
    """Render a hypothesis (unverified claim) box."""
    st.markdown(
        f'<div class="hypothesis-box">⚠️ 仮説（未検証）: {text}</div>',
        unsafe_allow_html=True,
    )


def estimation_notice():
    """Show the mandatory estimation notice."""
    st.markdown("""
    <div style="
        background: rgba(255, 165, 0, 0.08);
        border: 1px solid rgba(255, 165, 0, 0.2);
        border-radius: 8px;
        padding: 0.6rem 1rem;
        font-size: 0.8rem;
        color: #ffa500;
        margin: 0.5rem 0;
    ">
        ⚠️ 本指標は公表データに基づく推定値です。人流指数は相対的な指標であり、実測値ではありません。
    </div>
    """, unsafe_allow_html=True)
