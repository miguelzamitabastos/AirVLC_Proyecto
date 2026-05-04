"""
===================================================================
📊 Create Predictions Index — Elasticsearch Index Template
===================================================================
Crea el índice 'airvlc-predictions' en Elasticsearch para almacenar
los resultados de predicciones del modelo LSTM y clasificaciones
de riesgo. Esto alimenta los dashboards de Kibana.

Ejecución:
    python src/scripts/create_predictions_index.py

Requisitos:
    - Elasticsearch corriendo en localhost:9200
===================================================================
"""

import requests
import json
import sys

ES_HOST = "http://localhost:9200"
INDEX_NAME = "airvlc-predictions"


def check_elasticsearch():
    """Verifica que Elasticsearch está activo."""
    try:
        r = requests.get(ES_HOST, timeout=5)
        info = r.json()
        print(f"✅ Elasticsearch {info['version']['number']} activo")
        return True
    except Exception as e:
        print(f"❌ Elasticsearch no disponible: {e}")
        return False


def delete_index_if_exists():
    """Elimina el índice si ya existe (para recrear limpio)."""
    r = requests.head(f"{ES_HOST}/{INDEX_NAME}")
    if r.status_code == 200:
        print(f"  ⚠️  Índice '{INDEX_NAME}' ya existe. Eliminando...")
        requests.delete(f"{ES_HOST}/{INDEX_NAME}")
        print(f"  🗑️  Eliminado")


def create_index():
    """Crea el índice con mapping optimizado para dashboards."""

    mapping = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "index.mapping.total_fields.limit": 200
        },
        "mappings": {
            "properties": {
                # --- Timestamp ---
                "@timestamp": {"type": "date"},

                # --- Predicción ---
                "pm25_predicted": {"type": "float"},
                "pm25_actual": {"type": "float"},
                "residual": {"type": "float"},
                "absolute_error": {"type": "float"},

                # --- Modelo ---
                "model_used": {"type": "keyword"},

                # --- Riesgo ---
                "risk_level": {"type": "keyword"},
                "risk_level_actual": {"type": "keyword"},
                "risk_color": {"type": "keyword"},
                "risk_emoji": {"type": "keyword"},
                "alert_text": {"type": "text"},

                # --- Estación ---
                "station": {"type": "keyword"},
                "location": {"type": "geo_point"},

                # --- Contexto meteorológico ---
                "no2": {"type": "float"},
                "o3": {"type": "float"},
                "temperatura": {"type": "float"},
                "velocidad_viento": {"type": "float"},
                "precipitacion": {"type": "float"},
                "humedad_relativa": {"type": "float"},

                # --- Temporal ---
                "hora_del_dia": {"type": "integer"},
                "dia_de_la_semana": {"type": "integer"},

                # --- Metadatos ---
                "source": {"type": "keyword"},  # "api" | "backtest" | "seed"
                "prediction_type": {"type": "keyword"},  # "realtime" | "historical"
            }
        }
    }

    r = requests.put(
        f"{ES_HOST}/{INDEX_NAME}",
        headers={"Content-Type": "application/json"},
        data=json.dumps(mapping)
    )

    if r.status_code in (200, 201):
        print(f"✅ Índice '{INDEX_NAME}' creado correctamente")
        print(f"   Mapping: {len(mapping['mappings']['properties'])} campos")
    else:
        print(f"❌ Error creando índice: {r.status_code}")
        print(f"   {r.text}")
        sys.exit(1)


def verify_index():
    """Verifica que el índice se creó correctamente."""
    r = requests.get(f"{ES_HOST}/{INDEX_NAME}/_mapping")
    if r.status_code == 200:
        fields = list(r.json()[INDEX_NAME]['mappings']['properties'].keys())
        print(f"  📋 Campos del índice: {len(fields)}")
        print(f"     {', '.join(sorted(fields)[:10])}...")
        return True
    return False


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("📊 AirVLC — Crear Índice de Predicciones en ES")
    print("=" * 60 + "\n")

    if not check_elasticsearch():
        sys.exit(1)

    delete_index_if_exists()
    create_index()
    verify_index()

    print(f"\n🎯 Índice listo: {ES_HOST}/{INDEX_NAME}")
    print("   Siguiente paso: ejecutar seed_predictions_to_es.py\n")
