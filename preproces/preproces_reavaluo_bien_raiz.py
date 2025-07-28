import os
import pdfplumber
import pandas as pd

def extraer_region_comuna(nombre_archivo):
    base = os.path.basename(nombre_archivo).replace('.pdf', '')
    partes = base.split('_')
    if len(partes) >= 3:
        region = partes[1]
        comuna = '_'.join(partes[2:])
        return region, comuna
    return '', ''

def extraer_tablas_con_region_comuna(carpeta):
    salida = []
    for archivo in os.listdir(carpeta):
        if archivo.endswith('.pdf'):
            path_pdf = os.path.join(carpeta, archivo)
            region, comuna = extraer_region_comuna(archivo)

            with pdfplumber.open(path_pdf) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    for table in tables:
                        for fila in table:
                            if any(cell is not None for cell in fila):
                                salida.append(fila + [region, comuna])
                        break
    return salida

# Ejecutar
carpeta_descargas = 'scraper/descargas/reavaluos'
datos = extraer_tablas_con_region_comuna(carpeta_descargas)

# Convertir a DataFrame
df = pd.DataFrame(datos, columns=['Código', 'Rango Sup.', 'Valor Unitario ($/m2)', 'Región', 'Comuna'])
df = df[~df['Código'].str.contains('Código Área', na=False)]

# Guardar en Excel
df.to_excel('tabla_reavaluo_completa.xlsx', index=False)
print("✅ Archivo guardado como tabla_reavaluo_completa.xlsx")
