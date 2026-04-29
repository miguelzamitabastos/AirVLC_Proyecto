"""
Script de verificación para revisar el estado actual de la colección
meteo_historical en MongoDB Atlas.
Muestra qué datos hay, de qué estaciones, y qué rangos de fechas.
"""
import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

try:
    client = MongoClient(MONGO_URI)
    client.admin.command('ping')
    db = client["airvlc_db"]
    print("✅ Conectado a MongoDB Atlas\n")
except Exception as e:
    print(f"❌ Error conectando: {e}")
    exit(1)

print("=" * 60)
print("  VERIFICACIÓN: Colecciones en airvlc_db")
print("=" * 60)

collections = db.list_collection_names()
for coll_name in sorted(collections):
    count = db[coll_name].count_documents({})
    print(f"  📁 {coll_name}: {count} documentos")

print()

# ── Análisis detallado de meteo_historical ──────────────────
collection = db["meteo_historical"]
total = collection.count_documents({})
print("=" * 60)
print(f"  DETALLE: meteo_historical ({total} documentos)")
print("=" * 60)

if total == 0:
    print("  (vacía)")
else:
    # Agrupar por estación
    pipeline_stations = [
        {"$group": {
            "_id": {
                "indicativo": "$indicativo",
                "nombre": "$nombre",
                "provincia": "$provincia"
            },
            "count": {"$sum": 1},
            "fecha_min": {"$min": "$fecha"},
            "fecha_max": {"$max": "$fecha"}
        }},
        {"$sort": {"count": -1}}
    ]
    
    stations = list(collection.aggregate(pipeline_stations))
    
    for st in stations:
        info = st["_id"]
        print(f"\n  🏢 Estación: {info.get('nombre', '?')} ({info.get('indicativo', '?')})")
        print(f"     Provincia: {info.get('provincia', '?')}")
        print(f"     Documentos: {st['count']}")
        print(f"     Rango fechas: {st['fecha_min']} → {st['fecha_max']}")

    # Agrupar por tipo de datos (metadata.type)
    pipeline_types = [
        {"$group": {
            "_id": "$metadata.type",
            "count": {"$sum": 1}
        }}
    ]
    types = list(collection.aggregate(pipeline_types))
    print(f"\n  📊 Por tipo de datos:")
    for t in types:
        tipo = t["_id"] if t["_id"] else "sin metadata"
        print(f"     - {tipo}: {t['count']} docs")

    # Mostrar un documento de ejemplo
    sample = collection.find_one()
    if sample:
        print(f"\n  📄 Ejemplo de documento (campos):")
        for key in sorted(sample.keys()):
            if key == "_id":
                continue
            val = sample[key]
            if isinstance(val, dict):
                print(f"     {key}: {{...}}")
            else:
                print(f"     {key}: {val}")

# ── Análisis de meteo_realtime ──────────────────
print()
rt_collection = db["meteo_realtime"]
rt_total = rt_collection.count_documents({})
print("=" * 60)
print(f"  DETALLE: meteo_realtime ({rt_total} documentos)")
print("=" * 60)

if rt_total > 0:
    sample_rt = rt_collection.find_one()
    if sample_rt:
        print(f"  📄 Último documento:")
        print(f"     city: {sample_rt.get('city', '?')}")
        print(f"     ingested_at: {sample_rt.get('ingested_at', '?')}")

print("\n✅ Verificación completada")
