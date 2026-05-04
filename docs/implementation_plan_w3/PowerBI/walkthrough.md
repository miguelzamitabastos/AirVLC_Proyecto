# 📊 Walkthrough — Semana 3, Días 11-12 (Actualizado)

## Resumen

Implementados todos los componentes de **visualización y servicios** del proyecto AirVLC:

- **Kibana**: 5 Data Views + 4 Dashboards (aire, modelo, contaminantes, realtime)
- **ES**: 4 índices propios (calidad-aire, predictions, meteo-realtime, api-heartbeat)
- **Pipeline**: MongoDB Atlas → Elasticsearch para meteo en tiempo real
- **Heartbeat**: Monitor de API indexando estado cada 30s
- **PowerBI**: 6 CSVs exportados + guía paso a paso

---

## Archivos Creados/Modificados

### Nuevos

| Archivo | Descripción |
|---------|-------------|
| [create_predictions_index.py](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/src/scripts/create_predictions_index.py) | Índice ES `airvlc-predictions` (23 campos) |
| [seed_predictions_to_es.py](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/src/scripts/seed_predictions_to_es.py) | 7,994 predicciones históricas (Nov 2025 → Abr 2026) |
| [setup_kibana_dashboards.py](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/src/scripts/setup_kibana_dashboards.py) | Data Views + dashboards vía API Kibana |
| [es_indexer.py](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/src/api/es_indexer.py) | Módulo fail-safe API → ES |
| [export_powerbi_data.py](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/src/scripts/export_powerbi_data.py) | 6 CSVs para PowerBI |
| [sync_meteo_to_es.py](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/src/scripts/sync_meteo_to_es.py) | Pipeline MongoDB → ES (meteo realtime) |
| [api_heartbeat.py](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/src/scripts/api_heartbeat.py) | Monitor de estado de la API → ES |

### Modificados

| Archivo | Cambio |
|---------|--------|
| [app.py](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/src/api/app.py) | Inicializa ESIndexer |
| [routes.py](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/src/api/routes.py) | Indexa predicciones tras /predict y /risk |

---

## Estado de Elasticsearch

| Índice | Documentos | Tamaño |
|--------|-----------|--------|
| airvlc-calidad-aire | 449,027 | 73.4 MB |
| airvlc-predictions | 7,994 | 1.4 MB |
| airvlc-meteo-realtime | 112 | 19.1 KB |
| airvlc-api-heartbeat | ~acumulando | ~KB |
| estaciones-geojson | 11 | 21.6 KB |

## Kibana Data Views

| Data View | Índice |
|-----------|--------|
| AirVLC - Calidad del Aire | airvlc-calidad-aire |
| AirVLC - Predicciones IA | airvlc-predictions |
| AirVLC - Meteo Tiempo Real | airvlc-meteo-realtime |
| AirVLC - API Heartbeat | airvlc-api-heartbeat |
| AirVLC - Estaciones | estaciones-geojson |

---

## 📊 Guía PowerBI Paso a Paso

### Preparación
1. Copia la carpeta `data/processed/powerbi/` a tu Windows (USB, Drive, o git)
2. Abre **PowerBI Desktop** (gratis en Microsoft Store)

---

### Dashboard 1: Forecast vs Actual

**CSV**: `forecast_vs_actual.csv`

1. **Obtener datos** → Texto/CSV → selecciona el archivo
2. Haz clic en **Transformar datos** → verifica que las columnas se detectan bien → **Cerrar y aplicar**
3. En el panel derecho, elige **Gráfico de líneas**
4. Arrastra:
   - **Eje X**: `fecha`
   - **Valores (línea 1)**: `pm25_actual` → clic derecho → **Promedio**
   - **Valores (línea 2)**: `pm25_predicted` → clic derecho → **Promedio**
5. Arrastra `station` al campo **Leyenda** si quieres filtrar por estación
6. Añade un **Segmentador** (Slicer) con `station` para poder filtrar interactivamente
7. Añade un **Segmentador** con `risk_level_predicted` para filtrar por riesgo
8. **Título**: "Predicción LSTM vs Valor Real de PM2.5"

**Extra**: Añade una **Tarjeta** (Card) con:
- `absolute_error` → Promedio → muestra el MAE en grande
- `residual` → Promedio → muestra el sesgo del modelo

---

### Dashboard 2: Comparativa de Modelos

**CSV**: `model_comparison.csv`

1. **Obtener datos** → Texto/CSV
2. Elige **Gráfico de barras agrupadas**
3. Arrastra:
   - **Eje Y**: `model`
   - **Valores**: `mae`
4. Ordena de menor a mayor (clic en los 3 puntos → Ordenar)
5. Duplica el gráfico (Ctrl+C, Ctrl+V) y cambia `mae` por `r2`
6. Añade un **Gráfico de dispersión** (Scatter):
   - **Eje X**: `mae`
   - **Eje Y**: `r2`
   - **Detalles**: `model`
   - **Tamaño**: `n_params`
7. Añade una **Tabla** con todos los campos para referencia
8. **Título**: "Comparativa de 7 Modelos de IA"

**Extra**: Carga también `classifier_comparison.csv` y añade un gráfico de barras con `accuracy` y `f1` para los clasificadores de riesgo.

---

### Dashboard 3: Resumen por Estación

**CSV**: `station_daily_summary.csv`

1. **Obtener datos** → Texto/CSV
2. Elige **Mapa** (Map visualization):
   - Necesitarás añadir coordenadas manualmente o usar un **Treemap** como alternativa
3. Alternativa sin mapa — usa **Matriz** (Matrix):
   - **Filas**: `station`
   - **Columnas**: `date` (agrupado por mes)
   - **Valores**: `avg_pm25`
   - Aplica **formato condicional** (verde→rojo según valor)
4. Añade **Gráfico de área apilada**:
   - **Eje X**: `date`
   - **Valores**: `horas_bueno`, `horas_moderado`, `horas_malo`, `horas_peligroso`
   - Esto muestra las horas en cada nivel de riesgo por día
5. Añade una **Tabla** con KPIs por estación:
   - Agrupa por `station`
   - Muestra avg_pm25, max_pm25, n_measurements
6. **Título**: "Análisis por Estación y Día"

---

### Dashboard 4: Driver de Contaminación

**CSV**: `feature_correlations.csv` + `correlation_matrix.csv`

1. **Obtener datos** → Texto/CSV → `feature_correlations.csv`
2. Elige **Gráfico de barras horizontales**:
   - **Eje Y**: `variable`
   - **Valores**: `abs_correlation`
   - Ordena de mayor a menor
3. Aplica **formato condicional** por color según `direction` (Positiva=rojo, Negativa=azul)
4. Añade una **Tarjeta** por cada top-3 variable correlacionada
5. Para la matriz: carga `correlation_matrix.csv` y usa **Mapa de calor** (Heat map) si está disponible, o una **Tabla con formato condicional**
6. **Título**: "¿Qué Variables Meteorológicas Influyen Más en el PM2.5?"

---

## Comandos útiles

```bash
# Re-sincronizar meteo (one-shot)
python src/scripts/sync_meteo_to_es.py

# Sincronización continua meteo (cada 5 min)
python src/scripts/sync_meteo_to_es.py --daemon

# Heartbeat de la API (cada 60s)
python src/scripts/api_heartbeat.py

# Heartbeat rápido (cada 30s)
python src/scripts/api_heartbeat.py --interval 30
```
