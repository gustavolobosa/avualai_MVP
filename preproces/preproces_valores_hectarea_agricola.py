# extraer_long_desde_pdf.py
# Requisitos:
#   pip install pdfplumber pandas openpyxl

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Optional

import pandas as pd
import pdfplumber

# -----------------------------
# CONFIG: pon aquí tu ruta
# -----------------------------
PDF_PATH = r"Anexo 4 Rex 150 .pdf"
# -----------------------------


def strip_accents(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


def parse_int_cell(val) -> Optional[int]:
    if val is None:
        return None
    v = str(val).strip()
    if not v:
        return None
    v = v.replace("\u00ad", "")       # soft hyphen
    v = v.replace(".", "").replace(" ", "")
    if v.isdigit():
        return int(v)
    v = re.sub(r"[^\d]", "", v)
    return int(v) if v.isdigit() else None


def parse_pdf_to_long(pdf_path: str | Path) -> pd.DataFrame:
    pdf_path = Path(pdf_path)
    rows = []

    valid_class = re.compile(r"^\d+R$|^\d+$")  # ej: 1R, 2R, 20, 8, etc.

    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            for table in (page.extract_tables() or []):
                if not table or len(table) < 3:
                    continue

                # Busca fila header: ["COMUNA","SECTOR",...]
                header_idx = None
                for r_idx, r in enumerate(table):
                    if not r or len(r) < 2:
                        continue
                    c0 = (r[0] or "").strip().upper()
                    c1 = (r[1] or "").strip().upper()
                    if c0 == "COMUNA" and c1 == "SECTOR":
                        header_idx = r_idx
                        break

                if header_idx is None or header_idx + 1 >= len(table):
                    continue

                class_row = table[header_idx + 1]

                # Mapa: índice de columna -> etiqueta de clase (manteniendo posiciones, aunque haya celdas vacías)
                col_map = {}
                for ci in range(2, len(class_row)):
                    lab = (class_row[ci] or "").strip()
                    if valid_class.match(lab):
                        col_map[ci] = lab

                if not col_map:
                    continue

                # Filas de datos
                for r in table[header_idx + 2 :]:
                    if not r or len(r) < 2:
                        continue

                    comuna = (r[0] or "").strip()
                    sector = (r[1] or "").strip()

                    if not comuna or not sector or not re.fullmatch(r"\d+", sector):
                        continue

                    comuna = strip_accents(comuna)  # sin acentos
                    sector = int(sector)

                    for ci, clase in col_map.items():
                        if ci >= len(r):
                            continue
                        valor = parse_int_cell(r[ci])
                        if valor is None:
                            continue  # si quieres guardar también vacíos, cambia por: rows.append(..., valor=None)
                        rows.append(
                            {
                                "comuna": comuna,
                                "sector": sector,
                                "clase_suelo": clase,
                                "valor": valor,
                            }
                        )

    return pd.DataFrame(rows)


def main():
    pdf_path = Path(PDF_PATH)
    if not pdf_path.exists():
        raise FileNotFoundError(f"No existe el archivo: {pdf_path}")

    df_long = parse_pdf_to_long(pdf_path)
    if df_long.empty:
        raise RuntimeError("No se extrajo ninguna fila. Revisa el PDF o el método de extracción.")

    out_xlsx = pdf_path.with_name(f"{pdf_path.stem}_long.xlsx")
    df_long.to_excel(out_xlsx, index=False)

    print(f"Excel creado en: {out_xlsx}")


if __name__ == "__main__":
    main()
