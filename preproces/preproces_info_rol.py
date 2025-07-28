import pandas as pd
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.insertar_info_rol import insertar_info_rol

# Ruta del archivo
filename = '../datos/BRORGA2441N_NAC_2025_1'
pd.set_option('display.max_columns', None)

# with open(filename, 'rb') as f:
#     for i, line in enumerate(f):
#         try:
#             line.decode('utf-8')
#         except UnicodeDecodeError as e:
#             print(line)
#             print(f"Error en línea {i + 1}: {e}")
#             break


# Leer el archivo con separador '|'
columnas = [
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

df = pd.read_csv(filename, sep='|', names=columnas, dtype=str, index_col=False, encoding='latin1')

# Convertir columnas numéricas
df[['manzana_actual', 'predio_actual', 'avaluo_fiscal_total', 'contribuciones_semana_con_aseo', 'sup_total', 'avaluo_exento', 'numero_manzana_bc1', 'numero_manzana_bc2', 'numero_predio_bc1', 'numero_predio_bc2']] = df[
    ['manzana_actual', 'predio_actual', 'avaluo_fiscal_total', 'contribuciones_semana_con_aseo', 'sup_total', 'avaluo_exento', 'numero_manzana_bc1', 'numero_manzana_bc2', 'numero_predio_bc1', 'numero_predio_bc2']
].apply(pd.to_numeric, errors='coerce').astype('Int64')

# Generar la clave_predio
df['clave_predio'] = df['cod_comuna'].astype(str) + '-' + df['manzana_actual'].astype(str) + '-' + df['predio_actual'].astype(str)
df['clave_predio_bien_comun_1'] = df['codigo_sii_comuna_bc1'].astype(str) + '-' + df['numero_manzana_bc1'].astype(str) + '-' + df['numero_predio_bc1'].astype(str)
df['clave_predio_bien_comun_2'] = df['codigo_sii_comuna_bc2'].astype(str) + '-' + df['numero_manzana_bc2'].astype(str) + '-' + df['numero_predio_bc2'].astype(str)

# Dejar como null los clave_predio_bien_comun_1 y clave_predio_bien_comun_2 quw tengan valores 00000-0-0
df.loc[df['clave_predio_bien_comun_1'] == '00000-0-0', 'clave_predio_bien_comun_1'] = None
df.loc[df['clave_predio_bien_comun_2'] == '00000-0-0', 'clave_predio_bien_comun_2'] = None

# Verificación rápida
print(df.dtypes)
print(f"Total filas: {len(df)}")
print(f"Valores únicos en clave_predio: {df['clave_predio'].nunique()}")

# Eliminar columna inválida
df = df.drop(columns=['cod_destino', 'manzana_actual', 'predio_actual', 'cod_comuna', 'direccion_predial', 'invalida1', 'invalida2', 'invalida3', 'invalida4', 'codigo_sii_comuna_bc1', 'numero_manzana_bc1', 'numero_predio_bc1', 'codigo_sii_comuna_bc2', 'numero_manzana_bc2', 'numero_predio_bc2'])

print(df.head())
#Insertar en la base de datos
print("Iniciando inserción en info_rol...")
insertar_info_rol(df)
print("✅ Inserción completada.")
