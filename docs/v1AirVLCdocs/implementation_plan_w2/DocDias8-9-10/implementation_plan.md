# Plan de Implementación: Días 8, 9, 10 — Semana 2 (Final)

## Contexto

Se completaron los Días 6-7-8 del plan de preparación, con estos resultados:
- **Mejor modelo**: LSTM_Attention (MAE=2.64 µg/m³, R²=0.767)
- **Mejor hiperparámetros**: lr=0.001, batch=64, optimizer=rmsprop, dropout=0.2, seq=24
- **Ensemble**: 3 modelos guardados en `.keras`
- **CV temporal**: MAE medio real ~3.42 µg/m³

Ahora debemos completar la Semana 2 según el `implementation_plan.md`:
- **Jue 8**: Modelo HuggingFace: clasificación de niveles de riesgo
- **Vie 9**: Comparativa de modelos (FC vs LSTM vs CNN) + visualización resultados
- **Sáb 10**: API Flask: endpoints de predicción

> [!IMPORTANT]
> Los scripts de entrenamiento (Días 8-9) serán para ejecutar en Colab. La API Flask (Día 10) se creará localmente.

---

## Día 8 — Modelo HuggingFace: Clasificación de Niveles de Riesgo

### Concepto
Usar un modelo de HuggingFace para **clasificar el nivel de riesgo de calidad del aire** a partir de los valores de PM2.5. Se definirán 4 categorías según estándares OMS:

| Nivel | PM2.5 (µg/m³) | Etiqueta |
|-------|---------------|----------|
| 🟢 Bueno | 0 – 12 | `bueno` |
| 🟡 Moderado | 12.1 – 35.4 | `moderado` |
| 🟠 Malo | 35.5 – 55.4 | `malo` |
| 🔴 Peligroso | > 55.4 | `peligroso` |

### Enfoque
Dado que es un problema de clasificación sobre datos tabulares/numéricos (no texto), usaremos un enfoque práctico:
1. **Clasificador basado en features**: Tomar las mismas features del dataset, crear la etiqueta de riesgo a partir de PM2.5 real, y entrenar un modelo de clasificación
2. **Usar HuggingFace para**: Fine-tuning de un modelo tabular (ej: `TabTransformer`) o, alternativamente, usar HuggingFace `pipeline` con un modelo de texto para generar descripciones de riesgo a partir de los datos numéricos

### Deliverables
| # | Archivo | Descripción |
|---|---------|-------------|
| 8.1 | `notebooks/09_Colab_HuggingFace_Risk.py` | Script Colab con clasificador de riesgo |
| 8.2 | `src/ml/risk_classifier.py` | Módulo reutilizable de clasificación |

---

## Día 9 — Comparativa de Modelos + Visualización

### Modelos a comparar
| Modelo | Tipo | Estado |
|--------|------|--------|
| FC (Fully Connected) | Baseline simple | **Por crear** |
| LSTM 3-Layer | Baseline LSTM | ✅ Ya entrenado (Día 7) |
| LSTM Attention | Mejor LSTM | ✅ Ya entrenado (Día 7) |
| CNN 1D | Detección de patrones | **Por crear** |
| Ensemble (3 LSTM) | Agregado | ✅ Ya entrenado (Día 8) |

### Deliverables
| # | Archivo | Descripción |
|---|---------|-------------|
| 9.1 | `notebooks/10_Colab_Model_Comparison.py` | Script Colab: entrena FC + CNN 1D, carga resultados anteriores, genera comparativa completa |
| 9.2 | Figuras de comparativa | Barras MAE/RMSE/R², curvas de entrenamiento superpuestas, tabla resumen |

---

## Día 10 — API Flask: Endpoints de Predicción

### Endpoints
| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/predict` | Predicción PM2.5 (acepta features, devuelve valor predicho) |
| `POST` | `/api/risk` | Clasificación de riesgo (acepta features, devuelve nivel + color) |
| `GET` | `/api/model/info` | Info del modelo (arquitectura, métricas, fecha entrenamiento) |

### Deliverables
| # | Archivo | Descripción |
|---|---------|-------------|
| 10.1 | `src/api/app.py` | Aplicación Flask principal |
| 10.2 | `src/api/routes.py` | Definición de rutas/endpoints |
| 10.3 | `src/api/model_loader.py` | Cargador de modelos .keras |
| 10.4 | `src/api/schemas.py` | Esquemas de request/response |

---

## Estructura de archivos

```
AirVLCProyecto/
├── notebooks/
│   ├── 09_Colab_HuggingFace_Risk.py          # [NEW] Día 8
│   └── 10_Colab_Model_Comparison.py           # [NEW] Día 9
├── src/
│   ├── api/
│   │   ├── app.py                              # [NEW] Día 10
│   │   ├── routes.py                           # [NEW] Día 10
│   │   ├── model_loader.py                     # [NEW] Día 10
│   │   └── schemas.py                          # [NEW] Día 10
│   └── ml/
│       ├── risk_classifier.py                  # [NEW] Día 8
│       └── ensemble_predict.py                 # Ya existe
└── models/
    └── modelo_09_HuggingFace/                  # [NEW] Resultados Día 8
    └── modelo_10_Comparison/                   # [NEW] Resultados Día 9
```

---

## Open Questions

> [!IMPORTANT]
> **Para el Día 8 (HuggingFace)**: ¿Prefieres usar un modelo de HuggingFace para clasificación tabular (TabTransformer) o prefieres un enfoque más sencillo con un clasificador sklearn (RandomForest/XGBoost) que se guarde y sirva junto con el LSTM? El plan original dice "HuggingFace" pero un clasificador clásico podría ser más práctico para este caso de uso.

> [!NOTE]
> **Para el Día 10 (API Flask)**: La API se creará localmente y se podrá testear en tu máquina. Los modelos `.keras` que guardaste de Colab se usarán directamente. ¿Las rutas de los modelos deben apuntar a la carpeta `models/` del proyecto?

---

## Verificación

- Día 8: El clasificador debe lograr **accuracy > 90%** en la clasificación de riesgo (es relativamente fácil dado que las categorías son amplias)
- Día 9: La comparativa debe incluir al menos **5 modelos** con métricas MAE, RMSE, R² + visualizaciones
- Día 10: La API debe responder correctamente a `curl` requests con predicciones en formato JSON
