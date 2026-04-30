"""
===================================================================
🔮 Ensemble Predict — Predicción por Ensemble de Modelos LSTM
===================================================================
Carga los modelos del ensemble entrenados en el Día 8 y genera
predicciones promediadas para nuevos datos.

Uso:
    from ensemble_predict import EnsemblePredictor

    predictor = EnsemblePredictor(
        models_dir="/path/to/ensemble_models",
        scaler=fitted_scaler,
        pm25_col_idx=0,
        n_features=22
    )
    predictions = predictor.predict(X_new)
===================================================================
"""

import os
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import load_model


class EnsemblePredictor:
    """
    Predictor que carga múltiples modelos LSTM y promedia sus predicciones
    para obtener estimaciones más robustas de PM2.5.
    """

    def __init__(self, models_dir, scaler=None, pm25_col_idx=None, n_features=None):
        """
        Args:
            models_dir: Directorio donde se guardan los modelos .keras
            scaler: MinMaxScaler ya ajustado (para desnormalización)
            pm25_col_idx: Índice de la columna pm25 en el scaler
            n_features: Número total de features del scaler
        """
        self.models_dir = models_dir
        self.scaler = scaler
        self.pm25_col_idx = pm25_col_idx
        self.n_features = n_features
        self.models = []

        # Cargar todos los modelos .keras del directorio
        self._load_models()

    def _load_models(self):
        """Carga todos los modelos .keras del directorio ensemble."""
        if not os.path.exists(self.models_dir):
            raise FileNotFoundError(f"Directorio no encontrado: {self.models_dir}")

        model_files = sorted([
            f for f in os.listdir(self.models_dir)
            if f.endswith('.keras')
        ])

        if len(model_files) == 0:
            raise ValueError(f"No se encontraron modelos .keras en {self.models_dir}")

        for mf in model_files:
            model_path = os.path.join(self.models_dir, mf)
            model = load_model(model_path)
            self.models.append(model)
            print(f"  ✅ Modelo cargado: {mf}")

        print(f"  📦 Total modelos en ensemble: {len(self.models)}")

    def predict_scaled(self, X):
        """
        Genera predicciones en escala normalizada promediando los modelos.

        Args:
            X: array (n_samples, seq_length, n_features) normalizado

        Returns:
            array (n_samples,) con predicciones normalizadas
        """
        predictions = []
        for model in self.models:
            pred = model.predict(X, verbose=0)
            predictions.append(pred.flatten())

        # Promediar predicciones
        ensemble_pred = np.mean(predictions, axis=0)
        return ensemble_pred

    def predict(self, X, return_individual=False):
        """
        Genera predicciones en escala real (µg/m³) promediando los modelos.

        Args:
            X: array (n_samples, seq_length, n_features) normalizado
            return_individual: Si True, devuelve también las predicciones individuales

        Returns:
            array (n_samples,) con predicciones en escala real
            (opcional) lista de arrays con predicciones individuales
        """
        if self.scaler is None or self.pm25_col_idx is None or self.n_features is None:
            raise ValueError(
                "Se requiere scaler, pm25_col_idx y n_features para predicciones en escala real. "
                "Usa predict_scaled() para predicciones normalizadas."
            )

        individual_preds = []
        for model in self.models:
            pred_scaled = model.predict(X, verbose=0)
            pred_real = self._inverse_pm25(pred_scaled)
            individual_preds.append(pred_real)

        # Promediar predicciones
        ensemble_pred = np.mean(individual_preds, axis=0)

        if return_individual:
            return ensemble_pred, individual_preds
        return ensemble_pred

    def predict_with_uncertainty(self, X):
        """
        Genera predicciones con estimación de incertidumbre
        (desviación estándar entre los modelos del ensemble).

        Args:
            X: array (n_samples, seq_length, n_features) normalizado

        Returns:
            mean_pred: array (n_samples,) media de predicciones
            std_pred: array (n_samples,) desviación estándar
        """
        ensemble_pred, individual = self.predict(X, return_individual=True)
        std_pred = np.std(individual, axis=0)
        return ensemble_pred, std_pred

    def _inverse_pm25(self, values_scaled):
        """Desnormaliza valores de PM2.5 usando el scaler."""
        dummy = np.zeros((len(values_scaled), self.n_features))
        dummy[:, self.pm25_col_idx] = values_scaled.flatten()
        dummy_inv = self.scaler.inverse_transform(dummy)
        return dummy_inv[:, self.pm25_col_idx]

    @property
    def n_models(self):
        """Número de modelos en el ensemble."""
        return len(self.models)


# ==========================================
# Ejemplo de uso (descomenta para probar)
# ==========================================
# if __name__ == '__main__':
#     from sklearn.preprocessing import MinMaxScaler
#
#     ENSEMBLE_DIR = "/path/to/ensemble_models"
#     predictor = EnsemblePredictor(
#         models_dir=ENSEMBLE_DIR,
#         scaler=fitted_scaler,       # MinMaxScaler ya ajustado
#         pm25_col_idx=0,             # Índice de pm25 en cols_to_scale
#         n_features=22               # Número total de features
#     )
#
#     # Predicción con incertidumbre
#     mean_pred, std_pred = predictor.predict_with_uncertainty(X_test)
#     print(f"Predicción media: {mean_pred[:5]}")
#     print(f"Incertidumbre:    {std_pred[:5]}")
