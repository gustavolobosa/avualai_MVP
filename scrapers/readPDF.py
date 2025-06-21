import sys
import fitz  # PyMuPDF
import re
import json

def extraer_avaluo(path_pdf):
    doc = fitz.open(path_pdf)
    texto = ""
    for pagina in doc:
        texto += pagina.get_text()

    match = re.search(r'AVAL[ÚU]O TOTAL al (primer|segundo) semestre de (\d{4})\s*:\$\s*([\d\.\,]+)', texto)
    if match:
        semestre = 1 if match.group(1) == 'primer' else 2
        año = int(match.group(2))
        valor_str = match.group(3).replace('.', '').replace(',', '')
        valor = int(valor_str)
        return (año, semestre, valor)
    return None

def procesar_archivos(archivos):
    resultados = []

    for path in archivos:
        res = extraer_avaluo(path)
        if res:
            resultados.append(res)

    resultados.sort()
    return resultados

if __name__ == '__main__':
    archivos = sys.argv[1:]
    resultados = procesar_archivos(archivos)

    if not resultados:
        print("No se encontraron datos válidos.")
        sys.exit(0)

    anterior = None
    etiquetas = []
    valores = []

    for año, semestre, valor in resultados:
        label = f"{año} - {semestre}"
        etiquetas.append(label)
        valores.append(valor)

    print(json.dumps({"labels": etiquetas, "values": valores}))
