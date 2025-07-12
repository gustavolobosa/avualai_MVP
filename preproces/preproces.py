import pandas as pd
import os
import json

filename = '../datos/BRTMPNACROL_NAC_2025_1'
parquet_file = 'datos_procesados.parquet'
json_por_predio_file = 'datos_por_predio_LAS_CONDES.json'
pd.set_option('display.max_columns', None)

if os.path.exists(parquet_file):
    # Cargar DataFrame desde archivo Parquet si ya existe
    df = pd.read_parquet(parquet_file)
else:
    colspecs = [
        (0, 5),    # Comuna Actual
        (5, 9),    # Año
        (9, 10),   # Semestre
        (10, 11),  # Indicador_de_aseo
        (17, 57),  # Direccion_predial
        (57, 62),  # Manzana_actual
        (62, 67),  # predio_actual
        (67, 68),  # Cod_serie
        (68, 81),  # Cuota_trimestra
        (81, 96),  # Avaluo_tot
        (96, 111), # Avaluo_ex
        (111, 115),# Año_termino_ex
        (115, 116),# Cod_ubi
        (116, 117) # Cod_destino
    ]

    column_names = [
        'Comuna Actual', 'Año', 'Semestre', 'Indicador_de_aseo', 'Direccion_predial',
        'Manzana_actual', 'predio_actual', 'Cod_serie', 'Cuota_trimestra',
        'Avaluo_tot', 'Avaluo_ex', 'Año_termino_ex', 'Cod_ubi', 'Cod_destino'
    ]


    
    df = pd.read_fwf(filename, colspecs=colspecs, names=column_names, encoding='utf-8')

    cols_to_int = [
        'Comuna Actual', 'Año', 'Semestre', 'Manzana_actual', 'Avaluo_ex',
        'predio_actual', 'Cuota_trimestra', 'Año_termino_ex', 'Avaluo_tot'
    ]

    for col in cols_to_int:
        df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
    df['clave_predio'] = df['predio_actual'].astype(str) + '-' + df['Manzana_actual'].astype(str) + '-' + df['Comuna Actual'].astype(str)

    print(df.dtypes)
    
    # si la columna aseo es nan reemplazarla por ""
    df['Indicador_de_aseo'] = df['Indicador_de_aseo'].fillna('')

    # Filtrar DataFrame para la comuna específica (por ejemplo, Las Condes con código 15108)
    df = df[(df['Comuna Actual'] == 15108) | (df['Comuna Actual'] == 7401)]
    # Guardar DataFrame procesado en archivo Parquet
    df.to_parquet(parquet_file)

# Verificar unicidad
print(f"Total filas: {len(df)}")
print(f"Valores únicos en clave_predio: {df['clave_predio'].nunique()}")

duplicados = df[df.duplicated(subset=['clave_predio'], keep=False)].sort_values(by='clave_predio')

print("Filas duplicadas según 'clave_predio':")
print(duplicados)

# Crear diccionario indexado por 'clave_predio'
dict_por_predio = df.set_index('clave_predio').to_dict(orient='index')

# Guardar diccionario en JSON para acceso rápido por predio
with open(json_por_predio_file, 'w', encoding='utf-8') as f:
    json.dump(dict_por_predio, f, ensure_ascii=False, indent=2)

print(f"Archivo JSON con índice por predio guardado en '{json_por_predio_file}'")

print(df.head())
