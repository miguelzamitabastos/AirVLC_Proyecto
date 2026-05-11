"""
===================================================================
⏰ Hourly Data Refresh — Sprint 5 B.3
===================================================================
Orquesta el pipeline de refresco horario de datos:

    1. Descarga contaminantes (WAQI en vivo o Geoportal) → Mongo
    2. Descarga meteo actual de OpenWeather → Mongo
    3. Append incremental al CSV v2
    4. Notifica a la API Flask para que recargue el dataset

Modos de uso:
    python src/scripts/hourly_data_refresh.py --once      # una vez
    python src/scripts/hourly_data_refresh.py --daemon     # persistente

Variables de entorno:
    MONGO_URI, OPENWEATHER_API_KEY,
    WAQI_TOKEN (Sprint 6 — contaminantes en vivo via aqicn),
    AIRVLC_AIR_SOURCE (default: waqi | geoportal — fallback histórico Geoportal),
    AIRVLC_MAX_DATA_AGE_H (opcional, append truthful — default 6),
    AIRVLC_INTERNAL_RELOAD_TOKEN (default: airvlc-reload-secret),
    AIRVLC_API_URL (default: http://localhost:5001)
===================================================================
"""

import os
import sys
import time
import argparse
import logging
from datetime import datetime, timedelta

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT_DIR, '.env'))

import requests

# -----------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------
LOG_DIR = os.path.expanduser("~/airvlc_logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "hourly_refresh.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE),
    ],
)
log = logging.getLogger("hourly_refresh")

# -----------------------------------------------------------------------
# Configuración
# -----------------------------------------------------------------------
API_URL = os.getenv("AIRVLC_API_URL", "http://localhost:5001")
RELOAD_TOKEN = os.getenv("AIRVLC_INTERNAL_RELOAD_TOKEN", "airvlc-reload-secret")


def step_1_fetch_air_quality():
    """B.1: Descarga contaminantes → Mongo (WAQI live o Geoportal histórico)."""
    source = os.getenv("AIRVLC_AIR_SOURCE", "waqi").lower().strip()
    log.info(f"📌 Paso 1: Descargando contaminantes (fuente={source})...")
    try:
        if source == "waqi":
            from src.ingestion.waqi_air_quality_client import fetch_waqi_air_quality

            result = fetch_waqi_air_quality(hours=6)
        elif source == "geoportal":
            from src.ingestion.valencia_air_quality_client import fetch_valencia_air_quality

            result = fetch_valencia_air_quality(hours=6)
        else:
            raise ValueError(
                f"AIRVLC_AIR_SOURCE debe ser 'waqi' o 'geoportal', recibido: {source!r}"
            )
        log.info(f"   Resultado aire: {result}")
        return result
    except Exception as e:
        log.error(f"   ❌ Error en paso 1 (aire): {e}")
        return {"error": str(e)}


def step_2_fetch_meteo():
    """Descarga meteo actual OpenWeather → Mongo (reutiliza el client existente)."""
    log.info("📌 Paso 2: Descargando meteo de OpenWeather...")
    try:
        from src.ingestion.openweather_client import ingest_current_weather
        result = ingest_current_weather()
        log.info(f"   ✅ Meteo ingestada: {result}")
        return result if isinstance(result, dict) else {"ok": True}
    except Exception as e:
        log.error(f"   ❌ Error en paso 2 (meteo): {e}")
        return {"ok": False, "error": str(e)}


def step_3_append_dataset():
    """B.2: Append incremental al CSV v2."""
    log.info("📌 Paso 3: Append incremental al dataset v2...")
    try:
        from src.ml.append_to_dataset_v2 import append_to_dataset_v2
        result = append_to_dataset_v2()
        log.info(f"   Resultado append: {result}")
        return result
    except Exception as e:
        log.error(f"   ❌ Error en paso 3 (append): {e}")
        return {"error": str(e)}


def step_4_notify_api_reload():
    """B.4: POST /api/v2/_internal/reload para que Flask recargue el CSV."""
    log.info("📌 Paso 4: Notificando API para recarga...")
    url = f"{API_URL}/api/v2/_internal/reload"
    try:
        resp = requests.post(
            url,
            headers={"X-Internal-Token": RELOAD_TOKEN},
            timeout=20,
        )
        if resp.status_code == 200:
            log.info(f"   ✅ API recargada: {resp.json()}")
        else:
            log.warning(f"   ⚠️ API respondió {resp.status_code}: {resp.text[:200]}")
        return resp.json()
    except requests.ConnectionError:
        log.warning("   ⚠️ API no disponible (Flask no está arrancado). Se recargará al próximo arranque.")
        return {"error": "API no disponible"}
    except requests.Timeout:
        log.warning("   ⚠️ Timeout notificando a la API. (El refresco de datos ha terminado igualmente.)")
        return {"error": "API timeout"}
    except Exception as e:
        log.error(f"   ❌ Error en paso 4 (reload): {e}")
        return {"error": str(e)}


def run_once():
    """Ejecuta los 4 pasos del pipeline una vez."""
    log.info("=" * 60)
    log.info(f"🔄 Inicio del pipeline de refresco — {datetime.now().isoformat()}")
    log.info("=" * 60)

    t0 = time.time()

    r1 = step_1_fetch_air_quality()
    r2 = step_2_fetch_meteo()
    r3 = step_3_append_dataset()
    r4 = step_4_notify_api_reload()

    elapsed = time.time() - t0
    log.info(f"✅ Pipeline completado en {elapsed:.1f}s")
    log.info(f"   Aire: {r1}")
    log.info(f"   Meteo: {r2}")
    log.info(f"   Append: {r3}")
    log.info(f"   Reload: {r4}")

    return {"air": r1, "meteo": r2, "append": r3, "reload": r4, "elapsed_s": elapsed}


def run_daemon(interval_seconds: int = 3600):
    """Ejecuta el pipeline de forma persistente, esperando al minuto 2 de cada hora."""
    log.info(f"🔄 Modo daemon activado (cada {interval_seconds}s)")
    log.info(f"   Logs en: {LOG_FILE}")
    log.info("   Ctrl+C para detener\n")

    # Ejecutar una vez inmediatamente
    run_once()

    while True:
        try:
            # Calcular próximo top de hora + 2 min (los datos suelen publicarse ~HH:00)
            now = datetime.now()
            next_top = (now + timedelta(hours=1)).replace(minute=2, second=0, microsecond=0)
            wait = (next_top - now).total_seconds()

            if wait <= 0:
                wait = interval_seconds

            log.info(f"   ⏳ Próxima ejecución: {next_top.strftime('%H:%M:%S')} (en {wait:.0f}s)")
            time.sleep(wait)

            run_once()

        except KeyboardInterrupt:
            log.info("\n🛑 Daemon detenido por el usuario")
            break
        except Exception as e:
            log.error(f"   ❌ Error inesperado: {e}")
            log.info("   Reintentando en 60s...")
            time.sleep(60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AirVLC — Pipeline de refresco horario de datos (Sprint 5)"
    )
    parser.add_argument("--once", action="store_true", help="Ejecutar una sola vez")
    parser.add_argument("--daemon", action="store_true", help="Ejecutar en modo daemon")
    parser.add_argument(
        "--interval", type=int, default=3600,
        help="Intervalo en segundos para el daemon (default: 3600)"
    )
    args = parser.parse_args()

    if not args.once and not args.daemon:
        parser.print_help()
        print("\n⚠️  Especifica --once o --daemon")
        sys.exit(1)

    if args.once:
        run_once()
    elif args.daemon:
        run_daemon(args.interval)
