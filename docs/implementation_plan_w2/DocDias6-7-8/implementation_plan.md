# Plan de Implementación: Días 6, 7, 8 — Semana 2

## Contexto

Se completó el entrenamiento inicial del modelo LSTM para predicción de PM2.5 en el notebook `05_Colab_LSTM_Model.ipynb`. El modelo actual presenta:
- **Arquitectura**: 3 capas LSTM apiladas (128→64→32 unidades) con Dropout + Dense(16) + Dense(1)
- **Métricas (escala real)**: MAE ≈ 2.99 µg/m³ | RMSE ≈ 4.82 µg/m³ | R² ≈ 0.75
- **Dataset**: ~195K secuencias de 24 horas, 7 estaciones, 22 features
- **Hiperparámetros**: lr=0.001, batch=256, optimizer=Adam, dropout=0.2/0.3

El plan de preparación (`preparacionDias6-7-8.md`) define tres días de trabajo. Se crearán notebooks Colab para las tareas que requieran entrenamiento (el usuario los ejecutará manualmente).

> [!IMPORTANT]
> Los notebooks/scripts que impliquen entrenamiento largo **no se ejecutarán** — serán preparados para que el usuario los ejecute en Google Colab.

---

## Día 6 (Martes) — Exploración Sistemática de Hiperparámetros

### Deliverables
| # | Tarea | Archivo |
|---|-------|---------|
| 6.1 | Ampliar y completar `hyperparams_grid.json` con un grid más exhaustivo (lr: [1e-4, 5e-4, 1e-3], batch: [32, 64, 128, 256], optimizer: [adam, rmsprop], dropout: [0.2, 0.3, 0.4], seq_length: [24, 48]) | `hyperparams_grid.json` |
| 6.2 | Crear un Colab notebook con función reutilizable `train_lstm()` que acepte los hiperparámetros del grid, entrene, registre métricas (loss, MAE para train & val) y guarde el mejor checkpoint | `notebooks/06_Colab_HyperParam_Search.ipynb` |
| 6.3 | El notebook incluirá lógica para ejecutar el grid completo, guardar resultados en CSV `day6_hyperparams_results.csv` y generar heatmaps de validación MAE vs lr/dropout | `notebooks/06_Colab_HyperParam_Search.ipynb` |
| 6.4 | Análisis de resultados con visualizaciones (heatmaps) integrado en el propio notebook | Dentro del notebook |
| 6.5 | Selección automática de la mejor configuración y guardado del checkpoint | Dentro del notebook |

---

## Día 7 (Miércoles) — Arquitectura & Feature Engineering

### Deliverables
| # | Tarea | Archivo |
|---|-------|---------|
| 7.1 | Añadir encodings cíclicos (sin/cos de hora del día y día de la semana) como nuevas features al pipeline de datos | `notebooks/07_Colab_Architecture_Experiments.ipynb` |
| 7.2 | Definir variantes arquitectónicas: LSTM 2-capas, LSTM 3-capas, Bidirectional LSTM | Dentro del notebook |
| 7.3 | Implementar una capa de atención simple (Bahdanau) después de la última salida LSTM | Dentro del notebook |
| 7.4 | (Opcional) Conexiones residuales del input a la capa dense penúltima | Dentro del notebook |
| 7.5 | Entrenar cada arquitectura con los mejores hiperparámetros del Día 6, registrar métricas en `day7_architecture_results.csv` | Dentro del notebook |
| 7.6 | Visualizar curvas de entrenamiento y comparar MAE/RMSE de validación entre arquitecturas | Dentro del notebook |
| 7.7 | Seleccionar la arquitectura ganadora (menor MAE de validación) y guardar checkpoint | Dentro del notebook |

---

## Día 8 (Jueves) — Trucos Avanzados de Entrenamiento & Evaluación Rigurosa

### Deliverables
| # | Tarea | Archivo |
|---|-------|---------|
| 8.1 | Implementar Early Stopping mejorado (monitorear val MAE con patience 5, restore best weights) | `notebooks/08_Colab_Advanced_Training_Eval.ipynb` |
| 8.2 | Implementar ReduceLROnPlateau (factor 0.5, cooldown 2) | Dentro del notebook |
| 8.3 | Regularización L2 (1e-4) y/o GaussianNoise en inputs | Dentro del notebook |
| 8.4 | Ensemble: entrenar 3 modelos con distintas seeds, promediar predicciones | Dentro del notebook / `src/ensemble_predict.py` |
| 8.5 | Cross-validation con TimeSeriesSplit (5-fold respetando cronología), computar media/desviación de MAE | CSV `day8_cv_results.csv` |
| 8.6 | Análisis de errores: true vs predicted, distribución de residuos, sesgo sistemático | Figuras dentro del notebook |
| 8.7 | Documentación: sección "Training & Evaluation" resumiendo hallazgos, hiperparámetros y rendimiento final | Celdas markdown en el notebook |

---

## Estructura de archivos a crear/modificar

```
AirVLCProyecto/
├── hyperparams_grid.json                          # [MODIFY] Grid ampliado
├── notebooks/
│   ├── 06_Colab_HyperParam_Search.ipynb          # [NEW] Día 6
│   ├── 07_Colab_Architecture_Experiments.ipynb    # [NEW] Día 7
│   └── 08_Colab_Advanced_Training_Eval.ipynb      # [NEW] Día 8
└── src/
    └── ensemble_predict.py                        # [NEW] Ensemble (Día 8)
```

---

## Verificación

### Checks Automatizados
- Tras el Día 8, el ensemble final debería lograr **MAE < 2.5 µg/m³** (la baseline actual es ~3.0 µg/m³)
- Reproducibilidad: todos los scripts aceptan `seed` y fijan NumPy/TF seeds
- Verificación de existencia de archivos de salida (`*_results.csv`, PNGs, checkpoints)

### Revisión Manual
- Loss curves suaves, sin divergencia, early stopping trunca el entrenamiento correctamente
- Residuos con media ≈ 0 y homocedasticidad
- Notebooks legibles con markdown explicativo

---

> [!NOTE]
> **Recuerda**: Los notebooks Colab se crearán listos para ejecutar, pero **no se ejecutarán** desde aquí. El usuario los ejecutará en Google Colab manualmente.
