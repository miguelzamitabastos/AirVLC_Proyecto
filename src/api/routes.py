"""
===================================================================
🛣️ API Routes — Endpoints de la API AirVLC
===================================================================
"""

from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
import numpy as np

# Importar clasificador de riesgo
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from src.ml.risk_classifier import RiskClassifier
from src.api.schemas import (
    validate_predict_request,
    validate_risk_request,
    format_predict_response,
    format_risk_response,
    format_error_response,
)

# Importar el orquestador del chatbot y extractor
from src.services.chatbot_orchestrator import ChatbotOrchestrator
from src.api.feature_extractor import FeatureExtractor

# Inicializar clasificador de riesgo, orquestador y extractor
risk_classifier = RiskClassifier()
try:
    feature_extractor = FeatureExtractor()
except Exception as e:
    print(f"⚠️ Error inicializando FeatureExtractor: {e}")
    feature_extractor = None
try:
    chatbot = ChatbotOrchestrator()
except Exception as e:
    print(f"⚠️ Error inicializando ChatbotOrchestrator: {e}")
    chatbot = None


api_bp = Blueprint('api', __name__, url_prefix='/api')


def register_routes(app):
    """Registra todas las rutas de la API."""
    app.register_blueprint(api_bp)


# ==========================================
# GET /api/health
# ==========================================
@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check — verifica que la API y los modelos estén activos."""
    loader = current_app.config.get('MODEL_LOADER')

    status = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'AirVLC PM2.5 Prediction API',
        'version': '1.0.0',
        'models': {
            'loaded': loader.is_ready if loader else False,
            'best_model': loader.best_model_name if loader else None,
            'available_models': list(loader.models.keys()) if loader else [],
        }
    }

    http_code = 200 if (loader and loader.is_ready) else 503
    return jsonify(status), http_code


# ==========================================
# POST /api/predict
# ==========================================
@api_bp.route('/predict', methods=['POST'])
def predict_pm25():
    """
    Predice el valor de PM2.5 a partir de features de entrada.

    Body (JSON):
    {
        "features": [[...], [...], ...],   // Secuencia de features (seq_length x n_features)
        "model": "LSTM_Attention"           // Opcional: modelo a usar
    }

    Response:
    {
        "prediction_pm25": 15.3,
        "model_used": "LSTM_Attention",
        "timestamp": "..."
    }
    """
    loader = current_app.config.get('MODEL_LOADER')

    if not loader or not loader.is_ready:
        return jsonify(format_error_response(
            'Modelos no disponibles. Asegúrate de que los archivos .keras están en models/',
            503
        )), 503

    # Validar request
    data = request.get_json()
    if not data:
        return jsonify(format_error_response('Request body vacío. Envía JSON.', 400)), 400

    error = validate_predict_request(data)
    if error:
        return jsonify(format_error_response(error, 400)), 400

    try:
        # Preparar input
        features = np.array(data['features'])

        # Si es 2D (seq_length, n_features), añadir batch dimension
        if features.ndim == 2:
            features = features.reshape(1, features.shape[0], features.shape[1])

        # Predecir
        model_name = data.get('model', None)
        prediction = loader.predict(features, model_name=model_name)
        pred_value = float(prediction.flatten()[0])

        # Formato de respuesta
        response = format_predict_response(
            prediction=pred_value,
            model_used=model_name or loader.best_model_name,
        )

        # Indexar predicción en Elasticsearch (async, fail-safe)
        es_indexer = current_app.config.get('ES_INDEXER')
        if es_indexer:
            es_indexer.index_prediction({
                'pm25_predicted': pred_value,
                'model_used': model_name or loader.best_model_name,
                'source': 'api',
                'prediction_type': 'realtime',
            })

        return jsonify(response), 200

    except Exception as e:
        return jsonify(format_error_response(f'Error en predicción: {str(e)}', 500)), 500


# ==========================================
# POST /api/risk
# ==========================================
@api_bp.route('/risk', methods=['POST'])
def classify_risk():
    """
    Clasifica el nivel de riesgo a partir de un valor de PM2.5.

    Body (JSON):
    {
        "pm25": 25.3,
        "station": "Valencia Viveros"   // Opcional
    }

    O con features para predecir primero:
    {
        "features": [[...], [...], ...],
        "station": "Valencia Viveros"
    }

    Response:
    {
        "pm25_value": 25.3,
        "risk_level": "moderado",
        "color": "#f39c12",
        "emoji": "🟡",
        "description": "...",
        "recommendation": "...",
        "alert_text": "..."
    }
    """
    data = request.get_json()
    if not data:
        return jsonify(format_error_response('Request body vacío. Envía JSON.', 400)), 400

    error = validate_risk_request(data)
    if error:
        return jsonify(format_error_response(error, 400)), 400

    try:
        pm25_value = None
        station = data.get('station', None)

        # Caso 1: PM2.5 proporcionado directamente
        if 'pm25' in data:
            pm25_value = float(data['pm25'])

        # Caso 2: Features proporcionadas directamente o extraídas automáticamente
        else:
            loader = current_app.config.get('MODEL_LOADER')
            if not loader or not loader.is_ready:
                return jsonify(format_error_response(
                    'Modelos no disponibles para predicción', 503
                )), 503

            if 'features' in data:
                features = np.array(data['features'])
            elif station and feature_extractor:
                try:
                    extracted_features, real_station = feature_extractor.get_features(station)
                    features = np.array(extracted_features)
                    station = real_station # Update to real station name
                except Exception as e:
                    return jsonify(format_error_response(f'Error extrayendo features para {station}: {str(e)}', 400)), 400
            else:
                 return jsonify(format_error_response('Faltan features o station, o FeatureExtractor no disponible', 400)), 400

            if features.ndim == 2:
                features = features.reshape(1, features.shape[0], features.shape[1])

            model_name = data.get('model', None)
            prediction = loader.predict(features, model_name=model_name)
            norm_value = float(prediction.flatten()[0])

            # Denormalizar (de escala 0-1 a µg/m³ reales)
            if feature_extractor:
                pm25_value = feature_extractor.denormalize_pm25(norm_value)
            else:
                pm25_value = norm_value # Fallback si no hay extractor

        # Clasificar riesgo
        result = risk_classifier.classify(pm25_value, station=station)
        response = format_risk_response(result)

        # Indexar en Elasticsearch (async, fail-safe)
        es_indexer = current_app.config.get('ES_INDEXER')
        if es_indexer:
            es_indexer.index_prediction({
                'pm25_predicted': pm25_value,
                'station': station,
                'risk_level': result['level'],
                'risk_color': result['color'],
                'risk_emoji': result['emoji'],
                'alert_text': result['alert_text'],
                'model_used': 'direct' if 'pm25' in data else (loader.best_model_name if loader else 'unknown'),
                'source': 'api',
                'prediction_type': 'realtime',
            })

        return jsonify(response), 200

    except Exception as e:
        return jsonify(format_error_response(f'Error en clasificación: {str(e)}', 500)), 500





# ==========================================
# GET /api/model/info
# ==========================================
@api_bp.route('/model/info', methods=['GET'])
def model_info():
    """
    Devuelve información sobre los modelos cargados.

    Response:
    {
        "models_loaded": ["LSTM_Attention", "Best_Day7", ...],
        "best_model": "LSTM_Attention",
        "best_model_params": 126818,
        ...
    }
    """
    loader = current_app.config.get('MODEL_LOADER')

    if not loader:
        return jsonify(format_error_response('Model loader no configurado', 503)), 503

    info = loader.get_info()
    info['timestamp'] = datetime.now().isoformat()
    info['risk_thresholds'] = risk_classifier.thresholds

    return jsonify(info), 200


# ==========================================
# POST /api/chat
# ==========================================
@api_bp.route('/chat', methods=['POST'])
def chat():
    """
    Endpoint para interactuar con el Chatbot de Lex.
    
    Body (JSON):
    {
        "message": "Dime la calidad del aire en la politecnica",
        "session_id": "usuario-123" // Opcional
    }
    
    Response:
    {
        "reply": "La calidad del aire esperada en la politecnica...",
        "intent": "ConsultarCalidad",
        "station": "politecnica",
        ...
    }
    """
    if not chatbot:
        return jsonify(format_error_response('Servicio de Chatbot no disponible', 503)), 503

    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify(format_error_response('Se requiere el campo "message"', 400)), 400

    message = data['message']
    session_id = data.get('session_id', 'test-session')
    loader = current_app.config.get('MODEL_LOADER')

    try:
        response = chatbot.process_message(text=message, session_id=session_id, model_loader=loader)
        return jsonify(response), 200
    except Exception as e:
        return jsonify(format_error_response(f'Error en el chat: {str(e)}', 500)), 500

