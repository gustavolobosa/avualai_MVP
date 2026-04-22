import os
import io
import time
import psycopg2
from psycopg2 import OperationalError
from dotenv import load_dotenv

load_dotenv()

# ========================
# Config
# ========================
TARGET_TABLE  = "public.avaluo_periodo"
STAGING_TABLE = "public.avaluo_periodo_stg"

# Si True: UPSERT (actualiza); si False: DO NOTHING
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
# Carga: AVALUO_PERIODO
# ========================
def insertar_avaluo_periodo(df):
    """
    Pobla 'public.avaluo_periodo' uniendo contra 'public.predios' para obtener predio_id.
    Clave de conflicto: (predio_id, anio, semestre).

    Columnas esperadas en df (se crean si faltan):
      - comuna_actual, manzana_actual, predio_actual    (para resolver predio_id)
      - anio, semestre
      - avaluo_tot -> avaluo_tot
      - avaluo_ex  -> avaluo_ex
      - cuota_trimestral
      - cod_destino, cod_serie, indicador_de_aseo
      - anio_termino_ex   (opcional)
    """
    import pandas as pd

    # Normaliza columnas de origen (si faltan, crea nulas)
    needed = [
        "comuna_actual", "manzana_actual", "predio_actual",
        "anio", "semestre",
        "avaluo_tot", "avaluo_ex", "cuota_trimestral",
        "cod_destino", "cod_serie", "indicador_de_aseo", "anio_termino_ex", "cod_ubi",
    ]
    df = df.copy()
    

    
    for c in needed:
        if c not in df.columns:
            df[c] = None

    # Tipos y limpieza
    df["cod_comuna"] = (
        df.get("comuna_actual")
        .astype(str)
        .str.strip()
        .str.zfill(5)
    )
    # semestre 1/2
    df["semestre"] = (
        df["semestre"]
        .fillna(1)
        .astype("Int64")
        .clip(lower=1, upper=2)
    )
    # ints/bigints
    for c in ["anio", "manzana_actual", "predio_actual", "avaluo_tot", "avaluo_ex", "cuota_trimestral", "anio_termino_ex"]:
        df[c] = df[c].astype("Int64").where(df[c].notnull(), None)

    # Filtra comunas válidas
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

        # Dedup dentro del mismo comando por clave natural de período
        df = df.drop_duplicates(
            subset=["cod_comuna", "manzana_actual", "predio_actual", "anio", "semestre"],
            keep="last"
        )

        # Crear staging (guarda la clave natural + valores de período)
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '0';")
            cur.execute(f"DROP TABLE IF EXISTS {STAGING_TABLE};")
            cur.execute(f"""
                CREATE UNLOGGED TABLE {STAGING_TABLE} (
                    id BIGSERIAL PRIMARY KEY,
                    cod_comuna TEXT,
                    manzana_actual INTEGER,
                    predio_actual INTEGER,
                    anio INTEGER,
                    semestre SMALLINT,
                    avaluo_tot BIGINT,
                    avaluo_ex BIGINT,
                    cuota_trimestral BIGINT,
                    cod_destino TEXT,
                    cod_serie TEXT,
                    cod_ubi TEXT,
                    indicador_de_aseo TEXT,
                    anio_termino_ex INTEGER
                );
            """)
        conn.commit()

        # Proyección a columnas de staging
        df_stg = pd.DataFrame({
            "cod_comuna": df["cod_comuna"],
            "manzana_actual": df["manzana_actual"],
            "predio_actual": df["predio_actual"],
            "anio": df["anio"],
            "semestre": df["semestre"],
            "avaluo_tot": df["avaluo_tot"],
            "avaluo_ex": df["avaluo_ex"],
            "cuota_trimestral": df["cuota_trimestral"],
            "cod_destino": df["cod_destino"],
            "cod_serie": df["cod_serie"],
            "cod_ubi": df["cod_ubi"],
            "indicador_de_aseo": df["indicador_de_aseo"],
            "anio_termino_ex": df["anio_termino_ex"],
        })

        cols = list(df_stg.columns)

        # COPY por chunks
        chunk_size = int(200000)
        total = len(df_stg)
        loaded = 0

        # Orden estable opcional
        df_stg = df_stg.sort_values(["cod_comuna", "manzana_actual", "predio_actual", "anio", "semestre"], kind="stable")

        for start in range(0, total, chunk_size):
            end = min(start + chunk_size, total)
            df_chunk = df_stg.iloc[start:end]
            with conn.cursor() as cur:
                cur.execute("SET LOCAL synchronous_commit = OFF;")
                cur.execute("SET LOCAL statement_timeout = '0';")
                _copy_chunk(cur, df_chunk, cols)
            conn.commit()
            loaded = end
            print(f"COPY a staging: {loaded}/{total}")

        # INSERT/UPSERT → resolviendo predio_id por JOIN a predios
        insert_batch = int(300000)
        print(f"Iniciando INSERT en lotes de {insert_batch} filas...")

        with conn.cursor() as cur:
            cur.execute(f"SELECT COALESCE(MIN(id),0), COALESCE(MAX(id),0) FROM {STAGING_TABLE};")
            min_id, max_id = cur.fetchone()

        if UPSERT_MODE:
            upsert_sql = """
            ON CONFLICT (predio_id, anio, semestre) DO UPDATE SET
                avaluo_tot = EXCLUDED.avaluo_tot,
                avaluo_ex       = EXCLUDED.avaluo_ex,
                cuota_trimestral    = EXCLUDED.cuota_trimestral,
                cod_destino         = EXCLUDED.cod_destino,
                cod_serie           = EXCLUDED.cod_serie,
                cod_ubi             = EXCLUDED.cod_ubi,
                indicador_de_aseo   = EXCLUDED.indicador_de_aseo,
                anio_termino_ex     = EXCLUDED.anio_termino_ex
            """
        else:
            upsert_sql = "ON CONFLICT (predio_id, anio, semestre) DO NOTHING"

        base_insert = f"""
            INSERT INTO {TARGET_TABLE} (
                predio_id, anio, semestre,
                avaluo_tot, avaluo_ex, cuota_trimestral,
                cod_destino, cod_serie, indicador_de_aseo, anio_termino_ex, cod_ubi
            )
            SELECT
                p.predio_id,
                s.anio,
                s.semestre,
                s.avaluo_tot,
                s.avaluo_ex,
                s.cuota_trimestral,
                s.cod_destino,
                s.cod_serie,
                s.indicador_de_aseo,
                s.anio_termino_ex,
                s.cod_ubi
            FROM {STAGING_TABLE} s
            JOIN public.predios p
              ON p.cod_comuna = s.cod_comuna
             AND p.manzana_actual = s.manzana_actual
             AND p.predio_actual  = s.predio_actual
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

        print("✅ Inserción a avaluo_periodo completada.")

        # Limpieza
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {STAGING_TABLE};")
        conn.commit()
        print("🧹 STAGING eliminada. Proceso finalizado.")

    finally:
        conn.close()
