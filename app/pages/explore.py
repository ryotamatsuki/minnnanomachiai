"""
Explore page — Urban data visualization.
Displays multiple data layers on a map with statistical panels.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from app.components.map_viewer import (
    create_base_map,
    add_geojson_layer,
    add_isochrone_layer,
    render_map,
    LAYER_COLORS,
)
from app.components.stats_card import stat_card, estimation_notice


# Layer definitions
LAYERS = {
    "poi": {"name": "📍 POI（施設）", "source": "OpenStreetMap"},
    "transit": {"name": "🚆 公共交通（駅・バス停）", "source": "OpenStreetMap"},
    "buildings": {"name": "🏢 建物", "source": "OpenStreetMap"},
    "boundary": {"name": "🗺️ 行政界", "source": "OpenStreetMap"},
}


def render_explore():
    """Render the Explore page."""
    st.markdown("## 🗺️ Explore — 都市データ統合ビューア")
    st.markdown(
        "地図上に複数のデータレイヤを重ね、地域の特性を多角的に分析します。"
    )

    place_name = st.session_state.get("place_name", "Chiyoda, Tokyo, Japan")

    # --- Layer Selection ---
    col_layers, col_map = st.columns([1, 3])

    with col_layers:
        st.markdown("### レイヤ選択")
        selected_layers = []
        for layer_id, layer_info in LAYERS.items():
            if st.checkbox(layer_info["name"], value=(layer_id == "boundary"), key=f"layer_{layer_id}"):
                selected_layers.append(layer_id)

        st.markdown("---")
        st.markdown("### 到達圏分析")
        show_isochrone = st.checkbox("🔵 到達圏を表示")
        if show_isochrone:
            iso_center_lat = st.number_input("中心 緯度", value=35.694, format="%.6f", key="iso_lat")
            iso_center_lon = st.number_input("中心 経度", value=139.754, format="%.6f", key="iso_lon")
            iso_speed = st.selectbox(
                "移動手段",
                ["徒歩 (4km/h)", "自転車 (12km/h)", "高齢者徒歩 (3km/h)"],
            )
            speed_map = {"徒歩 (4km/h)": 4.0, "自転車 (12km/h)": 12.0, "高齢者徒歩 (3km/h)": 3.0}
            walk_speed = speed_map.get(iso_speed, 4.0)

    with col_map:
        # Create map
        m = create_base_map()

        # Load and display selected layers
        loaded_data = {}
        for layer_id in selected_layers:
            with st.spinner(f"{LAYERS[layer_id]['name']} を読み込み中..."):
                try:
                    gdf = _load_layer(layer_id, place_name)
                    if gdf is not None and not gdf.empty:
                        loaded_data[layer_id] = gdf
                        tooltip_cols = _get_tooltip_cols(layer_id, gdf)
                        m = add_geojson_layer(m, gdf, LAYERS[layer_id]["name"],
                                              color=LAYER_COLORS.get(layer_id),
                                              tooltip_columns=tooltip_cols)
                except Exception as e:
                    st.warning(f"⚠️ {LAYERS[layer_id]['name']} の読み込みに失敗: {e}")

        # Add isochrone
        if show_isochrone:
            with st.spinner("到達圏を計算中..."):
                try:
                    from src.connectors.osm import get_road_network
                    from src.indicators.accessibility import compute_isochrone

                    G = get_road_network(place_name, "walk")
                    iso_gdf = compute_isochrone(
                        G, (iso_center_lat, iso_center_lon),
                        minutes=[5, 10, 15],
                        speed_kmh=walk_speed,
                    )
                    m = add_isochrone_layer(m, iso_gdf)
                except Exception as e:
                    st.warning(f"⚠️ 到達圏計算に失敗: {e}")

        # Render map
        map_data = render_map(m, height=550, key="explore_map")

    # --- Stats Panel ---
    st.markdown("---")
    st.markdown("### 📊 地域統計")

    cols = st.columns(4)

    # Show stats for loaded layers
    for i, (layer_id, gdf) in enumerate(loaded_data.items()):
        with cols[i % 4]:
            stat_card(
                label=LAYERS[layer_id]["name"],
                value=f"{len(gdf):,} 件",
                source=LAYERS[layer_id]["source"],
            )

    # Show isochrone stats
    if show_isochrone and "iso_gdf" in dir() and not iso_gdf.empty:
        estimation_notice()
        for _, row in iso_gdf.iterrows():
            with cols[0]:
                stat_card(
                    label=f"到達圏 {int(row['minutes'])}分",
                    value=f"{row.get('node_count', '?')} ノード",
                    source="OSMnx ネットワーク分析",
                    is_estimate=True,
                )

    # --- Demo Charts ---
    st.markdown("---")
    st.markdown("### 📈 指標ダッシュボード")

    tab1, tab2 = st.tabs(["時系列推移", "地域比較"])

    with tab1:
        _render_timeseries_chart()

    with tab2:
        _render_comparison_chart()


def _load_layer(layer_id: str, place_name: str):
    """Load a data layer."""
    if layer_id == "poi":
        from src.connectors.osm import get_pois
        return get_pois(place_name)
    elif layer_id == "transit":
        from src.connectors.osm import get_transit_stops
        return get_transit_stops(place_name)
    elif layer_id == "buildings":
        from src.connectors.osm import get_buildings
        gdf = get_buildings(place_name)
        # Limit to 2000 for performance
        if len(gdf) > 2000:
            gdf = gdf.head(2000)
        return gdf
    elif layer_id == "boundary":
        from src.connectors.osm import get_boundary
        return get_boundary(place_name)
    return None


def _get_tooltip_cols(layer_id: str, gdf) -> list[str]:
    """Get relevant tooltip columns for a layer."""
    candidates = {
        "poi": ["name", "amenity", "shop", "tourism"],
        "transit": ["name", "railway", "highway"],
        "buildings": ["name", "building"],
        "boundary": ["display_name"],
    }
    cols = candidates.get(layer_id, [])
    return [c for c in cols if c in gdf.columns]


def _render_timeseries_chart():
    """Render a demo time series chart."""
    # Demo data
    years = list(range(2015, 2026))
    data = pd.DataFrame({
        "年": years,
        "人口": [68000, 67500, 67200, 66800, 66500, 66000, 65800, 65500, 65200, 65000, 64800],
        "世帯数": [38000, 38500, 39000, 39200, 39500, 39800, 40000, 40200, 40500, 40700, 41000],
        "事業所数": [8500, 8400, 8350, 8300, 8250, 8200, 8150, 8100, 8050, 8000, 7980],
    })

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data["年"], y=data["人口"], name="人口",
                             line=dict(color="#667eea", width=3),
                             fill="tozeroy", fillcolor="rgba(102,126,234,0.1)"))
    fig.add_trace(go.Scatter(x=data["年"], y=data["世帯数"], name="世帯数",
                             line=dict(color="#43e97b", width=3),
                             yaxis="y2"))
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(title="人口", gridcolor="rgba(255,255,255,0.05)"),
        yaxis2=dict(title="世帯数", overlaying="y", side="right", gridcolor="rgba(255,255,255,0.05)"),
        legend=dict(orientation="h", y=1.12),
        height=350,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("📎 出典: デモデータ（実装時はe-Stat APIから取得）")


def _render_comparison_chart():
    """Render a demo area comparison chart."""
    data = pd.DataFrame({
        "指標": ["人口密度\n(人/km²)", "高齢化率\n(%)", "事業所密度\n(件/km²)", "公共交通\nカバー率(%)", "公園面積\n率(%)"],
        "千代田区": [85, 18, 650, 95, 12],
        "中央区": [120, 16, 580, 92, 8],
        "港区": [95, 14, 520, 90, 15],
    })

    fig = go.Figure()
    colors = ["#667eea", "#43e97b", "#f093fb"]
    for i, area in enumerate(["千代田区", "中央区", "港区"]):
        fig.add_trace(go.Bar(
            name=area,
            x=data["指標"],
            y=data[area],
            marker_color=colors[i],
            opacity=0.85,
        ))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        barmode="group",
        legend=dict(orientation="h", y=1.12),
        height=350,
        margin=dict(l=20, r=20, t=40, b=20),
        yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("📎 出典: デモデータ（実装時はe-Stat APIから取得）")
