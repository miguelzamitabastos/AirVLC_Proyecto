"""
===================================================================
🔬 AirVLC v2 — Validación del Dataset Maestro Multivariante
===================================================================
Carga ``data/processed/master_dataset_colab_v2.csv`` y emite un
informe de salud del dataset:

* Filas totales y rango temporal.
* Conteo de filas por estación y rango por estación.
* NaNs por columna (debería ser 0 tras el dropna del script v2).
* Estadísticos básicos (min/median/max) de los 3 targets.
* Detección rápida de huecos temporales mayores de 1 hora por estación.

El script imprime un Markdown válido por stdout para poder embeberlo
fácilmente en ``docs/v2AirVLCdocs/sprint1/walkthrough.md`` (vía pipe).

Uso:
    python src/ml/validate_dataset_v2.py
    python src/ml/validate_dataset_v2.py --markdown > /tmp/report.md
===================================================================
"""

import argparse
import os
import sys

import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DATASET_PATH = os.path.join(PROJECT_ROOT, 'data', 'processed', 'master_dataset_colab_v2.csv')

TARGETS = ['pm25', 'no2', 'o3']


def load_dataset(path):
    if not os.path.exists(path):
        sys.exit(f"❌ No se encontró el dataset v2 en {path}. Corre primero src/ml/prepare_colab_dataset_v2.py")
    df = pd.read_csv(path, parse_dates=['fecha'])
    df.set_index('fecha', inplace=True)
    return df


def report_text(df: pd.DataFrame) -> str:
    """Genera un reporte humano (Markdown) sobre el estado del dataset v2."""
    lines = []
    lines.append("# Validación del dataset v2\n")
    lines.append(f"- **Ruta**: `data/processed/master_dataset_colab_v2.csv`")
    lines.append(f"- **Shape**: {df.shape[0]:,} filas × {df.shape[1]} columnas")
    lines.append(f"- **Rango temporal global**: {df.index.min()} → {df.index.max()}\n")

    # Conteo por estación
    lines.append("## Conteo por estación")
    lines.append("| Estación | Filas | Desde | Hasta |")
    lines.append("|---|---:|---|---|")
    for station, group in df.groupby('station_name'):
        lines.append(
            f"| {station} | {len(group):,} | {group.index.min()} | {group.index.max()} |"
        )
    lines.append("")

    # NaNs por columna
    nan_counts = df.isna().sum()
    nan_counts = nan_counts[nan_counts > 0]
    lines.append("## Valores NaN")
    if nan_counts.empty:
        lines.append("✅ Sin NaNs en ninguna columna.\n")
    else:
        lines.append("| Columna | NaNs |")
        lines.append("|---|---:|")
        for col, n in nan_counts.items():
            lines.append(f"| `{col}` | {n:,} |")
        lines.append("")

    # Estadísticos targets
    lines.append("## Estadísticos de los 3 targets (µg/m³)")
    lines.append("| Target | Min | P25 | Mediana | P75 | Max | Media | Std |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for col in TARGETS:
        s = df[col]
        lines.append(
            f"| `{col}` | {s.min():.2f} | {s.quantile(.25):.2f} | "
            f"{s.median():.2f} | {s.quantile(.75):.2f} | {s.max():.2f} | "
            f"{s.mean():.2f} | {s.std():.2f} |"
        )
    lines.append("")

    # Huecos temporales > 1h
    lines.append("## Huecos temporales por estación (gaps > 1h)")
    lines.append("| Estación | Gaps>1h | Gap máx (h) |")
    lines.append("|---|---:|---:|")
    for station, group in df.groupby('station_name'):
        diffs = group.sort_index().index.to_series().diff().dt.total_seconds() / 3600
        big_gaps = (diffs > 1).sum()
        max_gap = diffs.max() if not diffs.empty else 0
        lines.append(f"| {station} | {int(big_gaps):,} | {max_gap:.1f} |")
    lines.append("")

    # Lista de columnas
    lines.append("## Columnas del dataset")
    lines.append("```")
    for col in df.columns:
        lines.append(f"- {col} ({df[col].dtype})")
    lines.append("```")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path', default=DATASET_PATH,
                        help='Ruta al CSV v2 a validar')
    parser.add_argument('--markdown', action='store_true',
                        help='Emitir solo el reporte Markdown sin cabeceras de texto')
    args = parser.parse_args()

    df = load_dataset(args.path)
    report = report_text(df)
    if args.markdown:
        print(report)
    else:
        print(report)
        print("\n[OK] Validación completada.")


if __name__ == '__main__':
    main()
