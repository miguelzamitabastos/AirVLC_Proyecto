# Resumen del Trabajo: Semana 2 (Días 1 y 2) - Modelado de IA

Se han completado todas las tareas correspondientes a la preparación de los datos y la creación del modelo LSTM estipuladas para el inicio de la Fase de IA del proyecto AirVLC.

## 1. El "Master Join" (Preprocesado y Feature Engineering)
He creado el script `src/ml/prepare_dataset.py`, el cual realiza las siguientes operaciones automáticas:
- **Extracción Híbrida**: Se conecta a la base de datos PostgreSQL para descargar los históricos de calidad del aire y a MongoDB Atlas para extraer los datos climatológicos de AEMET.
- **Cambio de Estación**: Dado que la estación de *Viveros* no registraba valores del contaminante PM2.5, se ha cambiado el objetivo principal a la estación **Pista de Silla** que cuenta con la mayor cantidad de registros históricos (~51,000 registros). 
- **Fusión Temporal**: Se han unido exitosamente los registros diarios del clima con las granularidades horarias del aire.
- **Limpieza**: Se aplicó una interpolación lineal para rellenar vacíos temporales cortos y se eliminaron los outliers imposibles (e.g., valores extremos muy infrecuentes en PM2.5 o O3).
- **Ingeniería de Características**: Se calcularon y añadieron las variables: `hora_del_dia`, `dia_de_la_semana`, retardos (`pm25_lag1`, `pm25_lag2`, `pm25_lag3`), y medias móviles (`pm25_rolling_6h`).
- **Normalización**: Las métricas se han escalado entre 0 y 1 utilizando `MinMaxScaler`, guardando el resultado en `data/processed/master_dataset.csv` (11.3 MB) y el escalador en `models/scaler.pkl`.

## 2. Entrenamiento del Modelo LSTM
Se ha creado y ejecutado el notebook `notebooks/04_LSTM_Model.ipynb`:
- **Ventanas Temporales (Sliding Windows)**: El notebook transforma las series temporales en tensores 3D secuenciales (ventanas de 24 horas previas para predecir la hora siguiente).
- **Entrenamiento Secuencial**: Se ha diseñado un modelo neuronal de Keras con dos capas `LSTM` de 64 y 32 unidades, acompañadas de regularización `Dropout (0.2)`. 
- **Resultados**: El modelo fue entrenado exitosamente. En las métricas de prueba, el error de validación desciende de forma estable y las curvas de predicción generadas visualmente se acoplan muy bien a los valores reales de testeo.
- **Exportación**: El modelo entrenado ha sido exportado exitosamente como `models/lstm_pm25.keras`.

> [!NOTE]
> Puedes abrir el notebook `notebooks/04_LSTM_Model.ipynb` en tu IDE o Jupyter Lab y ver las gráficas (pérdida de entrenamiento vs. test, y la gráfica de valores de PM2.5 reales vs. predicciones) que ya se han generado y guardado dentro del archivo de resultados interactivo.
