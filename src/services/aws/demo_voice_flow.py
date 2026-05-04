"""
===================================================================
🎙️ Demo Completa: Flujo de Voz AirVLC
===================================================================
Flujo end-to-end:
  1. ASR  — Graba tu voz desde el micrófono y la transcribe (AWS Transcribe Streaming)
  2. NLU  — Envía el texto a Amazon Lex para identificar intención + slots
  3. IA   — Ejecuta la predicción con el modelo LSTM + RiskClassifier
  4. TTS  — Convierte la respuesta en audio con AWS Polly

Ejecución:
  cd <project_root>
  python -m src.services.aws.demo_voice_flow

Requisitos:
  pip install sounddevice soundfile amazon-transcribe boto3
===================================================================
"""

import os
import sys
import time
import uuid
import wave
import struct
import asyncio
import subprocess
import requests
import json

# --- Path Setup ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)

import sounddevice as sd
import soundfile as sf
import numpy as np

from src.services.aws.config import AWSConfig
from src.services.aws.polly_service import PollyService
from src.services.aws.lex_service import LexService
from src.ml.risk_classifier import RiskClassifier


# =============================================
# Configuración
# =============================================
SAMPLE_RATE = 16000       # Hz (lo que espera Transcribe)
CHANNELS = 1              # Mono
RECORD_SECONDS = 6        # Duración máxima de grabación
AUDIO_DIR = os.path.join(project_root, 'src', 'services', 'aws', 'tests')

# IDs de tu Bot Lex — actualízalos con tus valores reales
LEX_BOT_ID = os.environ.get('LEX_BOT_ID', '')
LEX_BOT_ALIAS_ID = os.environ.get('LEX_BOT_ALIAS_ID', 'TSTALIASID')
LEX_LOCALE_ID = 'es_ES'


# =============================================
# PASO 1: ASR — Grabar y Transcribir
# =============================================
def record_audio(duration=RECORD_SECONDS, filename='user_query.wav'):
    """Graba audio desde el micrófono del Mac."""
    filepath = os.path.join(AUDIO_DIR, filename)
    os.makedirs(AUDIO_DIR, exist_ok=True)

    print(f"\n🎙️  Habla ahora... ({duration} segundos)")
    print("   Ejemplo: 'Dime la calidad del aire en la pista de silla'")
    print("   " + "▓" * 40)

    # Grabar audio
    audio_data = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype='int16'
    )
    sd.wait()  # Esperar a que termine la grabación

    print("   ✅ Grabación completada.")

    # Guardar como WAV
    sf.write(filepath, audio_data, SAMPLE_RATE, subtype='PCM_16')
    print(f"   💾 Audio guardado en: {filepath}")
    return filepath


def transcribe_audio_streaming(audio_path):
    """
    Transcribe audio usando AWS Transcribe Streaming SDK.
    Envía el audio directamente sin necesitar S3.
    """
    from amazon_transcribe.client import TranscribeStreamingClient
    from amazon_transcribe.handlers import TranscriptResultStreamHandler
    from amazon_transcribe.model import TranscriptEvent

    print("\n📝 PASO 1: ASR — Transcribiendo audio con AWS Transcribe Streaming...")

    # Leer credenciales
    creds = AWSConfig.get_credentials()

    # Variable para almacenar la transcripción final
    final_transcript = []

    class MyEventHandler(TranscriptResultStreamHandler):
        async def handle_transcript_event(self, transcript_event: TranscriptEvent):
            results = transcript_event.transcript.results
            for result in results:
                if not result.is_partial:
                    for alt in result.alternatives:
                        final_transcript.append(alt.transcript)

    async def _stream_audio():
        client = TranscribeStreamingClient(region=creds['region_name'])

        stream = await client.start_stream_transcription(
            language_code='es-ES',
            media_sample_rate_hz=SAMPLE_RATE,
            media_encoding='pcm',
        )

        handler = MyEventHandler(stream.output_stream)

        # Leer el archivo WAV y enviar chunks
        with open(audio_path, 'rb') as f:
            # Saltar cabecera WAV (44 bytes)
            f.read(44)
            while True:
                chunk = f.read(SAMPLE_RATE * 2)  # 1 segundo de audio (16-bit = 2 bytes)
                if not chunk:
                    break
                await stream.input_stream.send_audio_event(audio_chunk=chunk)

        await stream.input_stream.end_stream()
        await handler.handle_events()

    # Ejecutar el streaming
    asyncio.run(_stream_audio())

    transcript = ' '.join(final_transcript).strip()
    if transcript:
        print(f"   ✅ Transcripción: \"{transcript}\"")
    else:
        print("   ⚠️  No se pudo transcribir el audio. ¿Hablaste lo suficientemente alto?")
    return transcript


def transcribe_audio_batch(audio_path):
    """
    Alternativa: Transcribe via el servicio batch estándar (necesita S3).
    Usaremos Lex directamente con recognize_text como fallback.
    """
    print("\n📝 PASO 1 (Fallback): Usando transcripción manual...")
    print("   (El servicio batch de Transcribe necesita un bucket S3)")
    text = input("   ✏️  Escribe tu pregunta manualmente: ").strip()
    return text


# =============================================
# PASO 2: NLU — Amazon Lex
# =============================================
def process_with_lex(text, session_id=None):
    """Envía el texto a Amazon Lex y extrae intención + slots."""
    print(f"\n🧠 PASO 2: NLU — Enviando a Amazon Lex...")
    print(f"   Texto: \"{text}\"")

    lex = LexService()

    if not LEX_BOT_ID:
        print("   ⚠️  LEX_BOT_ID no configurado en .env")
        print("   Necesitas añadir LEX_BOT_ID y LEX_BOT_ALIAS_ID a tu .env")
        return None, None, None

    response = lex.recognize_text(
        bot_id=LEX_BOT_ID,
        bot_alias_id=LEX_BOT_ALIAS_ID,
        locale_id=LEX_LOCALE_ID,
        text=text,
        session_id=session_id
    )

    interpretations = response.get('interpretations', [])
    if not interpretations:
        print("   ❌ Lex no pudo interpretar el mensaje.")
        return 'FallbackIntent', {}, response

    top = interpretations[0].get('intent', {})
    intent_name = top.get('name', 'FallbackIntent')
    slots = top.get('slots', {})
    confidence = interpretations[0].get('nluConfidence', {}).get('score', 0)

    print(f"   ✅ Intención: {intent_name} (confianza: {confidence:.2f})")

    # Extraer slots
    parsed_slots = {}
    for slot_name, slot_data in slots.items():
        if slot_data and slot_data.get('value'):
            val = slot_data['value'].get('interpretedValue', slot_data['value'].get('originalValue', ''))
            parsed_slots[slot_name] = val
            print(f"   📌 Slot '{slot_name}': {val}")

    if not parsed_slots:
        print("   ℹ️  No se detectaron slots (estación no especificada)")

    return intent_name, parsed_slots, response


# =============================================
# PASO 3: Predicción IA
# =============================================
def run_prediction(intent_name, slots):
    """Ejecuta la predicción según la intención detectada."""
    print(f"\n🤖 PASO 3: Predicción IA...")

    if intent_name != 'ConsultarCalidad':
        reply = "No tengo entrenada esa intención todavía."
        print(f"   ℹ️  {reply}")
        return reply, {}

    estacion = slots.get('Estacion', 'Valencia (general)')
    print(f"   📍 Estación: {estacion}")

    # En lugar de simulación, llamamos al endpoint local que aloja el modelo real (LSTM_Attention).
    # La API local ahora usa el FeatureExtractor para buscar las últimas 24h reales
    # de esta estación en el dataset y las procesa automáticamente.
    try:
        api_response = requests.post(
            'http://localhost:5001/api/risk',
            json={
                "station": estacion,
                "model": "LSTM_Attention"
            },
            timeout=5
        )
        api_response.raise_for_status()
        risk_data = api_response.json()
        
        pm25_pred = risk_data['pm25_value']
        level = risk_data['risk_level'].upper()
        emoji = risk_data['emoji']
        recommendation = risk_data['recommendation']
        
        print(f"   📊 Predicción PM2.5 (Modelo LSTM_Attention): {pm25_pred:.1f} µg/m³")
        print(f"   ✅ Nivel: {level} {emoji}")
        
        reply = (
            f"La calidad del aire en {estacion} se espera con un valor de "
            f"{pm25_pred:.1f} microgramos por metro cúbico de PM2.5. "
            f"Esto corresponde a un nivel {level}. "
            f"{recommendation}"
        )
        print(f"   💬 Respuesta: {reply[:80]}...")
        
        return reply, risk_data
        
    except Exception as e:
        print(f"   ⚠️ Error contactando con la API local: {e}")
        print("   (Asegúrate de que 'python src/api/app.py' está corriendo)")
        reply = f"No he podido contactar con mi motor de predicción neuronal para {estacion}."
        return reply, {}


# =============================================
# PASO 4: TTS — AWS Polly
# =============================================
def speak_response(text, filename='response_audio.mp3'):
    """Convierte texto a voz con AWS Polly y lo reproduce."""
    print(f"\n🔊 PASO 4: TTS — Generando audio con AWS Polly...")

    filepath = os.path.join(AUDIO_DIR, filename)
    polly = PollyService()
    polly.synthesize_speech(text, filepath, voice_id='Lucia', engine='neural')

    print(f"   ✅ Audio generado: {filepath}")

    # Reproducir audio en macOS
    print("   ▶️  Reproduciendo respuesta...")
    try:
        subprocess.run(['afplay', filepath], check=True)
        print("   ✅ Reproducción completada.")
    except FileNotFoundError:
        print("   ⚠️  No se pudo reproducir automáticamente. Abre el archivo manualmente.")
    except Exception as e:
        print(f"   ⚠️  Error reproduciendo: {e}")

    return filepath


# =============================================
# FLUJO PRINCIPAL
# =============================================
def run_demo(use_voice=True):
    """
    Ejecuta el flujo completo:
    ASR (micrófono) → NLU (Lex) → Predicción (LSTM/RiskClassifier) → TTS (Polly)
    """
    print("\n" + "=" * 60)
    print("🌐 AirVLC — Demo de Asistente de Voz")
    print("=" * 60)
    print("Flujo: 🎙️ ASR → 🧠 NLU → 🤖 IA → 🔊 TTS")
    print("=" * 60)

    # --- PASO 1: ASR ---
    if use_voice:
        audio_path = record_audio()
        try:
            user_text = transcribe_audio_streaming(audio_path)
        except Exception as e:
            print(f"\n   ⚠️  Error en Transcribe Streaming: {e}")
            print("   Usando entrada manual como fallback...")
            user_text = transcribe_audio_batch(audio_path)
    else:
        user_text = transcribe_audio_batch(None)

    if not user_text:
        print("\n❌ No se obtuvo texto. Finalizando demo.")
        return

    # --- PASO 2: NLU ---
    try:
        # Generar session_id único para que Lex no arrastre slots de conversaciones anteriores
        session_id = f"demo-{uuid.uuid4().hex[:8]}"
        intent, slots, lex_raw = process_with_lex(user_text, session_id=session_id)
    except Exception as e:
        print(f"\n   ❌ Error en Lex: {e}")
        print("   Usando intención manual como fallback...")
        intent = 'ConsultarCalidad'
        slots = {}

    if not intent or intent == 'FallbackIntent':
        reply = "No he podido entender tu consulta. ¿Puedes reformularla?"
    else:
        # --- PASO 3: Predicción ---
        reply, risk_data = run_prediction(intent, slots)

    # --- PASO 4: TTS ---
    speak_response(reply)

    # --- Resumen ---
    print("\n" + "=" * 60)
    print("📋 RESUMEN DEL FLUJO")
    print("=" * 60)
    print(f"  🎙️  ASR Input:   \"{user_text}\"")
    print(f"  🧠  Intención:   {intent}")
    print(f"  📌  Slots:       {slots}")
    print(f"  🔊  Respuesta:   \"{reply[:100]}...\"")
    print("=" * 60 + "\n")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='AirVLC Voice Assistant Demo')
    parser.add_argument('--text', action='store_true',
                        help='Usar entrada de texto en vez de micrófono')
    args = parser.parse_args()

    run_demo(use_voice=not args.text)
