import pandas as pd
import numpy as np
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.insertar_info_construccion import insertar_info_construccion

# Ruta del archivo
filename = '../datos/BRORGA2441NL_NAC_2025_1'
pd.set_option('display.max_columns', None)


# Leer el archivo con separador '|'
columnas = [
    'cod_comuna',
    'manzana_actual',
    'predio_actual',
    'correlativo_linea_constru',
    'cod_material',
    'cod_calidad',
    'anio_constru',
    'sup_constru',
    'cod_destino',
    'cod_condicion_especial',
    'columna_invalida'
]

df = pd.read_csv(filename, sep='|', names=columnas, dtype=str, index_col=False)

# Convertir columnas numéricas
df[['manzana_actual', 'predio_actual', 'correlativo_linea_constru', 'anio_constru', 'sup_constru']] = df[
    ['manzana_actual', 'predio_actual', 'correlativo_linea_constru', 'anio_constru', 'sup_constru']
].apply(pd.to_numeric, errors='coerce').astype('Int64')

#delete blank spaces in thee rigth of cod_materal, cod_calidad, cod_condicion_especial
df['cod_material'] = df['cod_material'].str.strip()
df['cod_calidad'] = df['cod_calidad'].str.strip()
df['cod_condicion_especial'] = df['cod_condicion_especial'].str.strip()

df['cod_condicion_especial'] = df['cod_condicion_especial'].str.strip().replace('', np.nan)

# Generar la clave_predio
df['clave_predio'] = df['cod_comuna'].astype(str) + '-' + df['manzana_actual'].astype(str) + '-' + df['predio_actual'].astype(str)
df = df.where(pd.notnull(df), None)

# Verificación rápida
print(df.dtypes)
print(f"Total filas: {len(df)}")
print(f"Valores únicos en clave_predio: {df['clave_predio'].nunique()}")

# Eliminar columna inválida
df = df.drop(columns=['columna_invalida', 'manzana_actual', 'predio_actual', 'cod_comuna', 'cod_destino'])

print(df.head())
# Insertar en la base de datos
print("Iniciando inserción en info_rol_construccion...")
insertar_info_construccion(df)
print("✅ Inserción completada.")
