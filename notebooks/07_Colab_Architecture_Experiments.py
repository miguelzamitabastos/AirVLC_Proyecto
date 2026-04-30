"""
===================================================================
🏗️ Día 7 — Experimentos de Arquitectura & Feature Engineering
===================================================================
Script preparado para ejecutar en Google Colab con GPU.
Incluye:
  1. Encodings cíclicos (sin/cos hora del día y día de la semana)
  2. Variantes arquitectónicas:
     a) LSTM 2-capas (baseline simplificado)
     b) LSTM 3-capas (baseline original)
     c) Bidirectional LSTM
     d) LSTM + Attention (Bahdanau)
  3. Entrenamiento con los mejores hiperparámetros del Día 6
  4. Comparación de métricas y selección de arquitectura ganadora

Uso en Colab:
  1. Sube este archivo a tu Google Drive
  2. Monta Google Drive
  3. Ejecuta este script
===================================================================
"""

# ==========================================
# 1. CONFIGURACIÓN Y MONTAJE DE DRIVE
# ==========================================
import os
import json
import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

import tensorflow as tf
from tensorflow.keras.models import Sequential, Model
from tensorflow.keras.layers import (
    LSTM, Dense, Dropout, Input, Bidirectional,
    Layer, Concatenate, Add, Flatten, Permute, Multiply,
    RepeatVector, Lambda
)
from tensorflow.keras.optimizers import Adam, RMSprop
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
import tensorflow.keras.backend as K

# Fijar seeds
SEED = 42
np.random.seed(SEED)
tf.random.set_seed(SEED)

# Estilos
sns.set_style('whitegrid')
plt.rcParams['figure.figsize'] = (14, 6)

print('✅ Librerías importadas correctamente')

# ------------------------------------------
# Montar Google Drive (descomenta en Colab)
# ------------------------------------------
# from google.colab import drive
# drive.mount('/content/drive')

# ------------------------------------------
# Rutas
# ------------------------------------------
DATA_PATH = "/content/drive/MyDrive/Curso Especializacion/Proyecto/master_dataset_colab.csv"
RESULTS_DIR = "/content/drive/MyDrive/Curso Especializacion/Proyecto/results"
DAY6_RESULTS = os.path.join(RESULTS_DIR, "day6_hyperparams_results.csv")
os.makedirs(RESULTS_DIR, exist_ok=True)

RESULTS_CSV = os.path.join(RESULTS_DIR, "day7_architecture_results.csv")
BEST_MODEL_PATH = os.path.join(RESULTS_DIR, "best_model_day7.keras")


# ==========================================
# 2. CARGAR MEJOR CONFIGURACIÓN DEL DÍA 6
# ==========================================
print("\n📋 Cargando resultados del Día 6...")
if os.path.exists(DAY6_RESULTS):
    day6_df = pd.read_csv(DAY6_RESULTS)
    best_config = day6_df.dropna(subset=['test_mae_real']).nsmallest(1, 'test_mae_real').iloc[0]
    BEST_LR = best_config['learning_rate']
    BEST_BATCH = int(best_config['batch_size'])
    BEST_OPTIMIZER = best_config['optimizer']
    BEST_DROPOUT = best_config['dropout']
    BEST_SEQ = int(best_config['seq_length'])
    print(f"  Mejor config Día 6: lr={BEST_LR}, batch={BEST_BATCH}, "
          f"opt={BEST_OPTIMIZER}, dropout={BEST_DROPOUT}, seq={BEST_SEQ}")
    print(f"  MAE baseline: {best_config['test_mae_real']:.4f} µg/m³")
else:
    print("  ⚠️ No se encontraron resultados del Día 6. Usando defaults.")
    BEST_LR = 0.001
    BEST_BATCH = 64
    BEST_OPTIMIZER = 'adam'
    BEST_DROPOUT = 0.2
    BEST_SEQ = 24


# ==========================================
# 3. CARGA Y PREPROCESAMIENTO DE DATOS
# ==========================================
print("\n📂 Cargando datos...")
df = pd.read_csv(DATA_PATH)
print(f"  Shape original: {df.shape}")

# ----- Feature Engineering: Encodings Cíclicos -----
# Nota: Las columnas hour_sin, hour_cos, etc. ya podrían existir desde el notebook 05.
# Si no existen, las creamos aquí.
if 'hour_sin' not in df.columns:
    print("  🔧 Creando encodings cíclicos...")
    # Necesitamos la columna 'hour' y 'day_of_week' si existen
    if 'hour' in df.columns:
        df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
    if 'day_of_week' in df.columns:
        df['dow_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
        df['dow_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
    print(f"  Shape con features cíclicos: {df.shape}")
else:
    print("  ✅ Encodings cíclicos ya presentes en el dataset")


# ==========================================
# 4. FUNCIONES AUXILIARES
# ==========================================
def create_sequences_by_station(data, seq_length, target_col_name='pm25', group_col='station_name'):
    """Genera secuencias temporales agrupadas por estación."""
    xs, ys = [], []
    for station, group in data.groupby(group_col):
        group_no_station = group.drop(columns=[group_col])
        group_values = group_no_station.values
        target_values = group[target_col_name].values
        for i in range(len(group_values) - seq_length):
            xs.append(group_values[i:(i + seq_length), :])
            ys.append(target_values[i + seq_length])
    return np.array(xs), np.array(ys)


def prepare_data(df, seq_length, seed=42):
    """Normaliza, crea secuencias y divide en train/val/test."""
    scaler = MinMaxScaler()
    cols_to_scale = [c for c in df.columns if c != 'station_name']
    df_scaled = df.copy()
    df_scaled[cols_to_scale] = scaler.fit_transform(df[cols_to_scale])
    pm25_col_idx = cols_to_scale.index('pm25')
    n_features = len(cols_to_scale)

    X, y = create_sequences_by_station(df_scaled, seq_length)
    X_train, X_temp, y_train, y_temp = train_test_split(X, y, test_size=0.30, random_state=seed)
    X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.50, random_state=seed)

    return {
        'X_train': X_train, 'y_train': y_train,
        'X_val': X_val, 'y_val': y_val,
        'X_test': X_test, 'y_test': y_test,
        'scaler': scaler, 'pm25_col_idx': pm25_col_idx,
        'n_features': n_features, 'n_input_features': X.shape[2]
    }


def inverse_pm25(values, scaler, pm25_col_idx, n_features):
    """Desnormaliza valores de PM2.5."""
    dummy = np.zeros((len(values), n_features))
    dummy[:, pm25_col_idx] = values.flatten()
    dummy_inv = scaler.inverse_transform(dummy)
    return dummy_inv[:, pm25_col_idx]


def evaluate_model(model, data, name="Modelo"):
    """Evalúa un modelo y devuelve métricas."""
    y_pred_scaled = model.predict(data['X_test'])
    y_test_real = inverse_pm25(data['y_test'], data['scaler'], data['pm25_col_idx'], data['n_features'])
    y_pred_real = inverse_pm25(y_pred_scaled, data['scaler'], data['pm25_col_idx'], data['n_features'])

    mse_real = mean_squared_error(y_test_real, y_pred_real)
    mae_real = mean_absolute_error(y_test_real, y_pred_real)
    rmse_real = np.sqrt(mse_real)
    r2_real = r2_score(y_test_real, y_pred_real)

    print(f"  📊 {name}:")
    print(f"     MAE:  {mae_real:.4f} µg/m³")
    print(f"     RMSE: {rmse_real:.4f} µg/m³")
    print(f"     R²:   {r2_real:.4f}")

    return {
        'test_mae_real': round(mae_real, 4),
        'test_rmse_real': round(rmse_real, 4),
        'test_r2_real': round(r2_real, 4),
    }


# ==========================================
# 5. DEFINICIÓN DE ARQUITECTURAS
# ==========================================

def build_lstm_2layer(seq_length, n_features, dropout=0.2, lr=0.001, opt='adam'):
    """LSTM de 2 capas — más simple que el baseline."""
    model = Sequential([
        Input(shape=(seq_length, n_features)),
        LSTM(128, activation='relu', return_sequences=True),
        Dropout(dropout),
        LSTM(64, activation='relu'),
        Dropout(dropout),
        Dense(16, activation='relu'),
        Dense(1)
    ])
    optimizer = Adam(learning_rate=lr) if opt == 'adam' else RMSprop(learning_rate=lr)
    model.compile(optimizer=optimizer, loss='mse', metrics=['mae'])
    return model


def build_lstm_3layer(seq_length, n_features, dropout=0.2, lr=0.001, opt='adam'):
    """LSTM de 3 capas — baseline original."""
    model = Sequential([
        Input(shape=(seq_length, n_features)),
        LSTM(128, activation='relu', return_sequences=True),
        Dropout(dropout),
        LSTM(64, activation='relu', return_sequences=True),
        Dropout(dropout),
        LSTM(32, activation='relu'),
        Dropout(max(dropout - 0.1, 0.1)),
        Dense(16, activation='relu'),
        Dense(1)
    ])
    optimizer = Adam(learning_rate=lr) if opt == 'adam' else RMSprop(learning_rate=lr)
    model.compile(optimizer=optimizer, loss='mse', metrics=['mae'])
    return model


def build_bidirectional_lstm(seq_length, n_features, dropout=0.2, lr=0.001, opt='adam'):
    """Bidirectional LSTM — captura patrones temporales en ambas direcciones."""
    model = Sequential([
        Input(shape=(seq_length, n_features)),
        Bidirectional(LSTM(64, activation='relu', return_sequences=True)),
        Dropout(dropout),
        Bidirectional(LSTM(32, activation='relu')),
        Dropout(dropout),
        Dense(16, activation='relu'),
        Dense(1)
    ])
    optimizer = Adam(learning_rate=lr) if opt == 'adam' else RMSprop(learning_rate=lr)
    model.compile(optimizer=optimizer, loss='mse', metrics=['mae'])
    return model


def build_lstm_attention(seq_length, n_features, dropout=0.2, lr=0.001, opt='adam'):
    """LSTM + Capa de Atención Bahdanau simplificada."""
    inputs = Input(shape=(seq_length, n_features))

    # LSTM layers
    x = LSTM(128, activation='relu', return_sequences=True)(inputs)
    x = Dropout(dropout)(x)
    x = LSTM(64, activation='relu', return_sequences=True)(x)
    x = Dropout(dropout)(x)

    # Atención simple (scoring + softmax + weighted sum)
    # score: (batch, seq_length, 64) -> (batch, seq_length, 1)
    attention_scores = Dense(1, activation='tanh')(x)
    attention_weights = tf.nn.softmax(attention_scores, axis=1)
    # weighted sum: (batch, 64)
    context = tf.reduce_sum(x * attention_weights, axis=1)

    # Dense
    out = Dense(16, activation='relu')(context)
    out = Dropout(max(dropout - 0.1, 0.1))(out)
    output = Dense(1)(out)

    model = Model(inputs=inputs, outputs=output)
    optimizer = Adam(learning_rate=lr) if opt == 'adam' else RMSprop(learning_rate=lr)
    model.compile(optimizer=optimizer, loss='mse', metrics=['mae'])
    return model


# ==========================================
# 6. ENTRENAMIENTO DE CADA ARQUITECTURA
# ==========================================
print(f"\n📂 Preparando datos con seq_length={BEST_SEQ}...")
data = prepare_data(df, BEST_SEQ, seed=SEED)
print(f"  Train: {data['X_train'].shape} | Val: {data['X_val'].shape} | Test: {data['X_test'].shape}")

architectures = {
    'LSTM_2Layer': build_lstm_2layer,
    'LSTM_3Layer': build_lstm_3layer,
    'BiLSTM': build_bidirectional_lstm,
    'LSTM_Attention': build_lstm_attention,
}

all_results = []
all_histories = {}
best_mae = float('inf')
best_model = None
best_arch_name = None

for arch_name, build_fn in architectures.items():
    print(f"\n{'='*60}")
    print(f"🔄 Entrenando: {arch_name}")
    print(f"{'='*60}")

    np.random.seed(SEED)
    tf.random.set_seed(SEED)

    model = build_fn(
        BEST_SEQ, data['n_input_features'],
        dropout=BEST_DROPOUT, lr=BEST_LR, opt=BEST_OPTIMIZER
    )
    model.summary()

    early_stop = EarlyStopping(
        monitor='val_loss', patience=7,
        restore_best_weights=True, verbose=1
    )
    reduce_lr = ReduceLROnPlateau(
        monitor='val_loss', factor=0.5,
        patience=3, min_lr=1e-6, verbose=1
    )

    start_time = time.time()
    history = model.fit(
        data['X_train'], data['y_train'],
        epochs=80,
        batch_size=BEST_BATCH,
        validation_data=(data['X_val'], data['y_val']),
        callbacks=[early_stop, reduce_lr],
        verbose=1
    )
    training_time = time.time() - start_time

    # Evaluar
    metrics = evaluate_model(model, data, name=arch_name)

    result = {
        'architecture': arch_name,
        'learning_rate': BEST_LR,
        'batch_size': BEST_BATCH,
        'optimizer': BEST_OPTIMIZER,
        'dropout': BEST_DROPOUT,
        'seq_length': BEST_SEQ,
        'best_epoch': int(np.argmin(history.history['val_loss']) + 1),
        'total_epochs': len(history.history['loss']),
        'training_time_sec': round(training_time, 1),
        'n_params': model.count_params(),
        **metrics
    }
    all_results.append(result)
    all_histories[arch_name] = history.history

    # Guardar parcial
    pd.DataFrame(all_results).to_csv(RESULTS_CSV, index=False)

    # Tracking del mejor
    if metrics['test_mae_real'] < best_mae:
        best_mae = metrics['test_mae_real']
        best_model = model
        best_arch_name = arch_name
        model.save(BEST_MODEL_PATH)
        print(f"\n  🏆 ¡Nueva mejor arquitectura! {arch_name}, MAE={best_mae:.4f}")

    tf.keras.backend.clear_session()


# ==========================================
# 7. RESULTADOS Y VISUALIZACIONES
# ==========================================
print("\n" + "="*60)
print("📊 COMPARACIÓN DE ARQUITECTURAS")
print("="*60)

results_df = pd.DataFrame(all_results)
results_df.to_csv(RESULTS_CSV, index=False)
print(f"\n✅ Resultados guardados en: {RESULTS_CSV}")

sorted_df = results_df.sort_values('test_mae_real')
print("\n🏆 Ranking de arquitecturas:")
print(sorted_df[['architecture', 'test_mae_real', 'test_rmse_real', 'test_r2_real',
                  'n_params', 'best_epoch', 'training_time_sec']].to_string(index=False))

# --- Gráfico 1: Barras comparativas ---
fig, axes = plt.subplots(1, 3, figsize=(18, 6))

# MAE
ax = axes[0]
colors = sns.color_palette('viridis', len(sorted_df))
bars = ax.barh(sorted_df['architecture'], sorted_df['test_mae_real'], color=colors)
ax.set_xlabel('MAE (µg/m³)', fontsize=12)
ax.set_title('MAE por Arquitectura', fontsize=14, fontweight='bold')
for bar, val in zip(bars, sorted_df['test_mae_real']):
    ax.text(val + 0.02, bar.get_y() + bar.get_height()/2., f'{val:.4f}',
            ha='left', va='center', fontsize=10)

# RMSE
ax = axes[1]
bars = ax.barh(sorted_df['architecture'], sorted_df['test_rmse_real'], color=colors)
ax.set_xlabel('RMSE (µg/m³)', fontsize=12)
ax.set_title('RMSE por Arquitectura', fontsize=14, fontweight='bold')
for bar, val in zip(bars, sorted_df['test_rmse_real']):
    ax.text(val + 0.02, bar.get_y() + bar.get_height()/2., f'{val:.4f}',
            ha='left', va='center', fontsize=10)

# R²
ax = axes[2]
bars = ax.barh(sorted_df['architecture'], sorted_df['test_r2_real'], color=colors)
ax.set_xlabel('R²', fontsize=12)
ax.set_title('R² por Arquitectura', fontsize=14, fontweight='bold')
for bar, val in zip(bars, sorted_df['test_r2_real']):
    ax.text(val + 0.005, bar.get_y() + bar.get_height()/2., f'{val:.4f}',
            ha='left', va='center', fontsize=10)

plt.tight_layout()
comparison_path = os.path.join(RESULTS_DIR, "day7_architecture_comparison.png")
plt.savefig(comparison_path, dpi=150, bbox_inches='tight')
plt.show()
print(f"✅ Comparación guardada en: {comparison_path}")

# --- Gráfico 2: Curvas de entrenamiento ---
fig, axes = plt.subplots(2, 2, figsize=(16, 12))
for idx, (arch_name, hist) in enumerate(all_histories.items()):
    ax = axes[idx // 2][idx % 2]
    ax.plot(hist['loss'], label='Train Loss', linewidth=2)
    ax.plot(hist['val_loss'], label='Val Loss', linewidth=2)
    ax.set_title(f'{arch_name}', fontsize=13, fontweight='bold')
    ax.set_xlabel('Epochs')
    ax.set_ylabel('Loss (MSE)')
    ax.legend()
    ax.grid(True, alpha=0.3)

plt.suptitle('Curvas de Entrenamiento por Arquitectura', fontsize=16, fontweight='bold', y=1.02)
plt.tight_layout()
curves_path = os.path.join(RESULTS_DIR, "day7_training_curves.png")
plt.savefig(curves_path, dpi=150, bbox_inches='tight')
plt.show()
print(f"✅ Curvas guardadas en: {curves_path}")


print(f"\n🏆 Mejor arquitectura: {best_arch_name}")
print(f"   MAE: {best_mae:.4f} µg/m³")
print(f"   Modelo guardado en: {BEST_MODEL_PATH}")
print("🎯 Experimentos completados. Usa esta arquitectura para el Día 8.")
