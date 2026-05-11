"""
Tests Sprint 5 — Data Freshness en las respuestas v2.

Verifica que los endpoints /predict y /risk devuelven:
- data_timestamp (ISO string)
- data_age_minutes (int >= 0)
- data_window_start (ISO string)
- server_timestamp (ISO string)
"""

import json
from datetime import datetime

import pytest


# ---- fixtures reutilizables -------------------------------------------------

def _make_fake_feature_extractor():
    """Devuelve un FeatureExtractorV2 mock que no necesita CSV ni scaler."""
    import numpy as np

    class FakeExtractor:
        def get_features(self, station_name):
            meta = {
                "data_timestamp": "2026-05-07T12:00:00",
                "data_window_start": "2026-05-06T13:00:00",
                "data_age_minutes": 42,
            }
            features = np.random.rand(1, 24, 44).astype(np.float32)
            return features, station_name or "Pista de Silla", meta

        def inverse_transform_predictions(self, y_scaled):
            return {"pm25": 12.5, "no2": 25.0, "o3": 60.0}

        def reload(self):
            pass

    return FakeExtractor()


def _make_fake_loader():
    """Devuelve un ModelLoader mock."""
    import numpy as np

    class FakeLoader:
        is_ready = True
        best_model_name = "LSTM_Attention_Multi"
        models = {"LSTM_Attention_Multi": True}

        def predict(self, features, model_name=None):
            return np.array([[0.3, 0.5, 0.7]], dtype=np.float32)

    return FakeLoader()


@pytest.fixture
def app():
    """Crea una app Flask de prueba con mocks."""
    import sys
    import os
    ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    sys.path.insert(0, ROOT_DIR)

    from flask import Flask
    from src.api.routes_v2 import create_api_v2_blueprint

    fe = _make_fake_feature_extractor()
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['MODEL_LOADER'] = _make_fake_loader()

    bp = create_api_v2_blueprint(feature_extractor=fe)
    app.register_blueprint(bp)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


# ---- tests -------------------------------------------------------------------

class TestDataFreshness:
    """Verifica que los endpoints v2 incluyen campos de frescura."""

    def test_predict_includes_freshness(self, client):
        resp = client.post(
            "/api/v2/predict",
            data=json.dumps({"station": "Pista de Silla"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True

        # Campos de frescura
        assert "data_timestamp" in body
        assert "data_age_minutes" in body
        assert "data_window_start" in body
        assert "server_timestamp" in body

        # data_age_minutes debe ser >= 0
        assert isinstance(body["data_age_minutes"], int)
        assert body["data_age_minutes"] >= 0

        # data_timestamp debe ser parseable como ISO
        dt = datetime.fromisoformat(body["data_timestamp"])
        assert dt is not None

    def test_risk_includes_freshness(self, client):
        resp = client.post(
            "/api/v2/risk",
            data=json.dumps({"station": "Francia"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True

        assert "data_timestamp" in body
        assert "data_age_minutes" in body
        assert body["data_age_minutes"] >= 0

    def test_predict_direct_features_no_freshness(self, client):
        """Cuando se envían features directos, no hay meta de frescura."""
        import numpy as np
        features = np.random.rand(24, 44).tolist()
        resp = client.post(
            "/api/v2/predict",
            data=json.dumps({"features": features}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        body = resp.get_json()
        # data_timestamp no debería estar cuando se usan features directos
        assert body.get("data_timestamp") is None

    def test_server_timestamp_is_recent(self, client):
        resp = client.post(
            "/api/v2/predict",
            data=json.dumps({"station": "Francia"}),
            content_type="application/json",
        )
        body = resp.get_json()
        server_ts = datetime.fromisoformat(body["server_timestamp"])
        # Debe ser de los últimos 10 segundos
        assert (datetime.now() - server_ts).total_seconds() < 10


class TestReloadEndpoint:
    """Verifica el endpoint POST /api/v2/_internal/reload."""

    def test_reload_without_token_returns_403(self, client):
        resp = client.post("/api/v2/_internal/reload")
        assert resp.status_code == 403

    def test_reload_with_wrong_token_returns_403(self, client):
        resp = client.post(
            "/api/v2/_internal/reload",
            headers={"X-Internal-Token": "wrong-token"},
        )
        assert resp.status_code == 403

    def test_reload_with_correct_token_returns_200(self, client):
        # Default token es "airvlc-reload-secret"
        resp = client.post(
            "/api/v2/_internal/reload",
            headers={"X-Internal-Token": "airvlc-reload-secret"},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert "server_timestamp" in body
