# preproces_info_construccion.py
import pandas as pd
import numpy as np
import os
import sys
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.insertar_info_cosntruccion_agricolas import insertar_info_construccion_agricola, actualizar_sup_suelo

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
    'cod_suelo',
    'sup_suelo',
    'correlativo_linea_constru',
    'cod_material',
    'cod_calidad',
    'sup_constru',
    'cod_destino',
    'cod_condicion_especial',
    'num_pisos'
]

def procesar_archivo(filepath):
    print(f"\n📂 Procesando archivo: {filepath.name}")

    df = pd.read_csv(filepath, sep='|', names=columnas, dtype=str, index_col=False, encoding='latin1')

    # Numéricos
    for c in ['manzana_actual', 'predio_actual', 'correlativo_linea_constru', 'sup_constru', 'num_pisos', 'sup_suelo']:
        df[c] = pd.to_numeric(df[c], errors='coerce').astype('Int64')

    # Limpia strings
    for c in ['cod_material', 'cod_calidad', 'cod_condicion_especial', 'cod_comuna', 'cod_destino', 'cod_suelo']:
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
    df['anio_construccion'] = 0000
    df['sup_suelo'] = df['sup_suelo'].astype('Int64')
    df['sup_suelo'] = df['sup_suelo'] * 100

    # Renombra para que coincida con tu tabla destino
    df = df.rename(columns={
        'sup_constru':  'sup_construccion'
    })

    # Quita columnas que no usaremos en construcciones
    df = df.drop(columns=[
        'manzana_actual', 'predio_actual', 'cod_comuna'
    ])

    # cod_suelo: asegurar que no sea None/NaN (la PK parcial lo necesita)
    df['cod_suelo'] = df['cod_suelo'].fillna('')

    # Reemplaza NaN por None (para COPY como \N)
    df = df.where(pd.notnull(df), None)
    # Restaurar cod_suelo vacío (no debe ser None)
    df['cod_suelo'] = df['cod_suelo'].fillna('')

    print(df.dtypes)
    print(f"Total filas: {len(df)}")
    print(f"Valores únicos en clave_predio: {df['clave_predio'].nunique()}")
    print(df.head())

    print("Iniciando inserción en construcciones...")
    insertar_info_construccion_agricola(df)
    print(f"✅ Inserción completada para {filepath.name}.")

def main():
    folder = Path(DIRECTORIO)
    archivos = sorted(folder.glob('*AL*'))

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
