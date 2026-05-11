"""
Tests Sprint 5 — Append to Dataset v2 (B.2)

Verifica que dado un CSV de 48h y una nueva fila, el append calcula
correctamente lag1, lag24 y rolling_24h.
"""

import os
import sys
import tempfile

import numpy as np
import pandas as pd
import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT_DIR)

from src.ml.prepare_colab_dataset_v2 import TARGETS, LAGS, ROLLING_WINDOWS
from src.ml.append_to_dataset_v2 import _compute_features


# ---- Helpers -----------------------------------------------------------------

def _make_synthetic_df(n_hours: int = 48, station: str = "Pista de Silla"):
    """Genera un DataFrame sintético con n_hours filas para una estación."""
    dates = pd.date_range("2026-05-06 00:00", periods=n_hours, freq="h")
    rng = np.random.RandomState(42)

    data = {
        "fecha": dates,
        "station_name": station,
        "pm25": rng.uniform(5, 50, n_hours),
        "no2": rng.uniform(10, 80, n_hours),
        "o3": rng.uniform(20, 120, n_hours),
        "temperatura": rng.uniform(15, 35, n_hours),
        "velocidad_viento": rng.uniform(0, 10, n_hours),
        "precipitacion": rng.uniform(0, 5, n_hours),
        "humedad_relativa": rng.uniform(30, 90, n_hours),
    }
    return pd.DataFrame(data)


# ---- Tests -------------------------------------------------------------------

class TestComputeFeatures:
    """Verifica el cálculo de features incrementales."""

    def test_temporal_columns_created(self):
        df = _make_synthetic_df(48)
        result = _compute_features(df.copy())
        assert "hora_del_dia" in result.columns
        assert "is_weekend" in result.columns
        assert "is_fallas" in result.columns
        assert "hora_sin" in result.columns
        assert "mes_cos" in result.columns

    def test_lags_computed(self):
        df = _make_synthetic_df(48)
        result = _compute_features(df.copy())
        for target in TARGETS:
            for lag in LAGS:
                col = f"{target}_lag{lag}"
                assert col in result.columns, f"Falta columna {col}"
                # La fila 24 (lag24) no debe ser NaN si hay suficientes datos
                assert not pd.isna(result[col].iloc[-1]), \
                    f"{col} es NaN en la última fila"

    def test_rolling_computed(self):
        df = _make_synthetic_df(48)
        result = _compute_features(df.copy())
        for target in TARGETS:
            for window in ROLLING_WINDOWS:
                col = f"{target}_rolling_{window}h"
                assert col in result.columns, f"Falta columna {col}"
                # La última fila debería tener rolling calculado
                assert not pd.isna(result[col].iloc[-1]), \
                    f"{col} es NaN en la última fila"

    def test_lag1_equals_shifted_value(self):
        """lag1 de la última fila debe ser el valor de la penúltima."""
        df = _make_synthetic_df(48)
        result = _compute_features(df.copy())
        for target in TARGETS:
            expected = result[target].iloc[-2]
            actual = result[f"{target}_lag1"].iloc[-1]
            assert abs(expected - actual) < 1e-6, \
                f"{target}_lag1: expected {expected}, got {actual}"

    def test_lag24_equals_shifted_24h(self):
        """lag24 de la última fila debe ser el valor de 24 horas antes."""
        df = _make_synthetic_df(48)
        result = _compute_features(df.copy())
        for target in TARGETS:
            expected = result[target].iloc[-25]  # 24 rows before the last
            actual = result[f"{target}_lag24"].iloc[-1]
            assert abs(expected - actual) < 1e-6, \
                f"{target}_lag24: expected {expected}, got {actual}"

    def test_rolling_24h_is_mean_of_last_24(self):
        """rolling_24h de la última fila debe ser la media de las últimas 24."""
        df = _make_synthetic_df(48)
        result = _compute_features(df.copy())
        for target in TARGETS:
            expected = result[target].iloc[-24:].mean()
            actual = result[f"{target}_rolling_24h"].iloc[-1]
            assert abs(expected - actual) < 1e-4, \
                f"{target}_rolling_24h: expected {expected:.4f}, got {actual:.4f}"

    def test_trig_encoding_range(self):
        """Los valores sin/cos deben estar en [-1, 1]."""
        df = _make_synthetic_df(48)
        result = _compute_features(df.copy())
        for col in ["hora_sin", "hora_cos", "mes_sin", "mes_cos"]:
            assert result[col].min() >= -1.001, f"{col} min < -1"
            assert result[col].max() <= 1.001, f"{col} max > 1"

    def test_fallas_flag(self):
        """Filas del 15-19 de marzo deben tener is_fallas=1."""
        dates = pd.date_range("2026-03-14 00:00", periods=48 * 7, freq="h")
        rng = np.random.RandomState(42)
        n = len(dates)
        df = pd.DataFrame({
            "fecha": dates,
            "station_name": "Francia",
            "pm25": rng.uniform(5, 50, n),
            "no2": rng.uniform(10, 80, n),
            "o3": rng.uniform(20, 120, n),
            "temperatura": rng.uniform(15, 35, n),
            "velocidad_viento": rng.uniform(0, 10, n),
            "precipitacion": rng.uniform(0, 5, n),
            "humedad_relativa": rng.uniform(30, 90, n),
        })
        result = _compute_features(df)
        fallas_rows = result[(result["fecha"].dt.month == 3) &
                             (result["fecha"].dt.day >= 15) &
                             (result["fecha"].dt.day <= 19)]
        assert (fallas_rows["is_fallas"] == 1).all()
