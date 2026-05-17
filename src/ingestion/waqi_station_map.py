"""
Mapeo opcional estación AirVLC -> uid WAQI (@uid en api.waqi.info).

**Uso en producción:** WAQI solo como fallback para estaciones que la GVA no
publica en RVVCCA (ver ``WAQI_FALLBACK_STATIONS``). Las otras 6 canónicas
siguen con ingesta GVA exclusivamente.

Por defecto vacío: el cliente usa ``feed/geo:lat;lon`` con coordenadas de
``src.api.es_indexer.STATION_COORDS``.

Tras ejecutar ``python src/scripts/discover_waqi_stations.py``, puedes pegar aquí
los ``uid`` recomendados para forzar una estación concreta en lugar del vecino
más cercano por geo.

Ejemplo:
    WAQI_STATION_UID_OVERRIDE = {
        "Puerto Valencia": 12345,
    }
"""

from __future__ import annotations

# Estaciones v2 sin fila propia en el WFS RVVCCA.
WAQI_FALLBACK_STATIONS: frozenset[str] = frozenset({"Puerto Valencia"})

# Proxy espacial GVA (preferido): estación oficial GVA muy cercana.
GVA_SPATIAL_PROXY_FOR: dict[str, str] = {
    "Puerto Valencia": "Puerto Moll Trans. Ponent",
}
GVA_SPATIAL_PROXY_LABEL: dict[str, str] = {
    "Puerto Valencia": "Puerto Moll Trans. Ponent (GVA oficial, ~300 m)",
}

# Puerto Valencia no tiene estación propia en WAQI ni en GVA.
# El feed geo:lat;lon de WAQI devuelve sensores incorrectos (p. ej. Murcia);
# usamos el UID oficial más cercano en la red valenciana: Av. França (GVA).
WAQI_STATION_PROXY_LABEL: dict[str, str] = {
    "Puerto Valencia": "Avd. Francia, València (proxy WAQI ~2.4 km)",
}

# type: dict[str, int]
WAQI_STATION_UID_OVERRIDE: dict[str, int] = {
    "Puerto Valencia": 6639,
}
