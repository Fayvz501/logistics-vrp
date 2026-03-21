import math
from copy import deepcopy
from functools import lru_cache
from typing import Dict, List, Tuple

import pandas as pd
import requests
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

DEPOTS = [
    {"id": "depot_grivno", "name": "Склад Gloria Jeans — Гривно", "address": "Московская область, г.о. Подольск, деревня Гривно, территория промышленного парка Гривно, 1", "lat": 55.354159, "lon": 37.573241, "tw_start": 360, "tw_end": 1440},
    {"id": "depot_orientir_yug", "name": "РЦ Gloria Jeans — Ориентир-Юг", "address": "Московская область, г.о. Подольск, индустриальный парк Ориентир-Юг, район села Сынково", "lat": 55.3249, "lon": 37.5335, "tw_start": 360, "tw_end": 1440},
]

STORES = [
    {"id": 1, "name": "GJ Тверская", "address": "Москва, Тверская ул., 16с1", "lat": 55.764551, "lon": 37.606406, "demand": 4, "pickup_demand": 0, "tw_start": 600, "tw_end": 1320, "service_time": 20},
    {"id": 2, "name": "GJ Новый Арбат", "address": "Москва, ул. Новый Арбат, 11с1", "lat": 55.752085, "lon": 37.596237, "demand": 3, "pickup_demand": 0, "tw_start": 600, "tw_end": 1320, "service_time": 20},
    {"id": 3, "name": "GJ Киевский", "address": "Москва, пл. Киевского Вокзала, 2", "lat": 55.744637, "lon": 37.566072, "demand": 5, "pickup_demand": 1, "tw_start": 600, "tw_end": 1320, "service_time": 30},
    {"id": 4, "name": "GJ Кожуховская (Мозаика)", "address": "Москва, 7-я Кожуховская ул., 9", "lat": 55.710692, "lon": 37.675109, "demand": 3, "pickup_demand": 0, "tw_start": 600, "tw_end": 1320, "service_time": 20},
    {"id": 5, "name": "GJ Орджоникидзе", "address": "Москва, ул. Орджоникидзе, 11", "lat": 55.709160, "lon": 37.595321, "demand": 2, "pickup_demand": 0, "tw_start": 600, "tw_end": 1260, "service_time": 15},
    {"id": 6, "name": "GJ Шоссе Энтузиастов", "address": "Москва, ш. Энтузиастов, 12к2", "lat": 55.747368, "lon": 37.707107, "demand": 4, "pickup_demand": 1, "tw_start": 600, "tw_end": 1320, "service_time": 25},
    {"id": 7, "name": "GJ Зеленодольская", "address": "Москва, Зеленодольская ул., 42", "lat": 55.701856, "lon": 37.764528, "demand": 3, "pickup_demand": 0, "tw_start": 600, "tw_end": 1320, "service_time": 20},
    {"id": 8, "name": "GJ Черемушкинская", "address": "Москва, Б. Черемушкинская ул., 1", "lat": 55.690283, "lon": 37.601879, "demand": 4, "pickup_demand": 1, "tw_start": 600, "tw_end": 1320, "service_time": 25},
    {"id": 9, "name": "GJ Шереметьевская", "address": "Москва, Шереметьевская ул., 6к1", "lat": 55.795403, "lon": 37.617033, "demand": 2, "pickup_demand": 0, "tw_start": 600, "tw_end": 1320, "service_time": 20},
    {"id": 10, "name": "GJ Комсомольская", "address": "Москва, Комсомольская пл., 6", "lat": 55.775864, "lon": 37.660413, "demand": 3, "pickup_demand": 0, "tw_start": 540, "tw_end": 1320, "service_time": 20},
    {"id": 11, "name": "GJ Афимолл (Сити)", "address": "Москва, Пресненская наб., 2", "lat": 55.749162, "lon": 37.539742, "demand": 5, "pickup_demand": 1, "tw_start": 600, "tw_end": 1320, "service_time": 35},
    {"id": 12, "name": "GJ Columbus", "address": "Москва, Кировоградская ул., 13А", "lat": 55.612146, "lon": 37.606999, "demand": 5, "pickup_demand": 1, "tw_start": 600, "tw_end": 1320, "service_time": 30},
    {"id": 13, "name": "GJ Хорошёвское", "address": "Москва, Хорошёвское ш., 27", "lat": 55.777105, "lon": 37.523716, "demand": 3, "pickup_demand": 0, "tw_start": 600, "tw_end": 1320, "service_time": 20},
    {"id": 14, "name": "GJ Каховка", "address": "Москва, ул. Каховка, 29А", "lat": 55.656357, "lon": 37.569360, "demand": 2, "pickup_demand": 0, "tw_start": 600, "tw_end": 1320, "service_time": 15},
    {"id": 15, "name": "GJ Открытое шоссе", "address": "Москва, Открытое ш., 4с1", "lat": 55.809090, "lon": 37.729970, "demand": 2, "pickup_demand": 0, "tw_start": 600, "tw_end": 1320, "service_time": 20},
    {"id": 16, "name": "GJ Поречная (Mari)", "address": "Москва, Поречная ул., 10", "lat": 55.649830, "lon": 37.770052, "demand": 3, "pickup_demand": 1, "tw_start": 600, "tw_end": 1320, "service_time": 20},
    {"id": 17, "name": "GJ Проспект Мира", "address": "Москва, пр-т Мира, 211к2", "lat": 55.845855, "lon": 37.662093, "demand": 5, "pickup_demand": 1, "tw_start": 600, "tw_end": 1320, "service_time": 30},
    {"id": 18, "name": "GJ Океания", "address": "Москва, Кутузовский пр-т, 57", "lat": 55.727988, "lon": 37.476061, "demand": 4, "pickup_demand": 1, "tw_start": 600, "tw_end": 1320, "service_time": 25},
    {"id": 19, "name": "GJ Ленинский", "address": "Москва, Ленинский пр-т, 109", "lat": 55.663842, "lon": 37.511445, "demand": 3, "pickup_demand": 0, "tw_start": 600, "tw_end": 1320, "service_time": 20},
    {"id": 20, "name": "GJ Спектр", "address": "Москва, Новоясеневский пр-т, 1", "lat": 55.619472, "lon": 37.509289, "demand": 2, "pickup_demand": 0, "tw_start": 600, "tw_end": 1320, "service_time": 20},
    {"id": 21, "name": "GJ Avenue", "address": "Москва, пр-т Вернадского, 86А", "lat": 55.663024, "lon": 37.481001, "demand": 3, "pickup_demand": 0, "tw_start": 600, "tw_end": 1320, "service_time": 20},
    {"id": 22, "name": "GJ Староватутинский", "address": "Москва, Староватутинский пр., 14", "lat": 55.875804, "lon": 37.665551, "demand": 2, "pickup_demand": 0, "tw_start": 600, "tw_end": 1200, "service_time": 15},
    {"id": 23, "name": "GJ Облака", "address": "Москва, Ореховый б-р, 22А", "lat": 55.612045, "lon": 37.732718, "demand": 3, "pickup_demand": 1, "tw_start": 600, "tw_end": 1320, "service_time": 20},
]

VEHICLES = [
    {"id": 0, "name": "Фура 1 (20м3)", "capacity": 20, "pickup_capacity": 20, "depot_id": "depot_grivno", "max_shift_min": 600},
    {"id": 1, "name": "Фура 2 (20м3)", "capacity": 20, "pickup_capacity": 20, "depot_id": "depot_orientir_yug", "max_shift_min": 600},
    {"id": 2, "name": "Грузовик 1 (15м3)", "capacity": 15, "pickup_capacity": 15, "depot_id": "depot_grivno", "max_shift_min": 540},
    {"id": 3, "name": "Грузовик 2 (15м3)", "capacity": 15, "pickup_capacity": 15, "depot_id": "depot_orientir_yug", "max_shift_min": 540},
    {"id": 4, "name": "Газель (10м3)", "capacity": 10, "pickup_capacity": 10, "depot_id": "depot_grivno", "max_shift_min": 480},
]

TRAFFIC = {"offpeak": 0.9, "day": 1.0, "morning_peak": 1.25, "evening_peak": 1.35}


def build_template_frames():
    return (
        pd.DataFrame([{"active": True, **x} for x in deepcopy(DEPOTS)]),
        pd.DataFrame([{"active": True, **x} for x in deepcopy(STORES)]),
        pd.DataFrame([{"active": True, **x} for x in deepcopy(VEHICLES)]),
    )


def haversine(lat1, lon1, lat2, lon2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@lru_cache(maxsize=32)
def _cached(coords, traffic_profile):
    nodes = [{"lat": c[0], "lon": c[1]} for c in coords]
    return _build_matrices(nodes, traffic_profile)


def get_matrices(nodes, traffic_profile="day"):
    coords = tuple((round(n["lat"], 6), round(n["lon"], 6)) for n in nodes)
    return _cached(coords, traffic_profile)


def _build_matrices(nodes, traffic_profile="day"):
    factor = TRAFFIC.get(traffic_profile, 1.0)
    coords = ";".join([f"{n['lon']},{n['lat']}" for n in nodes])
    try:
        r = requests.get(f"http://router.project-osrm.org/table/v1/driving/{coords}", params={"annotations": "duration,distance"}, timeout=12)
        r.raise_for_status()
        data = r.json()
        if data.get("code") == "Ok":
            tm = [[max(1, int((v / 60) * factor)) if i != j else 0 for j, v in enumerate(row)] for i, row in enumerate(data["durations"])]
            dm = [[int(v) for v in row] for row in data["distances"]]
            return tm, dm
    except Exception:
        pass
    speeds = {"offpeak": 36.0, "day": 30.0, "morning_peak": 24.0, "evening_peak": 22.0}
    speed = speeds.get(traffic_profile, 30.0)
    n = len(nodes)
    tm = [[0] * n for _ in range(n)]
    dm = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            d = int(haversine(nodes[i]["lat"], nodes[i]["lon"], nodes[j]["lat"], nodes[j]["lon"]) * 1.35)
            dm[i][j] = d
            tm[i][j] = max(1, int((d / 1000 / speed) * 60))
    return tm, dm


def get_route_geometry(segments, nodes):
    out = []
    for a, b in segments:
        n1, n2 = nodes[a], nodes[b]
        straight = [(n1["lat"], n1["lon"]), (n2["lat"], n2["lon"])]
        try:
            r = requests.get(
                f"http://router.project-osrm.org/route/v1/driving/{n1['lon']},{n1['lat']};{n2['lon']},{n2['lat']}",
                params={"overview": "full", "geometries": "geojson"}, timeout=2.5,
            )
            if r.status_code == 200 and r.json().get("routes"):
                out.append([(p[1], p[0]) for p in r.json()["routes"][0]["geometry"]["coordinates"]])
            else:
                out.append(straight)
        except Exception:
            out.append(straight)
    return out


def solve_vrp(depots: List[Dict], stores: List[Dict], vehicles_config: List[Dict], max_search_time=10, optimization_goal="time", traffic_profile="day", penalty=100000, balance_routes=True):
    nodes, depot_map, store_map = [], {}, {}
    for d in depots:
        x = {**d, "node_type": "depot", "time_window": d.get("time_window") or (d["tw_start"], d["tw_end"]), "service_time": 0, "demand": 0, "pickup_demand": 0}
        depot_map[d["id"]] = len(nodes); nodes.append(x)
    for s in stores:
        x = {**s, "node_type": "store", "time_window": s.get("time_window") or (s["tw_start"], s["tw_end"])}
        store_map[s["id"]] = len(nodes); nodes.append(x)
    tm, dm = get_matrices(nodes, traffic_profile)
    starts = [depot_map[v["depot_id"]] for v in vehicles_config]
    ends = [depot_map[v["depot_id"]] for v in vehicles_config]
    man = pywrapcp.RoutingIndexManager(len(nodes), len(vehicles_config), starts, ends)
    routing = pywrapcp.RoutingModel(man)

    def time_cb(fi, ti):
        f, t = man.IndexToNode(fi), man.IndexToNode(ti)
        return tm[f][t] + int(nodes[f].get("service_time", 0))

    def dist_cb(fi, ti):
        f, t = man.IndexToNode(fi), man.IndexToNode(ti)
        return dm[f][t]

    ti = routing.RegisterTransitCallback(time_cb)
    di = routing.RegisterTransitCallback(dist_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(di if optimization_goal == "distance" else ti)

    deli = routing.RegisterUnaryTransitCallback(lambda idx: int(nodes[man.IndexToNode(idx)].get("demand", 0)))
    picki = routing.RegisterUnaryTransitCallback(lambda idx: int(nodes[man.IndexToNode(idx)].get("pickup_demand", 0)))
    routing.AddDimensionWithVehicleCapacity(deli, 0, [int(v["capacity"]) for v in vehicles_config], True, "Delivery")
    routing.AddDimensionWithVehicleCapacity(picki, 0, [int(v.get("pickup_capacity", v["capacity"])) for v in vehicles_config], True, "Pickup")
    routing.AddDimension(ti, 1440, max(int(v.get("max_shift_min", 600)) for v in vehicles_config), False, "Time")
    td = routing.GetDimensionOrDie("Time")

    for n, node in enumerate(nodes):
        idx = man.NodeToIndex(n)
        s, e = node["time_window"]
        if node["node_type"] == "store":
            td.CumulVar(idx).SetRange(int(s), int(e))
            routing.AddDisjunction([idx], int(penalty))

    for vid, v in enumerate(vehicles_config):
        s_idx, e_idx = routing.Start(vid), routing.End(vid)
        ds, de = nodes[starts[vid]]["time_window"]
        td.CumulVar(s_idx).SetRange(int(ds), int(de))
        td.CumulVar(e_idx).SetRange(int(ds), int(min(de, ds + v.get("max_shift_min", 600))))
        routing.AddVariableMinimizedByFinalizer(td.CumulVar(s_idx))
        routing.AddVariableMinimizedByFinalizer(td.CumulVar(e_idx))
        if optimization_goal == "fleet":
            routing.SetFixedCostOfVehicle(50000, vid)
    if optimization_goal == "balanced" or balance_routes:
        td.SetGlobalSpanCostCoefficient(80)

    p = pywrapcp.DefaultRoutingSearchParameters()
    p.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    p.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    p.time_limit.seconds = int(max_search_time)
    sol = routing.SolveWithParameters(p)
    if not sol:
        return None

    routes, served, total_dist, total_dur = [], set(), 0, 0
    for vid, v in enumerate(vehicles_config):
        idx = routing.Start(vid)
        if routing.IsEnd(sol.Value(routing.NextVar(idx))):
            continue
        route_nodes, times = [], []
        while not routing.IsEnd(idx):
            route_nodes.append(man.IndexToNode(idx)); times.append(sol.Value(td.CumulVar(idx))); idx = sol.Value(routing.NextVar(idx))
        route_nodes.append(man.IndexToNode(idx)); times.append(sol.Value(td.CumulVar(idx)))
        segments, dist, drive, wait, service, d_used, p_used, stops = [], 0, 0, 0, 0, 0, 0, []
        for seq, node_idx in enumerate(route_nodes):
            node = nodes[node_idx]; arr = times[seq]; svc = int(node.get("service_time", 0)); dep = arr + svc; w = 0
            if seq > 0:
                prev = route_nodes[seq - 1]
                expected = times[seq - 1] + int(nodes[prev].get("service_time", 0)) + tm[prev][node_idx]
                w = max(0, arr - expected); wait += w; segments.append((prev, node_idx)); dist += dm[prev][node_idx]; drive += tm[prev][node_idx]
            if node["node_type"] == "store":
                served.add(node["id"]); d_used += node.get("demand", 0); p_used += node.get("pickup_demand", 0); service += svc
            stops.append({"sequence": seq, "node_type": node["node_type"], "name": node["name"], "address": node.get("address", ""), "lat": node["lat"], "lon": node["lon"], "arrival": arr, "departure": dep, "service_time": svc, "waiting": w, "delivery": node.get("demand", 0), "pickup": node.get("pickup_demand", 0)})
        duration = times[-1] - times[0]; total_dist += dist; total_dur += duration
        routes.append({"vehicle_type": v["name"], "depot_name": nodes[route_nodes[0]]["name"], "route": route_nodes, "times": times, "distance": dist, "duration": duration, "drive_minutes": drive, "service_minutes": service, "waiting_minutes": wait, "stops_count": sum(1 for n in route_nodes if nodes[n]["node_type"] == "store"), "delivery_used": d_used, "pickup_used": p_used, "avg_speed_kmh": round((dist / 1000) / max(drive / 60, 1e-9), 1) if drive else 0, "geometry": get_route_geometry(segments, nodes), "stops_detail": stops})
    unserved = [{"id": s["id"], "name": s["name"], "address": s["address"], "lat": s["lat"], "lon": s["lon"], "delivery": s.get("demand", 0), "pickup": s.get("pickup_demand", 0)} for s in stores if s["id"] not in served]
    return {"routes": routes, "unserved": unserved, "total_distance_km": round(total_dist / 1000, 2), "used_vehicles": len(routes), "total_duration_min": total_dur}
