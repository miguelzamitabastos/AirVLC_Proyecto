import os
import psycopg2
from pymongo import MongoClient
import redis
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

def test_postgres():
    print("--- Test PostgreSQL ---")
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST"),
            port=os.getenv("POSTGRES_PORT"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            dbname=os.getenv("POSTGRES_DB")
        )
        cur = conn.cursor()
        
        # Crear tabla de prueba
        cur.execute("""
            CREATE TABLE IF NOT EXISTS test_table (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50),
                value INTEGER
            )
        """)
        
        # Insertar dato
        cur.execute("INSERT INTO test_table (name, value) VALUES ('test_postgres', 100)")
        conn.commit()
        
        # Leer dato
        cur.execute("SELECT * FROM test_table ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        print(f"✅ Conectado y escrito con éxito en Postgres. Último registro: {row}")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error en PostgreSQL: {e}")

def test_mongodb():
    print("\n--- Test MongoDB Atlas ---")
    try:
        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri or "<user>" in mongo_uri:
            print("⚠️ Faltan las credenciales de MongoDB Atlas en el archivo .env")
            return
            
        client = MongoClient(mongo_uri)
        db = client["airvlc_db"]
        collection = db["test_collection"]
        
        # Insertar dato
        result = collection.insert_one({"name": "test_mongo", "value": 200})
        
        # Leer dato
        doc = collection.find_one({"_id": result.inserted_id})
        print(f"✅ Conectado y escrito con éxito en MongoDB Atlas. Documento: {doc}")
        
    except Exception as e:
        print(f"❌ Error en MongoDB Atlas: {e}")

def test_redis():
    print("\n--- Test Redis ---")
    try:
        r = redis.Redis(
            host=os.getenv("REDIS_HOST"),
            port=int(os.getenv("REDIS_PORT")),
            decode_responses=True
        )
        
        # Escribir dato
        r.set('test_key', 'Hello from Redis!')
        
        # Leer dato
        val = r.get('test_key')
        print(f"✅ Conectado y escrito con éxito en Redis. Valor leído: {val}")
        
    except Exception as e:
        print(f"❌ Error en Redis: {e}")

if __name__ == "__main__":
    print("Iniciando test de conexiones ETL...\n")
    test_postgres()
    test_mongodb()
    test_redis()
    print("\n¡Test finalizado!")
