import psycopg2
import os
from dotenv import load_dotenv

load_dotenv('.env')

def main():
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        dbname=os.getenv("POSTGRES_DB"),
    )
    cur = conn.cursor()

    updates = [
        (39.4732, -0.4069, 'Consellería Meteo'),
        (39.4533, -0.3200, 'Puerto Valencia'),
        (39.4475, -0.3308, 'Nazaret Meteo'),
        (39.4600, -0.3340, 'Puerto llit antic Túria'),
        (39.4430, -0.3250, 'Puerto Moll Trans. Ponent')
    ]

    for lat, lon, name in updates:
        cur.execute("UPDATE estaciones SET latitud = %s, longitud = %s WHERE nombre_csv = %s OR nombre = %s", (lat, lon, name, name))
        print(f"Updated {name}")

    conn.commit()
    cur.close()
    conn.close()
    print("Done updating coordinates.")

if __name__ == "__main__":
    main()
