"""
===================================================================
🌐 AirVLC API — Endpoints de Predicción PM2.5
===================================================================
API Flask para servir predicciones del modelo LSTM y
clasificación de riesgo de calidad del aire.

Ejecución:
    python src/api/app.py

    O con gunicorn:
    gunicorn -w 2 -b 0.0.0.0:5000 src.api.app:app

Endpoints:
    GET  /api/health     → Health check
    POST /api/predict    → Predicción de PM2.5
    POST /api/risk       → Clasificación de riesgo
    GET  /api/model/info → Información del modelo
===================================================================
"""

import os
import sys

from flask import Flask
import logging

# Añadir el directorio raíz al path para imports
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT_DIR)

from src.api.routes import register_routes
from src.api.model_loader import ModelLoader
from src.api.es_indexer import ESIndexer


def create_app():
    """Factory para crear la aplicación Flask."""
    app = Flask(__name__)

    # Configuración
    app.config['JSON_SORT_KEYS'] = False
    app.config['JSON_AS_ASCII'] = False

    # Directorio de modelos — ajusta según tu estructura
    models_dir = os.path.join(ROOT_DIR, 'models')
    app.config['MODELS_DIR'] = models_dir

    # Cargar modelos al iniciar
    try:
        loader = ModelLoader(models_dir)
        app.config['MODEL_LOADER'] = loader
        print(f"✅ Modelos cargados desde: {models_dir}")
    except Exception as e:
        print(f"⚠️ Error cargando modelos: {e}")
        print("   La API funcionará pero sin capacidad de predicción LSTM.")
        import traceback
        traceback.print_exc()
        app.config['MODEL_LOADER'] = None

    # Inicializar ES Indexer para indexar predicciones
    try:
        es_indexer = ESIndexer()
        app.config['ES_INDEXER'] = es_indexer
        if es_indexer.is_connected:
            print(f"✅ ES Indexer conectado (indexará predicciones en airvlc-predictions)")
        else:
            print(f"⚠️ ES Indexer no conectado. Predicciones NO se indexarán.")
    except Exception as e:
        print(f"⚠️ ES Indexer no disponible: {e}")
        app.config['ES_INDEXER'] = None

    # Registrar rutas
    register_routes(app)

    return app


app = create_app()


if __name__ == '__main__':
    print("\n" + "="*50)
    print("🌐 AirVLC API — Predicción PM2.5")
    print("="*50)
    print(f"  📂 Modelos: {app.config['MODELS_DIR']}")
    print(f"  🔗 URL: http://localhost:5001")
    print(f"  📋 Endpoints:")
    print(f"     GET  /api/health")
    print(f"     POST /api/predict")
    print(f"     POST /api/risk")
    print(f"     GET  /api/model/info")
    print("="*50 + "\n")

    app.run(debug=True, host='0.0.0.0', port=5001)
