import nbformat as nbf
import os

nb = nbf.v4.new_notebook()

# =====================================================================
# CELDA 0: Título e Introducción
# =====================================================================
markdown_0 = """# 🧠 Entrenamiento Masivo LSTM para PM2.5 (Colab)
Este notebook está preparado para recibir el *Dataset Maestro de Colab* completo con todas las estaciones. El pipeline incluye:
1. **Exploración y visualización** de los datos
2. **Feature Engineering** con transformaciones cíclicas (seno/coseno)
3. **Normalización** con MinMaxScaler
4. Construcción de **ventanas temporales** por estación (sin cruzar secuencias)
5. Entrenamiento de un modelo **LSTM multicapa** aprovechando la GPU
6. **Evaluación** con métricas y gráficos (valores reales desnormalizados)
"""

# =====================================================================
# CELDA 1: Imports
# =====================================================================
code_1 = """import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau

# Asegúrate de subir tu master_dataset_colab.csv a esta misma ruta o modifica la ruta
DATA_PATH = 'master_dataset_colab.csv'
MODEL_PATH = 'lstm_pm25_colab.keras'

# Estilo de gráficos
sns.set_style('whitegrid')
plt.rcParams['figure.figsize'] = (14, 6)

print('✅ Librerías importadas correctamente')
"""

# =====================================================================
# CELDA 2-3: Carga de Datos
# =====================================================================
markdown_2 = """## 1. Carga de Datos"""

code_2 = """df = pd.read_csv(DATA_PATH)
df['fecha'] = pd.to_datetime(df['fecha'])
df.set_index('fecha', inplace=True)
print(f'Dimensiones del dataset: {df.shape}')
print(f'Estaciones disponibles: {df["station_name"].unique()}')
display(df.head())"""

# =====================================================================
# CELDA 3-4: EDA - Exploración y Visualización
# =====================================================================
markdown_3 = """## 2. Exploración y Visualización de Datos (EDA)

Antes de entrenar el modelo, es fundamental **entender** los datos con los que trabajamos.
Analizaremos la distribución de las variables, las correlaciones y la evolución temporal del target (PM2.5)."""

code_3a = """# 2.1 Estadísticas descriptivas generales
print("=" * 60)
print("INFORMACIÓN DEL DATASET")
print("=" * 60)
df.info()
print()

print("=" * 60)
print("ESTADÍSTICAS DESCRIPTIVAS")
print("=" * 60)
# Seleccionar solo columnas numéricas para describe
numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
display(df[numeric_cols].describe())
print()

print("=" * 60)
print("VALORES NULOS POR COLUMNA")
print("=" * 60)
null_counts = df.isnull().sum()
print(null_counts[null_counts > 0] if null_counts.sum() > 0 else "✅ No hay valores nulos")
"""

code_3b = """# 2.2 Distribución del Target (PM2.5)
fig, axes = plt.subplots(1, 2, figsize=(16, 5))

# Histograma
axes[0].hist(df['pm25'], bins=50, color='steelblue', edgecolor='black', alpha=0.7)
axes[0].set_title('Distribución de PM2.5', fontsize=14, fontweight='bold')
axes[0].set_xlabel('PM2.5')
axes[0].set_ylabel('Frecuencia')
axes[0].axvline(df['pm25'].mean(), color='red', linestyle='--', label=f'Media: {df["pm25"].mean():.2f}')
axes[0].axvline(df['pm25'].median(), color='orange', linestyle='--', label=f'Mediana: {df["pm25"].median():.2f}')
axes[0].legend()

# Boxplot por estación
stations = df['station_name'].unique()
data_by_station = [df[df['station_name'] == s]['pm25'].values for s in stations]
bp = axes[1].boxplot(data_by_station, labels=stations, patch_artist=True)
for patch in bp['boxes']:
    patch.set_facecolor('lightblue')
axes[1].set_title('PM2.5 por Estación', fontsize=14, fontweight='bold')
axes[1].set_ylabel('PM2.5')
axes[1].tick_params(axis='x', rotation=45)

plt.tight_layout()
plt.show()
"""

code_3c = """# 2.3 Serie temporal del PM2.5 para una estación representativa
sample_station = df['station_name'].unique()[0]
df_sample = df[df['station_name'] == sample_station]

plt.figure(figsize=(18, 5))
plt.plot(df_sample.index, df_sample['pm25'], linewidth=0.5, color='steelblue', alpha=0.8)
plt.title(f'Evolución temporal de PM2.5 - Estación: {sample_station}', fontsize=14, fontweight='bold')
plt.xlabel('Fecha')
plt.ylabel('PM2.5')
plt.tight_layout()
plt.show()
"""

code_3d = """# 2.4 Heatmap de correlaciones entre features numéricas
# Excluimos columnas one-hot de estaciones y station_name para mayor claridad
exclude_cols = [c for c in df.columns if c.startswith('station_') or c == 'station_name']
corr_cols = [c for c in numeric_cols if c not in exclude_cols]

corr_matrix = df[corr_cols].corr()

plt.figure(figsize=(12, 8))
sns.heatmap(corr_matrix, annot=True, cmap='RdBu_r', center=0, fmt='.2f',
            linewidths=0.5, square=True)
plt.title('Matriz de Correlaciones', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.show()
"""

# =====================================================================
# CELDA 5: Feature Engineering - Transformaciones Cíclicas
# =====================================================================
markdown_4 = """## 3. Feature Engineering: Transformación Seno/Coseno

Las variables temporales como `hora_del_dia` (0-23) y `dia_de_la_semana` (0-6) son **cíclicas**.
Si las usamos directamente como valores lineales, el modelo pensará que la hora 23 y la hora 0 están muy lejos,
cuando en realidad son consecutivas.

La solución es codificarlas con **seno y coseno**, mapeando los valores a un círculo unitario.
De esta forma, las horas/días consecutivos siempre estarán cerca en el espacio de features."""

code_4 = """# 3.1 Transformaciones cíclicas
df['hora_sin'] = np.sin(2 * np.pi * df['hora_del_dia'] / 24)
df['hora_cos'] = np.cos(2 * np.pi * df['hora_del_dia'] / 24)
df['dia_sin'] = np.sin(2 * np.pi * df['dia_de_la_semana'] / 7)
df['dia_cos'] = np.cos(2 * np.pi * df['dia_de_la_semana'] / 7)

# Eliminar las columnas originales lineales (ya no las necesitamos)
df.drop(columns=['hora_del_dia', 'dia_de_la_semana'], inplace=True)

print("✅ Transformaciones cíclicas aplicadas")
print(f"Nuevas columnas: hora_sin, hora_cos, dia_sin, dia_cos")
print(f"Shape actual del DataFrame: {df.shape}")
"""

code_4b = """# 3.2 Visualización de la transformación cíclica (Círculo Unitario)
horas = np.arange(0, 24)
hora_sin = np.sin(2 * np.pi * horas / 24)
hora_cos = np.cos(2 * np.pi * horas / 24)

fig, axes = plt.subplots(1, 2, figsize=(14, 6))

# Círculo unitario para horas
theta = np.linspace(0, 2 * np.pi, 100)
axes[0].plot(np.cos(theta), np.sin(theta), linestyle='dashed', color='gray', alpha=0.5)
axes[0].scatter(hora_cos, hora_sin, color='steelblue', s=60, zorder=5)
for i, h in enumerate(horas):
    axes[0].annotate(f'{h}h', (hora_cos[i]*1.12, hora_sin[i]*1.12),
                     fontsize=8, ha='center', va='center', fontweight='bold')
axes[0].set_xlabel("Coseno de la Hora")
axes[0].set_ylabel("Seno de la Hora")
axes[0].set_title("Codificación Cíclica: Hora del Día", fontsize=12, fontweight='bold')
axes[0].set_aspect('equal')
axes[0].grid(True, alpha=0.3)
axes[0].set_xlim(-1.3, 1.3)
axes[0].set_ylim(-1.3, 1.3)

# Círculo unitario para días
dias = np.arange(0, 7)
dia_sin = np.sin(2 * np.pi * dias / 7)
dia_cos = np.cos(2 * np.pi * dias / 7)
nombres_dias = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']

axes[1].plot(np.cos(theta), np.sin(theta), linestyle='dashed', color='gray', alpha=0.5)
axes[1].scatter(dia_cos, dia_sin, color='coral', s=80, zorder=5)
for i, d in enumerate(nombres_dias):
    axes[1].annotate(d, (dia_cos[i]*1.15, dia_sin[i]*1.15),
                     fontsize=9, ha='center', va='center', fontweight='bold')
axes[1].set_xlabel("Coseno del Día")
axes[1].set_ylabel("Seno del Día")
axes[1].set_title("Codificación Cíclica: Día de la Semana", fontsize=12, fontweight='bold')
axes[1].set_aspect('equal')
axes[1].grid(True, alpha=0.3)
axes[1].set_xlim(-1.3, 1.3)
axes[1].set_ylim(-1.3, 1.3)

plt.tight_layout()
plt.show()
"""

# =====================================================================
# CELDA 6: Normalización
# =====================================================================
markdown_5 = """## 4. Normalización de los Datos (MinMaxScaler)

Las redes neuronales LSTM funcionan mucho mejor cuando las features están en un rango similar.
Usaremos `MinMaxScaler` para escalar todas las features numéricas al rango [0, 1].

**Importante:** Guardamos el scaler para poder hacer la **transformación inversa** después y
mostrar las predicciones en valores reales de PM2.5."""

code_5 = """# 4.1 Normalización con MinMaxScaler
scaler = MinMaxScaler()

# Columnas a normalizar (excluyendo station_name que es string)
cols_to_scale = [c for c in df.columns if c != 'station_name']

print(f"Columnas a normalizar ({len(cols_to_scale)}):")
for c in cols_to_scale:
    print(f"  - {c}: min={df[c].min():.4f}, max={df[c].max():.4f}")

# Aplicar normalización
df[cols_to_scale] = scaler.fit_transform(df[cols_to_scale])

# Guardar el índice de la columna pm25 para la transformación inversa
pm25_col_idx = cols_to_scale.index('pm25')

print(f"\\n✅ Normalización aplicada. Índice de pm25 en el scaler: {pm25_col_idx}")
print(f"Rango de PM2.5 después de normalizar: [{df['pm25'].min():.4f}, {df['pm25'].max():.4f}]")
"""

# =====================================================================
# CELDA 7-8: Ventanas Temporales
# =====================================================================
markdown_6 = """## 5. Creación de Ventanas Temporales por Estación
Para entrenar el LSTM, transformamos el DataFrame en tensores 3D `(muestras, pasos_de_tiempo, caracteristicas)`.
Usaremos 24 horas (lags temporales) para predecir la hora siguiente (Target: pm25).
Agruparemos los datos por estación para evitar secuencias donde la última hora de la estación A se use para predecir la primera hora de la estación B."""

code_6 = """def create_sequences_by_station(data, seq_length, target_col_name='pm25', group_col='station_name'):
    xs = []
    ys = []

    # Extraer nombres de las columnas para obtener los índices después
    columns = data.columns.tolist()
    target_idx = columns.index(target_col_name)

    # Agrupamos por estación
    for station, group in data.groupby(group_col):
        # Eliminamos la columna station_name ya que no se introduce como feature numérica en la LSTM
        group_no_station = group.drop(columns=[group_col])
        group_values = group_no_station.values
        target_values = group[target_col_name].values

        for i in range(len(group_values) - seq_length):
            x = group_values[i:(i + seq_length), :]
            y = target_values[i + seq_length]
            xs.append(x)
            ys.append(y)

    return np.array(xs), np.array(ys)

SEQ_LENGTH = 24 # 24 horas de historia

X, y = create_sequences_by_station(df, SEQ_LENGTH, target_col_name='pm25', group_col='station_name')
print(f'Shape de X (Input): {X.shape}')
print(f'Shape de y (Target): {y.shape}')
"""

# =====================================================================
# CELDA 9-10: División Train/Val/Test
# =====================================================================
markdown_7 = """### División en Train, Validation y Test
Dividimos aleatoriamente las secuencias generadas. Como tenemos muchas secuencias independientes
(generadas por estación), hacer shuffle está bien para generalizar el modelo."""

code_7 = """# Dividimos aleatoriamente las secuencias generadas
X_train, X_temp, y_train, y_temp = train_test_split(X, y, test_size=0.30, random_state=42)
X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.50, random_state=42)

print(f'Train: {X_train.shape}, {y_train.shape}')
print(f'Validation: {X_val.shape}, {y_val.shape}')
print(f'Test: {X_test.shape}, {y_test.shape}')
"""

# =====================================================================
# CELDA 11-12: Arquitectura LSTM
# =====================================================================
markdown_8 = """## 6. Construcción de la Arquitectura LSTM

Arquitectura multicapa con 3 capas LSTM apiladas, Dropout para regularización,
y una capa Dense intermedia antes de la salida."""

code_8 = """model = Sequential([
    LSTM(128, activation='relu', input_shape=(SEQ_LENGTH, X.shape[2]), return_sequences=True),
    Dropout(0.3),
    LSTM(64, activation='relu', return_sequences=True),
    Dropout(0.3),
    LSTM(32, activation='relu'),
    Dropout(0.2),
    Dense(16, activation='relu'),
    Dense(1)
])

model.compile(optimizer=Adam(learning_rate=0.001), loss='mse', metrics=['mae'])
model.summary()
"""

# =====================================================================
# CELDA 13-14: Entrenamiento
# =====================================================================
markdown_9 = """## 7. Entrenamiento del Modelo
Aprovechando la GPU de Colab, entrenamos con:
- **EarlyStopping** para detener si no mejora la val_loss
- **ReduceLROnPlateau** para reducir el learning rate cuando se estanca"""

code_9 = """early_stop = EarlyStopping(monitor='val_loss', patience=7, restore_best_weights=True, verbose=1)
reduce_lr = ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=3, min_lr=1e-6, verbose=1)

history = model.fit(
    X_train, y_train,
    epochs=80,
    batch_size=256,
    validation_data=(X_val, y_val),
    callbacks=[early_stop, reduce_lr],
    verbose=1
)
"""

# =====================================================================
# CELDA 15-16: Evaluación y Gráficos
# =====================================================================
markdown_10 = """## 8. Evaluación y Gráficos"""

code_10 = """# 8.1 Curvas de entrenamiento
fig, axes = plt.subplots(1, 2, figsize=(16, 5))

axes[0].plot(history.history['loss'], label='Train Loss (MSE)', linewidth=2)
axes[0].plot(history.history['val_loss'], label='Val Loss (MSE)', linewidth=2)
axes[0].set_title('Evolución de la Pérdida (MSE)', fontsize=14, fontweight='bold')
axes[0].set_xlabel('Epochs')
axes[0].set_ylabel('Pérdida (MSE)')
axes[0].legend()
axes[0].grid(True, alpha=0.3)

axes[1].plot(history.history['mae'], label='Train MAE', linewidth=2)
axes[1].plot(history.history['val_mae'], label='Val MAE', linewidth=2)
axes[1].set_title('Evolución del MAE', fontsize=14, fontweight='bold')
axes[1].set_xlabel('Epochs')
axes[1].set_ylabel('MAE')
axes[1].legend()
axes[1].grid(True, alpha=0.3)

plt.tight_layout()
plt.show()
"""

code_10b = """# 8.2 Predicciones sobre Test
y_pred_scaled = model.predict(X_test)

# Métricas en escala normalizada
mse_scaled = mean_squared_error(y_test, y_pred_scaled)
mae_scaled = mean_absolute_error(y_test, y_pred_scaled)
r2_scaled = r2_score(y_test, y_pred_scaled)

print(f'=== Métricas en escala NORMALIZADA ===')
print(f'Test MSE: {mse_scaled:.6f}')
print(f'Test MAE: {mae_scaled:.6f}')
print(f'Test R²:  {r2_scaled:.4f}')
"""

code_10c = """# 8.3 Desnormalización: Convertir predicciones a valores reales de PM2.5

def inverse_transform_pm25(values_scaled, scaler, pm25_idx, total_features):
    \"\"\"Desnormaliza valores de PM2.5 usando el scaler original.\"\"\"
    # Crear un array dummy con la misma cantidad de features
    dummy = np.zeros((len(values_scaled), total_features))
    dummy[:, pm25_idx] = values_scaled.flatten()
    # Hacer inverse_transform
    dummy_inv = scaler.inverse_transform(dummy)
    return dummy_inv[:, pm25_idx]

total_features = len(cols_to_scale)

y_test_real = inverse_transform_pm25(y_test, scaler, pm25_col_idx, total_features)
y_pred_real = inverse_transform_pm25(y_pred_scaled, scaler, pm25_col_idx, total_features)

# Métricas en escala real
mse_real = mean_squared_error(y_test_real, y_pred_real)
mae_real = mean_absolute_error(y_test_real, y_pred_real)
rmse_real = np.sqrt(mse_real)
r2_real = r2_score(y_test_real, y_pred_real)

print(f'=== Métricas en escala REAL (µg/m³) ===')
print(f'Test MSE:  {mse_real:.4f}')
print(f'Test RMSE: {rmse_real:.4f}')
print(f'Test MAE:  {mae_real:.4f}')
print(f'Test R²:   {r2_real:.4f}')
"""

code_10d = """# 8.4 Gráficos de predicción vs realidad (valores reales)
fig, axes = plt.subplots(2, 1, figsize=(18, 10))

# Predicciones vs Reales - primeras 300 muestras
n_show = 300
axes[0].plot(y_test_real[:n_show], label='Real (Test)', alpha=0.8, linewidth=1.5, color='steelblue')
axes[0].plot(y_pred_real[:n_show], label='Predicción (Test)', alpha=0.8, linewidth=1.5, color='coral')
axes[0].set_title('Predicciones vs Valores Reales de PM2.5 (µg/m³)', fontsize=14, fontweight='bold')
axes[0].set_xlabel('Muestras de Test')
axes[0].set_ylabel('PM2.5 (µg/m³)')
axes[0].legend(fontsize=12)
axes[0].grid(True, alpha=0.3)

# Scatter Plot: Predicción vs Real
axes[1].scatter(y_test_real, y_pred_real, alpha=0.3, s=10, color='steelblue')
min_val = min(y_test_real.min(), y_pred_real.min())
max_val = max(y_test_real.max(), y_pred_real.max())
axes[1].plot([min_val, max_val], [min_val, max_val], 'r--', linewidth=2, label='Línea ideal (y=x)')
axes[1].set_title(f'Scatter Plot: Predicción vs Real (R² = {r2_real:.4f})', fontsize=14, fontweight='bold')
axes[1].set_xlabel('PM2.5 Real (µg/m³)')
axes[1].set_ylabel('PM2.5 Predicho (µg/m³)')
axes[1].legend(fontsize=12)
axes[1].grid(True, alpha=0.3)

plt.tight_layout()
plt.show()
"""

# =====================================================================
# CELDA 17-18: Exportación
# =====================================================================
markdown_11 = """## 9. Exportación del Modelo"""

code_11 = """model.save(MODEL_PATH)
print(f'✅ Modelo LSTM guardado en: {MODEL_PATH}')

# Resumen final
print(f'\\n📊 Resumen del entrenamiento:')
print(f'   - Arquitectura: 3 capas LSTM (128→64→32) + Dense(16) + Dense(1)')
print(f'   - Ventana temporal: {SEQ_LENGTH} horas')
print(f'   - Features por timestep: {X.shape[2]}')
print(f'   - Total secuencias: {X.shape[0]}')
print(f'   - Train/Val/Test split: {X_train.shape[0]}/{X_val.shape[0]}/{X_test.shape[0]}')
print(f'   - RMSE final (escala real): {rmse_real:.4f} µg/m³')
print(f'   - R² final: {r2_real:.4f}')
"""

nb['cells'] = [
    nbf.v4.new_markdown_cell(markdown_0),
    nbf.v4.new_code_cell(code_1),
    nbf.v4.new_markdown_cell(markdown_2),
    nbf.v4.new_code_cell(code_2),
    nbf.v4.new_markdown_cell(markdown_3),
    nbf.v4.new_code_cell(code_3a),
    nbf.v4.new_code_cell(code_3b),
    nbf.v4.new_code_cell(code_3c),
    nbf.v4.new_code_cell(code_3d),
    nbf.v4.new_markdown_cell(markdown_4),
    nbf.v4.new_code_cell(code_4),
    nbf.v4.new_code_cell(code_4b),
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
    nbf.v4.new_markdown_cell(markdown_10),
    nbf.v4.new_code_cell(code_10),
    nbf.v4.new_code_cell(code_10b),
    nbf.v4.new_code_cell(code_10c),
    nbf.v4.new_code_cell(code_10d),
    nbf.v4.new_markdown_cell(markdown_11),
    nbf.v4.new_code_cell(code_11),
]

# Save to notebooks folder
# Subimos dos niveles desde src/scripts para llegar a la raíz del proyecto
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
notebook_dir = os.path.join(PROJECT_ROOT, 'notebooks')

os.makedirs(notebook_dir, exist_ok=True)
notebook_path = os.path.join(notebook_dir, '05_Colab_LSTM_Model.ipynb')

with open(notebook_path, 'w') as f:
    nbf.write(nb, f)

print(f'✅ Notebook de Colab generado exitosamente en: {notebook_path}')
