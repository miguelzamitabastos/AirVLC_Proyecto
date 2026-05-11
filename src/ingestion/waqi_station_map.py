"""
Mapeo opcional estación AirVLC -> uid WAQI (@uid en api.waqi.info).

Por defecto vacío: el cliente usa `feed/geo:lat;lon` con coordenadas de
`src.api.es_indexer.STATION_COORDS`.

Tras ejecutar `python src/scripts/discover_waqi_stations.py`, puedes pegar aquí
los `uid` recomendados para forzar una estación concreta en lugar del vecino
más cercano por geo.

Ejemplo:
    WAQI_STATION_UID_OVERRIDE = {
        "Francia": 6759,
        "Universidad Politécnica": 13989,
    }
"""

from __future__ import annotations

# type: dict[str, int]
WAQI_STATION_UID_OVERRIDE: dict[str, int] = {}
