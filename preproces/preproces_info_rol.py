# preproces_info_rol.py
import pandas as pd
import os
import sys
from pathlib import Path
from charset_normalizer import from_path

# Importa la función insertar_info_rol
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.insertar_info_rol import insertar_info_rol

# ========================
# CONFIG
# ========================
DIRECTORIO = '../datos/info_rol'
CHUNK_SIZE = 200_000  # ajusta según tu RAM
# ========================

COLUMNAS = [
    'cod_comuna',
    'manzana_actual',
    'predio_actual',
    'direccion_predial',
    'avaluo_fiscal_total',
    'contribuciones_semana_con_aseo',
    'cod_destino',
    'avaluo_exento',
    'codigo_sii_comuna_bc1',
    'numero_manzana_bc1',
    'numero_predio_bc1',
    'codigo_sii_comuna_bc2',
    'numero_manzana_bc2',
    'numero_predio_bc2',
    'sup_total',
    'invalida1',
    'invalida2',
    'invalida3',
    'invalida4'
]

# ========================
# Utilidades
# ========================
def detect_encoding(path: Path) -> str:
    """Detecta la codificación del archivo."""
    result = from_path(str(path)).best()
    enc = result.encoding if result else "latin-1"
    print(f"Detected encoding for {path.name}: {enc}")
    return enc

def transformar_chunk(df: pd.DataFrame) -> pd.DataFrame:
    # Normaliza tipos
    df['cod_comuna'] = df['cod_comuna'].astype(str).str.strip().str.zfill(5)
    
        # extract the anio from BRORGA2441N_NAC_2025_1
    

    # Numéricos -> Int64
    num_cols = [
        'manzana_actual', 'predio_actual',
        'avaluo_fiscal_total', 'contribuciones_semana_con_aseo',
        'sup_total', 'avaluo_exento',
        'numero_manzana_bc1', 'numero_manzana_bc2',
        'numero_predio_bc1', 'numero_predio_bc2'
    ]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').astype('Int64')

    # Generar claves
    df['clave_predio'] = (
        df['cod_comuna'].astype(str) + '-' +
        df['manzana_actual'].astype('Int64').astype(str) + '-' +
        df['predio_actual'].astype('Int64').astype(str)
    )

    df['clave_predio_bien_comun_1'] = (
        df['codigo_sii_comuna_bc1'].astype(str).str.strip().str.zfill(5) + '-' +
        df['numero_manzana_bc1'].astype('Int64').astype(str) + '-' +
        df['numero_predio_bc1'].astype('Int64').astype(str)
    )
    df['clave_predio_bien_comun_2'] = (
        df['codigo_sii_comuna_bc2'].astype(str).str.strip().str.zfill(5) + '-' +
        df['numero_manzana_bc2'].astype('Int64').astype(str) + '-' +
        df['numero_predio_bc2'].astype('Int64').astype(str)
    )

    # Normaliza claves “00000-0-0” a None
    df.loc[df['clave_predio_bien_comun_1'] == '00000-0-0', 'clave_predio_bien_comun_1'] = None
    df.loc[df['clave_predio_bien_comun_2'] == '00000-0-0', 'clave_predio_bien_comun_2'] = None

    # Deja solo las columnas que tu función insertar_info_rol espera
    # (según tu inserción actual)
    cols_keep = [
        'clave_predio',
        'anio',
        'semestre',
        'avaluo_fiscal_total',
        'avaluo_exento',
        'contribuciones_semana_con_aseo',
        'sup_total',
        'clave_predio_bien_comun_1',
        'clave_predio_bien_comun_2',
        'cod_ubicacion',
        'cod_destino'
    ]
    df = df[cols_keep]

    return df

def procesar_archivo(filepath: Path):
    """Procesa un archivo delimitado por '|' en chunks y lo inserta en info_rol."""
    print(f"\n📂 Procesando archivo: {filepath.name}")

    total_leidas = 0
    total_insertadas = 0
    anio = filepath.name[-6:-2]
    semestre = filepath.name[-1]

    try:
        reader = pd.read_csv(
            filepath,
            sep='|',
            names=COLUMNAS,
            dtype=str,
            index_col=False,
            encoding='cp1250', #detect_encoding(filepath),
            chunksize=CHUNK_SIZE
        )

    except Exception as e:
        print(f"❌ Error leyendo {filepath.name}: {e}")
        return

    for i, chunk in enumerate(reader, start=1):
        total_leidas += len(chunk)
        print(f"\n  [Chunk {i}] Filas leídas: {len(chunk)}")
        
        chunk['anio'] = int(anio)
        chunk['semestre'] = int(semestre)
        print('****')
        print(chunk.head(1))

        chunk = transformar_chunk(chunk)

        # Métricas rápidas (opcional)
        print(f"  [Chunk {i}] columnas -> {list(chunk.columns)}")
        print(f"  [Chunk {i}] claves únicas -> {chunk['clave_predio'].nunique()}")

        try:
            insertar_info_rol(chunk)
            total_insertadas += len(chunk)
            print(f"  [Chunk {i}] ✅ Insertadas: {len(chunk)} (acumulado: {total_insertadas})")
        except Exception as e:
            print(f"  ❌ Error insertando chunk {i} de {filepath.name}: {e}")

    print(f"\n✅ Archivo {filepath.name} finalizado. {total_insertadas} filas insertadas de {total_leidas} leídas.")

# ========================
# MAIN
# ========================
def main():
    folder = Path(DIRECTORIO)
    archivos = sorted([p for p in folder.glob('*') if p.is_file()])

    if not archivos:
        print("⚠️ No se encontraron archivos en la carpeta:", folder)
        return

    print(f"🔍 Se encontraron {len(archivos)} archivos para procesar.\n")

    for file in archivos:
        procesar_archivo(file)

    print("\n🎉 Proceso completado para todos los archivos.")

if __name__ == "__main__":
    main()
