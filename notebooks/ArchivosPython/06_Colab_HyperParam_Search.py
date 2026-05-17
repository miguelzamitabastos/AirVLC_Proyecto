"""
===================================================================
📊 Día 6 — Búsqueda Sistemática de Hiperparámetros LSTM para PM2.5
===================================================================
Script preparado para ejecutar en Google Colab con GPU.
Incluye:
  1. Función reutilizable train_lstm() parametrizada
  2. Grid search usando hyperparams_grid.json
  3. Registro de métricas en CSV
  4. Heatmaps de MAE por combinación de hiperparámetros
  5. Selección automática del mejor modelo

Uso en Colab:
  1. Sube este archivo y hyperparams_grid.json a tu Google Drive
  2. Monta Google Drive
  3. Ejecuta este script (o copia las secciones en celdas de un notebook)
===================================================================
"""

# ==========================================
# 1. CONFIGURACIÓN Y MONTAJE DE DRIVE
# ==========================================
import os
import json
import time
import itertools
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout, Input
from tensorflow.keras.optimizers import Adam, RMSprop
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau

# Fijar seeds para reproducibilidad
SEED = 42
np.random.seed(SEED)
tf.random.set_seed(SEED)

# Estilos de gráficos
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
GRID_PATH = "/content/drive/MyDrive/Curso Especializacion/Proyecto/hyperparams_grid.json"
RESULTS_DIR = "/content/drive/MyDrive/Curso Especializacion/Proyecto/results"
os.makedirs(RESULTS_DIR, exist_ok=True)

RESULTS_CSV = os.path.join(RESULTS_DIR, "day6_hyperparams_results.csv")
BEST_MODEL_PATH = os.path.join(RESULTS_DIR, "best_model_day6.keras")

# ==========================================
# 2. CARGA Y PREPROCESAMIENTO DE DATOS
# ==========================================
print("\n📂 Cargando datos...")
df = pd.read_csv(DATA_PATH)
print(f"  Shape: {df.shape}")
print(f"  Columnas: {list(df.columns)}")
print(f"  Estaciones: {df['station_name'].nunique()}")

# ==========================================
# 3. FUNCIÓN DE CREACIÓN DE SECUENCIAS
# ==========================================
def create_sequences_by_station(data, seq_length, target_col_name='pm25', group_col='station_name'):
    """
    Genera secuencias temporales agrupadas por estación.
    Evita secuencias que crucen entre estaciones.

    Args:
        data: DataFrame con todas las features
        seq_length: Número de pasos temporales (horas)
        target_col_name: Columna objetivo
        group_col: Columna para agrupar

    Returns:
        X: array (n_samples, seq_length, n_features)
        y: array (n_samples,)
    """
    xs, ys = [], []
    for station, group in data.groupby(group_col):
        group_no_station = group.drop(columns=[group_col])
        group_values = group_no_station.values
        target_values = group[target_col_name].values
        for i in range(len(group_values) - seq_length):
            xs.append(group_values[i:(i + seq_length), :])
            ys.append(target_values[i + seq_length])
    return np.array(xs), np.array(ys)


# ==========================================
# 4. FUNCIÓN REUTILIZABLE DE ENTRENAMIENTO
# ==========================================
def train_lstm(
    df,
    learning_rate=0.001,
    batch_size=64,
    optimizer_name='adam',
    dropout=0.2,
    seq_length=24,
    epochs=80,
    patience=7,
    seed=42,
    verbose=1
):
    """
    Entrena un modelo LSTM para predicción de PM2.5 con los hiperparámetros dados.

    Args:
        df: DataFrame completo (incluye station_name)
        learning_rate: Tasa de aprendizaje
        batch_size: Tamaño del batch
        optimizer_name: 'adam' o 'rmsprop'
        dropout: Tasa de dropout
        seq_length: Longitud de la secuencia temporal
        epochs: Máximo de épocas
        patience: Paciencia para early stopping
        seed: Semilla para reproducibilidad
        verbose: Nivel de log (0=silencioso, 1=barra, 2=detallado)

    Returns:
        dict con métricas, historia de entrenamiento y modelo
    """
    # Fijar seeds
    np.random.seed(seed)
    tf.random.set_seed(seed)

    # ----- Normalización -----
    scaler = MinMaxScaler()
    cols_to_scale = [c for c in df.columns if c != 'station_name']
    df_scaled = df.copy()
    df_scaled[cols_to_scale] = scaler.fit_transform(df[cols_to_scale])
    pm25_col_idx = cols_to_scale.index('pm25')
    n_features = len(cols_to_scale)

    # ----- Crear secuencias -----
    X, y = create_sequences_by_station(df_scaled, seq_length)

    # ----- Split: 70/15/15 -----
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.30, random_state=seed
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.50, random_state=seed
    )

    print(f"\n  Train: {X_train.shape} | Val: {X_val.shape} | Test: {X_test.shape}")

    # ----- Construir modelo -----
    model = Sequential([
        Input(shape=(seq_length, X.shape[2])),
        LSTM(128, activation='relu', return_sequences=True),
        Dropout(dropout),
        LSTM(64, activation='relu', return_sequences=True),
        Dropout(dropout),
        LSTM(32, activation='relu'),
        Dropout(max(dropout - 0.1, 0.1)),
        Dense(16, activation='relu'),
        Dense(1)
    ])

    # Seleccionar optimizador
    if optimizer_name.lower() == 'rmsprop':
        optimizer = RMSprop(learning_rate=learning_rate)
    else:
        optimizer = Adam(learning_rate=learning_rate)

    model.compile(optimizer=optimizer, loss='mse', metrics=['mae'])

    # ----- Callbacks -----
    early_stop = EarlyStopping(
        monitor='val_loss',
        patience=patience,
        restore_best_weights=True,
        verbose=1
    )
    reduce_lr = ReduceLROnPlateau(
        monitor='val_loss',
        factor=0.5,
        patience=3,
        min_lr=1e-6,
        verbose=1
    )

    # ----- Entrenamiento -----
    start_time = time.time()
    history = model.fit(
        X_train, y_train,
        epochs=epochs,
        batch_size=batch_size,
        validation_data=(X_val, y_val),
        callbacks=[early_stop, reduce_lr],
        verbose=verbose
    )
    training_time = time.time() - start_time

    # ----- Evaluación en Test (escala normalizada) -----
    y_pred_scaled = model.predict(X_test)
    mse_scaled = mean_squared_error(y_test, y_pred_scaled)
    mae_scaled = mean_absolute_error(y_test, y_pred_scaled)
    r2_scaled = r2_score(y_test, y_pred_scaled)

    # ----- Desnormalización -----
    def inverse_transform_pm25(values_scaled):
        dummy = np.zeros((len(values_scaled), n_features))
        dummy[:, pm25_col_idx] = values_scaled.flatten()
        dummy_inv = scaler.inverse_transform(dummy)
        return dummy_inv[:, pm25_col_idx]

    y_test_real = inverse_transform_pm25(y_test)
    y_pred_real = inverse_transform_pm25(y_pred_scaled)

    mse_real = mean_squared_error(y_test_real, y_pred_real)
    mae_real = mean_absolute_error(y_test_real, y_pred_real)
    rmse_real = np.sqrt(mse_real)
    r2_real = r2_score(y_test_real, y_pred_real)

    # ----- Métricas de validación -----
    val_mae = min(history.history['val_mae'])
    val_loss = min(history.history['val_loss'])
    best_epoch = np.argmin(history.history['val_loss']) + 1
    total_epochs = len(history.history['loss'])

    results = {
        'learning_rate': learning_rate,
        'batch_size': batch_size,
        'optimizer': optimizer_name,
        'dropout': dropout,
        'seq_length': seq_length,
        'best_epoch': best_epoch,
        'total_epochs': total_epochs,
        'training_time_sec': round(training_time, 1),
        'val_loss': round(val_loss, 6),
        'val_mae': round(val_mae, 6),
        'test_mse_scaled': round(mse_scaled, 6),
        'test_mae_scaled': round(mae_scaled, 6),
        'test_r2_scaled': round(r2_scaled, 4),
        'test_mse_real': round(mse_real, 4),
        'test_rmse_real': round(rmse_real, 4),
        'test_mae_real': round(mae_real, 4),
        'test_r2_real': round(r2_real, 4),
    }

    print(f"\n  📊 Resultados:")
    print(f"     MAE (real): {mae_real:.4f} µg/m³")
    print(f"     RMSE (real): {rmse_real:.4f} µg/m³")
    print(f"     R² (real): {r2_real:.4f}")
    print(f"     Mejor época: {best_epoch}/{total_epochs}")
    print(f"     Tiempo: {training_time:.1f}s")

    return {
        'results': results,
        'history': history.history,
        'model': model,
        'scaler': scaler,
        'pm25_col_idx': pm25_col_idx,
        'n_features': n_features,
    }


# ==========================================
# 5. EJECUCIÓN DEL GRID SEARCH
# ==========================================
print("\n📋 Cargando grid de hiperparámetros...")
with open(GRID_PATH, 'r') as f:
    grid_config = json.load(f)

grid = grid_config['grid']
print(f"   Total de configuraciones: {len(grid)}")

all_results = []
best_mae = float('inf')
best_model_info = None

for i, params in enumerate(grid):
    print(f"\n{'='*60}")
    print(f"🔄 Configuración {i+1}/{len(grid)}")
    print(f"   lr={params['learning_rate']}, batch={params['batch_size']}, "
          f"opt={params['optimizer']}, dropout={params['dropout']}, "
          f"seq_len={params['seq_length']}")
    print(f"{'='*60}")

    try:
        output = train_lstm(
            df,
            learning_rate=params['learning_rate'],
            batch_size=params['batch_size'],
            optimizer_name=params['optimizer'],
            dropout=params['dropout'],
            seq_length=params['seq_length'],
            epochs=80,
            patience=7,
            seed=SEED,
            verbose=1
        )

        result = output['results']
        all_results.append(result)

        # Guardar resultados parciales (por si se interrumpe)
        pd.DataFrame(all_results).to_csv(RESULTS_CSV, index=False)

        # Tracking del mejor modelo
        if result['test_mae_real'] < best_mae:
            best_mae = result['test_mae_real']
            best_model_info = output
            output['model'].save(BEST_MODEL_PATH)
            print(f"\n  🏆 ¡Nuevo mejor modelo! MAE={best_mae:.4f} µg/m³")

    except Exception as e:
        print(f"\n  ❌ Error en configuración {i+1}: {e}")
        error_result = {**params, 'error': str(e)}
        all_results.append(error_result)

    # Limpiar memoria
    tf.keras.backend.clear_session()

# ==========================================
# 6. RESULTADOS FINALES Y CSV
# ==========================================
print("\n" + "="*60)
print("📊 RESULTADOS DEL GRID SEARCH")
print("="*60)

results_df = pd.DataFrame(all_results)
results_df.to_csv(RESULTS_CSV, index=False)
print(f"\n✅ Resultados guardados en: {RESULTS_CSV}")

# Mostrar tabla ordenada por MAE real
if 'test_mae_real' in results_df.columns:
    display_cols = ['learning_rate', 'batch_size', 'optimizer', 'dropout',
                    'seq_length', 'test_mae_real', 'test_rmse_real', 'test_r2_real',
                    'best_epoch', 'training_time_sec']
    valid_cols = [c for c in display_cols if c in results_df.columns]
    sorted_df = results_df.dropna(subset=['test_mae_real']).sort_values('test_mae_real')
    print("\n🏆 Ranking de configuraciones:")
    print(sorted_df[valid_cols].to_string(index=False))

    # Mejor configuración
    best_row = sorted_df.iloc[0]
    print(f"\n🥇 Mejor configuración:")
    print(f"   lr={best_row['learning_rate']}, batch={best_row['batch_size']}, "
          f"opt={best_row['optimizer']}, dropout={best_row['dropout']}, "
          f"seq_len={best_row['seq_length']}")
    print(f"   MAE = {best_row['test_mae_real']:.4f} µg/m³")
    print(f"   RMSE = {best_row['test_rmse_real']:.4f} µg/m³")
    print(f"   R² = {best_row['test_r2_real']:.4f}")

# ==========================================
# 7. VISUALIZACIONES — HEATMAPS
# ==========================================
print("\n📈 Generando heatmaps...")

if 'test_mae_real' in results_df.columns:
    valid_results = results_df.dropna(subset=['test_mae_real'])

    # --- Heatmap 1: Learning Rate vs Dropout (filtrado seq_length=24, optimizer=adam) ---
    fig, axes = plt.subplots(1, 3, figsize=(20, 6))

    subset = valid_results[
        (valid_results['seq_length'] == 24) &
        (valid_results['optimizer'] == 'adam')
    ]
    if len(subset) > 0:
        pivot = subset.pivot_table(
            values='test_mae_real',
            index='dropout',
            columns='learning_rate',
            aggfunc='mean'
        )
        if len(pivot) > 0:
            sns.heatmap(
                pivot, annot=True, fmt='.4f', cmap='YlOrRd_r',
                ax=axes[0], cbar_kws={'label': 'MAE (µg/m³)'}
            )
            axes[0].set_title('MAE: Dropout vs Learning Rate\n(seq=24, adam)', fontsize=12, fontweight='bold')

    # --- Heatmap 2: Learning Rate vs Batch Size (filtrado seq_length=24, optimizer=adam) ---
    if len(subset) > 0:
        pivot2 = subset.pivot_table(
            values='test_mae_real',
            index='batch_size',
            columns='learning_rate',
            aggfunc='mean'
        )
        if len(pivot2) > 0:
            sns.heatmap(
                pivot2, annot=True, fmt='.4f', cmap='YlOrRd_r',
                ax=axes[1], cbar_kws={'label': 'MAE (µg/m³)'}
            )
            axes[1].set_title('MAE: Batch Size vs Learning Rate\n(seq=24, adam)', fontsize=12, fontweight='bold')

    # --- Heatmap 3: Comparación seq_length ---
    pivot3 = valid_results.pivot_table(
        values='test_mae_real',
        index='seq_length',
        columns='learning_rate',
        aggfunc='mean'
    )
    if len(pivot3) > 0:
        sns.heatmap(
            pivot3, annot=True, fmt='.4f', cmap='YlOrRd_r',
            ax=axes[2], cbar_kws={'label': 'MAE (µg/m³)'}
        )
        axes[2].set_title('MAE: Seq Length vs Learning Rate\n(promedio)', fontsize=12, fontweight='bold')

    plt.tight_layout()
    heatmap_path = os.path.join(RESULTS_DIR, "day6_heatmaps.png")
    plt.savefig(heatmap_path, dpi=150, bbox_inches='tight')
    plt.show()
    print(f"✅ Heatmaps guardados en: {heatmap_path}")

    # --- Bar chart: Top 5 configuraciones ---
    fig, ax = plt.subplots(figsize=(12, 6))
    top5 = valid_results.nsmallest(5, 'test_mae_real').reset_index(drop=True)
    labels = [
        f"lr={r['learning_rate']}\nb={r['batch_size']}\nd={r['dropout']}\nseq={r['seq_length']}"
        for _, r in top5.iterrows()
    ]
    bars = ax.bar(labels, top5['test_mae_real'], color=sns.color_palette('viridis', 5))
    ax.set_ylabel('MAE (µg/m³)', fontsize=12)
    ax.set_title('Top 5 Configuraciones de Hiperparámetros', fontsize=14, fontweight='bold')

    for bar, val in zip(bars, top5['test_mae_real']):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.02,
                f'{val:.4f}', ha='center', va='bottom', fontsize=10, fontweight='bold')

    plt.tight_layout()
    top5_path = os.path.join(RESULTS_DIR, "day6_top5.png")
    plt.savefig(top5_path, dpi=150, bbox_inches='tight')
    plt.show()
    print(f"✅ Top 5 chart guardado en: {top5_path}")


print(f"\n✅ Mejor modelo guardado en: {BEST_MODEL_PATH}")
print("🎯 Grid search completado. Usa la mejor configuración para el Día 7.")
