"""
===================================================================
💓 API Heartbeat — Monitorización de Estado de la API
===================================================================
Envía periódicamente el estado de la API Flask a Elasticsearch
para poder monitorizar su salud en un dashboard de Kibana.

Uso:
    # Ejecutar como proceso separado (cada 60s)
    python src/scripts/api_heartbeat.py

    # O importar y ejecutar en un thread
    from src.scripts.api_heartbeat import start_heartbeat_thread
===================================================================
"""

import os
import sys
import time
import json
import requests
import threading
from datetime import datetime

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT_DIR)

ES_HOST = "http://localhost:9200"
API_HOST = "http://localhost:5001"
HEARTBEAT_INDEX = "airvlc-api-heartbeat"


def create_heartbeat_index():
    """Crea el índice de heartbeat en ES si no existe."""
    r = requests.head(f"{ES_HOST}/{HEARTBEAT_INDEX}")
    if r.status_code == 200:
        return

    mapping = {
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "properties": {
                "@timestamp": {"type": "date"},
                "status": {"type": "keyword"},
                "response_time_ms": {"type": "float"},
                "models_loaded": {"type": "boolean"},
                "best_model": {"type": "keyword"},
                "available_models": {"type": "keyword"},
                "model_count": {"type": "integer"},
                "es_indexer_connected": {"type": "boolean"},
                "http_status_code": {"type": "integer"},
                "error_message": {"type": "text"},
                "api_version": {"type": "keyword"},
                "uptime_check": {"type": "keyword"},
            }
        }
    }

    r = requests.put(
        f"{ES_HOST}/{HEARTBEAT_INDEX}",
        headers={"Content-Type": "application/json"},
        data=json.dumps(mapping)
    )
    if r.status_code in (200, 201):
        print(f"  ✅ Índice '{HEARTBEAT_INDEX}' creado")


def check_api_health():
    """Consulta el health endpoint de la API y construye el documento."""
    doc = {
        "@timestamp": datetime.utcnow().isoformat(),
        "uptime_check": "heartbeat",
    }

    try:
        start = time.time()
        r = requests.get(f"{API_HOST}/api/health", timeout=10)
        elapsed = (time.time() - start) * 1000  # ms

        doc["response_time_ms"] = round(elapsed, 2)
        doc["http_status_code"] = r.status_code

        if r.status_code == 200:
            data = r.json()
            doc["status"] = "up"
            doc["models_loaded"] = data.get("models", {}).get("loaded", False)
            doc["best_model"] = data.get("models", {}).get("best_model")
            doc["available_models"] = data.get("models", {}).get("available_models", [])
            doc["model_count"] = len(doc["available_models"])
            doc["api_version"] = data.get("version", "unknown")
        else:
            doc["status"] = "degraded"
            doc["models_loaded"] = False

    except requests.exceptions.ConnectionError:
        doc["status"] = "down"
        doc["response_time_ms"] = 0
        doc["http_status_code"] = 0
        doc["error_message"] = "Connection refused — API not running"
        doc["models_loaded"] = False
    except requests.exceptions.Timeout:
        doc["status"] = "timeout"
        doc["response_time_ms"] = 10000
        doc["http_status_code"] = 0
        doc["error_message"] = "API timeout (>10s)"
        doc["models_loaded"] = False
    except Exception as e:
        doc["status"] = "error"
        doc["error_message"] = str(e)
        doc["models_loaded"] = False

    return doc


def send_heartbeat():
    """Envía un heartbeat a ES."""
    doc = check_api_health()

    try:
        from elasticsearch import Elasticsearch
        es = Elasticsearch(ES_HOST)
        es.index(index=HEARTBEAT_INDEX, document=doc)
        return doc["status"]
    except Exception as e:
        print(f"  ⚠️ Error indexando heartbeat: {e}")
        return "es_error"


def run_heartbeat_loop(interval=60):
    """Loop principal del heartbeat."""
    print(f"\n💓 Heartbeat iniciado (cada {interval}s)")
    print(f"   API: {API_HOST}")
    print(f"   ES:  {ES_HOST}/{HEARTBEAT_INDEX}")
    print(f"   Ctrl+C para detener\n")

    while True:
        try:
            status = send_heartbeat()
            now = datetime.now().strftime("%H:%M:%S")
            emoji = "🟢" if status == "up" else "🔴" if status == "down" else "🟡"
            print(f"  {emoji} [{now}] API status: {status}")
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\n🛑 Heartbeat detenido")
            break


def start_heartbeat_thread(interval=60):
    """Inicia el heartbeat en un thread separado (para integrar con la API)."""
    t = threading.Thread(target=run_heartbeat_loop, args=(interval,), daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("💓 AirVLC — API Heartbeat Monitor")
    print("=" * 60 + "\n")

    # Verificar ES
    try:
        r = requests.get(ES_HOST, timeout=5)
        print(f"✅ Elasticsearch activo")
    except Exception:
        print("❌ Elasticsearch no disponible")
        sys.exit(1)

    create_heartbeat_index()

    # Primer check inmediato
    status = send_heartbeat()
    emoji = "🟢" if status == "up" else "🔴" if status == "down" else "🟡"
    print(f"\n  {emoji} Estado actual de la API: {status}")

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=60, help="Intervalo en segundos")
    parser.add_argument("--once", action="store_true", help="Solo un check")
    args = parser.parse_args()

    if not args.once:
        run_heartbeat_loop(args.interval)
