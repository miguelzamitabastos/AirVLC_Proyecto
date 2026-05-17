import os
import requests
import time
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime, timedelta

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

# ── Estaciones de Valencia ──────────────────────────────────────────────
# 8416  → Valencia Aeropuerto (datos históricos más completos)
# 8416Y → Valencia ciudad (alternativa, puede no tener todos los años)
# 8025  → ¡Alicante! NO es Valencia (error anterior)
STATIONS_VALENCIA = {
    "8416": "Valencia Aeropuerto",
    "8416Y": "Valencia Viveros",  # Dentro de la ciudad, más cercana a las estaciones de calidad de aire
}


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
                if res_json.get('estado') == 200:
                    data_url = res_json['datos']
                    print(f"📥 Descargando datos desde: {data_url}")
                    data_response = requests.get(data_url, timeout=30)
                    if data_response.status_code == 200:
                        return data_response.json()
                    else:
                        print(f"❌ Error descargando datos finales: {data_response.status_code}")
                else:
                    desc = res_json.get('descripcion', 'Sin descripción')
                    estado = res_json.get('estado', '?')
                    print(f"⚠️ AEMET respondió (estado {estado}): {desc}")
                    # Si no hay datos para este rango, no reintentar
                    if "No hay datos" in desc:
                        return None
            elif response.status_code == 429:
                wait = 15 * (attempt + 1)
                print(f"⚠️ Rate limit (429). Esperando {wait} segundos...")
                time.sleep(wait)
            else:
                print(f"❌ Error en petición (Status {response.status_code}): {response.text[:200]}")

        except requests.exceptions.Timeout:
            print(f"⏳ Timeout en intento {attempt+1}")
        except requests.exceptions.ConnectionError:
            print(f"🔌 Error de conexión en intento {attempt+1}")
        except Exception as e:
            print(f"⚠️ Error en intento {attempt+1}: {e}")

        if attempt < retries - 1:
            wait_time = 8 * (attempt + 1)
            print(f"⏳ Reintentando en {wait_time} segundos...")
            time.sleep(wait_time)

    return None


def check_existing_data(station_id, fecha_str):
    """
    Verifica si ya existe un documento para esta estación y fecha
    para evitar duplicados.
    """
    existing = collection.find_one({
        "indicativo": station_id,
        "fecha": fecha_str
    })
    return existing is not None


def ingest_historical_meteo(station_id, start_date, end_date):
    """
    Obtiene datos climatológicos DIARIOS para una estación y rango de fechas.
    Endpoint: /api/valores/climatologicos/diarios/datos/
    start_date / end_date format: YYYY-MM-DDTHH:MM:SSUTC
    """
    url = (
        f"https://opendata.aemet.es/opendata/api/valores/climatologicos/"
        f"diarios/datos/fechaini/{start_date}/fechafin/{end_date}/"
        f"estacion/{station_id}"
    )

    data = get_aemet_data(url)

    if data:
        print(f"📊 Se han obtenido {len(data)} registros del API.")

        if len(data) > 0:
            # Filtrar duplicados antes de insertar
            new_docs = []
            skipped = 0
            for doc in data:
                if check_existing_data(station_id, doc.get('fecha', '')):
                    skipped += 1
                    continue

                # Añadimos metadatos útiles
                doc['metadata'] = {
                    'source': 'AEMET',
                    'station_id': station_id,
                    'type': 'daily',
                    'ingested_at': datetime.utcnow().isoformat()
                }
                new_docs.append(doc)

            if skipped > 0:
                print(f"⏭️ {skipped} registros ya existían (duplicados omitidos)")

            if new_docs:
                result = collection.insert_many(new_docs)
                print(f"🚀 Insertados {len(result.inserted_ids)} registros nuevos en 'meteo_historical'")
            else:
                print("ℹ️ Todos los registros de este período ya estaban insertados.")
        else:
            print("ℹ️ La respuesta de AEMET no contiene registros para este periodo.")
    else:
        print("❌ No se obtuvieron datos para este periodo.")


def bulk_ingest_range(station_id, station_name, start_year, end_year):
    """
    Realiza una ingesta masiva por bloques de 31 días
    (máximo permitido por AEMET para datos climatológicos diarios).
    """
    current_date = datetime(start_year, 1, 1)
    end_limit = datetime(end_year, 12, 31, 23, 59, 59)

    print(f"\n🚀 Iniciando INGESTA MENSUAL (Datos Diarios) para {station_name} ({station_id})")
    print(f"📅 Rango total: {start_year}-01-01 → {end_year}-12-31")
    print(f"📦 Bloques de ~31 días | Endpoint: valores/climatologicos/diarios\n")

    total_inserted = 0
    block_count = 0

    while current_date < end_limit:
        # Bloques de 31 días (máximo para datos diarios)
        next_date = current_date + timedelta(days=30, hours=23, minutes=59, seconds=59)
        if next_date > end_limit:
            next_date = end_limit

        start_str = current_date.strftime("%Y-%m-%dT%H:%M:%SUTC")
        end_str = next_date.strftime("%Y-%m-%dT%H:%M:%SUTC")

        block_count += 1
        print(f"\n{'='*60}")
        print(f"📅 Bloque {block_count}: {current_date.strftime('%Y-%m-%d')} → {next_date.strftime('%Y-%m-%d')}")

        try:
            before_count = collection.count_documents({"indicativo": station_id})
            ingest_historical_meteo(station_id, start_str, end_str)
            after_count = collection.count_documents({"indicativo": station_id})
            inserted_this_block = after_count - before_count
            total_inserted += inserted_this_block

            # Pausa entre peticiones para respetar rate-limit
            time.sleep(3)

        except Exception as e:
            print(f"❌ Fallo crítico en bloque {start_str}: {e}")
            time.sleep(15)

        current_date = current_date + timedelta(days=31)

    print(f"\n{'='*60}")
    print(f"📊 RESUMEN: {total_inserted} registros nuevos insertados para {station_name}")
    total_station = collection.count_documents({"indicativo": station_id})
    print(f"📊 Total documentos de {station_name} en MongoDB: {total_station}")


if __name__ == "__main__":
    print("="*60)
    print("  AEMET → MongoDB Atlas | Datos Climatológicos Diarios")
    print("  Proyecto AirVLC - Semana 1 Viernes")
    print("="*60)

    # Ingesta para cada estación de Valencia
    for station_id, station_name in STATIONS_VALENCIA.items():
        bulk_ingest_range(station_id, station_name, 2016, 2024)

    # Resumen final
    print("\n" + "="*60)
    print("✅ PROCESO DE INGESTA MASIVA FINALIZADO")
    total = collection.count_documents({})
    print(f"📊 Total documentos en meteo_historical: {total}")
    print("="*60)
