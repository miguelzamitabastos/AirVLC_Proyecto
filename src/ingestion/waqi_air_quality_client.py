"""
===================================================================
WAQI Air Quality Client — Sprint 6
===================================================================
Descarga mediciones recientes (PM2.5, NO2, O3) desde World Air Quality Index
(api.waqi.info), convierte sub-índices EPA a µg/m³ y hace upsert en MongoDB
`airvlc_db.aire_realtime`.

Por estación canónica del modelo v2 se usa:
1) Si existe `WAQI_STATION_UID_OVERRIDE[estacion]` → feed /@uid
2) Si no → feed/geo:lat;lon (vecino más cercano según WAQI)

Variables de entorno:
    WAQI_TOKEN            (obligatoria) — https://aqicn.org/data-platform/token/
    MONGO_URI             (obligatoria)

Uso:
    python src/ingestion/waqi_air_quality_client.py --hours 6
===================================================================
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)
load_dotenv(os.path.join(ROOT_DIR, ".env"))

from src.api.es_indexer import STATION_COORDS
from src.ingestion.aqi_conversion import (
    no2_subindex_to_ugm3,
    o3_subindex_to_ugm3,
    pm25_subindex_to_ugm3,
)
from src.ingestion.waqi_station_map import WAQI_STATION_UID_OVERRIDE

MONGO_URI = os.getenv("MONGO_URI")

# Quality gates (valores plausibles) — evita outliers obvios por parseo/unidades.
# Ajustables vía env si fuese necesario.
PM25_MAX = float(os.getenv("AIRVLC_PM25_MAX", "500"))
NO2_MAX = float(os.getenv("AIRVLC_NO2_MAX", "1000"))
O3_MAX = float(os.getenv("AIRVLC_O3_MAX", "1000"))

# Estaciones canónicas del CSV v2 (mismo orden que append_to_dataset_v2)
CANONICAL_STATIONS = [
    "Francia",
    "Molí del Sol",
    "Pista de Silla",
    "Puerto Moll Trans. Ponent",
    "Puerto Valencia",
    "Puerto llit antic Túria",
    "Universidad Politécnica",
]

WAQI_BASE = "https://api.waqi.info"


def _get_token() -> str:
    token = (os.getenv("WAQI_TOKEN") or "").strip()
    if not token:
        raise RuntimeError(
            "WAQI_TOKEN no configurada. Obtén un token en https://aqicn.org/data-platform/token/ "
            "y añádela al archivo .env"
        )
    return token


def _parse_time_iso(data: dict) -> datetime | None:
    t = (data or {}).get("time") or {}
    iso = t.get("iso") or t.get("s")
    if not iso:
        return None
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _iaqi_v(iaqi: dict, key: str) -> float | None:
    if not iaqi or key not in iaqi:
        return None
    node = iaqi[key]
    if isinstance(node, dict) and "v" in node:
        try:
            return float(node["v"])
        except (TypeError, ValueError):
            return None
    return None


def _convert_pollutants(iaqi: dict) -> tuple[float | None, float | None, float | None]:
    """Convierte sub-índices iaqi a µg/m³ (solo pm25 explícito; sin proxy pm10)."""
    pm_i = _iaqi_v(iaqi, "pm25")
    no2_i = _iaqi_v(iaqi, "no2")
    o3_i = _iaqi_v(iaqi, "o3")

    pm25 = pm25_subindex_to_ugm3(pm_i) if pm_i is not None else None
    no2 = no2_subindex_to_ugm3(no2_i) if no2_i is not None else None
    o3 = o3_subindex_to_ugm3(o3_i) if o3_i is not None else None
    return pm25, no2, o3


def _plausible(pm25: float, no2: float, o3: float) -> bool:
    """Filtro rápido para valores imposibles o claramente corruptos."""
    if pm25 < 0 or no2 < 0 or o3 < 0:
        return False
    if pm25 > PM25_MAX or no2 > NO2_MAX or o3 > O3_MAX:
        return False
    return True


def _feed_url_for_station(station: str) -> str:
    token = _get_token()
    uid = WAQI_STATION_UID_OVERRIDE.get(station)
    if uid is not None:
        return f"{WAQI_BASE}/feed/@{uid}/?token={token}"
    coords = STATION_COORDS.get(station)
    if not coords:
        raise RuntimeError(f"No hay coordenadas STATION_COORDS para '{station}'")
    lat, lon = coords["lat"], coords["lon"]
    return f"{WAQI_BASE}/feed/geo:{lat};{lon}/?token={token}"


def fetch_station_payload(station: str) -> dict | None:
    """GET una estación; devuelve el JSON `data` o None."""
    url = _feed_url_for_station(station)
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"   ⚠️  WAQI error [{station}]: {e}")
        return None

    body = r.json()
    if body.get("status") != "ok":
        print(f"   ⚠️  WAQI status!=ok [{station}]: {body}")
        return None
    return body.get("data")


def build_document(station: str, data: dict, hours: int) -> dict | None:
    """Construye documento Mongo o None si fuera de ventana / incompleto."""
    fecha_dt = _parse_time_iso(data)
    if fecha_dt is None:
        print(f"   ⚠️  Sin timestamp WAQI [{station}]")
        return None

    if fecha_dt.tzinfo is None:
        fecha_dt = fecha_dt.replace(tzinfo=timezone.utc)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    if fecha_dt < cutoff:
        print(f"   ⚠️  Dato demasiado antiguo [{station}] {fecha_dt.isoformat()} (>{hours}h)")
        return None

    iaqi = data.get("iaqi") or {}
    # Trazabilidad: guardar valores crudos reportados por WAQI.
    raw_pm25 = _iaqi_v(iaqi, "pm25")
    raw_no2 = _iaqi_v(iaqi, "no2")
    raw_o3 = _iaqi_v(iaqi, "o3")
    pm25, no2, o3 = _convert_pollutants(iaqi)
    if pm25 is None or no2 is None or o3 is None:
        print(f"   ⚠️  Faltan contaminantes tras conversión [{station}] pm25={pm25} no2={no2} o3={o3}")
        return None
    if not _plausible(pm25, no2, o3):
        print(f"   ⚠️  Valores fuera de rango plausible [{station}] pm25={pm25} no2={no2} o3={o3}")
        return None

    fecha_iso = fecha_dt.isoformat()
    city = (data.get("city") or {}).get("name") or ""

    return {
        "estacion": station,
        "fecha_iso": fecha_iso,
        "fecha": fecha_dt,
        "pm25": pm25,
        "no2": no2,
        "o3": o3,
        "ingested_at": datetime.utcnow().isoformat(),
        "source": "waqi",
        "waqi_city_name": city,
        "waqi_idx": data.get("idx"),
        # --- Traceability: conservar payload crudo relevante ---
        "waqi_time_raw": (data.get("time") or {}),
        "waqi_iaqi_raw": iaqi,
        "waqi_raw_values": {"pm25": raw_pm25, "no2": raw_no2, "o3": raw_o3},
        # Declaramos explícitamente la transformación aplicada.
        "conversion": {
            "method": "epa_aqi_subindex_to_ugm3",
            "note": "Se asume que iaqi.*.v son subíndices AQI; si son concentraciones, ajustar conversión.",
        },
    }


def upsert_to_mongo(documents: list) -> dict:
    """Upsert idempotente en MongoDB airvlc_db.aire_realtime."""
    if not MONGO_URI:
        print("❌ MONGO_URI no configurado en .env")
        return {"inserted": 0, "modified": 0, "errors": len(documents)}

    client = MongoClient(MONGO_URI)
    db = client["airvlc_db"]
    coll = db["aire_realtime"]

    coll.create_index(
        [("estacion", 1), ("fecha_iso", 1)],
        unique=True,
        name="idx_estacion_fecha_unique",
        background=True,
    )

    ops = []
    for doc in documents:
        ops.append(
            UpdateOne(
                {"estacion": doc["estacion"], "fecha_iso": doc["fecha_iso"]},
                {"$set": doc},
                upsert=True,
            )
        )

    if not ops:
        return {"inserted": 0, "modified": 0, "errors": 0}

    result = coll.bulk_write(ops, ordered=False)
    client.close()

    return {
        "inserted": result.upserted_count,
        "modified": result.modified_count,
        "errors": 0,
    }


def fetch_waqi_air_quality(hours: int = 6) -> dict:
    """Pipeline: WAQI por estación → parse → MongoDB."""
    print(f"🔍 WAQI — ventana últimas {hours}h, estaciones={len(CANONICAL_STATIONS)}")

    raw_count = 0
    parsed_docs: list = []

    for station in CANONICAL_STATIONS:
        data = fetch_station_payload(station)
        if not data:
            continue
        raw_count += 1
        doc = build_document(station, data, hours=hours)
        if doc:
            parsed_docs.append(doc)

    print(f"   📊 Respuestas ok: {raw_count}, documentos válidos: {len(parsed_docs)}")

    if not parsed_docs:
        print("⚠️  Sin datos nuevos ingestables de WAQI.")
        return {"raw": raw_count, "parsed": 0, "inserted": 0, "modified": 0}

    stats = upsert_to_mongo(parsed_docs)
    print(f"   ✅ Mongo upsert: {stats['inserted']} nuevos, {stats['modified']} actualizados")

    return {
        "raw": raw_count,
        "parsed": len(parsed_docs),
        **stats,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WAQI → Mongo (aire_realtime)")
    parser.add_argument("--hours", type=int, default=48, help="Ventana máxima de antigüedad del dato")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("🌍 AirVLC — WAQI Air Quality Client (Sprint 6)")
    print("=" * 60 + "\n")

    result = fetch_waqi_air_quality(hours=args.hours)
    print(f"\n🎯 Resultado: {result}")
