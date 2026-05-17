"""
===================================================================
📊 Append to Dataset v2 — Sprint 5 B.2
===================================================================
Lee la cola del CSV ``master_dataset_colab_v2.csv`` (últimas 48h por
estación), cruza con datos nuevos de Mongo (``aire_realtime`` +
``meteo_realtime``), recalcula los features incrementales (lags,
rolling, trig, booleans) y hace append al CSV.

NO recalcula todo el dataset — solo añade las filas nuevas.

Uso:
    python src/ml/append_to_dataset_v2.py              # append
    python src/ml/append_to_dataset_v2.py --dry-run    # solo muestra

    Desde código:
        from src.ml.append_to_dataset_v2 import append_to_dataset_v2
        result = append_to_dataset_v2()
===================================================================
"""

import os
import sys
import argparse
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from pymongo import MongoClient
from dotenv import load_dotenv

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT_DIR)
load_dotenv(os.path.join(ROOT_DIR, '.env'))

# Reutilizar constantes del script de preparación original
try:
    # Importa constantes canónicas (si están disponibles en el entorno)
    from src.ml.prepare_colab_dataset_v2 import TARGETS, LAGS, ROLLING_WINDOWS
except Exception:
    # Fallback: evitar dependencia dura de psycopg2/stack de preparación completa.
    TARGETS = ["pm25", "no2", "o3"]
    LAGS = [1, 3, 6, 24]
    ROLLING_WINDOWS = [6, 12, 24]

MONGO_URI = os.getenv("MONGO_URI")
DATASET_PATH = os.path.join(ROOT_DIR, "data", "processed", "master_dataset_colab_v2.csv")
MAX_DATA_AGE_HOURS = int(os.getenv("AIRVLC_MAX_DATA_AGE_H", "6"))
ALLOW_BOOTSTRAP = os.getenv("AIRVLC_ALLOW_BOOTSTRAP_RECENT", "1").strip() not in ("0", "false", "False")
BOOTSTRAP_HOURS = int(os.getenv("AIRVLC_BOOTSTRAP_HOURS", "48"))
BOOTSTRAP_WHEN_GAP_HOURS = float(os.getenv("AIRVLC_BOOTSTRAP_WHEN_GAP_H", "30"))

# Estaciones del CSV v2
STATIONS = [
    "Francia", "Molí del Sol", "Pista de Silla",
    "Puerto Moll Trans. Ponent", "Puerto Valencia",
    "Puerto llit antic Túria", "Universidad Politécnica",
]

# One-hot columns para las estaciones (deben coincidir con el CSV existente)
STATION_ONEHOT_PREFIX = "station_"

# Quality gates (valores plausibles) — evita que outliers/errores de unidad contaminen el modelo.
PM25_MAX = float(os.getenv("AIRVLC_PM25_MAX", "500"))
NO2_MAX = float(os.getenv("AIRVLC_NO2_MAX", "1000"))
O3_MAX = float(os.getenv("AIRVLC_O3_MAX", "1000"))


def _quality_gates_air(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Aplica filtros de calidad sobre contaminantes (inplace-friendly)."""
    if df.empty:
        return df, {"dropped": 0, "reasons": {}}

    dropped_reasons: dict[str, int] = {}
    out = df.copy()

    # Parse y limpiar tipos
    for c in ("pm25", "no2", "o3"):
        out[c] = pd.to_numeric(out[c], errors="coerce")

    # Eliminar NaNs en targets
    mask_nan = out[["pm25", "no2", "o3"]].isna().any(axis=1)
    if mask_nan.any():
        dropped_reasons["nan_targets"] = int(mask_nan.sum())
        out = out.loc[~mask_nan].copy()

    # Rangos plausibles
    mask_range = (
        (out["pm25"] < 0) | (out["pm25"] > PM25_MAX) |
        (out["no2"] < 0) | (out["no2"] > NO2_MAX) |
        (out["o3"] < 0) | (out["o3"] > O3_MAX)
    )
    if mask_range.any():
        dropped_reasons["out_of_range"] = int(mask_range.sum())
        out = out.loc[~mask_range].copy()

    # Normalizar a hora y deduplicar por estación+h (mantener el último)
    out["fecha"] = pd.to_datetime(out["fecha"], errors="coerce")
    out = out.dropna(subset=["fecha"]).copy()
    out["fecha_hour"] = out["fecha"].dt.floor("h")
    before = len(out)
    out.sort_values(["station_name", "fecha"], inplace=True)
    out = out.drop_duplicates(subset=["station_name", "fecha_hour"], keep="last").copy()
    deduped = before - len(out)
    if deduped:
        dropped_reasons["dedup_hour"] = int(deduped)
    out.drop(columns=["fecha_hour"], inplace=True, errors="ignore")

    dropped = int(sum(dropped_reasons.values()))
    return out, {"dropped": dropped, "reasons": dropped_reasons}


def _read_csv_tail(n_hours_per_station: int = 48) -> pd.DataFrame:
    """Lee el CSV v2 y devuelve solo las últimas n_hours_per_station filas
    por estación (suficiente para lag24 + rolling24h)."""
    print(f"📖 Leyendo cola del dataset: {DATASET_PATH}")
    # low_memory=False evita inferencias inconsistentes por chunks
    df = pd.read_csv(DATASET_PATH, low_memory=False)

    # El CSV puede tener 'fecha' como index o como columna
    if "fecha" not in df.columns and df.index.name == "fecha":
        df.reset_index(inplace=True)

    # Normalizar one-hot station_* a boolean aunque el CSV contenga mezcla (True/False/0/1)
    station_cols = [c for c in df.columns if c.startswith(STATION_ONEHOT_PREFIX) and c != "station_name"]
    if station_cols:
        def _to_bool(x):
            if x is None:
                return False
            if isinstance(x, bool):
                return x
            s = str(x).strip().lower()
            return s in ("true", "1", "t", "yes", "y")
        for c in station_cols:
            df[c] = df[c].map(_to_bool).astype(bool)

    df["fecha"] = pd.to_datetime(df["fecha"])
    df.sort_values(["station_name", "fecha"], inplace=True)

    # Tomar solo la cola por estación
    tails = []
    for st in df["station_name"].unique():
        mask = df["station_name"] == st
        tails.append(df[mask].tail(n_hours_per_station))

    result = pd.concat(tails, ignore_index=True)
    print(f"   Filas cargadas (cola): {len(result)}")
    return result


def _filter_by_staleness(df: pd.DataFrame, max_hours: int) -> tuple[pd.DataFrame, int]:
    """Descarta filas cuya `fecha` sea más antigua que `max_hours` respecto a ahora (UTC)."""
    if df.empty:
        return df, 0
    fechas = pd.to_datetime(df["fecha"], utc=True)
    now_utc = pd.Timestamp.now(tz=timezone.utc)
    ages_h = (now_utc - fechas).dt.total_seconds() / 3600.0
    mask = ages_h <= float(max_hours)
    dropped = int((~mask).sum())
    return df.loc[mask].copy(), dropped


def _get_new_air_data(since: datetime) -> pd.DataFrame:
    """Obtiene nuevos datos de contaminantes desde Mongo aire_realtime."""
    if not MONGO_URI:
        print("❌ MONGO_URI no configurado")
        return pd.DataFrame()

    client = MongoClient(MONGO_URI)
    db = client["airvlc_db"]
    coll = db["aire_realtime"]

    cursor = coll.find(
        # Excluir datos sintéticos (bootstrap) para no contaminar el dataset.
        {"fecha": {"$gt": since}, "is_synthetic": {"$ne": True}},
        {"_id": 0, "estacion": 1, "fecha": 1, "pm25": 1, "no2": 1, "o3": 1},
    ).sort("fecha", 1)

    records = list(cursor)
    client.close()

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df.rename(columns={"estacion": "station_name"}, inplace=True)
    df["fecha"] = pd.to_datetime(df["fecha"])
    return df


def _get_recent_air_window(hours: int) -> pd.DataFrame:
    """Obtiene una ventana reciente (últimas N horas) de Mongo aire_realtime.

    Se usa para bootstrap cuando el CSV está desfasado en el tiempo.
    """
    if not MONGO_URI:
        return pd.DataFrame()
    since = datetime.now(tz=timezone.utc) - timedelta(hours=int(hours))
    client = MongoClient(MONGO_URI)
    db = client["airvlc_db"]
    coll = db["aire_realtime"]

    cursor = coll.find(
        {"fecha": {"$gte": since}, "is_synthetic": {"$ne": True}},
        {"_id": 0, "estacion": 1, "fecha": 1, "pm25": 1, "no2": 1, "o3": 1},
    ).sort("fecha", 1)
    records = list(cursor)
    client.close()
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    df.rename(columns={"estacion": "station_name"}, inplace=True)
    df["fecha"] = pd.to_datetime(df["fecha"], utc=True).dt.tz_convert(None)
    df = df[df["station_name"].isin(STATIONS)]
    df.sort_values(["station_name", "fecha"], inplace=True)
    return df


def _get_latest_meteo() -> dict:
    """Obtiene los últimos datos meteorológicos de Mongo meteo_realtime."""
    if not MONGO_URI:
        return {}

    client = MongoClient(MONGO_URI)
    db = client["airvlc_db"]

    # Buscar el documento más reciente
    doc = db["meteo_realtime"].find_one(
        sort=[("ingested_at", -1)],
    )
    client.close()

    if not doc:
        return {}

    current = doc.get("current", {})
    return {
        "temperatura": current.get("temp"),
        "velocidad_viento": current.get("wind_speed"),
        "humedad_relativa": current.get("humidity"),
        "precipitacion": current.get("rain", {}).get("1h", 0.0) if isinstance(current.get("rain"), dict) else 0.0,
    }


def _compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Recalcula features en las filas del dataframe (in-place friendly)."""
    # Temporales
    df["hora_del_dia"] = df["fecha"].dt.hour
    df["dia_de_la_semana"] = df["fecha"].dt.dayofweek
    df["mes"] = df["fecha"].dt.month

    df["is_weekend"] = (df["dia_de_la_semana"] >= 5).astype(int)
    df["is_fallas"] = (
        (df["fecha"].dt.month == 3)
        & (df["fecha"].dt.day >= 15)
        & (df["fecha"].dt.day <= 19)
    ).astype(int)

    # Trigonométricas
    df["hora_sin"] = np.sin(2 * np.pi * df["hora_del_dia"] / 24)
    df["hora_cos"] = np.cos(2 * np.pi * df["hora_del_dia"] / 24)
    df["mes_sin"] = np.sin(2 * np.pi * df["mes"] / 12)
    df["mes_cos"] = np.cos(2 * np.pi * df["mes"] / 12)

    # Lags por estación
    for col in TARGETS:
        for lag in LAGS:
            df[f"{col}_lag{lag}"] = df.groupby("station_name")[col].shift(lag)

    # Rolling por estación
    for col in TARGETS:
        for window in ROLLING_WINDOWS:
            df[f"{col}_rolling_{window}h"] = df.groupby("station_name")[col].transform(
                lambda x: x.rolling(window=window).mean()
            )

    return df


def _add_station_onehot(df: pd.DataFrame, reference_cols: list) -> pd.DataFrame:
    """Añade columnas one-hot de estación para que coincidan con el CSV existente."""
    # Detectar columnas one-hot existentes en reference
    onehot_cols = [c for c in reference_cols if c.startswith(STATION_ONEHOT_PREFIX) and c != "station_name"]

    for col in onehot_cols:
        station_name = col.replace(STATION_ONEHOT_PREFIX, "")
        # Mantener tipo boolean (el CSV v2 original usa True/False)
        df[col] = (df["station_name"] == station_name).astype(bool)

    return df


def append_to_dataset_v2(dry_run: bool = False) -> dict:
    """Pipeline completo: lee cola CSV → datos nuevos Mongo → features → append.
    Devuelve dict con estadísticas."""

    # 1. Leer cola del CSV
    df_tail = _read_csv_tail(n_hours_per_station=48)
    reference_cols = list(df_tail.columns)

    # 2. Obtener la fecha más reciente del CSV
    last_csv_date = df_tail["fecha"].max()
    print(f"   Última fecha en CSV: {last_csv_date}")

    # 2.b Bootstrap si el CSV está retrasado y existe ventana reciente en Mongo.
    #
    # Caso real observado: CSV ~2 días atrasado. El append normal + staleness guard (<=6h)
    # + dropna(lags) suele dejar df_to_append vacío. Por eso bootstrap debe activarse
    # también en desfases >24h (no solo >7 días).
    if ALLOW_BOOTSTRAP and last_csv_date is not None:
        try:
            last_ts = pd.to_datetime(last_csv_date, utc=True)
            now_ts = pd.Timestamp.now(tz=timezone.utc)
            gap_hours = float((now_ts - last_ts).total_seconds() / 3600.0)
        except Exception:
            gap_hours = 0.0

        required_history_h = int(max(max(LAGS, default=24), max(ROLLING_WINDOWS, default=24), 48))
        bootstrap_h = int(max(BOOTSTRAP_HOURS, required_history_h))

        if gap_hours > BOOTSTRAP_WHEN_GAP_HOURS:
            print(
                f"⚠️  CSV retrasado ~{gap_hours:.1f}h. Intentando bootstrap de {bootstrap_h}h desde Mongo..."
            )
            df_boot = _get_recent_air_window(hours=bootstrap_h)
            if not df_boot.empty:
                # Meteo (mismo fill que en el append normal)
                meteo = _get_latest_meteo()
                meteo_cols = ["temperatura", "velocidad_viento", "humedad_relativa", "precipitacion"]
                tail_last_row = df_tail.sort_values("fecha").iloc[-1] if not df_tail.empty else None
                for col in meteo_cols:
                    val = meteo.get(col)
                    if val is None and tail_last_row is not None and col in tail_last_row:
                        try:
                            val = float(tail_last_row[col])
                        except Exception:
                            val = None
                    if col == "precipitacion" and val is None:
                        val = 0.0
                    if val is None:
                        val = 0.0
                    df_boot[col] = val

                # Calcular features + onehot en la ventana bootstrap
                df_boot = _compute_features(df_boot)
                df_boot = _add_station_onehot(df_boot, reference_cols)

                lag_cols = [f"{t}_lag{l}" for t in TARGETS for l in LAGS]
                df_boot_ready = df_boot.dropna(subset=lag_cols).copy()
                common_cols = [c for c in reference_cols if c in df_boot_ready.columns]
                df_boot_ready = df_boot_ready[common_cols]

                if not df_boot_ready.empty:
                    print(f"   🧩 Bootstrap listo: {len(df_boot_ready)} filas (tras lags) para append al CSV.")
                    if not dry_run:
                        df_boot_ready.to_csv(DATASET_PATH, mode="a", header=False, index=False)
                        print(f"   ✅ Bootstrap append completado: {len(df_boot_ready)} filas añadidas.")
                    else:
                        print("   🔍 DRY RUN — no se escribe bootstrap al CSV.")
                    # Actualizar last_csv_date al máximo de bootstrap para el append normal
                    last_csv_date = df_boot_ready["fecha"].max()
                else:
                    print("   ℹ️  Bootstrap encontrado pero sin filas completas para lags (necesitas 24h continuas).")
            else:
                print("   ℹ️  No hay ventana reciente en Mongo para bootstrap.")

    # 3. Obtener datos nuevos de aire
    df_new_air = _get_new_air_data(since=last_csv_date)
    if df_new_air.empty:
        print("ℹ️  Sin datos nuevos de contaminantes en Mongo.")
        return {"new_rows": 0, "appended": 0, "stale_discarded": 0}

    # Filtrar solo estaciones válidas
    df_new_air = df_new_air[df_new_air["station_name"].isin(STATIONS)]
    if df_new_air.empty:
        print("ℹ️  Datos nuevos no corresponden a estaciones del CSV v2.")
        return {"new_rows": 0, "appended": 0, "stale_discarded": 0}

    df_new_air, stale_n = _filter_by_staleness(df_new_air, MAX_DATA_AGE_HOURS)
    if stale_n:
        print(f"   ⚠️  Descartadas {stale_n} filas por staleness (>{MAX_DATA_AGE_HOURS}h según AIRVLC_MAX_DATA_AGE_H)")
    if df_new_air.empty:
        print("ℹ️  Tras filtro de frescura: sin filas para append.")
        return {"new_rows": 0, "appended": 0, "stale_discarded": stale_n}

    # Quality gates: rangos plausibles + dedup por hora
    df_new_air, qstats = _quality_gates_air(df_new_air)
    if qstats.get("dropped"):
        print(f"   🧹 Quality gates: descartadas {qstats['dropped']} filas: {qstats.get('reasons')}")
    if df_new_air.empty:
        print("ℹ️  Tras quality gates: sin filas para append.")
        return {
            "new_rows": 0,
            "appended": 0,
            "stale_discarded": stale_n,
            "quality_dropped": qstats.get("dropped", 0),
            "quality_reasons": qstats.get("reasons", {}),
        }

    print(f"   📊 Filas nuevas de aire (tras frescura): {len(df_new_air)}")

    # 4. Obtener meteo actual
    meteo = _get_latest_meteo()
    # Fallback: si OpenWeather falló y hay None, usar último valor del CSV.
    # Esto evita introducir NaNs en columnas que luego usa el scaler/modelo.
    meteo_cols = ["temperatura", "velocidad_viento", "humedad_relativa", "precipitacion"]
    tail_last_row = df_tail.sort_values("fecha").iloc[-1] if not df_tail.empty else None

    for col in meteo_cols:
        val = meteo.get(col)
        if val is None and tail_last_row is not None and col in tail_last_row:
            try:
                val = float(tail_last_row[col])
            except Exception:
                val = None
        # Precipitación: si seguimos sin dato, usar 0.0 (mejor que NaN)
        if col == "precipitacion" and val is None:
            val = 0.0
        # Si sigue siendo None, usar 0.0 como último recurso para no romper el pipeline
        if val is None:
            val = 0.0
        df_new_air[col] = val
    print(f"   🌡️ Meteo actual: T={meteo.get('temperatura')}°C, "
          f"H={meteo.get('humedad_relativa')}%, "
          f"V={meteo.get('velocidad_viento')}m/s")

    # 5. Concatenar cola + nuevos para calcular lags/rolling correctamente
    df_combined = pd.concat([df_tail, df_new_air], ignore_index=True)
    df_combined.sort_values(["station_name", "fecha"], inplace=True)
    df_combined.reset_index(drop=True, inplace=True)

    # 6. Recalcular features
    df_combined = _compute_features(df_combined)

    # 7. Añadir one-hot de estación
    df_combined = _add_station_onehot(df_combined, reference_cols)

    # 8. Extraer solo las filas nuevas (las que no estaban en el CSV)
    df_to_append = df_combined[df_combined["fecha"] > last_csv_date].copy()

    # Eliminar filas con NaN en features críticos (lags que no se pueden calcular)
    lag_cols = [f"{t}_lag{l}" for t in TARGETS for l in LAGS]
    df_to_append.dropna(subset=lag_cols, inplace=True)

    if df_to_append.empty:
        print("ℹ️  No hay filas completas para append (faltan lags).")
        return {"new_rows": len(df_new_air), "appended": 0, "stale_discarded": stale_n}

    # 9. Reordenar columnas para que coincidan con el CSV existente
    # Filtrar solo las columnas que existen en ambos
    common_cols = [c for c in reference_cols if c in df_to_append.columns]
    df_to_append = df_to_append[common_cols]

    print(f"   📝 Filas listas para append: {len(df_to_append)}")

    if dry_run:
        print("   🔍 DRY RUN — no se escribe al CSV.")
        print(df_to_append.head())
        return {"new_rows": len(df_new_air), "appended": 0, "dry_run": True, "stale_discarded": stale_n}

    # 10. Append al CSV
    # Importante: NO escribir `fecha` como índice al hacer append (corrompe el CSV sin header).
    df_to_append.to_csv(DATASET_PATH, mode="a", header=False, index=False)
    print(f"   ✅ Append completado: {len(df_to_append)} filas añadidas a {DATASET_PATH}")

    return {"new_rows": len(df_new_air), "appended": len(df_to_append), "stale_discarded": stale_n}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Append incremental al dataset v2")
    parser.add_argument("--dry-run", action="store_true", help="Solo muestra, no escribe")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("📊 AirVLC — Append to Dataset v2 (Sprint 5)")
    print("=" * 60 + "\n")

    result = append_to_dataset_v2(dry_run=args.dry_run)
    print(f"\n🎯 Resultado: {result}")
