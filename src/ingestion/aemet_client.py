import os
import requests
import time
from pymongo import MongoClient
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

AEMET_API_KEY = os.getenv("AEMET_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

# Configuración de MongoDB
try:
    client = MongoClient(MONGO_URI)
    # Verificamos la conexión
    client.admin.command('ping')
    db = client["airvlc_db"]
    collection = db["meteo_historical"]
    print("✅ Conectado exitosamente a MongoDB Atlas")
except Exception as e:
    print(f"❌ Error conectando a MongoDB: {e}")
    exit(1)

def get_aemet_data(endpoint_url, retries=3):
    """
    Realiza la petición a AEMET con lógica de reintentos en dos pasos:
    1. Obtener la URL de descarga (metadatos).
    2. Descargar los datos finales desde la URL proporcionada.
    """
    headers = {
        'cache-control': "no-cache",
        'api_key': AEMET_API_KEY
    }
    
    for attempt in range(retries):
        try:
            print(f"🔍 Solicitando acceso a AEMET (Intento {attempt+1}): {endpoint_url}")
            response = requests.get(endpoint_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                res_json = response.json()
                if res_json['estado'] == 200:
                    data_url = res_json['datos']
                    print(f"📥 Descargando datos desde: {data_url}")
                    data_response = requests.get(data_url, timeout=30)
                    if data_response.status_code == 200:
                        return data_response.json()
                    else:
                        print(f"❌ Error descargando datos finales: {data_response.status_code}")
                else:
                    print(f"⚠️ AEMET respondió con error: {res_json.get('descripcion', 'Sin descripción')}")
            elif response.status_code == 429:
                print("⚠️ Demasiadas peticiones (Rate limit). Esperando 10 segundos...")
                time.sleep(10)
            else:
                print(f"❌ Error en la petición inicial (Status {response.status_code})")
        
        except Exception as e:
            print(f"⚠️ Error en intento {attempt+1}: {e}")
        
        if attempt < retries - 1:
            wait_time = 5 * (attempt + 1)
            print(f"⏳ Reintentando en {wait_time} segundos...")
            time.sleep(wait_time)
            
    return None

def ingest_historical_meteo(station_id, start_date, end_date, hourly=False):
    """
    Obtiene datos climatológicos (diarios o horarios) para una estación y rango de fechas.
    start_date / end_date format: YYYY-MM-DDTHH:MM:SSUTC
    """
    if hourly:
        # Nota: La API de AEMET para horarios suele tener límites de tiempo más cortos por petición
        url = f"https://opendata.aemet.es/opendata/api/valores/climatologicos/horarios/datos/fechaini/{start_date}/fechafin/{end_date}/estacion/{station_id}"
    else:
        url = f"https://opendata.aemet.es/opendata/api/valores/climatologicos/diarios/datos/fechaini/{start_date}/fechafin/{end_date}/estacion/{station_id}"
    
    data = get_aemet_data(url)
    
    if data:
        print(f"📊 Se han obtenido {len(data)} registros.")
        if len(data) > 0:
            # Añadimos metadatos útiles
            for doc in data:
                doc['metadata'] = {
                    'source': 'AEMET',
                    'station_id': station_id,
                    'type': 'hourly' if hourly else 'daily'
                }
            
            result = collection.insert_many(data)
            print(f"🚀 Insertados {len(result.inserted_ids)} registros en la colección 'meteo_historical' de MongoDB.")
        else:
            print("ℹ️ La respuesta de AEMET no contiene registros para este periodo.")
    else:
        print("❌ No se pudieron procesar los datos.")

from datetime import datetime, timedelta

def bulk_ingest_range(station_id, start_year, end_year):
    """
    Realiza una ingesta masiva por bloques de 7 días (máximo permitido por AEMET para datos horarios).
    """
    current_date = datetime(start_year, 1, 1)
    end_limit = datetime(end_year, 12, 31, 23, 59, 59)
    
    print(f"🚀 Iniciando INGESTA SEMANAL (Límite AEMET Horario) para {start_year}-{end_year}")
    
    while current_date < end_limit:
        next_date = current_date + timedelta(days=6, hours=23, minutes=59, seconds=59)
        if next_date > end_limit:
            next_date = end_limit
            
        start_str = current_date.strftime("%Y-%m-%dT%H:%M:%SUTC")
        end_str = next_date.strftime("%Y-%m-%dT%H:%M:%SUTC")
        
        print(f"\n📅 Período: {start_str} -> {end_str}")
        
        try:
            ingest_historical_meteo(station_id, start_str, end_str, hourly=True)
            # Espera más larga entre semanas para evitar bloqueos
            time.sleep(5)
        except Exception as e:
            print(f"❌ Fallo crítico en el bloque {start_str}: {e}")
            time.sleep(10)
            
        current_date = current_date + timedelta(days=7)

if __name__ == "__main__":
    # Estación Valencia Viveros
    STATION_VALENCIA = "8025"
    
    # Ingesta masiva desde 2016 hasta 2024 (Semana a Semana)
    bulk_ingest_range(STATION_VALENCIA, 2016, 2024)
    print("\n✅ PROCESO DE INGESTA MASIVA FINALIZADO")
