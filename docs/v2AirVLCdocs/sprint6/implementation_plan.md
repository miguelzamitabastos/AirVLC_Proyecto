# Sprint 6 — Contaminantes en vivo (WAQI) y política truthful

## Objetivo

Sustituir el feed del Geoportal de Valencia (con `fecha_carga` congelada en 2023) por **World Air Quality Index (WAQI / aqicn)** para obtener PM2.5, NO2 y O3 con marca temporal reciente, convertir sub-índices EPA a µg/m³, y hacer **append al CSV solo con datos realmente frescos** (ventana `AIRVLC_MAX_DATA_AGE_H`).

## Entregables

| Componente | Ruta |
|------------|------|
| Conversión AQI | `src/ingestion/aqi_conversion.py` |
| Cliente WAQI | `src/ingestion/waqi_air_quality_client.py` |
| Overrides opcional UID | `src/ingestion/waqi_station_map.py` |
| Descubrimiento estaciones | `src/scripts/discover_waqi_stations.py` |
| Guard staleness append | `src/ml/append_to_dataset_v2.py` (`_filter_by_staleness`) |
| Orquestador | `src/scripts/hourly_data_refresh.py` (`AIRVLC_AIR_SOURCE`) |
| Tests | `tests/ingestion/test_aqi_conversion.py`, `test_waqi_client.py`, `tests/ml/test_append_freshness_guard.py` |

## Decisiones

- **Fuente aire**: WAQI API (`api.waqi.info`), por defecto `feed/geo:lat;lon` usando `STATION_COORDS`.
- **Sin reentrenar**: mismas 44 features y `scaler_v2.pkl`; solo cambia el origen temporal de los contaminantes.
- **Truthful**: si los datos superan la ventana de frescura o WAQI falla, el CSV no crece artificialmente; la app ya muestra la edad real (Sprint 5).
