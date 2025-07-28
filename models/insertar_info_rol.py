import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

def insertar_info_rol(df):
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

    print(f"Filas: {len(df)}")
    # Filtrar DataFrame
    df_filtrado = df[df['clave_predio'].isin(claves_validas)]
    
    # df_invalido = df_filtrado[
    #                 df_filtrado['clave_predio_bien_comun_1'].notna() &
    #                 ~df_filtrado['clave_predio_bien_comun_1'].isin(claves_validas)
    #             ]
    # print("entonces, las filas removidas fueron:", len(df_invalido))
    # print(df_invalido.head(30))
    
    df_filtrado = df_filtrado[
        df_filtrado['clave_predio_bien_comun_1'].isna() |
        df_filtrado['clave_predio_bien_comun_1'].isin(claves_validas)
    ]
    
    print(f"Filas después del filtro 1: {len(df_filtrado)}")
    
    df_filtrado = df_filtrado[
        df_filtrado['clave_predio_bien_comun_2'].isna() |
        df_filtrado['clave_predio_bien_comun_2'].isin(claves_validas)
    ]

    print(f"Filas antes: {len(df)}")
    print(f"Filas después del filtro: {len(df_filtrado)}")

    query = """

        INSERT INTO info_rol (
            clave_predio, avaluo_fiscal_total, avaluo_exento, contribuciones_semana_con_aseo,
            superficie_total, clave_predio_bien_comun_1, clave_predio_bien_comun_2
        ) VALUES (
            %(clave_predio)s, %(avaluo_fiscal_total)s, %(avaluo_exento)s, %(contribuciones_semana_con_aseo)s,
            %(sup_total)s, %(clave_predio_bien_comun_1)s, %(clave_predio_bien_comun_2)s
        )
    """

    registros = df_filtrado.to_dict(orient='records')
    cur.executemany(query, registros)

    conn.commit()
    cur.close()
    conn.close()
