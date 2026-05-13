# Sprint 7 — Kibana Dashboard: Última Predicción (Operacional)

Este documento describe los pasos para configurar el dashboard de Kibana
que monitoriza el estado del pipeline de predicciones AirVLC v2.

## Pasos de Configuración Manual en Kibana (http://localhost:5601)

### 1. Crear Index Pattern
1. Ir a **Stack Management → Data Views**
2. Crear data view:
   - Name: `airvlc-predictions-v2`
   - Index pattern: `airvlc-predictions-v2*`
   - Timestamp field: `@timestamp`

### 2. Crear Dashboard "AirVLC — Última Predicción"

#### Panel 1: "Última Inferencia" (Métrica)
- Tipo: **Metric**
- Aggregation: **Max** de `@timestamp`
- Label: "Última inferencia"
- Filtro: `source: api-v2 OR source: api-v2-profile`

#### Panel 2: "Estaciones Predichas" (Métrica)
- Tipo: **Metric**
- Aggregation: **Cardinality** de `station.keyword`
- Label: "Estaciones predichas"
- Time range: **Last 1 hour**

#### Panel 3: "Distribución de Riesgo por Contaminante" (Horizontal Bar)
- Tipo: **Bar horizontal**
- Ejes:
  - Y: Count (agrupado por `worst_level.keyword`)
  - X: `worst_pollutant.keyword`
- Colores personalizados:
  - bueno → #2BB673
  - moderado → #F2C744
  - malo → #F4A300
  - peligroso → #D62828
- Time range: **Last 1 hour**

#### Panel 4: "PM2.5 / NO₂ / O₃ Predichos" (Line Chart)
- Tipo: **Line**
- 3 líneas:
  - `pm25_pred` (Avg)
  - `no2_pred` (Avg)
  - `o3_pred` (Avg)
- X: `@timestamp` (date histogram, interval: auto)
- Time range: **Last 24 hours**

#### Panel 5: "Estaciones por Peor Nivel" (Donut)
- Tipo: **Pie/Donut**
- Slice by: `worst_level.keyword`
- Size: Count
- Colores: misma paleta que Panel 3
- Time range: **Last 1 hour**

#### Panel 6: "Histórico de Riesgo por Estación" (Heatmap)
- Tipo: **Heatmap**
- Y: `station.keyword`
- X: `@timestamp` (interval: 1h)
- Value: Max de un campo numérico asignado a nivel:
  ```
  // Runtime field (opcional)
  // worst_level_num: bueno=0, moderado=1, malo=2, peligroso=3
  ```
- Color palette: Green → Red

### 3. Guardar Dashboard
- Nombre: `AirVLC — Pipeline Status (Sprint 7)`
- Marcar como favorito para acceso rápido

## Uso
- El dashboard se alimenta automáticamente cuando la API recibe peticiones
  `/api/v2/risk`, `/api/v2/profile/recommend`, etc. — cada predicción se
  indexa en `airvlc-predictions-v2`.
- Para verificar que el pipeline funciona, enviar una petición y refrescar
  el dashboard.
