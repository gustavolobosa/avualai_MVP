import pandas as pd
import psycopg2
from dotenv import load_dotenv
import os

# Cargar .env
load_dotenv()

# Leer archivo Excel
df = pd.read_excel('../datos/datos_comunas.xlsx',
                   dtype={
                            'codigo_comuna': str,
                            'codigo_tesoreria': str
                        })  # cambia la ruta

# Conectar a PostgreSQL
conn = psycopg2.connect(
    dbname=os.getenv('PGDATABASE'),
    user=os.getenv('PGUSER'),
    password=os.getenv('PGPASSWORD'),
    host=os.getenv('PGHOST'),
    port=os.getenv('PGPORT')
)
cur = conn.cursor()

print(df.head())

# Insertar fila a fila
for _, row in df.iterrows():
    cur.execute("""
        INSERT INTO comunas (cod_comuna, nombre_comuna, cod_tesoreria)
        VALUES (%s, %s, %s)
        ON CONFLICT (cod_comuna) DO NOTHING;
    """, (str(row['codigo_comuna']), str(row['nombre_comuna']), str(row['codigo_tesoreria'])))

# Finalizar
conn.commit()
cur.close()
conn.close()

print("Inserción completada.")
