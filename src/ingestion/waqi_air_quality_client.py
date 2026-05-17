"""
===================================================================
WAQI Air Quality Client — fallback Puerto Valencia (Sprint 6+)
===================================================================
Descarga mediciones recientes (PM2.5, NO2, O3) desde World Air Quality Index
(api.waqi.info), convierte sub-índices EPA a µg/m³ y hace upsert en MongoDB
``airvlc_db.aire_realtime``.

**Política de uso:** solo estaciones en ``WAQI_FALLBACK_STATIONS`` (hoy:
``Puerto Valencia``). Las otras 6 canónicas del modelo se alimentan **solo**
con GVA RVVCCA (``gva_rvvcca_csv_client``).

Formato de respuesta WAQI (ejemplo):
    {"status": "ok", "data": {"iaqi": {"pm25": {"v": 30}, ...},
     "time": {"iso": "2026-05-17T17:00:00+08:00", "s": "...", "tz": "..."}, ...}}

Por estación:
    1) Si existe ``WAQI_STATION_UID_OVERRIDE[estacion]`` → ``feed/@{uid}``
    2) Si no → ``feed/geo:{lat};{lon}`` (coordenadas de ``STATION_COORDS``)

No usar ``feed/here/`` (geolocalización por IP; no es Valencia).

Variables de entorno:
    WAQI_TOKEN            (obligatoria para fallback)
    MONGO_URI             (obligatoria)

Uso manual (solo fallback):
    python src/ingestion/waqi_air_quality_client.py --hours 6
===================================================================
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Iterable

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
from src.ingestion.waqi_station_map import (
    WAQI_FALLBACK_STATIONS,
    WAQI_STATION_PROXY_LABEL,
    WAQI_STATION_UID_OVERRIDE,
)

MONGO_URI = os.getenv("MONGO_URI")

PM25_MAX = float(os.getenv("AIRVLC_PM25_MAX", "500"))
NO2_MAX = float(os.getenv("AIRVLC_NO2_MAX", "1000"))
O3_MAX = float(os.getenv("AIRVLC_O3_MAX", "1000"))

WAQI_BASE = "https://api.waqi.info"
# Máx. distancia sensor WAQI → coordenadas AirVLC (el feed geo: devuelve ciudades erróneas).
WAQI_MAX_DISTANCE_KM = float(os.getenv("WAQI_MAX_DISTANCE_KM", "30"))


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math

    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _get_token() -> str:
    token = (os.getenv("WAQI_TOKEN") or "").strip().strip('"').strip("'")
    if not token:
        raise RuntimeError(
            "WAQI_TOKEN no configurada. Obtén un token en https://aqicn.org/data-platform/token/ "
            "y añádela al archivo .env"
        )
    return token


def _parse_time_iso(data: dict) -> datetime | None:
    """Acepta ``time.iso`` o ``time.s`` + ``time.tz`` como en la API WAQI."""
    t = (data or {}).get("time") or {}
    iso = t.get("iso")
    if iso:
        try:
            return datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    s = t.get("s")
    tz = t.get("tz")
    if s:
        s = str(s).strip()
        if tz and not s.endswith(str(tz)):
            # "2026-05-17 17:00:00" + "+08:00" → ISO con offset
            try:
                return datetime.fromisoformat(f"{s}{tz}")
            except ValueError:
                pass
        try:
            return datetime.fromisoformat(s.replace(" ", "T"))
        except ValueError:
            pass
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
    pm_i = _iaqi_v(iaqi, "pm25")
    no2_i = _iaqi_v(iaqi, "no2")
    o3_i = _iaqi_v(iaqi, "o3")

    pm25 = pm25_subindex_to_ugm3(pm_i) if pm_i is not None else None
    no2 = no2_subindex_to_ugm3(no2_i) if no2_i is not None else None
    o3 = o3_subindex_to_ugm3(o3_i) if o3_i is not None else None
    return pm25, no2, o3


def _plausible(pm25: float, no2: float, o3: float) -> bool:
    if pm25 < 0 or no2 < 0 or o3 < 0:
        return False
    if pm25 > PM25_MAX or no2 > NO2_MAX or o3 > O3_MAX:
        return False
    return True


def _feed_url_for_station(station: str) -> str:
    if station not in WAQI_FALLBACK_STATIONS:
        raise ValueError(
            f"WAQI solo permitido para fallback {sorted(WAQI_FALLBACK_STATIONS)}; "
            f"recibido: {station!r}"
        )
    token = _get_token()
    uid = WAQI_STATION_UID_OVERRIDE.get(station)
    if uid is None:
        raise RuntimeError(
            f"Falta WAQI_STATION_UID_OVERRIDE para {station!r}. "
            "No usar feed/geo: — en Valencia devuelve sensores incorrectos (p. ej. Murcia)."
        )
    return f"{WAQI_BASE}/feed/@{uid}/?token={token}"


def fetch_station_payload(station: str) -> dict | None:
    """GET una estación fallback; devuelve el JSON ``data`` o None."""
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
    data = body.get("data")
    if not data:
        return None

    city = (data.get("city") or {})
    city_name = city.get("name") or "?"
    geo = city.get("geo") or []
    coords = STATION_COORDS.get(station) or {}
    if coords and len(geo) >= 2:
        km = _haversine_km(coords["lat"], coords["lon"], float(geo[0]), float(geo[1]))
        if km > WAQI_MAX_DISTANCE_KM:
            print(
                f"   ⚠️  WAQI [{station}] rechazado: {city_name!r} está a {km:.0f} km "
                f"(máx {WAQI_MAX_DISTANCE_KM:.0f} km). Revisa WAQI_STATION_UID_OVERRIDE."
            )
            return None

    proxy = WAQI_STATION_PROXY_LABEL.get(station, "")
    print(
        f"   📡 WAQI [{station}] ← {city_name!r} (idx={data.get('idx')})"
        + (f" [proxy: {proxy}]" if proxy else "")
    )
    return data


def build_document(station: str, data: dict, hours: int) -> dict | None:
    """Construye documento Mongo o None si fuera de ventana / incompleto."""
    if station not in WAQI_FALLBACK_STATIONS:
        return None

    fecha_dt = _parse_time_iso(data)
    if fecha_dt is None:
        print(f"   ⚠️  Sin timestamp WAQI [{station}]")
        return None

    if fecha_dt.tzinfo is None:
        fecha_dt = fecha_dt.replace(tzinfo=timezone.utc)
    else:
        fecha_dt = fecha_dt.astimezone(timezone.utc)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    if fecha_dt < cutoff:
        print(f"   ⚠️  Dato demasiado antiguo [{station}] {fecha_dt.isoformat()} (>{hours}h)")
        return None

    iaqi = data.get("iaqi") or {}
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
    coords = STATION_COORDS.get(station) or {}

    return {
        "estacion": station,
        "fecha_iso": fecha_iso,
        "fecha": fecha_dt,
        "pm25": pm25,
        "no2": no2,
        "o3": o3,
        "is_canonical_v2": True,
        "longitude": coords.get("lon"),
        "latitude": coords.get("lat"),
        "location": (
            {"type": "Point", "coordinates": [coords["lon"], coords["lat"]]}
            if coords.get("lon") is not None and coords.get("lat") is not None
            else None
        ),
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "source": "waqi",
        "waqi_city_name": city,
        "waqi_proxy_label": WAQI_STATION_PROXY_LABEL.get(station),
        "waqi_feed_uid": WAQI_STATION_UID_OVERRIDE.get(station),
        "waqi_idx": data.get("idx"),
        "waqi_time_raw": (data.get("time") or {}),
        "waqi_iaqi_raw": iaqi,
        "waqi_raw_values": {"pm25": raw_pm25, "no2": raw_no2, "o3": raw_o3},
        "conversion": {
            "method": "epa_aqi_subindex_to_ugm3",
            "note": "iaqi.*.v tratados como subíndices AQI EPA.",
        },
    }


def upsert_to_mongo(documents: list) -> dict:
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

    ops = [
        UpdateOne(
            {"estacion": doc["estacion"], "fecha_iso": doc["fecha_iso"]},
            {"$set": doc},
            upsert=True,
        )
        for doc in documents
    ]

    if not ops:
        return {"inserted": 0, "modified": 0, "errors": 0}

    result = coll.bulk_write(ops, ordered=False)
    client.close()

    return {
        "inserted": result.upserted_count,
        "modified": result.modified_count,
        "errors": 0,
    }


def fetch_waqi_for_stations(
    stations: Iterable[str],
    *,
    hours: int = 6,
) -> dict:
    """Ingesta WAQI solo para las estaciones indicadas (deben ser fallback)."""
    allowed = WAQI_FALLBACK_STATIONS
    targets = [s for s in stations if s in allowed]
    skipped = [s for s in stations if s not in allowed]

    if skipped:
        print(
            f"   ⚠️  WAQI ignoradas (no son fallback GVA): {skipped}. "
            f"Permitidas: {sorted(allowed)}"
        )

    print(f"🔍 WAQI fallback — ventana {hours}h, estaciones={targets}")

    raw_count = 0
    parsed_docs: list = []

    for station in targets:
        data = fetch_station_payload(station)
        if not data:
            continue
        raw_count += 1
        doc = build_document(station, data, hours=hours)
        if doc:
            parsed_docs.append(doc)

    print(f"   📊 Respuestas ok: {raw_count}, documentos válidos: {len(parsed_docs)}")

    if not parsed_docs:
        return {"raw": raw_count, "parsed": 0, "inserted": 0, "modified": 0, "stations": targets}

    stats = upsert_to_mongo(parsed_docs)
    print(f"   ✅ Mongo upsert: {stats['inserted']} nuevos, {stats['modified']} actualizados")

    return {
        "raw": raw_count,
        "parsed": len(parsed_docs),
        "stations": targets,
        **stats,
    }


def fetch_waqi_air_quality(hours: int = 6) -> dict:
    """Pipeline fallback: **solo** ``WAQI_FALLBACK_STATIONS`` (Puerto Valencia)."""
    return fetch_waqi_for_stations(WAQI_FALLBACK_STATIONS, hours=hours)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="WAQI → Mongo (solo estaciones fallback, p. ej. Puerto Valencia)"
    )
    parser.add_argument("--hours", type=int, default=48, help="Ventana máxima de antigüedad del dato")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("🌍 AirVLC — WAQI fallback (Puerto Valencia)")
    print("=" * 60 + "\n")

    result = fetch_waqi_air_quality(hours=args.hours)
    print(f"\n🎯 Resultado: {result}")
