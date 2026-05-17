"""
Tests Sprint 8 — GVA RVVCCA CSV Client

Verifica:
- Parseo del CSV oficial (formato real adjuntado por el usuario)
- Mapeo a las 7 estaciones canónicas del modelo v2
- Extracción de valores con unidad ("12 µg/m³" → 12.0)
- Filtro de outliers contra historial mock
- Estructura del documento listo para Mongo
"""

from __future__ import annotations

import os
import sys

import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)

from src.ingestion.gva_rvvcca_csv_client import (
    GVA_ABSENT_CANONICAL_STATIONS,
    _extract_number,
    _is_outlier,
    parse_row,
    read_csv_text,
    resolve_canonical_station,
    supplement_missing_canonical_from_waqi,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------
SAMPLE_CSV_PATH = os.path.join(ROOT_DIR, "0503_CalidadAire.csv")


@pytest.fixture(scope="module")
def csv_rows() -> list[dict]:
    if not os.path.exists(SAMPLE_CSV_PATH):
        pytest.skip(f"Fixture {SAMPLE_CSV_PATH} no encontrado")
    with open(SAMPLE_CSV_PATH, "r", encoding="utf-8-sig") as f:
        return read_csv_text(f.read())


# ---------------------------------------------------------------------------
# Helpers de parsing
# ---------------------------------------------------------------------------
class TestExtractNumber:
    def test_with_unit(self):
        assert _extract_number("12 µg/m³") == 12.0

    def test_with_decimal_comma(self):
        assert _extract_number("0,5 mg/m³") == 0.5

    def test_with_decimal_dot(self):
        assert _extract_number("1.7 µg/m³") == 1.7

    def test_empty(self):
        assert _extract_number("") is None
        assert _extract_number(None) is None
        assert _extract_number("SIN DATOS") is None
        assert _extract_number("SENSE DADES") is None

    def test_negative(self):
        assert _extract_number("-3 µg/m³") == -3.0


class TestCanonicalResolution:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("València - Av. França", "Francia"),
            ("Valencia - Av. Franca", "Francia"),
            ("València - Molí del Sol", "Molí del Sol"),
            ("València - Pista de Silla", "Pista de Silla"),
            ("València - Politècnic", "Universidad Politécnica"),
            ("València Port llit antic Túria", "Puerto llit antic Túria"),
            ("Val Port Moll  Ponent", "Puerto Moll Trans. Ponent"),  # doble espacio CSV
            ("Val Port Moll Ponent", "Puerto Moll Trans. Ponent"),
        ],
    )
    def test_matches(self, raw, expected):
        assert resolve_canonical_station(raw) == expected

    def test_no_match_returns_none(self):
        assert resolve_canonical_station("València Olivereta") is None
        assert resolve_canonical_station("Castelló - Grau") is None
        assert resolve_canonical_station("") is None


# ---------------------------------------------------------------------------
# Parseo de filas reales
# ---------------------------------------------------------------------------
class TestParseRow:
    def test_valencia_moli_del_sol(self, csv_rows):
        rows = [r for r in csv_rows if "Molí del Sol" in (r.get("stationname") or "")]
        assert rows, "Fixture sin estación Molí del Sol"
        doc = parse_row(rows[0])
        assert doc is not None
        assert doc["estacion"] == "Molí del Sol"
        assert doc["is_canonical_v2"] is True
        assert doc["station_id"] == "46250048"
        assert doc["municipality"] == "Valencia"
        assert doc["pm25"] == 5.0
        assert doc["no2"] == 21.0
        assert doc["o3"] == 43.0
        assert doc["location"]["type"] == "Point"
        assert doc["location"]["coordinates"][0] == pytest.approx(-0.40855865, rel=1e-3)
        assert doc["source"] == "gva_rvvcca_csv"
        assert doc["is_synthetic"] is False

    def test_non_canonical_keeps_gva_name(self, csv_rows):
        rows = [r for r in csv_rows if "Olivereta" in (r.get("stationname") or "")]
        assert rows
        doc = parse_row(rows[0])
        assert doc is not None
        assert doc["is_canonical_v2"] is False
        assert doc["estacion"] == "València Olivereta"

    def test_missing_fields_returns_none(self):
        bad = {"stationid": "", "stationname": "", "timeinstant": ""}
        assert parse_row(bad) is None


# ---------------------------------------------------------------------------
# Outlier filter
# ---------------------------------------------------------------------------
class TestOutlierFilter:
    def test_spike_detected(self):
        history = [10.0, 11.0, 9.0, 10.5, 11.2]
        assert _is_outlier(500.0, history) is True

    def test_normal_value_not_flagged(self):
        history = [10.0, 11.0, 9.0, 10.5, 11.2]
        assert _is_outlier(12.0, history) is False

    def test_low_floor_skips_check(self):
        history = [0.5, 0.6, 0.4]
        # Cuando la mediana < 2, no marcamos pico (sensor en cero estructural).
        assert _is_outlier(10.0, history) is False

    def test_short_history_skips(self):
        assert _is_outlier(500.0, [10.0, 12.0]) is False


class TestWaqiSupplement:
    def test_puerto_valencia_marked_gva_absent(self):
        from src.ingestion.waqi_station_map import WAQI_FALLBACK_STATIONS

        assert GVA_ABSENT_CANONICAL_STATIONS == WAQI_FALLBACK_STATIONS
        assert "Puerto Valencia" in GVA_ABSENT_CANONICAL_STATIONS

    def test_skips_when_already_present(self):
        out = supplement_missing_canonical_from_waqi(
            present_canonical={"Puerto Valencia", "Francia"},
            dry_run=True,
        )
        assert out.get("skipped") is True
        assert out.get("stations") == []

    def test_requires_waqi_token_when_missing(self, monkeypatch):
        monkeypatch.delenv("WAQI_TOKEN", raising=False)
        out = supplement_missing_canonical_from_waqi(present_canonical=set(), dry_run=True)
        assert out["stations"] == ["Puerto Valencia"]
        assert out.get("error") == "WAQI_TOKEN missing"
