# 📊 Semana 3 — Días 11 y 12: Kibana Dashboards + PowerBI Export

## Contexto

Comenzamos la Semana 3 del proyecto AirVLC. Los servicios Docker están activos:

| Servicio | Versión | Estado |
|----------|---------|--------|
| Elasticsearch | 8.10.4 | ✅ Running |
| Kibana | 8.10.4 | ✅ Running |
| PostgreSQL | 15-alpine | ✅ Running |
| Redis | 7-alpine | ✅ Running |
| Logstash | 8.10.4 | ✅ Running |
| Node-RED | latest | ✅ Running |

**Datos disponibles en ES:**
- `airvlc-calidad-aire`: 449,027 docs (2016–2026), 12 estaciones, campos: pm25, no2, o3, co, so2, temperatura, humedad_relativa, velocidad_viento, location (geo_point), etc.
- `estaciones-geojson`: 11 docs con geometría de estaciones

**Modelos entrenados:**
- **LSTM_Attention**: R²=0.7672, MAE=2.64, RMSE=4.69 (mejor)
- **Ensemble (3 LSTM)**: R²=0.7619
- **RiskClassifier (Red Neuronal)**: Accuracy=89.6%, F1=0.895
- API Flask funcionando en puerto 5001

---

## Día 11 — Kibana: Dashboards de Calidad del Aire

### Objetivo
Crear dashboards analíticos profesionales en Kibana que cubran:
1. **Monitorización de calidad del aire** (series temporales, mapas, comparativas por estación)
2. **Visualización de métricas del modelo IA** (R², MAE, distribución de errores)
3. **Timeline de niveles de riesgo** (basado en umbrales del RiskClassifier)

### Componentes

#### 1. Crear índice `airvlc-predictions` para resultados de la API

##### [NEW] [create_predictions_index.py](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/src/scripts/create_predictions_index.py)

Script Python que:
- Crea el index template `airvlc-predictions` en Elasticsearch
- Mapping con campos: `@timestamp`, `pm25_predicted`, `pm25_actual` (nullable), `station`, `risk_level`, `risk_color`, `alert_text`, `model_used`, `mae_error` (nullable), `location` (geo_point), `residual`
- Incluye un **bulk insert inicial** con datos históricos de predicción vs. realidad (exportados del test set del modelo, ~5000 muestras) para que Kibana tenga datos desde el principio

#### 2. Script para poblar predicciones históricas en ES

##### [NEW] [seed_predictions_to_es.py](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/src/scripts/seed_predictions_to_es.py)

Script que:
- Lee los datos de test del modelo (los CSVs de resultados) y carga las predicciones históricas como documentos de `airvlc-predictions`
- Asigna niveles de riesgo usando `RiskClassifier` para cada predicción
- Genera campos calculados: residual (predicted - actual), absolute_error

#### 3. Configurar Kibana Dashboards via API (Saved Objects)

##### [NEW] [setup_kibana_dashboards.py](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/src/scripts/setup_kibana_dashboards.py)

Script Python que usa la API de Saved Objects de Kibana (8.10.4) para crear:

**Dashboard 1: "🌍 AirVLC — Monitorización de Calidad del Aire"**
- **Mapa de estaciones** (geo_point map layer con pm25 promedio como color)
- **Serie temporal PM2.5** (line chart, filtrable por estación)
- **Serie temporal NO₂** (line chart comparativo)
- **Tabla TOP estaciones contaminadas** (data table con avg PM2.5 y max PM2.5)
- **Gauge de PM2.5 actual** (promedio últimas 24h)
- **Histogram de distribución PM2.5** por hora del día
- **Heatmap de PM2.5** por día de la semana × hora

**Dashboard 2: "🤖 AirVLC — Rendimiento del Modelo IA"**
- **Gauge de R²** del modelo activo (0.77 vs objetivo 0.85)
- **Markdown panel** con métricas: MAE, RMSE, R² de todos los modelos
- **Histograma de residuos** (predicción - realidad)
- **Line chart: Forecast vs Actual** (serie temporal superpuesta)
- **Pie chart: Distribución de niveles de riesgo**
- **Bar chart: MAE por estación**

> [!IMPORTANT]
> Kibana 8.10.4 usa la API de Saved Objects v2. Los dashboards se crean programáticamente para que sean reproducibles y versionables en Git.

---

## Día 12 — PowerBI Data Export + API-to-ES Pipeline

### Objetivo
1. Exportar CSVs enriquecidos para consumo en PowerBI (Windows)
2. Integrar la API Flask con Elasticsearch para que cada predicción se indexe automáticamente

### Componentes

#### 1. Export de datos para PowerBI

##### [NEW] [export_powerbi_data.py](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/src/scripts/export_powerbi_data.py)

Genera 3 CSVs en `data/processed/powerbi/`:

- **`forecast_vs_actual.csv`**: timestamp, station, pm25_actual, pm25_predicted, residual, risk_level, model_used
- **`model_comparison.csv`**: model, mae, rmse, r2, n_params, training_time, type (ya existe pero lo enriquecemos con más contexto)
- **`station_daily_summary.csv`**: date, station, avg_pm25, max_pm25, min_pm25, avg_no2, avg_o3, avg_temperatura, horas_riesgo_alto, nivel_dominante
- **`feature_correlations.csv`**: correlaciones entre variables meteorológicas y PM2.5 para el gráfico de "driver de contaminación"

#### 2. Integración API → Elasticsearch

##### [MODIFY] [routes.py](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/src/api/routes.py)

Añadir middleware/función que tras cada predicción:
- Indexa el resultado en `airvlc-predictions`
- Incluye: timestamp, pm25_predicted, station, risk_level, model_used, alert_text

##### [NEW] [es_indexer.py](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/src/api/es_indexer.py)

Módulo dedicado para la conexión API → Elasticsearch:
- Usa `elasticsearch-py` (ya disponible) para conectar a ES local
- Función `index_prediction(data)` que indexa un documento en `airvlc-predictions`
- Manejo de errores silencioso (si ES no disponible, la API sigue funcionando)
- Conexión configurable vía variables de entorno

##### [MODIFY] [app.py](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/src/api/app.py)

Inicializar el `ESIndexer` en el factory de la app y pasarlo al config.

---

## Verificación

### Automated Tests
1. `curl http://localhost:9200/airvlc-predictions/_count` → Verificar documentos indexados
2. `curl http://localhost:5001/api/predict` con datos de test → Verificar que se indexa en ES
3. `python src/scripts/export_powerbi_data.py` → Verificar CSVs generados en `data/processed/powerbi/`

### Manual Verification
1. Abrir Kibana en `http://localhost:5601` → Verificar dashboards creados
2. Comprobar que los dashboards muestran datos correctamente (capturas de pantalla)
3. Verificar los CSVs exportados se pueden abrir en PowerBI

---

## Open Questions

> [!IMPORTANT]
> **¿Tienes datos de predicción del test set guardados?** Para poblar el índice `airvlc-predictions` con datos históricos de "forecast vs actual", necesito acceso a los resultados reales del test set del modelo. Si no tienes un CSV ya exportado, puedo generarlo cargando el modelo y ejecutando predicciones sobre los datos de test, pero necesitaré el scaler y los datos de test preprocesados. ¿Están disponibles localmente o solo en Colab?

> [!NOTE]
> Los dashboards de Kibana se crean programáticamente vía la API de Saved Objects. Esto significa que son 100% reproducibles — si alguien borra el dashboard, basta con re-ejecutar el script. Ideal para la presentación al jurado.
