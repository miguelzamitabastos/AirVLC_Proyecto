import os
import pandas as pd
import numpy as np
import psycopg2
import pymongo
from dotenv import load_dotenv
from sklearn.preprocessing import MinMaxScaler
import joblib

# Setup
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432')
POSTGRES_USER = os.getenv('POSTGRES_USER')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
POSTGRES_DB = os.getenv('POSTGRES_DB')
MONGO_URI = os.getenv('MONGO_URI')

STATION_NAME_PG = 'Pista de Silla'
STATION_ID_MONGO = '8416Y'

def get_postgres_data():
    """Extracts hourly air quality data from PostgreSQL."""
    conn = psycopg2.connect(
        host=POSTGRES_HOST, port=POSTGRES_PORT,
        user=POSTGRES_USER, password=POSTGRES_PASSWORD, dbname=POSTGRES_DB
    )
    query = f"""
        SELECT m.fecha, m.pm25, m.no2, m.o3 
        FROM mediciones_aire m
        JOIN estaciones e ON m.estacion_id = e.id
        WHERE e.nombre = '{STATION_NAME_PG}'
        ORDER BY m.fecha ASC
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
    """Extracts daily meteorological data from MongoDB."""
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
    print("1. Extracting data from PostgreSQL...")
    df_pg = get_postgres_data()
    df_pg['fecha'] = pd.to_datetime(df_pg['fecha'])
    df_pg['date'] = df_pg['fecha'].dt.date
    
    print("2. Extracting data from MongoDB...")
    df_mongo = get_mongodb_data()
    df_mongo['date'] = pd.to_datetime(df_mongo['fecha_diaria']).dt.date
    df_mongo.drop(columns=['fecha_diaria'], inplace=True)
    
    print("3. Merging datasets (The Master Join)...")
    # Merge hourly air quality with daily weather data
    df_master = pd.merge(df_pg, df_mongo, on='date', how='left')
    df_master.drop(columns=['date'], inplace=True)
    df_master.sort_values('fecha', inplace=True)
    df_master.reset_index(drop=True, inplace=True)
    print(f"Shape after merge: {df_master.shape}")
    
    print("4. Cleaning data (Nulls & Outliers)...")
    cols_to_interpolate = ['pm25', 'no2', 'o3', 'temperatura', 'velocidad_viento', 'precipitacion', 'humedad_relativa']
    
    # Ensure they are numeric
    for col in cols_to_interpolate:
        df_master[col] = pd.to_numeric(df_master[col], errors='coerce')
        
    print(f"Missing values before interpolate:\n{df_master[cols_to_interpolate].isna().sum()}")
        
    # Interpolate short missing gaps
    df_master[cols_to_interpolate] = df_master[cols_to_interpolate].interpolate(method='linear', limit=24)
    df_master.dropna(inplace=True) # drop remaining NaNs
    print(f"Shape after dropna(interpolated): {df_master.shape}")
    
    # Cap outliers (e.g. PM2.5 > 200 is extremely rare, let's cap at 99.9th percentile)
    for col in ['pm25', 'no2', 'o3']:
        upper_limit = df_master[col].quantile(0.999)
        df_master.loc[df_master[col] > upper_limit, col] = upper_limit

    print("5. Feature Engineering...")
    df_master['hora_del_dia'] = df_master['fecha'].dt.hour
    df_master['dia_de_la_semana'] = df_master['fecha'].dt.dayofweek
    
    # Lags
    df_master['pm25_lag1'] = df_master['pm25'].shift(1)
    df_master['pm25_lag2'] = df_master['pm25'].shift(2)
    df_master['pm25_lag3'] = df_master['pm25'].shift(3)
    
    # Rolling averages
    df_master['pm25_rolling_6h'] = df_master['pm25'].rolling(window=6).mean()
    
    df_master.dropna(inplace=True) # Drop rows with NaNs caused by lags
    df_master.set_index('fecha', inplace=True)
    
    print("6. Normalization...")
    scaler = MinMaxScaler()
    # Fit scaler on all columns
    scaled_data = scaler.fit_transform(df_master)
    df_scaled = pd.DataFrame(scaled_data, columns=df_master.columns, index=df_master.index)
    
    # Save the scaler
    os.makedirs(os.path.join(PROJECT_ROOT, 'models'), exist_ok=True)
    joblib.dump(scaler, os.path.join(PROJECT_ROOT, 'models/scaler.pkl'))
    
    # Save dataset
    os.makedirs(os.path.join(PROJECT_ROOT, 'data/processed'), exist_ok=True)
    df_scaled.to_csv(os.path.join(PROJECT_ROOT, 'data/processed/master_dataset.csv'))
    
    print(f"✅ Success! Master dataset saved with shape: {df_scaled.shape}")
    print("Features included:", df_scaled.columns.tolist())

if __name__ == '__main__':
    main()
