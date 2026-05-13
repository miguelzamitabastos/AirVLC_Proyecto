# Sprint 3 — Backend Flask v2 (multitarget)

## Objetivo

Evolucionar el backend Flask para servir el **modelo v2 multitarget** (PM2.5, NO₂, O₃) sin romper v1, añadiendo:

- Rutas nuevas `/api/v2/*` en paralelo a `/api/*`.
- Extracción de features v2 (44 features, ventana 24 h) para inferencia.
- Clasificación de riesgo tipo ICA (devuelve el **peor** de los 3 contaminantes + desglose).
- Orquestación NLU (Lex) que narra el peor contaminante y muestra los 3 valores.
- Indexación a Elasticsearch en un índice nuevo `airvlc-predictions-v2`.

Este sprint implementa la parte “Sprint 3” descrita en [`docs/v2AirVLCdocs/implementation_plan.md`](../implementation_plan.md).

## Contexto (inputs de Sprint 2)

- Modelo ganador: `models/modelo_11_v2_Multitarget/best_model_v2.keras` (requiere `BahdanauAttention`).
- Scaler oficial: `models/scaler_v2.pkl` con `feature_names_in_` (44 columnas).
- Dataset de inferencia: `data/processed/master_dataset_colab_v2.csv`.
- Walkthrough del entrenamiento v2: [`docs/v2AirVLCdocs/sprint2/walkthrough.md`](../sprint2/walkthrough.md).

## Decisiones clave

- **Compatibilidad v1↔v2**: v1 queda intacto (misma API, mismas rutas). v2 se expone con un blueprint dedicado.
- **Extractor paralelo**: `FeatureExtractorV2` no “mezcla flags” con v1; evita deuda técnica.
- **Riesgo ICA-like**: se clasifica cada contaminante y se devuelve el peor nivel (labels compatibles: `bueno/moderado/malo/peligroso`).
- **Index separado**: v2 escribe en `airvlc-predictions-v2`.

## Contrato de ficheros (código)

### `src/api/feature_extractor_v2.py` (nuevo)

- Carga `master_dataset_colab_v2.csv` + `scaler_v2.pkl`.
- `get_features(station)` → `(np.ndarray (1, 24, 44), real_station)`.
- `inverse_transform_predictions(y_scaled)` → `{'pm25': float, 'no2': float, 'o3': float}` en µg/m³.

### `src/ml/risk_classifier_v2.py` (nuevo)

- `classify_multi(pm25, no2, o3, station=None)` →
  - `pollutants`: detalle por contaminante (level/color/emoji/value)
  - `worst`: contaminante dominante (ICA)
  - `reply_text`: narración humana

### `src/api/routes_v2.py` (nuevo)

Blueprint `/api/v2`:

- `GET /api/v2/health`
- `POST /api/v2/predict` (por `station` o por `features`)
- `POST /api/v2/risk` (por valores directos o prediciendo primero)
- `POST /api/v2/chat` (Lex → predicción multitarget → reply)

### `src/services/chatbot_orchestrator_v2.py` (nuevo)

Mantiene intent `ConsultarCalidad` (Lex), pero devuelve respuesta multitarget.

### `src/api/model_loader.py` (modificado)

- Carga preferente del modelo `LSTM_Attention_Multi` si está disponible.
- `custom_objects={'BahdanauAttention': BahdanauAttention}` para el modelo v2.

### `src/api/es_indexer.py` y `src/api/app.py` (modificados)

- Indexer v2: `ESIndexer(index_name='airvlc-predictions-v2')` guardado en `app.config['ES_INDEXER_V2']`.
- Documento ES v2: campos opcionales `pm25_pred/no2_pred/o3_pred`, riesgo por contaminante y peor contaminante.

## Criterios de aceptación

- `POST /api/v2/predict` devuelve `predictions.pm25/no2/o3` + `unit: µg/m³`.
- `POST /api/v2/risk` devuelve `worst.pollutant` y `reply_text` nombrando explícitamente los 3 contaminantes.
- v1 (`/api/predict`, `/api/risk`, `/api/chat`) no cambia su contrato.
- Si ES está disponible, se crean documentos en `airvlc-predictions-v2`.

