import json
from .aws.lex_service import LexService
import sys
import os
import numpy as np

# Asegurar que el path raíz está incluido
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from src.ml.risk_classifier import RiskClassifier
from src.api.feature_extractor import FeatureExtractor

class ChatbotOrchestrator:
    """
    Orquesta el flujo entre el usuario (App), AWS Lex y nuestros Modelos.
    """
    def __init__(self, bot_id=None, bot_alias_id=None, locale_id='es_ES'):
        self.lex_service = LexService()
        self.risk_classifier = RiskClassifier()
        # Puedes definir estos IDs en tu .env y pasarlos al instanciar
        self.bot_id = bot_id or os.environ.get('LEX_BOT_ID', 'DUMMY_BOT_ID')
        self.bot_alias_id = bot_alias_id or os.environ.get('LEX_BOT_ALIAS_ID', 'TSTALIASID')
        self.locale_id = locale_id

    def process_message(self, text, session_id, model_loader=None):
        """
        1. Llama a Lex para extraer intención y slots.
        2. Ejecuta la lógica correspondiente (ej: modelo predictivo).
        3. Devuelve la respuesta en lenguaje natural.
        """
        # --- 1. Llamada a AWS Lex ---
        try:
            lex_response = self.lex_service.recognize_text(
                bot_id=self.bot_id,
                bot_alias_id=self.bot_alias_id,
                locale_id=self.locale_id,
                text=text,
                session_id=session_id
            )
        except Exception as e:
            print(f"Error llamando a Lex: {e}")
            return {
                "reply": "Lo siento, tengo problemas conectando con mi motor NLU en AWS.",
                "intent": "Error",
                "error": str(e)
            }

        # Parsear respuesta de Lex
        interpretations = lex_response.get('interpretations', [])
        if not interpretations:
            return {"reply": "No he entendido tu mensaje.", "intent": "FallbackIntent"}

        # Lex ordena por confidence, cogemos la primera
        top_intent = interpretations[0].get('intent', {})
        intent_name = top_intent.get('name', 'FallbackIntent')
        slots = top_intent.get('slots', {})

        # --- 2. Lógica según Intención ---
        if intent_name == 'ConsultarCalidad':
            return self._handle_consultar_calidad(slots, model_loader)
        else:
            # Fallback o intención no manejada
            return {
                "reply": "Todavía no estoy entrenado para responder a esa pregunta.",
                "intent": intent_name
            }

    def _handle_consultar_calidad(self, slots, model_loader):
        """
        Maneja la intención ConsultarCalidad.
        Extrae la estación, obtiene predicción y genera texto de respuesta.
        """
        # Extraer slot de estación
        # Asumiendo que el slot se llama 'Estacion' (ajustar si es distinto en tu Lex Console)
        estacion = None
        if slots and 'Estacion' in slots and slots['Estacion'] is not None:
            estacion_slot = slots['Estacion'].get('value', {})
            estacion = estacion_slot.get('interpretedValue', estacion_slot.get('originalValue'))

        # Si no hay estación, preguntamos por ella
        if not estacion:
            return {
                "reply": "¿Para qué estación quieres consultar la calidad del aire? (ej: Valencia Viveros, Pista Silla...)",
                "intent": "ConsultarCalidad",
                "missing_slot": "Estacion"
            }

        # --- 3. Ejecutar Predicción LSTM y Clasificación de Riesgo ---
        if not model_loader or not model_loader.is_ready:
            return {
                "reply": "Mis modelos predictivos no están disponibles ahora mismo.",
                "intent": "ConsultarCalidad",
                "error": "ModelLoader not ready"
            }

        try:
            # Importar FeatureExtractor dentro de la ejecución si es necesario, o usar el instanciado
            extractor = FeatureExtractor()
            extracted_features, real_station = extractor.get_features(estacion)
            features_array = np.array(extracted_features)
            
            # Predecir con el modelo LSTM
            prediction = model_loader.predict(features_array)
            norm_value = float(prediction.flatten()[0])
            
            # Denormalizar el PM2.5 predicho
            pm25_pred = extractor.denormalize_pm25(norm_value)

            # 3.1. Obtener riesgo usando RiskClassifier
            risk_info = self.risk_classifier.classify(pm25_pred, real_station)

            # 3.2. Formatear Respuesta Natural
            risk_level = risk_info['level']
            recomendacion = risk_info['recommendation']
            emoji = risk_info['emoji']

            reply_text = (
                f"La calidad del aire esperada en {real_station} será de {pm25_pred:.1f} microgramos por metro cúbico. "
                f"Esto significa un nivel {risk_level.upper()}. {recomendacion}"
            )

            return {
                "reply": reply_text,
                "intent": "ConsultarCalidad",
                "station": estacion,
                "pm25": float(f"{pm25_pred:.2f}"),
                "risk": risk_level,
                "emoji": emoji
            }

        except Exception as e:
            print(f"Error procesando la intención: {e}")
            return {
                "reply": f"Ha ocurrido un error al calcular la predicción para {estacion}.",
                "intent": "ConsultarCalidad",
                "error": str(e)
            }
