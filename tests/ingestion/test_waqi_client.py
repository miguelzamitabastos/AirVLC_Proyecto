"""Tests cliente WAQI (mock HTTP)."""

import os
import sys
from unittest.mock import Mock, patch

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)


def _mock_response(body: dict):
    r = Mock()
    r.status_code = 200
    r.json.return_value = body
    r.raise_for_status = Mock()
    return r


@patch("src.ingestion.waqi_air_quality_client.requests.get")
def test_skips_when_o3_missing(mock_get, monkeypatch):
    monkeypatch.setenv("WAQI_TOKEN", "test-token")
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017/test")

    body = {
        "status": "ok",
        "data": {
            "time": {"iso": "2026-05-07T15:00:00Z"},
            "iaqi": {"pm25": {"v": 50}, "no2": {"v": 50}},
            "city": {"name": "X"},
        },
    }
    mock_get.return_value = _mock_response(body)

    with patch("src.ingestion.waqi_air_quality_client.MongoClient"):
        import src.ingestion.waqi_air_quality_client as mod

        with patch.object(mod, "CANONICAL_STATIONS", ["Francia"]):
            stats = mod.fetch_waqi_air_quality(hours=24)

    assert stats["parsed"] == 0
