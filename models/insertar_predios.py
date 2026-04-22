import os
import io
import time
import psycopg2
import psycopg2.extras as extras
from psycopg2 import OperationalError
from dotenv import load_dotenv

load_dotenv()

from models.insertar_info_cosntruccion_agricolas import _safe_strip

# ========================
# Config
# ========================
TARGET_TABLE  = "public.predios"
STAGING_TABLE = "public.predios_stg"

# Si True: hace UPSERT (actualiza columnas ante conflicto)
# Si False: hace DO NOTHING (inserta solo nuevas)
UPSERT_MODE = True

# ========================
# Conexión
# ========================
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

# ========================
# Utilidades
# ========================
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

# ========================
# Carga: PREDIOS
# ========================
def insertar_predios(df):
    """
    Inserta/actualiza 'public.predios' con PK surrogate (predio_id) y
    UNIQUE(cod_comuna, manzana_actual, predio_actual).

    Columnas esperadas en df (si alguna falta, se rellena con NULL):
      - comuna_actual (-> cod_comuna)
      - manzana_actual (int)
      - predio_actual  (int)
      - direccion_predial (str)
      - lat (float)
      - lng (float)
      - area_homogenea (str)
    """
    # Mapeo/orden de columnas para COPY/INSERT en predios
    cols = [
        "cod_comuna",
        "manzana_actual",
        "predio_actual",
        "direccion_predial",
        "lat",
        "lng",
        "area_homogenea"
    ]

    # Normaliza y proyecta DF a las columnas del destino
    df = df.copy()

    # Asegura columnas de origen (si no existen, crea vacías)
    source_defaults = {
        "comuna_actual": None,
        "manzana_actual": None,
        "predio_actual": None,
        "direccion_predial": None,
        "lat": None,
        "lng": None,
        "area_homogenea": None
    }
    for c, default in source_defaults.items():
        if c not in df.columns:
            df[c] = default

    # Crear columna destino cod_comuna desde comuna_actual
    df["cod_comuna"] = df["comuna_actual"]

    # Tipos
    if "manzana_actual" in df.columns:
        df["manzana_actual"] = df["manzana_actual"].astype("Int64").where(df["manzana_actual"].notnull(), None)
    if "predio_actual" in df.columns:
        df["predio_actual"] = df["predio_actual"].astype("Int64").where(df["predio_actual"].notnull(), None)
    for c in ["lat", "lng"]:
        if c in df.columns:
            df[c] = df[c].astype(float).where(df[c].notnull(), None)

    # Filtra comunas válidas (FK a comunas.cod_comuna)
    conn = _get_conn()
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '0';")
            cur.execute("SELECT cod_comuna FROM public.comunas;")
            comunas_validas = set(r[0] for r in cur.fetchall())

        before = len(df)
        df = df[df["cod_comuna"].isin(comunas_validas)]
        after = len(df)
        print(f"Filas antes: {before}")
        print(f"Filas después de filtrar comunas válidas: {after}")
        if after == 0:
            print("No hay filas válidas para insertar.")
            conn.close()
            return

        # Deduplicar por clave natural del predio
        # print si es que hay duplicados 
        dupes = df.duplicated(subset=["cod_comuna", "manzana_actual", "predio_actual"], keep=False)
        # print the dupes that are true
        print("Filas duplicadas detectadas (clave natural):", len(df[dupes]))
        print(df[dupes], "*********")
        df = df.drop_duplicates(subset=["cod_comuna", "manzana_actual", "predio_actual"], keep="last")

        # Re-crear staging
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '0';")
            cur.execute(f"DROP TABLE IF EXISTS {STAGING_TABLE};")
            cur.execute(f"""
                CREATE UNLOGGED TABLE {STAGING_TABLE} (

                    id BIGSERIAL PRIMARY KEY,
                    cod_comuna TEXT,
                    manzana_actual INTEGER,
                    predio_actual INTEGER,
                    direccion_predial TEXT,
                    lat DOUBLE PRECISION,
                    lng DOUBLE PRECISION,
                    area_homogenea TEXT
                );
            """)
        conn.commit()

        # COPY por chunks
        chunk_size = int(200000)
        total = len(df)
        loaded = 0

        # Orden estable opcional
        df = df.sort_values(["cod_comuna", "manzana_actual", "predio_actual"], kind="stable")

        for start in range(0, total, chunk_size):
            end = min(start + chunk_size, total)
            df_chunk = df.iloc[start:end]
            with conn.cursor() as cur:
                cur.execute("SET LOCAL synchronous_commit = OFF;")
                cur.execute("SET LOCAL statement_timeout = '0';")
                _copy_chunk(cur, df_chunk, cols)
            conn.commit()
            loaded = end
            print(f"COPY a staging: {loaded}/{total}")

        # INSERT/UPSERT por rangos
        insert_batch = int(300000)
        print(f"Iniciando INSERT en lotes de {insert_batch} filas...")

        with conn.cursor() as cur:
            cur.execute(f"SELECT COALESCE(MIN(id),0), COALESCE(MAX(id),0) FROM {STAGING_TABLE};")
            min_id, max_id = cur.fetchone()

        inserted = 0
        current = min_id

        if UPSERT_MODE:
            upsert_sql = """
            ON CONFLICT (cod_comuna, manzana_actual, predio_actual) DO UPDATE SET
                direccion_predial  = EXCLUDED.direccion_predial,
                lat                = EXCLUDED.lat,
                lng                = EXCLUDED.lng,
                area_homogenea     = EXCLUDED.area_homogenea
            """
        else:
            upsert_sql = "ON CONFLICT (cod_comuna, manzana_actual, predio_actual) DO NOTHING"

        base_insert = f"""
            INSERT INTO {TARGET_TABLE} (
                cod_comuna, manzana_actual, predio_actual,
                direccion_predial, lat, lng, area_homogenea
            )
            SELECT
                s.cod_comuna, s.manzana_actual, s.predio_actual,
                s.direccion_predial, s.lat, s.lng, s.area_homogenea
            FROM {STAGING_TABLE} s
            WHERE s.id BETWEEN %s AND %s
            {upsert_sql};
        """

        while current <= max_id:
            upper = current + insert_batch - 1
            with conn.cursor() as cur:
                cur.execute("SET LOCAL synchronous_commit = OFF;")
                cur.execute("SET LOCAL statement_timeout = '0';")
                _retrying_execute(cur, base_insert, (current, upper))
            conn.commit()

            inserted += (upper - current + 1)
            print(f"INSERT (lote) hasta id {upper}")

            current = upper + 1

        print("✅ Inserción de predios completada.")

        # Limpieza
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {STAGING_TABLE};")
        conn.commit()
        print("🧹 STAGING eliminada. Proceso finalizado.")

    finally:
        conn.close()

def actualizar_cod_serie_predios(df, insert_missing=False):
    """
    Actualiza SOLO predios.cod_serie en public.predios, matcheando por
    (cod_comuna, manzana_actual, predio_actual).

    Requiere en df:
      - cod_serie
      - manzana_actual
      - predio_actual
      - cod_comuna  (o comuna_actual, lo mapea)

    insert_missing=False (recomendado): solo UPDATE a predios existentes.
    insert_missing=True: hace UPSERT (inserta si no existe, si tu tabla permite NULL en el resto).
    """
    import pandas as pd

    TARGET = TARGET_TABLE  # "public.predios"
    STG = "public.predios_cod_serie_stg"

    needed_any = ["manzana_actual", "predio_actual", "cod_serie"]
    for c in needed_any:
        if c not in df.columns:
            raise ValueError(f"El DataFrame debe incluir '{c}'")

    if ("cod_comuna" not in df.columns) and ("comuna_actual" not in df.columns):
        raise ValueError("El DataFrame debe incluir 'cod_comuna' o 'comuna_actual'")

    df = df.copy()

    # Map cod_comuna
    if "cod_comuna" not in df.columns:
        df["cod_comuna"] = df["comuna_actual"]

    # Tipos
    df["manzana_actual"] = pd.to_numeric(df["manzana_actual"], errors="coerce").astype("Int64")
    df["predio_actual"]  = pd.to_numeric(df["predio_actual"], errors="coerce").astype("Int64")

    # Strip cod_serie y cod_comuna
    df["cod_comuna"] = _safe_strip(df["cod_comuna"]).replace("", None)
    df["cod_serie"]  = _safe_strip(df["cod_serie"]).replace("", None)

    # Filtra mínimos
    df = df[
        df["cod_comuna"].notna() &
        df["manzana_actual"].notna() &
        df["predio_actual"].notna()
    ]
    if df.empty:
        print("No hay filas válidas para actualizar cod_serie.")
        return

    # Dedup por clave natural
    df = df.drop_duplicates(subset=["cod_comuna", "manzana_actual", "predio_actual"], keep="last")

    # Filtra comunas válidas (FK)
    conn = _get_conn()
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '0';")
            cur.execute("SELECT cod_comuna FROM public.comunas;")
            comunas_validas = set(r[0] for r in cur.fetchall())

        before = len(df)
        df = df[df["cod_comuna"].isin(comunas_validas)]
        after = len(df)
        print(f"Filas antes: {before}")
        print(f"Filas después de filtrar comunas válidas: {after}")
        if after == 0:
            print("No hay filas válidas para actualizar.")
            return

        # Orden estable
        df = df.sort_values(["cod_comuna", "manzana_actual", "predio_actual"], kind="stable")
        df = df.where(df.notnull(), None)

        # Crear staging
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '0';")
            cur.execute(f"DROP TABLE IF EXISTS {STG};")
            cur.execute(f"""
                CREATE UNLOGGED TABLE {STG} (
                    id BIGSERIAL PRIMARY KEY,
                    cod_comuna TEXT,
                    manzana_actual INTEGER,
                    predio_actual INTEGER,
                    cod_serie TEXT
                );
            """)
        conn.commit()

        cols = ["cod_comuna", "manzana_actual", "predio_actual", "cod_serie"]

        # COPY por chunks (local, no usa STAGING_TABLE global)
        total = len(df)
        chunk_size = 200000
        loaded = 0

        for start in range(0, total, chunk_size):
            end = min(start + chunk_size, total)
            df_chunk = df.iloc[start:end]

            buf = io.StringIO()
            df_chunk.to_csv(buf, index=False, header=False, na_rep="\\N", columns=cols)
            buf.seek(0)

            with conn.cursor() as cur:
                cur.execute("SET LOCAL synchronous_commit = OFF;")
                cur.execute("SET LOCAL statement_timeout = '0';")
                cur.copy_expert(
                    f"COPY {STG} ({', '.join(cols)}) "
                    "FROM STDIN WITH (FORMAT CSV, DELIMITER ',', NULL '\\N')",
                    buf,
                )
            conn.commit()

            loaded = end
            print(f"COPY a staging cod_serie: {loaded}/{total}")

        # Rango staging
        with conn.cursor() as cur:
            cur.execute(f"SELECT COALESCE(MIN(id),0), COALESCE(MAX(id),0) FROM {STG};")
            min_id, max_id = cur.fetchone()

        if min_id == 0 and max_id == 0:
            print("Staging vacía. Nada que actualizar.")
            return

        batch = 300000
        print(f"Iniciando {( 'UPSERT' if insert_missing else 'UPDATE' )} en lotes de {batch} filas...")

        if not insert_missing:
            # UPDATE ONLY
            sql = f"""
                UPDATE {TARGET} p
                SET cod_serie = s.cod_serie
                FROM {STG} s
                WHERE p.cod_comuna = s.cod_comuna
                  AND p.manzana_actual = s.manzana_actual
                  AND p.predio_actual = s.predio_actual
                  AND s.id BETWEEN %s AND %s;
            """
        else:
            # UPSERT (inserta si no existe) - OJO: solo usar si tu tabla permite NULL en otras columnas
            sql = f"""
                INSERT INTO {TARGET} (cod_comuna, manzana_actual, predio_actual, cod_serie)
                SELECT s.cod_comuna, s.manzana_actual, s.predio_actual, s.cod_serie
                FROM {STG} s
                WHERE s.id BETWEEN %s AND %s
                ON CONFLICT (cod_comuna, manzana_actual, predio_actual) DO UPDATE SET
                    cod_serie = EXCLUDED.cod_serie;
            """

        current = min_id
        while current <= max_id:
            upper = current + batch - 1
            with conn.cursor() as cur:
                cur.execute("SET LOCAL synchronous_commit = OFF;")
                cur.execute("SET LOCAL statement_timeout = '0';")
                _retrying_execute(cur, sql, (current, upper))
            conn.commit()
            print(f"Lote procesado hasta id {upper}")
            current = upper + 1

        print("Proceso cod_serie completado.")

        # Limpieza
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {STG};")
        conn.commit()
        print("Staging eliminada.")

    finally:
        conn.close()
