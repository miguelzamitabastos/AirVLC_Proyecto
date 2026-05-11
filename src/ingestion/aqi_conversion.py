"""
US EPA AQI sub-index -> concentración física (Sprint 6).

Interpola linealmente entre puntos de ruptura (AQI, concentración) sin huecos.

PM2.5: µg/m³ (24h mean)
NO2: ppb (1h) -> µg/m³ con * 1.88
O3: ppb (8h) -> µg/m³ con * 1.96
"""

from __future__ import annotations

# Puntos de ruptura EPA: lista de (AQI, concentración en unidad nativa)
_PM25_I_C = [
    (0, 0.0),
    (50, 12.0),
    (100, 35.4),
    (150, 55.4),
    (200, 150.4),
    (300, 250.4),
    (400, 350.4),
    (500, 500.4),
]

_NO2_I_PPB = [
    (0, 0),
    (50, 53),
    (100, 100),
    (150, 360),
    (200, 649),
    (300, 1249),
    (400, 1649),
    (500, 2049),
]

_O3_I_PPB = [
    (0, 0),
    (50, 54),
    (100, 70),
    (150, 85),
    (200, 105),
    (300, 200),
]


def _interp_piecewise(aqi: float, breakpoints: list[tuple[float, float]]) -> float | None:
    if aqi is None:
        return None
    try:
        a = float(aqi)
    except (TypeError, ValueError):
        return None
    if a < 0:
        return None
    if a > 500:
        (i0, c0), (i1, c1) = breakpoints[-2], breakpoints[-1]
        if i1 == i0:
            return float(c1)
        return float(c1 + (c1 - c0) / (i1 - i0) * (a - i1))

    for j in range(len(breakpoints) - 1):
        i0, c0 = breakpoints[j]
        i1, c1 = breakpoints[j + 1]
        if i0 <= a <= i1:
            if i1 == i0:
                return float(c0)
            return float(c0 + (c1 - c0) / (i1 - i0) * (a - i0))

    # Por encima del último punto pero <= 500: extrapolar último tramo
    if breakpoints and a > breakpoints[-1][0]:
        (i0, c0), (i1, c1) = breakpoints[-2], breakpoints[-1]
        if i1 != i0:
            return float(c1 + (c1 - c0) / (i1 - i0) * (a - i1))
        return float(c1)
    return None


def pm25_subindex_to_ugm3(subindex: float | None) -> float | None:
    return _interp_piecewise(subindex, _PM25_I_C)


def no2_subindex_to_ugm3(subindex: float | None) -> float | None:
    ppb = _interp_piecewise(subindex, _NO2_I_PPB)
    if ppb is None:
        return None
    return ppb * 1.88


def o3_subindex_to_ugm3(subindex: float | None) -> float | None:
    ppb = _interp_piecewise(subindex, _O3_I_PPB)
    if ppb is None:
        return None
    return ppb * 1.96
