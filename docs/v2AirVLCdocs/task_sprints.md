# AirVLC v2 — Tareas

> Documento vivo. Cada Sprint añade su propio bloque y enlaza a su plan.

---

## Sprint 1 — Ingeniería de Datos Avanzada

- [x] Consolidación Multivariante (NO₂, O₃, PM2.5)
    - [x] Analizar los scripts de descarga de calidad del aire actuales para incluir NO₂ y O₃.
    - [x] Modificar el ETL (`prepare_colab_dataset.py`) para procesar estas nuevas métricas.
- [x] Feature Engineering Avanzado
    - [x] Implementar Lags temporales (t-1, t-3, t-6, t-24) para los 3 contaminantes.
    - [x] Implementar Rolling Statistics (Media móvil 6h, 12h, 24h) para los 3 contaminantes.
    - [x] Implementar variables temporales booleanas (`is_weekend`, `is_fallas`).
    - [x] Codificación trigonométrica (sin/cos) de hora y mes.
- [x] Construcción del Dataset
    - [x] Generar `master_dataset_colab_v2.csv` (sin pisar el v1).
    - [x] Validar la ausencia de NaNs y la consistencia temporal.

### Sprint 1 — Cierre (versionado paralelo v1↔v2)

- [x] Crear `src/ml/prepare_colab_dataset_v2.py` con salida a `master_dataset_colab_v2.csv`.
- [x] Restaurar `src/ml/prepare_colab_dataset.py` (v1) desde git para mantener viva la API v1.
- [x] Regenerar `data/processed/master_dataset_colab.csv` (v1) — 195,209 × 21.
- [x] Regenerar `data/processed/master_dataset_colab_v2.csv` (v2) — 194,993 × 45.
- [x] Crear `src/ml/validate_dataset_v2.py` (reporta filas, NaNs, gaps temporales).
- [x] Documentar diferencias y validación en [`sprint1/walkthrough.md`](sprint1/walkthrough.md).

---

## Sprint 2 — Modelado Multitarget en Google Colab

### Preparación local (cerrada el 5 de mayo de 2026)

- [x] Crear `src/ml/prepare_dataset_v2.py` (utilidades multitarget reutilizables).
- [x] Crear `src/ml/generate_scaler_v2.py` y producir `models/scaler_v2.pkl`.
- [x] Crear `src/scripts/generate_v2_notebook.py` (regenera el .ipynb por plantilla).
- [x] Crear `notebooks/11_v2_Colab_Multitarget.ipynb` con 3 arquitecturas:
    - [x] `LSTM_Attention_Multi` (Bahdanau, 3 salidas, 148.5k params).
    - [x] `CNN_LSTM_Attention_Multi` (Conv1D → LSTM → Attention, 98.4k params).
    - [x] `Transformer_Encoder_Multi` (MultiHeadAttention nativo Keras, 107.3k params).
- [x] Loss baseline `mse` + celda opcional con loss asimétrica.
- [x] Función `evaluate_multitarget` con MAE/RMSE/R² por target en µg/m³ reales.
- [x] Documentar plan, tareas y walkthrough en [`sprint2/`](sprint2/).

### Ejecución en Colab (cerrada el 6 de mayo de 2026)

- [x] Subir `master_dataset_colab_v2.csv` y `scaler_v2.pkl` a `MyDrive/AirVLC_v2/`.
- [x] Ejecutar `11_v2_Colab_Multitarget.ipynb` en Colab GPU (T4) de arriba a abajo.
- [x] Descargar `modelo_11_v2_Multitarget/` a `models/` local.
- [x] Rellenar tablas de métricas reales en [`sprint2/walkthrough.md`](sprint2/walkthrough.md).

### Cierre — Comparativa visual en Kibana (6 de mayo de 2026)

- [x] Crear `src/scripts/build_model_comparison_csv.py` que une métricas v1 (`modelo_10_Colab_Comparativas/day9_comparison_results.csv`) y v2 (`modelo_11_v2_Multitarget/day11_v2_results.csv`) en `data/processed/model_comparison_v1_v2.csv`.
- [x] Añadir pipeline Logstash `docker/logstash/pipeline/model_comparison.conf` + template `es-template-model-comparison.json` que indexa el CSV en `airvlc-model-comparison-v1v2`.
- [x] Crear `src/scripts/setup_kibana_v2_comparison.py` que genera el dashboard `airvlc-v1-vs-v2` con **15 visualizaciones Lens reales** (KPIs ganador v1/v2, bars R²/MAE/RMSE PM2.5 lado a lado, heatmap arch×target v2, barras de tiempo y params, tabla detalle).
- [x] Resultado clave: **v2 LSTM_Attention_Multi (PM2.5)** mejora a **v1 LSTM_Attention** un −40.5% MAE, −39.8% RMSE, +0.0899 R² **y** además predice NO₂/O₃ con R² ≥ 0.82.

**🥇 Ganador**: `LSTM_Attention_Multi` — R² medio 0.8610 (PM2.5: 0.8571 · NO₂: 0.8397 · O₃: 0.8861).

**🔗 Dashboard**: <http://localhost:5601/app/dashboards#/view/airvlc-v1-vs-v2>

---

## Sprint 3 — Backend Flask v2 (próxima tanda)

- **Docs Sprint 3**:
    - [`sprint3/implementation_plan.md`](sprint3/implementation_plan.md)
    - [`sprint3/task.md`](sprint3/task.md)
    - [`sprint3/walkthrough.md`](sprint3/walkthrough.md)

- [x] `src/api/feature_extractor_v2.py` (carga `master_dataset_colab_v2.csv` y `scaler_v2.pkl`).
- [x] `src/ml/risk_classifier_v2.py` con criterio ICA: peor de los 3 contaminantes.
- [x] Nuevas rutas `/api/v2/predict`, `/api/v2/risk`, `/api/v2/chat`.
- [x] Actualizar `chatbot_orchestrator_v2.py` (v2) para narrar los 3 contaminantes.
- [x] Indexar predicciones v2 en un nuevo índice `airvlc-predictions-v2`.
- [ ] Tests + demo local (pendiente de cerrar el sprint).

---

## Sprint 4 — App Flutter v2 (multitarget + diferencial)

- **Docs Sprint 4**:
    - [`sprint4/implementation_plan.md`](sprint4/implementation_plan.md)
    - [`sprint4/task.md`](sprint4/task.md)
    - [`sprint4/walkthrough.md`](sprint4/walkthrough.md)
    - [`sprint4/aws_keys_setup.md`](sprint4/aws_keys_setup.md)

### Backend (extensiones v2, manteniendo retro-compat)

- [x] `POST /api/v2/profile/recommend` — perfil de salud + worst v2 → recomendación humanizada.
- [x] `POST /api/v2/route` — ordena tramos por proximidad usando `STATION_COORDS`.
- [x] `ChatbotOrchestratorV2` con 3 intents nuevos (`ConsultarContaminante`, `CompararEstaciones`, `ConsejoSalud`).
- [x] Tests `tests/api/test_routes_v2_sprint4.py` en verde.

### App Flutter (`app/lib/` desde cero)

- [x] Bootstrap (`main.dart`, `app.dart`, theme, bottom nav).
- [x] `core/api/airvlc_api_client.dart` + modelos.
- [x] **F1** Onboarding + Perfil persistente + Dashboard adaptado al perfil.
- [x] **F2** Planificador de Ruta saludable (consume `/api/v2/route`).
- [x] **F3** Suscripciones + notificaciones locales + polling cada 15 min.
- [x] **F4** Modo voz manos libres (`speech_to_text` → `/api/v2/chat` → `flutter_tts`).
- [x] **F5** Comparador de estaciones in-app con slider temporal.
- [x] `app/test/widget_test.dart` — smoke test del bootstrap.

### AWS Lex (sin reentrenar)

- [ ] Añadir slot types `PollutantType`, `Activity` y los 3 intents nuevos en consola.
- [ ] `Build` del bot y verificación de utterances.

### Demo y entrega

- [ ] Capturas en `docs/v2AirVLCdocs/sprint4/img/` y vídeo ≤ 3 min.
- [ ] Métricas reales (latencias p50/p95 por endpoint, docs ES/día) rellenadas en `walkthrough.md`.

---

## Sprint 5 — Data Freshness y Refresco Horario

- **Docs Sprint 5**:
    - [`sprint5/implementation_plan.md`](sprint5/implementation_plan.md)
    - [`sprint5/task.md`](sprint5/task.md)
    - [`sprint5/walkthrough.md`](sprint5/walkthrough.md)
    - [`sprint5/data_pipeline_setup.md`](sprint5/data_pipeline_setup.md)
    - [`sprint5/launchd/com.airvlc.hourly_refresh.plist`](sprint5/launchd/com.airvlc.hourly_refresh.plist)

### Fase A — Backend: exponer frescura de datos

- [x] `FeatureExtractorV2.get_features()` → devuelve 3-tuple `(features, station, meta)` con `data_timestamp`, `data_age_minutes`, `data_window_start`.
- [x] `FeatureExtractorV2.reload()` — recarga CSV en memoria sin reiniciar Flask.
- [x] Todos los endpoints v2 (`/predict`, `/risk`, `/profile/recommend`, `/route`) incluyen `server_timestamp` + campos de frescura.
- [x] `POST /api/v2/_internal/reload` protegido por header `X-Internal-Token`.

### Fase B — Pipeline de ingesta horaria

- [x] `src/ingestion/valencia_air_quality_client.py` — descarga contaminantes Ayuntamiento → Mongo `aire_realtime` con upsert idempotente.
- [x] `src/ml/append_to_dataset_v2.py` — append incremental al CSV v2 (lags/rolling solo de la cola).
- [x] `src/scripts/hourly_data_refresh.py` — scheduler `--once` / `--daemon` + logs en `~/airvlc_logs/`.

### Fase C — Flutter: visualización + autorefresco

- [x] Modelo `Prediction` ampliado con `dataTimestamp`, `dataAgeMinutes`, `dataWindowStart`, `serverTimestamp`.
- [x] Widget `FreshnessChip` — "Datos hasta HH:MM — hace N min" con coloración verde/ámbar/rojo.
- [x] `RefreshScheduler` — Timer.periodic minute-tick + `onAppResumed` + check `dataAge > 70`.
- [x] Integración en `DashboardScreen` (chip encima de cards + scheduler + pull-to-refresh).

### Fase D — Tests y documentación

- [x] 25 tests pytest en verde:
    - `tests/api/test_v2_data_freshness.py` — 7 tests (payloads freshness + reload).
    - `tests/ingestion/test_valencia_client.py` — 10 tests (normalización + parsing idempotente).
    - `tests/ml/test_append_to_dataset_v2.py` — 8 tests (lags, rolling, trig, fallas).
- [x] `app/test/freshness_chip_test.dart` — 5 widget tests (3 ramas color + null + spinner).
- [x] Docs en `docs/v2AirVLCdocs/sprint5/` (plan, task, walkthrough, data_pipeline_setup, plist).

---

## Sprint 6 — Contaminantes en vivo (WAQI) + append truthful

- **Docs Sprint 6**:
    - [`sprint6/implementation_plan.md`](sprint6/implementation_plan.md)
    - [`sprint6/task.md`](sprint6/task.md)
    - [`sprint6/walkthrough.md`](sprint6/walkthrough.md)
    - [`sprint6/data_pipeline_setup.md`](sprint6/data_pipeline_setup.md)

### Ingesta y conversión

- [x] `src/ingestion/aqi_conversion.py` — sub-índice EPA → µg/m³ (PM2.5, NO2, O3).
- [x] `src/ingestion/waqi_air_quality_client.py` — `fetch_waqi_air_quality`, Mongo `aire_realtime`, `source=waqi`.
- [x] `src/ingestion/waqi_station_map.py` — overrides opcionales `WAQI_STATION_UID_OVERRIDE`.
- [x] `src/scripts/discover_waqi_stations.py` — bbox + Haversine vs `STATION_COORDS`.

### Append y orquestación

- [x] `src/ml/append_to_dataset_v2.py` — `AIRVLC_MAX_DATA_AGE_H` + `_filter_by_staleness`.
- [x] `src/scripts/hourly_data_refresh.py` — `AIRVLC_AIR_SOURCE` (`waqi` | `geoportal`).

### Tests

- [x] `tests/ingestion/test_aqi_conversion.py`, `tests/ingestion/test_waqi_client.py`, `tests/ml/test_append_freshness_guard.py`.

### Operativa

- [ ] Añadir `WAQI_TOKEN` al `.env` y validar pipeline `--once` con datos recientes.
