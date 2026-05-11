"""
===================================================================
🏛️ Valencia Air Quality Client — Sprint 5 B.1
===================================================================
Descarga las mediciones recientes de contaminantes (PM2.5, NO2, O3)
de la API de datos abiertos del Ayuntamiento de Valencia (Opendatasoft)
y las guarda con upsert idempotente en MongoDB `airvlc_db.aire_realtime`.

Clave de upsert: {estacion, fecha_iso}  — evita duplicados.

Variables de entorno:
    VALENCIA_AIR_API_URL  (opcional, hay default)
    MONGO_URI             (obligatoria)

Uso:
    python src/ingestion/valencia_air_quality_client.py          # últimas 48h
    python src/ingestion/valencia_air_quality_client.py --hours 6

    Desde código:
        from src.ingestion.valencia_air_quality_client import fetch_valencia_air_quality
        result = fetch_valencia_air_quality(hours=6)
===================================================================
"""

import os
import sys
import argparse
from datetime import datetime, timedelta, timezone

import requests
from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT_DIR)
load_dotenv(os.path.join(ROOT_DIR, '.env'))

MONGO_URI = os.getenv("MONGO_URI")

# -----------------------------------------------------------------------
# Endpoint por defecto: Geoportal Valencia (OpenData) con snapshot
# de valores actuales por estación.
#
# Nota: históricamente se usó Opendatasoft (`valencia.opendatasoft.com`),
# pero ese dominio puede no estar disponible / haber cambiado.
# Este client soporta ambos formatos y hace fallback automático.
#
# Se puede sobreescribir con la env VALENCIA_AIR_API_URL.
# -----------------------------------------------------------------------
DEFAULT_API_URL = "https://geoportal.valencia.es/apps/OpenData/MedioAmbiente/estatautomaticas.json"

VALENCIA_AIR_API_URL = os.getenv("VALENCIA_AIR_API_URL", DEFAULT_API_URL)

# Mapeo: nombre de estación en la API → nombre canónico en master_dataset_colab_v2.csv
# La API puede devolver variantes (mayúsculas, tildes diferentes, etc.)
STATION_CANONICAL_MAP = {
    "av. francia": "Francia",
    "avda. francia": "Francia",
    "avda.francia": "Francia",
    "francia": "Francia",
    "molí del sol": "Molí del Sol",
    "moli del sol": "Molí del Sol",
    "pista de silla": "Pista de Silla",
    "pista silla": "Pista de Silla",
    "puerto valencia": "Puerto Valencia",
    "puerto": "Puerto Valencia",
    "moll de la duana": "Puerto Valencia",
    "moll trans. ponent": "Puerto Moll Trans. Ponent",
    "puerto moll trans. ponent": "Puerto Moll Trans. Ponent",
    "moll trans ponent": "Puerto Moll Trans. Ponent",
    "llit antic del turia": "Puerto llit antic Túria",
    "llit antic del túria": "Puerto llit antic Túria",
    "puerto llit antic túria": "Puerto llit antic Túria",
    "puerto llit antic turia": "Puerto llit antic Túria",
    "universitat politècnica de valència": "Universidad Politécnica",
    "politècnic": "Universidad Politécnica",
    "politecnico": "Universidad Politécnica",
    "universidad politécnica": "Universidad Politécnica",
    "universidad politecnica": "Universidad Politécnica",
    "politécnico": "Universidad Politécnica",
}

# Estaciones válidas del CSV v2
VALID_STATIONS = {
    "Francia", "Molí del Sol", "Pista de Silla",
    "Puerto Moll Trans. Ponent", "Puerto Valencia",
    "Puerto llit antic Túria", "Universidad Politécnica",
}


def normalize_station(raw_name: str) -> str | None:
    """Intenta mapear el nombre de la API al canónico del CSV v2."""
    if not raw_name:
        return None
    norm = raw_name.strip().lower()

    # Coincidencia directa
    if norm in STATION_CANONICAL_MAP:
        return STATION_CANONICAL_MAP[norm]

    # Coincidencia parcial (la API a veces añade prefijos/sufijos)
    for key, canonical in STATION_CANONICAL_MAP.items():
        if key in norm or norm in key:
            return canonical

    # Si ya es un nombre canónico (case-insensitive)
    for s in VALID_STATIONS:
        if s.lower() == norm:
            return s

    return None


def _safe_float(val):
    if val is None:
        return None
    try:
        return float(str(val).replace(",", "."))
    except (ValueError, TypeError):
        return None


def _parse_fecha_carga(fecha_carga: str) -> datetime | None:
    """
    Geoportal usa `fecha_carga` como string `YYYYMMDDHHMMSS` (ej. 20230502112013).
    """
    if not fecha_carga:
        return None
    s = str(fecha_carga).strip()
    if len(s) != 14 or not s.isdigit():
        return None
    try:
        # Sin timezone explícita; asumimos hora local de Valencia y la tratamos como UTC-naive.
        # El resto del pipeline usa ISO; si necesitas zona, ajustamos más adelante.
        return datetime.strptime(s, "%Y%m%d%H%M%S")
    except Exception:
        return None


def parse_records(raw_records: list) -> list:
    """Convierte registros crudos a documentos listos para Mongo.

    Soporta 2 formatos:
    - Opendatasoft: lista de dicts con campos planos.
    - Geoportal: FeatureCollection (aquí raw_records ya viene como list de `features`).
    """
    parsed = []
    for rec in raw_records:
        # Geoportal FeatureCollection: {type, geometry, properties:{...}}
        if isinstance(rec, dict) and "properties" in rec:
            fields = rec.get("properties", {}) or {}
            station_raw = fields.get("nombre") or fields.get("estacion") or fields.get("station") or ""
            canonical = normalize_station(station_raw)
            if canonical is None:
                continue

            fecha_dt = _parse_fecha_carga(fields.get("fecha_carga")) or datetime.utcnow()
            fecha_iso = fecha_dt.replace(tzinfo=timezone.utc).isoformat()

            doc = {
                "estacion": canonical,
                "fecha_iso": fecha_iso,
                "fecha": fecha_dt.replace(tzinfo=timezone.utc),
                "pm25": _safe_float(fields.get("pm25")),
                "no2": _safe_float(fields.get("no2")),
                "o3": _safe_float(fields.get("o3")),
                "so2": _safe_float(fields.get("so2")),
                "co": _safe_float(fields.get("co")),
                "pm10": _safe_float(fields.get("pm10")),
                "ingested_at": datetime.utcnow().isoformat(),
                "source": "valencia_geoportal",
                "raw_station_name": station_raw,
            }
            parsed.append(doc)
            continue

        # Opendatasoft: dict plano
        fields = rec if "fields" not in rec else rec.get("fields", rec)

        # La API puede usar distintos nombres de campo
        station_raw = (
            fields.get("estacion")
            or fields.get("estaci_")
            or fields.get("station")
            or fields.get("nombre")
            or ""
        )
        canonical = normalize_station(station_raw)
        if canonical is None:
            continue  # estación no reconocida, saltamos

        # Timestamp: intentar varios campos
        fecha_str = (
            fields.get("fecha")
            or fields.get("date")
            or fields.get("datetime")
            or fields.get("fecha_dato")
            or ""
        )
        if not fecha_str:
            continue

        try:
            fecha_dt = datetime.fromisoformat(str(fecha_str).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue

        fecha_iso = fecha_dt.isoformat()

        doc = {
            "estacion": canonical,
            "fecha_iso": fecha_iso,
            "fecha": fecha_dt,
            "pm25": _safe_float(fields.get("pm2_5") or fields.get("pm25")),
            "no2": _safe_float(fields.get("no2")),
            "o3": _safe_float(fields.get("o3")),
            "so2": _safe_float(fields.get("so2")),
            "co": _safe_float(fields.get("co")),
            "pm10": _safe_float(fields.get("pm10")),
            "ingested_at": datetime.utcnow().isoformat(),
            "source": "valencia_opendata",
        }
        parsed.append(doc)

    return parsed


def _looks_like_html(text: str | None) -> bool:
    if not text:
        return False
    t = text.lstrip().lower()
    return t.startswith("<!doctype html") or t.startswith("<html") or "<head" in t[:200]


def fetch_from_api(hours: int = 48, limit: int = 200) -> list:
    """Descarga registros de la fuente configurada.

    - Si `VALENCIA_AIR_API_URL` apunta a Geoportal JSON (FeatureCollection),
      devuelve `features`.
    - Si apunta a Opendatasoft `/records`, aplica query param `where`.
    - Si hay 404 o HTML (dominio cambiado), hace fallback al Geoportal.
    """
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    print(f"🔍 Consultando API Valencia Air Quality (últimas {hours}h)...")
    print(f"   URL: {VALENCIA_AIR_API_URL}")

    try:
        # Geoportal: no soporta filtros; Opendatasoft sí.
        params = None
        if "/api/explore/" in VALENCIA_AIR_API_URL and "/records" in VALENCIA_AIR_API_URL:
            params = {
                "limit": limit,
                "order_by": "fecha desc",
                "where": f"fecha >= '{since}'",
            }

        resp = requests.get(VALENCIA_AIR_API_URL, params=params, timeout=30)
        if resp.status_code == 404 or _looks_like_html(resp.text):
            raise requests.HTTPError(f"Not Found/HTML from configured URL ({resp.status_code})", response=resp)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"❌ Error conectando a la API de Valencia: {e}")
        # Fallback automático al Geoportal si no estábamos ya en él
        if VALENCIA_AIR_API_URL != DEFAULT_API_URL:
            print("↪️  Probando fallback al Geoportal de Valencia...")
            try:
                resp = requests.get(DEFAULT_API_URL, timeout=30)
                resp.raise_for_status()
            except requests.RequestException as e2:
                print(f"❌ Fallback Geoportal falló: {e2}")
                return []
        else:
            return []

    data = resp.json()

    # Geoportal: FeatureCollection {features:[...]}
    if isinstance(data, dict) and "features" in data and isinstance(data["features"], list):
        return data["features"]

    # Opendatasoft v2.1 devuelve {results: [...]}
    if "results" in data:
        return data["results"]
    # Opendatasoft v1 devuelve {records: [{fields: {...}}, ...]}
    if "records" in data:
        return [r.get("fields", r) for r in data["records"]]

    return []


def upsert_to_mongo(documents: list) -> dict:
    """Upsert idempotente en MongoDB airvlc_db.aire_realtime."""
    if not MONGO_URI:
        print("❌ MONGO_URI no configurado en .env")
        return {"inserted": 0, "modified": 0, "errors": 0}

    client = MongoClient(MONGO_URI)
    db = client["airvlc_db"]
    coll = db["aire_realtime"]

    # Crear índice único para idempotencia
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


def fetch_valencia_air_quality(hours: int = 48) -> dict:
    """Pipeline completo: API → parse → MongoDB.
    Devuelve dict con estadísticas."""
    raw = fetch_from_api(hours=hours)
    if not raw:
        print("⚠️  Sin datos nuevos de la API de Valencia.")
        return {"raw": 0, "parsed": 0, "inserted": 0, "modified": 0}

    parsed = parse_records(raw)
    print(f"   📊 Registros crudos: {len(raw)}, parseados válidos: {len(parsed)}")

    if not parsed:
        return {"raw": len(raw), "parsed": 0, "inserted": 0, "modified": 0}

    stats = upsert_to_mongo(parsed)
    print(f"   ✅ Mongo upsert: {stats['inserted']} nuevos, {stats['modified']} actualizados")

    return {
        "raw": len(raw),
        "parsed": len(parsed),
        **stats,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Descarga contaminantes Valencia Open Data → MongoDB")
    parser.add_argument("--hours", type=int, default=48, help="Horas hacia atrás (default: 48)")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("🏛️ AirVLC — Valencia Air Quality Client (Sprint 5)")
    print("=" * 60 + "\n")

    result = fetch_valencia_air_quality(hours=args.hours)
    print(f"\n🎯 Resultado: {result}")
