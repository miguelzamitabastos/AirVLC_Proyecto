# Sprint 5 — Data Freshness y Refresco Horario

## Objetivo

Pasar el modelo de "predicción sobre dataset estático" a "predicción sobre datos refrescados cada hora", manteniendo coherencia con los sensores reales del Ayuntamiento de Valencia que entrenaron el modelo. Mostrar al usuario claramente la antigüedad de los datos y refrescar automáticamente cada hora en la app.

## Decisiones Arquitectónicas

| Decisión | Elección | Justificación |
|----------|----------|---------------|
| Fuente contaminantes | API Datos Abiertos Ayuntamiento Valencia | Mismos sensores que entrenaron el modelo |
| Fuente meteo | OpenWeather One Call 3.0 (ya integrado) | T, viento, humedad, precipitación |
| Scheduler | Script externo `--daemon` (launchd/cron) | Patrón ya usado en `sync_meteo_to_es.py` |
| Recarga API | POST `/_internal/reload` con token | Evita reiniciar Flask cada hora |
| AEMET | Se mantiene como histórico (no horario) | Solo publica datos diarios |

## Fases Implementadas

### Fase A — Backend: exponer frescura de datos

- **`FeatureExtractorV2.get_features()`** ahora devuelve una tupla `(features, station, meta)` donde `meta` contiene:
  - `data_timestamp`: timestamp de la última fila del CSV usada
  - `data_window_start`: inicio de la ventana de 24h
  - `data_age_minutes`: antigüedad en minutos

- **`FeatureExtractorV2.reload()`**: nuevo método que recarga el CSV en memoria sin reiniciar Flask.

- **Todos los endpoints v2** (`/predict`, `/risk`, `/profile/recommend`, `/route`) ahora incluyen:
  - `server_timestamp`: cuándo respondió el backend
  - `data_timestamp`, `data_age_minutes`, `data_window_start`: frescura del dato

- **`POST /api/v2/_internal/reload`**: endpoint protegido por header `X-Internal-Token` que fuerza la recarga del CSV en memoria.

### Fase B — Pipeline de ingesta horaria

- **B.1 `valencia_air_quality_client.py`**: cliente que descarga contaminantes de la API de datos abiertos del Ayuntamiento, normaliza estaciones al canónico del CSV v2, y hace upsert idempotente en `airvlc_db.aire_realtime`.

- **B.2 `append_to_dataset_v2.py`**: script incremental que lee la cola del CSV (48h), cruza con datos nuevos de Mongo, recalcula lags/rolling solo para las filas nuevas, y hace append al CSV.

- **B.3 `hourly_data_refresh.py`**: scheduler que orquesta los 4 pasos (fetch aire → fetch meteo → append CSV → reload API). Soporta `--once` y `--daemon`.

### Fase C — Flutter: visualización + autorefresco

- **C.1 Modelo `Prediction`**: ampliado con `dataTimestamp`, `dataAgeMinutes`, `dataWindowStart`, `serverTimestamp`.

- **C.2 Widget `FreshnessChip`**: muestra "Datos hasta HH:MM — hace N min" con coloración verde/ámbar/rojo según antigüedad. Se actualiza cada minuto vía `Timer.periodic`.

- **C.3 `RefreshScheduler`**: servicio que dispara refresco automático cuando cambia la hora o `dataAgeMinutes > 70`. También verifica al reanudar la app (`AppLifecycleState.resumed`).

### Fase D — Tests y documentación

- **25 tests pytest** en verde:
  - `test_v2_data_freshness.py`: 7 tests (freshness en payloads + reload endpoint)
  - `test_valencia_client.py`: 10 tests (normalización + parsing idempotente)
  - `test_append_to_dataset_v2.py`: 8 tests (lags, rolling, trig, fallas)
- **Widget test `freshness_chip_test.dart`**: 5 tests (3 ramas de color + null + spinner)

## Archivos Nuevos

| Archivo | Descripción |
|---------|-------------|
| `src/ingestion/valencia_air_quality_client.py` | Cliente API Valencia → Mongo |
| `src/ml/append_to_dataset_v2.py` | Append incremental al CSV v2 |
| `src/scripts/hourly_data_refresh.py` | Scheduler horario |
| `app/lib/features/dashboard/freshness_chip.dart` | Widget de frescura |
| `app/lib/core/services/refresh_scheduler.dart` | Servicio autorefresco |
| `tests/api/test_v2_data_freshness.py` | Tests de frescura API |
| `tests/ingestion/test_valencia_client.py` | Tests cliente Valencia |
| `tests/ml/test_append_to_dataset_v2.py` | Tests append incremental |
| `app/test/freshness_chip_test.dart` | Widget test FreshnessChip |

## Archivos Modificados

| Archivo | Cambios |
|---------|---------|
| `src/api/feature_extractor_v2.py` | `get_features()` → 3-tuple + `reload()` |
| `src/api/routes_v2.py` | Freshness meta en todos los endpoints + `/_internal/reload` |
| `app/lib/core/api/models/prediction.dart` | Campos de frescura |
| `app/lib/core/api/models/risk_response.dart` | Pasar parentJson a Prediction |
| `app/lib/features/dashboard/dashboard_screen.dart` | FreshnessChip + RefreshScheduler |
