import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

def insertar_info_construccion(df):
    conn = psycopg2.connect(
        dbname=os.getenv("PGDATABASE"),
        user=os.getenv("PGUSER"),
        password=os.getenv("PGPASSWORD"),
        host=os.getenv("PGHOST"),
        port=os.getenv("PGPORT")
    )
    cur = conn.cursor()

    # Obtener claves válidas desde la tabla propiedades
    cur.execute("SELECT clave_predio FROM propiedades")
    claves_validas = set(row[0] for row in cur.fetchall())

    # Filtrar DataFrame
    df_filtrado = df[df['clave_predio'].isin(claves_validas)]

    print(f"Filas antes: {len(df)}")
    print(f"Filas después del filtro: {len(df_filtrado)}")

    query = """
        INSERT INTO info_rol_construccion (
            clave_predio, correlativo_linea_constru,
            cod_material, cod_calidad, anio_constru,
            sup_constru, cod_condicion_especial
        ) VALUES (
            %(clave_predio)s, %(correlativo_linea_constru)s,
            %(cod_material)s, %(cod_calidad)s, %(anio_constru)s,
            %(sup_constru)s, %(cod_condicion_especial)s
        )
    """

    registros = df_filtrado.to_dict(orient='records')
    cur.executemany(query, registros)

    conn.commit()
    cur.close()
    conn.close()
