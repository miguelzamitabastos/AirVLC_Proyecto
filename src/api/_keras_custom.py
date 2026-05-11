"""
Custom Keras layers/objects used by AirVLC models.

Kept in a dedicated module so `ModelLoader` can pass `custom_objects`
without importing training notebooks code.
"""

from __future__ import annotations

try:
    import tensorflow as tf
    from tensorflow.keras.layers import Layer, Dense

    TF_AVAILABLE = True
except Exception:  # pragma: no cover
    TF_AVAILABLE = False
    tf = None  # type: ignore
    Layer = object  # type: ignore
    Dense = object  # type: ignore


if TF_AVAILABLE:

    @tf.keras.utils.register_keras_serializable(package="AirVLC")
    class BahdanauAttention(Layer):
        """
        Bahdanau-style additive attention over a time axis.

        Expected input: (batch, time, features)
        Output: (batch, features)
        """

        def __init__(self, units: int = 32, **kwargs):
            super().__init__(**kwargs)
            self.units = int(units)
            self.W = Dense(self.units, activation="tanh", name="attn_W")
            self.V = Dense(1, name="attn_V")

        def call(self, inputs):
            # inputs: (B, T, F)
            score = self.V(self.W(inputs))  # (B, T, 1)
            weights = tf.nn.softmax(score, axis=1)  # (B, T, 1)
            context = tf.reduce_sum(inputs * weights, axis=1)  # (B, F)
            return context

        def get_config(self):
            cfg = super().get_config()
            cfg.update({"units": self.units})
            return cfg

