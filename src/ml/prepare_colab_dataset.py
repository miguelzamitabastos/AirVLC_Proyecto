import os
import pandas as pd
import numpy as np
import psycopg2
import pymongo
from dotenv import load_dotenv

# Setup
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432')
POSTGRES_USER = os.getenv('POSTGRES_USER')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
POSTGRES_DB = os.getenv('POSTGRES_DB')
MONGO_URI = os.getenv('MONGO_URI')

STATION_ID_MONGO = '8416Y' # Usamos la de Viveros como representativa del clima de la ciudad

def get_postgres_data():
    print("Conectando a PostgreSQL para extraer TODAS las estaciones...")
    conn = psycopg2.connect(
        host=POSTGRES_HOST, port=POSTGRES_PORT,
        user=POSTGRES_USER, password=POSTGRES_PASSWORD, dbname=POSTGRES_DB
    )
    query = """
        SELECT e.nombre as estacion, m.fecha, m.pm25, m.no2, m.o3 
        FROM mediciones_aire m
        JOIN estaciones e ON m.estacion_id = e.id
        ORDER BY e.nombre, m.fecha ASC
    """
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def clean_aemet_value(val):
    if pd.isna(val):
        return np.nan
    if isinstance(val, str):
        val = val.replace(',', '.')
    try:
        return float(val)
    except ValueError:
        return np.nan

def get_mongodb_data():
    print("Conectando a MongoDB para extraer datos climáticos...")
    client = pymongo.MongoClient(MONGO_URI)
    db = client['airvlc_db']
    cursor = db['meteo_historical'].find({'indicativo': STATION_ID_MONGO})
    
    records = []
    for doc in cursor:
        records.append({
            'fecha_diaria': doc.get('fecha'),
            'temperatura': clean_aemet_value(doc.get('tmed')),
            'velocidad_viento': clean_aemet_value(doc.get('velmedia')),
            'precipitacion': clean_aemet_value(doc.get('prec')),
            'humedad_relativa': clean_aemet_value(doc.get('hrMedia'))
        })
    df = pd.DataFrame(records)
    return df

def main():
    df_pg = get_postgres_data()
    df_pg['fecha'] = pd.to_datetime(df_pg['fecha'])
    df_pg['date'] = df_pg['fecha'].dt.date
    
    df_mongo = get_mongodb_data()
    df_mongo['date'] = pd.to_datetime(df_mongo['fecha_diaria']).dt.date
    df_mongo.drop(columns=['fecha_diaria'], inplace=True)
    
    print("Fusionando datasets...")
    df_master = pd.merge(df_pg, df_mongo, on='date', how='left')
    df_master.drop(columns=['date'], inplace=True)
    df_master.sort_values(['estacion', 'fecha'], inplace=True)
    df_master.reset_index(drop=True, inplace=True)
    
    print("Limpiando e interpolando por estación...")
    cols_to_interpolate = ['pm25', 'no2', 'o3', 'temperatura', 'velocidad_viento', 'precipitacion', 'humedad_relativa']
    
    for col in cols_to_interpolate:
        df_master[col] = pd.to_numeric(df_master[col], errors='coerce')
        
    # Interpolamos pero limitando al grupo (estación) para no cruzar datos entre estaciones
    df_master[cols_to_interpolate] = df_master.groupby('estacion')[cols_to_interpolate].transform(lambda group: group.interpolate(method='linear', limit=24))
    
    # Eliminamos las filas que sigan teniendo NaNs (esto eliminará estaciones sin datos de PM25 como Viveros)
    df_master.dropna(inplace=True)
    
    # Capping outliers
    for col in ['pm25', 'no2', 'o3']:
        upper_limit = df_master[col].quantile(0.999)
        df_master.loc[df_master[col] > upper_limit, col] = upper_limit

    print("Feature Engineering por estación...")
    df_master['hora_del_dia'] = df_master['fecha'].dt.hour
    df_master['dia_de_la_semana'] = df_master['fecha'].dt.dayofweek
    
    # Retardos y medias agrupados por estación
    df_master['pm25_lag1'] = df_master.groupby('estacion')['pm25'].shift(1)
    df_master['pm25_lag2'] = df_master.groupby('estacion')['pm25'].shift(2)
    df_master['pm25_lag3'] = df_master.groupby('estacion')['pm25'].shift(3)
    df_master['pm25_rolling_6h'] = df_master.groupby('estacion')['pm25'].transform(lambda x: x.rolling(window=6).mean())
    
    df_master.dropna(inplace=True)
    
    print("One-Hot Encoding para las estaciones...")
    # Guardamos una copia del nombre de estación para crear las secuencias después en el notebook
    df_master['station_name'] = df_master['estacion']
    df_master = pd.get_dummies(df_master, columns=['estacion'], prefix='station')
    
    df_master.set_index('fecha', inplace=True)
    
    # NOTA: La normalización (MinMaxScaler) se ha movido al notebook de Colab
    # para que el usuario tenga control total del pipeline y pueda hacer
    # inverse_transform para evaluar predicciones en valores reales.
    # El dataset se guarda limpio, interpolado y con feature engineering,
    # pero en escala original (sin normalizar).
    
    out_path = os.path.join(PROJECT_ROOT, 'data/processed/master_dataset_colab.csv')
    df_master.to_csv(out_path)
    
    print(f"✅ ¡Éxito! Dataset completo para Colab guardado (sin normalizar). Shape: {df_master.shape}")
    print(f"Estaciones incluidas: {df_master['station_name'].unique()}")

if __name__ == '__main__':
    main()
