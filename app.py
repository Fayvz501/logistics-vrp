import streamlit as st 
import pandas as pd 
import folium 
from streamlit_folium import st_folium 
from data import locations, vehicles 
from routing import solve_vrp 
import traceback 
 
# ========================================== 
# 1. Хелперы и Настройки 
# ========================================== 
 
st.set_page_config( 
   page_title="RouteOptimizer VRPTW", 
   page_icon="🚚", 
   layout="wide", 
   initial_sidebar_state="expanded" 
) 
 
# Функция форматирования времени (минуты -> ЧЧ:ММ) 
def format_time(minutes): 
   """Переводит минуты от начала суток (напр. 600) в формат 10:00.""" 
   minutes = int(minutes) 
   h = (minutes // 60) % 24 
   m = minutes % 60 
   return f"{h:02d}:{m:02d}" 
 
# CSS стили для красоты 
st.markdown(""" 
<style> 
   .metric-container { 
       background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
       border-radius: 10px; 
       padding: 20px; 
       color: white; 
       text-align: center; 
       box-shadow: 0 4px 6px rgba(0,0,0,0.1); 
       margin-bottom: 10px; 
   } 
   .metric-value { font-size: 26px; font-weight: bold; margin: 5px 0; } 
   .metric-label { font-size: 14px; opacity: 0.9; } 
   .info-box { 
       background-color: #f8f9fa; 
       border-left: 4px solid #3498db; 
       padding: 15px; 
       border-radius: 4px; 
       margin: 10px 0; 
       color: #2c3e50; 
   } 
</style> 
""", unsafe_allow_html=True) 
 
# Цвета для маршрутов 
COLORS = [ 
   'blue', 'green', 'red', 'purple', 'orange', 'darkred', 
   'lightred', 'beige', 'darkblue', 'darkgreen', 'cadetblue', 
   'darkpurple', 'pink', 'lightblue', 'lightgreen', 'gray', 'black' 
] 
 
# ========================================== 
# 2. Сайдбар (Ввод данных) 
# ========================================== 
 
st.sidebar.title("🚚 RouteOptimizer") 
st.sidebar.markdown("---") 
 
st.sidebar.header("⚙️ Настройки парка") 
st.sidebar.info("Выберите машины, которые выйдут в рейс:") 
 
selected_vehicles = [] 
 
# Группируем машины по типам для красоты, но используем реальные ID из data.py 
# (В data.py у нас плоский список, так что просто выводим чекбоксы) 
vehicle_stats = {"Фура": 0, "Грузовик": 0, "Газель": 0} 
 
for v in vehicles: 
   # Определяем иконку по имени 
   icon = "🚚" if "Фура" in v['name'] else "📦" if "Грузовик" in v['name'] else "🔧" 
   label = f"{icon} {v['name']} (Вмест: {v['capacity']}м³)" 
    
   # Чекбокс включен по умолчанию 
   if st.sidebar.checkbox(label, value=True, key=f"v_{v['id']}"): 
       selected_vehicles.append(v) 
        
       # Подсчет для статистики 
       if "Фура" in v['name']: vehicle_stats["Фура"] += 1 
       elif "Грузовик" in v['name']: vehicle_stats["Грузовик"] += 1 
       else: vehicle_stats["Газель"] += 1 
 
st.sidebar.markdown("---") 
st.sidebar.header("⚡ Оптимизация") 
 
max_search_time = st.sidebar.slider( 
   "⏱️ Время поиска решения (сек)", 
   min_value=1, max_value=60, value=10, 
   help="Больше времени = качественнее маршрут, но дольше ожидание." 
) 
 
calc_button = st.sidebar.button("🚀 Рассчитать маршруты", type="primary", use_container_width=True) 
 
# ========================================== 
# 3. Основная логика приложения 
# ========================================== 
 
st.title("🗺️ Маршрутизация с временными окнами (VRPTW)") 
st.markdown("### Учебный проект оптимизации логистики") 
 
# Состояние сессии 
if 'solution' not in st.session_state: 
   st.session_state.solution = None 
 
if calc_button: 
   if not selected_vehicles: 
       st.error("❌ Не выбрано ни одной машины! Пожалуйста, выберите транспорт в меню слева.") 
   else: 
       with st.spinner("⏳ Запрос к OSRM, построение матрицы и оптимизация..."): 
           try: 
               # ВЫЗОВ ФУНКЦИИ ИЗ ROUTING.PY 
               solution = solve_vrp(locations, selected_vehicles, max_search_time=max_search_time) 
               st.session_state.solution = solution 
                
               if not solution: 
                   st.warning("⚠️ Решение не найдено. Возможно, ограничения слишком жесткие (например, не хватает машин).") 
               else: 
                   st.success("✅ Маршруты успешно построены!") 
                    
           except Exception as e: 
               st.error(f"❌ Произошла ошибка: {e}") 
               st.code(traceback.format_exc()) 
 
# ========================================== 
# 4. Отображение результатов 
# ========================================== 
 
solution = st.session_state.solution 
 
if solution: 
   # --- МЕТРИКИ (KPI) --- 
   st.markdown("---") 
   col1, col2, col3, col4 = st.columns(4) 
    
   # Расчет общей загрузки 
   total_capacity = sum(v['capacity'] for v in selected_vehicles) 
   used_capacity = sum(r['capacity_used'] for r in solution['routes']) 
   util_percent = (used_capacity / total_capacity * 100) if total_capacity > 0 else 0 
    
   # Расчет общего времени (сумма длительностей всех маршрутов) 
   total_minutes = sum(r['duration'] for r in solution['routes']) 
    
   with col1: 
       st.markdown(f"""<div class="metric-container"><div class="metric-label">🌍 Общая дистанция</div> 
       <div class="metric-value">{solution['total_distance_km']} км</div></div>""", unsafe_allow_html=True) 
        
   with col2: 
       st.markdown(f"""<div class="metric-container" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);"> 
       <div class="metric-label">⏱️ Время в пути</div><div class="metric-value">{total_minutes // 60}ч {total_minutes % 60}м</div></div>""", unsafe_allow_html=True) 
        
   with col3: 
       st.markdown(f"""<div class="metric-container" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);"> 
       <div class="metric-label">🚚 Машин в рейсе</div><div class="metric-value">{solution['used_vehicles']} / {len(selected_vehicles)}</div></div>""", unsafe_allow_html=True) 
        
   with col4: 
       st.markdown(f"""<div class="metric-container" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);"> 
       <div class="metric-label">📦 Загрузка парка</div><div class="metric-value">{util_percent:.1f}%</div></div>""", unsafe_allow_html=True) 
 
   # --- ТАБЛИЦА МАРШРУТОВ --- 
   st.subheader("📋 Сводная таблица") 
    
   table_data = [] 
   for r in solution['routes']: 
       # Находим полную вместимость этой машины 
       cap_limit = next((v['capacity'] for v in vehicles if v['name'] == r['vehicle_type']), 0) 
       load_pct = (r['capacity_used'] / cap_limit * 100) if cap_limit > 0 else 0 
        
       table_data.append({ 
           "Транспорт": r['vehicle_type'], 
           "Точек": len(r['route']) - 2, # вычитаем старт и финиш на складе 
           "Дистанция (км)": f"{r['distance']/1000:.1f}", 
           "Время (мин)": r['duration'], 
           "Загрузка (м³)": f"{r['capacity_used']} / {cap_limit} ({load_pct:.0f}%)" 
       }) 
    
   st.dataframe(pd.DataFrame(table_data), use_container_width=True) 
 
   # --- КАРТА --- 
   st.subheader("🗺️ Карта маршрутов") 
    
   # Центр карты (Москва) 
   m = folium.Map(location=[55.751244, 37.618423], zoom_start=10) 
   m.get_root().html.add_child(folium.Element("<style>.leaflet-control-attribution { display: none !important; }</style>"))
    
   # Маркер склада 
   depot = locations[0] 
   folium.Marker( 
       [depot['lat'], depot['lon']], 
       tooltip="🏭 СКЛАД (Подольск)", 
       icon=folium.Icon(color='black', icon='home', prefix='fa') 
   ).add_to(m) 
    
   # Отрисовка маршрутов 
   for i, route_data in enumerate(solution['routes']): 
       color = COLORS[i % len(COLORS)] 
       route_num = i + 1 
        
       # Создаем группу для маршрута (для интерактивной подсветки) 
       route_group = folium.FeatureGroup(name=f"Маршрут {route_num}: {route_data['vehicle_type']}") 
        
       # Линия маршрута (geometry из OSRM) с повышенной видимостью при наведении 
       for segment in route_data['geometry']: 
           if segment: 
               folium.PolyLine( 
                   locations=segment, 
                   color=color, 
                   weight=5, 
                   opacity=0.7, 
                   tooltip=f"🚛 Маршрут {route_num}: {route_data['vehicle_type']}" 
               ).add_to(route_group) 
        
       # Маркеры магазинов (пропускаем 0 и последний индекс - это склад) 
       route_indices = route_data['route'] 
       route_times = route_data['times'] 
        
       for idx_in_route, loc_idx in enumerate(route_indices): 
           if loc_idx == 0: continue # Склад уже нарисовали 
            
           loc = locations[loc_idx] 
           arrival_time = format_time(route_times[idx_in_route]) 
            
           # Порядковый номер точки на маршруте (исключая склад) 
           point_number = idx_in_route 
            
           # HTML для попапа 
           popup_html = f""" 
           <div style="font-family: Arial; width: 250px;"> 
               <b style="font-size: 14px; color: {color};">📍 Точка {point_number} маршрута {route_num}</b><br> 
               <b>{loc['name']}</b><br> 
               <hr style="margin: 5px 0;"> 
               ⏰ Прибытие: {arrival_time}<br> 
               📦 Груз: {loc['demand']} м³<br> 
               🕐 Разгрузка: {loc['service_time']} мин 
           </div> 
           """ 
            
           # Создаем HTML для метки с номером 
           marker_html = f""" 
           <div style=" 
               font-size: 14px; 
               font-weight: bold; 
               color: white; 
               text-align: center; 
               background-color: {color}; 
               border-radius: 50%; 
               width: 28px; 
               height: 28px; 
               display: flex; 
               align-items: center; 
               justify-content: center; 
               border: 2px solid white; 
               box-shadow: 0 2px 4px rgba(0,0,0,0.3); 
           ">{point_number}</div> 
           """ 
            
           folium.CircleMarker( 
               location=[loc['lat'], loc['lon']], 
               radius=14, 
               color=color, 
               fill=True, 
               fill_color=color, 
               fill_opacity=0.8, 
               weight=2, 
               popup=folium.Popup(popup_html, max_width=280), 
               tooltip=f"🚛 Маршрут {route_num}, точка {point_number}: {loc['name']} ({arrival_time})" 
           ).add_to(route_group) 
            
           # Добавляем текстовый маркер с номером 
           folium.Marker( 
               location=[loc['lat'], loc['lon']], 
               icon=folium.DivIcon(html=marker_html), 
               popup=folium.Popup(popup_html, max_width=280) 
           ).add_to(route_group) 
        
       route_group.add_to(m) 
    
   # Добавляем контроль слоев для интерактивности 
   folium.LayerControl(position='topright', collapsed=False).add_to(m) 
    
   # Добавляем JavaScript для подсветки при наведении 
   highlight_script = """ 
   <script> 
   document.addEventListener('DOMContentLoaded', function() { 
       const map = document.querySelector('iframe').contentWindow; 
       setTimeout(function() { 
           const featureGroups = document.querySelectorAll('.leaflet-overlay-pane path, .leaflet-overlay-pane polyline'); 
           featureGroups.forEach(el => { 
               el.addEventListener('mouseover', function() { 
                   this.style.opacity = '1'; 
                   this.style.strokeWidth = '8'; 
               }); 
               el.addEventListener('mouseout', function() { 
                   this.style.opacity = '0.7'; 
                   this.style.strokeWidth = '5'; 
               }); 
           }); 
       }, 1000); 
   }); 
   </script> 
   """ 
    
   m_html = m._repr_html_() 
   st_folium(m, width=None, height=500) 
 
   # --- ДЕТАЛИЗАЦИЯ (Text Itinerary) --- 
   st.subheader("📍 Маршрутный лист (Детализация)") 
    
   itinerary_text = "" 
   for r in solution['routes']: 
       itinerary_text += f"\n{'='*40}\n🚛 {r['vehicle_type']} | Дистанция: {r['distance']/1000:.1f} км\n{'='*40}\n" 
        
       route_indices = r['route'] 
       times = r['times'] 
        
       for i, loc_id in enumerate(route_indices): 
           loc = locations[loc_id] 
           time_str = format_time(times[i]) 
            
           if loc_id == 0: 
               action = "СТАРТ СО СКЛАДА" if i == 0 else "ВОЗВРАТ НА БАЗУ" 
               itinerary_text += f"⏰ {time_str} - {action}\n" 
           else: 
               # Время убытия = Прибытие + Разгрузка 
               departure_min = times[i] + loc['service_time'] 
               dep_str = format_time(departure_min) 
                
               itinerary_text += f"  ⬇️ {time_str} Прибытие: {loc['name']}\n" 
               itinerary_text += f"     📦 Разгрузка: {loc['demand']}м³ ({loc['service_time']} мин)\n" 
               itinerary_text += f"     ⬆️ Выезд: {dep_str}\n" 
                
       itinerary_text += "\n" 
 
   # Вывод текста в expandable блоке 
   with st.expander("📄 Показать текстовый отчет", expanded=False): 
       st.text(itinerary_text) 
    
   # Кнопка скачивания 
   st.download_button( 
       label="📥 Скачать отчет (.txt)", 
       data=itinerary_text, 
       file_name="route_plan.txt", 
       mime="text/plain" 
   ) 
 
else: 
   # --- СТАРТОВЫЙ ЭКРАН --- 
   st.markdown(""" 
   <div class="info-box"> 
   <h3>👋 Добро пожаловать!</h3> 
   <p>Это система маршрутизации для компании одежды.</p> 
   <ul> 
       <li><b>Склад:</b> Подольск</li> 
       <li><b>Точки:</b> 23 магазина Gloria Jeans в Москве</li> 
       <li><b>Цель:</b> Развезти товар минимальным количеством машин с учетом пробок.</li> 
   </ul> 
   <p>👈 <b>Начните с настройки парка машин в меню слева.</b></p> 
   </div> 
   """, unsafe_allow_html=True) 
    
   # Показываем данные 
   with st.expander("📋 Просмотр исходных данных (Магазины)"): 
       df_locs = pd.DataFrame(locations) 
       # Убираем сложные колонки для показа 
       st.dataframe(df_locs[['id', 'name', 'address', 'demand', 'service_time']]) 
