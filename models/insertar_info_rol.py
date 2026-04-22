# models/actualizar_superficie_periodo.py
import os
import io
import time
import psycopg2
from psycopg2 import OperationalError
from dotenv import load_dotenv

load_dotenv()

TARGET_TABLE  = "public.avaluo_periodo"
STAGING_TABLE = "public.superficie_periodo_stg"

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

def insertar_info_rol(df):
    """
    Actualiza public.avaluo_periodo.superficie_total a partir de un DataFrame con, al menos:
      - clave_predio
      - sup_total o superficie_total   (ambos aceptados)
    Opcionalmente:
      - anio
      - semestre

    Reglas:
      - Si el DF trae anio+semestre: se actualiza ese período específico.
      - Si NO trae anio+semestre: se actualizan todas las filas del predio con superficie_total IS NULL.
    """
    import pandas as pd

    if "clave_predio" not in df.columns:
        raise ValueError("El DataFrame debe incluir 'clave_predio'")

    df = df.copy()

    # Normaliza nombre de superficie
    if "superficie_total" in df.columns:
        df["superficie_total"] = pd.to_numeric(df["superficie_total"], errors="coerce").astype("Int64")
    elif "sup_total" in df.columns:
        df["superficie_total"] = pd.to_numeric(df["sup_total"], errors="coerce").astype("Int64")
    else:
        raise ValueError("El DataFrame debe incluir 'superficie_total' o 'sup_total'")

    # anio/semestre opcionales (para scope de actualización)
    has_periodo = ("anio" in df.columns) and ("semestre" in df.columns)
    if has_periodo:
        df["anio"] = pd.to_numeric(df["anio"], errors="coerce").astype("Int64")
        df["semestre"] = (
            pd.to_numeric(df["semestre"], errors="coerce")
              .astype("Int64")
              .clip(lower=1, upper=2)
        )

    # Drop nulos de clave_predio o superficie (no hay nada que actualizar)
    df = df[df["clave_predio"].notna() & df["superficie_total"].notna()]
    if df.empty:
        print("No hay filas válidas para actualizar superficie_total.")
        return

    # Dedup por (clave_predio[, anio, semestre]) -> usa la última
    subset_keys = ["clave_predio"]
    if has_periodo:
        subset_keys += ["anio", "semestre"]
    df = df.drop_duplicates(subset=subset_keys, keep="last")

    conn = _get_conn()
    conn.autocommit = False
    try:
        # staging: guardamos clave_predio, superficie_total y periodo opcional
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '0';")
            cur.execute(f"DROP TABLE IF EXISTS {STAGING_TABLE};")
            cur.execute(f"""
                CREATE UNLOGGED TABLE {STAGING_TABLE} (
                    id BIGSERIAL PRIMARY KEY,
                    clave_predio TEXT NOT NULL,
                    superficie_total INTEGER,
                    anio INTEGER,
                    semestre SMALLINT
                );
            """)
        conn.commit()

        # Proyección a staging
        df_stg = pd.DataFrame({
            "clave_predio": df["clave_predio"].astype(str),
            "superficie_total": df["superficie_total"].astype("Int64"),
            "anio": df["anio"] if has_periodo else None,
            "semestre": df["semestre"] if has_periodo else None,
        })

        cols = list(df_stg.columns)

        # COPY (puedes chunkear si es muy grande)
        with conn.cursor() as cur:
            cur.execute("SET LOCAL synchronous_commit = OFF;")
            cur.execute("SET LOCAL statement_timeout = '0';")
            _copy_chunk(cur, df_stg, cols)
        conn.commit()
        print(f"COPY a staging: {len(df_stg)} filas")

        # 1) si tenemos periodo en staging: actualiza ese período exacto
        sql_update_periodo = f"""
            UPDATE {TARGET_TABLE} ap
            SET superficie_total = s.superficie_total
            FROM {STAGING_TABLE} s
            JOIN public.predios p ON p.clave_predio = s.clave_predio
            WHERE ap.predio_id = p.predio_id
              AND s.anio IS NOT NULL
              AND s.semestre IS NOT NULL
              AND ap.anio = s.anio
              AND ap.semestre = s.semestre
        """

        # 2) si NO tenemos periodo: actualiza filas del predio que estén NULL
        sql_update_nulls = f"""
            UPDATE {TARGET_TABLE} ap
            SET superficie_total = s.superficie_total
            FROM {STAGING_TABLE} s
            JOIN public.predios p ON p.clave_predio = s.clave_predio
            WHERE ap.predio_id = p.predio_id
              AND (s.anio IS NULL OR s.semestre IS NULL)
              AND ap.superficie_total IS NULL
        """

        with conn.cursor() as cur:
            cur.execute("SET LOCAL synchronous_commit = OFF;")
            cur.execute("SET LOCAL statement_timeout = '0';")
            # ejecuta ambos; cada uno solo afecta sus filas aplicables
            _retrying_execute(cur, sql_update_periodo)
            _retrying_execute(cur, sql_update_nulls)
        conn.commit()
        print("✅ superficie_total actualizada en avaluo_periodo.")

        # limpieza
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {STAGING_TABLE};")
        conn.commit()
        print("🧹 STAGING eliminada.")
    finally:
        conn.close()
