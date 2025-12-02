import psycopg2
from psycopg2 import sql

# 🔧 CONFIGURA ESTOS DATOS SEGÚN TU POSTGRES
DB_NAME = "bencidata_db"      # nombre de la base que quieres crear
DB_USER = "postgres"          # usuario de postgres
DB_PASSWORD = "TU_PASSWORD"   # contraseña de ese usuario
DB_HOST = "localhost"
DB_PORT = "5432"


def create_database():
    # Nos conectamos a la BD "postgres" del servidor para poder crear otras BD
    conn = psycopg2.connect(
        dbname="postgres",
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
    )
    conn.autocommit = True
    cursor = conn.cursor()

    # Verificar si la BD ya existe
    cursor.execute(
        sql.SQL("SELECT 1 FROM pg_database WHERE datname = %s"),
        [DB_NAME],
    )
    exists = cursor.fetchone()

    if exists:
        print(f"✅ La base de datos '{DB_NAME}' ya existe.")
    else:
        cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB_NAME)))
        print(f"🎉 Base de datos '{DB_NAME}' creada correctamente.")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    create_database()
