"""
Compatibilidad al cargar .keras guardados con Keras que serializa
`quantization_config` en capas Dense (u otras): versiones actuales de
keras en TensorFlow pueden rechazar ese campo con
"Unrecognized keyword arguments".
"""

from __future__ import annotations

import json
import os
import tempfile
import zipfile


def _strip_key_recursive(obj, key: str):
    if isinstance(obj, dict):
        obj.pop(key, None)
        for v in obj.values():
            _strip_key_recursive(v, key)
    elif isinstance(obj, list):
        for item in obj:
            _strip_key_recursive(item, key)


def _rewrite_keras_zip_without_quantization_config(src_path: str, dst_path: str) -> None:
    with zipfile.ZipFile(src_path, "r") as zin, zipfile.ZipFile(
        dst_path, "w", compression=zipfile.ZIP_DEFLATED
    ) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == "config.json":
                cfg = json.loads(data.decode("utf-8"))
                _strip_key_recursive(cfg, "quantization_config")
                data = json.dumps(cfg, separators=(",", ":")).encode("utf-8")
            zout.writestr(info, data)


def load_keras_model_compat(path: str, custom_objects=None):
    """
    Carga un modelo .keras; si falla por quantization_config en capas,
    reescribe config.json temporalmente y reintenta.
    """
    from tensorflow.keras.models import load_model

    custom_objects = custom_objects or {}
    try:
        return load_model(path, custom_objects=custom_objects)
    except (TypeError, ValueError) as e:
        err = str(e)
        if "quantization_config" not in err and "could not be deserialized" not in err:
            raise

    fd, tmp = tempfile.mkstemp(suffix=".keras", prefix="airvlc_keras_")
    os.close(fd)
    try:
        _rewrite_keras_zip_without_quantization_config(path, tmp)
        return load_model(tmp, custom_objects=custom_objects)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
