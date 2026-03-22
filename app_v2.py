import io
import json

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from vrp_core import build_template_frames, solve_vrp, DEPOTS, STORES, VEHICLES

st.set_page_config(page_title="RouteOptimizer VRPTW+", page_icon="🚚", layout="wide", initial_sidebar_state="expanded")

TRAFFIC_PROFILES = {
    "offpeak": "Вне часа пик",
    "day": "Дневной поток",
    "morning_peak": "Утренний пик",
    "evening_peak": "Вечерний пик",
}
GOAL_LABELS = {
    "time": "Минимум времени",
    "distance": "Минимум расстояния",
    "fleet": "Минимум числа машин",
    "balanced": "Баланс маршрутов",
}
COLORS = ["blue", "green", "red", "purple", "orange", "darkred", "darkblue", "darkgreen", "cadetblue", "darkpurple", "pink", "lightblue", "lightgreen", "gray", "black"]

st.markdown(
    """
<style>
.metric-container {background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px; padding: 18px; color: white; text-align: center; box-shadow: 0 4px 10px rgba(0,0,0,0.12); margin-bottom: 10px;}
.metric-value { font-size: 26px; font-weight: 700; margin: 5px 0; }
.metric-label { font-size: 14px; opacity: 0.92; }
.info-box {background-color: #f8f9fa; border-left: 4px solid #3498db; padding: 15px; border-radius: 6px; margin: 10px 0; color: #2c3e50;}
</style>
""",
    unsafe_allow_html=True,
)

if "depots_df_v2" not in st.session_state:
    depots_df, stores_df, vehicles_df = build_template_frames()
    st.session_state.depots_df_v2 = depots_df
    st.session_state.stores_df_v2 = stores_df
    st.session_state.vehicles_df_v2 = vehicles_df
    st.session_state.solution_v2 = None


def format_time(minutes):
    minutes = int(minutes)
    h = (minutes // 60) % 24
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


def load_tabular(uploaded_file):
    if uploaded_file is None:
        return None
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(uploaded_file)
    raise ValueError("Поддерживаются только CSV и Excel")


def normalize_store_df(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {"pickup": "pickup_demand", "delivery": "demand", "open": "tw_start", "close": "tw_end"}
    df = df.rename(columns=rename_map).copy()
    required = ["id", "name", "address", "lat", "lon", "demand", "pickup_demand", "tw_start", "tw_end", "service_time"]
    for col in required:
        if col not in df.columns:
            if col == "pickup_demand":
                df[col] = 0
            elif col == "service_time":
                df[col] = 20
            else:
                raise ValueError(f"В файле магазинов нет столбца: {col}")
    if "active" not in df.columns:
        df["active"] = True
    return df[["active"] + required]


def normalize_vehicle_df(df: pd.DataFrame, depots_df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    required = ["id", "name", "capacity", "pickup_capacity", "depot_id", "max_shift_min"]
    for col in required:
        if col not in df.columns:
            if col == "pickup_capacity":
                df[col] = df["capacity"] if "capacity" in df.columns else 0
            elif col == "max_shift_min":
                df[col] = 600
            else:
                raise ValueError(f"В файле транспорта нет столбца: {col}")
    if "active" not in df.columns:
        df["active"] = True
    valid_depots = set(depots_df["id"].tolist())
    df["depot_id"] = df["depot_id"].where(df["depot_id"].isin(valid_depots), depots_df.iloc[0]["id"])
    return df[["active"] + required]


def dataframe_to_records(df: pd.DataFrame, kind: str):
    rows = []
    for row in df.to_dict(orient="records"):
        if not row.get("active", True):
            continue
        base = {k: row[k] for k in row if k != "active"}
        if kind in {"store", "depot"}:
            base["time_window"] = (int(base.pop("tw_start")), int(base.pop("tw_end")))
            base["lat"] = float(base["lat"])
            base["lon"] = float(base["lon"])
        if kind == "store":
            base["demand"] = float(base["demand"])
            base["pickup_demand"] = float(base.get("pickup_demand", 0))
            base["service_time"] = int(base["service_time"])
        elif kind == "vehicle":
            base["capacity"] = float(base["capacity"])
            base["pickup_capacity"] = float(base["pickup_capacity"])
            base["max_shift_min"] = int(base["max_shift_min"])
        rows.append(base)
    return rows


def compute_constraints(stores, vehicles):
    total_delivery = sum(s["demand"] for s in stores)
    total_pickup = sum(s.get("pickup_demand", 0) for s in stores)
    total_delivery_cap = sum(v["capacity"] for v in vehicles)
    total_pickup_cap = sum(v.get("pickup_capacity", v["capacity"]) for v in vehicles)
    return {
        "delivery_demand": total_delivery,
        "pickup_demand": total_pickup,
        "delivery_gap": total_delivery_cap - total_delivery,
        "pickup_gap": total_pickup_cap - total_pickup,
    }


def route_export_frames(solution):
    summary_rows, stop_rows = [], []
    for idx, route in enumerate(solution["routes"], start=1):
        summary_rows.append({
            "route_no": idx,
            "vehicle": route["vehicle_type"],
            "depot": route["depot_name"],
            "stops": route["stops_count"],
            "distance_km": round(route["distance"] / 1000, 2),
            "drive_minutes": route["drive_minutes"],
            "service_minutes": route["service_minutes"],
            "waiting_minutes": route["waiting_minutes"],
            "duration_minutes": route["duration"],
            "delivery_used": route["delivery_used"],
            "pickup_used": route["pickup_used"],
            "avg_speed_kmh": route["avg_speed_kmh"],
        })
        for stop in route["stops_detail"]:
            stop_rows.append({
                "route_no": idx,
                "vehicle": route["vehicle_type"],
                "sequence": stop["sequence"],
                "node_type": stop["node_type"],
                "name": stop["name"],
                "address": stop["address"],
                "arrival": format_time(stop["arrival"]),
                "departure": format_time(stop["departure"]),
                "delivery": stop.get("delivery", 0),
                "pickup": stop.get("pickup", 0),
                "waiting_min": stop.get("waiting", 0),
                "service_min": stop.get("service_time", 0),
            })
    return pd.DataFrame(summary_rows), pd.DataFrame(stop_rows)


def build_geojson(solution):
    features = []
    for idx, route in enumerate(solution["routes"], start=1):
        for seg in route["geometry"]:
            if not seg:
                continue
            features.append({
                "type": "Feature",
                "properties": {"route_no": idx, "vehicle": route["vehicle_type"], "depot": route["depot_name"]},
                "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in seg]},
            })
    return {"type": "FeatureCollection", "features": features}


def build_excel_bytes(summary_df, stops_df, unserved_df):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="routes", index=False)
        stops_df.to_excel(writer, sheet_name="stops", index=False)
        if unserved_df is not None and not unserved_df.empty:
            unserved_df.to_excel(writer, sheet_name="unserved", index=False)
    buf.seek(0)
    return buf.getvalue()


st.sidebar.title("🚚 RouteOptimizer+")
st.sidebar.markdown("---")
store_upload = st.sidebar.file_uploader("Загрузить магазины (CSV/XLSX)", type=["csv", "xlsx", "xls"])
vehicle_upload = st.sidebar.file_uploader("Загрузить транспорт (CSV/XLSX)", type=["csv", "xlsx", "xls"])
if store_upload is not None:
    try:
        st.session_state.stores_df_v2 = normalize_store_df(load_tabular(store_upload))
        st.sidebar.success("Магазины загружены")
    except Exception as exc:
        st.sidebar.error(str(exc))
if vehicle_upload is not None:
    try:
        st.session_state.vehicles_df_v2 = normalize_vehicle_df(load_tabular(vehicle_upload), st.session_state.depots_df_v2)
        st.sidebar.success("Транспорт загружен")
    except Exception as exc:
        st.sidebar.error(str(exc))

st.sidebar.header("⚙️ Оптимизация")
goal = st.sidebar.selectbox("Цель оптимизации", list(GOAL_LABELS.keys()), format_func=lambda x: GOAL_LABELS[x])
traffic_profile = st.sidebar.selectbox("Профиль трафика", list(TRAFFIC_PROFILES.keys()), format_func=lambda x: TRAFFIC_PROFILES[x])
max_search_time = st.sidebar.slider("Время поиска, сек", 1, 60, 12)
penalty = st.sidebar.number_input("Штраф за пропуск точки", min_value=1000, max_value=1000000, value=100000, step=5000)
balance_routes = st.sidebar.checkbox("Балансировать маршруты", value=True)
calc = st.sidebar.button("🚀 Рассчитать", type="primary", use_container_width=True)

st.title("🗺️ Gloria Jeans Logistics VRP+")
st.markdown("### Реальные магазины, мультисклады, возвраты, сценарии и аналитика")

tab_data, tab_result = st.tabs(["✏️ Данные", "📊 Результаты"])

with tab_data:
    c_left, c_right = st.columns([1, 2])
    with c_left:
        st.subheader("🏭 Склады")
        st.caption("В проект включены реальные объекты Gloria Jeans в Подольске.")
        st.session_state.depots_df_v2 = st.data_editor(
            st.session_state.depots_df_v2,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            column_config={
                "active": st.column_config.CheckboxColumn("Вкл"),
                "tw_start": st.column_config.NumberColumn("Открытие", min_value=0, max_value=1440, step=5),
                "tw_end": st.column_config.NumberColumn("Закрытие", min_value=0, max_value=1440, step=5),
            },
            key="depots_df_v2_editor",
        )
        st.subheader("🚛 Парк")
        st.session_state.vehicles_df_v2 = st.data_editor(
            st.session_state.vehicles_df_v2,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            column_config={
                "active": st.column_config.CheckboxColumn("В рейс"),
                "capacity": st.column_config.NumberColumn("Доставка, м³", min_value=0.0, step=1.0),
                "pickup_capacity": st.column_config.NumberColumn("Забор, м³", min_value=0.0, step=1.0),
                "max_shift_min": st.column_config.NumberColumn("Смена, мин", min_value=60, max_value=1440, step=30),
                "depot_id": st.column_config.SelectboxColumn("Склад", options=st.session_state.depots_df_v2["id"].tolist()),
            },
            key="vehicles_df_v2_editor",
        )
    with c_right:
        st.subheader("🏬 Магазины")
        st.session_state.stores_df_v2 = st.data_editor(
            st.session_state.stores_df_v2,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            column_config={
                "active": st.column_config.CheckboxColumn("Активен"),
                "demand": st.column_config.NumberColumn("Доставка, м³", min_value=0.0, step=1.0),
                "pickup_demand": st.column_config.NumberColumn("Возвраты, м³", min_value=0.0, step=1.0),
                "tw_start": st.column_config.NumberColumn("Открытие", min_value=0, max_value=1440, step=5),
                "tw_end": st.column_config.NumberColumn("Закрытие", min_value=0, max_value=1440, step=5),
                "service_time": st.column_config.NumberColumn("Разгрузка, мин", min_value=0, max_value=240, step=5),
            },
            key="stores_df_v2_editor",
        )
    stores = dataframe_to_records(st.session_state.stores_df_v2, "store")
    depots = dataframe_to_records(st.session_state.depots_df_v2, "depot")
    vehicles = dataframe_to_records(st.session_state.vehicles_df_v2, "vehicle")
    cons = compute_constraints(stores, vehicles)
    st.markdown("---")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Спрос на доставку", f"{cons['delivery_demand']:.0f} м³", f"{cons['delivery_gap']:+.0f} м³")
    k2.metric("Возвраты", f"{cons['pickup_demand']:.0f} м³", f"{cons['pickup_gap']:+.0f} м³")
    k3.metric("Активных складов", len(depots))
    k4.metric("Активных машин", len(vehicles))
    if cons["delivery_gap"] < 0:
        st.warning("Недостаточно delivery-вместимости: часть точек может остаться необслуженной.")
    if cons["pickup_gap"] < 0:
        st.warning("Недостаточно pickup-вместимости: обратный забор может не поместиться в парк.")

with tab_result:
    if calc:
        stores = dataframe_to_records(st.session_state.stores_df_v2, "store")
        depots = dataframe_to_records(st.session_state.depots_df_v2, "depot")
        vehicles = dataframe_to_records(st.session_state.vehicles_df_v2, "vehicle")
        if not depots:
            st.error("Нужно оставить хотя бы один активный склад.")
        elif not vehicles:
            st.error("Нужно выбрать хотя бы одну машину.")
        elif not stores:
            st.error("Нет активных магазинов для расчёта.")
        else:
            with st.spinner("⏳ Выполняется расчёт маршрутов..."):
                st.session_state.solution_v2 = solve_vrp(
                    depots=depots,
                    stores=stores,
                    vehicles_config=vehicles,
                    max_search_time=max_search_time,
                    optimization_goal=goal,
                    traffic_profile=traffic_profile,
                    penalty=int(penalty),
                    balance_routes=balance_routes,
                )
    solution = st.session_state.solution_v2
    if solution:
        summary_df, stops_df = route_export_frames(solution)
        unserved_df = pd.DataFrame(solution["unserved"]) if solution["unserved"] else pd.DataFrame()
        total_capacity = sum(v["capacity"] for v in dataframe_to_records(st.session_state.vehicles_df_v2, "vehicle"))
        used_capacity = sum(r["delivery_used"] for r in solution["routes"])
        util_percent = (used_capacity / total_capacity * 100) if total_capacity else 0
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f"<div class='metric-container'><div class='metric-label'>🌍 Общая дистанция</div><div class='metric-value'>{solution['total_distance_km']:.1f} км</div></div>", unsafe_allow_html=True)
        with m2:
            st.markdown(f"<div class='metric-container' style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);'><div class='metric-label'>⏱️ Время рейсов</div><div class='metric-value'>{solution['total_duration_min']//60}ч {solution['total_duration_min']%60}м</div></div>", unsafe_allow_html=True)
        with m3:
            st.markdown(f"<div class='metric-container' style='background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);'><div class='metric-label'>🚛 Машин в рейсе</div><div class='metric-value'>{solution['used_vehicles']}</div></div>", unsafe_allow_html=True)
        with m4:
            st.markdown(f"<div class='metric-container' style='background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);'><div class='metric-label'>📦 Загрузка парка</div><div class='metric-value'>{util_percent:.1f}%</div></div>", unsafe_allow_html=True)
        st.subheader("📋 Сводная таблица")
        st.dataframe(summary_df, use_container_width=True)
        if not unserved_df.empty:
            st.subheader("⚠️ Необслуженные магазины")
            st.dataframe(unserved_df, use_container_width=True)
        st.subheader("🧠 Аналитика маршрутов")
        vehicle_caps = {v["name"]: v["capacity"] for v in dataframe_to_records(st.session_state.vehicles_df_v2, "vehicle")}
        analytics_df = summary_df.copy()
        analytics_df["service_share_%"] = (analytics_df["service_minutes"] / analytics_df["duration_minutes"] * 100).round(1)
        analytics_df["waiting_share_%"] = (analytics_df["waiting_minutes"] / analytics_df["duration_minutes"] * 100).round(1)
        analytics_df["delivery_fill_%"] = analytics_df.apply(lambda row: round((row["delivery_used"] / vehicle_caps.get(row["vehicle"], 1)) * 100, 1), axis=1)
        st.dataframe(analytics_df, use_container_width=True)
        st.subheader("🗺️ Карта")
        all_points = dataframe_to_records(st.session_state.depots_df_v2, "depot") + dataframe_to_records(st.session_state.stores_df_v2, "store")
        center_lat = sum(p["lat"] for p in all_points) / len(all_points)
        center_lon = sum(p["lon"] for p in all_points) / len(all_points)
        fmap = folium.Map(location=[center_lat, center_lon], zoom_start=10)
        for depot in dataframe_to_records(st.session_state.depots_df_v2, "depot"):
            folium.Marker([depot["lat"], depot["lon"]], tooltip=f"🏭 {depot['name']}", popup=f"{depot['name']}<br>{depot['address']}", icon=folium.Icon(color="black", icon="home", prefix="fa")).add_to(fmap)
        for idx, route in enumerate(solution["routes"], start=1):
            color = COLORS[(idx - 1) % len(COLORS)]
            group = folium.FeatureGroup(name=f"Маршрут {idx}: {route['vehicle_type']}")
            for seg in route["geometry"]:
                if seg:
                    folium.PolyLine(seg, color=color, weight=5, opacity=0.75, tooltip=f"Маршрут {idx}").add_to(group)
            for stop in route["stops_detail"]:
                if stop["node_type"] == "depot":
                    continue
                popup = f"<b>Маршрут {idx}</b><br>{stop['name']}<br>⏰ {format_time(stop['arrival'])}<br>📦 Доставка: {stop.get('delivery', 0)} м³<br>♻️ Забор: {stop.get('pickup', 0)} м³<br>🕒 Ожидание: {stop.get('waiting', 0)} мин"
                folium.CircleMarker(location=[stop["lat"], stop["lon"]], radius=10, color=color, fill=True, fill_color=color, fill_opacity=0.9, popup=folium.Popup(popup, max_width=260), tooltip=f"{stop['sequence']}. {stop['name']}").add_to(group)
            group.add_to(fmap)
        if not unserved_df.empty:
            for _, row in unserved_df.iterrows():
                folium.Marker([row["lat"], row["lon"]], tooltip=f"Необслужено: {row['name']}", icon=folium.Icon(color="lightgray", icon="remove-sign")).add_to(fmap)
        folium.LayerControl(collapsed=False).add_to(fmap)
        st_folium(fmap, width=None, height=560)
        st.subheader("📍 Маршрутный лист")
        with st.expander("Показать детализацию", expanded=False):
            for idx, route in enumerate(solution["routes"], start=1):
                st.markdown(f"**Маршрут {idx} — {route['vehicle_type']} ({route['depot_name']})**")
                for stop in route["stops_detail"]:
                    st.write(f"{stop['sequence']:>2}. {stop['name']} | {format_time(stop['arrival'])} → {format_time(stop['departure'])} | дост. {stop.get('delivery', 0)} м³ | забор {stop.get('pickup', 0)} м³ | ожид. {stop.get('waiting', 0)} мин")
                st.divider()
        st.subheader("📤 Экспорт")
        geojson_bytes = json.dumps(build_geojson(solution), ensure_ascii=False, indent=2).encode("utf-8")
        excel_bytes = build_excel_bytes(summary_df, stops_df, unserved_df)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.download_button("CSV (маршруты)", summary_df.to_csv(index=False).encode("utf-8-sig"), "routes_summary.csv", "text/csv")
        with c2:
            st.download_button("Excel", excel_bytes, "vrp_routes.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with c3:
            st.download_button("GeoJSON", geojson_bytes, "routes.geojson", "application/geo+json")
    else:
        st.markdown("<div class='info-box'><h3>👋 Расширенная версия проекта</h3><ul><li>необслуженные точки</li><li>редактирование данных в интерфейсе</li><li>загрузка CSV / Excel</li><li>сводка ограничений</li><li>несколько складов</li><li>обратный забор возвратов</li><li>экспорт CSV / Excel / GeoJSON</li><li>переключение цели оптимизации</li><li>учёт профиля трафика</li><li>смены водителей</li><li>аналитика маршрутов</li></ul><p>Запусти <b>app_v2.py</b> вместо старого app.py.</p></div>", unsafe_allow_html=True)
