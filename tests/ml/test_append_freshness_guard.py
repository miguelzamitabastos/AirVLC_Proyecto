"""Tests guard de staleness en append (Sprint 6)."""

import os
import sys
from unittest.mock import patch

import pandas as pd
import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)

from src.ml.append_to_dataset_v2 import _filter_by_staleness


class TestFilterByStaleness:
    def test_drops_rows_older_than_max_hours(self):
        df = pd.DataFrame(
            {
                "fecha": [
                    pd.Timestamp("2026-05-07 09:00:00+00:00"),
                    pd.Timestamp("2026-05-07 14:00:00+00:00"),
                ],
                "station_name": ["Francia", "Francia"],
            }
        )
        fixed_now = pd.Timestamp("2026-05-07 16:00:00+00:00")

        with patch("src.ml.append_to_dataset_v2.pd.Timestamp.now", return_value=fixed_now):
            out, dropped = _filter_by_staleness(df, max_hours=6)

        assert dropped == 1
        assert len(out) == 1
        assert out.iloc[0]["fecha"] == pd.Timestamp("2026-05-07 14:00:00+00:00")

    def test_keeps_boundary_six_hours(self):
        df = pd.DataFrame(
            {
                "fecha": [pd.Timestamp("2026-05-07 10:00:00+00:00")],
                "station_name": ["Francia"],
            }
        )
        fixed_now = pd.Timestamp("2026-05-07 16:00:00+00:00")

        with patch("src.ml.append_to_dataset_v2.pd.Timestamp.now", return_value=fixed_now):
            out, dropped = _filter_by_staleness(df, max_hours=6)

        assert dropped == 0
        assert len(out) == 1
