import pandas as pd
import os
import sys
import traceback
from pathlib import Path
from charset_normalizer import from_path

# Importa la función insertar_propiedades
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.insertar_predios import actualizar_cod_serie_predios, insertar_predios
from models.insertar_avaluo_periodos import insertar_avaluo_periodo

# ========================
# CONFIG
# ========================
DIRECTORIO = '../datos/predios'
CHUNK_SIZE = 200_000  # ajusta según tu RAM
# ========================

COLSPECS = [
    (0, 5),    # comuna_actual
    (5, 9),    # anio
    (9, 10),   # semestre
    (10, 11),  # indicador_de_aseo
    (17, 57),  # direccion_predial
    (57, 62),  # manzana_actual
    (62, 67),  # predio_actual
    (67, 68),  # cod_serie
    (68, 81),  # cuota_trimestral
    (81, 96),  # avaluo_tot
    (96, 111), # avaluo_ex
    (111, 115),# anio_termino_ex
    (115, 116),# cod_ubi
    (116, 117) # cod_destino
]

COLUMN_NAMES = [
    'comuna_actual', 'anio', 'semestre', 'indicador_de_aseo', 'direccion_predial',
    'manzana_actual', 'predio_actual', 'cod_serie', 'cuota_trimestral',
    'avaluo_tot', 'avaluo_ex', 'anio_termino_ex', 'cod_ubi', 'cod_destino'
]

# ========================
# Funciones auxiliares
# ========================
def detect_encoding(path: str) -> str:
    """Detecta la codificación del archivo."""
    result = from_path(path).best()
    print(f"Detected encoding for {path.name}: {result.encoding}")
    return result.encoding if result else "latin-1"

def transformar_chunk(df: pd.DataFrame) -> pd.DataFrame:
    df['comuna_actual'] = df['comuna_actual'].astype(str).str.strip().str.zfill(5)
    for col in ['anio', 'semestre', 'manzana_actual', 'predio_actual',
                'cuota_trimestral', 'avaluo_tot', 'avaluo_ex', 'anio_termino_ex']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
    if 'indicador_de_aseo' in df.columns:
        df['indicador_de_aseo'] = df['indicador_de_aseo'].fillna('')
    df['clave_predio'] = (
        df['comuna_actual'].astype(str).str.strip() + '-' +
        df['manzana_actual'].astype('Int64').astype(str).str.strip() + '-' +
        df['predio_actual'].astype('Int64').astype(str).str.strip()
    )
    if 'cod_serie' in df.columns:
        df['cod_serie'] = df['cod_serie'].astype(str).str.strip().str.upper()
        df = df[df['cod_serie'].eq('A')]

    return df

def procesar_archivo(filepath: Path):
    """Procesa un archivo FWF grande en chunks y lo inserta."""
    print(f"\n📂 Procesando archivo: {filepath.name}")


    total_leidas = 0
    total_insertadas = 0

    try:
        reader = pd.read_fwf(
            filepath,
            colspecs=COLSPECS,
            names=COLUMN_NAMES,
            encoding='latin-1',
            chunksize=CHUNK_SIZE
        )
    except Exception as e:
        print(f"❌ Error leyendo {filepath.name}: {e}")
        return

    for i, chunk in enumerate(reader, start=1):
        total_leidas += len(chunk)
        print(f"\n  [Chunk {i}] Filas leídas: {len(chunk)}")
        chunk = transformar_chunk(chunk)
        try:
            #insertar_predios(chunk)
            insertar_avaluo_periodo(chunk)
            #actualizar_cod_serie_predios(chunk, insert_missing=False)
            total_insertadas += len(chunk)
            print(f"  [Chunk {i}] ✅ Insertadas: {len(chunk)} (acumulado: {total_insertadas})")
        except Exception as e:
            print(f"  ❌ Error insertando chunk {i} de {filepath.name}: {e}")
            traceback.print_exc()

    print(f"\n✅ Archivo {filepath.name} finalizado. {total_insertadas} filas insertadas de {total_leidas} leídas.")

# ========================
# MAIN
# ========================
def main():
    folder = Path(DIRECTORIO)
    archivos = sorted(folder.glob('*'))  # todos los archivos dentro de la carpeta

    if not archivos:
        print("⚠️ No se encontraron archivos en la carpeta:", folder)
        return

    print(f"🔍 Se encontraron {len(archivos)} archivos para procesar.\n")

    for file in archivos:
        if file.is_file():
            procesar_archivo(file)

    print("\n🎉 Proceso completado para todos los archivos.")

if __name__ == "__main__":
    main()
