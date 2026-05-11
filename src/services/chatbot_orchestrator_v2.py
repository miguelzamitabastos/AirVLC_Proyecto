import logging
import os
import sys
import numpy as np

from .aws.lex_service import LexService

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.api.feature_extractor_v2 import FeatureExtractorV2
from src.ml.risk_classifier_v2 import LEVEL_ORDER, RiskClassifierV2
from src.services.profile_advisor import build_recommendation


PRETTY_POLLUTANT = {"pm25": "PM2.5", "no2": "NO₂", "o3": "O₃"}


def _slot_value(slots, name):
    """Extrae el valor textual de un slot Lex (interpretedValue o originalValue)."""
    if not slots or name not in slots or slots[name] is None:
        return None
    val = slots[name].get("value", {}) or {}
    return val.get("interpretedValue") or val.get("originalValue")


class ChatbotOrchestratorV2:
    """
    Orquesta el flujo entre el usuario (App), AWS Lex y nuestros Modelos v2 (multitarget).
    Soporta 6 intents: ConsultarCalidad, ConsultarContaminante, CompararEstaciones,
    ConsejoSalud, VerMapaRiesgo, PrevisionRiesgo.

    Sprint 7: todas las respuestas incluyen `ui_payload` para que Flutter
    pueda navegar automáticamente a la pantalla correspondiente.
    """

    def __init__(self, bot_id=None, bot_alias_id=None, locale_id="es_ES"):
        self.lex_service = LexService()
        self.risk_classifier = RiskClassifierV2()
        self.bot_id = bot_id or os.environ.get("LEX_BOT_ID", "DUMMY_BOT_ID")
        self.bot_alias_id = bot_alias_id or os.environ.get("LEX_BOT_ALIAS_ID", "TSTALIASID")
        self.locale_id = locale_id
        if not self.bot_id or self.bot_id == "DUMMY_BOT_ID":
            logger.warning(
                "LEX_BOT_ID no está definido (o es DUMMY). Configura LEX_BOT_ID y "
                "LEX_BOT_ALIAS_ID en .env en la raíz del proyecto."
            )
        # FeatureExtractorV2 carga dataset+scaler al instanciarse; lo creamos perezosamente.
        self._extractor = None

    def _get_extractor(self):
        if self._extractor is None:
            self._extractor = FeatureExtractorV2()
        return self._extractor

    def process_message(self, text, session_id, model_loader=None):
        try:
            lex_response = self.lex_service.recognize_text(
                bot_id=self.bot_id,
                bot_alias_id=self.bot_alias_id,
                locale_id=self.locale_id,
                text=text,
                session_id=session_id,
            )
        except Exception as e:
            logger.warning(
                "Lex recognize_text falló (bot_id=%s alias=%s locale=%s): %s",
                self.bot_id,
                self.bot_alias_id,
                self.locale_id,
                e,
                exc_info=True,
            )
            return {
                "reply": "Lo siento, tengo problemas conectando con mi motor NLU en AWS.",
                "intent": "Error",
                "error": str(e),
            }

        interpretations = lex_response.get("interpretations", [])
        if not interpretations:
            return {"reply": "No he entendido tu mensaje.", "intent": "FallbackIntent"}

        top_intent = interpretations[0].get("intent", {})
        intent_name = top_intent.get("name", "FallbackIntent")
        slots = top_intent.get("slots", {})

        # Heurística anti-confusión: a veces Lex confunde consultas del tipo
        # "cómo está la calidad en X" con `CompararEstaciones` si detecta solo
        # una estación. Si pasa, degradamos a `ConsultarCalidad`.
        if intent_name == "CompararEstaciones":
            a = _slot_value(slots, "EstacionA")
            b = _slot_value(slots, "EstacionB")
            looks_like_quality_query = "calidad" in (text or "").lower()
            # Si solo hay 0–1 estaciones, es casi seguro que es una consulta simple.
            if looks_like_quality_query and not (a and b):
                # Si Lex no rellenó slots, intentamos deducir estación del texto.
                guessed = a or b
                if not guessed:
                    t = (text or "").lower()
                    candidates = [
                        "Francia",
                        "Molí del Sol",
                        "Pista de Silla",
                        "Puerto Moll Trans. Ponent",
                        "Puerto Valencia",
                        "Puerto llit antic Túria",
                        "Universidad Politécnica",
                    ]
                    aliases = {
                        "politecnico": "Universidad Politécnica",
                        "politécnico": "Universidad Politécnica",
                        "upv": "Universidad Politécnica",
                        "moli del sol": "Molí del Sol",
                        "molí del sol": "Molí del Sol",
                        "pista silla": "Pista de Silla",
                        "pista de silla": "Pista de Silla",
                        "puerto moll": "Puerto Moll Trans. Ponent",
                        "puerto turia": "Puerto llit antic Túria",
                        "puerto túria": "Puerto llit antic Túria",
                    }
                    for c in candidates:
                        if c.lower() in t:
                            guessed = c
                            break
                    if not guessed:
                        for k, v in aliases.items():
                            if k in t:
                                guessed = v
                                break

                if guessed:
                    intent_name = "ConsultarCalidad"
                    slots = {
                        "Estacion": {
                            "value": {
                                "interpretedValue": guessed,
                                "originalValue": guessed,
                            }
                        }
                    }

        if intent_name == "ConsultarCalidad":
            return self._handle_consultar_calidad(slots, model_loader)
        if intent_name == "ConsultarContaminante":
            return self._handle_consultar_contaminante(slots, model_loader)
        if intent_name == "CompararEstaciones":
            return self._handle_comparar_estaciones(slots, model_loader)
        if intent_name == "ConsejoSalud":
            return self._handle_consejo_salud(slots, model_loader, profile=None)
        # --- Sprint 7: nuevos intents ---
        if intent_name == "VerMapaRiesgo":
            return self._handle_ver_mapa_riesgo(slots)
        if intent_name == "PrevisionRiesgo":
            return self._handle_prevision_riesgo(slots, model_loader)
        if intent_name == "TopPeoresEstaciones":
            return self._handle_top_peores_estaciones(slots, model_loader)

        return {
            "reply": "Todavía no estoy entrenado para responder a esa pregunta.",
            "intent": intent_name,
            "ui_payload": None,
        }

    # --------- helpers de inferencia ---------

    def _infer(self, station_name, model_loader, offset_hours=0):
        if not model_loader or not getattr(model_loader, "is_ready", False):
            raise RuntimeError("ModelLoader not ready")
        extractor = self._get_extractor()
        # Normalizar nombre de estación para que coincida con las 7 canónicas v2.
        # Reutiliza el mismo resolver que la API v2.
        try:
            from src.api.routes_v2 import _resolve_station as _rs
            station_name = _rs(station_name) or station_name
        except Exception:
            pass

        features, real_station, meta = extractor.get_features(station_name, offset_hours=offset_hours)
        prediction_scaled = model_loader.predict(np.array(features), model_name="LSTM_Attention_Multi")
        preds = extractor.inverse_transform_predictions(prediction_scaled)
        risk_payload = self.risk_classifier.classify_multi(
            pm25=preds["pm25"], no2=preds["no2"], o3=preds["o3"], station=real_station,
        )
        return real_station, preds, risk_payload, meta

    # --------- intents ---------

    def _handle_consultar_calidad(self, slots, model_loader):
        estacion = _slot_value(slots, "Estacion")
        if not estacion:
            return {
                "reply": "¿Para qué estación quieres consultar la calidad del aire? (ej: Politécnico, Viveros...)",
                "intent": "ConsultarCalidad",
                "missing_slot": "Estacion",
                "ui_payload": None,
            }

        try:
            real_station, preds, risk_payload, _ = self._infer(estacion, model_loader)
            return {
                "reply": risk_payload["reply_text"],
                "intent": "ConsultarCalidad",
                "station": real_station,
                "predictions": {"unit": "µg/m³", **{k: round(v, 2) for k, v in preds.items()}},
                "pollutants": risk_payload["pollutants"],
                "worst": risk_payload["worst"],
                "ui_payload": {
                    "action": "open_station_detail",
                    "station": real_station,
                    "pollutant": risk_payload["worst"]["pollutant"],
                    "horizon": "now",
                },
            }
        except Exception as e:
            return {
                "reply": f"Ha ocurrido un error al calcular la predicción para {estacion}.",
                "intent": "ConsultarCalidad",
                "error": str(e),
                "ui_payload": None,
            }

    def _handle_consultar_contaminante(self, slots, model_loader):
        estacion = _slot_value(slots, "Estacion")
        contaminante_raw = _slot_value(slots, "Contaminante")
        if not estacion or not contaminante_raw:
            missing = []
            if not estacion:
                missing.append("Estacion")
            if not contaminante_raw:
                missing.append("Contaminante")
            return {
                "reply": "Necesito saber estación y contaminante (PM2.5, NO₂ u O₃).",
                "intent": "ConsultarContaminante",
                "missing_slots": missing,
                "ui_payload": None,
            }

        # Normalización del contaminante a las 3 keys del modelo
        norm = contaminante_raw.strip().lower().replace(" ", "").replace(".", "").replace("₂", "2").replace("₃", "3")
        mapping = {
            "pm25": "pm25", "pm2.5": "pm25", "particulas": "pm25", "partículas": "pm25",
            "no2": "no2", "dioxidodenitrogeno": "no2", "nitrogeno": "no2",
            "o3": "o3", "ozono": "o3",
        }
        pollutant = mapping.get(norm)
        if not pollutant:
            return {
                "reply": f"No reconozco el contaminante '{contaminante_raw}'. Usa PM2.5, NO₂ u O₃.",
                "intent": "ConsultarContaminante",
                "ui_payload": None,
            }

        try:
            real_station, preds, risk_payload, _ = self._infer(estacion, model_loader)
            info = risk_payload["pollutants"][pollutant]
            pretty = PRETTY_POLLUTANT[pollutant]
            reply = (
                f"El {pretty} en {real_station} está {info['level'].upper()} "
                f"({info['value']:.1f} µg/m³). {info['recommendation']}"
            )
            return {
                "reply": reply,
                "intent": "ConsultarContaminante",
                "station": real_station,
                "pollutant": pollutant,
                "value": info["value"],
                "level": info["level"],
                "color": info["color"],
                "predictions": {"unit": "µg/m³", **{k: round(v, 2) for k, v in preds.items()}},
                "ui_payload": {
                    "action": "open_station_detail",
                    "station": real_station,
                    "pollutant": pollutant,
                    "horizon": "now",
                },
            }
        except Exception as e:
            return {
                "reply": f"Ha ocurrido un error al calcular la predicción para {estacion}.",
                "intent": "ConsultarContaminante",
                "error": str(e),
                "ui_payload": None,
            }

    def _handle_comparar_estaciones(self, slots, model_loader):
        a = _slot_value(slots, "EstacionA")
        b = _slot_value(slots, "EstacionB")
        if not a or not b:
            missing = []
            if not a:
                missing.append("EstacionA")
            if not b:
                missing.append("EstacionB")
            return {
                "reply": "Dime las dos estaciones que quieres comparar.",
                "intent": "CompararEstaciones",
                "missing_slots": missing,
            }
        try:
            sa, pa, ra, _ = self._infer(a, model_loader)
            sb, pb, rb, _ = self._infer(b, model_loader)
        except Exception as e:
            return {
                "reply": f"No pude completar la comparación: {e}",
                "intent": "CompararEstaciones",
                "error": str(e),
            }

        order_a = LEVEL_ORDER.get(ra["worst"]["level"], 0)
        order_b = LEVEL_ORDER.get(rb["worst"]["level"], 0)
        if order_a < order_b:
            best, worst = (sa, ra), (sb, rb)
        elif order_b < order_a:
            best, worst = (sb, rb), (sa, ra)
        else:
            best = (sa, ra) if ra["worst"]["value"] <= rb["worst"]["value"] else (sb, rb)
            worst = (sb, rb) if best[0] == sa else (sa, ra)

        reply = (
            f"{best[0]} ({best[1]['worst']['level'].upper()} por {PRETTY_POLLUTANT[best[1]['worst']['pollutant']]}) "
            f"está mejor que {worst[0]} "
            f"({worst[1]['worst']['level'].upper()} por {PRETTY_POLLUTANT[worst[1]['worst']['pollutant']]})."
        )
        return {
            "reply": reply,
            "intent": "CompararEstaciones",
            "stations": {
                sa: {"predictions": {"unit": "µg/m³", **{k: round(v, 2) for k, v in pa.items()}}, "worst": ra["worst"]},
                sb: {"predictions": {"unit": "µg/m³", **{k: round(v, 2) for k, v in pb.items()}}, "worst": rb["worst"]},
            },
            "best_station": best[0],
            "ui_payload": {
                "action": "open_comparison",
                "station_a": sa,
                "station_b": sb,
            },
        }

    def _handle_consejo_salud(self, slots, model_loader, profile=None):
        estacion = _slot_value(slots, "Estacion")
        actividad = _slot_value(slots, "Actividad")
        if not estacion:
            return {
                "reply": "¿Sobre qué estación quieres consejo? (ej: Politécnico, Viveros...)",
                "intent": "ConsejoSalud",
                "missing_slot": "Estacion",
            }
        try:
            real_station, preds, risk_payload, _ = self._infer(estacion, model_loader)
        except Exception as e:
            return {
                "reply": f"No pude calcular el consejo para {estacion}: {e}",
                "intent": "ConsejoSalud",
                "error": str(e),
            }

        rec = build_recommendation(risk_payload, profile=profile, activity=actividad)
        return {
            "reply": rec["recommendation_text"],
            "intent": "ConsejoSalud",
            "station": real_station,
            "activity": actividad,
            "predictions": {"unit": "µg/m³", **{k: round(v, 2) for k, v in preds.items()}},
            "worst": risk_payload["worst"],
            "color": rec["color"],
            "level_adjusted": rec["level_adjusted"],
            "is_sensitive_profile": rec["is_sensitive_profile"],
            "ui_payload": {
                "action": "open_advice",
                "station": real_station,
                "cta": "ver_mapa",
            },
        }

    # --------- Sprint 7: nuevos intents ---------

    def _handle_ver_mapa_riesgo(self, slots):
        """Intent VerMapaRiesgo: abre el mapa de riesgo, opcionalmente
        filtrado por contaminante."""
        contaminante_raw = _slot_value(slots, "Contaminante")
        pollutant = None
        if contaminante_raw:
            norm = contaminante_raw.strip().lower().replace(" ", "").replace(".", "").replace("₂", "2").replace("₃", "3")
            mapping = {
                "pm25": "pm25", "pm2.5": "pm25", "particulas": "pm25",
                "no2": "no2", "nitrogeno": "no2",
                "o3": "o3", "ozono": "o3",
            }
            pollutant = mapping.get(norm, "pm25")

        pretty = PRETTY_POLLUTANT.get(pollutant, "") if pollutant else "calidad del aire"
        return {
            "reply": f"Aquí tienes el mapa de {pretty} en Valencia. Toca una estación para ver el detalle.",
            "intent": "VerMapaRiesgo",
            "ui_payload": {
                "action": "open_map",
                "pollutant": pollutant or "pm25",
                "horizon": "now",
            },
        }

    def _handle_prevision_riesgo(self, slots, model_loader):
        """Intent PrevisionRiesgo: forecast de un contaminante en una estación
        a un horizonte dado (24/48/72h)."""
        estacion = _slot_value(slots, "Estacion")
        contaminante_raw = _slot_value(slots, "Contaminante")
        horizonte_raw = _slot_value(slots, "Horizonte")

        if not estacion:
            return {
                "reply": "¿Para qué estación quieres la previsión? (ej: Politécnico, Francia...)",
                "intent": "PrevisionRiesgo",
                "missing_slot": "Estacion",
                "ui_payload": None,
            }

        # Parse horizonte
        horizon = 24  # default
        if horizonte_raw:
            try:
                h = int(horizonte_raw.replace("h", "").strip())
                if h in (24, 48, 72):
                    horizon = h
            except ValueError:
                pass

        # Parse contaminante
        pollutant = "pm25"
        if contaminante_raw:
            norm = contaminante_raw.strip().lower().replace(" ", "").replace(".", "").replace("₂", "2").replace("₃", "3")
            mapping = {
                "pm25": "pm25", "pm2.5": "pm25", "particulas": "pm25",
                "no2": "no2", "nitrogeno": "no2",
                "o3": "o3", "ozono": "o3",
            }
            pollutant = mapping.get(norm, "pm25")

        try:
            real_station, preds, risk_payload, meta = self._infer(estacion, model_loader, offset_hours=-horizon)
            info = risk_payload["pollutants"][pollutant]
            pretty = PRETTY_POLLUTANT[pollutant]
            reply = (
                f"La previsión de {pretty} en {real_station} a +{horizon}h es "
                f"{info['level'].upper()} ({info['value']:.1f} µg/m³). "
                f"⚠️ El modelo predice tendencia, no valor exacto."
            )
            return {
                "reply": reply,
                "intent": "PrevisionRiesgo",
                "station": real_station,
                "pollutant": pollutant,
                "horizon_hours": horizon,
                "value": info["value"],
                "level": info["level"],
                "predictions": {"unit": "µg/m³", **{k: round(v, 2) for k, v in preds.items()}},
                "ui_payload": {
                    "action": "open_station_detail",
                    "station": real_station,
                    "pollutant": pollutant,
                    "horizon": str(horizon),
                },
            }
        except Exception as e:
            return {
                "reply": f"No pude calcular la previsión para {estacion}: {e}",
                "intent": "PrevisionRiesgo",
                "error": str(e),
                "ui_payload": None,
            }

    def _handle_top_peores_estaciones(self, slots, model_loader):
        """Intent TopPeoresEstaciones: ranking de estaciones con peor riesgo
        para un horizonte (24/48/72) y contaminante opcional."""
        contaminante_raw = _slot_value(slots, "Contaminante")
        horizonte_raw = _slot_value(slots, "Horizonte")

        # Parse horizonte
        horizon = 24
        if horizonte_raw:
            try:
                h = int(str(horizonte_raw).replace("h", "").strip())
                if h in (24, 48, 72):
                    horizon = h
            except ValueError:
                pass

        # Parse contaminante
        pollutant = None  # None => worst overall
        if contaminante_raw:
            norm = (
                contaminante_raw.strip()
                .lower()
                .replace(" ", "")
                .replace(".", "")
                .replace("₂", "2")
                .replace("₃", "3")
            )
            mapping = {
                "pm25": "pm25",
                "pm2.5": "pm25",
                "particulas": "pm25",
                "partículas": "pm25",
                "no2": "no2",
                "nitrogeno": "no2",
                "nitrógeno": "no2",
                "o3": "o3",
                "ozono": "o3",
            }
            pollutant = mapping.get(norm)

        try:
            from src.api.routes_v2 import V2_STATIONS
        except Exception:
            V2_STATIONS = [
                "Francia",
                "Molí del Sol",
                "Pista de Silla",
                "Puerto Moll Trans. Ponent",
                "Puerto Valencia",
                "Puerto llit antic Túria",
                "Universidad Politécnica",
            ]

        entries = []
        for st in V2_STATIONS:
            try:
                real_station, preds, risk_payload, _ = self._infer(st, model_loader, offset_hours=-horizon)
                if pollutant:
                    info = risk_payload["pollutants"][pollutant]
                    entries.append(
                        (LEVEL_ORDER.get(info["level"], 0), float(info["value"]), real_station, info)
                    )
                else:
                    w = risk_payload["worst"]
                    entries.append(
                        (LEVEL_ORDER.get(w["level"], 0), float(w["value"]), real_station, w)
                    )
            except Exception:
                continue

        entries.sort(key=lambda x: (x[0], x[1]), reverse=True)
        top = entries[:3]
        if not top:
            return {
                "reply": "No pude calcular el ranking ahora mismo. Inténtalo de nuevo en unos minutos.",
                "intent": "TopPeoresEstaciones",
                "ui_payload": None,
            }

        lines = []
        for i, (_, value, st, info) in enumerate(top, start=1):
            pol = info.get("pollutant") if not pollutant else pollutant
            pretty = PRETTY_POLLUTANT.get(pol, pol)
            level = info.get("level", "bueno").upper()
            lines.append(f"{i}. {st}: {level} ({pretty} {value:.1f} µg/m³)")

        pretty_pol = PRETTY_POLLUTANT.get(pollutant, None)
        title = f"Peores estaciones a +{horizon}h" + (f" para {pretty_pol}" if pretty_pol else "")
        reply = title + ":\n" + "\n".join(lines) + "\n\nPuedes verlo en el mapa."

        return {
            "reply": reply,
            "intent": "TopPeoresEstaciones",
            "horizon_hours": horizon,
            "pollutant": pollutant,
            "top": [{"station": st, **info} for (_, _, st, info) in top],
            "ui_payload": {
                "action": "open_map",
                "pollutant": pollutant or "pm25",
                "horizon": str(horizon),
            },
        }
