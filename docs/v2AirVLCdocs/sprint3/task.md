# Sprint 3 — Task (Backend Flask v2)

## Checklist

### Extractor v2

- [x] Crear `src/api/feature_extractor_v2.py`
- [x] Leer `feature_names_in_` desde `models/scaler_v2.pkl` (sin hardcodear features)
- [x] `get_features(station) -> (1, 24, 44)`
- [x] `inverse_transform_predictions -> pm25/no2/o3` en µg/m³

### RiskClassifier v2

- [x] Crear `src/ml/risk_classifier_v2.py`
- [x] Umbrales por contaminante (PM2.5 / NO₂ / O₃)
- [x] Devolver peor contaminante + desglose + `reply_text`

### Loader / custom objects

- [x] Añadir `src/api/_keras_custom.py` con `BahdanauAttention`
- [x] Cargar `best_model_v2.keras` como `LSTM_Attention_Multi` en `ModelLoader`

### Rutas v2

- [x] Crear `src/api/routes_v2.py` y registrar blueprint `/api/v2`
- [x] `GET /api/v2/health`
- [x] `POST /api/v2/predict`
- [x] `POST /api/v2/risk`
- [x] `POST /api/v2/chat`

### Orquestador NLU v2

- [x] Crear `src/services/chatbot_orchestrator_v2.py` (Lex → inferencia multitarget → reply)

### Elasticsearch v2

- [x] Crear `ES_INDEXER_V2` en `src/api/app.py` para `airvlc-predictions-v2`
- [x] Extender documento ES con campos v2 (sin romper v1)

### Tests y demo local

- [ ] Añadir `pytest` y tests mínimos de contrato JSON para `/api/v2/*`
- [ ] Smoke test v1 unchanged
- [ ] Probar localmente con `curl` a `/api/v2/predict` y `/api/v2/risk`

## Enlaces

- Plan: [`implementation_plan.md`](implementation_plan.md)
- Walkthrough (rellenar al cierre): [`walkthrough.md`](walkthrough.md)
- Contexto Sprint 2: [`../sprint2/walkthrough.md`](../sprint2/walkthrough.md)

