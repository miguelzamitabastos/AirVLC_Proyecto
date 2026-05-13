# Sprint 5 — Task Checklist

> Fecha: 7 mayo 2026

## Fase A: Backend — Exponer frescura de datos
- [x] Modificar `FeatureExtractorV2.get_features()` para devolver meta con timestamps
- [x] Añadir método `reload()` a `FeatureExtractorV2`
- [x] Modificar `routes_v2.py`: incluir `data_timestamp`, `data_age_minutes`, `data_window_start` en respuestas `/predict`, `/risk`, `/profile/recommend`, `/route`
- [x] Añadir `server_timestamp` a todas las respuestas
- [x] Añadir endpoint `POST /api/v2/_internal/reload` protegido por `X-Internal-Token`

## Fase B: Backend — Pipeline de ingesta horaria
- [x] B.1: Crear `src/ingestion/valencia_air_quality_client.py`
  - [x] Endpoint parametrizable por env `VALENCIA_AIR_API_URL`
  - [x] Normalización de estaciones al canónico del CSV v2
  - [x] Upsert idempotente en Mongo `aire_realtime` con clave `{estacion, fecha_iso}`
- [x] B.2: Crear `src/ml/append_to_dataset_v2.py`
  - [x] Lectura de cola del CSV (48h por estación)
  - [x] Cruce con datos nuevos de Mongo
  - [x] Recálculo incremental de lags/rolling/trig/booleans
  - [x] Append al CSV sin recalcular todo
- [x] B.3: Crear `src/scripts/hourly_data_refresh.py`
  - [x] Modo `--once` y `--daemon`
  - [x] Orquesta: fetch aire → fetch meteo → append → reload API
  - [x] Logging a `~/airvlc_logs/hourly_refresh.log`

## Fase C: Flutter — Visualización + autorefresco
- [x] C.1: Ampliar modelo `Prediction` con `dataTimestamp`, `dataAgeMinutes`, `dataWindowStart`, `serverTimestamp`
- [x] C.1: Actualizar `RiskResponse.fromJson` para pasar `parentJson`
- [x] C.2: Crear widget `FreshnessChip` con coloración verde/ámbar/rojo
  - [x] Timer.periodic cada 60s para actualizar "hace N min"
  - [x] Spinner mientras se refresca
- [x] C.3: Crear `RefreshScheduler` en Flutter
  - [x] Timer.periodic minute-tick
  - [x] Check hora cambiada o dataAge > 70
  - [x] Observer `AppLifecycleState.resumed`
- [x] C.3: Integrar FreshnessChip y RefreshScheduler en `DashboardScreen`

## Fase D: Tests, docs y operación
- [x] `tests/api/test_v2_data_freshness.py` — 7 tests
- [x] `tests/ingestion/test_valencia_client.py` — 10 tests
- [x] `tests/ml/test_append_to_dataset_v2.py` — 8 tests
- [x] `app/test/freshness_chip_test.dart` — 5 tests
- [x] Docs en `docs/v2AirVLCdocs/sprint5/`
  - [x] `implementation_plan.md`
  - [x] `task.md` (este archivo)
  - [x] `walkthrough.md`
  - [x] `data_pipeline_setup.md`
  - [x] `launchd/com.airvlc.hourly_refresh.plist`
- [x] Actualizar `task_sprints.md`
