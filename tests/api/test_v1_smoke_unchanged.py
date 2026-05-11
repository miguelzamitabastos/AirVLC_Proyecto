from flask import Flask

from src.api.routes import register_routes


def test_v1_endpoints_exist_and_fail_without_models():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["MODEL_LOADER"] = None
    app.config["ES_INDEXER"] = None

    register_routes(app)
    client = app.test_client()

    # /api/health returns 503 when no models loaded (existing behavior)
    r = client.get("/api/health")
    assert r.status_code in {200, 503}

    r = client.post("/api/predict", json={"features": [[0.0] * 20] * 24})
    assert r.status_code == 503

