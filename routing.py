import requests
import math
import time
from typing import List, Dict, Tuple, Any
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

# ==========================================
# Блок работы с API OSRM и Расчетами
# ==========================================

def get_matrices(locations: List[Dict]) -> Tuple[List[List[int]], List[List[int]]]:
    """
    Получает матрицы времени (минуты) и расстояний (метры) из OSRM.
    Если OSRM недоступен, использует запасной расчет (Haversine).
    """
    print("⏳ Запрос матриц к OSRM...")
    
    # Формируем строку координат: lon,lat;lon,lat
    coordinates = ";".join([f"{loc['lon']},{loc['lat']}" for loc in locations])
    url = f"http://router.project-osrm.org/table/v1/driving/{coordinates}"
    params = {"annotations": "duration,distance"}
    
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        
        if data["code"] == "Ok":
            # ВАЖНО: duration приходит в секундах. 
            # Округляем до минут, но не меньше 1 минуты, чтобы не было "нулевых" переездов.
            time_matrix = [
                [max(1, int(val / 60)) if i != j else 0 for j, val in enumerate(row)] 
                for i, row in enumerate(data["durations"])
            ]
            
            dist_matrix = [
                [int(val) for val in row] 
                for row in data["distances"]
            ]
            
            print("✅ Данные OSRM получены успешно.")
            return time_matrix, dist_matrix
            
    except Exception as e:
        print(f"⚠️ Ошибка OSRM ({e}). Переход на запасной вариант (Haversine).")

    return _calculate_fallback_matrices(locations)


def _calculate_fallback_matrices(locations: List[Dict]) -> Tuple[List[List[int]], List[List[int]]]:
    """Запасной расчет по формуле Haversine (прямая + коэфф. кривизны)."""
    print("...расчет матриц по формуле Haversine...")
    n = len(locations)
    time_mat = [[0] * n for _ in range(n)]
    dist_mat = [[0] * n for _ in range(n)]
    
    AVERAGE_SPEED_KMH = 30.0 # Снизил скорость для Москвы (пробки)
    FACTOR = 1.4 # Коэффициент извилистости
    
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            
            dist = haversine(locations[i]['lat'], locations[i]['lon'], locations[j]['lat'], locations[j]['lon'])
            real_dist = int(dist * FACTOR)
            # Время в минутах
            travel_time = int((real_dist / 1000 / AVERAGE_SPEED_KMH) * 60)
            
            dist_mat[i][j] = real_dist
            time_mat[i][j] = max(1, travel_time) # Минимум 1 минута
            
    return time_mat, dist_mat


def haversine(lat1, lon1, lat2, lon2):
    """Расстояние между точками в метрах"""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2) * math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))


def get_route_geometry(segments: List[Tuple[int, int]], locations: List[Dict]) -> List[List[Tuple[float, float]]]:
    """
    Пытается получить красивую геометрию дорог.
    Если API падает или превышен лимит — возвращает прямые линии.
    """
    geometries = []
    
    # Чтобы не спамить API, если сегментов много, используем упрощение
    # Но для учебного проекта попробуем запросить.
    
    for from_node, to_node in segments:
        loc1, loc2 = locations[from_node], locations[to_node]
        
        # Сразу делаем прямую линию как fallback
        straight_line = [(loc1['lat'], loc1['lon']), (loc2['lat'], loc2['lon'])]
        
        url = (
               f"http://router.project-osrm.org/route/v1/driving/"
               f"{loc1['lon']},{loc1['lat']};{loc2['lon']},{loc2['lat']}"
        )
        params = {"overview": "full", "geometries": "geojson"}
        
        try:
            # Маленькая пауза, чтобы не получить бан (429 Too Many Requests)
            # time.sleep(0.1) 
            
            r = requests.get(url, params=params, timeout=2) # Короткий таймаут
            if r.status_code == 200:
                data = r.json()
                if data.get("routes"):
                    geom = data["routes"][0]["geometry"]["coordinates"]
                    # GeoJSON [lon, lat] -> Folium [lat, lon]
                    geometries.append([(p[1], p[0]) for p in geom])
                else:
                    geometries.append(straight_line)
            else:
                geometries.append(straight_line)
        except:
            # При любой ошибке сети рисуем прямую линию
            geometries.append(straight_line)
            
    return geometries


# ==========================================
# Блок OR-Tools (Логика решения)
# ==========================================

def solve_vrp(locations: List[Dict], vehicles_config: List[Dict], max_search_time: int = 10):
    """Основная функция решения задачи."""
    
    time_matrix, dist_matrix = get_matrices(locations)
    
    # Если матрицы не построились (критическая ошибка), выходим
    if not time_matrix:
        return None

    num_locations = len(locations)
    num_vehicles = len(vehicles_config)
    depot_idx = 0
    
    manager = pywrapcp.RoutingIndexManager(num_locations, num_vehicles, depot_idx)
    routing = pywrapcp.RoutingModel(manager)

    # --- 1. Callback времени (Travel + Service Time) ---
    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        # Время в пути + время на разгрузку в точке отправления
        # (Логика: Приехали в А -> Разгрузились -> Поехали в Б)
        return time_matrix[from_node][to_node] + locations[from_node]['service_time']

    transit_callback_index = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # --- 2. Callback емкости (Demand) ---
    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return locations[from_node]['demand']

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    
    # Добавляем ограничение по объему (Capacity)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,  # null_capacity_slack
        [v['capacity'] for v in vehicles_config], # Массив вместимости машин
        True, # start_cumul_to_zero
        "Capacity"
    )

    # --- 3. Dimension Времени (Time Windows) ---
    # Horizon = 24 часа * 60 мин = 1440. Slack (допустимое ожидание) = 1440 (можно ждать сколько угодно, если приехал рано)
    routing.AddDimension(
        transit_callback_index,
        1440,  # Max wait time (slack) - увеличил, чтобы водитель мог ждать открытия
        1440,  # Max total time (horizon) - сутки
        False, # fix_start_cumul_to_zero
        "Time"
    )
    time_dimension = routing.GetDimensionOrDie("Time")

    # Временные окна для магазинов
    for node_idx, loc in enumerate(locations):
        if node_idx == depot_idx:
            continue
        index = manager.NodeToIndex(node_idx)
        start, end = loc['time_window']
        time_dimension.CumulVar(index).SetRange(start, end)

    # Временные окна для склада (общее время работы смен водителей)
    depot_start, depot_end = locations[depot_idx]['time_window']
    for i in range(num_vehicles):
        routing.AddVariableMinimizedByFinalizer(time_dimension.CumulVar(routing.Start(i)))
        routing.AddVariableMinimizedByFinalizer(time_dimension.CumulVar(routing.End(i)))
        
        # Машина должна выехать и вернуться в рамках работы склада
        time_dimension.CumulVar(routing.Start(i)).SetRange(depot_start, depot_end)
        time_dimension.CumulVar(routing.End(i)).SetRange(depot_start, depot_end)

    # --- 4. Штрафы за пропуск точек (Disjunctions) ---
    # Позволяет алгоритму "выкинуть" магазин, если к нему невозможно успеть
    penalty = 100000 
    for node_idx in range(1, num_locations):
        index = manager.NodeToIndex(node_idx)
        routing.AddDisjunction([index], penalty)

    # --- Параметры поиска ---
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    # Эвристика для первого решения
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    # Мета-эвристика для улучшения решения (Local Search)
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.seconds = max_search_time

    # --- Запуск ---
    print("🧠 Запуск оптимизатора OR-Tools...")
    solution = routing.SolveWithParameters(search_parameters)

    if solution:
        print(f"✅ Решение найдено! (Status: {routing.status()})")
        return _extract_solution(manager, routing, solution, locations, vehicles_config, dist_matrix)
    else:
        print("❌ Решение НЕ найдено.")
        return None


def _extract_solution(manager, routing, solution, locations, vehicles, dist_matrix):
    """Парсинг результата OR-Tools в удобный словарь."""
    routes = []
    total_dist = 0
    time_dimension = routing.GetDimensionOrDie("Time")

    for vehicle_id in range(len(vehicles)):
        index = routing.Start(vehicle_id)
        
        # Проверяем, используется ли машина (если сразу End, значит стоит на базе)
        if routing.IsEnd(solution.Value(routing.NextVar(index))):
            continue

        route_indices = []
        route_segments = []
        route_distance = 0
        
        start_time_var = time_dimension.CumulVar(routing.Start(vehicle_id))
        
        # Получаем время старта
        start_time = solution.Value(start_time_var)

        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            route_indices.append(node_index)
            
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            
            if not routing.IsEnd(index):
                to_node = manager.IndexToNode(index)
                route_segments.append((node_index, to_node))
                # Добавляем реальное расстояние из матрицы
                route_distance += dist_matrix[node_index][to_node]

        # Добавляем финиш (склад)
        final_node = manager.IndexToNode(index)
        route_indices.append(final_node)
        
        # Время окончания
        end_time_var = time_dimension.CumulVar(index)
        end_time = solution.Value(end_time_var)
        
        # Извлекаем тайминги для каждой точки маршрута
        route_times = []
        for i in range(len(route_indices)):
            # Нужно найти NodeIndex для каждой точки.
            # Для склада (0) в начале и конце разные индексы в OR-Tools
            if i == 0: # Start
                 t = solution.Value(time_dimension.CumulVar(routing.Start(vehicle_id)))
            elif i == len(route_indices) - 1: # End
                 t = solution.Value(time_dimension.CumulVar(routing.End(vehicle_id)))
            else: # Intermediate
                 t = solution.Value(time_dimension.CumulVar(manager.NodeToIndex(route_indices[i])))
            route_times.append(t)

        routes.append({
            "vehicle_type": vehicles[vehicle_id]['name'],
            "route": route_indices,
            "times": route_times,
            "distance": route_distance, # метры
            "duration": end_time - start_time, # минуты
            "geometry": get_route_geometry(route_segments, locations),
            "capacity_used": sum([locations[n]['demand'] for n in route_indices if n != 0])
        })
        total_dist += route_distance

    return {
        "routes": routes,
        "total_distance_km": round(total_dist / 1000, 2),
        "used_vehicles": len(routes),
    }