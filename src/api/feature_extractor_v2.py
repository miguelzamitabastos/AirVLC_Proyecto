import math
import os
import pickle
import threading
from datetime import datetime, timezone
from datetime import timedelta
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

# Estaciones canónicas v2 (mismo orden que routes_v2 / master CSV)
V2_CANONICAL_STATIONS: Tuple[str, ...] = (
    "Francia",
    "Molí del Sol",
    "Pista de Silla",
    "Puerto Moll Trans. Ponent",
    "Puerto Valencia",
    "Puerto llit antic Túria",
    "Universidad Politécnica",
)


class FeatureExtractorV2:
    """
    Extractor de features v2 (multitarget).

    - Carga `data/processed/master_dataset_colab_v2.csv`
    - Carga `models/scaler_v2.pkl`
    - Devuelve tensor (1, 24, 44) ya normalizado con el scaler
    - Permite invertir predicciones de targets a µg/m³ reales
    """

    def __init__(self):
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        self.dataset_path = os.path.join(
            self.project_root, "data", "processed", "master_dataset_colab_v2.csv"
        )
        self.scaler_path = os.path.join(self.project_root, "models", "scaler_v2.pkl")
        self._df_lock = threading.Lock()
        self._initial_csv_end_ts: Dict[str, datetime] = {}

        self._load_data()
        self._load_scaler()

        # Mapeo (Lex/usuario) -> nombre real en master_dataset_colab_v2.csv
        # Estaciones disponibles en v2:
        #   Francia, Molí del Sol, Pista de Silla, Puerto Moll Trans. Ponent,
        #   Puerto Valencia, Puerto llit antic Túria, Universidad Politécnica
        self.lex_to_station = {
            "francia": "Francia",
            "av. frança": "Francia",
            "avda francia": "Francia",
            "moli del sol": "Molí del Sol",
            "molí del sol": "Molí del Sol",
            "pista de silla": "Pista de Silla",
            "pista silla": "Pista de Silla",
            "puerto valencia": "Puerto Valencia",
            "puerto": "Puerto Valencia",
            "port": "Puerto Valencia",
            "puerto moll": "Puerto Moll Trans. Ponent",
            "puerto moll trans. ponent": "Puerto Moll Trans. Ponent",
            "puerto turia": "Puerto llit antic Túria",
            "puerto llit antic turia": "Puerto llit antic Túria",
            "puerto llit antic túria": "Puerto llit antic Túria",
            "politecnico": "Universidad Politécnica",
            "politécnico": "Universidad Politécnica",
            "politecnic": "Universidad Politécnica",
            "politècnic": "Universidad Politécnica",
            "universidad politecnica": "Universidad Politécnica",
            "universidad politécnica": "Universidad Politécnica",
        }

    def _load_data(self):
        print(f"Cargando dataset base para extracción v2: {self.dataset_path}")
        import pandas as pd

        self.df = pd.read_csv(self.dataset_path)
        if "fecha" in self.df.columns:
            self.df.sort_values(by=["station_name", "fecha"], inplace=True)
        self._snapshot_csv_end_times()

    def _snapshot_csv_end_times(self) -> None:
        """Guarda el último timestamp por estación del CSV en disco (sin filas sintéticas)."""
        import pandas as pd

        self._initial_csv_end_ts.clear()
        if self.df is None or self.df.empty or "fecha" not in self.df.columns:
            return
        dfc = self.df.copy()
        dfc["fecha"] = pd.to_datetime(dfc["fecha"], utc=True, errors="coerce")
        for st, g in dfc.groupby("station_name"):
            mx = g["fecha"].max()
            if pd.isna(mx):
                continue
            dt = mx.to_pydatetime()
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            self._initial_csv_end_ts[str(st)] = dt.astimezone(timezone.utc)

    def _mongo_air_collection(self):
        mongo_uri = (os.getenv("MONGO_URI") or "").strip()
        if not mongo_uri:
            return None, None
        try:
            from pymongo import MongoClient
        except Exception:
            return None, None
        client = MongoClient(mongo_uri)
        return client, client["airvlc_db"]["aire_realtime"]

    @staticmethod
    def _parse_mongo_doc_datetime(doc: Optional[dict]) -> Optional[datetime]:
        if not doc:
            return None
        fe = doc.get("fecha")
        if isinstance(fe, datetime):
            if fe.tzinfo is None:
                fe = fe.replace(tzinfo=timezone.utc)
            return fe.astimezone(timezone.utc)
        fis = doc.get("fecha_iso")
        if isinstance(fis, str) and fis.strip():
            s = fis.strip().replace("Z", "+00:00")
            try:
                dt = datetime.fromisoformat(s)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except ValueError:
                pass
        return None

    def _fetch_latest_mongo_doc(self, station: str) -> Optional[dict]:
        client, coll = self._mongo_air_collection()
        if coll is None:
            return None
        try:
            return coll.find_one(
                {"estacion": station, "is_canonical_v2": True},
                sort=[("fecha_iso", -1)],
            )
        except Exception as e:
            print(f"⚠️ Mongo (feature extractor): lectura frescura {station!r}: {e}")
            return None
        finally:
            try:
                client.close()
            except Exception:
                pass

    def _strip_synthetic_rows_for_station(self, station: str) -> None:
        """Elimina filas posteriores al último timestamp del CSV original (inyecciones previas)."""
        import pandas as pd

        end = self._initial_csv_end_ts.get(station)
        if end is None or self.df is None or self.df.empty:
            return
        ts_end = pd.Timestamp(end).tz_convert("UTC")
        fe = pd.to_datetime(self.df["fecha"], utc=True, errors="coerce")
        mask = (self.df["station_name"] == station) & (fe > ts_end)
        if mask.any():
            self.df = self.df.loc[~mask].reset_index(drop=True)

    @staticmethod
    def _fallas_flag(ts: datetime) -> int:
        return 1 if (ts.month == 3 and 15 <= ts.day <= 19) else 0

    def _build_synthetic_row(
        self,
        station: str,
        mongo_ts: datetime,
        mongo_doc: dict,
        before: "pd.DataFrame",
    ) -> dict:
        """Construye una fila alineada con el esquema del master CSV (lags + rollings).

        ``before`` debe contener al menos 24 filas con ``fecha`` estrictamente
        anteriores a ``mongo_ts`` (típicamente t-24…t-1 en resolución horaria).
        """
        import pandas as pd

        if before.empty or len(before) < 24:
            raise ValueError(f"Historial insuficiente para {station} (<24 filas previas a Mongo).")

        prev = before.iloc[-1]
        tpl = prev.to_dict()

        def _num(doc, key: str, fb: float) -> float:
            v = doc.get(key)
            if v is None:
                return float(fb)
            try:
                return float(v)
            except (TypeError, ValueError):
                return float(fb)

        pm25_n = _num(mongo_doc, "pm25", float(prev["pm25"]))
        no2_n = _num(mongo_doc, "no2", float(prev["no2"]))
        o3_n = _num(mongo_doc, "o3", float(prev["o3"]))

        meteo_keys = (
            "temperatura",
            "velocidad_viento",
            "precipitacion",
            "humedad_relativa",
        )
        for k in meteo_keys:
            if k in tpl:
                tpl[k] = float(prev[k]) if pd.notna(prev.get(k)) else float(tpl.get(k) or 0.0)

        ts = mongo_ts.astimezone(timezone.utc)
        hour = ts.hour
        dow = ts.weekday()
        month = ts.month

        tpl["fecha"] = ts.replace(tzinfo=None)  # CSV suele guardar naive UTC
        tpl["pm25"] = pm25_n
        tpl["no2"] = no2_n
        tpl["o3"] = o3_n
        tpl["hora_del_dia"] = float(hour)
        tpl["dia_de_la_semana"] = float(dow)
        tpl["mes"] = float(month)
        tpl["is_weekend"] = 1.0 if dow >= 5 else 0.0
        tpl["is_fallas"] = float(self._fallas_flag(ts))
        tpl["hora_sin"] = float(math.sin(2 * math.pi * hour / 24))
        tpl["hora_cos"] = float(math.cos(2 * math.pi * hour / 24))
        tpl["mes_sin"] = float(math.sin(2 * math.pi * month / 12))
        tpl["mes_cos"] = float(math.cos(2 * math.pi * month / 12))

        b = before.tail(24)
        for col in ("pm25", "no2", "o3"):
            tpl[f"{col}_lag1"] = float(b.iloc[-1][col])
            tpl[f"{col}_lag3"] = float(b.iloc[-3][col])
            tpl[f"{col}_lag6"] = float(b.iloc[-6][col])
            tpl[f"{col}_lag24"] = float(b.iloc[0][col])

        new_by_col = {"pm25": pm25_n, "no2": no2_n, "o3": o3_n}
        for col in ("pm25", "no2", "o3"):
            nv = new_by_col[col]
            tpl[f"{col}_rolling_6h"] = float(np.mean(b[col].iloc[-5:].tolist() + [nv]))
            tpl[f"{col}_rolling_12h"] = float(np.mean(b[col].iloc[-11:].tolist() + [nv]))
            tpl[f"{col}_rolling_24h"] = float(np.mean(b[col].iloc[1:].tolist() + [nv]))

        return tpl

    def _inject_one_station_from_mongo(self, station: str) -> bool:
        """Inyecta el último documento Mongo si es más reciente que el CSV. Devuelve True si hubo cambio."""
        import pandas as pd

        csv_end = self._initial_csv_end_ts.get(station)
        if csv_end is None:
            return False

        doc = self._fetch_latest_mongo_doc(station)
        if not doc:
            return False

        mongo_ts = self._parse_mongo_doc_datetime(doc)
        if mongo_ts is None:
            return False

        csv_end_utc = csv_end if csv_end.tzinfo else csv_end.replace(tzinfo=timezone.utc)
        if mongo_ts <= csv_end_utc:
            return False

        for pol in ("pm25", "no2", "o3"):
            if doc.get(pol) is not None:
                break
        else:
            return False

        self._strip_synthetic_rows_for_station(station)

        hist = self.df[self.df["station_name"] == station].copy()
        if hist.empty:
            return False
        hist["fecha"] = pd.to_datetime(hist["fecha"], utc=True, errors="coerce")
        hist = hist.dropna(subset=["fecha"]).sort_values("fecha")
        mongo_pd = pd.Timestamp(mongo_ts).tz_convert("UTC")
        before = hist[hist["fecha"] < mongo_pd].tail(24)
        if len(before) < 24:
            print(f"⚠️ Mongo inject: solo {len(before)} filas previas para {station!r}; se omite.")
            return False

        try:
            new_row = self._build_synthetic_row(station, mongo_ts, doc, before)
        except Exception as e:
            print(f"⚠️ Mongo inject: no se pudo sintetizar fila para {station!r}: {e}")
            return False

        new_df = pd.DataFrame([new_row])
        self.df = pd.concat([self.df, new_df], ignore_index=True)
        if "fecha" in self.df.columns:
            self.df.sort_values(by=["station_name", "fecha"], inplace=True)
            self.df.reset_index(drop=True, inplace=True)
        print(f"✅ Mongo inject: {station!r} ← {mongo_ts.isoformat()} (CSV hasta {csv_end.isoformat()})")
        return True

    def inject_latest_from_mongo(self, stations: Optional[Iterable[str]] = None) -> dict:
        """
        Añade (o sustituye) el punto más reciente por estación desde Mongo
        (`aire_realtime`, is_canonical_v2) si supera en fecha al CSV cargado.

        - Si ``stations`` es None, se procesan todas las canónicas v2.
        - Idempotente: elimina inyecciones previas (post-CSV) antes de volver a insertar.
        """
        targets: List[str]
        if stations is None:
            targets = list(V2_CANONICAL_STATIONS)
        else:
            targets = [str(s) for s in stations if s]

        out = {"updated": [], "skipped": [], "errors": []}
        with self._df_lock:
            for st in targets:
                try:
                    if self._inject_one_station_from_mongo(st):
                        out["updated"].append(st)
                    else:
                        out["skipped"].append(st)
                except Exception as e:
                    out["errors"].append(f"{st}: {e}")
        return out

    def _load_scaler(self):
        print(f"Cargando Scaler v2: {self.scaler_path}")
        if not os.path.exists(self.scaler_path):
            raise FileNotFoundError(f"No se encontró el scaler en {self.scaler_path}")
        with open(self.scaler_path, "rb") as f:
            obj = pickle.load(f)

        # Soporta dos formatos:
        # 1) dict producido por src/ml/generate_scaler_v2.py:
        #    {'scaler': MinMaxScaler, 'feature_cols': [...], 'targets': [...], 'non_feature_cols': [...]}
        # 2) MinMaxScaler "suelto" con `feature_names_in_` (compat con scripts antiguos).
        if isinstance(obj, dict) and "scaler" in obj and "feature_cols" in obj:
            self.scaler = obj["scaler"]
            self.feature_cols = list(obj["feature_cols"])
            self.targets = list(obj.get("targets") or ["pm25", "no2", "o3"])
        elif hasattr(obj, "feature_names_in_"):
            self.scaler = obj
            self.feature_cols = list(obj.feature_names_in_)
            self.targets = ["pm25", "no2", "o3"]
        else:
            raise ValueError(
                "Formato de scaler v2 desconocido: ni dict {'scaler','feature_cols',...} "
                "ni sklearn scaler con feature_names_in_."
            )

    def reload(self):
        """Recarga el CSV en memoria (hot-reload sin reiniciar Flask)."""
        print("🔄 Recargando dataset v2 en memoria...")
        self._load_data()
        print("✅ Dataset v2 recargado.")

    def get_features(self, station_name: str, offset_hours: int = 0) -> Tuple[np.ndarray, str, dict]:
        """
        Extrae una ventana de 24h de la estación, normaliza y devuelve:
        - features: np.ndarray shape (1, 24, 44)
        - real_station: str
        - meta: dict con data_timestamp, data_window_start, data_age_minutes

        `offset_hours` permite moverse hacia atrás en el tiempo:
          - 0  => ventana más reciente (termina en el último timestamp disponible)
          - 6  => ventana que termina 6h antes del último timestamp
          - 24 => ventana que termina 24h antes del último timestamp
        """
        import pandas as pd

        normalized = (station_name or "").lower().strip()
        real_station = self.lex_to_station.get(normalized, station_name)
        if not real_station:
            real_station = "Pista de Silla"

        with self._df_lock:
            df_station = self.df[self.df["station_name"] == real_station].copy()
        if df_station.empty:
            print(f"⚠️ Estación '{real_station}' no encontrada en el dataset v2. Usando Pista de Silla.")
            real_station = "Pista de Silla"
            with self._df_lock:
                df_station = self.df[self.df["station_name"] == real_station].copy()

        if len(df_station) < 24:
            raise ValueError(f"No hay suficientes datos (24h) para {real_station}")

        # Seleccionar ventana de 24h con offset (por fecha)
        if "fecha" in df_station.columns:
            df_station["fecha"] = pd.to_datetime(df_station["fecha"], errors="coerce")
            df_station = df_station.dropna(subset=["fecha"]).sort_values("fecha")

        df_end = df_station.tail(1).copy()
        if df_end.empty:
            raise ValueError(f"No hay timestamps válidos para {real_station}")

        last_available_ts = pd.to_datetime(df_end["fecha"].iloc[-1]) if "fecha" in df_end.columns else datetime.now()
        try:
            off = int(offset_hours or 0)
        except Exception:
            off = 0
        if off < 0:
            off = 0

        target_end_ts = last_available_ts - timedelta(hours=off)
        # tomar el último índice con fecha <= target_end_ts
        if "fecha" in df_station.columns:
            idx = df_station[df_station["fecha"] <= target_end_ts].index
            if len(idx) == 0:
                # si el offset se va más atrás que el histórico, caer al inicio
                end_pos = 23
            else:
                end_pos = df_station.index.get_loc(idx[-1])
            start_pos = max(0, end_pos - 23)
            df_last_24h = df_station.iloc[start_pos : end_pos + 1].copy()
        else:
            df_last_24h = df_station.tail(24).copy()

        if len(df_last_24h) < 24:
            raise ValueError(f"No hay suficientes datos (24h) para {real_station} con offset_hours={off}")

        # --- Sprint 5: metadata de frescura ---
        if "fecha" in df_last_24h.columns:
            # Importante: el CSV suele venir sin timezone; lo tratamos como UTC
            # para que el cliente (Flutter) pueda parsear correctamente con sufijo 'Z'.
            last_ts = pd.to_datetime(df_last_24h["fecha"].iloc[-1], utc=True)
            first_ts = pd.to_datetime(df_last_24h["fecha"].iloc[0], utc=True)
        elif df_last_24h.index.name == "fecha":
            last_ts = pd.to_datetime(df_last_24h.index[-1], utc=True)
            first_ts = pd.to_datetime(df_last_24h.index[0], utc=True)
        else:
            last_ts = datetime.now(timezone.utc)
            first_ts = last_ts

        # Normalizar a ISO UTC con sufijo 'Z' (evita que Flutter lo interprete como hora local)
        last_iso = last_ts.to_pydatetime().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        first_iso = first_ts.to_pydatetime().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

        meta = {
            "data_timestamp": last_iso,
            "data_window_start": first_iso,
            "data_age_minutes": int(
                (datetime.now(timezone.utc) - last_ts.to_pydatetime().astimezone(timezone.utc)).total_seconds() // 60
            ),
        }

        cols_to_scale = self.feature_cols
        data_to_scale = df_last_24h[cols_to_scale]
        scaled = self.scaler.transform(data_to_scale)  # (24, 44)
        final_features = np.expand_dims(scaled, axis=0)  # (1, 24, 44)
        return final_features, real_station, meta

    def get_features_for_horizon(
        self, station_name: str, horizon_hours: int = 0
    ) -> Tuple[np.ndarray, str, dict]:
        """Extrae features para un horizonte futuro ajustando las variables temporales.

        Para h=0 equivale a get_features(). Para h>0, toma la última ventana
        disponible y modifica las codificaciones temporales (hora_sin/cos,
        hora_del_dia, dia_de_la_semana, is_weekend, mes, mes_sin/cos) para
        reflejar el instante ``now + horizon_hours``. De este modo el modelo
        LSTM recibe la señal temporal correcta y produce predicciones
        genuinamente distintas por horizonte.
        """
        # Obtenemos la ventana base más reciente (offset=0)
        features, real_station, meta = self.get_features(station_name, offset_hours=0)

        if horizon_hours <= 0:
            return features, real_station, meta

        import pandas as pd
        from datetime import datetime, timezone, timedelta

        # Construir el timestamp objetivo
        now = datetime.now(timezone.utc)
        target_time = now + timedelta(hours=int(horizon_hours))

        # Mapeo nombre-col → índice en el vector de 44 features
        col_idx = {c: i for i, c in enumerate(self.feature_cols)}

        # Valores temporales para el instante futuro
        target_hour = target_time.hour
        target_dow = target_time.weekday()  # 0=lunes … 6=domingo
        target_month = target_time.month
        target_weekend = 1 if target_dow >= 5 else 0
        target_fallas = 1 if (target_month == 3 and 15 <= target_time.day <= 19) else 0

        hora_sin = np.sin(2 * np.pi * target_hour / 24)
        hora_cos = np.cos(2 * np.pi * target_hour / 24)
        mes_sin = np.sin(2 * np.pi * target_month / 12)
        mes_cos = np.cos(2 * np.pi * target_month / 12)

        # Crear copia mutable y ajustar los últimos pasos de la ventana.
        # Modificamos los últimos 6 pasos para suavizar la transición temporal.
        adjusted = features.copy()
        n_steps_to_adjust = min(6, adjusted.shape[1])

        # Necesitamos escalar los valores temporales nuevos usando los rangos
        # del MinMaxScaler original.
        data_min = self.scaler.data_min_
        data_max = self.scaler.data_max_
        data_range = data_max - data_min
        data_range[data_range == 0] = 1.0  # evitar div/0

        temporal_updates = {
            "hora_del_dia": float(target_hour),
            "dia_de_la_semana": float(target_dow),
            "mes": float(target_month),
            "is_weekend": float(target_weekend),
            "is_fallas": float(target_fallas),
            "hora_sin": hora_sin,
            "hora_cos": hora_cos,
            "mes_sin": mes_sin,
            "mes_cos": mes_cos,
        }

        for col_name, raw_value in temporal_updates.items():
            if col_name not in col_idx:
                continue
            idx = col_idx[col_name]
            # MinMax scale: (x - min) / (max - min)
            scaled_val = (raw_value - data_min[idx]) / data_range[idx]
            scaled_val = np.clip(scaled_val, 0.0, 1.0)
            for step in range(adjusted.shape[1] - n_steps_to_adjust, adjusted.shape[1]):
                adjusted[0, step, idx] = scaled_val

        # Actualizar meta para reflejar que es un forecast
        meta["horizon_hours"] = horizon_hours
        meta["target_time_utc"] = target_time.isoformat().replace("+00:00", "Z")

        return adjusted, real_station, meta

    def inverse_transform_predictions(self, y_scaled: np.ndarray) -> Dict[str, float]:
        """
        Convierte la predicción normalizada del modelo (1,3) o (3,) a µg/m³ reales.
        Devuelve dict con llaves: pm25, no2, o3
        """
        y_scaled = np.asarray(y_scaled, dtype=np.float32)
        if y_scaled.ndim == 2 and y_scaled.shape[0] == 1:
            y_scaled = y_scaled.reshape(-1)
        if y_scaled.ndim == 1:
            y_scaled = y_scaled.reshape(1, -1)

        # Invert MinMax scaling for only the target columns by building a dummy row.
        targets = getattr(self, "targets", ["pm25", "no2", "o3"])
        feature_cols = self.feature_cols
        target_idx = [feature_cols.index(t) for t in targets]

        n = y_scaled.shape[0]
        dummy = np.zeros((n, len(feature_cols)), dtype=np.float32)
        for j, idx in enumerate(target_idx):
            dummy[:, idx] = y_scaled[:, j]

        inv_full = self.scaler.inverse_transform(dummy)
        inv = inv_full[:, target_idx]
        pm25, no2, o3 = inv[0, :].tolist()
        return {"pm25": float(pm25), "no2": float(no2), "o3": float(o3)}

