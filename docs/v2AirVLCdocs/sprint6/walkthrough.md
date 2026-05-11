# Sprint 6 — Walkthrough

## Prerrequisitos

- `WAQI_TOKEN` en `.env`
- `MONGO_URI`, `OPENWEATHER_API_KEY` (meteo)
- Variables opcionales: `AIRVLC_AIR_SOURCE=waqi`, `AIRVLC_MAX_DATA_AGE_H=6`

## Pasos de verificación

1. Ejecutar `./venv/bin/python src/scripts/hourly_data_refresh.py --once`
2. Confirmar en logs: Paso 1 `parsed > 0` y Mongo upsert con `inserted` o `modified` > 0 cuando WAQI responde.
3. Confirmar Paso 3 `appended > 0` cuando hay filas nuevas con `fecha` > última del CSV y dentro de la ventana de frescura.
4. En la app: Dashboard muestra **FreshnessChip** en verde si `data_age_minutes` < umbral.

## Capturas (rellenar en entrega)

- Log del pipeline con `source=waqi`
- Pantalla Flutter con chip verde y hora de datos

## Notas

- Si WAQI no devuelve algún contaminante (p. ej. O3), esa estación no genera documento (política estricta).
- El Geoportal histórico sigue disponible con `AIRVLC_AIR_SOURCE=geoportal` para demos offline.
