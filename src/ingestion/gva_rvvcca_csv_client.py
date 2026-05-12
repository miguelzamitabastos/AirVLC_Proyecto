"""
===================================================================
🏛️  GVA RVVCCA CSV Client — Ingesta oficial Comunitat Valenciana
===================================================================
Descarga el snapshot horario de la Red Valenciana de Vigilancia y
Control de la Contaminación Atmosférica (RVVCCA) publicada por la
Generalitat Valenciana a través de TerraMapas (servicio WFS).

URL oficial (parámetros estándar WFS 2.0.0, output CSV):

    https://terramapas.icv.gva.es/0503_CalidadAire?request=GetFeature
        &service=WFS&version=2.0.0&typename=RVVCCA.ICA&outputformat=csv

El CSV contiene una fila por estación con el último valor horario
oficial de SO2, NO2, PM2.5, PM10 y O3 (cuando proceda) y datos de
ubicación (lon/lat, comarca, provincia, municipio).

Este módulo:
    1. Descarga el CSV (o lee uno local).
    2. Lo parsea (csv.DictReader, robusto a comas dentro de comillas).
    3. Mapea las estaciones a un esquema estable.
    4. Aplica un filtro de outliers basado en el historial (Mongo).
    5. Upsert idempotente en ``airvlc_db.aire_realtime`` (clave: stationid + fecha_iso).
    6. Crea índices útiles (``fecha`` desc + ``estacion``) y, opcionalmente,
       una Time Series Collection (``aire_realtime_ts``) en Atlas.

Compatibilidad con el pipeline v2:
    Las 7 estaciones canónicas del modelo ML siguen llamándose igual
    en el campo ``estacion`` para que ``routes_v2.py`` no rompa. El resto
    de estaciones se guardan con su nombre oficial GVA en ese mismo
    campo. Todas conservan el ``station_id`` GVA en un campo aparte.

Variables de entorno:
    MONGO_URI               (obligatoria para upsert).
    GVA_RVVCCA_CSV_URL      (opcional, override de la URL oficial).
    GVA_OUTLIER_MAX_RATIO   (opcional, default 5.0).

Uso CLI:
    python src/ingestion/gva_rvvcca_csv_client.py               # descarga + upsert
    python src/ingestion/gva_rvvcca_csv_client.py --csv ruta.csv  # lee fichero local
    python src/ingestion/gva_rvvcca_csv_client.py --dry-run       # parsea pero no escribe
    python src/ingestion/gva_rvvcca_csv_client.py --create-ts     # crea aire_realtime_ts

Desde código:
    from src.ingestion.gva_rvvcca_csv_client import fetch_gva_rvvcca
    result = fetch_gva_rvvcca()
===================================================================
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Iterable

import requests
from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient, UpdateOne
from pymongo.errors import CollectionInvalid

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)
load_dotenv(os.path.join(ROOT_DIR, ".env"))

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
MONGO_URI = os.getenv("MONGO_URI")
DEFAULT_CSV_URL = (
    "https://terramapas.icv.gva.es/0503_CalidadAire"
    "?request=GetFeature&service=WFS&version=2.0.0"
    "&typename=RVVCCA.ICA&outputformat=csv"
)
CSV_URL = os.getenv("GVA_RVVCCA_CSV_URL", DEFAULT_CSV_URL)
OUTLIER_MAX_RATIO = float(os.getenv("GVA_OUTLIER_MAX_RATIO", "5.0"))
OUTLIER_MIN_FLOOR = 2.0  # µg/m³: si la mediana histórica es < 2, ignoramos el ratio.

# Las 7 estaciones canónicas del modelo v2. El nombre del fichero CSV de GVA
# se mapea a estos nombres para preservar compatibilidad con `routes_v2.py`,
# `feature_extractor_v2.py` y la app Flutter.
CANONICAL_NAME_BY_GVA: dict[str, str] = {
    # raw GVA stationname (lower-cased, espacios colapsados) → canónico v2
    "valència - av. frança": "Francia",
    "valencia - av. franca": "Francia",
    "valència - molí del sol": "Molí del Sol",
    "valencia - moli del sol": "Molí del Sol",
    "valència - pista de silla": "Pista de Silla",
    "valencia - pista de silla": "Pista de Silla",
    "valència - politècnic": "Universidad Politécnica",
    "valencia - politecnic": "Universidad Politécnica",
    "valència port llit antic túria": "Puerto llit antic Túria",
    "valencia port llit antic turia": "Puerto llit antic Túria",
    "val port moll ponent": "Puerto Moll Trans. Ponent",
    "val port moll  ponent": "Puerto Moll Trans. Ponent",  # CSV trae doble espacio
}

# Las 7 canónicas (idéntico al backend / Flutter).
CANONICAL_V2_STATIONS: set[str] = {
    "Francia",
    "Molí del Sol",
    "Pista de Silla",
    "Puerto Moll Trans. Ponent",
    "Puerto Valencia",
    "Puerto llit antic Túria",
    "Universidad Politécnica",
}

# Campos GVA → campos limpios en Mongo (subset). El resto se guarda en
# `raw_fields` por trazabilidad.
POLLUTANT_FIELDS: dict[str, str] = {
    "so2value": "so2",
    "no2value": "no2",
    "pm25value": "pm25",
    "pm10value": "pm10",
    "o3value": "o3",
}

# Quality fields (numeric quality id 0–5 según GVA). 0 = sin datos.
QUALITY_FIELDS: dict[str, str] = {
    "so2qaulityid": "so2_quality_id",
    "no2qaulityid": "no2_quality_id",
    "pm25qaulityid": "pm25_quality_id",
    "pm10qaulityid": "pm10_quality_id",
    "o3qaulityid": "o3_quality_id",
}


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------
_VALUE_PATTERN = re.compile(r"-?\d+(?:[\.,]\d+)?")


def _extract_number(raw: str | None) -> float | None:
    """Saca el número de strings tipo "12 µg/m³", "0,5 mg/m³" o "".
    Devuelve None si no hay valor numérico válido."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s.upper() in {"", "ND", "S/D", "SIN DATOS", "SENSE DADES"}:
        return None
    m = _VALUE_PATTERN.search(s.replace(",", "."))
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _safe_float(raw) -> float | None:
    if raw is None:
        return None
    try:
        return float(str(raw).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _safe_int(raw) -> int | None:
    if raw is None:
        return None
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _parse_timeinstant(value: str | None) -> datetime | None:
    """GVA usa ``2026-05-12 07:35:14+02`` (ISO con offset corto)."""
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    # Normaliza ``+02`` → ``+02:00``
    if re.search(r"[+-]\d{2}$", s):
        s = s + ":00"
    s = s.replace(" ", "T")
    try:
        return datetime.fromisoformat(s).astimezone(timezone.utc)
    except ValueError:
        try:
            return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def _normalize_station_key(name: str) -> str:
    """Lower-cased + colapsa espacios múltiples para hacer match con el mapa."""
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def resolve_canonical_station(raw_name: str) -> str | None:
    """Devuelve el nombre canónico v2 (Francia, Molí del Sol, ...) o None
    si la estación NO forma parte de las 7 del modelo (pero igualmente la
    guardamos con su nombre oficial GVA)."""
    if not raw_name:
        return None
    key = _normalize_station_key(raw_name)
    return CANONICAL_NAME_BY_GVA.get(key)


# ---------------------------------------------------------------------------
# Descarga del CSV
# ---------------------------------------------------------------------------
def download_csv(url: str = CSV_URL, timeout: int = 30) -> str:
    """Descarga el CSV (text/csv) de la GVA y devuelve el cuerpo como str.

    Importante: el WFS de TerraMapas devuelve ``Content-Type: text/csv`` SIN
    ``charset``, así que ``requests`` por defecto asume Latin-1 y rompe los
    nombres con acentos (Valencia → ValÃ¨ncia). Forzamos UTF-8 explícito.
    """
    print(f"⬇️  Descargando RVVCCA GVA: {url}")
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    text = resp.text
    if not text.lstrip().startswith("WKT"):
        raise RuntimeError(
            "Respuesta inesperada del WFS (no empieza por cabecera 'WKT'). "
            f"Primeros 80 bytes: {text[:80]!r}"
        )
    return text


def read_csv_text(text: str) -> list[dict[str, str]]:
    """Convierte el texto CSV en lista de dicts (DictReader)."""
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


# ---------------------------------------------------------------------------
# Parsing de filas
# ---------------------------------------------------------------------------
def parse_row(row: dict[str, str]) -> dict | None:
    """Convierte una fila CSV → documento limpio listo para Mongo.

    Devuelve None si la fila no tiene timestamp o stationid (registro inútil).
    """
    station_id = (row.get("stationid") or "").strip()
    station_name = (row.get("stationname") or "").strip()
    timeinstant = (row.get("timeinstant") or "").strip()
    if not station_id or not station_name or not timeinstant:
        return None

    fecha_dt = _parse_timeinstant(timeinstant)
    if fecha_dt is None:
        return None
    fecha_iso = fecha_dt.isoformat().replace("+00:00", "Z")

    lon = _safe_float(row.get("stationlongitude"))
    lat = _safe_float(row.get("stationlatitude"))

    canonical = resolve_canonical_station(station_name)
    # El campo `estacion` del documento Mongo sigue el contrato existente:
    # las 7 canónicas usan su nombre del modelo; el resto usan el nombre
    # oficial GVA (sirven para mapa/ranking, no para el modelo).
    estacion_field = canonical or station_name

    pollutants = {
        clean_name: _extract_number(row.get(csv_name))
        for csv_name, clean_name in POLLUTANT_FIELDS.items()
    }
    qualities = {
        clean_name: _safe_int(row.get(csv_name))
        for csv_name, clean_name in QUALITY_FIELDS.items()
    }

    doc: dict = {
        # Identidad
        "station_id": station_id,                # 46250048
        "station_code": (row.get("stationcode") or "").strip(),
        "station_name_gva": station_name,        # tal como lo da la GVA
        "estacion": estacion_field,              # canónico v2 si aplica
        "is_canonical_v2": canonical is not None,

        # Timestamp
        "fecha": fecha_dt,                       # datetime UTC (timeField)
        "fecha_iso": fecha_iso,                  # str ISO para upserts idempotentes

        # Localización
        "location": (
            {"type": "Point", "coordinates": [lon, lat]}
            if lon is not None and lat is not None
            else None
        ),
        "longitude": lon,
        "latitude": lat,
        "municipality": (row.get("municipalityname") or "").strip(),
        "municipality_ca": (row.get("noms_mun") or "").strip(),
        "comarca": (row.get("comarca") or "").strip(),
        "provincia": (row.get("provincia") or "").strip(),
        "station_type": (row.get("stationtype") or "").strip(),
        "station_source": (row.get("stationsource") or "").strip(),

        # Contaminantes
        **pollutants,
        **qualities,
        "quality_color": (row.get("stqualitycolor") or "").strip() or None,

        # Trazabilidad
        "url_es": (row.get("url_cas") or "").strip() or None,
        "url_val": (row.get("url_val") or "").strip() or None,
        "source": "gva_rvvcca_csv",
        "is_synthetic": False,
        "ingested_at": datetime.now(timezone.utc),
    }
    return doc


def parse_rows(rows: Iterable[dict[str, str]]) -> list[dict]:
    """Parsea filas, descarta las inválidas, devuelve lista de documentos."""
    parsed: list[dict] = []
    skipped = 0
    for r in rows:
        d = parse_row(r)
        if d is None:
            skipped += 1
            continue
        parsed.append(d)
    if skipped:
        print(f"   ⚠️  Filas descartadas por datos incompletos: {skipped}")
    return parsed


# ---------------------------------------------------------------------------
# Filtro de outliers
# ---------------------------------------------------------------------------
def _is_outlier(
    new_value: float,
    history: list[float],
    *,
    max_ratio: float = OUTLIER_MAX_RATIO,
) -> bool:
    """Detecta picos absurdos contra el historial reciente de la misma
    estación/contaminante.

    Criterios (todos deben cumplirse para marcarlo outlier):
        1. Hay al menos 3 puntos previos válidos.
        2. La mediana histórica está por encima del piso ``OUTLIER_MIN_FLOOR``
           (evitamos clasificar 1 → 10 µg/m³ como outlier cuando el sensor
            normalmente está cerca de cero).
        3. ``new_value`` > ``mediana * max_ratio`` o < ``mediana / max_ratio``.
    """
    if len(history) < 3:
        return False
    med = median(history)
    if med < OUTLIER_MIN_FLOOR:
        return False
    if new_value <= 0:
        return False
    return (new_value > med * max_ratio) or (new_value < med / max_ratio)


def _fetch_recent_history(
    coll, station_id: str, pollutant: str, *, hours: int = 6
) -> list[float]:
    """Últimos `hours` valores válidos del contaminante para outlier check."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    cur = (
        coll.find(
            {"station_id": station_id, "fecha": {"$gte": since}, pollutant: {"$ne": None}},
            {"_id": 0, pollutant: 1},
        )
        .sort("fecha", DESCENDING)
        .limit(12)
    )
    out: list[float] = []
    for d in cur:
        v = d.get(pollutant)
        if isinstance(v, (int, float)):
            out.append(float(v))
    return out


def apply_outlier_filter(coll, documents: list[dict]) -> tuple[list[dict], dict]:
    """Marca los picos atípicos contra el histórico Mongo. NO descarta el
    documento; añade ``outliers`` (lista) y ``is_outlier_any`` (bool) y
    pone a None los contaminantes marcados — así no contaminan los gráficos
    pero sí queda traza en ``raw_outlier_values``.
    """
    if coll is None:
        return documents, {"outliers_detected": 0, "checked": 0}

    pollutants = list(POLLUTANT_FIELDS.values())
    flagged = 0
    checked = 0
    for doc in documents:
        sid = doc.get("station_id")
        if not sid:
            continue
        outliers: list[str] = []
        raw_outlier_values: dict[str, float] = {}
        for p in pollutants:
            val = doc.get(p)
            if val is None:
                continue
            history = _fetch_recent_history(coll, sid, p)
            checked += 1
            if _is_outlier(val, history):
                outliers.append(p)
                raw_outlier_values[p] = val
                doc[p] = None  # blanqueamos el valor limpio
                flagged += 1
        if outliers:
            doc["outliers"] = outliers
            doc["raw_outlier_values"] = raw_outlier_values
        doc["is_outlier_any"] = bool(outliers)
    return documents, {"outliers_detected": flagged, "checked": checked}


# ---------------------------------------------------------------------------
# Persistencia
# ---------------------------------------------------------------------------
def _ensure_indexes(coll) -> None:
    """Crea (idempotente) índices esenciales para consultas time-series."""
    coll.create_index(
        [("station_id", ASCENDING), ("fecha_iso", ASCENDING)],
        unique=True,
        name="idx_stationid_fechaiso_unique",
        background=True,
    )
    coll.create_index(
        [("estacion", ASCENDING), ("fecha", DESCENDING)],
        name="idx_estacion_fecha_desc",
        background=True,
    )
    coll.create_index(
        [("fecha", DESCENDING)],
        name="idx_fecha_desc",
        background=True,
    )
    coll.create_index(
        [("location", "2dsphere")],
        name="idx_location_geo",
        background=True,
        sparse=True,
    )


def upsert_to_mongo(documents: list[dict]) -> dict:
    """Upsert idempotente en `airvlc_db.aire_realtime`. Clave: (station_id, fecha_iso)."""
    if not MONGO_URI:
        print("❌ MONGO_URI no configurado en .env")
        return {"inserted": 0, "modified": 0, "matched": 0}

    client = MongoClient(MONGO_URI)
    db = client["airvlc_db"]
    coll = db["aire_realtime"]
    _ensure_indexes(coll)

    ops = [
        UpdateOne(
            {"station_id": d["station_id"], "fecha_iso": d["fecha_iso"]},
            {"$set": d},
            upsert=True,
        )
        for d in documents
    ]
    if not ops:
        client.close()
        return {"inserted": 0, "modified": 0, "matched": 0}

    result = coll.bulk_write(ops, ordered=False)
    client.close()
    return {
        "inserted": result.upserted_count,
        "modified": result.modified_count,
        "matched": result.matched_count,
    }


def ensure_timeseries_collection(name: str = "aire_realtime_ts") -> dict:
    """Crea (si no existe) una **Time Series Collection** en MongoDB Atlas
    apuntando a ``fecha`` con metaField ``station_id`` y granularidad hora.

    No migra datos: solo deja la colección lista para que ingestas futuras
    puedan duplicarse aquí. Mongo 5.0+ / Atlas M0+ lo soporta.
    """
    if not MONGO_URI:
        return {"created": False, "error": "MONGO_URI no configurado"}
    client = MongoClient(MONGO_URI)
    db = client["airvlc_db"]
    try:
        db.create_collection(
            name,
            timeseries={
                "timeField": "fecha",
                "metaField": "station_id",
                "granularity": "hours",
            },
        )
        msg = {"created": True, "name": name}
    except CollectionInvalid:
        msg = {"created": False, "name": name, "note": "ya existía"}
    except Exception as e:  # pragma: no cover
        msg = {"created": False, "error": str(e)}
    finally:
        client.close()
    return msg


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------
def fetch_gva_rvvcca(
    *,
    csv_path: str | None = None,
    url: str | None = None,
    dry_run: bool = False,
    apply_outliers: bool = True,
) -> dict:
    """Pipeline completo: descarga (o lee local) → parse → outliers → upsert.

    Args:
        csv_path: si se pasa, lee el fichero local en vez de descargar.
        url:       override de la URL del WFS.
        dry_run:   no escribe en Mongo, solo devuelve estadísticas.
        apply_outliers: aplica el filtro contra el histórico Mongo.
    """
    if csv_path:
        print(f"📂 Leyendo CSV local: {csv_path}")
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            text = f.read()
    else:
        text = download_csv(url or CSV_URL)

    rows = read_csv_text(text)
    print(f"   📄 Filas CSV crudas: {len(rows)}")
    docs = parse_rows(rows)
    print(f"   ✅ Documentos parseados: {len(docs)}")

    # Subgrupos para reporting
    canonical_count = sum(1 for d in docs if d.get("is_canonical_v2"))
    by_province: dict[str, int] = defaultdict(int)
    for d in docs:
        by_province[d.get("provincia") or "?"] += 1
    print(f"   🎯 Estaciones canónicas v2 detectadas: {canonical_count}/7")
    for prov, n in sorted(by_province.items()):
        print(f"      • {prov}: {n}")

    if dry_run:
        return {
            "raw": len(rows),
            "parsed": len(docs),
            "canonical_v2": canonical_count,
            "by_province": dict(by_province),
            "outliers_detected": 0,
            "inserted": 0,
            "modified": 0,
            "dry_run": True,
        }

    if not MONGO_URI:
        print("⚠️  Sin MONGO_URI: no se persiste. Use --dry-run para evitar este warning.")
        return {
            "raw": len(rows),
            "parsed": len(docs),
            "canonical_v2": canonical_count,
            "by_province": dict(by_province),
            "inserted": 0,
            "modified": 0,
        }

    client = MongoClient(MONGO_URI)
    coll = client["airvlc_db"]["aire_realtime"]
    _ensure_indexes(coll)

    if apply_outliers:
        docs, outlier_stats = apply_outlier_filter(coll, docs)
        print(
            f"   🧹 Outliers filtrados: {outlier_stats['outliers_detected']} "
            f"de {outlier_stats['checked']} valores comprobados."
        )
    else:
        outlier_stats = {"outliers_detected": 0, "checked": 0}

    client.close()

    stats = upsert_to_mongo(docs)
    print(f"   🟢 Mongo upsert → insertados={stats['inserted']}  actualizados={stats['modified']}")

    return {
        "raw": len(rows),
        "parsed": len(docs),
        "canonical_v2": canonical_count,
        "by_province": dict(by_province),
        **outlier_stats,
        **stats,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Ingesta oficial RVVCCA (GVA) → MongoDB Atlas",
    )
    p.add_argument("--csv", help="Ruta a CSV local (en vez de descargar)")
    p.add_argument("--url", help="URL alternativa del WFS (override env)")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Parsea y reporta, pero no toca MongoDB.",
    )
    p.add_argument(
        "--no-outliers",
        action="store_true",
        help="Desactiva el filtro de outliers (útil para depurar histórico).",
    )
    p.add_argument(
        "--create-ts",
        action="store_true",
        help="Crea la colección Time Series 'aire_realtime_ts' si no existe y sale.",
    )
    return p


def main() -> int:
    args = _build_argparser().parse_args()

    print("\n" + "=" * 68)
    print("🏛️  AirVLC — Ingesta RVVCCA Generalitat Valenciana (Sprint 8)")
    print("=" * 68)

    if args.create_ts:
        out = ensure_timeseries_collection()
        print(f"\n🎯 Time series collection: {out}")
        return 0

    try:
        result = fetch_gva_rvvcca(
            csv_path=args.csv,
            url=args.url,
            dry_run=args.dry_run,
            apply_outliers=not args.no_outliers,
        )
    except requests.RequestException as e:
        print(f"\n❌ Error de red al consultar GVA: {e}")
        return 2
    except Exception as e:  # pragma: no cover
        print(f"\n❌ Error inesperado: {e}")
        return 3

    print(f"\n🎯 Resultado: {result}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
