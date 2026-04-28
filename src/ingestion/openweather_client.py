import os
import requests
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime

# Cargar variables de entorno
load_dotenv()

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

# Configuración de MongoDB
try:
    client = MongoClient(MONGO_URI)
    db = client["airvlc_db"]
    collection = db["meteo_realtime"]
    print("✅ Conectado a MongoDB Atlas (Colección: meteo_realtime)")
except Exception as e:
    print(f"❌ Error conectando a MongoDB: {e}")
    exit(1)

def get_weather_data(lat, lon):
    """
    Obtiene datos de OpenWeather One Call API 3.0.
    Incluye: Current, Minutely (1h), Hourly (48h), Daily (8 days), Alertas.
    """
    url = f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=es"
    
    print(f"🔍 Solicitando datos a OpenWeather para Lat: {lat}, Lon: {lon}...")
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        return data
    elif response.status_code == 401:
        print("❌ Error 401: API Key inválida o no activada aún (suele tardar un par de horas).")
    else:
        print(f"❌ Error en la petición (Status {response.status_code}): {response.text}")
    return None

def ingest_current_weather():
    """
    Captura el estado actual y la predicción para Valencia Ciudad.
    """
    # Coordenadas de Valencia, España
    VALENCIA_LAT = 39.4697
    VALENCIA_LON = -0.3774
    
    data = get_weather_data(VALENCIA_LAT, VALENCIA_LON)
    
    if data:
        # Añadir timestamp de ingesta
        data['ingested_at'] = datetime.utcnow().isoformat()
        data['city'] = "Valencia"
        
        # Insertar en MongoDB
        # Usamos update_one con upsert=True si queremos mantener solo el "último estado" 
        # o insert_one si queremos un histórico de consultas de tiempo real.
        # Para el proyecto, un histórico de consultas es mejor para analítica.
        result = collection.insert_one(data)
        print(f"🚀 Datos de tiempo real + predicción insertados. ID: {result.inserted_id}")
        
        # Mostrar resumen
        current = data.get('current', {})
        print(f"\n--- Resumen Valencia ({datetime.now().strftime('%H:%M:%S')}) ---")
        print(f"🌡️ Temperatura: {current.get('temp')}°C")
        print(f"💧 Humedad: {current.get('humidity')}%")
        print(f"☁️ Estado: {current.get('weather', [{}])[0].get('description')}")
        print(f"🔮 Predicción próxima hora: {data.get('hourly', [{}])[1].get('temp')}°C")
    else:
        print("❌ No se pudieron obtener los datos de OpenWeather.")

if __name__ == "__main__":
    ingest_current_weather()
