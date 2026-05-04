"""
===================================================================
🔌 ES Indexer — Indexación de Predicciones en Elasticsearch
===================================================================
Módulo dedicado para la conexión API → Elasticsearch.
Indexa cada predicción/clasificación de riesgo en el índice
'airvlc-predictions' para alimentar los dashboards de Kibana.

Uso:
    from src.api.es_indexer import ESIndexer

    indexer = ESIndexer()
    indexer.index_prediction({
        'pm25_predicted': 15.3,
        'station': 'Viveros',
        'risk_level': 'moderado',
        ...
    })

Diseño:
    - Fail-safe: si ES no está disponible, la API sigue funcionando
    - Async-ready: no bloquea el response de la API
    - Configurable vía variables de entorno
===================================================================
"""

import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Coordenadas de las estaciones de Valencia para enriquecer predicciones
STATION_COORDS = {
    'Avda. Francia': {'lat': 39.4578, 'lon': -0.343},
    'Francia': {'lat': 39.4578, 'lon': -0.343},
    'Bulevard Sud': {'lat': 39.4504, 'lon': -0.3963},
    'Boulevar Sur': {'lat': 39.4504, 'lon': -0.3963},
    'Molí del Sol': {'lat': 39.4811, 'lon': -0.4088},
    'Pista Silla': {'lat': 39.4581, 'lon': -0.3766},
    'Pista de Silla': {'lat': 39.4581, 'lon': -0.3766},
    'Politécnico': {'lat': 39.4796, 'lon': -0.3374},
    'Universidad Politécnica': {'lat': 39.4796, 'lon': -0.3374},
    'Viveros': {'lat': 39.4796, 'lon': -0.3696},
    'Valencia Centro': {'lat': 39.4705, 'lon': -0.3764},
    'Centro': {'lat': 39.4705, 'lon': -0.3764},
    'Consellería Meteo': {'lat': 39.4692, 'lon': -0.4059},
    'Nazaret Meteo': {'lat': 39.4667, 'lon': -0.3283},
    'Puerto Valencia': {'lat': 39.4484, 'lon': -0.3172},
    'Puerto Moll Trans. Ponent': {'lat': 39.4470, 'lon': -0.3200},
    'Puerto llit antic Túria': {'lat': 39.4560, 'lon': -0.3300},
    'Patraix': {'lat': 39.4592, 'lon': -0.4014},
}


class ESIndexer:
    """
    Indexador de predicciones en Elasticsearch.
    Diseñado para ser fail-safe: si ES no está disponible,
    la API sigue funcionando normalmente.
    """

    def __init__(self, es_host=None, index_name='airvlc-predictions'):
        """
        Args:
            es_host: URL de Elasticsearch (default: localhost:9200)
            index_name: Nombre del índice de predicciones
        """
        self.es_host = es_host or os.environ.get('ES_HOST', 'http://localhost:9200')
        self.index_name = index_name
        self.enabled = True
        self._es_client = None

        self._init_client()

    def _init_client(self):
        """Inicializa el cliente de Elasticsearch."""
        try:
            from elasticsearch import Elasticsearch
            self._es_client = Elasticsearch(self.es_host)
            # Verificar conexión
            if self._es_client.ping():
                logger.info(f"✅ ESIndexer conectado a {self.es_host}")
            else:
                logger.warning(f"⚠️ ES no responde en {self.es_host}. Indexación deshabilitada.")
                self.enabled = False
        except ImportError:
            logger.warning("⚠️ elasticsearch-py no instalado. Indexación deshabilitada.")
            self.enabled = False
        except Exception as e:
            logger.warning(f"⚠️ Error conectando a ES: {e}. Indexación deshabilitada.")
            self.enabled = False

    def index_prediction(self, prediction_data):
        """
        Indexa un resultado de predicción en ES.

        Args:
            prediction_data: dict con los campos de la predicción:
                - pm25_predicted (float): valor predicho
                - pm25_actual (float, optional): valor real
                - station (str, optional): nombre de la estación
                - risk_level (str): nivel de riesgo
                - risk_color (str): color del nivel
                - alert_text (str): texto de alerta
                - model_used (str): modelo utilizado
                - extra context fields...

        Returns:
            bool: True si se indexó correctamente, False en caso contrario
        """
        if not self.enabled or not self._es_client:
            return False

        try:
            doc = self._build_document(prediction_data)
            self._es_client.index(index=self.index_name, document=doc)
            return True
        except Exception as e:
            logger.warning(f"⚠️ Error indexando predicción: {e}")
            return False

    def _build_document(self, data):
        """Construye el documento ES a partir de los datos de predicción."""
        pm25_pred = data.get('pm25_predicted', data.get('prediction_pm25'))
        pm25_actual = data.get('pm25_actual')
        station = data.get('station')

        doc = {
            '@timestamp': data.get('@timestamp', data.get('timestamp', datetime.utcnow().isoformat())),
            'pm25_predicted': pm25_pred,
            'model_used': data.get('model_used', 'unknown'),
            'risk_level': data.get('risk_level', data.get('level')),
            'risk_color': data.get('risk_color', data.get('color')),
            'risk_emoji': data.get('risk_emoji', data.get('emoji')),
            'alert_text': data.get('alert_text'),
            'station': station,
            'source': data.get('source', 'api'),
            'prediction_type': data.get('prediction_type', 'realtime'),
        }

        # Añadir valor real y residual si disponible
        if pm25_actual is not None:
            doc['pm25_actual'] = pm25_actual
            doc['residual'] = pm25_pred - pm25_actual
            doc['absolute_error'] = abs(pm25_pred - pm25_actual)

        # Añadir coordenadas de la estación
        if station and station in STATION_COORDS:
            doc['location'] = STATION_COORDS[station]

        # Añadir contexto meteorológico si disponible
        for field in ['no2', 'o3', 'temperatura', 'velocidad_viento',
                       'precipitacion', 'humedad_relativa',
                       'hora_del_dia', 'dia_de_la_semana']:
            if field in data:
                doc[field] = data[field]

        return doc

    def index_bulk(self, predictions, chunk_size=500):
        """
        Indexa un lote de predicciones eficientemente.

        Args:
            predictions: lista de dicts con datos de predicción
            chunk_size: tamaño de cada batch para bulk

        Returns:
            tuple: (indexados, errores)
        """
        if not self.enabled or not self._es_client:
            return 0, len(predictions)

        try:
            from elasticsearch.helpers import bulk

            actions = []
            for pred in predictions:
                doc = self._build_document(pred)
                actions.append({
                    '_index': self.index_name,
                    '_source': doc
                })

            success, errors = bulk(
                self._es_client,
                actions,
                chunk_size=chunk_size,
                raise_on_error=False
            )
            return success, errors if isinstance(errors, int) else len(errors)
        except Exception as e:
            logger.error(f"❌ Error en bulk indexing: {e}")
            return 0, len(predictions)

    @property
    def is_connected(self):
        """True si la conexión a ES está activa."""
        if not self._es_client:
            return False
        try:
            return self._es_client.ping()
        except Exception:
            return False
