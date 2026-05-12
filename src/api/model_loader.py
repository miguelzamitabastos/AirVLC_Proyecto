"""
===================================================================
📦 Model Loader — Carga de modelos LSTM para la API
===================================================================
Gestiona la carga y uso de modelos .keras para predicción.
Soporta modelo individual y ensemble.
===================================================================
"""

import os
import glob
import numpy as np
import json

# Importación condicional de TensorFlow (puede ser pesado)
try:
    import tensorflow as tf
    from tensorflow.keras.layers import Layer, Dense

    from src.api._keras_load_compat import load_keras_model_compat
    # Permitir deserialización de capas Lambda (fallback para modelos legacy)
    tf.keras.config.enable_unsafe_deserialization()

    def _configure_tensorflow_runtime():
        """GPU: memoria no reservada de golpe; CPU forzada vía AIRVLC_TF_CPU_ONLY=1."""
        if os.environ.get("AIRVLC_TF_CPU_ONLY", "").lower() in ("1", "true", "yes"):
            try:
                tf.config.set_visible_devices([], "GPU")
            except Exception:
                pass
        # Evita fallos INTERNAL del autotuner XLA en algunas GPUs/arquitecturas nuevas.
        try:
            jit_off = getattr(tf.config.optimizer, "set_jit", None) or getattr(
                tf.config.optimizer, "set_optimizer_jit", None
            )
            if callable(jit_off):
                jit_off(False)
        except Exception:
            pass
        gpus = tf.config.list_physical_devices("GPU")
        for g in gpus:
            try:
                tf.config.experimental.set_memory_growth(g, True)
            except Exception:
                pass
        if gpus:
            names = ", ".join(g.name for g in gpus)
            print(
                f"  🎮 TensorFlow usará la(s) GPU para inferencia Keras "
                f"({len(gpus)}): {names}. "
                f"CPU forzada: AIRVLC_TF_CPU_ONLY=1."
            )
        else:
            print("  💻 TensorFlow: sin GPU visible; inferencia en CPU.")

    _configure_tensorflow_runtime()

    # Custom objects (v2 multitarget)
    try:
        from src.api._keras_custom import BahdanauAttention
    except Exception:  # pragma: no cover
        BahdanauAttention = None

    # Registrar capa custom de Atención para que load_model la reconozca
    @tf.keras.utils.register_keras_serializable(package="AirVLC")
    class AttentionLayer(Layer):
        """Capa de atención Bahdanau serializable."""
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
        def build(self, input_shape):
            self.score_dense = Dense(1, activation='tanh', name='attention_score')
            super().build(input_shape)
        def call(self, inputs):
            scores = self.score_dense(inputs)
            weights = tf.nn.softmax(scores, axis=1)
            context = tf.reduce_sum(inputs * weights, axis=1)
            return context
        def get_config(self):
            return super().get_config()

    TF_AVAILABLE = True
except ImportError:
    tf = None  # noqa: F401  — evita NameError en helpers si TF no está instalado
    TF_AVAILABLE = False
    print("⚠️ TensorFlow no disponible. Las predicciones LSTM no funcionarán.")

try:
    from sklearn.preprocessing import MinMaxScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


class ModelLoader:
    """
    Gestiona la carga de modelos LSTM para la API de predicción.
    Busca modelos en el directorio de modelos del proyecto.
    """

    def __init__(self, models_dir):
        """
        Args:
            models_dir: Ruta al directorio 'models/' del proyecto
        """
        self.models_dir = models_dir
        self.models = {}
        self.best_model = None
        self.best_model_name = None
        self.model_info = {}
        # Clones en CPU por id(model) cuando la GPU falla (XLA/sm_120); se reutilizan.
        self._cpu_shadow_models = {}

        self._scan_and_load()

    def _scan_and_load(self):
        """Escanea el directorio de modelos y carga los disponibles."""
        if not TF_AVAILABLE:
            print("  ⚠️ TensorFlow no disponible, omitiendo carga de modelos")
            return

        if not os.path.exists(self.models_dir):
            print(f"  ⚠️ Directorio de modelos no encontrado: {self.models_dir}")
            return

        # Buscar modelos .keras en subdirectorios
        keras_files = glob.glob(os.path.join(self.models_dir, '**', '*.keras'), recursive=True)

        if not keras_files:
            print(f"  ⚠️ No se encontraron modelos .keras en {self.models_dir}")
            return

        print(f"  📦 Encontrados {len(keras_files)} modelos .keras")

        # Intentar cargar el mejor modelo
        # Prioridad: attention_fixed > attention_original > day7 best > day6 best
        priority_models = [
            ('LSTM_Attention_Multi', os.path.join(self.models_dir, 'modelo_11_v2_Multitarget', 'best_model_v2.keras')),
            ('LSTM_Attention', os.path.join(self.models_dir, 'modelo_07_Colab', 'lstm_attention_fixed.keras')),
            ('LSTM_Attention', os.path.join(self.models_dir, 'modelo_07_Colab', 'lstm_attention_day7.keras')),
            ('Best_Day7', os.path.join(self.models_dir, 'modelo_07_Colab', 'best_model_day7.keras')),
            ('Best_Day6', os.path.join(self.models_dir, 'modelo_06_Colab', 'best_model_day6.keras')),
        ]

        for name, path in priority_models:
            if not os.path.exists(path):
                continue
            if name in self.models:
                continue  # Ya cargado (ej: attention_fixed ya cargó, no intentar la original)
            try:
                # v2 model requires BahdanauAttention
                if name == 'LSTM_Attention_Multi' and BahdanauAttention is not None:
                    model = load_keras_model_compat(
                        path, custom_objects={'BahdanauAttention': BahdanauAttention}
                    )
                else:
                    model = load_keras_model_compat(path)
                self.models[name] = model
                if self.best_model is None:
                    self.best_model = model
                    self.best_model_name = name
                print(f"  ✅ Cargado: {name} ({os.path.basename(path)})")
            except Exception as e:
                print(f"  ⏭️  Omitido: {name} (error: {str(e)})")

        # Cargar ensemble si existe
        ensemble_dir = os.path.join(self.models_dir, 'modelo_08_Colab', 'ensemble_models')
        if os.path.exists(ensemble_dir):
            ensemble_files = sorted(glob.glob(os.path.join(ensemble_dir, '*.keras')))
            if ensemble_files:
                ensemble_models = []
                for ef in ensemble_files:
                    try:
                        m = load_keras_model_compat(ef)
                        ensemble_models.append(m)
                    except Exception:
                        pass  # Silenciar errores individuales del ensemble
                if ensemble_models:
                    self.models['Ensemble'] = ensemble_models
                    print(f"  ✅ Ensemble cargado: {len(ensemble_models)} modelos")
                else:
                    print(f"  ⏭️  Omitido: Ensemble (usa capas Lambda incompatibles con TF local)")

        # Resumen
        if self.models:
            print(f"  🎯 Modelo activo: {self.best_model_name}")
        else:
            print("  ⚠️ No se pudo cargar ningún modelo")

        self._warmup_best_model_if_possible()

        # Cargar métricas si existen
        self._load_metrics()

    def _warmup_best_model_if_possible(self):
        """
        Una pasada predict() al arranque para que kernels CUDA/PTX se compilen
        antes del primer request (útil en GPUs muy nuevas, p. ej. sm_120).
        Desactivar: AIRVLC_TF_INFERENCE_WARMUP=0
        """
        if self.best_model is None:
            return
        if os.environ.get("AIRVLC_TF_INFERENCE_WARMUP", "1").lower() in ("0", "false", "no"):
            return
        spec = self.best_model.input_shape
        if spec is None or isinstance(spec, list):
            return
        rest = tuple(spec[1:])
        if not rest or any(d is None for d in rest):
            return
        try:
            dummy = np.zeros((1,) + rest, dtype=np.float32)
            self._predict_with_gpu_cpu_fallback(self.best_model, dummy)
            print("  🔥 Warmup inferencia en modelo activo (primera predict más rápida).")
        except Exception:
            pass

    def _predict_with_gpu_cpu_fallback(self, model, X_arr):
        """predict en GPU; si falla XLA/CUDA, reutiliza un clon en CPU con los mismos pesos."""
        if not TF_AVAILABLE or tf is None:
            raise RuntimeError("TensorFlow no está disponible")
        X_arr = np.asarray(X_arr, dtype=np.float32)
        try:
            return model.predict(X_arr, verbose=0)
        except Exception as e:
            msg = str(e).lower()
            retry_hints = (
                "internal",
                "xla",
                "autotuner",
                "invalid_argument",
                "different device",
                "cuda",
                "cudnn",
                "dnn",
                "gpu",
                "blas",
            )
            if not any(h in msg for h in retry_hints):
                raise
            try:
                mid = id(model)
                cpu_m = self._cpu_shadow_models.get(mid)
                if cpu_m is None:
                    with tf.device("/CPU:0"):
                        cpu_m = tf.keras.models.clone_model(model)
                        cpu_m.set_weights(model.get_weights())
                    self._cpu_shadow_models[mid] = cpu_m
                with tf.device("/CPU:0"):
                    return cpu_m.predict(X_arr, verbose=0)
            except Exception:
                raise e

    def _load_metrics(self):
        """Carga métricas de resultados de los CSVs."""
        import pandas as pd

        metrics_files = {
            'day7': os.path.join(self.models_dir, 'modelo_07_Colab', 'day7_architecture_results.csv'),
            'day8': os.path.join(self.models_dir, 'modelo_08_Colab', 'day8_advanced_results.csv'),
        }

        for day, path in metrics_files.items():
            if os.path.exists(path):
                try:
                    metrics_df = pd.read_csv(path)
                    self.model_info[day] = metrics_df.to_dict(orient='records')
                except Exception:
                    pass

    def predict(self, X, model_name=None):
        """
        Genera predicción con el modelo especificado.

        Args:
            X: array con forma (n_samples, seq_length, n_features), normalizado
            model_name: Nombre del modelo. Si None, usa el mejor.

        Returns:
            array de predicciones (normalizadas)
        """
        if model_name and model_name == 'Ensemble':
            return self._predict_ensemble(X)

        model = self.models.get(model_name, self.best_model)
        if model is None:
            raise ValueError("No hay modelos cargados")

        return self._predict_with_gpu_cpu_fallback(model, X)

    def _predict_ensemble(self, X):
        """Predicción promediada del ensemble."""
        ensemble = self.models.get('Ensemble', [])
        if not ensemble:
            raise ValueError("No hay modelos de ensemble cargados")

        predictions = [self._predict_with_gpu_cpu_fallback(m, X) for m in ensemble]
        return np.mean(predictions, axis=0)

    def get_info(self):
        """Devuelve información sobre los modelos cargados."""
        info = {
            'models_loaded': list(self.models.keys()),
            'best_model': self.best_model_name,
            'models_dir': self.models_dir,
            'tensorflow_available': TF_AVAILABLE,
        }

        # Añadir métricas si disponibles
        if 'day7' in self.model_info:
            info['day7_results'] = self.model_info['day7']
        if 'day8' in self.model_info:
            info['day8_results'] = self.model_info['day8']

        # Info del mejor modelo
        if self.best_model:
            info['best_model_input_shape'] = str(self.best_model.input_shape)
            info['best_model_params'] = self.best_model.count_params()

        return info

    @property
    def is_ready(self):
        """True si al menos un modelo está cargado."""
        return self.best_model is not None
