"""Tests EPA sub-index -> concentración (Sprint 6)."""

import os
import sys

import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)

from src.ingestion.aqi_conversion import (
    no2_subindex_to_ugm3,
    o3_subindex_to_ugm3,
    pm25_subindex_to_ugm3,
)


class TestPm25Conversion:
    def test_zero(self):
        assert pm25_subindex_to_ugm3(0) == pytest.approx(0.0)

    def test_fifty_maps_to_twelve(self):
        assert pm25_subindex_to_ugm3(50) == pytest.approx(12.0)

    def test_mid_good_range(self):
        assert pm25_subindex_to_ugm3(25) == pytest.approx(6.0)

    def test_one_hundred_maps_upper_moderate(self):
        assert pm25_subindex_to_ugm3(100) == pytest.approx(35.4)


class TestNo2Conversion:
    def test_subindex_50_gives_ppb_53(self):
        ppb_equivalent = no2_subindex_to_ugm3(50) / 1.88
        assert ppb_equivalent == pytest.approx(53.0)


class TestO3Conversion:
    def test_subindex_50_gives_ppb_54(self):
        ppb_equivalent = o3_subindex_to_ugm3(50) / 1.96
        assert ppb_equivalent == pytest.approx(54.0)
