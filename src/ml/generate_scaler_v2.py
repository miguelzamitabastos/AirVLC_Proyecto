"""
===================================================================
🧪 AirVLC v2 — Generador del MinMaxScaler v2
===================================================================
Lee ``data/processed/master_dataset_colab_v2.csv``, ajusta un
``MinMaxScaler`` sobre **el split de train cronológico por estación**
(80/10/10) y persiste el scaler en
``models/scaler_v2.pkl``.

¿Por qué ajustar el scaler solo sobre train y no sobre todo el CSV?
-------------------------------------------------------------------
* Si ajustamos sobre todo el CSV, el modelo "ve" en el min/max de cada
  columna información que en producción no tendría (estamos filtrando
  el futuro al pasado). Eso es **data leakage**.
* Para que la API v2 (Sprint 3) sea reproducible 1:1 con el modelo
  entrenado en Colab, generamos aquí el scaler único y oficial. El
  notebook lo cargará tal cual; nada de re-fitear en Colab.

Diferencias frente al ``scaler_day7.pkl`` (v1)
----------------------------------------------
* v1 escalaba 20 columnas (1 target + meteo + lags simples + station
  one-hot).
* v2 escala 43 columnas (3 targets + meteo + 12 lags + 9 rollings +
  calendario + cíclicas + station one-hot). El scaler ``feature_names_in_``
  refleja ese conjunto y la API v2 lo usará directamente.

Uso:
    python src/ml/generate_scaler_v2.py
===================================================================
"""

from __future__ import annotations

import argparse
import os
import pickle
import sys
from typing import List

import pandas as pd
from sklearn.preprocessing import MinMaxScaler

# Permite ejecutar el script directamente: `python src/ml/generate_scaler_v2.py`
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_THIS_DIR))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.ml.prepare_dataset_v2 import (
    DEFAULT_DATASET_PATH,
    NON_FEATURE_COLS,
    chronological_split_by_station,
    list_feature_columns,
    load_v2_dataset,
)


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DEFAULT_OUTPUT = os.path.join(PROJECT_ROOT, 'models', 'scaler_v2.pkl')


def fit_v2_scaler(
    dataset_path: str = DEFAULT_DATASET_PATH,
    train_frac: float = 0.8,
    val_frac: float = 0.1,
) -> tuple[MinMaxScaler, List[str]]:
    """Ajusta el scaler sobre el split de train cronológico por estación."""
    df = load_v2_dataset(dataset_path)
    train_df, _, _ = chronological_split_by_station(
        df, train_frac=train_frac, val_frac=val_frac,
    )
    feature_cols = list_feature_columns(train_df)
    scaler = MinMaxScaler()
    scaler.fit(train_df[feature_cols])
    return scaler, feature_cols


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', default=DEFAULT_DATASET_PATH,
                        help='Ruta al master_dataset_colab_v2.csv')
    parser.add_argument('--output', default=DEFAULT_OUTPUT,
                        help='Ruta de salida del scaler_v2.pkl')
    parser.add_argument('--train-frac', type=float, default=0.8)
    parser.add_argument('--val-frac', type=float, default=0.1)
    args = parser.parse_args()

    scaler, feature_cols = fit_v2_scaler(
        dataset_path=args.dataset,
        train_frac=args.train_frac,
        val_frac=args.val_frac,
    )

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'wb') as fh:
        pickle.dump({
            'scaler': scaler,
            'feature_cols': feature_cols,
            'non_feature_cols': NON_FEATURE_COLS,
            'targets': ['pm25', 'no2', 'o3'],
        }, fh)

    print(f"✅ Scaler v2 guardado en: {args.output}")
    print(f"   Features ({len(feature_cols)}): {feature_cols[:6]} ...")
    print(f"   Min global por target: {dict(zip(['pm25','no2','o3'], scaler.data_min_[[feature_cols.index(t) for t in ['pm25','no2','o3']]]))}")
    print(f"   Max global por target: {dict(zip(['pm25','no2','o3'], scaler.data_max_[[feature_cols.index(t) for t in ['pm25','no2','o3']]]))}")


if __name__ == '__main__':
    main()
