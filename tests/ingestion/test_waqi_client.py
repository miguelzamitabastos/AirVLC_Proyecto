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

        stats = mod.fetch_waqi_air_quality(hours=24)

    assert stats["parsed"] == 0


@patch("src.ingestion.waqi_air_quality_client.requests.get")
def test_build_document_sets_is_canonical_v2(mock_get, monkeypatch):
    monkeypatch.setenv("WAQI_TOKEN", "test-token")

    body = {
        "status": "ok",
        "data": {
            "time": {"iso": "2026-05-17T08:00:00Z"},
            "iaqi": {"pm25": {"v": 30}, "no2": {"v": 40}, "o3": {"v": 35}},
            "city": {"name": "Puerto Valencia"},
        },
    }
    mock_get.return_value = _mock_response(body)

    import src.ingestion.waqi_air_quality_client as mod

    doc = mod.build_document("Puerto Valencia", body["data"], hours=24)
    assert doc is not None
    assert doc["is_canonical_v2"] is True
    assert doc["estacion"] == "Puerto Valencia"
    assert doc["source"] == "waqi"


def test_parse_time_from_waqi_example_payload():
    import src.ingestion.waqi_air_quality_client as mod

    data = {
        "time": {
            "s": "2026-05-17 17:00:00",
            "tz": "+08:00",
            "iso": "2026-05-17T17:00:00+08:00",
        },
        "iaqi": {"pm25": {"v": 30}, "no2": {"v": 11}, "o3": {"v": 9}},
        "city": {"name": "Beijing (北京)"},
    }
    dt = mod._parse_time_iso(data)
    assert dt is not None
    assert dt.year == 2026 and dt.month == 5 and dt.day == 17


@patch("src.ingestion.waqi_air_quality_client.fetch_station_payload", return_value=None)
def test_fetch_waqi_for_stations_rejects_non_fallback(mock_fetch):
    """Solo estaciones en WAQI_FALLBACK_STATIONS; no requiere WAQI_TOKEN ni red."""
    import src.ingestion.waqi_air_quality_client as mod

    out = mod.fetch_waqi_for_stations(["Francia", "Puerto Valencia"], hours=24)
    assert out.get("stations") == ["Puerto Valencia"]
    mock_fetch.assert_called_once_with("Puerto Valencia")
