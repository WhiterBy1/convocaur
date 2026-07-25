"""
Parser de una hoja de vida CvLAC (scienti.minciencias.gov.co).

El HTML de CvLAC es viejo (tablas anidadas, sin ids consistentes) pero sigue
un patrón regular: cada sección es un <h3> dentro de una tabla propia, y cada
fila de esa tabla es una entrada. Hay dos variantes de fila:
  1) Fila con 2 <td>: el primero es un bullet vacío, el segundo trae toda la
     info (formación académica, reconocimientos, áreas, líneas...).
  2) Par de filas: la primera trae solo "<li><b>Tipo de producto</b></li>"
     (con el chulo de aval), la segunda trae el <blockquote> con el detalle
     (producción bibliográfica, proyectos, tutorías...).
Este módulo detecta ambos casos y los normaliza a una lista de strings por
sección (o dicts para casos especiales: datos generales e idiomas).
"""

import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}
TIMEOUT = 25


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def cod_rh_from_url(url: str) -> str:
    m = re.search(r"cod_rh=(\d+)", url or "")
    return m.group(1) if m else ""


def parse_datos_generales(soup: BeautifulSoup) -> dict:
    anchor = soup.find("a", attrs={"name": "datos_generales"})
    data = {}
    if not anchor:
        return data
    table = anchor.find_next("table")
    if not table:
        return data
    for tr in table.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) == 2:
            key = clean(tds[0].get_text(" "))
            val = clean(tds[1].get_text(" "))
            if key and val and "messageText" not in (tds[0].get("class") or []):
                data[key] = val
        elif len(tds) == 1 and "messageText" in (tds[0].get("class") or []):
            data["nota"] = clean(tds[0].get_text(" "))
    return data


def parse_idiomas(table) -> list:
    idiomas = []
    rows = table.find_all("tr")
    for tr in rows:
        tds = tr.find_all("td", recursive=False)
        if len(tds) == 5:
            idioma = clean(tds[0].get_text(" "))
            if not idioma or idioma.lower().startswith("habla") or not tds[1].get_text(strip=True):
                # fila de encabezado (Habla/Escribe/Lee/Entiende) o vacía
                if not clean(tds[1].get_text(" ")):
                    continue
            idiomas.append({
                "idioma": idioma,
                "habla": clean(tds[1].get_text(" ")),
                "escribe": clean(tds[2].get_text(" ")),
                "lee": clean(tds[3].get_text(" ")),
                "entiende": clean(tds[4].get_text(" ")),
            })
    return [i for i in idiomas if i["idioma"]]


def parse_generic_section(table) -> list:
    trs = table.find_all("tr")[1:]  # la primera fila es el <h3> de la sección
    entries = []
    pending_label = None
    for tr in trs:
        text_full = clean(tr.get_text(" "))
        if not text_full:
            continue
        li = tr.find("li")
        b = tr.find("b")
        has_blockquote = tr.find("blockquote") is not None

        label_only = False
        if li and b and not has_blockquote:
            li_text = clean(li.get_text(" "))
            b_text = clean(b.get_text(" "))
            if b_text and (li_text == b_text or (li_text.endswith(b_text) and len(li_text) - len(b_text) < 5)):
                label_only = True

        if label_only:
            pending_label = b_text
            continue

        if pending_label:
            entries.append(clean(f"{pending_label}: {text_full}"))
            pending_label = None
        else:
            entries.append(text_full)
    return entries


def extract_articulo_meta(entry_text: str) -> dict:
    """Para entradas de 'Artículos' intenta separar título (entre comillas) y DOI."""
    meta = {"texto": entry_text}
    m_titulo = re.search(r'"([^"]+)"', entry_text)
    if m_titulo:
        meta["titulo"] = m_titulo.group(1)
    m_doi = re.search(r"DOI:\s*([^\s,]+)", entry_text, re.IGNORECASE)
    if m_doi:
        meta["doi"] = m_doi.group(1).rstrip(".")
    m_anio = re.findall(r"\b(19|20)\d{2}\b", entry_text)
    if m_anio:
        meta["anio"] = re.findall(r"\b(?:19|20)\d{2}\b", entry_text)[-1]
    return meta


SECTION_KEY_MAP = {
    "formación académica": "formacion_academica",
    "formación complementaria": "formacion_complementaria",
    "experiencia profesional": "experiencia_profesional",
    "áreas de actuación": "areas_actuacion",
    "líneas de investigación": "lineas_investigacion",
    "reconocimientos": "reconocimientos",
    "trabajos dirigidos/tutorías": "trabajos_dirigidos_tutorias",
    "jurado en comités de evaluación": "jurado_comites_evaluacion",
    "participación en comités de evaluación": "participacion_comites_evaluacion",
    "par evaluador": "par_evaluador",
    "consultorías": "consultorias",
    "ediciones/revisiones": "ediciones_revisiones",
    "eventos científicos": "eventos_cientificos",
    "redes de conocimiento especializado": "redes_conocimiento_especializado",
    "publicaciones editoriales no especializadas": "publicaciones_editoriales_no_especializadas",
    "artículos": "articulos",
    "libros": "libros",
    "capitulos de libro": "capitulos_libro",
    "capítulos de libro": "capitulos_libro",
    "textos en publicaciones no científicas": "textos_no_cientificos",
    "documentos de trabajo": "documentos_trabajo",
    "libros de divulgación y/o compilación de divulgación": "libros_divulgacion",
    "informes técnicos": "informes_tecnicos",
    "proyectos": "proyectos",
}


def scrape_cvlac(url: str) -> dict:
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    resp.encoding = "ISO-8859-1"  # declarado en el <meta charset> de la página
    soup = BeautifulSoup(resp.text, "html.parser")

    data = {"url": url, "cod_rh": cod_rh_from_url(url)}
    data["datos_generales"] = parse_datos_generales(soup)

    for h3 in soup.find_all("h3"):
        titulo_raw = clean(h3.get_text(" "))
        if not titulo_raw or titulo_raw.lower() == "hoja de vida":
            continue  # es el título de toda la página, no una sección real
        key = SECTION_KEY_MAP.get(titulo_raw.lower())
        if not key:
            # sección no mapeada explícitamente: generar una clave a partir del título
            key = re.sub(r"[^a-z0-9]+", "_", titulo_raw.lower()).strip("_")
        table = h3.find_parent("table")
        if not table:
            continue
        if titulo_raw.lower() == "idiomas":
            data["idiomas"] = parse_idiomas(table)
            continue
        entries = parse_generic_section(table)
        if key == "articulos":
            entries = [extract_articulo_meta(e) for e in entries]
        # evitar sobreescribir si ya existe (por si dos h3 comparten texto)
        if key in data and isinstance(data[key], list):
            data[key].extend(entries)
        else:
            data[key] = entries

    return data


if __name__ == "__main__":
    import sys
    import json

    url = sys.argv[1] if len(sys.argv) > 1 else (
        "https://scienti.minciencias.gov.co/cvlac/visualizador/generarCurriculoCv.do?cod_rh=0000500950"
    )
    d = scrape_cvlac(url)
    print(json.dumps(d, ensure_ascii=False, indent=2))
