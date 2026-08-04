"""
Scraper Minciencias - ConvocaUR
================================
Rol: Ingesta y ETL

Minciencias no tiene una API pública como SECOP, así que esta fuente se
extrae por web scraping (permitido: es información pública, respetando
robots.txt y sin sobrecargar el servidor -> hay pausa entre requests).

Extrae dos niveles:
  1. Listado de convocatorias (tabla paginada en /convocatorias/todas)
  2. Detalle de cada convocatoria: metadatos + tabla "Datos de la
     convocatoria" (Actividad / Fecha / Documentos), que se descompone en
     dos tablas relacionales:
        - actividades: una fila por hito (Apertura, Modificaciones, Cierre,
          Publicación de resultados preliminares/definitivos), cada una con
          su propia fecha.
        - documentos: una fila por archivo adjunto, ligado a la actividad
          en la que aparece, clasificado por tipo (resolución, términos de
          referencia, anexo, modificación/nota aclaratoria, comunicado,
          resultado, otro) y deduplicado entre versión PDF y "editable"
          (Word/Excel) del mismo documento.

IMPORTANTE: este script no se pudo probar en vivo desde este entorno
(sandbox sin salida de red hacia minciencias.gov.co). Está escrito con
base en el HTML real inspeccionado de dos convocatorias (976 y 49), pero
antes de correrlo a escala:
  - Verifica manualmente contra 4-5 convocatorias más que los selectores
    (texto de headers "Número:", "Objetivo:", "Recursos disponibles:",
    nombre de la tabla) sean estables entre convocatorias antiguas y
    recientes.
  - Revisa robots.txt del sitio y ajusta REQUEST_DELAY_SECONDS si hace falta.

Uso:
    python scrape_minciencias.py --paginas 5 --out convocatorias_minciencias
"""

import argparse
import logging
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("scrape_minciencias")

BASE_URL = "https://minciencias.gov.co"
LISTADO_URL = f"{BASE_URL}/convocatorias/todas"
REQUEST_DELAY_SECONDS = 1.5  # cortesía con el servidor público
HEADERS = {"User-Agent": "ConvocaUR-ETL/0.1 (proyecto academico Universidad del Rosario)"}


def id_desde_url(url: str | None) -> str | None:
    """Fallback estable cuando Minciencias no publica 'Número' (concursos, /node/N)."""
    if not url:
        return None
    m = re.search(r"/node/(\d+)", str(url))
    if m:
        return f"node_{m.group(1)}"
    m = re.search(r"/convocatoria[s]?/(\d+)", str(url), re.IGNORECASE)
    if m:
        return m.group(1)
    return None


# ---------------------------------------------------------------------------
# Utilidades de request
# ---------------------------------------------------------------------------
def obtener_html(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    time.sleep(REQUEST_DELAY_SECONDS)
    return BeautifulSoup(resp.text, "html.parser")


# ---------------------------------------------------------------------------
# 1. Listado de convocatorias (tabla paginada)
# ---------------------------------------------------------------------------
def extraer_listado(max_paginas: int) -> pd.DataFrame:
    filas = []
    for page in range(max_paginas):
        url = LISTADO_URL if page == 0 else f"{LISTADO_URL}?page={page}"
        log.info("Listado: página %s -> %s", page, url)
        soup = obtener_html(url)

        tabla = soup.find("table")
        if tabla is None:
            log.warning("No se encontró tabla en %s, deteniendo paginación.", url)
            break

        filas_pagina = tabla.find("tbody").find_all("tr") if tabla.find("tbody") else tabla.find_all("tr")[1:]
        if not filas_pagina:
            log.info("Página %s sin filas, fin del listado.", page)
            break

        for tr in filas_pagina:
            celdas = tr.find_all("td")
            if len(celdas) < 5:
                continue
            link_titulo = celdas[1].find("a")
            url_detalle = urljoin(BASE_URL, link_titulo["href"]) if link_titulo else None
            numero = celdas[0].get_text(strip=True)
            if not numero:
                numero = id_desde_url(url_detalle) or ""
            filas.append({
                "numero": numero,
                "titulo": link_titulo.get_text(strip=True) if link_titulo else celdas[1].get_text(strip=True),
                "url_detalle": url_detalle,
                "descripcion": celdas[2].get_text(strip=True),
                "total_recursos_texto": celdas[3].get_text(strip=True),
                "fecha_apertura_texto": celdas[4].get_text(strip=True),
            })

    df = pd.DataFrame(filas).drop_duplicates(subset=["url_detalle"])
    log.info("Listado extraído: %s convocatorias", len(df))
    return df


# ---------------------------------------------------------------------------
# 2. Clasificación de documentos
# ---------------------------------------------------------------------------
ANEXO_PATTERN = re.compile(r"anexo[\s_]*(\d+)", re.IGNORECASE)

# Orden importa: se evalúa de arriba a abajo, primera coincidencia gana.
REGLAS_CLASIFICACION = [
    ("resolucion", re.compile(r"resoluci[oó]n", re.IGNORECASE)),
    ("terminos_referencia", re.compile(r"t[eé]rminos?\s+de\s+referencia", re.IGNORECASE)),
    ("modificacion", re.compile(r"nota\s+aclaratoria|adenda|adendo|modificaci[oó]n", re.IGNORECASE)),
    ("resultado", re.compile(r"listado|resultados?\s+(preliminar|definitiv)", re.IGNORECASE)),
    ("comunicado", re.compile(r"respuesta\s+(a\s+)?observaciones|respuesta\s+radicado|comunicado", re.IGNORECASE)),
    ("anexo", ANEXO_PATTERN),
]

# Sub-clasificación de anexos por contenido del título (para alimentar las
# dimensiones de la calculadora: técnico, talento, finanzas, alianzas, etc.)
SUBTIPOS_ANEXO = [
    ("aval_institucional", re.compile(r"aval|compromiso institucional|gobernanza", re.IGNORECASE)),
    ("talento_hv", re.compile(r"hoja de vida|investigador|jóvenes investigadores|semilleros", re.IGNORECASE)),
    ("finanzas", re.compile(r"presupuesto|rubros? financiables?", re.IGNORECASE)),
    ("tecnico", re.compile(r"contenido t[eé]cnico|documento t[eé]cnico|madurez tecnol[oó]gica|categorizaci[oó]n", re.IGNORECASE)),
    ("apropiacion_social", re.compile(r"apropiaci[oó]n social|divulgaci[oó]n", re.IGNORECASE)),
    ("poblacion_especifica", re.compile(r"enfoque[\s_]+diferencial|comunidad|territorial", re.IGNORECASE)),
    ("procedimental", re.compile(r"instructivo|procedimiento|mga", re.IGNORECASE)),
    ("alianzas", re.compile(r"carta de experiencia|empresa nacional|convenio", re.IGNORECASE)),
]


def clasificar_documento(nombre: str) -> tuple[str, str | None, str | None]:
    """Devuelve (tipo_documento, numero_anexo, subtipo_anexo)."""
    for tipo, patron in REGLAS_CLASIFICACION:
        m = patron.search(nombre)
        if m:
            if tipo == "anexo":
                numero = m.group(1)
                subtipo = next(
                    (sub for sub, pat in SUBTIPOS_ANEXO if pat.search(nombre)),
                    "otro",
                )
                return "anexo", numero, subtipo
            return tipo, None, None
    return "otro", None, None


def es_version_editable(nombre: str, url: str) -> bool:
    if "editable" in nombre.lower():
        return True
    return url.lower().endswith((".doc", ".docx", ".xls", ".xlsx"))


def clave_deduplicacion(nombre: str) -> str:
    """Nombre base sin '(editable)' ni ruido de formato, para agrupar
    la versión PDF y la versión Word/Excel del mismo documento."""
    base = re.sub(r"\(editable\)\.?", "", nombre, flags=re.IGNORECASE)
    base = re.sub(r"\s+", " ", base).strip()
    base = base.rstrip(". ").lower()
    return base


# ---------------------------------------------------------------------------
# 3. Detalle de convocatoria: metadatos + actividades + documentos
# ---------------------------------------------------------------------------
@dataclass
class DetalleConvocatoria:
    numero: str = None
    titulo: str = None
    objetivo: str = None
    estado: str = None
    recursos_disponibles_texto: str = None
    actividades: list = field(default_factory=list)
    documentos: list = field(default_factory=list)


def extraer_detalle(url: str) -> DetalleConvocatoria:
    soup = obtener_html(url)
    detalle = DetalleConvocatoria()

    texto_pagina = soup.get_text("\n")

    m = re.search(r"Número:\s*\n?\s*(\d+)", texto_pagina)
    if m:
        detalle.numero = m.group(1)
    elif not detalle.numero:
        detalle.numero = id_desde_url(url)

    h1 = soup.find("h1")
    if h1:
        detalle.titulo = h1.get_text(strip=True)

    m = re.search(r"Objetivo:\s*\n(.+?)(?:\n\n|\nEjes temáticos|\nDirigida a)", texto_pagina, re.DOTALL)
    if m:
        detalle.objetivo = m.group(1).strip()

    m = re.search(r"Recursos disponibles:\s*\n?\s*(\$[\d.,]+)", texto_pagina)
    if m:
        detalle.recursos_disponibles_texto = m.group(1)

    img_estado = soup.find("img", src=re.compile(r"estado-convocatoria"))
    if img_estado:
        # p.ej. ".../estado-convocatoria-finalizada.png" -> "finalizada"
        m = re.search(r"estado-convocatoria-([a-z0-9_-]+)\.png", img_estado.get("src", ""))
        if m:
            detalle.estado = m.group(1)

    # Tabla "Datos de la convocatoria": columnas Actividad | Fecha | Documentos
    tabla_datos = None
    for tabla in soup.find_all("table"):
        headers_tabla = [th.get_text(strip=True) for th in tabla.find_all("th")]
        if "Actividad" in headers_tabla and "Documentos" in headers_tabla:
            tabla_datos = tabla
            break

    if tabla_datos is None:
        log.warning("No se encontró tabla 'Datos de la convocatoria' en %s", url)
        return detalle

    filas = tabla_datos.find("tbody").find_all("tr") if tabla_datos.find("tbody") else tabla_datos.find_all("tr")[1:]

    for tr in filas:
        celdas = tr.find_all("td")
        if len(celdas) < 3:
            continue
        tipo_actividad = celdas[0].get_text(strip=True)
        fecha_texto = celdas[1].get_text(strip=True)
        celda_docs = celdas[2]

        detalle.actividades.append({
            "convocatoria_numero": detalle.numero,
            "tipo_actividad": tipo_actividad,
            "fecha_texto": fecha_texto,
        })

        vistos = {}  # clave_dedup -> índice en detalle.documentos, para fusionar formatos
        for a in celda_docs.find_all("a"):
            nombre = a.get_text(strip=True) or a.get("title", "")
            href = urljoin(BASE_URL, a.get("href", ""))
            if not nombre or not href:
                continue

            tipo_doc, numero_anexo, subtipo_anexo = clasificar_documento(nombre)
            editable = es_version_editable(nombre, href)
            clave = clave_deduplicacion(nombre)

            if clave in vistos:
                # Ya existe la contraparte (PDF <-> editable) de este documento;
                # solo le agregamos la url del formato adicional.
                doc_existente = detalle.documentos[vistos[clave]]
                campo = "url_editable" if editable else "url_pdf"
                doc_existente[campo] = href
                continue

            documento = {
                "convocatoria_numero": detalle.numero,
                "tipo_actividad": tipo_actividad,
                "nombre_documento": nombre,
                "tipo_documento": tipo_doc,
                "numero_anexo": numero_anexo,
                "subtipo_anexo": subtipo_anexo,
                "url_pdf": href if not editable else None,
                "url_editable": href if editable else None,
            }
            detalle.documentos.append(documento)
            vistos[clave] = len(detalle.documentos) - 1

    return detalle


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Scraper de convocatorias Minciencias")
    parser.add_argument("--paginas", type=int, default=3, help="Número de páginas del listado a recorrer")
    parser.add_argument("--out", default="convocatorias_minciencias", help="Prefijo de los CSV de salida")
    args = parser.parse_args()

    df_listado = extraer_listado(args.paginas)
    df_listado.to_csv(f"{args.out}_listado.csv", index=False, encoding="utf-8")
    log.info("Guardado %s_listado.csv (%s filas)", args.out, len(df_listado))

    todas_actividades = []
    todos_documentos = []
    for _, fila in df_listado.iterrows():
        if not fila["url_detalle"]:
            continue
        try:
            detalle = extraer_detalle(fila["url_detalle"])
        except Exception as exc:
            log.error("Fallo extrayendo detalle de %s: %s", fila["url_detalle"], exc)
            continue
        todas_actividades.extend(detalle.actividades)
        todos_documentos.extend(detalle.documentos)
        log.info(
            "Convocatoria %s: %s actividades, %s documentos",
            detalle.numero, len(detalle.actividades), len(detalle.documentos),
        )

    pd.DataFrame(todas_actividades).to_csv(f"{args.out}_actividades.csv", index=False, encoding="utf-8")
    pd.DataFrame(todos_documentos).to_csv(f"{args.out}_documentos.csv", index=False, encoding="utf-8")
    log.info("Guardado %s_actividades.csv y %s_documentos.csv", args.out, args.out)


if __name__ == "__main__":
    main()
