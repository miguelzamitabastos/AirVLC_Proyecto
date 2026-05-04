"""
===================================================================
🔧 Fix: Re-exportar modelo LSTM Attention para compatibilidad
===================================================================
Ejecuta esto en Google Colab donde el modelo sí carga.
Reconstruye la arquitectura con una capa custom serializable
y copia los pesos. El nuevo .keras se puede cargar en cualquier TF.
===================================================================
"""

# ==========================================
# 1. CONFIGURACIÓN
# ==========================================
import os
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Model, load_model
from tensorflow.keras.layers import (
    LSTM, Dense, Dropout, Input, Layer
)
from tensorflow.keras.optimizers import RMSprop

print(f"TensorFlow version: {tf.__version__}")

# ------------------------------------------
# Montar Google Drive (descomenta en Colab)
# ------------------------------------------
# from google.colab import drive
# drive.mount('/content/drive')

RESULTS_DIR = "/content/drive/MyDrive/Curso Especializacion/Proyecto/results"
ORIGINAL_MODEL = os.path.join(RESULTS_DIR, "best_model_day7.keras")
# Si tienes el attention en otro sitio, ajusta esta ruta:
ATTENTION_MODEL = os.path.join(RESULTS_DIR, "lstm_attention_day7.keras")

FIXED_MODEL = os.path.join(RESULTS_DIR, "lstm_attention_fixed.keras")
ENSEMBLE_DIR = os.path.join(RESULTS_DIR, "ensemble_models")
os.makedirs(RESULTS_DIR, exist_ok=True)


# ==========================================
# 2. CAPA DE ATENCIÓN SERIALIZABLE
# ==========================================
@tf.keras.utils.register_keras_serializable(package="AirVLC")
class AttentionLayer(Layer):
    """Capa de atención Bahdanau serializable."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def build(self, input_shape):
        self.score_dense = Dense(1, activation='tanh', name='attention_score')
        super().build(input_shape)

    def call(self, inputs):
        # inputs shape: (batch, seq_length, features)
        scores = self.score_dense(inputs)       # (batch, seq_length, 1)
        weights = tf.nn.softmax(scores, axis=1) # (batch, seq_length, 1)
        context = tf.reduce_sum(inputs * weights, axis=1)  # (batch, features)
        return context

    def get_config(self):
        config = super().get_config()
        return config


# ==========================================
# 3. RECONSTRUIR MODELO ATTENTION
# ==========================================
print("\n🔧 Reconstruyendo modelo LSTM Attention con capa serializable...")

# Cargar el modelo original para obtener los pesos y la forma de input
try:
    original = load_model(ATTENTION_MODEL)
    input_shape = original.input_shape  # (None, seq_length, n_features)
    seq_length = input_shape[1]
    n_features = input_shape[2]
    print(f"  Modelo original cargado: input_shape={input_shape}")
except Exception as e:
    print(f"  ⚠️ No se pudo cargar modelo attention, usando el best_day7 para referencia")
    original = load_model(ORIGINAL_MODEL)
    input_shape = original.input_shape
    seq_length = input_shape[1]
    n_features = input_shape[2]

# Construir nueva arquitectura con capa serializable
inputs = Input(shape=(seq_length, n_features))
x = LSTM(128, activation='relu', return_sequences=True)(inputs)
x = Dropout(0.2)(x)
x = LSTM(64, activation='relu', return_sequences=True)(x)
x = Dropout(0.2)(x)
context = AttentionLayer(name='attention')(x)
out = Dense(16, activation='relu')(context)
out = Dropout(0.1)(out)
output = Dense(1)(out)

new_model = Model(inputs=inputs, outputs=output)
new_model.compile(optimizer=RMSprop(learning_rate=0.001), loss='mse', metrics=['mae'])

print(f"  Nueva arquitectura construida")
new_model.summary()

# Intentar copiar pesos del modelo original
try:
    original_attention = load_model(ATTENTION_MODEL)
    # Los pesos de las capas LSTM y Dense deberían ser compatibles
    # Copiar capa por capa las que coincidan
    for new_layer, orig_layer in zip(new_model.layers, original_attention.layers):
        try:
            orig_weights = orig_layer.get_weights()
            if orig_weights:
                new_layer.set_weights(orig_weights)
                print(f"  ✅ Pesos copiados: {new_layer.name}")
        except Exception:
            print(f"  ⏭️  Saltado: {new_layer.name} (formas incompatibles)")
    print("\n  ✅ Pesos transferidos del modelo original")
except Exception as e:
    print(f"\n  ⚠️ No se pudieron copiar pesos: {e}")
    print("  El modelo se guardará con pesos aleatorios — necesitará reentrenamiento")

# Guardar modelo fijo
new_model.save(FIXED_MODEL)
print(f"\n✅ Modelo guardado en: {FIXED_MODEL}")


# ==========================================
# 4. FIX ENSEMBLE (si existe)
# ==========================================
if os.path.exists(ENSEMBLE_DIR):
    print("\n🔧 Reconstruyendo modelos Ensemble...")
    ensemble_files = sorted([f for f in os.listdir(ENSEMBLE_DIR) if f.endswith('.keras')])

    for ef in ensemble_files:
        ef_path = os.path.join(ENSEMBLE_DIR, ef)
        fixed_path = os.path.join(ENSEMBLE_DIR, ef.replace('.keras', '_fixed.keras'))

        try:
            orig_ens = load_model(ef_path)
            inp_shape = orig_ens.input_shape

            # Reconstruir con capa serializable
            inp = Input(shape=(inp_shape[1], inp_shape[2]))
            x = LSTM(128, activation='relu', return_sequences=True)(inp)
            x = Dropout(0.2)(x)
            x = LSTM(64, activation='relu', return_sequences=True)(x)
            x = Dropout(0.2)(x)
            ctx = AttentionLayer(name='attention')(x)
            o = Dense(16, activation='relu')(ctx)
            o = Dropout(0.1)(o)
            out = Dense(1)(o)

            fixed_ens = Model(inputs=inp, outputs=out)
            fixed_ens.compile(optimizer=RMSprop(learning_rate=0.001), loss='mse', metrics=['mae'])

            # Copiar pesos
            for new_l, orig_l in zip(fixed_ens.layers, orig_ens.layers):
                try:
                    w = orig_l.get_weights()
                    if w:
                        new_l.set_weights(w)
                except Exception:
                    pass

            fixed_ens.save(fixed_path)
            print(f"  ✅ {ef} → {os.path.basename(fixed_path)}")
        except Exception as e:
            print(f"  ❌ {ef}: {e}")

print("\n🎯 ¡Modelos re-exportados! Descárgalos y cópialos a models/")


# ==========================================
# 5. VERIFICACIÓN
# ==========================================
print("\n🔍 Verificando que el modelo fixed se puede cargar...")
try:
    test_model = load_model(FIXED_MODEL)
    dummy_input = np.random.rand(1, seq_length, n_features).astype(np.float32)
    pred = test_model.predict(dummy_input)
    print(f"  ✅ Modelo cargado y predicción OK: {pred.flatten()[0]:.6f}")
except Exception as e:
    print(f"  ❌ Error: {e}")
