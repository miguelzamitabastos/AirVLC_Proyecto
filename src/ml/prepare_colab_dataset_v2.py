"""
===================================================================
🚀 AirVLC v2 — Preparación del Dataset Maestro Multivariante
===================================================================
Genera ``data/processed/master_dataset_colab_v2.csv`` con:

* Tres targets: ``pm25``, ``no2``, ``o3`` (Índice de Calidad del Aire ICA).
* Feature Engineering avanzado por estación:
    - Lags temporales (t-1, t-3, t-6, t-24) para los 3 contaminantes.
    - Medias móviles (6h, 12h, 24h) para los 3 contaminantes.
    - Variables de calendario booleanas (``is_weekend``, ``is_fallas``).
    - Codificación trigonométrica (sin/cos) de hora y mes.
* Cruce con datos meteorológicos diarios de AEMET (estación Viveros).
* Capping de outliers (percentil 99.9) para mitigar picos extremos.

Este script convive con el script v1 (``prepare_colab_dataset.py``)
sin pisarlo. v1 sigue siendo el origen de datos para la API actual,
mientras v2 alimenta el nuevo notebook ``11_v2_Colab_Multitarget.ipynb``
y la futura API v2.

Uso:
    python src/ml/prepare_colab_dataset_v2.py
===================================================================
"""

import os
import pandas as pd
import numpy as np
import psycopg2
import pymongo
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432')
POSTGRES_USER = os.getenv('POSTGRES_USER')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
POSTGRES_DB = os.getenv('POSTGRES_DB')
MONGO_URI = os.getenv('MONGO_URI')

# Estación meteo representativa del clima de la ciudad de Valencia
STATION_ID_MONGO = '8416Y'  # Viveros

TARGETS = ['pm25', 'no2', 'o3']
LAGS = [1, 3, 6, 24]
ROLLING_WINDOWS = [6, 12, 24]


def get_postgres_data():
    """Extrae todas las mediciones de aire (pm25, no2, o3) por estación.

    En la BD, ``mediciones_aire.fecha`` es un TIMESTAMP siempre a medianoche
    y la hora real vive en ``mediciones_aire.hora`` (TIME). Aquí los
    combinamos en SQL (``fecha::date + hora``) para producir un único
    timestamp horario y evitar que 24 filas distintas compartan la misma
    ``fecha`` (lo cual rompía el sequencing temporal del Sprint 2).
    """
    print("Conectando a PostgreSQL para extraer TODAS las estaciones...")
    conn = psycopg2.connect(
        host=POSTGRES_HOST, port=POSTGRES_PORT,
        user=POSTGRES_USER, password=POSTGRES_PASSWORD, dbname=POSTGRES_DB
    )
    query = """
        SELECT e.nombre AS estacion,
               (m.fecha::date + m.hora) AS fecha,
               m.pm25, m.no2, m.o3
        FROM mediciones_aire m
        JOIN estaciones e ON m.estacion_id = e.id
        WHERE m.hora IS NOT NULL
        ORDER BY e.nombre, m.fecha ASC, m.hora ASC
    """
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def clean_aemet_value(val):
    """Convierte valores AEMET (con coma decimal o vacíos) a float."""
    if pd.isna(val):
        return np.nan
    if isinstance(val, str):
        val = val.replace(',', '.')
    try:
        return float(val)
    except ValueError:
        return np.nan


def get_mongodb_data():
    """Extrae datos climatológicos diarios de AEMET para Viveros."""
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
    cols_to_interpolate = TARGETS + ['temperatura', 'velocidad_viento', 'precipitacion', 'humedad_relativa']

    for col in cols_to_interpolate:
        df_master[col] = pd.to_numeric(df_master[col], errors='coerce')

    df_master[cols_to_interpolate] = df_master.groupby('estacion')[cols_to_interpolate].transform(
        lambda group: group.interpolate(method='linear', limit=24)
    )
    df_master.dropna(inplace=True)

    print("Capping de outliers en targets (percentil 99.9)...")
    for col in TARGETS:
        upper_limit = df_master[col].quantile(0.999)
        df_master.loc[df_master[col] > upper_limit, col] = upper_limit

    print("Feature Engineering por estación...")
    df_master['hora_del_dia'] = df_master['fecha'].dt.hour
    df_master['dia_de_la_semana'] = df_master['fecha'].dt.dayofweek
    df_master['mes'] = df_master['fecha'].dt.month

    df_master['is_weekend'] = (df_master['dia_de_la_semana'] >= 5).astype(int)
    df_master['is_fallas'] = (
        (df_master['fecha'].dt.month == 3)
        & (df_master['fecha'].dt.day >= 15)
        & (df_master['fecha'].dt.day <= 19)
    ).astype(int)

    for col in TARGETS:
        for lag in LAGS:
            df_master[f'{col}_lag{lag}'] = df_master.groupby('estacion')[col].shift(lag)

    for col in TARGETS:
        for window in ROLLING_WINDOWS:
            df_master[f'{col}_rolling_{window}h'] = df_master.groupby('estacion')[col].transform(
                lambda x: x.rolling(window=window).mean()
            )

    df_master['hora_sin'] = np.sin(2 * np.pi * df_master['hora_del_dia'] / 24)
    df_master['hora_cos'] = np.cos(2 * np.pi * df_master['hora_del_dia'] / 24)
    df_master['mes_sin'] = np.sin(2 * np.pi * df_master['mes'] / 12)
    df_master['mes_cos'] = np.cos(2 * np.pi * df_master['mes'] / 12)

    df_master.dropna(inplace=True)

    print("One-Hot Encoding para las estaciones...")
    df_master['station_name'] = df_master['estacion']
    df_master = pd.get_dummies(df_master, columns=['estacion'], prefix='station')

    df_master.set_index('fecha', inplace=True)

    out_path = os.path.join(PROJECT_ROOT, 'data/processed/master_dataset_colab_v2.csv')
    df_master.to_csv(out_path)

    print(f"\n✅ ¡Éxito! Dataset v2 multitarget guardado: {out_path}")
    print(f"   Shape: {df_master.shape}")
    print(f"   Estaciones: {sorted(df_master['station_name'].unique())}")
    print(f"   Targets: {TARGETS}")
    print(f"   Columnas totales: {df_master.shape[1]}")


if __name__ == '__main__':
    main()
