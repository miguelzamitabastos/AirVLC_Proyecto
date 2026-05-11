# Sprint 2 v2 — Tareas

> Plan completo: [`implementation_plan.md`](implementation_plan.md).
> Walkthrough técnico: [`walkthrough.md`](walkthrough.md).

## Preparación local (cerrada)

- [x] `src/ml/prepare_dataset_v2.py` — utilidades reutilizables:
    - [x] `load_v2_dataset` (parsea fecha, ordena por estación).
    - [x] `chronological_split_by_station` (80/10/10 por estación).
    - [x] `build_sequences_multitarget` (descarta gaps > 1 h).
    - [x] `inverse_transform_targets` (µg/m³ reales para reportes).
- [x] `src/ml/generate_scaler_v2.py` + `models/scaler_v2.pkl` (44 features).
- [x] `src/scripts/generate_v2_notebook.py` — generador del .ipynb por plantilla.
- [x] `notebooks/11_v2_Colab_Multitarget.ipynb` — 27 celdas, 3 arquitecturas.
- [x] Test de construcción de las 3 arquitecturas localmente:
    - LSTM_Attention_Multi → 148,548 params, output (B, 3).
    - CNN_LSTM_Attention_Multi → 98,372 params, output (B, 3).
    - Transformer_Encoder_Multi → 107,331 params, output (B, 3).
- [x] Documentación: `implementation_plan.md`, `task.md`, `walkthrough.md` stub.

## Pendiente (lo ejecutas tú en Colab)

- [ ] Subir `master_dataset_colab_v2.csv` y `scaler_v2.pkl` a `MyDrive/AirVLC_v2/`.
- [ ] Abrir `notebooks/11_v2_Colab_Multitarget.ipynb` en Colab con runtime GPU.
- [ ] Ejecutar el notebook completo (EPOCHS=60, BATCH=128).
- [ ] Comprobar el ranking por R² medio entre los 3 targets.
- [ ] (Opcional) correr la celda de loss asimétrica (`alpha=2.0`).
- [ ] Descargar `modelo_11_v2_Multitarget/` a `models/` local.
- [ ] Volver y completar `walkthrough.md` con métricas reales y elección de ganador.

## Aceptación

- [ ] `r2 ≥ 0.5` en al menos 2 de los 3 targets (referencia v1 monotarget: 0.77).
- [ ] El ganador se carga con `keras.models.load_model(..., custom_objects=...)`.
- [ ] `day11_v2_results.csv` está en `models/modelo_11_v2_Multitarget/`.
