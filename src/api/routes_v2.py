"""
API Routes v2 — Endpoints multitarget (PM2.5, NO2, O3)

Rutas bajo /api/v2 (coexisten con v1).
"""

from __future__ import annotations

import math
import os
from datetime import datetime
from datetime import timezone, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
from flask import Blueprint, current_app, jsonify, request

from src.api.es_indexer import STATION_COORDS, ESIndexer
from src.api.feature_extractor_v2 import FeatureExtractorV2
from src.api.schemas import format_error_response
from src.ml.risk_classifier_v2 import RiskClassifierV2
from src.services.chatbot_orchestrator_v2 import ChatbotOrchestratorV2
from src.services.profile_advisor import build_recommendation


# Estaciones del v2 (coinciden con las del CSV master_dataset_colab_v2.csv)
V2_STATIONS = [
    "Francia",
    "Molí del Sol",
    "Pista de Silla",
    "Puerto Moll Trans. Ponent",
    "Puerto Valencia",
    "Puerto llit antic Túria",
    "Universidad Politécnica",
]

# Métricas estáticas del modelo v2 (transparencia / CSV de logs).
# Fuente: `models/modelo_11_v2_Multitarget/day11_v2_results.csv`
V2_MODEL_METRICS = {
    "LSTM_Attention_Multi": {
        "pm25": {"mae": 1.5681, "rmse": 2.8279, "r2": 0.8571},
        "no2": {"mae": 3.8648, "rmse": 5.9141, "r2": 0.8397},
        "o3": {"mae": 6.2557, "rmse": 8.8754, "r2": 0.8861},
    }
}

_ROUTES_V2_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _append_predictions_log_v2(
    real_station: str,
    horizon_hours: int,
    preds: Dict[str, float],
    model_name: str = "LSTM_Attention_Multi",
) -> None:
    """Añade una fila a `data/logs/predictions_log.csv` (mismo esquema que antes)."""
    try:
        log_dir = os.path.join(_ROUTES_V2_PROJECT_ROOT, "data", "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "predictions_log.csv")
        file_exists = os.path.exists(log_file)
        m = V2_MODEL_METRICS.get(model_name, {})
        pm = m.get("pm25", {})
        n2 = m.get("no2", {})
        o3m = m.get("o3", {})
        with open(log_file, "a") as f:
            if not file_exists:
                f.write(
                    "timestamp,station,horizon_hours,model,pm25,no2,o3,"
                    "pm25_rmse,no2_rmse,o3_rmse,pm25_r2,no2_r2,o3_r2\n"
                )
            f.write(
                f"{datetime.now().isoformat()},{real_station},{horizon_hours},{model_name},"
                f"{preds['pm25']},{preds['no2']},{preds['o3']},"
                f"{pm.get('rmse','')},{n2.get('rmse','')},{o3m.get('rmse','')},"
                f"{pm.get('r2','')},{n2.get('r2','')},{o3m.get('r2','')}\n"
            )
    except Exception as e:
        print(f"⚠️ Error guardando log de predicción: {e}")

def _mongo_air_collection():
    """Devuelve colección Mongo `airvlc_db.aire_realtime` o None si no hay config."""
    mongo_uri = (os.getenv("MONGO_URI") or "").strip()
    if not mongo_uri:
        return None, None
    try:
        from pymongo import MongoClient
    except Exception:
        return None, None
    client = MongoClient(mongo_uri)
    db = client["airvlc_db"]
    return client, db["aire_realtime"]


def _mongo_predictions_cache():
    """Devuelve colección Mongo `airvlc_db.predictions_cache` o None."""
    mongo_uri = (os.getenv("MONGO_URI") or "").strip()
    if not mongo_uri:
        return None, None
    try:
        from pymongo import MongoClient
    except Exception:
        return None, None
    client = MongoClient(mongo_uri)
    db = client["airvlc_db"]
    return client, db["predictions_cache"]


def _save_prediction_cache(station: str, horizon_hours: int, preds: dict,
                           risk_payload: dict, pollutant: str = "all") -> bool:
    """Guarda una predicción en el cache de MongoDB."""
    client, coll = _mongo_predictions_cache()
    if coll is None:
        return False
    try:
        from src.ml.risk_classifier_v2 import RiskClassifierV2 as _RC
        now = datetime.now(timezone.utc)
        doc = {
            "station": station,
            "horizon_hours": horizon_hours,
            "predictions": {
                "pm25": round(preds["pm25"], 2),
                "no2": round(preds["no2"], 2),
                "o3": round(preds["o3"], 2),
            },
            "pollutants": risk_payload.get("pollutants", {}),
            "worst": risk_payload.get("worst", {}),
            "model_used": "LSTM_Attention_Multi",
            "generated_at": now,
            "expires_at": now + timedelta(hours=2),
        }
        coll.update_one(
            {"station": station, "horizon_hours": horizon_hours},
            {"$set": doc},
            upsert=True,
        )
        return True
    except Exception as e:
        print(f"⚠️ Error guardando cache de predicción: {e}")
        return False
    finally:
        try:
            client.close()
        except Exception:
            pass


def _get_cached_prediction(station: str, pollutant: str, horizon_hours: int) -> Optional[dict]:
    """Lee la predicción cacheada más reciente para una estación/horizonte.
    Devuelve dict listo para la respuesta del endpoint, o None si no hay cache válido."""
    if horizon_hours == 0:
        return None  # h=0 siempre se calcula en tiempo real
    client, coll = _mongo_predictions_cache()
    if coll is None:
        return None
    try:
        doc = coll.find_one(
            {
                "station": station,
                "horizon_hours": horizon_hours,
                "expires_at": {"$gt": datetime.now(timezone.utc)},
            },
            sort=[("generated_at", -1)],
        )
        if not doc:
            return None
        preds = doc.get("predictions", {})
        pol_info = doc.get("pollutants", {}).get(pollutant, {})
        return {
            "horizon_hours": horizon_hours,
            "label": f"+{horizon_hours}h",
            "value": preds.get(pollutant),
            "level": pol_info.get("level", "bueno"),
            "color": pol_info.get("color", "#2BB673"),
            "available": True,
            "source": "model_cache",
            "model_used": doc.get("model_used", "LSTM_Attention_Multi"),
            "all_predictions": preds,
        }
    except Exception:
        return None
    finally:
        try:
            client.close()
        except Exception:
            pass


def _get_cached_map_entry(station: str, pollutant: str, horizon_hours: int) -> Optional[dict]:
    """Lee cache para el endpoint /map. Devuelve dict con value/level/color o None."""
    if horizon_hours == 0:
        return None
    client, coll = _mongo_predictions_cache()
    if coll is None:
        return None
    try:
        doc = coll.find_one(
            {
                "station": station,
                "horizon_hours": horizon_hours,
                "expires_at": {"$gt": datetime.now(timezone.utc)},
            },
            sort=[("generated_at", -1)],
        )
        if not doc:
            return None
        preds = doc.get("predictions", {})
        pol_info = doc.get("pollutants", {}).get(pollutant, {})
        return {
            "value": preds.get(pollutant),
            "level": pol_info.get("level", "bueno"),
            "color": pol_info.get("color", "#2BB673"),
            "all_predictions": {**preds, "unit": "µg/m³"},
            "worst": doc.get("worst", {}),
            "model_used": doc.get("model_used"),
        }
    except Exception:
        return None
    finally:
        try:
            client.close()
        except Exception:
            pass


def _fetch_observed_from_mongo(station: str, pollutant: str, hours: int = 72) -> tuple[list[dict], dict]:
    """Obtiene los últimos `hours` puntos observados desde Mongo (sin sintéticos)."""
    client, coll = _mongo_air_collection()
    if coll is None:
        return [], {"error": "Mongo no configurado"}
    try:
        since = datetime.now(timezone.utc) - timedelta(hours=int(hours))
        q = {
            "estacion": station,
            "fecha": {"$gte": since},
            "is_synthetic": {"$ne": True},
        }
        proj = {"_id": 0, "fecha": 1, pollutant: 1, "source": 1}
        cur = coll.find(q, proj).sort("fecha", 1)
        obs: list[dict] = []
        for doc in cur:
            ts = doc.get("fecha")
            val = doc.get(pollutant)
            if ts is None or val is None:
                continue
            try:
                v = float(val)
            except Exception:
                continue
            # Normalizar timestamp a ISO con Z
            if hasattr(ts, "tzinfo") and ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            iso = ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            obs.append({"timestamp": iso, "value": round(v, 2), "source": doc.get("source")})

        meta: dict = {}
        if obs:
            meta["observed_last_timestamp"] = obs[-1]["timestamp"]
            meta["observed_points"] = len(obs)
            # cobertura esperada (1 punto/h): % horas presentes aprox.
            meta["expected_points"] = int(hours)
            meta["coverage_ratio"] = round(len(obs) / float(max(1, int(hours))), 3)
        return obs, meta
    finally:
        try:
            client.close()
        except Exception:
            pass


def _haversine_km(a: Dict[str, float], b: Dict[str, float]) -> float:
    R = 6371.0
    lat1, lon1 = math.radians(a["lat"]), math.radians(a["lon"])
    lat2, lon2 = math.radians(b["lat"]), math.radians(b["lon"])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def _resolve_station(name: Optional[str]) -> Optional[str]:
    """Mapea nombre libre → estación canónica del v2 (las 7 disponibles)."""
    if not name:
        return None
    norm = name.strip().lower()
    for canonical in V2_STATIONS:
        if canonical.lower() == norm:
            return canonical
    aliases = {
        "francia": "Francia",
        "avda. francia": "Francia",
        "av. frança": "Francia",
        "moli del sol": "Molí del Sol",
        "molí del sol": "Molí del Sol",
        "pista silla": "Pista de Silla",
        "pista de silla": "Pista de Silla",
        "puerto valencia": "Puerto Valencia",
        "puerto": "Puerto Valencia",
        "port": "Puerto Valencia",
        "puerto moll": "Puerto Moll Trans. Ponent",
        "puerto moll trans. ponent": "Puerto Moll Trans. Ponent",
        "puerto turia": "Puerto llit antic Túria",
        "puerto llit antic turia": "Puerto llit antic Túria",
        "puerto llit antic túria": "Puerto llit antic Túria",
        "politecnico": "Universidad Politécnica",
        "politécnico": "Universidad Politécnica",
        "politecnica": "Universidad Politécnica",
        "politécnica": "Universidad Politécnica",
        "universidad politecnica": "Universidad Politécnica",
        "universidad politécnica": "Universidad Politécnica",
    }
    return aliases.get(norm)


def _order_route(from_st: str, to_st: str) -> List[str]:
    """Ordena las 7 estaciones del v2 entre `from` y `to` por proximidad geográfica
    (greedy nearest-neighbor con sesgo hacia el destino)."""
    if from_st not in STATION_COORDS or to_st not in STATION_COORDS:
        return [from_st, to_st]
    if from_st == to_st:
        return [from_st]

    coords = {s: STATION_COORDS[s] for s in V2_STATIONS if s in STATION_COORDS}
    target = STATION_COORDS[to_st]

    visited = {from_st}
    path = [from_st]
    current = from_st
    while current != to_st:
        candidates = [s for s in coords if s not in visited]
        if not candidates:
            break
        # Elige el siguiente que minimiza dist(current→s) + dist(s→destino)
        next_st = min(
            candidates,
            key=lambda s: _haversine_km(coords[current], coords[s])
            + _haversine_km(coords[s], target),
        )
        path.append(next_st)
        visited.add(next_st)
        current = next_st
        if len(path) > len(coords):  # safety
            break
    if path[-1] != to_st:
        path.append(to_st)
    return path


def _validate_v2_payload(data) -> Optional[str]:
    if not isinstance(data, dict):
        return "Body inválido. Envía JSON."

    if any(k in data for k in ("pm25", "no2", "o3")):
        missing = [k for k in ("pm25", "no2", "o3") if k not in data]
        if missing:
            return f"Faltan campos para valores directos: {missing}"
        try:
            float(data["pm25"])
            float(data["no2"])
            float(data["o3"])
        except Exception:
            return "'pm25', 'no2' y 'o3' deben ser numéricos."
        return None

    if "features" not in data and "station" not in data:
        return "Debe enviar 'features' (array 2D) o 'station' (nombre de estación)."

    if "features" in data:
        feats = data["features"]
        if not isinstance(feats, list) or not feats:
            return "'features' debe ser una lista 2D no vacía."
        if not isinstance(feats[0], list):
            return "'features' debe ser una lista de listas (array 2D)."
    return None


def _safe_get_features(extractor, station: Optional[str], offset_hours: int):
    """Compat: algunos extractores de test no aceptan offset_hours."""
    try:
        out = extractor.get_features(station, offset_hours)
    except TypeError:
        out = extractor.get_features(station)

    # Normalizar salida a (features, station, meta)
    if isinstance(out, tuple) and len(out) == 2:
        features, real_station = out
        return features, real_station, {}
    return out


def create_api_v2_blueprint(
    feature_extractor: Optional[FeatureExtractorV2] = None,
    risk_classifier: Optional[RiskClassifierV2] = None,
    chatbot: Optional[ChatbotOrchestratorV2] = None,
) -> Blueprint:
    # Fail-safe init: allow API to boot even if optional deps (pandas/boto3) are missing
    if feature_extractor is None:
        try:
            feature_extractor = FeatureExtractorV2()
        except Exception as e:
            print(f"⚠️ Error inicializando FeatureExtractorV2: {e}")
            feature_extractor = None
    risk_classifier = risk_classifier or RiskClassifierV2()
    if chatbot is None:
        try:
            chatbot = ChatbotOrchestratorV2()
        except Exception as e:
            print(f"⚠️ Error inicializando ChatbotOrchestratorV2: {e}")
            chatbot = None

    api_v2_bp = Blueprint("api_v2", __name__, url_prefix="/api/v2")

    @api_v2_bp.route("/health", methods=["GET"])
    def health_check_v2():
        loader = current_app.config.get("MODEL_LOADER")
        es_v2 = current_app.config.get("ES_INDEXER_V2")
        status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "AirVLC v2 Multitarget API",
            "version": "2.0.0",
            "models": {
                "loaded": bool(loader and loader.is_ready),
                "best_model": getattr(loader, "best_model_name", None) if loader else None,
                "available_models": list(getattr(loader, "models", {}).keys()) if loader else [],
                "v2_required": "LSTM_Attention_Multi",
                "v2_loaded": bool(loader and getattr(loader, "models", {}).get("LSTM_Attention_Multi") is not None),
            },
            "elasticsearch": {
                "connected": bool(es_v2 and es_v2.is_connected),
                "index": getattr(es_v2, "index_name", "airvlc-predictions-v2"),
            },
        }

        http_code = 200 if (loader and loader.is_ready) else 503
        return jsonify(status), http_code

    @api_v2_bp.route("/health/freshness", methods=["GET"])
    def health_freshness_v2():
        """Healthcheck específico de frescura del dataset v2 (CSV en memoria)."""
        if feature_extractor is None:
            return jsonify(
                format_error_response(
                    "FeatureExtractorV2 no disponible (dataset/scaler/pandas).",
                    503,
                )
            ), 503

        try:
            # Estación canónica por defecto para medir frescura.
            features, real_station, meta = _safe_get_features(feature_extractor, "Francia", 0)
            age_min = int(meta.get("data_age_minutes") or 0)
            data_ts = meta.get("data_timestamp")
            status = "ok" if age_min < 120 else "stale"
            code = 200 if status == "ok" else 503
            return jsonify(
                {
                    "status": status,
                    "station": real_station,
                    "data_timestamp": data_ts,
                    "data_age_minutes": age_min,
                }
            ), code
        except Exception as e:
            return jsonify(format_error_response(f"Error comprobando frescura: {str(e)}", 500)), 500

    @api_v2_bp.route("/predict", methods=["POST"])
    def predict_v2():
        loader = current_app.config.get("MODEL_LOADER")
        if not loader or not loader.is_ready:
            return jsonify(
                format_error_response(
                    "Modelos no disponibles. Asegúrate de que el modelo v2 está en models/.",
                    503,
                )
            ), 503

        data = request.get_json()
        if not data:
            return jsonify(format_error_response("Request body vacío. Envía JSON.", 400)), 400

        error = _validate_v2_payload(data)
        if error:
            return jsonify(format_error_response(error, 400)), 400

        try:
            if feature_extractor is None and "features" not in data:
                return jsonify(
                    format_error_response(
                        "FeatureExtractorV2 no disponible (falta instalar 'pandas' o dataset/scaler). "
                        "Envía 'features' directamente o instala dependencias.",
                        503,
                    )
                ), 503
            station = data.get("station")
            model_name = data.get("model", "LSTM_Attention_Multi")
            offset_hours = data.get("offset_hours", 0)

            meta = {}
            if "features" in data:
                features = np.array(data["features"], dtype=np.float32)
                if features.ndim == 2:
                    features = features.reshape(1, features.shape[0], features.shape[1])
                real_station = station
            else:
                features, real_station, meta = _safe_get_features(
                    feature_extractor, station, int(offset_hours or 0)
                )

            y_scaled = loader.predict(features, model_name=model_name)
            preds = feature_extractor.inverse_transform_predictions(y_scaled) if feature_extractor else {
                "pm25": float(y_scaled[0, 0]),
                "no2": float(y_scaled[0, 1]),
                "o3": float(y_scaled[0, 2]),
            }

            response = {
                "success": True,
                "station": real_station,
                "predictions": {
                    "pm25": round(preds["pm25"], 2),
                    "no2": round(preds["no2"], 2),
                    "o3": round(preds["o3"], 2),
                    "unit": "µg/m³",
                },
                "model_used": model_name,
                "server_timestamp": datetime.now().isoformat(),
                "timestamp": datetime.now().isoformat(),
            }
            if meta:
                response["data_timestamp"] = meta.get("data_timestamp")
                response["data_age_minutes"] = meta.get("data_age_minutes")
                response["data_window_start"] = meta.get("data_window_start")

            return jsonify(response), 200
        except Exception as e:
            return jsonify(format_error_response(f"Error en predicción v2: {str(e)}", 500)), 500

    @api_v2_bp.route("/risk", methods=["POST"])
    def risk_v2():
        data = request.get_json()
        if not data:
            return jsonify(format_error_response("Request body vacío. Envía JSON.", 400)), 400

        error = _validate_v2_payload(data)
        if error:
            return jsonify(format_error_response(error, 400)), 400

        loader = current_app.config.get("MODEL_LOADER")
        es_v2 = current_app.config.get("ES_INDEXER_V2")

        try:
            station = data.get("station")
            model_name = data.get("model", "LSTM_Attention_Multi")
            offset_hours = data.get("offset_hours", 0)

            if all(k in data for k in ("pm25", "no2", "o3")):
                real_station = station
                pm25 = float(data["pm25"])
                no2 = float(data["no2"])
                o3 = float(data["o3"])
            else:
                if not loader or not loader.is_ready:
                    return jsonify(format_error_response("Modelos no disponibles para predicción", 503)), 503

                if feature_extractor is None and "features" not in data:
                    return jsonify(
                        format_error_response(
                            "FeatureExtractorV2 no disponible (falta instalar 'pandas' o dataset/scaler). "
                            "Envía 'features' directamente o instala dependencias.",
                            503,
                        )
                    ), 503

                meta = {}
                if "features" in data:
                    features = np.array(data["features"], dtype=np.float32)
                    if features.ndim == 2:
                        features = features.reshape(1, features.shape[0], features.shape[1])
                    real_station = station
                else:
                    features, real_station, meta = _safe_get_features(
                        feature_extractor, station, int(offset_hours or 0)
                    )

                y_scaled = loader.predict(features, model_name=model_name)
                preds = feature_extractor.inverse_transform_predictions(y_scaled) if feature_extractor else {
                    "pm25": float(y_scaled[0, 0]),
                    "no2": float(y_scaled[0, 1]),
                    "o3": float(y_scaled[0, 2]),
                }
                pm25, no2, o3 = preds["pm25"], preds["no2"], preds["o3"]

            payload = risk_classifier.classify_multi(pm25=pm25, no2=no2, o3=o3, station=real_station)
            response = {
                "success": True,
                "station": real_station,
                "predictions": {"pm25": round(pm25, 2), "no2": round(no2, 2), "o3": round(o3, 2), "unit": "µg/m³"},
                **payload,
                "server_timestamp": datetime.now().isoformat(),
                "timestamp": datetime.now().isoformat(),
            }
            if meta:
                response["data_timestamp"] = meta.get("data_timestamp")
                response["data_age_minutes"] = meta.get("data_age_minutes")
                response["data_window_start"] = meta.get("data_window_start")

            if es_v2:
                worst = payload.get("worst", {})
                es_v2.index_prediction(
                    {
                        "pm25_pred": pm25,
                        "no2_pred": no2,
                        "o3_pred": o3,
                        "risk_pm25": payload["pollutants"]["pm25"]["level"],
                        "risk_no2": payload["pollutants"]["no2"]["level"],
                        "risk_o3": payload["pollutants"]["o3"]["level"],
                        "worst_pollutant": worst.get("pollutant"),
                        "worst_level": worst.get("level"),
                        "station": real_station,
                        "model_used": model_name if ("features" in data or "station" in data) else "direct",
                        "source": "api-v2",
                        "prediction_type": "realtime",
                        "alert_text": payload.get("reply_text"),
                    }
                )

            return jsonify(response), 200
        except Exception as e:
            return jsonify(format_error_response(f"Error en clasificación v2: {str(e)}", 500)), 500

    @api_v2_bp.route("/chat", methods=["POST"])
    def chat_v2():
        if chatbot is None:
            return jsonify(format_error_response("Servicio de Chatbot v2 no disponible (AWS/boto3/credenciales).", 503)), 503
        data = request.get_json()
        if not data or "message" not in data:
            return jsonify(format_error_response('Se requiere el campo "message"', 400)), 400

        message = data["message"]
        session_id = data.get("session_id", "test-session")
        loader = current_app.config.get("MODEL_LOADER")

        try:
            response = chatbot.process_message(text=message, session_id=session_id, model_loader=loader)
            return jsonify(response), 200
        except Exception as e:
            return jsonify(format_error_response(f"Error en el chat v2: {str(e)}", 500)), 500

    def _infer_for_station(
        station: Optional[str],
        model_name: str = "LSTM_Attention_Multi",
        offset_hours: int = 0,
    ) -> Tuple[str, Dict, Dict, dict]:
        """Helper interno: dado el nombre de una estación, ejecuta inferencia v2
        y devuelve (real_station, predictions_dict, risk_payload, freshness_meta).
        Levanta excepción si no hay modelo o extractor disponible.
        """
        loader = current_app.config.get("MODEL_LOADER")
        if not loader or not loader.is_ready:
            raise RuntimeError("Modelos no disponibles para predicción")
        if feature_extractor is None:
            raise RuntimeError("FeatureExtractorV2 no disponible (falta dataset/scaler)")

        features, real_station, meta = _safe_get_features(
            feature_extractor,
            station,
            int(offset_hours or 0) if offset_hours > 0 else 0,
        )
        y_scaled = loader.predict(features, model_name=model_name)
        preds = feature_extractor.inverse_transform_predictions(y_scaled)

        risk_payload = risk_classifier.classify_multi(
            pm25=preds["pm25"], no2=preds["no2"], o3=preds["o3"], station=real_station,
        )

        horizon_hours = abs(int(offset_hours)) if offset_hours < 0 else int(offset_hours)
        _append_predictions_log_v2(
            real_station,
            horizon_hours,
            {"pm25": preds["pm25"], "no2": preds["no2"], "o3": preds["o3"]},
            model_name=model_name,
        )

        return real_station, preds, risk_payload, meta

    def _infer_for_station_horizon(
        station: Optional[str],
        horizon_hours: int = 0,
        model_name: str = "LSTM_Attention_Multi",
    ) -> Tuple[str, Dict, Dict, dict]:
        """Inferencia para un horizonte futuro: usa features temporales ajustadas.
        Delega en FeatureExtractorV2.get_features_for_horizon()."""
        loader = current_app.config.get("MODEL_LOADER")
        if not loader or not loader.is_ready:
            raise RuntimeError("Modelos no disponibles para predicción")
        if feature_extractor is None:
            raise RuntimeError("FeatureExtractorV2 no disponible")

        features, real_station, meta = feature_extractor.get_features_for_horizon(
            station, horizon_hours=int(horizon_hours),
        )
        y_scaled = loader.predict(features, model_name=model_name)
        preds = feature_extractor.inverse_transform_predictions(y_scaled)
        risk_payload = risk_classifier.classify_multi(
            pm25=preds["pm25"], no2=preds["no2"], o3=preds["o3"], station=real_station,
        )
        _append_predictions_log_v2(
            real_station,
            int(horizon_hours),
            {"pm25": preds["pm25"], "no2": preds["no2"], "o3": preds["o3"]},
            model_name=model_name,
        )
        return real_station, preds, risk_payload, meta

    @api_v2_bp.route("/profile/recommend", methods=["POST"])
    def profile_recommend_v2():
        data = request.get_json() or {}
        station = data.get("station")
        if not station:
            return jsonify(format_error_response("Falta 'station' en el body.", 400)), 400

        profile = data.get("profile") or {}
        activity = data.get("activity") or profile.get("activity")

        offset_hours = data.get("offset_hours", 0)
        try:
            real_station, preds, risk_payload, meta = _infer_for_station(station, offset_hours=int(offset_hours or 0))
        except RuntimeError as e:
            return jsonify(format_error_response(str(e), 503)), 503
        except Exception as e:
            return jsonify(format_error_response(f"Error en inferencia v2: {str(e)}", 500)), 500

        rec = build_recommendation(risk_payload, profile=profile, activity=activity)

        es_v2 = current_app.config.get("ES_INDEXER_V2")
        if es_v2:
            worst = risk_payload.get("worst", {})
            try:
                es_v2.index_prediction(
                    {
                        "pm25_pred": preds["pm25"],
                        "no2_pred": preds["no2"],
                        "o3_pred": preds["o3"],
                        "risk_pm25": risk_payload["pollutants"]["pm25"]["level"],
                        "risk_no2": risk_payload["pollutants"]["no2"]["level"],
                        "risk_o3": risk_payload["pollutants"]["o3"]["level"],
                        "worst_pollutant": worst.get("pollutant"),
                        "worst_level": worst.get("level"),
                        "station": real_station,
                        "model_used": "LSTM_Attention_Multi",
                        "source": "api-v2-profile",
                        "prediction_type": "realtime",
                        "alert_text": rec.get("recommendation_text"),
                    }
                )
            except Exception:
                pass

        resp = {
            "success": True,
            "station": real_station,
            "predictions": {
                "pm25": round(preds["pm25"], 2),
                "no2": round(preds["no2"], 2),
                "o3": round(preds["o3"], 2),
                "unit": "µg/m³",
            },
            "pollutants": risk_payload["pollutants"],
            "worst": risk_payload["worst"],
            "reply_text": risk_payload["reply_text"],
            "recommendation_text": rec["recommendation_text"],
            "color": rec["color"],
            "level_adjusted": rec["level_adjusted"],
            "is_sensitive_profile": rec["is_sensitive_profile"],
            "profile_used": rec["profile_used"],
            "server_timestamp": datetime.now().isoformat(),
            "timestamp": datetime.now().isoformat(),
        }
        if meta:
            resp["data_timestamp"] = meta.get("data_timestamp")
            resp["data_age_minutes"] = meta.get("data_age_minutes")
            resp["data_window_start"] = meta.get("data_window_start")

        return jsonify(resp), 200

    @api_v2_bp.route("/route", methods=["POST"])
    def route_v2():
        data = request.get_json() or {}
        from_raw = data.get("from_station") or data.get("from")
        to_raw = data.get("to_station") or data.get("to")
        offset_hours = data.get("offset_hours", 0)
        if not from_raw or not to_raw:
            return jsonify(
                format_error_response("Se requieren 'from_station' y 'to_station'.", 400)
            ), 400

        from_st = _resolve_station(from_raw)
        to_st = _resolve_station(to_raw)
        if not from_st or not to_st:
            return jsonify(
                format_error_response(
                    f"Estación no reconocida. Disponibles: {V2_STATIONS}", 400
                )
            ), 400

        path = _order_route(from_st, to_st)
        segments: List[Dict] = []
        worst_overall: Optional[Dict] = None
        worst_idx = -1

        route_meta = {}
        for st in path:
            try:
                real_station, preds, risk_payload, seg_meta = _infer_for_station(st, offset_hours=int(offset_hours or 0))
            except RuntimeError as e:
                return jsonify(format_error_response(str(e), 503)), 503
            except Exception as e:
                return jsonify(format_error_response(f"Error en inferencia para {st}: {str(e)}", 500)), 500

            if not route_meta and seg_meta:
                route_meta = seg_meta

            seg = {
                "station": real_station,
                "predictions": {
                    "pm25": round(preds["pm25"], 2),
                    "no2": round(preds["no2"], 2),
                    "o3": round(preds["o3"], 2),
                    "unit": "µg/m³",
                },
                "pollutants": risk_payload["pollutants"],
                "worst": risk_payload["worst"],
                "location": STATION_COORDS.get(real_station),
            }
            segments.append(seg)

            from src.ml.risk_classifier_v2 import LEVEL_ORDER as _LO
            cur_order = _LO.get(seg["worst"]["level"], 0)
            best_so_far = _LO.get((worst_overall or {}).get("level", "bueno"), 0)
            if worst_overall is None or cur_order > best_so_far:
                worst_overall = {**seg["worst"], "station": real_station}
                worst_idx = len(segments) - 1

        # Mensaje narrativo: cuál es el tramo problemático
        narrative: Optional[str] = None
        if worst_overall and worst_overall.get("level") in {"moderado", "malo", "peligroso"}:
            narrative = (
                f"El tramo más comprometido es {worst_overall['station']}: "
                f"{worst_overall['level'].upper()} por {worst_overall['pollutant'].upper()}. "
                f"Si puedes, evita ese punto."
            )
        elif worst_overall:
            narrative = "Ruta saludable: ningún tramo supera el nivel bueno."

        resp = {
            "success": True,
            "from_station": from_st,
            "to_station": to_st,
            "segments": segments,
            "worst_segment_index": worst_idx,
            "worst_overall": worst_overall,
            "reply_text": narrative,
            "server_timestamp": datetime.now().isoformat(),
            "timestamp": datetime.now().isoformat(),
        }
        if route_meta:
            resp["data_timestamp"] = route_meta.get("data_timestamp")
            resp["data_age_minutes"] = route_meta.get("data_age_minutes")
            resp["data_window_start"] = route_meta.get("data_window_start")

        return jsonify(resp), 200

    # --- Sprint 5: endpoint interno de recarga ---
    @api_v2_bp.route("/_internal/reload", methods=["POST"])
    def internal_reload():
        """Recarga el CSV en memoria sin reiniciar Flask.
        Protegido por header X-Internal-Token."""
        expected_token = os.environ.get("AIRVLC_INTERNAL_RELOAD_TOKEN", "airvlc-reload-secret")
        provided_token = request.headers.get("X-Internal-Token", "")
        if provided_token != expected_token:
            return jsonify(format_error_response("Token inválido.", 403)), 403

        if feature_extractor is None:
            return jsonify(format_error_response("FeatureExtractorV2 no disponible.", 503)), 503

        try:
            feature_extractor.reload()
            return jsonify({
                "success": True,
                "message": "Dataset v2 recargado en memoria.",
                "server_timestamp": datetime.now().isoformat(),
            }), 200
        except Exception as e:
            return jsonify(format_error_response(f"Error recargando: {str(e)}", 500)), 500

    # --- Sprint 6.2: endpoint interno append + reload (para Node-RED) ---
    @api_v2_bp.route("/_internal/append_and_reload", methods=["POST"])
    def internal_append_and_reload():
        """Hace append al CSV v2 (si hay datos nuevos en Mongo) y recarga en memoria.
        Protegido por header X-Internal-Token.
        Pensado para ser llamado tras ingesta (p.ej. Node-RED)."""
        expected_token = os.environ.get("AIRVLC_INTERNAL_RELOAD_TOKEN", "airvlc-reload-secret")
        provided_token = request.headers.get("X-Internal-Token", "")
        if provided_token != expected_token:
            return jsonify(format_error_response("Token inválido.", 403)), 403

        if feature_extractor is None:
            return jsonify(format_error_response("FeatureExtractorV2 no disponible.", 503)), 503

        try:
            from src.ml.append_to_dataset_v2 import append_to_dataset_v2

            append_result = append_to_dataset_v2()
            feature_extractor.reload()
            return jsonify({
                "success": True,
                "append": append_result,
                "message": "Append ejecutado y dataset recargado en memoria.",
                "server_timestamp": datetime.now().isoformat(),
            }), 200
        except Exception as e:
            return jsonify(format_error_response(f"Error en append/reload: {str(e)}", 500)), 500

    # =====================================================================
    # Sprint 7 — Visualisation endpoints (map, timeseries, ranking)
    # =====================================================================

    @api_v2_bp.route("/map", methods=["GET"])
    def map_stations():
        """Devuelve todas las estaciones con su valor/riesgo para un
        contaminante y horizonte dados.

        Query params:
            pollutant (str): pm25 | no2 | o3  (default: pm25)
            horizon  (int):  0 | 24 | 48 | 72  (horas, default: 0 = ahora)
        """
        pollutant = request.args.get("pollutant", "pm25").lower().strip()
        if pollutant not in ("pm25", "no2", "o3"):
            return jsonify(format_error_response(
                f"Contaminante inválido '{pollutant}'. Usa pm25, no2 u o3.", 400
            )), 400

        try:
            horizon = int(request.args.get("horizon", 0))
        except ValueError:
            horizon = 0

        # Validar horizonte
        if horizon not in (0, 24, 48, 72):
            horizon = 0

        stations_out = []
        for st in V2_STATIONS:
            try:
                # Para horizontes futuros, intentar leer del cache primero
                if horizon > 0:
                    cached = _get_cached_map_entry(st, pollutant, horizon)
                    if cached:
                        stations_out.append({
                            "station": st,
                            "location": STATION_COORDS.get(st),
                            "value": cached["value"],
                            "level": cached["level"],
                            "color": cached["color"],
                            "emoji": "",
                            "all_predictions": cached["all_predictions"],
                            "worst": cached.get("worst", {}),
                            "meta": {
                                "model_used": cached.get("model_used", "LSTM_Attention_Multi"),
                                "horizon_hours": horizon,
                                "available": True,
                                "source": "model_cache",
                            },
                        })
                        ap = cached.get("all_predictions") or {}
                        try:
                            _append_predictions_log_v2(
                                st,
                                horizon,
                                {
                                    "pm25": float(ap["pm25"]),
                                    "no2": float(ap["no2"]),
                                    "o3": float(ap["o3"]),
                                },
                                model_name=cached.get("model_used") or "LSTM_Attention_Multi",
                            )
                        except (KeyError, TypeError, ValueError):
                            pass
                        continue
                    # Fallback: inferir en tiempo real con features ajustadas
                    try:
                        real_station, preds, risk_payload, meta = _infer_for_station_horizon(
                            st, horizon_hours=horizon,
                        )
                        pol_info = risk_payload["pollutants"].get(pollutant, {})
                        stations_out.append({
                            "station": real_station,
                            "location": STATION_COORDS.get(real_station),
                            "value": round(preds.get(pollutant, 0), 2),
                            "level": pol_info.get("level", "bueno"),
                            "color": pol_info.get("color", "#2BB673"),
                            "emoji": pol_info.get("emoji", ""),
                            "all_predictions": {
                                "pm25": round(preds["pm25"], 2),
                                "no2": round(preds["no2"], 2),
                                "o3": round(preds["o3"], 2),
                                "unit": "µg/m³",
                            },
                            "worst": risk_payload["worst"],
                            "meta": {
                                "model_used": "LSTM_Attention_Multi",
                                "horizon_hours": horizon,
                                "available": True,
                                "source": "realtime_forecast",
                            },
                        })
                        continue
                    except Exception:
                        pass  # caer al caso h=0 como fallback final

                real_station, preds, risk_payload, meta = _infer_for_station(st, offset_hours=0)
                pol_info = risk_payload["pollutants"].get(pollutant, {})
                stations_out.append({
                    "station": real_station,
                    "location": STATION_COORDS.get(real_station),
                    "value": round(preds.get(pollutant, 0), 2),
                    "level": pol_info.get("level", "bueno"),
                    "color": pol_info.get("color", "#2BB673"),
                    "emoji": pol_info.get("emoji", ""),
                    "all_predictions": {
                        "pm25": round(preds["pm25"], 2),
                        "no2": round(preds["no2"], 2),
                        "o3": round(preds["o3"], 2),
                        "unit": "µg/m³",
                    },
                    "worst": risk_payload["worst"],
                    "meta": {
                        "model_used": "LSTM_Attention_Multi",
                        "data_timestamp": meta.get("data_timestamp") if meta else None,
                        "data_age_minutes": meta.get("data_age_minutes") if meta else None,
                        "horizon_hours": horizon,
                        "available": True,
                    },
                })
            except Exception as e:
                stations_out.append({
                    "station": st,
                    "location": STATION_COORDS.get(st),
                    "error": str(e),
                })

        return jsonify({
            "success": True,
            "pollutant": pollutant,
            "horizon_hours": horizon,
            "stations": stations_out,
            "server_timestamp": datetime.now().isoformat(),
        }), 200

    @api_v2_bp.route("/timeseries", methods=["GET"])
    def timeseries():
        """Devuelve serie temporal para una estación:
        - Últimas 72h de datos observados (del CSV)
        - Forecast a 24/48/72h usando el modelo

        Query params:
            station    (str): nombre de la estación
            pollutant  (str): pm25 | no2 | o3
        """
        station_raw = request.args.get("station")
        pollutant = request.args.get("pollutant", "pm25").lower().strip()

        if not station_raw:
            return jsonify(format_error_response("Falta 'station' en query.", 400)), 400
        if pollutant not in ("pm25", "no2", "o3"):
            return jsonify(format_error_response(
                f"Contaminante inválido '{pollutant}'. Usa pm25, no2 u o3.", 400
            )), 400

        resolved = _resolve_station(station_raw) or station_raw

        # ---- observed data (fuente de verdad: Mongo) ----
        observed, obs_meta = _fetch_observed_from_mongo(resolved, pollutant, hours=72)

        # ---- forecast (predicciones reales del modelo LSTM) ----
        forecast = []
        for h in [0, 24, 48, 72]:
            try:
                # Para horizontes futuros, intentar cache primero
                if h > 0:
                    cached = _get_cached_prediction(resolved, pollutant, h)
                    if cached:
                        forecast.append(cached)
                        continue
                    # Fallback: inferencia en tiempo real con features ajustadas
                    try:
                        real_station, preds, risk_payload, meta = _infer_for_station_horizon(
                            resolved, horizon_hours=h,
                        )
                        pol_info = risk_payload["pollutants"].get(pollutant, {})
                        forecast.append({
                            "horizon_hours": h,
                            "label": f"+{h}h",
                            "value": round(preds.get(pollutant, 0), 2),
                            "level": pol_info.get("level", "bueno"),
                            "color": pol_info.get("color", "#2BB673"),
                            "available": True,
                            "source": "realtime_forecast",
                        })
                        continue
                    except Exception:
                        pass  # caer al caso genérico

                # h=0: inferencia normal con ventana más reciente
                real_station, preds, risk_payload, meta = _infer_for_station(
                    resolved, offset_hours=0
                )
                pol_info = risk_payload["pollutants"].get(pollutant, {})
                forecast.append({
                    "horizon_hours": h,
                    "label": "Ahora" if h == 0 else f"+{h}h",
                    "value": round(preds.get(pollutant, 0), 2),
                    "level": pol_info.get("level", "bueno"),
                    "color": pol_info.get("color", "#2BB673"),
                    "available": True,
                })
            except Exception:
                forecast.append({
                    "horizon_hours": h,
                    "label": "Ahora" if h == 0 else f"+{h}h",
                    "value": None,
                    "level": None,
                    "error": "No se pudo calcular",
                    "available": False,
                })

        return jsonify({
            "success": True,
            "station": resolved,
            "pollutant": pollutant,
            "observed": observed,
            "forecast": forecast,
            "meta": {
                **(obs_meta or {}),
                "observed_source": "mongo",
            },
            "server_timestamp": datetime.now().isoformat(),
        }), 200

    @api_v2_bp.route("/ranking", methods=["GET"])
    def ranking():
        """Top N estaciones por riesgo en un horizonte.

        Query params:
            pollutant (str): pm25 | no2 | o3 (default: pm25)
            horizon   (int): 0 | 24 | 48 | 72
            top       (int): cuántas devolver (default: 7 = todas)
        """
        pollutant = request.args.get("pollutant", "pm25").lower().strip()
        if pollutant not in ("pm25", "no2", "o3"):
            return jsonify(format_error_response(
                f"Contaminante inválido '{pollutant}'.", 400
            )), 400
        try:
            horizon = int(request.args.get("horizon", 0))
        except ValueError:
            horizon = 0
        try:
            top_n = int(request.args.get("top", len(V2_STATIONS)))
        except ValueError:
            top_n = len(V2_STATIONS)

        from src.ml.risk_classifier_v2 import LEVEL_ORDER as _LO

        if horizon not in (0, 24, 48, 72):
            horizon = 0

        entries = []

        for st in V2_STATIONS:
            try:
                if horizon > 0:
                    # Intentar cache, luego fallback a inferencia con horizonte
                    cached = _get_cached_map_entry(st, pollutant, horizon)
                    if cached:
                        pol_level = cached.get("level", "bueno")
                        entries.append({
                            "station": st,
                            "value": cached.get("value", 0),
                            "level": pol_level,
                            "color": cached.get("color", "#2BB673"),
                            "worst": cached.get("worst", {}),
                            "_sort": _LO.get(pol_level, 0),
                            "_value": cached.get("value", 0),
                        })
                        continue
                    real_station, preds, risk_payload, _ = _infer_for_station_horizon(
                        st, horizon_hours=horizon,
                    )
                else:
                    real_station, preds, risk_payload, _ = _infer_for_station(st, offset_hours=0)
                pol_info = risk_payload["pollutants"].get(pollutant, {})
                entries.append({
                    "station": real_station,
                    "value": round(preds.get(pollutant, 0), 2),
                    "level": pol_info.get("level", "bueno"),
                    "color": pol_info.get("color", "#2BB673"),
                    "worst": risk_payload["worst"],
                    "_sort": _LO.get(pol_info.get("level", "bueno"), 0),
                    "_value": preds.get(pollutant, 0),
                })
            except Exception:
                continue

        entries.sort(key=lambda e: (e["_sort"], e["_value"]), reverse=True)
        for e in entries:
            del e["_sort"]
            del e["_value"]

        return jsonify({
            "success": True,
            "pollutant": pollutant,
            "horizon_hours": horizon,
            "ranking": entries[:top_n],
            "meta": {"available": True},
            "server_timestamp": datetime.now().isoformat(),
        }), 200

    # --- Endpoint interno: generar y cachear predicciones para todos los horizontes ---
    @api_v2_bp.route("/_internal/predict_horizons", methods=["POST"])
    def internal_predict_horizons():
        """Genera predicciones para horizontes 0/24/48/72h para todas las estaciones
        y las guarda en MongoDB predictions_cache. Llamado por Node-RED."""
        expected_token = os.environ.get("AIRVLC_INTERNAL_RELOAD_TOKEN", "airvlc-reload-secret")
        provided_token = request.headers.get("X-Internal-Token", "")
        if provided_token != expected_token:
            return jsonify(format_error_response("Token inválido.", 403)), 403

        results = {"stations": {}, "errors": []}
        es_indexer = current_app.config.get("ES_INDEXER_V2")

        # 1. Indexar valores reales más recientes (ground truth) en ES
        #    y capturar el timestamp base (observado) para alinear forecasts.
        base_ts_by_station: dict[str, datetime] = {}
        if es_indexer:
            try:
                client, coll = _mongo_air_collection()
                if coll is not None:
                    for st in V2_STATIONS:
                        doc = coll.find_one({"estacion": st}, sort=[("fecha", -1)])
                        if doc and "fecha" in doc:
                            ts = doc["fecha"]
                            if hasattr(ts, "tzinfo") and ts.tzinfo is None:
                                ts = ts.replace(tzinfo=timezone.utc)
                            base_ts_by_station[st] = ts.astimezone(timezone.utc)
                            iso_ts = ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
                            doc_id = ESIndexer.build_document_id("v2", "actual", st, "-1", iso_ts)
                            es_indexer.index_prediction({
                                "document_id": doc_id,
                                "station": st,
                                "target_timestamp": iso_ts,
                                "generated_at": iso_ts,
                                "horizon_hours": -1,  # -1 significa DATO REAL
                                "pm25_actual": doc.get("pm25"),
                                "no2_actual": doc.get("no2"),
                                "o3_actual": doc.get("o3"),
                                "prediction_type": "actual",
                                "source": "mongo_realtime"
                            })
                    client.close()
            except Exception as e:
                print(f"⚠️ Error indexando actuals en ES: {e}")

        # 2. Generar y cachear predicciones
        for st in V2_STATIONS:
            results["stations"][st] = {}
            for h in [0, 24, 48, 72]:
                try:
                    if h == 0:
                        real_station, preds, risk_payload, meta = _infer_for_station(st, offset_hours=0)
                    else:
                        real_station, preds, risk_payload, meta = _infer_for_station_horizon(
                            st, horizon_hours=h,
                        )
                    _save_prediction_cache(real_station, h, preds, risk_payload)

                    # Enviar a Elasticsearch para Kibana (target_timestamp)
                    if es_indexer:
                        # Alinear el timestamp objetivo al timestamp OBSERVADO más reciente.
                        # Esto hace la ingesta idempotente si Node-RED reintenta el mismo ciclo.
                        base_dt = base_ts_by_station.get(real_station) or base_ts_by_station.get(st)
                        if base_dt is None:
                            now = datetime.now(timezone.utc)
                            base_dt = now.replace(minute=0, second=0, microsecond=0)
                        target_dt = base_dt + timedelta(hours=h)
                        target_ts = target_dt.isoformat().replace("+00:00", "Z")
                        
                        doc_id = ESIndexer.build_document_id("v2", "forecast", real_station, str(h), target_ts)
                        es_payload = {
                            "document_id": doc_id,
                            "station": real_station,
                            "pm25_pred": round(preds["pm25"], 2),
                            "no2_pred": round(preds["no2"], 2),
                            "o3_pred": round(preds["o3"], 2),
                            "prediction_pm25": round(preds["pm25"], 2), # legacy attr
                            "target_timestamp": target_ts,
                            "horizon_hours": h,
                            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                            "model_used": "LSTM_Attention_Multi",
                            "risk_pm25": risk_payload["pollutants"].get("pm25", {}).get("level"),
                            "risk_no2": risk_payload["pollutants"].get("no2", {}).get("level"),
                            "risk_o3": risk_payload["pollutants"].get("o3", {}).get("level"),
                            "worst_pollutant": risk_payload.get("worst", {}).get("pollutant"),
                            "worst_level": risk_payload.get("worst", {}).get("level"),
                            "prediction_type": "forecast",
                            "source": "api_predict_horizons"
                        }
                        es_indexer.index_prediction(es_payload)

                    results["stations"][st][f"+{h}h"] = {
                        "pm25": round(preds["pm25"], 2),
                        "no2": round(preds["no2"], 2),
                        "o3": round(preds["o3"], 2),
                        "worst_level": risk_payload.get("worst", {}).get("level"),
                    }
                except Exception as e:
                    results["errors"].append(f"{st} h={h}: {str(e)}")

        return jsonify({
            "success": True,
            "message": f"Predicciones generadas para {len(V2_STATIONS)} estaciones × 4 horizontes.",
            "results": results,
            "server_timestamp": datetime.now().isoformat(),
        }), 200

    return api_v2_bp


def register_routes_v2(app):
    """Registra las rutas v2 en la app Flask."""
    bp = create_api_v2_blueprint()
    app.register_blueprint(bp)

