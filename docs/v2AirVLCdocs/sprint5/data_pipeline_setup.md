# Sprint 5 — Data Pipeline Setup

Guía de configuración del pipeline de refresco horario de datos.

---

## Variables de Entorno

Añade estas variables a tu `.env` (las que no tengas ya):

```bash
# --- MongoDB Atlas (ya existente) ---
MONGO_URI="mongodb+srv://..."

# --- OpenWeather API (ya existente) ---
OPENWEATHER_API_KEY="..."

# --- Valencia Air Quality API (Sprint 5, opcional) ---
# URL base de la API de datos abiertos del Ayuntamiento de Valencia.
# Si no se especifica, usa la URL por defecto (Opendatasoft).
# VALENCIA_AIR_API_URL="https://valencia.opendatasoft.com/api/explore/v2.1/catalog/datasets/rvvcca-calidad-del-aire-en-tiempo-real-red-de-vigilancia-y-control/records"

# --- Token interno para recarga de la API (Sprint 5) ---
# Protege el endpoint POST /api/v2/_internal/reload.
# Si no se especifica, usa el default "airvlc-reload-secret".
AIRVLC_INTERNAL_RELOAD_TOKEN="airvlc-reload-secret"

# --- URL base de la API Flask (Sprint 5, opcional) ---
# El scheduler usa esta URL para notificar la recarga.
# Default: http://localhost:5001
# AIRVLC_API_URL="http://localhost:5001"
```

## Ejecución Manual (debug/test)

```bash
# Activar virtualenv
source venv/bin/activate

# 1. Probar el cliente de Valencia en aislamiento
python src/ingestion/valencia_air_quality_client.py --hours 6

# 2. Probar el append incremental (modo dry-run primero)
python src/ml/append_to_dataset_v2.py --dry-run

# 3. Ejecutar el pipeline completo una vez
python src/scripts/hourly_data_refresh.py --once

# 4. Ejecutar el pipeline en modo daemon
python src/scripts/hourly_data_refresh.py --daemon
```

## Configuración con launchd (macOS)

Para que el pipeline se ejecute automáticamente cada hora en macOS:

### 1. Copiar el plist

```bash
cp docs/v2AirVLCdocs/sprint5/launchd/com.airvlc.hourly_refresh.plist \
   ~/Library/LaunchAgents/
```

### 2. Editar las rutas

Abre el plist y ajusta:
- `<RUTA_PROYECTO>` → ruta absoluta al proyecto
- `<RUTA_PYTHON>` → ruta al python del virtualenv

### 3. Cargar el servicio

```bash
launchctl load ~/Library/LaunchAgents/com.airvlc.hourly_refresh.plist
```

### 4. Verificar

```bash
# Ver si está cargado
launchctl list | grep airvlc

# Ver logs
tail -f ~/airvlc_logs/hourly_refresh.log
```

### 5. Detener

```bash
launchctl unload ~/Library/LaunchAgents/com.airvlc.hourly_refresh.plist
```

## Verificación del Endpoint de Recarga

```bash
# Probar que la recarga funciona (con Flask arrancado)
curl -X POST http://localhost:5001/api/v2/_internal/reload \
  -H "X-Internal-Token: airvlc-reload-secret"

# Respuesta esperada:
# {"success": true, "message": "Dataset v2 recargado en memoria.", "server_timestamp": "..."}
```

## Troubleshooting

### El scheduler no descarga datos de Valencia
- **Causa**: La API de datos abiertos puede estar caída o el dataset ha cambiado de nombre.
- **Solución**: Verificar manualmente `curl "https://valencia.opendatasoft.com/api/explore/v2.1/catalog/datasets/rvvcca-calidad-del-aire-en-tiempo-real-red-de-vigilancia-y-control/records?limit=1"`. Si no responde, sobreescribir `VALENCIA_AIR_API_URL` con la URL correcta.

### `data_age_minutes` crece sin parar
- **Causa**: El scheduler no está corriendo o la API no recargó.
- **Solución**: 
  1. Verificar que `hourly_data_refresh.py --daemon` está corriendo
  2. Verificar que Flask está arrancado para recibir el POST de recarga
  3. Revisar logs: `tail ~/airvlc_logs/hourly_refresh.log`

### El FreshnessChip está en rojo
- **Significado**: Los datos tienen más de 180 minutos de antigüedad.
- **No es un error**: La app sigue funcionando con datos antiguos. El chip rojo es una señal visual de que el scheduler necesita atención.

### Mongo no tiene documentos en `aire_realtime`
- **Verificar**: `mongosh "MONGO_URI" --eval 'db.aire_realtime.countDocuments({})'`
- **Causa probable**: El cliente no reconoce los nombres de estación de la API. Revisar los logs del cliente.

## Colecciones MongoDB

| Colección | Descripción | Origen |
|-----------|-------------|--------|
| `meteo_realtime` | Datos meteorológicos de OpenWeather | `openweather_client.py` |
| `aire_realtime` | Contaminantes del Ayuntamiento de Valencia | `valencia_air_quality_client.py` (Sprint 5) |
| `meteo_historical` | Datos climatológicos diarios AEMET | Carga inicial |
