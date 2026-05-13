"""
===================================================================
🌤️ Sync Meteo to ES — Pipeline MongoDB Atlas → Elasticsearch
===================================================================
Sincroniza los datos meteorológicos en tiempo real de la colección
'meteo_realtime' de MongoDB Atlas al índice 'airvlc-meteo-realtime'
de Elasticsearch para visualización en Kibana.

Modos de ejecución:
    # Sincronización única (full)
    python src/scripts/sync_meteo_to_es.py

    # Modo daemon (cada 5 minutos)
    python src/scripts/sync_meteo_to_es.py --daemon

Requisitos:
    - MongoDB Atlas con colección meteo_realtime
    - Elasticsearch corriendo en localhost:9200
===================================================================
"""

import os
import sys
import json
import time
import argparse
import requests
from datetime import datetime

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT_DIR, '.env'))

ES_HOST = "http://localhost:9200"
METEO_INDEX = "airvlc-meteo-realtime"
MONGO_DB = "airvlc_db"
MONGO_COLLECTION = "meteo_realtime"

# Coordenadas de Valencia para geo_point
VALENCIA_COORDS = {"lat": 39.4699, "lon": -0.3763}


def create_meteo_index():
    """Crea el índice de meteo en ES si no existe."""
    r = requests.head(f"{ES_HOST}/{METEO_INDEX}")
    if r.status_code == 200:
        print(f"  ✅ Índice '{METEO_INDEX}' ya existe")
        return

    mapping = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0
        },
        "mappings": {
            "properties": {
                "@timestamp": {"type": "date"},
                "temp": {"type": "float"},
                "humidity": {"type": "integer"},
                "pressure": {"type": "integer"},
                "wind_speed": {"type": "float"},
                "clouds": {"type": "integer"},
                "description": {"type": "keyword"},
                "icon": {"type": "keyword"},
                "city": {"type": "keyword"},
                "location": {"type": "geo_point"},
                "source": {"type": "keyword"},
            }
        }
    }

    r = requests.put(
        f"{ES_HOST}/{METEO_INDEX}",
        headers={"Content-Type": "application/json"},
        data=json.dumps(mapping)
    )
    if r.status_code in (200, 201):
        print(f"  ✅ Índice '{METEO_INDEX}' creado")
    else:
        print(f"  ❌ Error creando índice: {r.text[:200]}")
        sys.exit(1)


def get_last_synced_timestamp():
    """Obtiene el timestamp del último documento sincronizado en ES."""
    r = requests.post(
        f"{ES_HOST}/{METEO_INDEX}/_search",
        headers={"Content-Type": "application/json"},
        json={"size": 1, "sort": [{"@timestamp": "desc"}], "_source": ["@timestamp"]}
    )
    if r.status_code == 200:
        hits = r.json().get("hits", {}).get("hits", [])
        if hits:
            return hits[0]["_source"]["@timestamp"]
    return None


def sync_from_mongo():
    """Sincroniza datos de MongoDB Atlas → Elasticsearch."""
    from pymongo import MongoClient

    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        print("❌ MONGO_URI no configurado en .env")
        sys.exit(1)

    client = MongoClient(mongo_uri)
    db = client[MONGO_DB]
    coll = db[MONGO_COLLECTION]

    # Obtener último timestamp sincronizado
    last_ts = get_last_synced_timestamp()

    # Consulta MongoDB: solo documentos nuevos
    query = {}
    if last_ts:
        query = {"timestamp": {"$gt": last_ts}}
        print(f"  📅 Último sync: {last_ts}")
    else:
        print(f"  📅 Primera sincronización (full)")

    # Fetch documentos
    docs = list(coll.find(query).sort("timestamp", 1))
    print(f"  📥 Documentos nuevos desde MongoDB: {len(docs)}")

    if not docs:
        print("  ✅ Todo sincronizado, no hay datos nuevos")
        return 0

    # Construir bulk actions
    from elasticsearch import Elasticsearch
    from elasticsearch.helpers import bulk

    es = Elasticsearch(ES_HOST)
    actions = []

    for doc in docs:
        mongo_id = str(doc.pop("_id", ""))
        ts = doc.get("timestamp", datetime.utcnow().isoformat())

        es_doc = {
            "@timestamp": ts,
            "temp": doc.get("temp"),
            "humidity": doc.get("humidity"),
            "pressure": doc.get("pressure"),
            "wind_speed": doc.get("wind_speed"),
            "clouds": doc.get("clouds"),
            "description": doc.get("description"),
            "icon": doc.get("icon"),
            "city": doc.get("city", "Valencia"),
            "location": VALENCIA_COORDS,
            "source": "openweather_nodered",
        }

        actions.append({
            "_index": METEO_INDEX,
            "_id": mongo_id,  # Usar _id de Mongo para evitar duplicados
            "_source": es_doc,
        })

    success, errors = bulk(es, actions, raise_on_error=False)
    print(f"  ✅ Indexados: {success}")
    if errors:
        err_count = errors if isinstance(errors, int) else len(errors)
        print(f"  ⚠️  Errores: {err_count}")

    client.close()
    return success


def run_daemon(interval_seconds=300):
    """Ejecuta la sincronización en modo daemon."""
    print(f"\n🔄 Modo daemon activado (cada {interval_seconds}s)")
    print(f"   Ctrl+C para detener\n")

    while True:
        try:
            print(f"\n--- Sync: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
            sync_from_mongo()
            print(f"   Próximo sync en {interval_seconds}s...")
            time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\n\n🛑 Daemon detenido")
            break
        except Exception as e:
            print(f"   ⚠️ Error: {e}")
            time.sleep(30)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync meteo data from MongoDB to ES")
    parser.add_argument("--daemon", action="store_true", help="Run in daemon mode (every 5 min)")
    parser.add_argument("--interval", type=int, default=300, help="Daemon interval in seconds")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("🌤️ AirVLC — Sync Meteo MongoDB → Elasticsearch")
    print("=" * 60 + "\n")

    # Verificar ES
    try:
        r = requests.get(ES_HOST, timeout=5)
        print(f"✅ Elasticsearch {r.json()['version']['number']} activo")
    except Exception:
        print("❌ Elasticsearch no disponible")
        sys.exit(1)

    create_meteo_index()
    synced = sync_from_mongo()

    if args.daemon:
        run_daemon(args.interval)
    else:
        print(f"\n🎯 Sincronización completada: {synced} documentos")
        print(f"   Para modo continuo: python {__file__} --daemon")
