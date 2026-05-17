"""
Risk Classifier v2 — Multicontaminante (PM2.5, NO2, O3) con criterio ICA:
devuelve el peor nivel entre los tres (estándar ICA-like).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from src.ml.risk_classifier import RISK_LEVELS


POLLUTANT_THRESHOLDS = {
    # µg/m³
    "pm25": {"bueno": 12.0, "moderado": 35.4, "malo": 55.4},
    # NO2 (1h)
    "no2": {"bueno": 50.0, "moderado": 100.0, "malo": 200.0},
    # O3 (1h)
    "o3": {"bueno": 100.0, "moderado": 160.0, "malo": 240.0},
}


LEVEL_ORDER = {"bueno": 0, "moderado": 1, "malo": 2, "peligroso": 3}


@dataclass(frozen=True)
class PollutantResult:
    pollutant: str
    value: float
    level: str
    color: str
    emoji: str


class RiskClassifierV2:
    def __init__(self):
        self.levels = RISK_LEVELS

    def classify_multi(self, pm25: float, no2: float, o3: float, station: Optional[str] = None) -> Dict:
        pollutants: Dict[str, Dict] = {}
        results = [
            self._classify_one("pm25", float(pm25)),
            self._classify_one("no2", float(no2)),
            self._classify_one("o3", float(o3)),
        ]

        for r in results:
            pollutants[r.pollutant] = {
                "value": round(r.value, 2),
                "unit": "µg/m³",
                "level": r.level,
                "color": r.color,
                "emoji": r.emoji,
                "description": self.levels[r.level]["description"],
                "recommendation": self.levels[r.level]["recommendation"],
            }

        worst = max(results, key=lambda r: LEVEL_ORDER.get(r.level, -1))
        worst_payload = {
            "pollutant": worst.pollutant,
            "value": round(worst.value, 2),
            "unit": "µg/m³",
            "level": worst.level,
            "color": worst.color,
            "emoji": worst.emoji,
        }

        station_str = f" en {station}" if station else ""
        reply_text = (
            f"El ICA{station_str} es {worst.level.upper()} por {self._pretty_name(worst.pollutant)} "
            f"({worst.value:.1f} µg/m³). "
            f"PM2.5: {pm25:.1f} · NO₂: {no2:.1f} · O₃: {o3:.1f} µg/m³."
        )

        return {
            "pollutants": pollutants,
            "worst": worst_payload,
            "reply_text": reply_text,
            "station": station,
        }

    def _classify_one(self, pollutant: str, value: float) -> PollutantResult:
        thr = POLLUTANT_THRESHOLDS[pollutant]
        if value <= thr["bueno"]:
            level = "bueno"
        elif value <= thr["moderado"]:
            level = "moderado"
        elif value <= thr["malo"]:
            level = "malo"
        else:
            level = "peligroso"

        info = self.levels[level]
        return PollutantResult(
            pollutant=pollutant,
            value=value,
            level=level,
            color=info["color"],
            emoji=info["emoji"],
        )

    def _pretty_name(self, pollutant: str) -> str:
        return {"pm25": "PM2.5", "no2": "NO₂", "o3": "O₃"}.get(pollutant, pollutant.upper())

