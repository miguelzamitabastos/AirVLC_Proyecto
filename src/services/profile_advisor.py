"""
Profile Advisor — combina el output multitarget de RiskClassifierV2 con el
perfil de salud del usuario (edad, condición, sensibilidad, actividad) para
producir un texto de recomendación humanizado.

Diseño:
- **Stateless**: no persiste nada. El backend nunca guarda datos personales.
- **Fail-safe**: si el `profile` viene vacío o inválido, devuelve la
  recomendación genérica (la que ya viene de `RiskClassifierV2.classify_multi`).
- **Sin ML adicional**: solo reglas heurísticas sobre los thresholds existentes,
  ajustando el nivel de cada contaminante para perfiles sensibles.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from src.ml.risk_classifier_v2 import POLLUTANT_THRESHOLDS, LEVEL_ORDER
from src.ml.risk_classifier import RISK_LEVELS


SENSITIVE_CONDITIONS = {"asma", "epoc", "embarazada", "cardiopatía", "cardiopatia"}
HIGH_AGE_RANGES = {"niño", "nino", "mayor", "mayor de 65", "mayor_65", ">65"}

ACTIVITY_LABELS = {
    "correr": "salir a correr",
    "running": "salir a correr",
    "pasear": "pasear",
    "andar": "pasear",
    "caminar": "pasear",
    "pasear al perro": "pasear al perro",
    "ir en bici": "salir en bicicleta",
    "bicicleta": "salir en bicicleta",
    "quedarme en casa": "quedarte en casa",
    "salir": "salir a la calle",
}

LEVEL_TO_COLOR_HEX = {
    "bueno": "#2BB673",      # verde
    "moderado": "#F2C744",   # amarillo
    "malo": "#F4A300",       # naranja
    "peligroso": "#D62828",  # rojo
}


@dataclass(frozen=True)
class HealthProfile:
    age: str = "adulto"
    condition: str = "sano"
    sensitivity: str = "media"
    activity: Optional[str] = None

    @classmethod
    def from_dict(cls, raw: Optional[Dict]) -> "HealthProfile":
        if not isinstance(raw, dict):
            return cls()
        return cls(
            age=str(raw.get("age", "adulto")).strip().lower(),
            condition=str(raw.get("condition", "sano")).strip().lower(),
            sensitivity=str(raw.get("sensitivity", "media")).strip().lower(),
            activity=(str(raw["activity"]).strip().lower() if raw.get("activity") else None),
        )

    @property
    def is_sensitive(self) -> bool:
        if self.condition in SENSITIVE_CONDITIONS:
            return True
        if self.sensitivity == "alta":
            return True
        if self.age in HIGH_AGE_RANGES:
            return True
        return False


def _adjust_level_for_profile(level: str, profile: HealthProfile) -> str:
    """Si el perfil es sensible, sube un escalón (max peligroso) la severidad."""
    if not profile.is_sensitive:
        return level
    order = LEVEL_ORDER.get(level, 0)
    levels_inv = {v: k for k, v in LEVEL_ORDER.items()}
    return levels_inv.get(min(order + 1, 3), level)


def adjusted_pollutant_thresholds(profile: HealthProfile) -> Dict[str, Dict[str, float]]:
    """Devuelve los thresholds ICA con un buffer del 20% si el perfil es sensible.
    La app puede pedir esto para colorear umbrales personalizados, pero el
    backend ya lo aplica internamente al producir el `recommendation_text`.
    """
    if not profile.is_sensitive:
        return {k: dict(v) for k, v in POLLUTANT_THRESHOLDS.items()}
    out: Dict[str, Dict[str, float]] = {}
    for pol, thr in POLLUTANT_THRESHOLDS.items():
        out[pol] = {k: round(float(v) * 0.8, 2) for k, v in thr.items()}
    return out


def _activity_phrase(activity: Optional[str]) -> Optional[str]:
    if not activity:
        return None
    return ACTIVITY_LABELS.get(activity.strip().lower(), activity.strip().lower())


def _profile_intro(profile: HealthProfile) -> str:
    chunks = []
    if profile.condition not in {"", "sano"}:
        chunks.append(f"con {profile.condition}")
    if profile.sensitivity == "alta":
        chunks.append("sensibilidad alta")
    if profile.age in HIGH_AGE_RANGES:
        chunks.append("perfil de edad sensible")
    if not chunks:
        return "Para tu perfil"
    return "Con " + ", ".join(chunks)


def _pretty_pollutant(p: str) -> str:
    return {"pm25": "PM2.5", "no2": "NO₂", "o3": "O₃"}.get(p, p.upper())


def build_recommendation(
    risk_payload: Dict,
    profile: Optional[Dict] = None,
    activity: Optional[str] = None,
) -> Dict:
    """
    Toma la salida de `RiskClassifierV2.classify_multi(...)` y un dict de perfil
    y devuelve un dict con:
        - recommendation_text (str, ya humanizado y adaptado)
        - color (str hex)
        - level_adjusted (str, peor nivel tras ajuste por perfil sensible)
    Si el perfil es vacío/None, conserva el `reply_text` genérico.
    """
    hp = HealthProfile.from_dict(profile)
    if activity and not hp.activity:
        hp = HealthProfile(
            age=hp.age, condition=hp.condition, sensitivity=hp.sensitivity, activity=activity.strip().lower()
        )

    worst = risk_payload.get("worst", {}) or {}
    worst_level = worst.get("level", "bueno")
    worst_pollutant = worst.get("pollutant", "pm25")
    worst_value = worst.get("value")
    station = risk_payload.get("station") or "esta estación"

    adjusted_level = _adjust_level_for_profile(worst_level, hp)
    color = LEVEL_TO_COLOR_HEX.get(adjusted_level, "#2BB673")

    activity_phrase = _activity_phrase(hp.activity)
    intro = _profile_intro(hp)

    if adjusted_level == "bueno":
        action = (
            f"puedes {activity_phrase} con tranquilidad" if activity_phrase
            else "es un buen momento para actividades al aire libre"
        )
        reason = "la calidad del aire es buena en los 3 contaminantes"
    elif adjusted_level == "moderado":
        action = (
            f"puedes {activity_phrase} pero modera la intensidad"
            if activity_phrase
            else "modera la actividad al aire libre"
        )
        reason = (
            f"el {_pretty_pollutant(worst_pollutant)} está en moderado"
            f"{f' ({worst_value:.1f} µg/m³)' if isinstance(worst_value,(int,float)) else ''}"
        )
    elif adjusted_level == "malo":
        action = (
            f"evita {activity_phrase} al aire libre"
            if activity_phrase
            else "evita el ejercicio al aire libre"
        )
        reason = (
            f"el {_pretty_pollutant(worst_pollutant)} está en malo"
            f"{f' ({worst_value:.1f} µg/m³)' if isinstance(worst_value,(int,float)) else ''}"
        )
    else:  # peligroso
        action = (
            "quédate en casa con ventanas cerradas"
            if not activity_phrase or activity_phrase == "quedarte en casa"
            else f"NO {activity_phrase} hoy y mantente en interiores"
        )
        reason = (
            f"el {_pretty_pollutant(worst_pollutant)} está en peligroso"
            f"{f' ({worst_value:.1f} µg/m³)' if isinstance(worst_value,(int,float)) else ''}"
        )

    text = f"{intro} en {station}, {action}: {reason}."

    return {
        "recommendation_text": text,
        "color": color,
        "level_adjusted": adjusted_level,
        "is_sensitive_profile": hp.is_sensitive,
        "profile_used": {
            "age": hp.age,
            "condition": hp.condition,
            "sensitivity": hp.sensitivity,
            "activity": hp.activity,
        },
        "level_description": RISK_LEVELS.get(adjusted_level, {}).get("description"),
    }
