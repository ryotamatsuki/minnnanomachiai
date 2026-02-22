"""
みんなのまちAI風 — Streamlit Main Entry
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

# --- Page Config ---
st.set_page_config(
    page_title="みんなのまちAI風",
    page_icon="🏙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Custom CSS ---
st.markdown("""
<style>
    /* Global */
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700&display=swap');

    html, body, [class*="st-"] {
        font-family: 'Noto Sans JP', sans-serif;
    }

    /* Header gradient */
    .main-header {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        color: white;
    }
    .main-header h1 {
        margin: 0;
        font-size: 1.8rem;
        font-weight: 700;
        letter-spacing: 0.05em;
    }
    .main-header p {
        margin: 0.3rem 0 0 0;
        font-size: 0.9rem;
        opacity: 0.8;
    }

    /* Nav pills */
    .nav-container {
        display: flex;
        gap: 0.5rem;
        margin-bottom: 1rem;
    }
    .nav-pill {
        padding: 0.5rem 1.2rem;
        border-radius: 20px;
        cursor: pointer;
        font-weight: 500;
        font-size: 0.9rem;
        transition: all 0.3s ease;
    }
    .nav-pill-active {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
    }
    .nav-pill-inactive {
        background: rgba(255,255,255,0.05);
        color: #aaa;
        border: 1px solid rgba(255,255,255,0.1);
    }

    /* Cards */
    .stat-card {
        background: linear-gradient(145deg, #1a1a2e, #16213e);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 0.8rem;
    }
    .stat-card h3 {
        font-size: 0.85rem;
        color: #888;
        margin: 0 0 0.3rem 0;
        font-weight: 400;
    }
    .stat-card .value {
        font-size: 1.8rem;
        font-weight: 700;
        background: linear-gradient(to right, #667eea, #764ba2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .stat-card .source {
        font-size: 0.7rem;
        color: #666;
        margin-top: 0.3rem;
    }

    /* Estimation badge */
    .estimation-badge {
        display: inline-block;
        background: rgba(255, 165, 0, 0.15);
        color: #ffa500;
        padding: 0.2rem 0.6rem;
        border-radius: 4px;
        font-size: 0.75rem;
        margin-left: 0.5rem;
        border: 1px solid rgba(255, 165, 0, 0.3);
    }

    /* Evidence tag */
    .evidence-tag {
        display: inline-block;
        background: rgba(102, 126, 234, 0.15);
        color: #667eea;
        padding: 0.15rem 0.5rem;
        border-radius: 4px;
        font-size: 0.7rem;
        margin: 0.1rem;
        border: 1px solid rgba(102, 126, 234, 0.3);
    }

    /* Hypothesis box */
    .hypothesis-box {
        background: rgba(255, 100, 100, 0.08);
        border-left: 3px solid #ff6464;
        padding: 0.8rem 1rem;
        border-radius: 0 8px 8px 0;
        margin: 0.5rem 0;
        font-size: 0.85rem;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f0c29, #1a1a2e);
    }

    /* Hide default header padding */
    .block-container {
        padding-top: 1rem;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 8px 20px;
    }
</style>
""", unsafe_allow_html=True)

# --- Header ---
st.markdown("""
<div class="main-header">
    <h1>🏙️ みんなのまちAI 風</h1>
    <p>都市データ可視化 ・ シミュレーション ・ EBPM支援プラットフォーム</p>
</div>
""", unsafe_allow_html=True)

# --- Sidebar Navigation ---
with st.sidebar:
    st.markdown("### 🧭 ナビゲーション")
    page = st.radio(
        "画面を選択",
        ["🗺️ Explore", "🔬 Scenario", "📋 Budget Draft"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown("### ⚙️ 設定")
    place_name = st.text_input(
        "対象エリア",
        value="Chiyoda, Tokyo, Japan",
        help="OSM / Geocoding で使用する地名",
    )
    st.session_state["place_name"] = place_name

    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #666; font-size: 0.75rem;'>"
        "みんなのまちAI風 v0.1.0<br>"
        "公表データに基づく推定ツール<br>"
        "© 2026 Open Source Project"
        "</div>",
        unsafe_allow_html=True,
    )

# --- Page Routing ---
if page == "🗺️ Explore":
    from app.pages.explore import render_explore
    render_explore()
elif page == "🔬 Scenario":
    from app.pages.scenario import render_scenario
    render_scenario()
elif page == "📋 Budget Draft":
    from app.pages.budget import render_budget
    render_budget()
