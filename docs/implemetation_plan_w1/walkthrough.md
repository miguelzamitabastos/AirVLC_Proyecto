# Walkthrough: Fix AEMET Historical Data Ingestion

## Problema
El script `aemet_client.py` no podía descargar datos históricos de AEMET por dos errores:
1. **Estación incorrecta**: `8025` = Alicante, no Valencia
2. **Endpoint incorrecto**: `horarios` no tiene datos históricos desde 2016

## Cambios realizados

### [MODIFY] [aemet_client.py](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/src/ingestion/aemet_client.py)

```diff:aemet_client.py
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
===
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

```

**Cambios clave:**
| Antes | Después |
|---|---|
| Estación `8025` (Alicante) | Estación `8416` (Valencia Aeropuerto) |
| Endpoint `horarios` | Endpoint `diarios` |
| Bloques de 7 días | Bloques de 31 días |
| Sin detección de duplicados | Verificación por `indicativo` + `fecha` |
| Reintento simple | Rate-limit progresivo + early exit si "No hay datos" |

### [NEW] [verify_mongodb.py](file:///Users/miguel/Desktop/Curso%20IA/Propuesta%20Proyecto/AirVLCProyecto/src/ingestion/verify_mongodb.py)

Script de verificación que muestra el estado de las colecciones en MongoDB Atlas: estaciones, rangos de fechas, conteos, y tipos de datos.

## Resultado de la ingesta

| Métrica | Valor |
|---|---|
| Registros Valencia insertados | **3.288** |
| Rango de fechas | `2016-01-01` → `2024-12-31` |
| Bloques procesados | 107 |
| Errores recuperados | 2 (1 rate-limit, 1 server error 500) |
| Tiempo total | ~12 minutos |

## Estado final MongoDB Atlas

```
meteo_historical: 3.685 documentos total
├── VALÈNCIA (8416):           3.288 docs (2016-01-01 → 2024-12-31)  ← NUEVO
└── ALACANT/ALICANTE (8025):    397 docs (2016-01-01 → 2024-01-31)  ← anterior

meteo_realtime: 6 documentos (OpenWeather)
test_collection: 4 documentos
```

> [!NOTE]
> Los 397 documentos de Alicante siguen en la colección. Se pueden eliminar o mover a una colección separada según lo que Miguel decida.

## Estrategia de datos recomendada

| BD | Datos | Estado |
|---|---|---|
| PostgreSQL | CSVs calidad aire + GeoJSON + ruido + emisiones | ✅ Hecho |
| MongoDB | Meteo AEMET histórico + OpenWeather real-time | ✅ Hecho |
| Elasticsearch | Calidad aire (vía Logstash) | ✅ Hecho |

> [!TIP]
> No es necesario duplicar los CSVs en MongoDB. Cada BD tiene su rol específico en la arquitectura del proyecto.
