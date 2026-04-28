"""
AirVLC — Script ETL para carga de datos en PostgreSQL
=====================================================
Semana 1, Martes 29: Diseño de esquema + carga de datos históricos.

Este script:
1. Crea el esquema relacional (4 tablas) en PostgreSQL
2. Carga las estaciones desde el GeoJSON
3. Carga ~449K registros de calidad del aire desde el CSV principal
4. Carga datos de ruido de Russafa desde cda-export.csv
5. Carga datos de emisiones GEI desde datos-emisiones-gei-en-valencia-cas.csv
6. Crea índices para optimizar consultas de series temporales

Uso:
    python src/scripts/load_postgres.py
"""

import os
import sys
import json
import csv
import time
from datetime import datetime, date
from pathlib import Path

import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# ─── Configuración ────────────────────────────────────────────────────────────

# Cargar .env desde la raíz del proyecto
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DATA_RAW = PROJECT_ROOT / "data" / "raw"

# Archivos de datos
GEOJSON_FILE = DATA_RAW / "estaciones-geojson.geojson"
CALIDAD_AIRE_CSV = DATA_RAW / "calidad-aire-2016.csv"
RUIDO_CSV = DATA_RAW / "cda-export.csv"
EMISIONES_CSV = DATA_RAW / "datos-emisiones-gei-en-valencia-cas.csv"

# Tamaño del batch para inserciones masivas
BATCH_SIZE = 5000

# ─── Mapeo de nombres CSV → GeoJSON ──────────────────────────────────────────
# Los nombres de estación en el CSV no coinciden exactamente con los del GeoJSON.
# Este diccionario mapea nombre_csv → nombre_geojson (o None si no tiene equivalente).

STATION_CSV_TO_GEOJSON = {
    "Avda. Francia":              "Francia",
    "Bulevard Sud":               "Boulevar Sur",
    "Molí del Sol":               "Molí del Sol",
    "Pista Silla":                "Pista de Silla",
    "Politécnico":                "Universidad Politécnica",
    "Viveros":                    "Viveros",
    "Valencia Centro":            "Centro",
    "Puerto Valencia":            None,   # No tiene equivalente exacto en GeoJSON
    "Puerto Moll Trans. Ponent":  None,
    "Puerto llit antic Túria":    None,
    "Consellería Meteo":          None,
    "Nazaret Meteo":              None,
}


# ─── DDL: Definición del esquema ──────────────────────────────────────────────

DDL_STATEMENTS = [
    # Tabla de estaciones de medición
    """
    CREATE TABLE IF NOT EXISTS estaciones (
        id              SERIAL PRIMARY KEY,
        nombre          VARCHAR(100) NOT NULL UNIQUE,
        nombre_csv      VARCHAR(100),
        direccion       VARCHAR(200),
        tipo_zona       VARCHAR(50),
        tipo_emision    VARCHAR(50),
        latitud         DOUBLE PRECISION,
        longitud        DOUBLE PRECISION,
        fiware_id       VARCHAR(100),
        parametros      TEXT,
        calidad_ambient VARCHAR(50),
        created_at      TIMESTAMP DEFAULT NOW()
    );
    """,

    # Tabla principal: mediciones horarias de calidad del aire
    """
    CREATE TABLE IF NOT EXISTS mediciones_aire (
        id                      BIGSERIAL PRIMARY KEY,
        estacion_id             INTEGER NOT NULL REFERENCES estaciones(id),
        fecha                   TIMESTAMP NOT NULL,
        dia_semana              VARCHAR(20),
        dia_mes                 SMALLINT,
        hora                    TIME,
        pm1                     REAL,
        pm25                    REAL,
        pm10                    REAL,
        no_val                  REAL,
        no2                     REAL,
        nox                     REAL,
        o3                      REAL,
        so2                     REAL,
        co                      REAL,
        velocidad_viento        REAL,
        direccion_viento        REAL,
        nh3                     REAL,
        c7h8                    REAL,
        c6h6                    REAL,
        ruido                   REAL,
        c8h10                   REAL,
        temperatura             REAL,
        humedad_relativa        REAL,
        presion                 REAL,
        radiacion               REAL,
        precipitacion           REAL,
        velocidad_max_viento    REAL
    );
    """,

    # Tabla de ruido (sensor Russafa) — datos diarios
    """
    CREATE TABLE IF NOT EXISTS ruido_russafa (
        id                  SERIAL PRIMARY KEY,
        recv_time           TIMESTAMP,
        fecha_observacion   DATE,
        laeq                REAL,
        laeq_d              REAL,
        laeq_den            REAL,
        laeq_e              REAL,
        laeq_n              REAL
    );
    """,

    # Tabla de emisiones de gases de efecto invernadero
    """
    CREATE TABLE IF NOT EXISTS emisiones_gei (
        id              SERIAL PRIMARY KEY,
        posicion        VARCHAR(20),
        sector          VARCHAR(100),
        criterios       VARCHAR(200),
        indicador       VARCHAR(200),
        valor_tco2      REAL
    );
    """,
]

# Índices — se crean DESPUÉS de la carga masiva para mayor rendimiento
INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_mediciones_estacion_fecha ON mediciones_aire (estacion_id, fecha);",
    "CREATE INDEX IF NOT EXISTS idx_mediciones_fecha ON mediciones_aire (fecha);",
    "CREATE INDEX IF NOT EXISTS idx_mediciones_estacion ON mediciones_aire (estacion_id);",
    "CREATE INDEX IF NOT EXISTS idx_ruido_fecha ON ruido_russafa (fecha_observacion);",
]


# ─── Funciones auxiliares ─────────────────────────────────────────────────────

def safe_float(value):
    """Convierte un valor a float, retornando None si está vacío o no es válido."""
    if value is None or str(value).strip() == "":
        return None
    try:
        # Manejar formato español con comas: "12.950,19" → 12950.19
        val_str = str(value).strip()
        if "," in val_str and "." in val_str:
            val_str = val_str.replace(".", "").replace(",", ".")
        elif "," in val_str:
            val_str = val_str.replace(",", ".")
        return float(val_str)
    except (ValueError, TypeError):
        return None


def safe_int(value):
    """Convierte un valor a int, retornando None si está vacío."""
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return None


def parse_time(time_str):
    """Parsea una hora en formato H:MM:SS o HH:MM:SS."""
    if not time_str or str(time_str).strip() == "":
        return None
    try:
        parts = str(time_str).strip().split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        s = int(parts[2]) if len(parts) > 2 else 0
        return f"{h:02d}:{m:02d}:{s:02d}"
    except (ValueError, IndexError):
        return None


def parse_date(date_str):
    """Parsea una fecha ISO 8601 (YYYY-MM-DDTHH:MM:SS)."""
    if not date_str or str(date_str).strip() == "":
        return None
    try:
        return datetime.fromisoformat(str(date_str).strip())
    except ValueError:
        return None


def get_connection():
    """Crea una conexión a PostgreSQL con los parámetros del .env."""
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        dbname=os.getenv("POSTGRES_DB"),
    )


def print_header(title):
    """Imprime un header formateado."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_step(step, msg):
    """Imprime un paso numerado."""
    print(f"\n  [{step}] {msg}")


# ─── Paso 1: Crear esquema ───────────────────────────────────────────────────

def create_schema(conn):
    """Crea las tablas del esquema si no existen."""
    print_header("PASO 1: Creando esquema en PostgreSQL")
    cur = conn.cursor()

    for i, ddl in enumerate(DDL_STATEMENTS, 1):
        # Extraer nombre de tabla del DDL
        table_name = ddl.split("CREATE TABLE IF NOT EXISTS")[1].split("(")[0].strip()
        print_step(f"1.{i}", f"Creando tabla: {table_name}")
        cur.execute(ddl)

    conn.commit()
    cur.close()
    print("\n  ✅ Esquema creado correctamente")


# ─── Paso 2: Cargar estaciones ────────────────────────────────────────────────

def load_estaciones(conn):
    """
    Carga estaciones desde el GeoJSON + añade las estaciones del CSV
    que no están en el GeoJSON (sin coordenadas).
    Retorna un dict {nombre_csv: estacion_id} para usar como FK.
    """
    print_header("PASO 2: Cargando estaciones")
    cur = conn.cursor()

    # Verificar si ya hay datos
    cur.execute("SELECT COUNT(*) FROM estaciones")
    count = cur.fetchone()[0]
    if count > 0:
        print(f"  ⚠️  Ya existen {count} estaciones. Saltando carga.")
        # Construir mapeo existente
        cur.execute("SELECT nombre_csv, id FROM estaciones WHERE nombre_csv IS NOT NULL")
        station_map = {row[0]: row[1] for row in cur.fetchall()}
        cur.close()
        return station_map

    station_map = {}  # nombre_csv → estacion_id

    # 2.1 — Cargar desde GeoJSON
    print_step("2.1", f"Leyendo GeoJSON: {GEOJSON_FILE.name}")
    with open(GEOJSON_FILE, "r", encoding="utf-8") as f:
        geojson = json.load(f)

    geojson_stations = {}  # nombre_geojson → properties
    for feature in geojson["features"]:
        props = feature["properties"]
        coords = feature["geometry"]["coordinates"]
        nombre_geo = props["nombre"]
        geojson_stations[nombre_geo] = {
            "nombre": nombre_geo,
            "direccion": props.get("direccion"),
            "tipo_zona": props.get("tipozona"),
            "tipo_emision": props.get("tipoemisio"),
            "longitud": coords[0],
            "latitud": coords[1],
            "fiware_id": props.get("fiwareid"),
            "parametros": props.get("parametros"),
            "calidad_ambient": props.get("calidad_am"),
        }

    print(f"       → {len(geojson_stations)} estaciones en GeoJSON")

    # 2.2 — Insertar estaciones mapeando CSV → GeoJSON
    print_step("2.2", "Insertando estaciones con mapeo CSV ↔ GeoJSON")

    insert_sql = """
        INSERT INTO estaciones (nombre, nombre_csv, direccion, tipo_zona, tipo_emision,
                                latitud, longitud, fiware_id, parametros, calidad_ambient)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """

    inserted = 0
    for csv_name, geo_name in STATION_CSV_TO_GEOJSON.items():
        if geo_name and geo_name in geojson_stations:
            geo = geojson_stations[geo_name]
            cur.execute(insert_sql, (
                geo["nombre"], csv_name, geo["direccion"],
                geo["tipo_zona"], geo["tipo_emision"],
                geo["latitud"], geo["longitud"],
                geo["fiware_id"], geo["parametros"], geo["calidad_ambient"],
            ))
        else:
            # Estación del CSV sin equivalente en GeoJSON
            cur.execute(insert_sql, (
                csv_name, csv_name, None,
                None, None,
                None, None,
                None, None, None,
            ))

        station_id = cur.fetchone()[0]
        station_map[csv_name] = station_id
        inserted += 1
        has_coords = "📍" if (geo_name and geo_name in geojson_stations) else "❓"
        print(f"       {has_coords} {csv_name} → id={station_id}")

    # 2.3 — Insertar estaciones GeoJSON que NO están en el CSV (ej: Patraix, Dr. Lluch, etc.)
    geo_names_already_inserted = set(
        v for v in STATION_CSV_TO_GEOJSON.values() if v is not None
    )
    for geo_name, geo in geojson_stations.items():
        if geo_name not in geo_names_already_inserted:
            cur.execute(insert_sql, (
                geo["nombre"], None, geo["direccion"],
                geo["tipo_zona"], geo["tipo_emision"],
                geo["latitud"], geo["longitud"],
                geo["fiware_id"], geo["parametros"], geo["calidad_ambient"],
            ))
            station_id = cur.fetchone()[0]
            inserted += 1
            print(f"       📍 {geo_name} (solo GeoJSON) → id={station_id}")

    conn.commit()
    cur.close()
    print(f"\n  ✅ {inserted} estaciones insertadas")
    return station_map


# ─── Paso 3: Cargar mediciones de calidad del aire ───────────────────────────

def load_mediciones_aire(conn, station_map):
    """
    Carga el CSV principal de calidad del aire (~449K filas).
    Usa batch inserts con execute_values para rendimiento.
    """
    print_header("PASO 3: Cargando mediciones de calidad del aire")
    cur = conn.cursor()

    # Verificar si ya hay datos
    cur.execute("SELECT COUNT(*) FROM mediciones_aire")
    count = cur.fetchone()[0]
    if count > 0:
        print(f"  ⚠️  Ya existen {count:,} registros. Saltando carga.")
        cur.close()
        return count

    print_step("3.1", f"Leyendo CSV: {CALIDAD_AIRE_CSV.name}")

    insert_sql = """
        INSERT INTO mediciones_aire (
            estacion_id, fecha, dia_semana, dia_mes, hora,
            pm1, pm25, pm10, no_val, no2, nox, o3, so2, co,
            velocidad_viento, direccion_viento, nh3, c7h8, c6h6,
            ruido, c8h10, temperatura, humedad_relativa,
            presion, radiacion, precipitacion, velocidad_max_viento
        ) VALUES %s
    """

    total_rows = 0
    skipped_stations = set()
    batch = []
    start_time = time.time()

    # Detectar encoding: el archivo tiene BOM UTF-8
    with open(CALIDAD_AIRE_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")

        for row in reader:
            station_name = row.get("Estación", "").strip()

            # Buscar estación en el mapeo
            if station_name not in station_map:
                skipped_stations.add(station_name)
                continue

            estacion_id = station_map[station_name]

            record = (
                estacion_id,
                parse_date(row.get("Fecha")),
                row.get("Día de la semana", "").strip() or None,
                safe_int(row.get("Día del mes")),
                parse_time(row.get("Hora")),
                safe_float(row.get("PM1")),
                safe_float(row.get("PM2.5")),
                safe_float(row.get("PM10")),
                safe_float(row.get("NO")),
                safe_float(row.get("NO2")),
                safe_float(row.get("NOx")),
                safe_float(row.get("O3")),
                safe_float(row.get("SO2")),
                safe_float(row.get("CO")),
                safe_float(row.get("Velocidad del viento")),
                safe_float(row.get("Dirección del viento")),
                safe_float(row.get("NH3")),
                safe_float(row.get("C7H8")),
                safe_float(row.get("C6H6")),
                safe_float(row.get("Ruido")),
                safe_float(row.get("C8H10")),
                safe_float(row.get("Temperatura")),
                safe_float(row.get("Humedad relativa")),
                safe_float(row.get("Presión")),
                safe_float(row.get("Radiación")),
                safe_float(row.get("Precipitación")),
                safe_float(row.get("Velocidad máxima del viento")),
            )
            batch.append(record)
            total_rows += 1

            # Insertar en batches
            if len(batch) >= BATCH_SIZE:
                execute_values(cur, insert_sql, batch, page_size=BATCH_SIZE)
                conn.commit()
                elapsed = time.time() - start_time
                rate = total_rows / elapsed if elapsed > 0 else 0
                print(f"\r       → {total_rows:>8,} filas insertadas ({rate:,.0f} filas/s)", end="", flush=True)
                batch = []

    # Insertar el último batch
    if batch:
        execute_values(cur, insert_sql, batch, page_size=BATCH_SIZE)
        conn.commit()

    elapsed = time.time() - start_time
    print(f"\r       → {total_rows:>8,} filas insertadas en {elapsed:.1f}s ({total_rows/elapsed:,.0f} filas/s)")

    if skipped_stations:
        print(f"\n  ⚠️  Estaciones no mapeadas (filas saltadas): {skipped_stations}")

    cur.close()
    print(f"\n  ✅ {total_rows:,} mediciones de aire cargadas")
    return total_rows


# ─── Paso 4: Cargar datos de ruido (Russafa) ─────────────────────────────────

def load_ruido(conn):
    """Carga datos diarios del sensor de ruido de Russafa."""
    print_header("PASO 4: Cargando datos de ruido (Russafa)")
    cur = conn.cursor()

    # Verificar si ya hay datos
    cur.execute("SELECT COUNT(*) FROM ruido_russafa")
    count = cur.fetchone()[0]
    if count > 0:
        print(f"  ⚠️  Ya existen {count} registros. Saltando carga.")
        cur.close()
        return count

    print_step("4.1", f"Leyendo CSV: {RUIDO_CSV.name}")

    insert_sql = """
        INSERT INTO ruido_russafa (recv_time, fecha_observacion, laeq, laeq_d, laeq_den, laeq_e, laeq_n)
        VALUES %s
    """

    batch = []
    total_rows = 0

    with open(RUIDO_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")

        for row in reader:
            # Parsear recv_time (formato: "2026-04-27 06:00:12.463")
            recv_time_str = row.get("recvtime", "").strip()
            recv_time = None
            if recv_time_str:
                try:
                    recv_time = datetime.strptime(recv_time_str, "%Y-%m-%d %H:%M:%S.%f")
                except ValueError:
                    try:
                        recv_time = datetime.strptime(recv_time_str, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        pass

            # Parsear fecha observación (formato: "2026-04-26")
            date_str = row.get('"dateobserved"', "").strip().strip('"')
            fecha_obs = None
            if date_str:
                try:
                    fecha_obs = date.fromisoformat(date_str)
                except ValueError:
                    pass

            record = (
                recv_time,
                fecha_obs,
                safe_float(row.get('"laeq"', "").strip('"')),
                safe_float(row.get('"laeq_d"', "").strip('"')),
                safe_float(row.get('"laeq_den"', "").strip('"')),
                safe_float(row.get('"laeq_e"', "").strip('"')),
                safe_float(row.get('"laeq_n"', "").strip('"')),
            )
            batch.append(record)
            total_rows += 1

    if batch:
        execute_values(cur, insert_sql, batch)
        conn.commit()

    cur.close()
    print(f"\n  ✅ {total_rows:,} registros de ruido cargados")
    return total_rows


# ─── Paso 5: Cargar emisiones GEI ────────────────────────────────────────────

def load_emisiones(conn):
    """Carga datos de emisiones de gases de efecto invernadero."""
    print_header("PASO 5: Cargando emisiones GEI")
    cur = conn.cursor()

    # Verificar si ya hay datos
    cur.execute("SELECT COUNT(*) FROM emisiones_gei")
    count = cur.fetchone()[0]
    if count > 0:
        print(f"  ⚠️  Ya existen {count} registros. Saltando carga.")
        cur.close()
        return count

    print_step("5.1", f"Leyendo CSV: {EMISIONES_CSV.name}")

    insert_sql = """
        INSERT INTO emisiones_gei (posicion, sector, criterios, indicador, valor_tco2)
        VALUES %s
    """

    batch = []
    total_rows = 0

    with open(EMISIONES_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")

        for row in reader:
            record = (
                row.get("POSICIÓN", "").strip(),
                row.get("SECTOR", "").strip(),
                row.get("CRITERIOS", "").strip(),
                row.get("INDICADOR", "").strip(),
                safe_float(row.get("VALOR (tCO2)", "")),
            )
            batch.append(record)
            total_rows += 1

    if batch:
        execute_values(cur, insert_sql, batch)
        conn.commit()

    cur.close()
    print(f"\n  ✅ {total_rows:,} registros de emisiones GEI cargados")
    return total_rows


# ─── Paso 6: Crear índices ───────────────────────────────────────────────────

def create_indexes(conn):
    """Crea índices para optimizar consultas de series temporales."""
    print_header("PASO 6: Creando índices")
    cur = conn.cursor()

    for i, idx_sql in enumerate(INDEX_STATEMENTS, 1):
        idx_name = idx_sql.split("INDEX IF NOT EXISTS")[1].split("ON")[0].strip()
        print_step(f"6.{i}", f"Creando índice: {idx_name}")
        cur.execute(idx_sql)

    conn.commit()
    cur.close()
    print("\n  ✅ Índices creados correctamente")


# ─── Paso 7: Resumen final ──────────────────────────────────────────────────

def print_summary(conn):
    """Muestra un resumen de la carga con conteos por tabla."""
    print_header("RESUMEN DE CARGA")
    cur = conn.cursor()

    tables = [
        ("estaciones", "Estaciones de medición"),
        ("mediciones_aire", "Mediciones horarias calidad del aire"),
        ("ruido_russafa", "Registros sensor ruido Russafa"),
        ("emisiones_gei", "Registros emisiones GEI"),
    ]

    for table, description in tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"  📊 {table:25s} → {count:>10,} registros  ({description})")

    # Detalle por estación
    print(f"\n  {'─'*55}")
    print("  📍 Detalle por estación:")
    cur.execute("""
        SELECT e.nombre, e.nombre_csv, COUNT(m.id) as n_mediciones,
               CASE WHEN e.latitud IS NOT NULL THEN '📍' ELSE '❓' END as geo
        FROM estaciones e
        LEFT JOIN mediciones_aire m ON m.estacion_id = e.id
        GROUP BY e.id, e.nombre, e.nombre_csv, e.latitud
        ORDER BY n_mediciones DESC
    """)
    for row in cur.fetchall():
        nombre, nombre_csv, n_med, geo = row
        csv_label = f" (CSV: {nombre_csv})" if nombre_csv and nombre_csv != nombre else ""
        print(f"     {geo} {nombre:30s}{csv_label:35s} → {n_med:>8,} mediciones")

    # Rango temporal
    cur.execute("SELECT MIN(fecha), MAX(fecha) FROM mediciones_aire")
    min_date, max_date = cur.fetchone()
    if min_date and max_date:
        print(f"\n  📅 Rango temporal: {min_date.strftime('%Y-%m-%d')} → {max_date.strftime('%Y-%m-%d')}")

    cur.close()


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("╔══════════════════════════════════════════════════════════╗")
    print("║     AirVLC — ETL: Carga de datos en PostgreSQL          ║")
    print("╚══════════════════════════════════════════════════════════╝")

    # Verificar que los archivos existen
    for filepath in [GEOJSON_FILE, CALIDAD_AIRE_CSV, RUIDO_CSV, EMISIONES_CSV]:
        if not filepath.exists():
            print(f"❌ Archivo no encontrado: {filepath}")
            sys.exit(1)

    # Conectar a PostgreSQL
    print(f"\n  🔌 Conectando a PostgreSQL ({os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')})...")
    try:
        conn = get_connection()
        print("  ✅ Conexión establecida")
    except Exception as e:
        print(f"  ❌ Error de conexión: {e}")
        sys.exit(1)

    start_total = time.time()

    try:
        # Paso 1: Crear esquema
        create_schema(conn)

        # Paso 2: Cargar estaciones
        station_map = load_estaciones(conn)

        # Paso 3: Cargar mediciones de calidad del aire (la carga pesada)
        load_mediciones_aire(conn, station_map)

        # Paso 4: Cargar ruido Russafa
        load_ruido(conn)

        # Paso 5: Cargar emisiones GEI
        load_emisiones(conn)

        # Paso 6: Crear índices (después de la carga masiva)
        create_indexes(conn)

        # Paso 7: Resumen
        print_summary(conn)

    except Exception as e:
        conn.rollback()
        print(f"\n  ❌ Error durante la carga: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()

    elapsed_total = time.time() - start_total
    print(f"\n  ⏱️  Tiempo total: {elapsed_total:.1f} segundos")
    print("\n✅ ETL PostgreSQL completado exitosamente.\n")


if __name__ == "__main__":
    main()
