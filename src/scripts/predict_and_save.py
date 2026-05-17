"""
Autonomous prediction pipeline for GitHub Actions.

This script mirrors the behavior of the internal v2 endpoint:
POST /api/v2/_internal/predict_horizons

It:
  - Loads the v2 multitarget model via ModelLoader
  - Loads FeatureExtractorV2 (dataset + scaler)
  - Iterates over canonical stations and horizons (0/24/48/72)
  - Generates predictions, computes risk payload, and upserts into MongoDB
    collection: airvlc_db.predictions_cache

No Flask/FastAPI is used; this is pure Python.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple


# ---------------------------------------------------------------------------
# Path bootstrap (repo-root import style)
# ---------------------------------------------------------------------------
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)


# Optional dotenv support (useful locally; in GitHub Actions env vars are set)
try:  # pragma: no cover
    from dotenv import load_dotenv

    load_dotenv(os.path.join(ROOT_DIR, ".env"))
except Exception:  # pragma: no cover
    pass


# ---------------------------------------------------------------------------
# Canonical stations & horizons (must match routes_v2.py behavior)
# ---------------------------------------------------------------------------
V2_STATIONS = [
    "Francia",
    "Molí del Sol",
    "Pista de Silla",
    "Puerto Moll Trans. Ponent",
    "Puerto Valencia",
    "Puerto llit antic Túria",
    "Universidad Politécnica",
]

HORIZONS_HOURS = [0, 24, 48, 72]
MODEL_NAME = "LSTM_Attention_Multi"


def _append_predictions_log_v2(
    real_station: str,
    horizon_hours: int,
    preds: Dict[str, float],
    model_name: str = MODEL_NAME,
) -> None:
    """Append one line to data/logs/predictions_log.csv (same schema as API)."""
    try:
        log_dir = os.path.join(ROOT_DIR, "data", "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "predictions_log.csv")
        file_exists = os.path.exists(log_file)
        with open(log_file, "a") as f:
            if not file_exists:
                f.write(
                    "timestamp,station,horizon_hours,model,pm25,no2,o3,"
                    "pm25_rmse,no2_rmse,o3_rmse,pm25_r2,no2_r2,o3_r2\n"
                )
            # The endpoint version also includes metrics columns; here we leave them empty
            # to keep schema compatible without importing V2_MODEL_METRICS.
            f.write(
                f"{datetime.now().isoformat()},{real_station},{horizon_hours},{model_name},"
                f"{preds['pm25']},{preds['no2']},{preds['o3']},"
                f"{''},{''},{''},{''},{''},{''}\n"
            )
    except Exception as e:
        print(f"⚠️ Error guardando log de predicción: {e}")


def _mongo_predictions_cache() -> Tuple[object | None, object | None]:
    """Return (client, collection) for airvlc_db.predictions_cache or (None, None)."""
    mongo_uri = (os.getenv("MONGO_URI") or "").strip()
    if not mongo_uri:
        return None, None
    try:
        from pymongo import MongoClient
    except Exception as e:  # pragma: no cover
        raise RuntimeError(f"pymongo no disponible: {e}") from e
    client = MongoClient(mongo_uri)
    db = client["airvlc_db"]
    return client, db["predictions_cache"]


def _save_prediction_cache(station: str, horizon_hours: int, preds: dict, risk_payload: dict) -> None:
    """Upsert prediction cache document (same semantics as routes_v2._save_prediction_cache)."""
    client, coll = _mongo_predictions_cache()
    if coll is None:
        raise RuntimeError("Mongo no configurado (falta MONGO_URI).")
    try:
        now = datetime.now(timezone.utc)
        doc = {
            "station": station,
            "horizon_hours": int(horizon_hours),
            "predictions": {
                "pm25": round(float(preds["pm25"]), 2),
                "no2": round(float(preds["no2"]), 2),
                "o3": round(float(preds["o3"]), 2),
            },
            "pollutants": risk_payload.get("pollutants", {}),
            "worst": risk_payload.get("worst", {}),
            "model_used": MODEL_NAME,
            "generated_at": now,
            "expires_at": now + timedelta(hours=2),
        }
        coll.update_one(
            {"station": station, "horizon_hours": int(horizon_hours)},
            {"$set": doc},
            upsert=True,
        )
    finally:
        try:
            client.close()
        except Exception:
            pass


def _infer_one(feature_extractor, model_loader, risk_classifier, station: str, horizon_hours: int) -> dict:
    """Compute preds+risk for one station/horizon (mirrors routes_v2 logic)."""
    if horizon_hours == 0:
        features, real_station, meta = feature_extractor.get_features(station, offset_hours=0)
    else:
        features, real_station, meta = feature_extractor.get_features_for_horizon(
            station, horizon_hours=int(horizon_hours)
        )

    y_scaled = model_loader.predict(features, model_name=MODEL_NAME)
    preds = feature_extractor.inverse_transform_predictions(y_scaled)
    risk_payload = risk_classifier.classify_multi(
        pm25=preds["pm25"], no2=preds["no2"], o3=preds["o3"], station=real_station
    )

    _append_predictions_log_v2(
        real_station,
        int(horizon_hours),
        {"pm25": preds["pm25"], "no2": preds["no2"], "o3": preds["o3"]},
        model_name=MODEL_NAME,
    )

    return {
        "station": real_station,
        "horizon_hours": int(horizon_hours),
        "preds": preds,
        "risk": risk_payload,
        "meta": meta or {},
    }


def main() -> int:
    mongo_uri = (os.getenv("MONGO_URI") or "").strip()
    if not mongo_uri:
        print("❌ Falta MONGO_URI en variables de entorno.")
        return 2

    models_dir = os.path.join(ROOT_DIR, "models")

    print("\n" + "=" * 72)
    print("🧠 AirVLC — predict_and_save (v2 horizons → Mongo predictions_cache)")
    print("=" * 72)
    print(f"📁 ROOT_DIR: {ROOT_DIR}")
    print(f"📦 models_dir: {models_dir}")
    print(f"🗄️  Mongo: {'set' if mongo_uri else 'missing'}")
    print(f"🎯 stations: {len(V2_STATIONS)} · horizons: {HORIZONS_HOURS}")

    from src.api.feature_extractor_v2 import FeatureExtractorV2
    from src.api.model_loader import ModelLoader
    from src.ml.risk_classifier_v2 import RiskClassifierV2

    # 1) Instantiate pipeline components (same roles as API)
    feature_extractor = FeatureExtractorV2()
    model_loader = ModelLoader(models_dir)
    if not getattr(model_loader, "is_ready", False):
        print("❌ ModelLoader no está listo (no se cargó ningún modelo).")
        return 3
    risk_classifier = RiskClassifierV2()

    # Sincronizar observaciones recientes de Mongo (p. ej. WAQI → Puerto Valencia).
    try:
        inject_out = feature_extractor.inject_latest_from_mongo()
        print(f"🔄 Mongo → FeatureExtractorV2: {inject_out}")
    except Exception as e:
        print(f"⚠️ Mongo inject en predict_and_save: {e}")

    # 2) Iterate stations/horizons, infer and save
    results: dict = {"stations": {}, "errors": []}

    for st in V2_STATIONS:
        results["stations"][st] = {}
        for h in HORIZONS_HOURS:
            try:
                out = _infer_one(feature_extractor, model_loader, risk_classifier, st, h)
                _save_prediction_cache(out["station"], h, out["preds"], out["risk"])
                results["stations"][st][f"+{h}h"] = {
                    "pm25": round(float(out["preds"]["pm25"]), 2),
                    "no2": round(float(out["preds"]["no2"]), 2),
                    "o3": round(float(out["preds"]["o3"]), 2),
                    "worst_level": out["risk"].get("worst", {}).get("level"),
                }
                print(
                    f"✅ {out['station']:<28} h={h:<2}  "
                    f"pm25={results['stations'][st][f'+{h}h']['pm25']:<6}  "
                    f"no2={results['stations'][st][f'+{h}h']['no2']:<6}  "
                    f"o3={results['stations'][st][f'+{h}h']['o3']:<6}  "
                    f"worst={results['stations'][st][f'+{h}h']['worst_level']}"
                )
            except Exception as e:
                msg = f"{st} h={h}: {e}"
                results["errors"].append(msg)
                print(f"❌ {msg}")

    print("\n" + "-" * 72)
    print(
        f"Done. stations={len(V2_STATIONS)} horizons={len(HORIZONS_HOURS)} "
        f"errors={len(results['errors'])}"
    )
    if results["errors"]:
        # Non-zero so the GitHub Action fails visibly.
        return 4
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

