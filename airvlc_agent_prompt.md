# AirVLC — Diagnóstico y reparación del pipeline de datos en tiempo real

Eres un agente de ingeniería trabajando sobre el repositorio **AirVLC** (predicción de calidad del aire en Valencia con LSTM + Bahdanau Attention, API Flask, MongoDB Atlas, Node-RED en Docker, app Flutter).

Tu objetivo es **diagnosticar y arreglar tres problemas concretos** que afectan a la frescura de los datos que ve el usuario final. Trabaja por fases con checkpoints. **No toques código hasta haber completado la Fase 1 de diagnóstico y obtener confirmación explícita del humano para pasar a la Fase 2.**

---

## Contexto técnico imprescindible

### Cadena de datos (de fuente a usuario)

```
WAQI API
   ↓ (flows.json en Node-RED, contenedor Docker, cron 60min)
MongoDB Atlas (db: airvlc_db, collection: aire_realtime)
   ↓ (script de refresco — sospechoso de fallar)
data/processed/master_dataset_colab_v2.csv
   ↓ (leído por src/api/feature_extractor_v2.py)
API Flask (src/api/app.py + routes_v2.py)
   ↓ (HTTP)
App Flutter
```

### Componentes clave del repo

| Ruta | Rol |
|---|---|
| `src/api/feature_extractor_v2.py` | Carga el CSV en memoria, ventana 24h, escalado. Expone `data_timestamp` y `data_age_minutes` en `meta`. |
| `src/api/routes_v2.py` | Endpoints v2. Contiene `_fetch_observed_from_mongo` que filtra `is_synthetic: { $ne: true }`. |
| `src/api/model_loader.py` | Carga `LSTM_Attention_Multi` desde `models/modelo_11_v2_Multitarget/best_model_v2.keras`. |
| `src/ml/append_to_dataset_v2.py` | **Sospechoso #1.** Script que debería refrescar el CSV desde Mongo. |
| `tests/ml/test_append_freshness_guard.py` | Test de freshness que existe pero podría no estar bloqueando inserts viejos. |

### Estaciones canónicas v2 (las 7 únicas válidas)

`Francia`, `Molí del Sol`, `Pista de Silla`, `Puerto Moll Trans. Ponent`, `Puerto Valencia`, `Puerto llit antic Túria`, `Universidad Politécnica`.

---

## Problemas reportados

**P1. Retraso de ~4h en MongoDB** respecto al cron de 60 min de Node-RED. Los inserts no aparecen cuando deberían.

**P2. La app de Flutter muestra "Datos del 09/05 — hace 2 días"** cuando hoy es 11/05 (~48h de desfase, no minutos). Chip rojo de advertencia siempre visible.

**P3. Las predicciones a +24/+48/+72h son razonables pero "planas"** — nunca anticipan picos de contaminación. Esto es un problema separado del pipeline, probablemente comportamiento esperado del modelo.

---

# FASE 1 — Diagnóstico (read-only, NO modificar código)

Ejecuta los siguientes pasos en orden y reporta hallazgos al humano al final. Si algún comando falla por entorno (falta `mongosh`, falta acceso a Docker, etc.), dilo y continúa con los demás.

## 1.1 — Estado del contenedor Node-RED

```bash
docker ps --filter "name=node-red" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
docker logs --tail 300 --timestamps $(docker ps -qf "name=node-red") 2>&1 | tail -100
```

**Reporta:**
- ¿Contenedor `running` o `restarting`?
- ¿Hay errores `429`, `ECONNREFUSED`, `AuthenticationFailed`, `timeout` en los últimos logs?
- ¿La marca de tiempo del log más reciente coincide con el cron de 60 min, o lleva horas/días sin actividad?

## 1.2 — Estado del CSV que sirve la API

```bash
stat data/processed/master_dataset_colab_v2.csv
tail -3 data/processed/master_dataset_colab_v2.csv
```

**Reporta:**
- Fecha exacta de `Modify:` del CSV.
- Las últimas 3 filas: ¿qué `fecha` tienen? ¿De qué estación?
- ¿Hay un cron/systemd timer que lo regenere? Busca con:
  ```bash
  crontab -l 2>/dev/null
  ls -la /etc/cron.* 2>/dev/null | grep -i airvlc
  systemctl list-timers --all 2>/dev/null | grep -i airvlc
  docker ps --format "{{.Names}}" | xargs -I{} docker exec {} crontab -l 2>/dev/null
  ```

## 1.3 — Inspección directa de MongoDB

Pide al humano que ejecute en `mongosh` y te pegue la salida (o ejecútalo tú si tienes `MONGO_URI` en `.env`):

```js
use airvlc_db

// Últimos 5 documentos de Francia
db.aire_realtime.find({ estacion: "Francia" })
  .sort({ fecha: -1 }).limit(5).toArray()

// Tipo del campo fecha (debe ser Date, no string)
db.aire_realtime.aggregate([
  { $match: { estacion: "Francia" } },
  { $project: { fecha: 1, tipo: { $type: "$fecha" } } },
  { $sort: { fecha: -1 } }, { $limit: 3 }
])

// Último insert por estación
db.aire_realtime.aggregate([
  { $group: { _id: "$estacion", ultimo: { $max: "$fecha" }, total: { $sum: 1 } } },
  { $sort: { ultimo: -1 } }
])

// Volumen reciente
const hace24h = new Date(Date.now() - 24*3600*1000)
const hace72h = new Date(Date.now() - 72*3600*1000)
print("Últimas 24h:", db.aire_realtime.countDocuments({ fecha: { $gte: hace24h } }))
print("Últimas 72h:", db.aire_realtime.countDocuments({ fecha: { $gte: hace72h } }))

// ¿Está marcando todo como sintético?
print("Recientes synthetic=true:", db.aire_realtime.countDocuments({
  fecha: { $gte: hace24h }, is_synthetic: true }))
print("Recientes synthetic≠true:", db.aire_realtime.countDocuments({
  fecha: { $gte: hace24h }, is_synthetic: { $ne: true } }))
```

**Reporta:**
- `tipo` del campo `fecha` (`date` esperado; si es `string` ya tienes una causa raíz).
- ¿La fecha del último documento por estación es de hoy o de hace días?
- ¿Cuántos inserts en las últimas 24h? (con 7 estaciones × 24h = ~168 esperados).
- ¿Están marcados como `is_synthetic: true`? Si sí, la API los filtra fuera en `_fetch_observed_from_mongo`.

## 1.4 — Comportamiento real de la API

```bash
# Ajusta puerto si no es 5001
curl -s "http://localhost:5001/api/v2/quality/Francia" | python3 -m json.tool > /tmp/api_response.json
cat /tmp/api_response.json
```

**Reporta los campos:**
- `meta.data_timestamp`
- `meta.data_age_minutes`
- `meta.observed_last_timestamp` (si existe)
- `predictions` (valores)

## 1.5 — Lectura crítica del script de refresco

Lee **completo** `src/ml/append_to_dataset_v2.py` y reporta:

- ¿Cómo se invoca? ¿Hay un `if __name__ == "__main__"` con `argparse`?
- ¿Filtra `is_synthetic`? ¿Cómo?
- ¿Tiene un guard de freshness que pueda estar abortando silenciosamente?
- ¿Loguea a stdout, a fichero, o se traga errores?
- ¿Hace `dropna` o filtros que puedan estar descartando filas válidas?

Lee también `tests/ml/test_append_freshness_guard.py` para entender qué freshness se espera.

## 1.6 — Tratamiento de timestamps en la app Flutter

Si la carpeta de Flutter está en este repo, busca:

```bash
grep -rn "DateTime.parse\|DateFormat\|formatDate" lib/ 2>/dev/null | head -30
```

**Reporta:** ¿hay `DateTime.parse(...)` sin `.toLocal()` antes de formatear? Esto produciría un desfase de ~2h (CEST = UTC+2) pero **no** los 48h del chip — sin embargo es un bug residual a corregir.

## Checkpoint Fase 1

Antes de pasar a la Fase 2, **resume al humano**:

1. **Causa raíz de P2 (chip "hace 2 días")**: en qué capa se rompe la cadena (Node-RED parado / Mongo sin inserts / CSV congelado / API con bug / Flutter con bug de TZ).
2. **Causa raíz de P1 (retraso de 4h)**: si es el mismo problema que P2 o uno distinto.
3. **Confirmación de P3**: el comportamiento plano del modelo es esperado dada la implementación actual de `get_features_for_horizon` (solo actualiza features temporales, no meteorológicas).
4. **Plan de fix propuesto**, con archivos a modificar y cambios concretos.

**ESPERA confirmación explícita del humano antes de tocar código.**

---

# FASE 2 — Reparación (solo tras confirmación)

Aplica solo los fixes correspondientes a las causas raíz reales encontradas en la Fase 1. **No apliques fixes preventivos para problemas que no hayas confirmado.**

## Fix candidatos por causa raíz

### Caso A — Node-RED no inserta (contenedor parado, token caducado, rate limit)

- Reiniciar contenedor: `docker restart <nombre>`.
- Si es rate limit de WAQI: revisar `flows.json` para reducir frecuencia o añadir backoff. Indicar al humano que comparta el flow si no está versionado.
- Si es token: indicar al humano qué variable de entorno renovar (no hardcodear tokens).
- **Añadir** un healthcheck al `docker-compose.yml` que reinicie el contenedor si falla N veces.

### Caso B — Mongo recibe datos pero el campo `fecha` es `string`

- Modificar el nodo Function de Node-RED para hacer `msg.payload.fecha = new Date(msg.payload.fecha)` antes del insert.
- Script de migración en `src/scripts/migrate_fecha_to_date.py` que recorra la colección y convierta strings a `Date`. Idempotente.

### Caso C — Mongo está fresco pero el CSV está congelado (el cron no corre)

Esta es la causa más probable dado el chip "hace 2 días". Acciones:

1. **Verificar que el cron existe**. Si no existe, **crearlo** en `docker-compose.yml` como un servicio dedicado o como cron de host:
   ```cron
   # cada 30 min, refrescar CSV desde Mongo
   */30 * * * * cd /app && python -m src.ml.append_to_dataset_v2 --since-hours 6 >> /var/log/airvlc-refresh.log 2>&1
   ```
2. **Añadir logging estructurado** a `append_to_dataset_v2.py` si no lo tiene: log de inicio, filas leídas de Mongo, filas escritas al CSV, timestamp del CSV resultante. Sin logging no podremos detectar el próximo fallo.
3. **Añadir endpoint de health** en `routes_v2.py`:
   ```python
   @bp.route("/api/v2/health/freshness")
   def freshness():
       extractor = current_app.config.get("FEATURE_EXTRACTOR_V2")
       _, _, meta = extractor.get_features("Francia", offset_hours=0)
       age_min = meta["data_age_minutes"]
       return jsonify({
           "data_timestamp": meta["data_timestamp"],
           "data_age_minutes": age_min,
           "status": "ok" if age_min < 120 else "stale"
       }), 200 if age_min < 120 else 503
   ```
   Esto permite a la app de Flutter mostrar el chip rojo basándose en **datos reales** y no en heurísticas frágiles.

### Caso D — La API filtra documentos sintéticos pero todos los recientes son `is_synthetic: true`

- Cambiar el flujo de Node-RED para que NO marque `is_synthetic` los datos reales de WAQI. Solo el backfill manual debería llevar esa flag.
- **NO** quitar el filtro en la API — la flag existe por una razón (separar reales de imputados).

### Caso E — Flutter parsea UTC sin convertir a local

- En el widget del chip rojo, asegurar que cualquier `DateTime.parse(apiTimestamp)` va seguido de `.toLocal()` antes de formatear.
- Diferenciar dos conceptos en la UI:
  - **"Datos del ..."** → fecha del `data_timestamp` formateado en local.
  - **"hace X tiempo"** → `DateTime.now().difference(parsedUtc.toLocal())`.
- El chip solo debe ponerse rojo si `data_age_minutes > 120`. Por debajo, verde discreto o sin chip.

### Caso F — P3 (predicciones planas)

**No tocar aún.** Una vez P1+P2 estén verdes y haya datos frescos durante al menos 48h, abrir issue separado con estas opciones priorizadas:

1. **Inyectar forecast meteorológico real** (AEMET u OpenWeather) en los últimos 6 timesteps de `get_features_for_horizon` en lugar de copiar valores actuales. Es la causa principal de planitud — el modelo no puede anticipar episodios sin saber que viene calima/inversión térmica.
2. **Sample weights** en el entrenamiento proporcionales a `value²` para penalizar más los errores en picos.
3. **Quantile regression** (predecir p50/p75/p90) para que la UI pueda mostrar incertidumbre en lugar de un valor único engañoso.

---

## Restricciones generales para la Fase 2

- **No** modificar `notebooks/`. Son el record de entrenamiento.
- **No** tocar `_keras_custom.py`, `model_loader.py`, ni los modelos `.keras`. El problema no es el modelo.
- **No** hacer drop/recreate de colecciones de Mongo. Migraciones siempre idempotentes y reversibles.
- **No** commitear `.env` ni tokens.
- Cualquier cambio en `routes_v2.py` debe pasar los tests de `tests/api/test_routes_v2_contract.py` y `test_routes_v2_sprint4.py`.
- Si añades dependencias, actualiza `requirements.txt` y justifica.
- Cada fix debe ir en un commit separado con mensaje descriptivo.

## Checkpoint Fase 2

Al terminar, reporta:

- Lista de archivos modificados/creados.
- Tests que pasaron / fallaron.
- Comando que el humano puede ejecutar para verificar manualmente que el chip rojo desaparece (ej. `curl /api/v2/health/freshness` y esperar `status: ok`).
- Plan de monitorización propuesto para detectar el próximo fallo antes de que llegue al usuario.
