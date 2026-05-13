# Sprint 6 — Configuración del pipeline WAQI

## Variable obligatoria: `WAQI_TOKEN`

1. Registro en la plataforma de datos de aqicn: https://aqicn.org/data-platform/token/
2. Copiar el token y añadirlo al `.env` del proyecto:

```bash
WAQI_TOKEN="tu_token_aqui"
```

Sin este token, `fetch_waqi_air_quality` falla con un mensaje explícito.

## Fuente de contaminantes: `AIRVLC_AIR_SOURCE`

| Valor | Descripción |
|-------|-------------|
| `waqi` (default) | API en vivo `api.waqi.info` — geo por estación o UID opcional |
| `geoportal` | Cliente anterior (`valencia_air_quality_client`) — útil si el feed volviera a actualizarse |

```bash
AIRVLC_AIR_SOURCE=waqi
```

## Ventana de frescura (append truthful): `AIRVLC_MAX_DATA_AGE_H`

Filas en Mongo más antiguas que este número de horas **no** se usan para append (evita ensuciar el CSV si la API está stale).

```bash
AIRVLC_MAX_DATA_AGE_H=6
```

Default: `6` si no se define.

## Overrides opcionales de estación WAQI (`@uid`)

Por defecto cada estación usa:

`GET https://api.waqi.info/feed/geo:{lat};{lon}/?token=...`

con `{lat},{lon}` de `STATION_COORDS` en `src/api/es_indexer.py`.

Si quieres fijar una estación concreta del índice WAQI:

1. Ejecutar:

```bash
./venv/bin/python src/scripts/discover_waqi_stations.py
```

2. Copiar el bloque `WAQI_STATION_UID_OVERRIDE` sugerido a `src/ingestion/waqi_station_map.py`.

Con un UID definido, la URL pasa a ser `feed/@{uid}/`.

## Resto del pipeline (Sprint 5)

- Meteo: `OPENWEATHER_API_KEY` — ver `openweather_client.py` (prioriza Current 2.5).
- Recarga API: `AIRVLC_API_URL`, `AIRVLC_INTERNAL_RELOAD_TOKEN`.
- Logs scheduler: `~/airvlc_logs/hourly_refresh.log`.
