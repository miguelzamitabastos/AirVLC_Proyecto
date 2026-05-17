#!/usr/bin/env python3
"""
Bootstrap WAQI window (Sprint 6.1)
=================================

Problema:
  El modelo v2 necesita una ventana de 24 pasos con lags/rolling (lag24, rolling_24h).
  Si el CSV v2 está muy atrás en el tiempo (p.ej. 2023) y empezamos a ingerir WAQI
  en 2026, el append puede quedarse sin filas completas para lags si no existe un
  histórico horario continuo "reciente".

Solución:
  Este script genera 48 filas por estación (últimas 48 horas) a partir del valor
  actual de WAQI, como "warm-up" para habilitar lags/rolling hoy mismo.

  Las filas se insertan en Mongo `airvlc_db.aire_realtime` con:
    - source = "waqi_bootstrap"
    - is_synthetic = True

Uso:
  ./venv/bin/python src/scripts/bootstrap_waqi_window.py --hours 48

Notas:
  - Esto NO es reentrenamiento; solo warm-start del input.
  - Si prefieres 100% truthful, no uses este script y espera 24h para acumular puntos reales.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)
load_dotenv(os.path.join(ROOT_DIR, ".env"))

from src.ingestion.waqi_air_quality_client import CANONICAL_STATIONS, fetch_station_payload, build_document


def bootstrap(hours: int = 48) -> dict:
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise RuntimeError("MONGO_URI no configurado")

    client = MongoClient(mongo_uri)
    db = client["airvlc_db"]
    coll = db["aire_realtime"]

    coll.create_index(
        [("estacion", 1), ("fecha_iso", 1)],
        unique=True,
        name="idx_estacion_fecha_unique",
        background=True,
    )

    ops = []
    raw_ok = 0
    docs = 0

    for station in CANONICAL_STATIONS:
        data = fetch_station_payload(station)
        if not data:
            continue
        raw_ok += 1

        # Documento base (usa el timestamp WAQI actual)
        base = build_document(station, data, hours=24 * 365 * 10)  # no filtrar por antigüedad aquí
        if not base:
            continue

        # Tomar la hora actual (redondeada) como final de la ventana
        end = base["fecha"]
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        end = end.replace(minute=0, second=0, microsecond=0)

        for k in range(hours):
            ts = end - timedelta(hours=(hours - 1 - k))
            doc = dict(base)
            doc["fecha"] = ts
            doc["fecha_iso"] = ts.isoformat()
            doc["ingested_at"] = datetime.utcnow().isoformat()
            doc["source"] = "waqi_bootstrap"
            doc["is_synthetic"] = True
            ops.append(
                UpdateOne(
                    {"estacion": doc["estacion"], "fecha_iso": doc["fecha_iso"]},
                    {"$set": doc},
                    upsert=True,
                )
            )
            docs += 1

    if not ops:
        client.close()
        return {"stations_ok": raw_ok, "docs": 0, "inserted": 0, "modified": 0}

    result = coll.bulk_write(ops, ordered=False)
    client.close()

    return {
        "stations_ok": raw_ok,
        "docs": docs,
        "inserted": result.upserted_count,
        "modified": result.modified_count,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--hours", type=int, default=48, help="Horas a bootstrappear por estación (default 48)")
    args = p.parse_args()

    out = bootstrap(hours=args.hours)
    print(out)

