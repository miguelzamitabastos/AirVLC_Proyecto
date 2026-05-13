# 🧠 Guía Preparatoria: IA y Modelado (Semana 2)

Esta guía detalla los pasos críticos para los días 4 y 5 de la fase de Inteligencia Artificial del proyecto AirVLC.

---

## 🗓️ Día 4: Preprocesado y Feature Engineering
**Objetivo**: Crear el "Dataset Maestro" uniendo PostgreSQL y MongoDB.

### 1. Extracción y Fusión (The Master Join)
Debes crear un script `src/ml/prepare_dataset.py` que realice lo siguiente:
- **Calidad del Aire (Postgres)**: Extraer `fecha`, `pm25`, `no2`, `o3`.
- **Meteorología (MongoDB)**: Extraer `fecha`, `temperatura`, `velocidad_viento`, `precipitacion`.
- **Merge**: Usar `pandas.merge_asof` si las fechas no coinciden exactamente al segundo, o un `merge` normal si ambas están redondeadas a la hora.

### 2. Limpieza de Datos
- **Valores Nulos**: En series temporales, **no borres filas**. Usa `df.interpolate(method='linear')` para rellenar huecos cortos de sensores caídos.
- **Outliers**: Detecta picos imposibles (ej. PM2.5 > 500 en Valencia sin incendio) y suavízalos.

### 3. Feature Engineering (El "toque" de IA)
Añade variables que ayuden al modelo a entender el contexto:
- **Variables Temporales**: Extraer `hora_del_dia`, `dia_de_la_semana` (el tráfico de un lunes no es igual al de un domingo).
- **Lags (Retardos)**: Crear columnas con el valor de hace 1h, 2h y 3h (`df['pm25_lag1'] = df['pm25'].shift(1)`).
- **Medias Móviles**: Media de las últimas 6 horas para captar la tendencia.

### 4. Normalización
Para un LSTM, es obligatorio escalar los datos entre 0 y 1.
- Usa `MinMaxScaler` de `scikit-learn`.
- **IMPORTANTE**: Guarda el escalador (`scaler.pkl`) para poder "des-escalar" las predicciones después.

---

## 🗓️ Día 5: Entrenamiento del Modelo LSTM
**Objetivo**: Construir y entrenar la red neuronal recurrente.

### 1. Creación de Ventanas (Sliding Windows)
Transforma tu DataFrame en tensores de 3 dimensiones: `(muestras, pasos_de_tiempo, caracteristicas)`.
- **Input (X)**: Las últimas 24 horas de datos (aire + clima).
- **Output (y)**: El valor de PM2.5 de la hora 25.

### 2. Arquitectura Recomendada (Keras/TensorFlow)
```python
model = Sequential([
    # Capa LSTM para captar la secuencia temporal
    LSTM(64, activation='relu', input_shape=(24, n_features), return_sequences=True),
    Dropout(0.2),
    LSTM(32, activation='relu'),
    Dropout(0.2),
    # Capa de salida para la predicción numérica
    Dense(1) 
])
model.compile(optimizer='adam', loss='mse')
