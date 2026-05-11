"""
===================================================================
🧪 AirVLC v2 — Utilidades de carga y secuencias multitarget
===================================================================
Funciones reutilizables por el notebook de Colab (Sprint 2) y por la
futura API v2 (Sprint 3) para:

* Cargar ``data/processed/master_dataset_colab_v2.csv`` con el index
  temporal correcto y separar columnas de feature de las "no-feature"
  (``station_name``, etc.).
* Construir secuencias temporales **por estación** (sin cruzar
  fronteras entre estaciones) con ``X.shape = (N, seq_len, n_features)``
  e ``y.shape = (N, n_targets)`` para los 3 targets PM2.5/NO2/O3.
* Hacer un split **cronológico por estación** (80/10/10) para evitar
  fugas de futuro al pasado y mantener la estructura temporal por sitio.
* Escalar/desescalar con un ``MinMaxScaler`` ajustado solo sobre el train
  (evita data leakage) — pero el scaler "oficial" v2 se genera aparte
  con ``src/ml/generate_scaler_v2.py`` para alinearlo con la API v2.

Las funciones están pensadas para ser ejecutadas tanto en local como en
Colab. En Colab basta con copiar el CSV y este fichero al runtime y
llamar ``load_v2_dataset(path)`` y ``build_sequences_multitarget(...)``.

Uso típico (Colab):

    from src.ml.prepare_dataset_v2 import (
        load_v2_dataset, build_sequences_multitarget,
        chronological_split_by_station, fit_scaler_on_train,
    )

    df = load_v2_dataset('master_dataset_colab_v2.csv')
    train_df, val_df, test_df = chronological_split_by_station(df)
    scaler, feature_cols = fit_scaler_on_train(train_df)
    X_train, y_train = build_sequences_multitarget(
        train_df, feature_cols, scaler, seq_len=24,
    )

===================================================================
"""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DEFAULT_DATASET_PATH = os.path.join(
    PROJECT_ROOT, 'data', 'processed', 'master_dataset_colab_v2.csv'
)

TARGETS: List[str] = ['pm25', 'no2', 'o3']
NON_FEATURE_COLS: List[str] = ['station_name']
DEFAULT_SEQ_LEN: int = 24


def load_v2_dataset(path: str = DEFAULT_DATASET_PATH) -> pd.DataFrame:
    """Carga el CSV v2, parsea ``fecha`` como índice y ordena por estación.

    Parameters
    ----------
    path : str
        Ruta al ``master_dataset_colab_v2.csv``.

    Returns
    -------
    pd.DataFrame
        DataFrame con índice ``DatetimeIndex`` y la columna ``station_name``
        intacta. Ordenado por (station_name, fecha) para que las
        secuencias se construyan en el orden temporal correcto.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No se encontró el dataset v2 en {path}. "
            "Genera primero data/processed/master_dataset_colab_v2.csv "
            "ejecutando src/ml/prepare_colab_dataset_v2.py"
        )
    df = pd.read_csv(path, parse_dates=['fecha'])
    df = df.sort_values(['station_name', 'fecha']).reset_index(drop=True)
    df = df.set_index('fecha')
    return df


def list_feature_columns(df: pd.DataFrame) -> List[str]:
    """Devuelve las columnas que entran como features (todas menos
    ``station_name``). Los 3 targets también están aquí porque el modelo
    los recibe como entrada (lags y rolling) y los predice como salida
    en la siguiente hora.
    """
    return [c for c in df.columns if c not in NON_FEATURE_COLS]


def chronological_split_by_station(
    df: pd.DataFrame,
    train_frac: float = 0.8,
    val_frac: float = 0.1,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split cronológico **por estación** preservando el orden temporal.

    Para cada estación se cogen las primeras ``train_frac`` filas como
    train, las siguientes ``val_frac`` como validación y el resto como
    test. Esto evita data leakage de futuro a pasado y respeta la
    deriva temporal específica de cada sitio (las estaciones del puerto
    solo tienen 2020-2021, otras tienen 2016-2021).

    Parameters
    ----------
    df : pd.DataFrame
        Dataset ya ordenado por (station_name, fecha).
    train_frac : float
        Fracción inicial de cada estación para train (0.8 por defecto).
    val_frac : float
        Fracción intermedia para validación (0.1 por defecto). Test es
        el resto: ``1 - train_frac - val_frac``.
    """
    if not (0 < train_frac < 1 and 0 < val_frac < 1):
        raise ValueError("train_frac y val_frac deben estar en (0, 1).")
    if train_frac + val_frac >= 1:
        raise ValueError("train_frac + val_frac debe ser < 1.")

    train_parts, val_parts, test_parts = [], [], []
    for station, group in df.groupby('station_name', sort=False):
        n = len(group)
        n_train = int(n * train_frac)
        n_val = int(n * val_frac)
        train_parts.append(group.iloc[:n_train])
        val_parts.append(group.iloc[n_train:n_train + n_val])
        test_parts.append(group.iloc[n_train + n_val:])

    train_df = pd.concat(train_parts).sort_values(['station_name'])
    val_df = pd.concat(val_parts).sort_values(['station_name'])
    test_df = pd.concat(test_parts).sort_values(['station_name'])
    return train_df, val_df, test_df


def fit_scaler_on_train(
    train_df: pd.DataFrame,
    feature_cols: Optional[List[str]] = None,
) -> Tuple[MinMaxScaler, List[str]]:
    """Ajusta un ``MinMaxScaler`` sobre el train (sin tocar val/test).

    Returns
    -------
    scaler : MinMaxScaler
        Escalador ajustado sobre las columnas de feature.
    feature_cols : List[str]
        Lista efectiva de columnas escaladas (en el mismo orden que el
        scaler). El orden importa porque los modelos esperan un tensor
        con esa misma columna en cada índice.
    """
    if feature_cols is None:
        feature_cols = list_feature_columns(train_df)
    scaler = MinMaxScaler()
    scaler.fit(train_df[feature_cols])
    return scaler, feature_cols


def _scale_block(df: pd.DataFrame, feature_cols: List[str], scaler: MinMaxScaler) -> pd.DataFrame:
    scaled = scaler.transform(df[feature_cols])
    out = df.copy()
    out[feature_cols] = scaled
    return out


def build_sequences_multitarget(
    df: pd.DataFrame,
    feature_cols: List[str],
    scaler: Optional[MinMaxScaler] = None,
    seq_len: int = DEFAULT_SEQ_LEN,
    targets: Optional[List[str]] = None,
    group_col: str = 'station_name',
    skip_temporal_gaps: bool = True,
    max_gap_hours: float = 1.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Construye secuencias ``X = (N, seq_len, n_features)`` y
    ``y = (N, n_targets)`` agrupadas por estación.

    * Si ``scaler`` se pasa, las features se escalan **antes** de cortar.
    * Si ``skip_temporal_gaps=True``, descarta cualquier ventana cuya
      diferencia máxima entre timestamps consecutivos supere
      ``max_gap_hours`` (por defecto 1h). Esto es crítico: las estaciones
      del portal valenciano tienen gaps de meses; sin este filtro, una
      ventana podría empezar en 2018 y acabar en 2019.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame con índice DatetimeIndex y columna ``station_name``.
    feature_cols : List[str]
        Columnas que entran como features (en orden).
    scaler : MinMaxScaler, opcional
        Si se pasa, se aplica antes de construir las ventanas.
    seq_len : int
        Longitud de la ventana de entrada (24h por defecto = 1 día).
    targets : List[str], opcional
        Columnas objetivo. Por defecto ``['pm25', 'no2', 'o3']``.
    group_col : str
        Columna por la que agrupar (por defecto la estación).
    skip_temporal_gaps : bool
        Descarta ventanas que crucen huecos > ``max_gap_hours``.
    max_gap_hours : float
        Umbral en horas para considerar una ventana "no contigua".

    Returns
    -------
    X : np.ndarray, shape (N, seq_len, n_features)
    y : np.ndarray, shape (N, n_targets)
    """
    if targets is None:
        targets = TARGETS

    if scaler is not None:
        df = _scale_block(df, feature_cols, scaler)

    target_idx = [feature_cols.index(t) for t in targets]

    xs: List[np.ndarray] = []
    ys: List[np.ndarray] = []

    # Umbral de gap en nanosegundos. Trabajamos a int64 para ser robustos
    # a la unidad temporal del DatetimeIndex (us / ns / ms varía entre
    # versiones de pandas+numpy y entre Colab y local).
    gap_threshold_ns = np.int64(int(max_gap_hours * 3_600 * 1_000_000_000))

    for station, group in df.groupby(group_col, sort=False):
        if len(group) <= seq_len:
            continue

        feat = group[feature_cols].to_numpy(dtype=np.float32)
        ts_ns = group.index.values.astype('datetime64[ns]').astype(np.int64)

        for i in range(len(group) - seq_len):
            window_end = i + seq_len
            if skip_temporal_gaps:
                window_ts = ts_ns[i:window_end + 1]
                diffs_ns = np.diff(window_ts)
                if (diffs_ns > gap_threshold_ns).any():
                    continue
            xs.append(feat[i:window_end])
            target_values = feat[window_end, target_idx]
            ys.append(target_values)

    if not xs:
        return np.empty((0, seq_len, len(feature_cols)), dtype=np.float32), \
               np.empty((0, len(targets)), dtype=np.float32)

    X = np.stack(xs)
    y = np.stack(ys)
    return X, y


def inverse_transform_targets(
    y_scaled: np.ndarray,
    scaler: MinMaxScaler,
    feature_cols: List[str],
    targets: Optional[List[str]] = None,
) -> np.ndarray:
    """Invierte la transformación MinMax para los 3 targets.

    Construye internamente una matriz dummy con el resto de columnas a 0
    y le pasa ``scaler.inverse_transform`` quedándose solo con las
    columnas de target. Esto permite reportar métricas en µg/m³ reales.
    """
    if targets is None:
        targets = TARGETS

    if y_scaled.ndim == 1:
        y_scaled = y_scaled.reshape(-1, len(targets))

    n = y_scaled.shape[0]
    dummy = np.zeros((n, len(feature_cols)), dtype=np.float32)
    target_idx = [feature_cols.index(t) for t in targets]
    for j, idx in enumerate(target_idx):
        dummy[:, idx] = y_scaled[:, j]

    inv = scaler.inverse_transform(dummy)
    return inv[:, target_idx]


def summary(df: pd.DataFrame) -> str:
    """Resumen rápido del DataFrame para imprimir en el notebook."""
    lines = [
        f"Filas: {len(df):,}",
        f"Columnas: {df.shape[1]}",
        f"Rango temporal: {df.index.min()} → {df.index.max()}",
        f"Estaciones: {sorted(df['station_name'].unique())}",
    ]
    return "\n".join(lines)


if __name__ == '__main__':
    df = load_v2_dataset()
    print(summary(df))
    print()
    train_df, val_df, test_df = chronological_split_by_station(df)
    print(f"Train: {len(train_df):,}  Val: {len(val_df):,}  Test: {len(test_df):,}")

    scaler, feature_cols = fit_scaler_on_train(train_df)
    print(f"Features para entrenar (n={len(feature_cols)}): {feature_cols[:6]}...")

    X_train, y_train = build_sequences_multitarget(
        train_df, feature_cols, scaler, seq_len=DEFAULT_SEQ_LEN,
    )
    print(f"X_train: {X_train.shape}  y_train: {y_train.shape}")
