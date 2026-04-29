# Plan de Implementación: Semana 2 - Fase de IA (Días 1 y 2)

Este plan cubre los objetivos de los primeros dos días de la fase de Inteligencia Artificial ("Día 4 y 5" en la `guia_preparatoria_ia.md`) para el proyecto **AirVLC**. La meta principal es unir los datos de las bases de datos SQL y NoSQL, preprocesarlos, generar nuevas características ("feature engineering") y entrenar un modelo LSTM que prediga los niveles de PM2.5.

## User Review Required

> [!IMPORTANT]
> **Necesito tu confirmación sobre el enfoque del Dataset Maestro:**
> 1. Los datos meteorológicos en MongoDB (AEMET) son **diarios** (ej. temperatura media, precipitación diaria) mientras que los datos de calidad del aire en PostgreSQL son **horarios**. El plan propone usar un `merge` o `merge_asof` donde propagaremos (forward-fill) los datos diarios a todas las horas de ese día correspondiente. ¿Te parece bien este enfoque para la granularidad temporal?
> 2. Vamos a centrar el entrenamiento inicial del LSTM únicamente en la estación "Viveros" (o "Valencia Centro") para hacer el modelo más preciso localmente, y usaremos sus datos de clima más cercanos. ¿De acuerdo?

## Open Questions

> [!WARNING]
> ¿Tienes preferencia de que guardemos el "Dataset Maestro" preprocesado en un archivo (ej. `data/processed/master_dataset.csv`) para poder cargarlo fácilmente sin hacer el proceso pesado en cada ejecución del notebook? El plan asume que sí.

## Proposed Changes

---

### Módulo de Preprocesamiento y Feature Engineering

Este componente extrae los datos de PostgreSQL y MongoDB, los limpia, los fusiona y añade las variables necesarias para el modelo.

#### [NEW] [src/ml/prepare_dataset.py](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/src/ml/prepare_dataset.py)
Script ejecutable que realizará:
- **Conexión y Extracción:** Obtendrá datos horarios de `mediciones_aire` (`pm25`, `no2`, `o3`, `fecha`) de PostgreSQL y datos climatológicos diarios de MongoDB (`tmed`, `prec`, `velmedia`, `fecha`).
- **Limpieza de Datos (AEMET):** Formateará strings con comas (ej. `"13,4"`) a `float`.
- **Merge (The Master Join):** Fusionará ambos conjuntos de datos asegurando que la granularidad horaria tenga el contexto climático del día.
- **Limpieza (Nulls y Outliers):** Aplicará interpolación lineal para rellenar nulos cortos (`df.interpolate(method='linear')`) y limitará outliers estadísticos para evitar picos distorsionados de `PM2.5`.
- **Feature Engineering:**
    - Variables Temporales: `hora_del_dia`, `dia_de_la_semana`.
    - Retardos (Lags): Valores desplazados (`pm25_lag1`, `pm25_lag2`, `pm25_lag3`).
    - Media Móvil: Promedio móvil de las últimas 6 horas.
- **Normalización:** Usará `MinMaxScaler` en las columnas numéricas para dejarlas en el rango [0, 1]. El `scaler` resultante será exportado a `models/scaler.pkl`.
- **Exportación:** Guardará el `DataFrame` final estructurado en `data/processed/master_dataset.csv`.

---

### Módulo de Modelado de IA (LSTM)

Este componente se encarga de crear el modelo secuencial. Siguiendo tus instrucciones, se realizará en la carpeta `notebooks`.

#### [NEW] [notebooks/04_LSTM_Model.ipynb](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/notebooks/04_LSTM_Model.ipynb)
Notebook de Jupyter que realizará:
- **Carga de Datos:** Lectura del `master_dataset.csv`.
- **Sliding Windows (Ventanas Temporales):** Transformará los datos en tensores 3D `(muestras, pasos_de_tiempo, caracteristicas)`. El `X` constará de las últimas 24 horas y el `y` (target) será el valor real de `pm25` para la hora 25.
- **Entrenamiento (Keras/TensorFlow):**
    - División temporal (no aleatoria) en sets de *train*, *validation* y *test*.
    - Construcción del modelo Secuencial con capas `LSTM` y `Dropout` para prevenir overfitting.
    - Compilación con optimizador `adam` y función de pérdida `mse`.
    - Llamada a `model.fit()` registrando la historia del entrenamiento.
- **Evaluación y Visualización:** Trazará el historial de pérdida y comparará en una gráfica los valores de PM2.5 reales vs. las predicciones.
- **Exportación:** Guardará el modelo final en formato `models/lstm_pm25.h5`.

#### [NEW] [requirements_ml.txt](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/requirements_ml.txt)
Archivo auxiliar de requerimientos que asegurará la existencia de las librerías necesarias:
- `pandas`
- `numpy`
- `scikit-learn`
- `tensorflow`
- `psycopg2-binary`
- `pymongo`
- `python-dotenv`
- `matplotlib`

## Verification Plan

### Automated Tests
- Validaré que el script `prepare_dataset.py` genera correctamente los archivos `.csv` y `.pkl` en las carpetas de destino.

### Manual Verification
- Te pediré que verifiques la correcta creación del modelo en el notebook `04_LSTM_Model.ipynb` revisando las gráficas generadas y los valores de pérdida del entrenamiento (Loss Validation).
