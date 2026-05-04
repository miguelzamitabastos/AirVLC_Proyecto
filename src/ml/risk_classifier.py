"""
===================================================================
🏥 Risk Classifier — Clasificación de Niveles de Riesgo PM2.5
===================================================================
Módulo reutilizable para clasificar valores de PM2.5 en niveles
de riesgo según estándares OMS/EPA.

Uso:
    from risk_classifier import RiskClassifier

    classifier = RiskClassifier()
    result = classifier.classify(pm25_value=25.3)
    print(result)
    # {'level': 'moderado', 'color': '#f39c12', 'emoji': '🟡',
    #  'description': '...', 'recommendation': '...'}
===================================================================
"""

RISK_LEVELS = {
    'bueno': {
        'min': 0,
        'max': 12.0,
        'color': '#2ecc71',
        'emoji': '🟢',
        'description': 'La calidad del aire es satisfactoria y no presenta riesgos.',
        'recommendation': 'No se requieren precauciones especiales.',
    },
    'moderado': {
        'min': 12.1,
        'max': 35.4,
        'color': '#f39c12',
        'emoji': '🟡',
        'description': 'La calidad del aire es aceptable, pero puede afectar a personas sensibles.',
        'recommendation': 'Personas con enfermedades respiratorias deben limitar actividad exterior prolongada.',
    },
    'malo': {
        'min': 35.5,
        'max': 55.4,
        'color': '#e67e22',
        'emoji': '🟠',
        'description': 'La calidad del aire es deficiente y puede afectar a la salud.',
        'recommendation': 'Reducir actividades al aire libre. Grupos sensibles deben permanecer en interiores.',
    },
    'peligroso': {
        'min': 55.5,
        'max': float('inf'),
        'color': '#e74c3c',
        'emoji': '🔴',
        'description': 'La calidad del aire es peligrosa. Riesgo para toda la población.',
        'recommendation': 'Evitar toda actividad al aire libre. Cerrar ventanas y puertas.',
    },
}


class RiskClassifier:
    """
    Clasificador de niveles de riesgo de calidad del aire
    basado en concentraciones de PM2.5 (µg/m³).
    """

    def __init__(self):
        self.levels = RISK_LEVELS

    def classify(self, pm25_value, station=None):
        """
        Clasifica un valor de PM2.5 en nivel de riesgo.

        Args:
            pm25_value: Concentración de PM2.5 en µg/m³
            station: Nombre opcional de la estación

        Returns:
            dict con level, color, emoji, description, recommendation, pm25_value
        """
        level = self._get_level(pm25_value)
        info = self.levels[level]

        location_str = f" en {station}" if station else ""

        return {
            'pm25_value': round(pm25_value, 2),
            'level': level,
            'color': info['color'],
            'emoji': info['emoji'],
            'description': info['description'],
            'recommendation': info['recommendation'],
            'alert_text': self._generate_alert(pm25_value, level, location_str),
            'station': station,
        }

    def classify_batch(self, pm25_values, stations=None):
        """Clasifica un lote de valores PM2.5."""
        results = []
        for i, val in enumerate(pm25_values):
            station = stations[i] if stations else None
            results.append(self.classify(val, station))
        return results

    def _get_level(self, pm25_value):
        """Determina el nivel de riesgo a partir del valor PM2.5."""
        if pm25_value <= 12.0:
            return 'bueno'
        elif pm25_value <= 35.4:
            return 'moderado'
        elif pm25_value <= 55.4:
            return 'malo'
        else:
            return 'peligroso'

    def _generate_alert(self, pm25_value, level, location=""):
        """Genera un mensaje de alerta en lenguaje natural."""
        alerts = {
            'bueno': f"La calidad del aire{location} es BUENA (PM2.5: {pm25_value:.1f} µg/m³). Sin riesgos.",
            'moderado': f"La calidad del aire{location} es MODERADA (PM2.5: {pm25_value:.1f} µg/m³). Precaución para grupos sensibles.",
            'malo': f"⚠️ La calidad del aire{location} es MALA (PM2.5: {pm25_value:.1f} µg/m³). Reducir actividad exterior.",
            'peligroso': f"🚨 ALERTA: Calidad del aire{location} PELIGROSA (PM2.5: {pm25_value:.1f} µg/m³). Permanecer en interiores.",
        }
        return alerts[level]

    @property
    def thresholds(self):
        """Devuelve los umbrales de clasificación."""
        return {level: {'min': info['min'], 'max': info['max']}
                for level, info in self.levels.items()}
