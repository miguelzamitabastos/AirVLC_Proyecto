"""
Tests Sprint 5 — Valencia Air Quality Client (B.1)

Verifica:
- Normalización de nombres de estación
- Parser idempotente con fixture JSON
"""

import pytest
import sys
import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT_DIR)

from src.ingestion.valencia_air_quality_client import (
    normalize_station,
    parse_records,
    VALID_STATIONS,
)


# ---- Fixtures ----------------------------------------------------------------

FIXTURE_RECORDS = [
    {
        "estacion": "Av. Francia",
        "fecha": "2026-05-07T10:00:00+00:00",
        "pm2_5": "12.5",
        "no2": 30.0,
        "o3": "55,5",
    },
    {
        "estacion": "Pista de Silla",
        "fecha": "2026-05-07T10:00:00+00:00",
        "pm2_5": 8.0,
        "no2": None,
        "o3": 45.0,
    },
    {
        "estacion": "Estación Desconocida XYZ",
        "fecha": "2026-05-07T10:00:00+00:00",
        "pm2_5": 100.0,
        "no2": 100.0,
        "o3": 100.0,
    },
    {
        # Sin fecha → se descarta
        "estacion": "Francia",
        "pm2_5": 10.0,
    },
]


# ---- Tests -------------------------------------------------------------------

class TestNormalizeStation:
    """Verifica la normalización de nombres de estación."""

    def test_canonical_match(self):
        assert normalize_station("Av. Francia") == "Francia"
        assert normalize_station("av. francia") == "Francia"

    def test_known_aliases(self):
        assert normalize_station("Pista de Silla") == "Pista de Silla"
        assert normalize_station("Pista Silla") == "Pista de Silla"
        assert normalize_station("politecnico") == "Universidad Politécnica"

    def test_case_insensitive(self):
        assert normalize_station("MOLÍ DEL SOL") == "Molí del Sol"
        assert normalize_station("moli del sol") == "Molí del Sol"

    def test_unknown_returns_none(self):
        assert normalize_station("Estación Desconocida XYZ") is None
        assert normalize_station("") is None

    def test_all_valid_stations_recognized(self):
        """Cada estación canónica debe reconocerse por su nombre exacto."""
        for st in VALID_STATIONS:
            result = normalize_station(st)
            assert result is not None, f"Estación '{st}' no reconocida"


class TestParseRecords:
    """Verifica el parser de registros crudos."""

    def test_valid_records_parsed(self):
        parsed = parse_records(FIXTURE_RECORDS)
        # Solo 2 deben pasar (Francia + Pista de Silla)
        # El desconocido se descarta, el sin fecha se descarta
        assert len(parsed) == 2

    def test_station_names_canonical(self):
        parsed = parse_records(FIXTURE_RECORDS)
        stations = {d["estacion"] for d in parsed}
        assert stations <= VALID_STATIONS

    def test_contaminants_are_float(self):
        parsed = parse_records(FIXTURE_RECORDS)
        for doc in parsed:
            if doc["pm25"] is not None:
                assert isinstance(doc["pm25"], float)
            if doc["no2"] is not None:
                assert isinstance(doc["no2"], float)

    def test_comma_decimal_parsed(self):
        """'55,5' debe convertirse a 55.5 (float)."""
        parsed = parse_records(FIXTURE_RECORDS)
        francia = [d for d in parsed if d["estacion"] == "Francia"][0]
        assert francia["o3"] == 55.5

    def test_idempotent(self):
        """Parsear dos veces el mismo input produce el mismo resultado."""
        parsed1 = parse_records(FIXTURE_RECORDS)
        parsed2 = parse_records(FIXTURE_RECORDS)
        assert len(parsed1) == len(parsed2)
        for d1, d2 in zip(parsed1, parsed2):
            assert d1["estacion"] == d2["estacion"]
            assert d1["fecha_iso"] == d2["fecha_iso"]
