import nbformat as nbf
import os

nb = nbf.v4.new_notebook()

markdown_1 = """# 🧠 Entrenamiento del Modelo LSTM para PM2.5
En este notebook cargamos el *Dataset Maestro* (combinación de PostgreSQL y MongoDB), creamos las ventanas temporales (Sliding Windows) y entrenamos un modelo de red neuronal recurrente (LSTM) para predecir el valor de PM2.5 en la próxima hora, usando las 24 horas previas."""

code_1 = """import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import joblib
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.optimizers import Adam
from sklearn.metrics import mean_squared_error, mean_absolute_error

# Configuración de rutas
PROJECT_ROOT = os.path.dirname(os.getcwd())
DATA_PATH = os.path.join(PROJECT_ROOT, 'data', 'processed', 'master_dataset.csv')
MODEL_PATH = os.path.join(PROJECT_ROOT, 'models', 'lstm_pm25.keras')
SCALER_PATH = os.path.join(PROJECT_ROOT, 'models', 'scaler.pkl')

print('Librerías importadas correctamente')
"""

markdown_2 = """## 1. Carga de Datos y Creación de Ventanas Temporales
Cargamos los datos normalizados que hemos preprocesado previamente."""

code_2 = """df = pd.read_csv(DATA_PATH)
df['fecha'] = pd.to_datetime(df['fecha'])
df.set_index('fecha', inplace=True)
print(f'Dimensiones del dataset: {df.shape}')
display(df.head())"""

markdown_3 = """Para entrenar el LSTM, transformamos el DataFrame en tensores 3D `(muestras, pasos_de_tiempo, caracteristicas)`.
Usaremos 24 horas (lags temporales) para predecir la hora siguiente (Target: pm25)."""

code_3 = """def create_sequences(data, seq_length, target_col_idx):
    xs = []
    ys = []
    # data es un array numpy de (n_samples, n_features)
    for i in range(len(data) - seq_length):
        x = data[i:(i + seq_length), :]
        y = data[i + seq_length, target_col_idx]
        xs.append(x)
        ys.append(y)
    return np.array(xs), np.array(ys)

# Índice de la columna PM2.5 (asumimos que es la primera, pero verificamos)
target_col_name = 'pm25'
target_idx = df.columns.get_loc(target_col_name)

SEQ_LENGTH = 24 # 24 horas de historia

X, y = create_sequences(df.values, SEQ_LENGTH, target_idx)
print(f'Shape de X (Input): {X.shape}')
print(f'Shape de y (Target): {y.shape}')
"""

markdown_4 = """### División en Train, Validation y Test
Al ser series temporales, **NO** barajamos los datos. Usamos cortes cronológicos (ej: 70% train, 15% val, 15% test)."""

code_4 = """train_size = int(len(X) * 0.70)
val_size = int(len(X) * 0.15)
test_size = len(X) - train_size - val_size

X_train, y_train = X[:train_size], y[:train_size]
X_val, y_val = X[train_size:train_size+val_size], y[train_size:train_size+val_size]
X_test, y_test = X[train_size+val_size:], y[train_size+val_size:]

print(f'Train: {X_train.shape}, {y_train.shape}')
print(f'Validation: {X_val.shape}, {y_val.shape}')
print(f'Test: {X_test.shape}, {y_test.shape}')
"""

markdown_5 = """## 2. Construcción de la Arquitectura LSTM
Siguiendo la guía preparatoria, usaremos un modelo Keras Secuencial con dos capas LSTM y Dropout."""

code_5 = """model = Sequential([
    LSTM(64, activation='relu', input_shape=(SEQ_LENGTH, X.shape[2]), return_sequences=True),
    Dropout(0.2),
    LSTM(32, activation='relu'),
    Dropout(0.2),
    Dense(1) # Predicción del valor numérico
])

model.compile(optimizer=Adam(learning_rate=0.001), loss='mse', metrics=['mae'])
model.summary()
"""

markdown_6 = """## 3. Entrenamiento del Modelo"""

code_6 = """# Usaremos un número de epochs moderado para iterar rápidamente (ej: 20-30 epochs)
history = model.fit(
    X_train, y_train,
    epochs=10, # Bajar el número de epochs para el test en vivo rápido
    batch_size=64,
    validation_data=(X_val, y_val),
    verbose=1,
    shuffle=False # IMPORTANTE: En series temporales no mezclamos
)
"""

markdown_7 = """## 4. Evaluación y Gráficos"""

code_7 = """# Evolución del Loss
plt.figure(figsize=(10, 5))
plt.plot(history.history['loss'], label='Train Loss (MSE)')
plt.plot(history.history['val_loss'], label='Val Loss (MSE)')
plt.title('Evolución del Entrenamiento')
plt.xlabel('Epochs')
plt.ylabel('Pérdida (MSE)')
plt.legend()
plt.show()
"""

markdown_8 = """Hagamos predicciones sobre el conjunto de test y comprobemos qué tal."""

code_8 = """y_pred = model.predict(X_test)

# Métricas (sobre valores escalados)
mse = mean_squared_error(y_test, y_pred)
mae = mean_absolute_error(y_test, y_pred)

print(f'Test MSE (Scaled): {mse:.4f}')
print(f'Test MAE (Scaled): {mae:.4f}')

# Visualización rápida de una porción (e.g., últimas 100 horas)
plt.figure(figsize=(15, 5))
plt.plot(y_test[-200:], label='Real (Test)', alpha=0.7)
plt.plot(y_pred[-200:], label='Predicción (Test)', color='red', alpha=0.7)
plt.title('Predicciones vs Valores Reales (escalados)')
plt.xlabel('Horas (ultimas 200)')
plt.ylabel('PM2.5 Scaled')
plt.legend()
plt.show()
"""

markdown_9 = """## 5. Exportación del Modelo"""

code_9 = """# Guardamos el modelo en el formato Keras v3 (.keras)
model.save(MODEL_PATH)
print(f'✅ Modelo LSTM guardado en: {MODEL_PATH}')
"""

nb['cells'] = [
    nbf.v4.new_markdown_cell(markdown_1),
    nbf.v4.new_code_cell(code_1),
    nbf.v4.new_markdown_cell(markdown_2),
    nbf.v4.new_code_cell(code_2),
    nbf.v4.new_markdown_cell(markdown_3),
    nbf.v4.new_code_cell(code_3),
    nbf.v4.new_markdown_cell(markdown_4),
    nbf.v4.new_code_cell(code_4),
    nbf.v4.new_markdown_cell(markdown_5),
    nbf.v4.new_code_cell(code_5),
    nbf.v4.new_markdown_cell(markdown_6),
    nbf.v4.new_code_cell(code_6),
    nbf.v4.new_markdown_cell(markdown_7),
    nbf.v4.new_code_cell(code_7),
    nbf.v4.new_markdown_cell(markdown_8),
    nbf.v4.new_code_cell(code_8),
    nbf.v4.new_markdown_cell(markdown_9),
    nbf.v4.new_code_cell(code_9),
]

os.makedirs('notebooks', exist_ok=True)
with open('notebooks/04_LSTM_Model.ipynb', 'w') as f:
    nbf.write(nb, f)

print('✅ Notebook generado exitosamente.')
