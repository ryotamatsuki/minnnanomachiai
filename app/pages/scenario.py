"""
Scenario page — Urban simulation.
Draw facilities/roads on map and see the impact on accessibility and flow index.
"""

import json

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from app.components.map_viewer import (
    create_base_map,
    add_isochrone_layer,
    add_diff_layer,
    render_map,
)
from app.components.stats_card import stat_card, estimation_notice


def render_scenario():
    """Render the Scenario page."""
    st.markdown("## 🔬 Scenario — 都市シミュレーション")
    st.markdown(
        "地図上に施設や道路を描き、到達圏や人流指数の変化を予測します。"
    )

    estimation_notice()

    place_name = st.session_state.get("place_name", "Chiyoda, Tokyo, Japan")

    # --- Layout ---
    col_params, col_map = st.columns([1, 3])

    with col_params:
        st.markdown("### 🏗️ 介入パラメータ")

        intervention_type = st.selectbox(
            "介入タイプ",
            ["施設新設", "道路新設/改良"],
        )

        if intervention_type == "施設新設":
            fac_name = st.text_input("施設名", "新商業施設")
            fac_category = st.selectbox("用途カテゴリ", [
                "commercial（商業）",
                "public（公共）",
                "residential（住宅）",
                "industrial（産業）",
                "tourism（観光）",
            ])
            fac_lat = st.number_input("緯度", value=35.694, format="%.6f", key="fac_lat")
            fac_lon = st.number_input("経度", value=139.756, format="%.6f", key="fac_lon")
            fac_floors = st.slider("階数", 1, 50, 5)
            fac_radius = st.slider("敷地半径 (m)", 10, 500, 50)
            fac_attraction = st.slider("魅力度スコア", 0, 100, 50,
                                       help="POI集積度、類似施設の集客力等から設定")
        else:
            road_name = st.text_input("道路名", "新設道路")
            road_type = st.selectbox("道路種別", ["residential", "secondary", "primary"])
            road_speed = st.slider("想定速度 (km/h)", 10, 80, 30)
            st.info("地図上にラインを描画してください")

        st.markdown("---")
        st.markdown("### ⚙️ 計算設定")
        walk_speed = st.slider("歩行速度 (km/h)", 1.0, 6.0, 4.0, 0.5)
        iso_minutes = st.multiselect("到達圏 (分)", [5, 10, 15, 20, 30], default=[5, 10, 15])

        run_sim = st.button("🚀 シミュレーション実行", type="primary", use_container_width=True)

    with col_map:
        # Create map with draw tools
        m = create_base_map(draw_tools=True)
        map_result = render_map(m, height=500, key="scenario_map")

    # --- Run Simulation ---
    if run_sim:
        with st.spinner("🔄 シミュレーション実行中..."):
            _run_simulation(
                place_name=place_name,
                intervention_type=intervention_type,
                params=_collect_params(locals()),
                walk_speed=walk_speed,
                iso_minutes=iso_minutes,
                map_drawings=map_result,
            )


def _collect_params(local_vars: dict) -> dict:
    """Collect intervention parameters from local variables."""
    params = {}
    for key in ["fac_name", "fac_category", "fac_lat", "fac_lon",
                 "fac_floors", "fac_radius", "fac_attraction",
                 "road_name", "road_type", "road_speed"]:
        if key in local_vars:
            params[key] = local_vars[key]
    return params


def _run_simulation(
    place_name: str,
    intervention_type: str,
    params: dict,
    walk_speed: float,
    iso_minutes: list[int],
    map_drawings: dict,
):
    """Execute simulation and display results."""
    try:
        from shapely.geometry import Point, LineString
        from src.connectors.osm import get_road_network, get_pois, get_buildings, get_boundary
        from src.simulation.scenario_engine import (
            run_scenario,
            FacilityIntervention,
            RoadIntervention,
        )
        import geopandas as gpd
        import numpy as np

        # Get road network
        G = get_road_network(place_name, "walk")
        pois = get_pois(place_name)
        boundary = get_boundary(place_name)

        # Create origin/destination grid
        bounds = boundary.total_bounds
        nx_grid, ny_grid = 5, 5
        xs = np.linspace(bounds[0], bounds[2], nx_grid + 1)
        ys = np.linspace(bounds[1], bounds[3], ny_grid + 1)

        zones = []
        from shapely.geometry import box
        for i in range(nx_grid):
            for j in range(ny_grid):
                zone_geom = box(xs[i], ys[j], xs[i + 1], ys[j + 1])
                zones.append({
                    "geometry": zone_geom,
                    "population": np.random.randint(100, 5000),
                    "attraction": 1,
                })
        zones_gdf = gpd.GeoDataFrame(zones, crs="EPSG:4326")

        # Build interventions
        facilities = []
        roads = []

        if intervention_type == "施設新設":
            cat = params.get("fac_category", "commercial").split("（")[0]
            geom = Point(params["fac_lon"], params["fac_lat"]).buffer(
                params.get("fac_radius", 50) / 111000
            )
            facilities.append(FacilityIntervention(
                geometry=geom,
                name=params.get("fac_name", "新施設"),
                category=cat,
                floors=params.get("fac_floors", 3),
                estimated_attraction=params.get("fac_attraction", 50),
            ))
            center_point = (params["fac_lat"], params["fac_lon"])
        else:
            # Use drawn line from map, or default
            drawn_coords = _extract_line_from_drawings(map_drawings)
            if drawn_coords:
                roads.append(RoadIntervention(
                    geometry=LineString(drawn_coords),
                    name=params.get("road_name", "新道路"),
                    road_type=params.get("road_type", "residential"),
                    speed_kmh=params.get("road_speed", 30),
                ))
            else:
                # Default demo road
                center_lat = (bounds[1] + bounds[3]) / 2
                center_lon = (bounds[0] + bounds[2]) / 2
                roads.append(RoadIntervention(
                    geometry=LineString([
                        (center_lon - 0.005, center_lat),
                        (center_lon + 0.005, center_lat),
                    ]),
                    name=params.get("road_name", "新道路"),
                    road_type=params.get("road_type", "residential"),
                ))
            center_point = ((bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2)

        # Run simulation
        result = run_scenario(
            G=G,
            center_point=center_point,
            origins=zones_gdf,
            destinations=zones_gdf.copy(),
            pois=pois,
            facilities=facilities,
            roads=roads,
            minutes=iso_minutes,
            speed_kmh=walk_speed,
        )

        # === Display Results ===
        st.markdown("---")
        st.markdown("### 📊 シミュレーション結果")
        estimation_notice()

        # Summary metrics
        cols = st.columns(4)
        with cols[0]:
            stat_card("人流指数変化", f"{result.summary.get('flow_change_pct', 0):+.1f}%",
                      "重力モデル推定", is_estimate=True)
        with cols[1]:
            stat_card("追加施設", f"{result.summary.get('facilities_added', 0)} 件",
                      "ユーザー入力")
        with cols[2]:
            stat_card("追加道路", f"{result.summary.get('roads_added', 0)} 本",
                      "ユーザー入力")
        with cols[3]:
            total_before = result.summary.get("total_flow_before", 0)
            total_after = result.summary.get("total_flow_after", 0)
            stat_card("総人流指数", f"{total_after:.0f}",
                      f"変化前: {total_before:.0f}", is_estimate=True)

        # Diff map
        if not result.iso_diff.empty:
            st.markdown("#### 🗺️ 到達圏差分マップ")
            diff_map = create_base_map(center=center_point)
            diff_map = add_isochrone_layer(diff_map, result.iso_before, "到達圏（前）")
            diff_map = add_diff_layer(diff_map, result.iso_diff)
            render_map(diff_map, height=400, key="diff_map")

            st.markdown("""
            <div style="display: flex; gap: 1rem; margin: 0.5rem 0;">
                <span style="color: #43e97b;">🟢 拡大エリア</span>
                <span style="color: #ff6464;">🔴 縮小エリア</span>
                <span style="color: #888;">⚪ 変化なし</span>
            </div>
            """, unsafe_allow_html=True)

        # Flow diff chart
        if not result.flow_diff.empty:
            st.markdown("#### 📈 人流指数差分分布")
            fig = go.Figure()
            fig.add_trace(go.Histogram(
                x=result.flow_diff["delta_index"],
                nbinsx=30,
                marker_color="#667eea",
                opacity=0.7,
                name="差分分布",
            ))
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(title="人流指数差分（Δ）", gridcolor="rgba(255,255,255,0.05)"),
                yaxis=dict(title="OD ペア数", gridcolor="rgba(255,255,255,0.05)"),
                height=300,
                margin=dict(l=20, r=20, t=20, b=20),
            )
            st.plotly_chart(fig, use_container_width=True)

        # Benefited population
        if result.benefited_population:
            st.markdown("#### 👥 恩恵人口（属性別）")
            pop_data = []
            for minutes, vals in result.benefited_population.items():
                pop_data.append({
                    "到達圏 (分)": minutes,
                    "変化前": vals.get("before", 0),
                    "変化後": vals.get("after", 0),
                    "増減": vals.get("delta", 0),
                })
            pop_df = pd.DataFrame(pop_data)
            st.dataframe(pop_df, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"❌ シミュレーションエラー: {e}")
        st.exception(e)


def _extract_line_from_drawings(map_result: dict) -> list | None:
    """Extract line coordinates from Folium draw result."""
    if not map_result:
        return None

    drawings = map_result.get("all_drawings")
    if not drawings:
        return None

    for feature in drawings:
        geom = feature.get("geometry", {})
        if geom.get("type") == "LineString":
            return geom.get("coordinates")
        elif geom.get("type") == "Polygon":
            return geom.get("coordinates", [[]])[0]

    return None
