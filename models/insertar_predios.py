import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()
os.environ["PGCLIENTENCODING"] = "utf-8"

def insertar_predios(df):
    for key in ["PGUSER", "PGPASSWORD", "PGHOST", "PGPORT", "PGDATABASE"]:
        print(f"{key} = {os.getenv(key)!r}")
    
    print("Iniciando inserción de predios en la base de datos...")

    # Leer variables individuales desde el entorno
    conn = psycopg2.connect(
        dbname=os.getenv("PGDATABASE"),
        user=os.getenv("PGUSER"),
        password=os.getenv("PGPASSWORD"),
        host=os.getenv("PGHOST"),
        port=os.getenv("PGPORT"),
        options='-c client_encoding=UTF8'
    )


    cur = conn.cursor()

    insert_query = """
        INSERT INTO propiedades (
            clave_predio, anio, semestre, indicador_de_aseo,
            direccion_predial, manzana_actual, predio_actual, comuna_actual, cod_serie,
            cuota_trimestral, avaluo_tot, avaluo_ex, anio_termino_ex,
            cod_ubi, cod_destino
        )
        VALUES (
            %(clave_predio)s, %(Año)s, %(Semestre)s, %(Indicador_de_aseo)s,
            %(Direccion_predial)s, %(Manzana_actual)s, %(predio_actual)s, %(Comuna Actual)s, %(Cod_serie)s,
            %(Cuota_trimestral)s, %(Avaluo_tot)s, %(Avaluo_ex)s, %(Año_termino_ex)s,
            %(Cod_ubi)s, %(Cod_destino)s
        )
        ON CONFLICT (clave_predio) DO NOTHING;
    """

    data_dicts = df.to_dict(orient='records')
    cur.executemany(insert_query, data_dicts)

    conn.commit()
    cur.close()
    conn.close()
    print("Inserción de predios completada.")
