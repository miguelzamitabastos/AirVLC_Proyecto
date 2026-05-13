"""Encontrar estaciones WAQI reales en/alrededor de Valencia.

Estrategia:
  1) /map/bounds con varios bboxes (algunos tokens devuelven [] si el bbox es muy pequeño).
  2) /search?keyword=Valencia para listar candidatos por nombre.
  3) Para cada candidato, calcular distancia a las coords canónicas y proponer el UID más cercano.
"""

import json
import math
import os
import re
import sys
import urllib.parse
import urllib.request


def load_env_token() -> str:
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("WAQI_TOKEN="):
                m = re.match(r'WAQI_TOKEN\s*=\s*"?([^"\s#]+)"?', line.strip())
                if m:
                    return m.group(1)
    raise RuntimeError("No WAQI_TOKEN in .env")


def http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "airvlc-debug/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


CANONICAL = [
    ("Francia", 39.4578, -0.343),
    ("Molí del Sol", 39.4811, -0.4088),
    ("Pista de Silla", 39.4581, -0.3766),
    ("Puerto Moll Trans. Ponent", 39.4536, -0.3137),
    ("Puerto Valencia", 39.4484, -0.3172),
    ("Puerto llit antic Túria", 39.4661, -0.3306),
    ("Universidad Politécnica", 39.4796, -0.3374),
]


def main() -> None:
    token = load_env_token()
    base = "https://api.waqi.info"

    # 1) map/bounds con varios bboxes
    bboxes = [
        ("ciudad estrecha", "39.40,-0.45,39.55,-0.30"),
        ("ciudad amplia", "39.30,-0.55,39.60,-0.20"),
        ("CV/Valencia + costa", "39.10,-0.70,39.80,-0.10"),
        ("CV completa", "37.80,-1.70,40.80,0.50"),
    ]
    all_stations: dict[int, dict] = {}
    for label, bbox in bboxes:
        url = f"{base}/map/bounds/?latlng={urllib.parse.quote(bbox)}&token={token}"
        try:
            body = http_get_json(url)
        except Exception as e:
            print(f"[bounds {label}] ERROR {e}")
            continue
        if body.get("status") != "ok":
            print(f"[bounds {label}] status={body.get('status')} data={body.get('data')}")
            continue
        data = body.get("data") or []
        print(f"[bounds {label}] {len(data)} estaciones")
        for st in data:
            uid = st.get("uid")
            if not uid:
                continue
            all_stations[uid] = st

    # 2) search por nombre
    for kw in ("Valencia", "Politecnica", "Puerto Valencia", "Pista de Silla"):
        url = f"{base}/search/?keyword={urllib.parse.quote(kw)}&token={token}"
        try:
            body = http_get_json(url)
        except Exception as e:
            print(f"[search {kw}] ERROR {e}")
            continue
        if body.get("status") != "ok":
            print(f"[search {kw}] status={body.get('status')}")
            continue
        data = body.get("data") or []
        print(f"[search '{kw}'] {len(data)} resultados")
        for st in data:
            uid = (st.get("station") or {}).get("url") or st.get("uid")
            real_uid = st.get("uid")
            station_obj = st.get("station") or {}
            geo = station_obj.get("geo") or []
            name = station_obj.get("name") or ""
            if not real_uid:
                continue
            # WAQI search returns uid in top level; geo in station.geo (sometimes)
            if not geo and "lat" in st:
                geo = [st["lat"], st["lon"]]
            all_stations[real_uid] = {
                "uid": real_uid,
                "lat": geo[0] if geo else None,
                "lon": geo[1] if len(geo) > 1 else None,
                "station": {"name": name},
            }
            print(f"   uid={real_uid} name='{name}' geo={geo}")

    # 3) emparejar a cada estación canónica el UID más cercano
    print("\n=========== Emparejamiento con coords canónicas ===========")
    print(f"{'AirVLC station':<32} {'uid':>8} {'km':>7}  WAQI name")
    print("-" * 92)
    suggestions = []
    for name, lat0, lon0 in CANONICAL:
        best = None
        best_km = 1e9
        for uid, st in all_stations.items():
            lat = st.get("lat")
            lon = st.get("lon")
            if lat is None or lon is None:
                continue
            km = haversine_km(lat0, lon0, float(lat), float(lon))
            if km < best_km:
                best_km = km
                wname = ((st.get("station") or {}).get("name")) or ""
                best = (uid, wname, lat, lon, km)
        if best:
            uid, wname, lat, lon, km = best
            print(f"{name:<32} {uid:>8} {km:>7.2f}  {wname[:60]}")
            suggestions.append((name, uid, wname, km))
        else:
            print(f"{name:<32} {'(none)':>8}")

    print("\n# Sugerencia para WAQI_STATION_UID_OVERRIDE:\n")
    print("WAQI_STATION_UID_OVERRIDE = {")
    for name, uid, wname, km in suggestions:
        wname_safe = wname.replace("\\", "/")
        print(f'    "{name}": {uid},  # {km:.2f} km — {wname_safe[:60]}')
    print("}")


if __name__ == "__main__":
    main()
