"""
AirVLC — Verificación de datos en Elasticsearch
=================================================
Semana 1, Miércoles 30: Verifica que Logstash haya indexado correctamente
los datos de calidad del aire en Elasticsearch.

Uso:
    python src/scripts/verify_elasticsearch.py
"""

import os
import sys
import json
from pathlib import Path

from elasticsearch import Elasticsearch
from dotenv import load_dotenv

# Cargar .env
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")
INDEX_NAME = "airvlc-calidad-aire"


def print_header(title):
    """Imprime un header formateado."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def main():
    print("╔══════════════════════════════════════════════════════════╗")
    print("║   AirVLC — Verificación Elasticsearch                   ║")
    print("╚══════════════════════════════════════════════════════════╝")

    # Conectar a Elasticsearch
    print(f"\n  🔌 Conectando a Elasticsearch ({ES_HOST})...")
    try:
        es = Elasticsearch(ES_HOST)
        info = es.info()
        print(f"  ✅ Conectado — Versión: {info['version']['number']}")
    except Exception as e:
        print(f"  ❌ Error de conexión: {e}")
        sys.exit(1)

    # ── 1. Verificar si el índice existe ─────────────────────────────────────
    print_header("1. Verificación del índice")

    if es.indices.exists(index=INDEX_NAME):
        print(f"  ✅ Índice '{INDEX_NAME}' existe")
    else:
        print(f"  ❌ Índice '{INDEX_NAME}' NO encontrado")
        print("     → Verifica que Logstash haya terminado de procesar el CSV")
        print("     → Revisa los logs: docker compose logs logstash")
        sys.exit(1)

    # ── 2. Contar documentos ─────────────────────────────────────────────────
    print_header("2. Conteo de documentos")

    count = es.count(index=INDEX_NAME)["count"]
    print(f"  📊 Total de documentos indexados: {count:,}")

    if count == 0:
        print("  ⚠️  El índice está vacío. Logstash puede estar todavía procesando.")
        print("     → Espera unos minutos y vuelve a ejecutar este script.")
        sys.exit(0)

    # ── 3. Distribución por estación ─────────────────────────────────────────
    print_header("3. Distribución por estación")

    agg_query = {
        "size": 0,
        "aggs": {
            "por_estacion": {
                "terms": {
                    "field": "estacion.keyword",
                    "size": 20,
                    "order": {"_count": "desc"}
                }
            }
        }
    }

    result = es.search(index=INDEX_NAME, body=agg_query)
    buckets = result["aggregations"]["por_estacion"]["buckets"]

    for bucket in buckets:
        estacion = bucket["key"]
        doc_count = bucket["doc_count"]
        pct = (doc_count / count) * 100
        bar = "█" * int(pct / 2)
        print(f"  📍 {estacion:35s} → {doc_count:>8,} ({pct:5.1f}%) {bar}")

    # ── 4. Rango temporal ────────────────────────────────────────────────────
    print_header("4. Rango temporal")

    range_query = {
        "size": 0,
        "aggs": {
            "fecha_min": {"min": {"field": "@timestamp"}},
            "fecha_max": {"max": {"field": "@timestamp"}}
        }
    }

    result = es.search(index=INDEX_NAME, body=range_query)
    fecha_min = result["aggregations"]["fecha_min"]["value_as_string"]
    fecha_max = result["aggregations"]["fecha_max"]["value_as_string"]
    print(f"  📅 Desde: {fecha_min}")
    print(f"  📅 Hasta: {fecha_max}")

    # ── 5. Muestra de documentos ─────────────────────────────────────────────
    print_header("5. Muestra de documentos (últimos 3)")

    sample_query = {
        "size": 3,
        "sort": [{"@timestamp": {"order": "desc"}}],
        "_source": ["@timestamp", "estacion", "pm25", "pm10", "no2", "o3", "temperatura"]
    }

    result = es.search(index=INDEX_NAME, body=sample_query)

    for hit in result["hits"]["hits"]:
        src = hit["_source"]
        print(f"\n  📄 Documento:")
        for key, value in src.items():
            print(f"     {key:25s}: {value}")

    # ── 6. Estadísticas de PM2.5 ─────────────────────────────────────────────
    print_header("6. Estadísticas PM2.5")

    stats_query = {
        "size": 0,
        "aggs": {
            "pm25_stats": {
                "extended_stats": {"field": "pm25"}
            }
        }
    }

    result = es.search(index=INDEX_NAME, body=stats_query)
    stats = result["aggregations"]["pm25_stats"]

    if stats["count"] > 0:
        print(f"  📊 Registros con PM2.5: {stats['count']:,}")
        print(f"  📊 Media:               {stats['avg']:.2f} µg/m³")
        print(f"  📊 Mínimo:              {stats['min']:.2f} µg/m³")
        print(f"  📊 Máximo:              {stats['max']:.2f} µg/m³")
        print(f"  📊 Desviación estándar: {stats['std_deviation']:.2f} µg/m³")

    # ── 7. Verificar mapping ─────────────────────────────────────────────────
    print_header("7. Mapping del índice")

    mapping = es.indices.get_mapping(index=INDEX_NAME)
    properties = mapping[INDEX_NAME]["mappings"]["properties"]

    has_geo = "location" in properties and properties["location"].get("type") == "geo_point"
    print(f"  🗺️  Campo geo_point (location): {'✅ Configurado' if has_geo else '❌ No encontrado'}")
    print(f"  📋 Total de campos mapeados: {len(properties)}")

    # Resumen
    print_header("RESUMEN")
    print(f"  ✅ Índice:       {INDEX_NAME}")
    print(f"  ✅ Documentos:   {count:,}")
    print(f"  ✅ Estaciones:   {len(buckets)}")
    print(f"  ✅ Rango:        {fecha_min} → {fecha_max}")
    print(f"  ✅ Geo-point:    {'Sí' if has_geo else 'No'}")
    print(f"\n  🎯 Los datos están listos para Kibana en http://localhost:5601")
    print()


if __name__ == "__main__":
    main()
