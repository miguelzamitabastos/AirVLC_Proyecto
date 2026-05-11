"""
===================================================================
📊 AirVLC — Build CSV comparativo v1 vs v2
===================================================================
Une las métricas de los modelos de v1 (notebook 07/10, monotarget
PM2.5) con las de v2 (notebook 11, multitarget PM2.5/NO₂/O₃) en un
único CSV con schema común, listo para que Logstash lo indexe en
``airvlc-model-comparison-v1v2`` y Kibana pueda graficarlo.

Schema de salida (filas long-format, una métrica por fila):

    timestamp, version, architecture, family, target, mae, rmse, r2,
    n_params, training_time_sec, best_epoch, is_winner

* `version`: "v1" o "v2".
* `family`: "LSTM" / "CNN-LSTM" / "Transformer" / "Other" — para
  agruparlos como series visuales coherentes.
* `target`: "pm25" siempre en v1, uno de {"pm25","no2","o3"} en v2.
* `is_winner`: 1 si fue el ganador de su versión, 0 en otro caso.

Uso:
    python src/scripts/build_model_comparison_csv.py
===================================================================
"""

from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = PROJECT_ROOT / "data" / "processed" / "model_comparison_v1_v2.csv"

V1_RESULTS = PROJECT_ROOT / "models" / "modelo_10_Colab_Comparativas" / "day9_comparison_results.csv"
V2_RESULTS = PROJECT_ROOT / "models" / "modelo_11_v2_Multitarget" / "day11_v2_results.csv"


def _family(arch: str) -> str:
    a = arch.lower()
    if "transformer" in a:
        return "Transformer"
    if "cnn" in a and "lstm" in a:
        return "CNN-LSTM"
    if "lstm" in a or "bilstm" in a:
        return "LSTM"
    if a.startswith("fc") or "dense" in a:
        return "Dense"
    if a.startswith("cnn"):
        return "CNN"
    if "ensemble" in a:
        return "Ensemble"
    return "Other"


def _read_v1_rows() -> list[dict]:
    """v1: una fila por arquitectura, target=pm25 siempre.

    Source: ``models/modelo_10_Colab_Comparativas/day9_comparison_results.csv``
    Columnas: model, mae, rmse, r2, n_params, training_time, type
    """
    rows: list[dict] = []
    with V1_RESULTS.open("r") as fh:
        reader = csv.DictReader(fh)
        all_rows = list(reader)

    if not all_rows:
        return rows

    # Ganador v1: el de mayor R² entre los modelos LSTM/Transformer/etc.
    best = max(all_rows, key=lambda r: float(r["r2"]))
    best_name = best["model"]

    for r in all_rows:
        rows.append({
            "version": "v1",
            "architecture": r["model"],
            "family": _family(r["model"]),
            "target": "pm25",
            "mae": float(r["mae"]),
            "rmse": float(r["rmse"]),
            "r2": float(r["r2"]),
            "n_params": int(r["n_params"] or 0) or None,
            "training_time_sec": float(r["training_time"] or 0) or None,
            "best_epoch": None,
            "is_winner": 1 if r["model"] == best_name else 0,
        })
    return rows


def _read_v2_rows() -> list[dict]:
    """v2: 3 filas por arquitectura (una por target).

    Source: ``models/modelo_11_v2_Multitarget/day11_v2_results.csv``
    Columnas: arch, target, mae, rmse, r2, n_params, training_time_sec
    """
    if not V2_RESULTS.exists():
        raise FileNotFoundError(
            f"No se encontró {V2_RESULTS}. Descarga primero "
            "modelo_11_v2_Multitarget/ desde Drive a models/."
        )
    rows: list[dict] = []
    with V2_RESULTS.open("r") as fh:
        reader = csv.DictReader(fh)
        raw = list(reader)

    # El ganador v2 se decide por R² medio entre los 3 targets.
    by_arch: dict[str, list[float]] = {}
    for r in raw:
        by_arch.setdefault(r["arch"], []).append(float(r["r2"]))
    avg_r2 = {a: sum(vs) / len(vs) for a, vs in by_arch.items()}
    best_arch = max(avg_r2, key=avg_r2.get)

    for r in raw:
        rows.append({
            "version": "v2",
            "architecture": r["arch"],
            "family": _family(r["arch"]),
            "target": r["target"],
            "mae": float(r["mae"]),
            "rmse": float(r["rmse"]),
            "r2": float(r["r2"]),
            "n_params": int(r["n_params"] or 0) or None,
            "training_time_sec": float(r["training_time_sec"] or 0) or None,
            "best_epoch": None,
            "is_winner": 1 if r["arch"] == best_arch else 0,
        })
    return rows


def write_csv(rows: Iterable[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "timestamp", "version", "architecture", "family", "target",
        "mae", "rmse", "r2", "n_params", "training_time_sec",
        "best_epoch", "is_winner",
    ]
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            r = {**r, "timestamp": now}
            r = {k: ("" if r.get(k) is None else r.get(k)) for k in fieldnames}
            w.writerow(r)


def main() -> None:
    v1 = _read_v1_rows()
    v2 = _read_v2_rows()
    write_csv(v1 + v2, OUT_PATH)

    print(f"✅ CSV unificado v1+v2 en: {OUT_PATH}")
    print(f"   Filas v1: {len(v1)}  (1 fila por arquitectura, target=pm25)")
    print(f"   Filas v2: {len(v2)}  (3 filas por arquitectura, 1 por target)")
    print(f"   Total:    {len(v1) + len(v2)} filas")
    print()
    print("Vista previa (5 filas):")
    with OUT_PATH.open() as fh:
        for i, line in enumerate(fh):
            if i > 5:
                break
            print(" ", line.rstrip())


if __name__ == "__main__":
    main()
