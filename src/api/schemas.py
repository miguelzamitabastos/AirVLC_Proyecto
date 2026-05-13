"""
===================================================================
📐 API Schemas — Validación y formato de request/response
===================================================================
"""

from datetime import datetime


# ==========================================
# VALIDACIÓN DE REQUESTS
# ==========================================

def validate_predict_request(data):
    """
    Valida el request para /api/predict.

    Returns:
        str con error, o None si es válido.
    """
    if 'features' not in data:
        return "Campo 'features' es obligatorio. Debe ser una lista 2D (seq_length x n_features)."

    features = data['features']

    if not isinstance(features, list):
        return "'features' debe ser una lista de listas (array 2D)."

    if len(features) == 0:
        return "'features' no puede estar vacío."

    # Verificar que es 2D
    if not isinstance(features[0], list):
        return "'features' debe ser una lista de listas. Ej: [[f1, f2, ...], [f1, f2, ...], ...]"

    return None


def validate_risk_request(data):
    """
    Valida el request para /api/risk.

    Returns:
        str con error, o None si es válido.
    """
    if 'pm25' not in data and 'features' not in data and 'station' not in data:
        return "Debe enviar 'pm25' (valor directo), 'features' (para predecir) o 'station' (para extraer características automáticamente)."

    if 'pm25' in data:
        try:
            val = float(data['pm25'])
            if val < 0:
                return "'pm25' no puede ser negativo."
        except (ValueError, TypeError):
            return "'pm25' debe ser un número."

    if 'features' in data:
        error = validate_predict_request(data)
        if error:
            return error

    return None


# ==========================================
# FORMATO DE RESPONSES
# ==========================================

def format_predict_response(prediction, model_used):
    """Formatea la respuesta de predicción."""
    return {
        'success': True,
        'prediction_pm25': round(prediction, 4),
        'unit': 'µg/m³',
        'model_used': model_used,
        'timestamp': datetime.now().isoformat(),
    }


def format_risk_response(risk_result):
    """Formatea la respuesta de clasificación de riesgo."""
    return {
        'success': True,
        'pm25_value': risk_result['pm25_value'],
        'unit': 'µg/m³',
        'risk_level': risk_result['level'],
        'color': risk_result['color'],
        'emoji': risk_result['emoji'],
        'description': risk_result['description'],
        'recommendation': risk_result['recommendation'],
        'alert_text': risk_result['alert_text'],
        'station': risk_result.get('station'),
        'timestamp': datetime.now().isoformat(),
    }


def format_error_response(message, status_code):
    """Formatea una respuesta de error."""
    return {
        'success': False,
        'error': message,
        'status_code': status_code,
        'timestamp': datetime.now().isoformat(),
    }
