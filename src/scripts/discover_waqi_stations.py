#!/usr/bin/env python3
"""
Descubre estaciones WAQI cercanas a las coordenadas del modelo v2 y sugiere
un bloque Python para `src/ingestion/waqi_station_map.py`.

Requiere WAQI_TOKEN en .env

Uso:
    ./venv/bin/python src/scripts/discover_waqi_stations.py
"""

from __future__ import annotations

import math
import os
import sys

import requests
from dotenv import load_dotenv

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)
load_dotenv(os.path.join(ROOT_DIR, ".env"))

from src.api.es_indexer import STATION_COORDS

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


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def fetch_bbox_stations(token: str) -> list[dict]:
    """Estaciones dentro del bbox Valencia."""
    # lat1,lon1,lat2,lon2
    url = f"{WAQI_BASE}/map/bounds/"
    params = {
        "latlng": "39.40,-0.52,39.58,-0.28",
        "token": token,
    }
    r = requests.get(url, params=params, timeout=45)
    r.raise_for_status()
    body = r.json()
    if body.get("status") != "ok":
        raise RuntimeError(f"WAQI map/bounds error: {body}")
    return body.get("data") or []


def main() -> None:
    token = os.getenv("WAQI_TOKEN", "").strip()
    if not token:
        print("❌ Define WAQI_TOKEN en .env")
        sys.exit(1)

    stations = fetch_bbox_stations(token)
    print(f"✅ Estaciones en bbox: {len(stations)}\n")

    print(f"{'AirVLC station':<32} {'nearest uid':>12} {'km':>8} {'WAQI name'}")
    print("-" * 90)

    lines = []
    for name in CANONICAL_STATIONS:
        c = STATION_COORDS.get(name)
        if not c:
            print(f"{name:<32} {'MISSING_COORDS':>12}")
            continue
        lat0, lon0 = c["lat"], c["lon"]

        best = None
        best_km = 1e9
        for st in stations:
            lat = st.get("lat")
            lon = st.get("lon")
            geo = st.get("geo")
            if (lat is None or lon is None) and isinstance(geo, (list, tuple)) and len(geo) >= 2:
                lat, lon = geo[0], geo[1]
            uid = st.get("uid")
            if lat is None or lon is None or uid is None:
                continue
            km = haversine_km(lat0, lon0, float(lat), float(lon))
            if km < best_km:
                best_km = km
                stn = st.get("station")
                wname = stn.get("name") if isinstance(stn, dict) else None
                best = (uid, wname, lat, lon)

        if best:
            uid, wname, _, _ = best
            wname = wname or ""
            print(f"{name:<32} {uid:>12} {best_km:>8.2f} {wname}")
            lines.append(f'    "{name}": {uid},  # ~{best_km:.2f} km')
        else:
            print(f"{name:<32} {'(none)':>12}")

    print("\n# Copiar a waqi_station_map.py como WAQI_STATION_UID_OVERRIDE:\n")
    print("WAQI_STATION_UID_OVERRIDE = {")
    for line in lines:
        print(line)
    print("}")


if __name__ == "__main__":
    main()
