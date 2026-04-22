import os
import pdfplumber
import re
import pandas as pd


def extraer_codigo_area(bloque):
    m = re.search(r'(?:CÓDIGO ÁREA HOMOGÉNEA|CÓDIGO AH)\s*:\s*((?:[A-Z]\s*)+\d+)', bloque, re.IGNORECASE)

    if not m:
        return None
    crudo = m.group(1).replace(" ", "")
    letras = ''.join(filter(str.isalpha, crudo))
    numeros = ''.join(filter(str.isdigit, crudo)).zfill(3)
    return letras + numeros

def parsear_ipt_flags(bloque):
    seccion = re.search(
        r'INSTRUMENTO DE PLANIFICACIÓN TERRITORIAL(.*?)(?:\nCONDICIONES PARTICULARES DEL ÁREA HOMOGÉNEA|\nFORMA TOPOGRAFÍA|\nOBSERVACIONES Y/O CARACTERÍSTICAS:|$)',
        bloque, re.DOTALL
    )
    texto_ipt = seccion.group(1) if seccion else ""
    lineas = [l.strip() for l in texto_ipt.splitlines() if l.strip()]
    opciones = [
        "PLANO REGULADOR METROPOLITANO",
        "PLANO REGULADOR INTERCOMUNAL",
        "PLANO REGULADOR COMUNAL",
        "PLANO REGULADOR SECCIONAL",
        "LÍMITE URBANO",
        "LEY 21.078 DE 2018 (Artículo 28 quinquies)",
        "SIN INSTRUMENTO DE PLANIFICACIÓN TERRITORIAL (IPT)",
    ]
    flags = {op: False for op in opciones}
    for op in opciones:
        patron = re.compile(rf'^\s*[Xx✓✔]\s*{re.escape(op)}\s*$', re.IGNORECASE)
        if any(patron.match(l) for l in lineas):
            flags[op] = True
    return flags

def parsear_restricciones_flags(bloque):
    seccion = re.search(r'RESTRICCIONES(.*?)(?:\nOBSERVACIONES|$)', bloque, re.DOTALL)
    texto = seccion.group(1) if seccion else ""
    lineas = [l.strip() for l in texto.splitlines() if l.strip()]
    opciones = [
        "AFECTO A EXPROPIACIÓN (Artículo 83° L.G.U.C.)",
        "ÁREA DE PROTECCIÓN DE RECURSOS DE VALOR NATURAL (Artículo 2.1.18. O.G.U.C.)",
        "ÁREA DE PROTECCIÓN DE RECURSOS DE VALOR PATRIMONIAL CULTURAL O ZONA DE CONSERVACIÓN HISTÓRICA (Artículo 2.1.18 O.G.U.C)",
        "CON LIMITACIÓN DE USO: ESPACIO PÚBLICO O ÁREA VERDE COMPLEMENTARIA (Artículo 2.1.30. O.G.U.C.)",
        "CON PROHIBICIÓN DE EDIFICAR (Artículo 60° L.G.U.C.)",
        "DECLARADO DE UTILIDAD PÚBLICA (Artículo 59° L.G.U.C)",
        "HUMEDALES (Artículo 60° L.G.U.C.)",
        "SALDO PREDIAL (Artículo 1.1.2 O.G.U.C.)",
        "ZONA DE CONSTRUCCIÓN OBLIGATORIA (Artículo 76° L.G.U.C.)",
        "ZONA DE EQUIPAMIENTO (Artículo 2.1.33. O.G.U.C.)",
        "ZONA DE INFRAESTRUCTURA PELIGROSA (*)",
        "ZONA DE REMODELACIÓN (Artículo 72° L.G.U.C.)",
        "ZONA DE RIESGO (Artículo 2.1.17. O.G.U.C.)",
        "OTRA (indicar en observaciones)",
        "SIN RESTRICCIONES"
    ]
    flags = {op: False for op in opciones}
    for op in opciones:
        patron = re.compile(rf'^\s*[Xx✓✔]\s*{re.escape(op)}\s*$', re.IGNORECASE)
        if any(patron.match(l) for l in lineas):
            flags[op] = True
    return flags

# Solo devuelve checks + observaciones (sin textos crudos ni nota)
def parsear_condiciones_particulares(bloque):
    out = {
        "condiciones_observaciones": "",
        "forma_regular": False,
        "forma_irregular": False,
        "topografia_regular": False,
        "topografia_irregular": False,
    }
    seccion = re.search(
        r'CONDICIONES PARTICULARES DEL ÁREA HOMOGÉNEA(.*?)(?:\nRESTRICCIONES|\Z)',
        bloque, re.DOTALL
    )
    if not seccion:
        return out

    texto = seccion.group(1)
    # Observaciones internas de la sección
    m_obs = re.search(r'\nOBSERVACIONES\s*\n(.*?)(?=\nRESTRICCIONES|\Z)', texto, re.DOTALL | re.IGNORECASE)
    if m_obs:
        out["condiciones_observaciones"] = re.sub(r'\s+', ' ', m_obs.group(1)).strip()

    # Heurística de matriz Forma/Topografía
    lineas = [l.strip() for l in texto.splitlines() if l.strip()]
    hdr_idx = None
    for i, l in enumerate(lineas):
        if "PREDIOS DE FORMA" in l and "PREDIOS DE TOPOGRAFÍA" in l:
            hdr_idx = i
            break

    def _marcar(fila, clave_forma, clave_topo):
        xs = [(m.start(), m.group()) for m in re.finditer(r'[Xx✓✔]', fila)]
        if len(xs) >= 2:
            out[clave_forma] = True
            out[clave_topo] = True
        elif len(xs) == 1:
            pos = xs[0][0]
            mid = len(fila) // 2
            if pos <= mid:
                out[clave_forma] = True
            else:
                out[clave_topo] = True

    if hdr_idx is not None:
        if hdr_idx + 1 < len(lineas):
            _marcar(lineas[hdr_idx + 1], "forma_regular", "topografia_regular")
        if hdr_idx + 2 < len(lineas):
            _marcar(lineas[hdr_idx + 2], "forma_irregular", "topografia_irregular")
    else:
        for l in lineas:
            if re.search(r'^[Xx✓✔]\s*REGULAR$', l):
                out["forma_regular"] = True
                out["topografia_regular"] = True
            if re.search(r'^[Xx✓✔]\s*IRREGULAR$', l):
                out["forma_irregular"] = True
                out["topografia_irregular"] = True

    return out

def parsear_restricciones_observaciones(bloque):
    m = re.search(
        r'RESTRICCIONES.*?\nOBSERVACIONES\s*\n(.*?)(?=\n(?:IDENTIFICACIÓN DEL AH|FICHA COMUNAL|INSTRUMENTO DE PLANIFICACIÓN TERRITORIAL|CONDICIONES PARTICULARES DEL ÁREA HOMOGÉNEA)|\Z)',
        bloque, re.DOTALL | re.IGNORECASE
    )
    return re.sub(r'\s+', ' ', m.group(1)).strip() if m else ""
# ... (resto de imports y funciones iguales)

def extraer_fichas(path_pdf):
    fichas = []
    with pdfplumber.open(path_pdf) as pdf:
        for page_idx, page in enumerate(pdf.pages, start=1):
            texto = page.extract_text() or ""
            bloques = texto.split("IDENTIFICACIÓN DEL AH")

            for bloque_idx, bloque in enumerate(bloques[1:], start=1):
                ficha = {}

                # 🔎 contexto de origen
                ficha['source_pdf'] = os.path.basename(path_pdf)
                ficha['page_num'] = page_idx
                ficha['block_num'] = bloque_idx  # opcional, por si hay >1 AH por página

                region = re.search(r'REGIÓN:\s*(.*?)\n', bloque)
                comuna = re.search(r'NOMBRE DE LA COMUNA:\s*(.*?)\n', bloque)
                cod_ah = extraer_codigo_area(bloque)
                tipo = re.search(r'TIPO DE EMPLAZAMIENTO:\s*(.*?)\n', bloque)
                obs_gen = re.search(
                    r'OBSERVACIONES Y/O CARACTERÍSTICAS:\s*\n?(.*?)(?=\nINSTRUMENTO DE PLANIFICACIÓN TERRITORIAL|\Z)',
                    bloque, re.DOTALL | re.IGNORECASE
                )

                ficha['region'] = region.group(1).strip() if region else ''
                ficha['comuna'] = comuna.group(1).strip() if comuna else ''
                ficha['cod_ah'] = cod_ah if cod_ah else ''   # 👈 ojo: vacío produce muchos "duplicados"
                ficha['emplazamiento'] = tipo.group(1).strip() if tipo else ''
                ficha['observaciones'] = (obs_gen.group(1).strip() if obs_gen else '')

                # IPT (checks)
                ipt_flags = parsear_ipt_flags(bloque)
                mapping_ipt = {
                    "PLANO REGULADOR METROPOLITANO": "pr_metropolitano",
                    "PLANO REGULADOR INTERCOMUNAL": "pr_intercomunal",
                    "PLANO REGULADOR COMUNAL": "pr_comunal",
                    "PLANO REGULADOR SECCIONAL": "pr_seccional",
                    "LÍMITE URBANO": "limite_urbano",
                    "LEY 21.078 DE 2018 (Artículo 28 quinquies)": "ley_21078_art28_quinquies",
                    "SIN INSTRUMENTO DE PLANIFICACIÓN TERRITORIAL (IPT)": "sin_ipt",
                }
                for k, v in ipt_flags.items():
                    ficha[mapping_ipt.get(k, k)] = v

                # RESTRICCIONES (checks)
                restricciones_flags = parsear_restricciones_flags(bloque)
                mapping_restr = {
                    "AFECTO A EXPROPIACIÓN (Artículo 83° L.G.U.C.)": "expropiacion",
                    "ÁREA DE PROTECCIÓN DE RECURSOS DE VALOR NATURAL (Artículo 2.1.18. O.G.U.C.)": "area_proteccion_natural",
                    "ÁREA DE PROTECCIÓN DE RECURSOS DE VALOR PATRIMONIAL CULTURAL O ZONA DE CONSERVACIÓN HISTÓRICA (Artículo 2.1.18 O.G.U.C)": "area_patrimonial_cultural",
                    "CON LIMITACIÓN DE USO: ESPACIO PÚBLICO O ÁREA VERDE COMPLEMENTARIA (Artículo 2.1.30. O.G.U.C.)": "limitacion_uso_espacio_publico_area_verde",
                    "CON PROHIBICIÓN DE EDIFICAR (Artículo 60° L.G.U.C.)": "prohibicion_edificar",
                    "DECLARADO DE UTILIDAD PÚBLICA (Artículo 59° L.G.U.C)": "utilidad_publica",
                    "HUMEDALES (Artículo 60° L.G.U.C.)": "humedales",
                    "SALDO PREDIAL (Artículo 1.1.2 O.G.U.C.)": "saldo_predial",
                    "ZONA DE CONSTRUCCIÓN OBLIGATORIA (Artículo 76° L.G.U.C.)": "construccion_obligatoria",
                    "ZONA DE EQUIPAMIENTO (Artículo 2.1.33. O.G.U.C.)": "zona_equipamiento",
                    "ZONA DE INFRAESTRUCTURA PELIGROSA (*)": "infraestructura_peligrosa",
                    "ZONA DE REMODELACIÓN (Artículo 72° L.G.U.C.)": "zona_remodelacion",
                    "ZONA DE RIESGO (Artículo 2.1.17. O.G.U.C.)": "zona_riesgo",
                    "OTRA (indicar en observaciones)": "otra",
                    "SIN RESTRICCIONES": "sin_restricciones",
                }
                for k, v in restricciones_flags.items():
                    ficha[mapping_restr.get(k, k)] = v

                # Condiciones particulares (checks + obs)
                cond = parsear_condiciones_particulares(bloque)
                ficha.update(cond)

                # OBS de RESTRICCIONES
                ficha["restricciones_observaciones"] = parsear_restricciones_observaciones(bloque)

                fichas.append(ficha)
    return fichas

def procesar_carpeta(carpeta_pdf):
    todas = []
    for archivo in os.listdir(carpeta_pdf):
        if archivo.lower().endswith('.pdf'):
            path = os.path.join(carpeta_pdf, archivo)
            print(f"Procesando: {archivo}")
            todas.extend(extraer_fichas(path))
    return todas

# === Ejecutar y generar reporte de duplicados
carpeta = 'scraper/descargas/homogeneas'
fichas_total = procesar_carpeta(carpeta)
df = pd.DataFrame(fichas_total)

# Reporte de filas con cod_ah vacío (muy común causa de "duplicados")
df_codah_vacio = df[(df['cod_ah'].isna()) | (df['cod_ah'].astype(str).str.strip() == '')]
df_codah_vacio.to_csv('reporte_cod_ah_vacio.csv', index=False, encoding='utf-8-sig')

# Duplicados por (comuna, cod_ah)
mask_dups = df.duplicated(subset=['comuna', 'cod_ah'], keep=False)
dups = df.loc[mask_dups].sort_values(['comuna', 'cod_ah', 'source_pdf', 'page_num'])
dups.to_csv('reporte_duplicados_detalle.csv', index=False, encoding='utf-8-sig')

# Resumen agrupado: para cada combinación, lista PDFs y páginas
resumen = (
    dups.groupby(['comuna','cod_ah'])
        .agg(
            cantidad=('cod_ah','size'),
            pdfs=('source_pdf', lambda x: ', '.join(sorted(set(x)))),
            paginas=('page_num', lambda x: ', '.join(map(str, sorted(set(x)))))
        )
        .reset_index()
        .sort_values(['comuna','cod_ah'])
)
resumen.to_csv('reporte_duplicados_resumen.csv', index=False, encoding='utf-8-sig')

# (Opcional) Export principal sin tocar
df.to_csv('homogeneas_checks_y_obs_con_origen.csv', index=False, encoding='utf-8-sig')
print('👉 Generados:')
print('- reporte_cod_ah_vacio.csv')
print('- reporte_duplicados_detalle.csv')
print('- reporte_duplicados_resumen.csv')
print('- homogeneas_checks_y_obs_con_origen.csv')


# === Dataset SIN duplicados para importar (mergea checks por OR y toma las observaciones más ricas)
from typing import Iterable
import numpy as np

def pick_longest(series: pd.Series) -> str:
    s = series.dropna().astype(str).str.strip()
    s = s[s != ""]
    if s.empty:
        return ""
    return max(s, key=len)

keys = ['comuna', 'cod_ah']

# trabajar solo con filas con cod_ah válido
df_valid = df[df['cod_ah'].astype(str).str.strip() != ""].copy()

# detectar columnas booleanas (True/False/0/1) en df_valid
def is_boolish(col: pd.Series) -> bool:
    vals = col.dropna().unique()
    return set(vals).issubset({True, False, 0, 1})

bool_cols_df = [c for c in df_valid.columns if is_boolish(df_valid[c])]
for c in bool_cols_df:
    df_valid[c] = df_valid[c].fillna(False).astype(bool)

# agregaciones
agg = {c: 'any' for c in bool_cols_df}  # OR sobre checks
for c in ['region','emplazamiento','observaciones',
          'condiciones_observaciones','restricciones_observaciones']:
    if c in df_valid.columns:
        agg[c] = pick_longest

# trazabilidad
if 'source_pdf' in df_valid.columns:
    agg['source_pdf'] = lambda x: ', '.join(sorted(set(map(str, x))))
if 'page_num' in df_valid.columns:
    agg['page_num']  = lambda x: ', '.join(map(str, sorted(set(pd.to_numeric(x, errors='coerce').dropna().astype(int)))))
if 'block_num' in df_valid.columns:
    agg['block_num'] = lambda x: ', '.join(map(str, sorted(set(pd.to_numeric(x, errors='coerce').dropna().astype(int)))))

# construir deduplicado
dedup = df_valid.groupby(keys, as_index=False).agg(agg)

# forzar dtype booleano en dedup
for c in bool_cols_df:
    if c in dedup.columns:
        dedup[c] = dedup[c].fillna(False).astype(bool)

# === Exportar SIN columnas extra (encaja 1:1 con tu tabla) ===
table_cols = [
    'region','comuna','cod_ah','emplazamiento',
    'observaciones','condiciones_observaciones','restricciones_observaciones',
    'forma_regular','forma_irregular','topografia_regular','topografia_irregular',
    'pr_metropolitano','pr_intercomunal','pr_comunal','pr_seccional','limite_urbano',
    'ley_21078_art28_quinquies','sin_ipt',
    'expropiacion','area_proteccion_natural','area_patrimonial_cultural',
    'limitacion_uso_espacio_publico_area_verde','prohibicion_edificar','utilidad_publica',
    'humedales','saldo_predial','construccion_obligatoria','zona_equipamiento',
    'infraestructura_peligrosa','zona_remodelacion','zona_riesgo','otra','sin_restricciones',
]

# garantizar que existan todas las columnas esperadas
for c in table_cols:
    if c not in dedup.columns:
        dedup[c] = "" if c in ['region','comuna','cod_ah','emplazamiento',
                               'observaciones','condiciones_observaciones','restricciones_observaciones'] else False

# subset + orden
dedup_for_import = dedup[table_cols].copy()

# booleans correctos en el subset de importación
text_cols = ['region','comuna','cod_ah','emplazamiento',
             'observaciones','condiciones_observaciones','restricciones_observaciones']
bool_cols_import = [c for c in dedup_for_import.columns if c not in text_cols]
for c in bool_cols_import:
    dedup_for_import[c] = dedup_for_import[c].fillna(False).astype(bool)

# filtra filas que violarían NOT NULL
dedup_for_import = dedup_for_import[
    dedup_for_import['region'].astype(str).str.strip().ne('') &
    dedup_for_import['comuna'].astype(str).str.strip().ne('') &
    dedup_for_import['cod_ah'].astype(str).str.strip().ne('')
]

# === EXPORTS ===
# 1) CSV listo para importar (sin columnas extra) -> NO lo sobreescribas luego
dedup_for_import.to_csv('homogeneas_para_importar_sin_dups.csv', index=False, encoding='utf-8-sig')
print('- homogeneas_para_importar_sin_dups.csv listo (sin columnas extra)')

# 2) Trazabilidad (para referencia, NO importar)
trace_cols = [c for c in ['comuna','cod_ah','source_pdf','page_num','block_num'] if c in dedup.columns]
if trace_cols:
    dedup[trace_cols].to_csv('homogeneas_trazabilidad.csv', index=False, encoding='utf-8-sig')
    print('- homogeneas_trazabilidad.csv (para referencia)')
