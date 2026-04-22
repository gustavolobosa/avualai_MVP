# preproces_info_construccion_no_agricola.py
import pandas as pd
import numpy as np
import os
import sys
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.insertar_info_construccion_no_agricola import insertar_info_construccion

# ========================
# CONFIG
# ========================
DIRECTORIO = '../datos/construcciones'
# ========================

pd.set_option('display.max_columns', None)

columnas = [
    'cod_comuna',
    'manzana_actual',
    'predio_actual',
    'correlativo_linea_constru',
    'cod_material',
    'cod_calidad',
    'anio_constru',              # viene así en el archivo
    'sup_constru',               # viene así en el archivo
    'cod_destino',               # no se usa para construcciones
    'cod_condicion_especial',
    'columna_invalida'
]

def procesar_archivo(filepath):
    print(f"\n📂 Procesando archivo: {filepath.name}")

    df = pd.read_csv(filepath, sep='|', names=columnas, dtype=str, index_col=False, encoding='latin1')

    # Numéricos
    for c in ['manzana_actual', 'predio_actual', 'correlativo_linea_constru', 'anio_constru', 'sup_constru']:
        df[c] = pd.to_numeric(df[c], errors='coerce').astype('Int64')

    # Limpia strings
    for c in ['cod_material', 'cod_calidad', 'cod_condicion_especial', 'cod_comuna']:
        df[c] = df[c].astype(str).str.strip()

    # cod_condicion_especial vacío -> NaN
    df['cod_condicion_especial'] = df['cod_condicion_especial'].replace('', np.nan)

    # clave_predio
    df['cod_comuna'] = df['cod_comuna'].str.zfill(5)
    df['clave_predio'] = (
        df['cod_comuna'] + '-' +
        df['manzana_actual'].astype('Int64').astype(str) + '-' +
        df['predio_actual'].astype('Int64').astype(str)
    )

    # Renombra para que coincida con tu tabla destino
    df = df.rename(columns={
        'anio_constru': 'anio_construccion',
        'sup_constru':  'sup_construccion'
    })

    # Quita columnas que no usaremos en construcciones
    df = df.drop(columns=[
        'columna_invalida', 'manzana_actual', 'predio_actual', 'cod_comuna', 'cod_destino'
    ])

    # Reemplaza NaN por None (para COPY como \N)
    df = df.where(pd.notnull(df), None)

    print(df.dtypes)
    print(f"Total filas: {len(df)}")
    print(f"Valores únicos en clave_predio: {df['clave_predio'].nunique()}")
    print(df.head())

    print("Iniciando inserción en construcciones...")
    insertar_info_construccion(df)
    print(f"✅ Inserción completada para {filepath.name}.")

def main():
    folder = Path(DIRECTORIO)
    archivos = sorted(folder.glob('*NL*'))

    if not archivos:
        print("⚠️ No se encontraron archivos NL en la carpeta:", folder)
        return

    print(f"🔍 Se encontraron {len(archivos)} archivos NL para procesar.\n")

    for file in archivos:
        if file.is_file():
            procesar_archivo(file)

    print("\n🎉 Proceso completado para todos los archivos.")

if __name__ == "__main__":
    main()
