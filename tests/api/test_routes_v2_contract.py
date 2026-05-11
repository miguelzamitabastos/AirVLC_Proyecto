import numpy as np
from flask import Flask

from src.api.routes_v2 import create_api_v2_blueprint


class _FakeLoader:
    def __init__(self):
        self.models = {"LSTM_Attention_Multi": object()}
        self.best_model_name = "LSTM_Attention_Multi"
        self.best_model = object()

    @property
    def is_ready(self):
        return True

    def predict(self, X, model_name=None):
        # Return scaled y for pm25/no2/o3 in [0,1]
        return np.array([[0.5, 0.25, 0.75]], dtype=np.float32)


class _FakeExtractor:
    def get_features(self, station_name):
        return np.zeros((1, 24, 44), dtype=np.float32), "Politécnico"

    def inverse_transform_predictions(self, y_scaled):
        # Deterministic values (µg/m³)
        return {"pm25": 15.0, "no2": 60.0, "o3": 120.0}


class _FakeChatbot:
    def process_message(self, text, session_id, model_loader=None):
        return {"reply": "ok", "intent": "ConsultarCalidad"}


def _make_app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["MODEL_LOADER"] = _FakeLoader()
    app.config["ES_INDEXER_V2"] = None

    bp = create_api_v2_blueprint(feature_extractor=_FakeExtractor(), chatbot=_FakeChatbot())
    app.register_blueprint(bp)
    return app


def test_v2_predict_contract_station():
    app = _make_app()
    client = app.test_client()
    r = client.post("/api/v2/predict", json={"station": "Politécnico"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["success"] is True
    assert data["predictions"]["unit"] == "µg/m³"
    assert set(data["predictions"].keys()) >= {"pm25", "no2", "o3", "unit"}


def test_v2_risk_contract_station():
    app = _make_app()
    client = app.test_client()
    r = client.post("/api/v2/risk", json={"station": "Politécnico"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["success"] is True
    assert "worst" in data
    assert data["worst"]["pollutant"] in {"pm25", "no2", "o3"}
    assert "pollutants" in data
    assert "reply_text" in data

