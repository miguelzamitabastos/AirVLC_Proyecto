# Sprint 6 — Checklist

## Implementación

- [x] `aqi_conversion.py` — PM2.5, NO2, O3 sub-índice EPA → µg/m³
- [x] `waqi_air_quality_client.py` — `fetch_waqi_air_quality`, upsert Mongo `aire_realtime`, `source=waqi`
- [x] `waqi_station_map.py` — `WAQI_STATION_UID_OVERRIDE` (opcional; vacío = solo geo)
- [x] `discover_waqi_stations.py` — bbox Valencia + emparejamiento Haversine
- [x] `append_to_dataset_v2.py` — `AIRVLC_MAX_DATA_AGE_H` + `_filter_by_staleness`
- [x] `hourly_data_refresh.py` — `AIRVLC_AIR_SOURCE` (`waqi` | `geoportal`)

## Tests

- [x] `tests/ingestion/test_aqi_conversion.py`
- [x] `tests/ingestion/test_waqi_client.py` (HTTP mock)
- [x] `tests/ml/test_append_freshness_guard.py`

## Operativa

- [ ] Crear `WAQI_TOKEN` en https://aqicn.org/data-platform/token/ y añadir a `.env`
- [ ] (Opcional) Ejecutar `python src/scripts/discover_waqi_stations.py` y pegar UIDs en `waqi_station_map.py`
- [ ] Verificar pipeline: `./venv/bin/python src/scripts/hourly_data_refresh.py --once`
- [ ] Comprobar chip de frescura en Flutter con `data_timestamp` reciente
