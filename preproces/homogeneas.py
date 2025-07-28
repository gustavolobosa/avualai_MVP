import os
import pdfplumber
import re
import pandas as pd

def extraer_codigo_area(bloque):
    match = re.search(r'CÓDIGO ÁREA HOMOGÉNEA:\s*((?:[A-Z]\s*)+\d+)', bloque)
    if match:
        crudo = match.group(1)
        limpio = crudo.replace(" ", "")  # Eliminar los espacios: "H B B 1" → "HBB1"
        return limpio
    return None

def extraer_fichas(path_pdf):
    fichas = []
    with pdfplumber.open(path_pdf) as pdf:
        for page in pdf.pages:
            texto = page.extract_text()
            bloques = texto.split("IDENTIFICACIÓN DEL AH")

            for bloque in bloques[1:]:
                ficha = {}
                print(bloque)  # Muestra los primeros 30 caracteres del bloque
                region = re.search(r'REGIÓN:\s*(.*?)\n', bloque)
                comuna = re.search(r'NOMBRE DE LA COMUNA:\s*(.*?)\n', bloque)
                codigo = extraer_codigo_area(bloque)
                tipo = re.search(r'TIPO DE EMPLAZAMIENTO:\s*(.*?)\n', bloque)
                condiciones = re.search(r'CONDICIONES PARTICULARES DEL ÁREA HOMOGÉNEA\n.*?\n(.*?)\n', bloque, re.DOTALL)
                obs = re.search(r'OBSERVACIONES Y/O CARACTERÍSTICAS:\s*\n?(.*?)(?=\nINSTRUMENTO DE PLANIFICACIÓN TERRITORIAL)', bloque, re.DOTALL)


                ficha['Región'] = region.group(1).strip() if region else ''
                ficha['Comuna'] = comuna.group(1).strip() if comuna else ''
                ficha['Código AH'] = codigo if codigo else ''
                ficha['Emplazamiento'] = tipo.group(1).strip() if tipo else ''
                ficha['Condiciones Particulares'] = condiciones.group(1).strip() if condiciones else ''
                ficha['Observaciones'] = obs.group(1).strip() if obs else ''


                fichas.append(ficha)
    return fichas

def procesar_carpeta(carpeta_pdf):
    todas_fichas = []
    for archivo in os.listdir(carpeta_pdf):
        if archivo.endswith('.pdf'):
            path = os.path.join(carpeta_pdf, archivo)
            print(f"📄 Procesando: {archivo}")
            fichas = extraer_fichas(path)
            todas_fichas.extend(fichas)
    return todas_fichas

# Ejecutar todo
carpeta = 'scraper/descargas/homogeneas'
fichas_total = procesar_carpeta(carpeta)

# Guardar como Excel
df = pd.DataFrame(fichas_total)
df.to_excel("fichas_homogeneas_completas.xlsx", index=False)
print("✅ Guardado como fichas_homogeneas_completas.xlsx")
