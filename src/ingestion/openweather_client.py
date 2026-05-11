import os
import requests
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime

# Cargar variables de entorno
# `override=True` evita que una OPENWEATHER_API_KEY exportada en la shell
# (posiblemente antigua) tenga prioridad sobre el valor actualizado en `.env`.
load_dotenv(override=True)

def _get_openweather_api_key() -> str:
    key = (
        os.getenv("OPENWEATHER_API_KEY")
        or os.getenv("OPENWEATHER_KEY")
        or os.getenv("OWM_API_KEY")
    )
    if not key:
        raise RuntimeError(
            "OPENWEATHER_API_KEY no configurada. "
            "Añádela en tu `.env` o exporta la variable de entorno."
        )
    return key


def _get_collection():
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise RuntimeError("MONGO_URI no configurado en `.env`/env.")
    client = MongoClient(mongo_uri)
    db = client["airvlc_db"]
    return client, db["meteo_realtime"]

def _fingerprint_key(key: str) -> str:
    """Devuelve huella segura (no secreta) para depuración."""
    if not key:
        return "empty"
    return f"len={len(key)}...{key[-4:]}"

def get_weather_data(lat, lon):
    """
    Obtiene meteo de OpenWeather.

    Estrategia:
    - Usar primero Current Weather API 2.5 (es la más compatible con planes free).
    - Intentar One Call API 3.0 solo si 2.5 funciona y se desea más granularidad.
    """
    api_key = _get_openweather_api_key()
    print(f"   🔑 OpenWeather key fingerprint: {_fingerprint_key(api_key)}")
    
    print(f"🔍 Solicitando datos a OpenWeather para Lat: {lat}, Lon: {lon}...")
    url_current = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric&lang=es"
    response = requests.get(url_current, timeout=30)
    
    if response.status_code == 200:
        raw = response.json()
        current = {
            "temp": (raw.get("main") or {}).get("temp"),
            "humidity": (raw.get("main") or {}).get("humidity"),
            "wind_speed": (raw.get("wind") or {}).get("speed"),
            "weather": raw.get("weather") or [],
        }
        if isinstance(raw.get("rain"), dict):
            current["rain"] = raw.get("rain")
        data = {
            "current": current,
            "hourly": [],
            "_airvlc_source": "openweather_current_2_5",
        }
        return data
    elif response.status_code in (401, 403):
        raise RuntimeError(
            f"OpenWeather Current 2.5 HTTP {response.status_code}: {response.text[:200]}"
        )
    else:
        raise RuntimeError(
            f"OpenWeather error HTTP {response.status_code}: {response.text[:300]}"
        )

def ingest_current_weather():
    """
    Captura el estado actual y la predicción para Valencia Ciudad.
    """
    # Coordenadas de Valencia, España
    VALENCIA_LAT = 39.4697
    VALENCIA_LON = -0.3774
    
    data = get_weather_data(VALENCIA_LAT, VALENCIA_LON)

    # Añadir timestamp de ingesta
    data["ingested_at"] = datetime.utcnow().isoformat()
    data["city"] = "Valencia"

    client, collection = _get_collection()
    try:
        result = collection.insert_one(data)
    finally:
        client.close()

    print(f"🚀 Datos de tiempo real + predicción insertados. ID: {result.inserted_id}")

    # Mostrar resumen
    current = data.get("current", {})
    print(f"\n--- Resumen Valencia ({datetime.now().strftime('%H:%M:%S')}) ---")
    print(f"🌡️ Temperatura: {current.get('temp')}°C")
    print(f"💧 Humedad: {current.get('humidity')}%")
    print(f"☁️ Estado: {current.get('weather', [{}])[0].get('description')}")
    hourly = data.get("hourly") or []
    next_hour = hourly[1] if isinstance(hourly, list) and len(hourly) > 1 else {}
    if isinstance(next_hour, dict) and "temp" in next_hour:
        print(f"🔮 Predicción próxima hora: {next_hour.get('temp')}°C")
    else:
        print("🔮 Predicción próxima hora: (no disponible en este endpoint)")

    return {"ok": True, "inserted_id": str(result.inserted_id)}

if __name__ == "__main__":
    ingest_current_weather()
