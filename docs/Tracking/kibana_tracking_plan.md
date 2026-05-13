# 📊 Plan de Implementación: Tracking de Model Drift en Kibana

Este documento resume los cambios técnicos aplicados en el backend de AirVLC para permitir el análisis visual de "Datos Reales vs. Predicciones a +24h, +48h, +72h" en Elasticsearch/Kibana, sin alterar el modelo LSTM.

## 🎯 Arquitectura de la Solución

El objetivo es engañar a Kibana para que pinte la predicción *no cuando se hizo*, sino *para cuándo aplica* (target_timestamp).

### Modificaciones en el Backend

1. **`es_indexer.py`**
   - Se ha modificado `_build_document()` para aceptar `target_timestamp`.
   - El mapeo del campo especial `@timestamp` de Elasticsearch (el que usa Kibana para el eje X) ahora apunta directamente al `target_timestamp`.
   - Se han añadido los campos `horizon_hours` (0, 24, 48, 72, o -1 para real) y `generated_at` (cuándo se emitió la inferencia).

2. **`routes_v2.py` (Endpoint `/_internal/predict_horizons`)**
   - Dado que este endpoint es llamado por Node-RED *justo después* de guardar los datos de WAQI en la base de datos Mongo (`aire_realtime`), hemos aprovechado el trigger para dos cosas:
     - **Indexar Datos Reales:** Busca el último dato insertado en MongoDB para cada estación y lo manda a Elasticsearch con `horizon_hours = -1` y `prediction_type = "actual"`.
     - **Indexar Predicciones:** Tras generar los forecasts (h=0, 24, 48, 72), calcula dinámicamente el `target_timestamp` sumando el horizonte temporal y empuja los resultados a Elasticsearch.

## 🛠️ Cómo configurar el Dashboard en Kibana

Una vez que pasen unas horas y Node-RED alimente el índice de `airvlc-predictions`, sigue estos pasos en Kibana para conseguir la gráfica del Colab:

1. **Accede a Kibana > Dashboard > Create new Dashboard**.
2. **Crea una nueva Visualización (Lens o TSVB)**.
   - **Eje X:** `@timestamp` (Date Histogram).
3. **Capa 1: El Dato Real (Ground Truth)**
   - **Métrica (Eje Y):** Average of `pm25_actual` (o el target_field que elijas).
   - **Filtro:** `horizon_hours: -1` AND `prediction_type: actual`
   - **Estilo:** Línea continua, color Azul Fuerte.
4. **Capa 2: Predicción a corto plazo (+0h / +24h)**
   - **Métrica (Eje Y):** Average of `pm25_pred`
   - **Filtro:** `horizon_hours: 24`
   - **Estilo:** Línea punteada (Dashed), color Naranja.
5. **Capa 3 y 4: Predicciones +48h y +72h**
   - Repite la capa 2 cambiando el filtro a `horizon_hours: 48` y `horizon_hours: 72` con otros colores.
6. **Desglose por Estación:** Si quieres verlo estación por estación, usa el campo `station` en "Split Series".

### 💡 ¿Qué verás?
Dado que estamos usando el `@timestamp` futuro para las predicciones, verás que la línea Naranja (Predicción) se "adelanta" en el gráfico hacia la derecha. A medida que pasan los días, la línea Azul (Real) avanzará y se superpondrá exactamente sobre las líneas naranjas/rojas que se dibujaron días atrás. Esto te mostrará visualmente el R² y el MAE en vivo.
