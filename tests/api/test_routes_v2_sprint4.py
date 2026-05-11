"""
Sprint 4 — contratos de los nuevos endpoints v2:
- POST /api/v2/profile/recommend
- POST /api/v2/route

Usamos los mismos fakes que `test_routes_v2_contract.py` para no
depender de TF/pandas en CI.
"""

import numpy as np
import pytest
from flask import Flask

from src.api.routes_v2 import V2_STATIONS, create_api_v2_blueprint


class _FakeLoader:
    def __init__(self):
        self.models = {"LSTM_Attention_Multi": object()}
        self.best_model_name = "LSTM_Attention_Multi"
        self.best_model = object()
        self._calls = 0

    @property
    def is_ready(self):
        return True

    def predict(self, X, model_name=None):
        # Variamos un poco la salida para que distintos tramos den distintos worsts
        self._calls += 1
        # 0: pm25 ~ bueno, no2 ~ moderado/malo, o3 ~ moderado
        return np.array([[0.10 + 0.02 * (self._calls % 3),
                          0.40 + 0.05 * (self._calls % 3),
                          0.55 + 0.02 * (self._calls % 3)]], dtype=np.float32)


class _FakeExtractor:
    def get_features(self, station_name):
        # El blueprint normaliza el nombre, devolvemos lo que pidan tal cual
        return np.zeros((1, 24, 44), dtype=np.float32), station_name

    def inverse_transform_predictions(self, y_scaled):
        # Convertimos los "escalados" a µg/m³ deterministas según los valores
        arr = np.asarray(y_scaled).reshape(-1)
        return {
            "pm25": float(10.0 + 30.0 * arr[0]),
            "no2": float(50.0 + 80.0 * arr[1]),
            "o3": float(80.0 + 60.0 * arr[2]),
        }


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


def test_profile_recommend_minimal():
    app = _make_app()
    client = app.test_client()
    r = client.post("/api/v2/profile/recommend", json={"station": "Politécnico"})
    assert r.status_code == 200, r.get_json()
    data = r.get_json()
    assert data["success"] is True
    assert "recommendation_text" in data
    assert "color" in data
    assert "level_adjusted" in data
    assert "worst" in data
    assert "predictions" in data and data["predictions"]["unit"] == "µg/m³"


def test_profile_recommend_sensitive_profile_color():
    app = _make_app()
    client = app.test_client()
    body = {
        "station": "Politécnico",
        "activity": "correr",
        "profile": {"age": "adulto", "condition": "asma", "sensitivity": "alta"},
    }
    r = client.post("/api/v2/profile/recommend", json=body)
    assert r.status_code == 200, r.get_json()
    data = r.get_json()
    assert data["is_sensitive_profile"] is True
    assert data["profile_used"]["condition"] == "asma"
    # Nunca devolvemos None ni vacío en el texto
    assert isinstance(data["recommendation_text"], str)
    assert len(data["recommendation_text"]) > 10


def test_profile_recommend_missing_station():
    app = _make_app()
    client = app.test_client()
    r = client.post("/api/v2/profile/recommend", json={})
    assert r.status_code == 400
    assert r.get_json()["success"] is False


def test_route_basic_contract():
    app = _make_app()
    client = app.test_client()
    r = client.post(
        "/api/v2/route",
        json={"from_station": "Francia", "to_station": "Universidad Politécnica"},
    )
    assert r.status_code == 200, r.get_json()
    data = r.get_json()
    assert data["success"] is True
    segs = data["segments"]
    assert isinstance(segs, list)
    assert len(segs) >= 2
    # El primer y último segmento son las estaciones pedidas (canónicas)
    assert segs[0]["station"] == "Francia"
    assert segs[-1]["station"] == "Universidad Politécnica"
    # Cada segmento tiene predicciones y worst
    for s in segs:
        assert s["predictions"]["unit"] == "µg/m³"
        assert s["worst"]["pollutant"] in {"pm25", "no2", "o3"}
        assert s["location"] is not None  # tiene lat/lon


def test_route_alias_resolution():
    app = _make_app()
    client = app.test_client()
    r = client.post("/api/v2/route", json={"from_station": "politecnico", "to_station": "puerto"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["from_station"] == "Universidad Politécnica"
    assert data["to_station"] == "Puerto Valencia"


def test_route_unknown_station():
    app = _make_app()
    client = app.test_client()
    r = client.post("/api/v2/route", json={"from_station": "Foo", "to_station": "Bar"})
    assert r.status_code == 400
    assert r.get_json()["success"] is False


@pytest.mark.parametrize("station", V2_STATIONS)
def test_route_same_origin_destination_returns_single_segment(station):
    app = _make_app()
    client = app.test_client()
    r = client.post("/api/v2/route", json={"from_station": station, "to_station": station})
    assert r.status_code == 200
    data = r.get_json()
    assert len(data["segments"]) >= 1
    assert data["segments"][0]["station"] == station
