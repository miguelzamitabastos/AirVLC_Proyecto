# Sprint 2 v2 — Modelado Multitarget en Google Colab

> Sprint preparado el 5 de mayo de 2026.
> El entrenamiento real lo ejecutas tú en Colab; aquí dejamos los
> artefactos listos y validados localmente.

## 1. Objetivo

Tomar `data/processed/master_dataset_colab_v2.csv` (Sprint 1) y
producir un **modelo Keras nativo multitarget** capaz de predecir
simultáneamente **PM2.5, NO₂ y O₃** a 1 hora vista, comparando
3 arquitecturas:

1. `LSTM_Attention_Multi` — LSTM 2 capas + Bahdanau Attention.
2. `CNN_LSTM_Attention_Multi` — Conv1D → LSTM → Attention.
3. `Transformer_Encoder_Multi` — MultiHeadAttention nativa Keras + LN + GAP.

> **Recordatorio**: la decisión 2 de [`implementation_plan.md`](../implementation_plan.md)
> descartó PyTorch/TFT por riesgo de bloqueo. Las 3 arquitecturas
> son 100 % Keras/TensorFlow y caben sin esfuerzo en una GPU T4.

## 2. Decisiones técnicas

### 2.1 Split temporal **por estación**

`src/ml/prepare_dataset_v2.py::chronological_split_by_station`
divide cada estación en 80 / 10 / 10 cronológico. Esto:

- Evita data leakage de futuro a pasado (no usamos `train_test_split`
  aleatorio).
- Mantiene la deriva estacional/anual de cada sitio (el puerto solo
  tiene 2020-2021; las urbanas 2016-2021).
- Hace que el test sea siempre lo más reciente de cada estación —
  el escenario realista de despliegue.

### 2.2 Sequencing con descarte de gaps

Cada ventana de 24 h se valida: si la diferencia máxima entre dos
timestamps consecutivos supera 1 h, se descarta. Las estaciones del
portal valenciano tienen huecos de meses; sin este filtro
construiríamos secuencias artificiales saltando 2018→2019.

Resultado típico (verificado localmente):

```
Train rows: 155,992  →  X_train: (28,321, 24, 44)
Val   rows:  19,497  →  X_val:   ( ~3,500, 24, 44)
Test  rows:  19,504  →  X_test:  ( ~3,500, 24, 44)
```

### 2.3 Scaler único compartido (`models/scaler_v2.pkl`)

`src/ml/generate_scaler_v2.py` ajusta un `MinMaxScaler` **solo sobre
el split de train** (sin contaminar con val/test). Se persiste con
sus `feature_cols` y se carga tanto en el notebook como en la futura
API v2 (Sprint 3). Así garantizamos reproducibilidad 1:1 entre
entrenamiento e inferencia.

### 2.4 Targets multitarget en una sola salida `Dense(3)`

Las 3 arquitecturas terminan con `Dense(3)` y entrenan con `mse`.
Hay un experimento opcional con **loss asimétrica** (`alpha=2.0`)
que penaliza más la infrapredicción — útil para no quedarse cortos
en picos de O₃ o NO₂ que es donde hay más riesgo sanitario.

### 2.5 Ranking por **R² medio** entre los 3 targets

`day11_v2_results.csv` tendrá una fila por (arquitectura, target). El
ganador se elige por la media de R² entre los 3 targets. Reportamos
también MAE y RMSE por target en µg/m³ reales (vía
`inverse_transform_targets`).

## 3. Entregables

| Fichero | Qué hace |
|---|---|
| `src/ml/prepare_dataset_v2.py` | Carga CSV v2 + split por estación + secuencias multitarget + inverse-transform. Reutilizable desde notebook y desde API v2. |
| `src/ml/generate_scaler_v2.py` | Genera `models/scaler_v2.pkl` (scaler + feature_cols). |
| `src/scripts/generate_v2_notebook.py` | Regenera el .ipynb desde plantilla. |
| `notebooks/11_v2_Colab_Multitarget.ipynb` | Notebook **autocontenido** con las 3 arquitecturas, train/eval/export. |
| `models/scaler_v2.pkl` | Scaler oficial v2 (44 features). |

Tras correr el notebook en Colab, en tu Drive aparecerá:

```
modelo_11_v2_Multitarget/
├── best_model_v2.keras           # ganador (loss MSE)
├── best_model_v2_asym.keras      # opcional: ganador con loss asimétrica
├── day11_v2_results.csv          # métricas por (arch, target)
└── training_history.json         # curvas de las 3 arquitecturas
```

## 4. Cómo ejecutarlo

### 4.1 Localmente (preparación)

```bash
venv/bin/python src/ml/generate_scaler_v2.py
venv/bin/python src/scripts/generate_v2_notebook.py
```

Esto genera `models/scaler_v2.pkl` y
`notebooks/11_v2_Colab_Multitarget.ipynb`.

### 4.2 En Colab (entrenamiento real)

1. Sube a tu Drive en `MyDrive/AirVLC_v2/`:
   - `master_dataset_colab_v2.csv` (66 MB).
   - `scaler_v2.pkl` (~3 KB).
2. Abre `notebooks/11_v2_Colab_Multitarget.ipynb` en Colab con runtime
   GPU (T4).
3. Ejecuta de arriba a abajo. Las 3 arquitecturas tardan
   ~20-30 min cada una en T4 con `EPOCHS=60`, `BATCH=128` y
   `EarlyStopping(patience=8)`.
4. Cuando termine, descarga la carpeta `modelo_11_v2_Multitarget/`
   a `models/modelo_11_v2_Multitarget/` en local.

## 5. Criterios de aceptación

- ✅ El notebook se genera sin errores y `nbformat.validate` pasa.
- ✅ Las 3 arquitecturas construyen con `output_shape == (None, 3)`
  (verificado localmente).
- ✅ `scaler_v2.pkl` carga y tiene 44 `feature_cols`.
- ✅ Cuando corras Colab: `r2 > 0.5` en al menos 2 de los 3 targets
  (referencia v1: PM2.5 R² = 0.7672 con LSTM_Attention monotarget).
- ✅ El ganador exporta a `.keras` y se puede recargar con
  `keras.models.load_model(..., custom_objects={'BahdanauAttention': BahdanauAttention})`.

## 6. Próximo paso

Cuando vuelvas con los `.keras` de Colab, abrimos otra tanda para
**Sprint 3 — Backend Flask v2**:

- `src/api/feature_extractor_v2.py` (carga scaler v2 + dataset v2).
- `src/ml/risk_classifier_v2.py` (peor de los 3 contaminantes).
- Rutas `/api/v2/predict`, `/api/v2/risk`, `/api/v2/chat`.
- Indexar predicciones en `airvlc-predictions-v2`.
