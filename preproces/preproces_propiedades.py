import pandas as pd
import os
import sys
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.insertar_predios import insertar_predios

def detectar_errores_utf8(df):
    errores = []

    for col in df.select_dtypes(include='object').columns:
        for i, val in df[col].items():
            try:
                if isinstance(val, str):
                    val.encode('utf-8')
            except UnicodeEncodeError:
                errores.append((i, col, val))

    return errores


filename = '../datos/BRTMPNACROL_NAC_2025_1'

pd.set_option('display.max_columns', None)

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
    'Manzana_actual', 'predio_actual', 'Cod_serie', 'Cuota_trimestral',
    'Avaluo_tot', 'Avaluo_ex', 'Año_termino_ex', 'Cod_ubi', 'Cod_destino'
]



df = pd.read_fwf(filename, colspecs=colspecs, names=column_names, encoding='utf-8')
df['Comuna Actual'] = df['Comuna Actual'].astype(str).str.zfill(5)

cols_to_int = [
    'Año', 'Semestre', 'Manzana_actual', 'Avaluo_ex',
    'predio_actual', 'Cuota_trimestral', 'Año_termino_ex', 'Avaluo_tot'
]

for col in cols_to_int:
    df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
df['clave_predio'] = df['Comuna Actual'].astype(str) + '-' + df['Manzana_actual'].astype(str) + '-' + df['predio_actual'].astype(str)

print(df.dtypes)

# si la columna aseo es nan reemplazarla por ""
df['Indicador_de_aseo'] = df['Indicador_de_aseo'].fillna('')


# Verificar unicidad
print(f"Total filas: {len(df)}")
print(f"Valores únicos en clave_predio: {df['clave_predio'].nunique()}")

duplicados = df[df.duplicated(subset=['clave_predio'], keep=False)].sort_values(by='clave_predio')

print("Filas duplicadas según 'clave_predio':")
print(duplicados)

# Guardar diccionario en JSON para acceso rápido por predio
print("iniciando funcion insertar_predios")

errores = detectar_errores_utf8(df)
print("Errores de codificación UTF-8 detectados:")
print(f"Total de errores detectados: {len(errores)}")
for fila, columna, valor in errores:
    print(f"❌ Error en fila {fila}, columna '{columna}': {repr(valor)}")

#solo dejar los que no contienen A en la columna cod_serie
df = df[~df['Cod_serie'].str.contains('A', na=False)]

print(len(df))

insertar_predios(df)
print("✅ Datos insertados en la base de datos.")


print(df.head())
