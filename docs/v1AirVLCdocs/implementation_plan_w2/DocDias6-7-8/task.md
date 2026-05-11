# Tareas — Semana 2, Días 6-7-8

## Día 6 — Exploración de Hiperparámetros
- [x] 6.1 Ampliar `hyperparams_grid.json` con grid exhaustivo (16 configuraciones)
- [x] 6.2 Crear script Colab `06_Colab_HyperParam_Search.py` con `train_lstm()` reutilizable
- [x] 6.3 Grid search completo + guardado CSV de resultados + heatmaps

## Día 7 — Arquitectura & Feature Engineering
- [x] 7.1 Crear script Colab `07_Colab_Architecture_Experiments.py`
- [x] 7.2 Encodings cíclicos + variantes arquitectónicas (Bidirectional, Attention, 2-Layer, 3-Layer)
- [x] 7.3 Entrenamiento, comparación y selección de arquitectura ganadora

## Día 8 — Entrenamiento Avanzado & Evaluación
- [x] 8.1 Crear script Colab `08_Colab_Advanced_Training_Eval.py`
- [x] 8.2 Early stopping mejorado (val_mae, patience=5) + LR scheduling (cooldown=2) + regularización L2 + GaussianNoise + ensemble 3 modelos
- [x] 8.3 Cross-validation temporal (TimeSeriesSplit 5-fold) + análisis de errores (real vs pred, residuos, Q-Q plot, homocedasticidad)
- [x] 8.4 Crear `src/ml/ensemble_predict.py` con clase EnsemblePredictor
