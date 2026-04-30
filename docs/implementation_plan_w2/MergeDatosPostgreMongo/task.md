# Tareas de la Fase de IA - Semana 2 (Días 1 y 2)

- [x] Instalar/Verificar dependencias (TensorFlow, scikit-learn, etc.).
- [x] Crear el script `src/ml/prepare_dataset.py`:
  - [x] Conectar y extraer de PostgreSQL (calidad del aire) - (Cambiado a estación 'Pista de Silla' por falta de datos PM2.5 en Viveros).
  - [x] Conectar y extraer de MongoDB (AEMET histórico) - (Estación 8416Y, Valencia Viveros).
  - [x] Limpiar datos (formateo strings, interpolación, limitación de outliers).
  - [x] Hacer merge (Forward fill para los datos diarios hacia los horarios).
  - [x] Feature Engineering (Lags, rolling means, tiempo).
  - [x] Normalización (`MinMaxScaler`).
  - [x] Guardar `master_dataset.csv` y `scaler.pkl`.
- [x] Ejecutar el script `prepare_dataset.py` y validar la salida.
- [x] Crear el Notebook `notebooks/04_LSTM_Model.ipynb`:
  - [x] Carga del `master_dataset.csv`.
  - [x] Transformación en ventanas temporales (Sliding Windows).
  - [x] Construcción de la arquitectura LSTM en Keras.
  - [x] Entrenamiento del modelo (fit) y visualización.
  - [x] Exportación de `lstm_pm25.keras`.
- [x] Verificación y actualización del `walkthrough.md`.
