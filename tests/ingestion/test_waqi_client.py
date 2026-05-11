"""Tests cliente WAQI (mock HTTP)."""

import os
import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)


def _mock_response(body: dict):
    r = Mock()
    r.status_code = 200
    r.json.return_value = body
    r.raise_for_status = Mock()
    return r


@patch("src.ingestion.waqi_air_quality_client.requests.get")
def test_fetch_waqi_inserts_one_station(mock_get, monkeypatch):
    monkeypatch.setenv("WAQI_TOKEN", "test-token")
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017/test")

    iso_now = "2026-05-07T15:00:00Z"
    body = {
        "status": "ok",
        "data": {
            "idx": 42,
            "time": {"iso": iso_now},
            "iaqi": {"pm25": {"v": 50}, "no2": {"v": 50}, "o3": {"v": 50}},
            "city": {"name": "Valencia Test"},
        },
    }
    mock_get.return_value = _mock_response(body)

    mock_bulk = MagicMock()
    mock_bulk.upserted_count = 1
    mock_bulk.modified_count = 0

    mock_coll = MagicMock()
    mock_coll.bulk_write.return_value = mock_bulk

    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_coll

    mock_client = MagicMock()
    mock_client.__getitem__.return_value = mock_db

    with patch("src.ingestion.waqi_air_quality_client.MongoClient", return_value=mock_client):
        import src.ingestion.waqi_air_quality_client as mod

        with patch.object(mod, "CANONICAL_STATIONS", ["Francia"]):
            stats = mod.fetch_waqi_air_quality(hours=24)

    assert stats["parsed"] == 1
    assert stats["inserted"] == 1


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
