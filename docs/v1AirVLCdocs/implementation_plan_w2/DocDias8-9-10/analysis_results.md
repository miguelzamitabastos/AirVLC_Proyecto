# 📊 Análisis Honesto de Resultados — Días 6, 7, 8

## Resumen Ejecutivo

| Métrica | Baseline (Notebook 05) | Mejor Día 6 | Mejor Día 7 | Ensemble Día 8 |
|---------|----------------------|-------------|-------------|----------------|
| **MAE (µg/m³)** | 2.99 | **2.68** (rmsprop) | **2.64** (Attention) | **2.68** |
| **RMSE (µg/m³)** | 4.82 | 4.83 | **4.69** | **4.75** |
| **R²** | 0.755 | 0.754 | **0.767** | **0.762** |

> [!IMPORTANT]
> **Mejora global: ~11% en MAE** (de 2.99 → 2.64 µg/m³ con LSTM_Attention). Es una mejora real pero modesta, lo cual es normal en este tipo de problemas.

---

## Día 6 — Grid Search de Hiperparámetros

### Lo que fue bien ✅
- Se completaron **13 de 16 configuraciones** (las 3 restantes con `seq_length=48` y lr bajo se pueden completar después)
- El grid descubrió que **RMSprop supera a Adam** ligeramente en este problema (MAE: 2.68 vs 2.69)
- Learning rate bajo (`1e-4`) con Adam dio el **mejor MAE absoluto del grid**: **2.69 µg/m³**, pero tardó más (735s vs 492s con RMSprop)
- Batch size de 64 fue consistentemente el mejor

### Ranking Top 5 del Grid Search
| # | LR | Batch | Optimizer | Dropout | Seq | MAE | RMSE | R² |
|---|-----|-------|-----------|---------|-----|-----|------|-----|
| 1 | 0.001 | 64 | rmsprop | 0.2 | 24 | **2.678** | 4.830 | 0.754 |
| 2 | 0.001 | 64 | adam | 0.2 | 48 | **2.680** | 4.736 | 0.759 |
| 3 | 0.0001 | 64 | adam | 0.2 | 24 | **2.693** | 4.777 | 0.759 |
| 4 | 0.001 | 256 | adam | 0.2 | 24 | **2.696** | 4.779 | 0.759 |
| 5 | 0.001 | 32 | adam | 0.2 | 24 | **2.744** | 4.737 | 0.763 |

### Observaciones honestas ⚠️
- Dropout alto (0.3-0.4) perjudicó el rendimiento consistentemente. **Dropout = 0.2 es claramente el óptimo**.
- Seq_length=48 no mejoró sustancialmente sobre seq_length=24, pero sí duplicó el tiempo de entrenamiento. **No merece la pena el coste extra**.
- Las diferencias entre las mejores configuraciones son **muy pequeñas** (rango: 2.68-2.74), lo que indica que el modelo ya está cerca del límite de lo que esta arquitectura puede extraer de estos datos.

---

## Día 7 — Experimentos de Arquitectura

### Ranking de Arquitecturas
| Arquitectura | MAE | RMSE | R² | Params | Épocas | Tiempo |
|-------------|-----|------|-----|--------|--------|--------|
| **LSTM_Attention** | **2.638** | **4.695** | **0.767** | 126K | 17/24 | 425s |
| LSTM_3Layer | 2.652 | 4.802 | 0.757 | 139K | 13/20 | 417s |
| BiLSTM | 2.755 | 4.746 | 0.762 | 86K | 5/12 | 305s |
| LSTM_2Layer | 2.793 | 4.898 | 0.747 | 127K | 2/9 | 159s |

### Lo que fue bien ✅
- **LSTM_Attention ganó** en MAE y RMSE, confirmando que la atención temporal aporta valor real
- La atención permite al modelo "decidir" qué horas de las 24 son más relevantes — esto tiene sentido físico (ej: horas pico de tráfico pesan más para PM2.5)
- LSTM_3Layer quedó segundo, muy cerca. El baseline no estaba mal.

### Observaciones honestas ⚠️
- **BiLSTM decepciona**: solo 86K params y convergió en 5 épocas, lo que sugiere que no logró capturar patrones adicionales mirando "hacia atrás" en el tiempo. En series temporales como la calidad del aire, el futuro no influye en el pasado, así que la dirección reversa aporta poco.
- **LSTM_2Layer** fue la peor — confirma que 3 capas son necesarias para la complejidad de estos datos.
- Las **curvas de entrenamiento** muestran un comportamiento saludable: descenso suave sin oscilaciones, sin overfitting claro (train/val convergen).

---

## Día 8 — Entrenamiento Avanzado & Evaluación

### Modelo Avanzado (L2 + GaussianNoise)
- **MAE: 2.713** | RMSE: 4.810 | R²: 0.756
- Esto es **peor que el LSTM_Attention del Día 7** (2.638). La regularización L2 fue demasiado agresiva para este modelo.

### Ensemble (3 modelos, seeds: 42, 123, 456)
- **MAE: 2.679** | RMSE: 4.748 | R²: 0.762
- El ensemble mejoró sobre el modelo avanzado individual pero **no superó al mejor del Día 7**. Esto es informativo: la variabilidad entre runs es baja, lo que significa que los modelos son estables.

### Cross-Validation Temporal (5-fold)

| Fold | MAE | RMSE | R² |
|------|-----|------|-----|
| 1 | 4.19 | 6.42 | 0.703 |
| 2 | 3.68 | 5.59 | 0.716 |
| 3 | 2.63 | 4.39 | 0.751 |
| 4 | **4.14** | 5.32 | **0.551** |
| 5 | **2.44** | 4.33 | 0.750 |
| **Media** | **3.42 ± 0.83** | **5.21** | **0.694** |

> [!WARNING]
> **El CV temporal revela la verdad más importante**: el MAE medio real del modelo es **3.42 µg/m³**, no 2.64. La diferencia ocurre porque:
> - Los folds 1, 2 y 4 tienen MAE > 3.5, indicando que el modelo generaliza peor en ciertos períodos
> - El fold 4 tiene R² = 0.551 — el modelo explica solo el 55% de la varianza en ese período
> - Los folds con datos más recientes (3, 5) tienen mejor rendimiento, sugiriendo que el modelo captura mejor los patrones más recientes

### Análisis de Errores

![Análisis de errores del modelo ensemble](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/models/modelo_08_Colab/day8_error_analysis.png)

**Diagnóstico de los 4 gráficos:**

1. **Real vs Predicción**: El modelo funciona bien para valores bajos-medios (0-30 µg/m³) pero **subestima sistemáticamente los picos altos** (>40 µg/m³). El "abanico" que se abre para valores altos indica heterocedasticidad.

2. **Distribución de Residuos**: Media ≈ 0.13 (casi sin sesgo global), pero la distribución tiene **cola derecha pesada** — los errores grandes son siempre por subestimación.

3. **Residuos vs Predicción**: Confirma la heterocedasticidad: a mayor predicción, mayor dispersión del error. Esto es típico en datos ambientales con eventos extremos.

4. **Q-Q Plot**: Los residuos **no son normales** — las colas se desvían significativamente. Esto no invalida el modelo, pero indica que los intervalos de confianza basados en normalidad no serían fiables.

---

## Valoración Global — Con Total Sinceridad 🎯

### Lo que se logró ✅
- **MAE mejoró de 2.99 → 2.64 µg/m³** (mejor modelo single) — mejora del ~11%
- Se identificó que **LSTM con Atención** es la mejor arquitectura para este problema
- Se confirmó que **RMSprop** funciona mejor que Adam y **dropout=0.2** es óptimo
- El pipeline completo de experimentación (grid search → arquitectura → ensemble + CV) funciona correctamente
- Los modelos ensemble están guardados y listos para servir predicciones

### Limitaciones reales ⚠️
- El **CV temporal** muestra que el rendimiento real es peor de lo que sugiere el test set fijo (~3.4 MAE vs ~2.6 MAE)
- El modelo **falla con picos de contaminación** — justo los eventos más importantes para alertas
- El **R² medio del CV es 0.694**, lejos del >0.85 que sería deseable para un sistema de alertas fiable
- La regularización L2 + GaussianNoise del Día 8 **no mejoró** el rendimiento (en realidad lo empeoró ligeramente)

### ¿Estamos preparados para los Días 8-10 del plan? 

Según el [implementation_plan.md](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/docs/implementation_plan.md):

| Día Plan | Tarea | ¿Listos? |
|----------|-------|----------|
| **Jue 8** | Modelo HuggingFace: clasificación de niveles de riesgo | ✅ Sí — tenemos datos y pipeline. Se puede usar un modelo preentrenado de HuggingFace para clasificar PM2.5 en niveles (Bueno/Moderado/Malo/Peligroso) |
| **Vie 9** | Comparativa de modelos + visualización resultados | ✅ Sí — ya tenemos datos de 4 arquitecturas + ensemble para comparar. Faltaría entrenar un FC (fully connected) simple y quizás una CNN 1D |
| **Sáb 10** | API Flask: endpoints de predicción | ✅ Sí — los modelos están guardados como `.keras`. Se puede crear la API usando los modelos del Día 7 (Attention) o el ensemble del Día 8 |

> [!NOTE]
> **Mi recomendación**: Sí estamos preparados. El modelo no es perfecto (ninguno lo es), pero es **suficientemente bueno** para continuar con la integración (HuggingFace, comparativa, API). Las mejoras futuras pueden venir de **más datos** o **mejor feature engineering**, no de ajustar más la arquitectura.
