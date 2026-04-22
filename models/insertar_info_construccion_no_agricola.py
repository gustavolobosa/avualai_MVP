# models/insertar_info_construccion.py
import os
import io
import time
import psycopg2
from psycopg2 import OperationalError
from dotenv import load_dotenv

load_dotenv()

TARGET_TABLE  = "public.construcciones"
STAGING_TABLE = "public.construcciones_stg"
UPSERT_MODE   = True  # False => DO NOTHING

def _get_conn():
    return psycopg2.connect(
        dbname=os.getenv('PGDATABASE'),
        user=os.getenv('PGUSER'),
        password=os.getenv('PGPASSWORD'),
        host=os.getenv('PGHOST'),
        port=os.getenv('PGPORT'),
        sslmode="require",
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    )

def _copy_chunk(cur, df_chunk, cols):
    buf = io.StringIO()
    df_chunk.to_csv(buf, index=False, header=False, na_rep="\\N", columns=cols)
    buf.seek(0)
    cur.copy_expert(
        f"COPY {STAGING_TABLE} ({', '.join(cols)}) "
        "FROM STDIN WITH (FORMAT CSV, DELIMITER ',', NULL '\\N')",
        buf,
    )

def _retrying_execute(cur, sql, params=None, max_retries=4, backoff=5):
    attempt = 0
    while True:
        try:
            cur.execute(sql, params)
            return
        except OperationalError as e:
            attempt += 1
            if attempt > max_retries:
                raise
            print(f"[WARN] OperationalError: {e}. Reintentando en {backoff}s (intento {attempt}/{max_retries})...")
            time.sleep(backoff)

def _safe_strip(series):
    # respeta None/NaN, sólo hace strip si es str
    return series.map(lambda x: x.strip() if isinstance(x, str) else x)

def insertar_info_construccion(df):
    """
    Inserta/actualiza public.construcciones (nuevo esquema).
    Requiere en df:
      - clave_predio
      - correlativo_linea_constru
      - anio_construccion
    Opcional:
      - cod_material, cod_calidad, cod_condicion_especial
      - sup_construccion

    UPSERT key: (predio_id, anio_construccion, correlativo_linea_constru)
    """
    import pandas as pd

    needed = ["clave_predio", "correlativo_linea_constru", "anio_construccion"]
    for c in needed:
        if c not in df.columns:
            raise ValueError(f"El DataFrame debe incluir '{c}'")

    df = df.copy()

    # Tipos
    for c in ["correlativo_linea_constru", "anio_construccion", "sup_construccion"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")

    for c in ["clave_predio", "cod_material", "cod_calidad", "cod_condicion_especial"]:
        if c in df.columns:
            df[c] = _safe_strip(df[c])
            # vacío -> None (para que COPY lo pase como \N)
            df[c] = df[c].replace("", None)


    # Filtra mínimos
    df = df[
        df["clave_predio"].notna() &
        df["correlativo_linea_constru"].notna() &
        df["anio_construccion"].notna()
    ]
    if df.empty:
        print("No hay filas válidas para insertar en construcciones.")
        return

    # Dedup por clave natural
    df = df.drop_duplicates(
        subset=["clave_predio", "anio_construccion", "correlativo_linea_constru"],
        keep="last"
    )

    conn = _get_conn()
    conn.autocommit = False
    try:
        # valida predios existentes
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '0';")
            cur.execute("SELECT clave_predio FROM public.predios;")
            claves_validas = set(r[0] for r in cur.fetchall())

        before = len(df)
        df = df[df["clave_predio"].isin(claves_validas)]
        after = len(df)
        print(f"Filas antes: {before}")
        print(f"Filas después de filtrar predios válidos: {after}")
        if after == 0:
            print("No hay filas con clave_predio válida para insertar.")
            conn.close()
            return

        # (Re)crear staging UNLOGGED
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '0';")
            cur.execute(f"DROP TABLE IF EXISTS {STAGING_TABLE};")
            cur.execute(f"""
                CREATE UNLOGGED TABLE {STAGING_TABLE} (
                    id BIGSERIAL PRIMARY KEY,
                    clave_predio TEXT,
                    anio_construccion INTEGER,
                    correlativo_linea_constru INTEGER,
                    cod_material TEXT,
                    cod_calidad TEXT,
                    cod_condicion_especial TEXT,
                    sup_construccion INTEGER,
                    tipo TEXT DEFAULT 'no_agricola'
                );
            """)
        conn.commit()

        # Agregar columna tipo
        df["tipo"] = "no_agricola"

        # Asegura columnas opcionales
        cols = [
            "clave_predio",
            "anio_construccion",
            "correlativo_linea_constru",
            "cod_material",
            "cod_calidad",
            "cod_condicion_especial",
            "sup_construccion",
            "tipo",
        ]
        for c in cols:
            if c not in df.columns:
                df[c] = None

        # Orden estable
        df = df.sort_values(
            ["clave_predio", "anio_construccion", "correlativo_linea_constru"],
            kind="stable"
        )
        
        df = df.where(df.notnull(), None)

        # COPY por chunks
        total = len(df)
        chunk_size = 200000
        loaded = 0
        for start in range(0, total, chunk_size):
            end = min(start + chunk_size, total)
            df_chunk = df.iloc[start:end]
            with conn.cursor() as cur:
                cur.execute("SET LOCAL synchronous_commit = OFF;")
                cur.execute("SET LOCAL statement_timeout = '0';")
                _copy_chunk(cur, df_chunk, cols)
            conn.commit()
            loaded = end
            if loaded % 200000 == 0 or loaded == total:
                print(f"COPY a staging: {loaded}/{total}")

        # INSERT/UPSERT → resolviendo predio_id
        insert_batch = 300000
        print(f"Iniciando INSERT en lotes de {insert_batch} filas...")

        with conn.cursor() as cur:
            cur.execute(f"SELECT COALESCE(MIN(id),0), COALESCE(MAX(id),0) FROM {STAGING_TABLE};")
            min_id, max_id = cur.fetchone()

        if UPSERT_MODE:
            upsert_sql = """
            ON CONFLICT (predio_id, anio_construccion, correlativo_linea_constru)
            WHERE tipo = 'no_agricola'
            DO UPDATE SET
                cod_material           = EXCLUDED.cod_material,
                cod_calidad            = EXCLUDED.cod_calidad,
                cod_condicion_especial = EXCLUDED.cod_condicion_especial,
                sup_construccion       = EXCLUDED.sup_construccion
            """
        else:
            upsert_sql = """
            ON CONFLICT (predio_id, anio_construccion, correlativo_linea_constru)
            WHERE tipo = 'no_agricola'
            DO NOTHING
            """

        base_insert = f"""
            INSERT INTO {TARGET_TABLE} (
                predio_id, anio_construccion, correlativo_linea_constru,
                cod_material, cod_calidad, cod_condicion_especial, sup_construccion, tipo
            )
            SELECT
                p.predio_id,
                s.anio_construccion,
                s.correlativo_linea_constru,
                s.cod_material,
                s.cod_calidad,
                s.cod_condicion_especial,
                s.sup_construccion,
                'no_agricola'
            FROM {STAGING_TABLE} s
            JOIN public.predios p
              ON p.clave_predio = s.clave_predio
            WHERE s.id BETWEEN %s AND %s
            {upsert_sql};
        """

        current = min_id
        while current <= max_id:
            upper = current + insert_batch - 1
            with conn.cursor() as cur:
                cur.execute("SET LOCAL synchronous_commit = OFF;")
                cur.execute("SET LOCAL statement_timeout = '0';")
                _retrying_execute(cur, base_insert, (current, upper))
            conn.commit()
            print(f"INSERT (lote) hasta id {upper}")
            current = upper + 1

        print("✅ Inserción/actualización de construcciones completada.")

        # Limpieza
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {STAGING_TABLE};")
        conn.commit()
        print("🧹 STAGING eliminada. Proceso finalizado.")

    finally:
        conn.close()
