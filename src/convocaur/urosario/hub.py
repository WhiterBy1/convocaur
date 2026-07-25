"""
Universidad del Rosario - capacidad institucional (HUB-UR) - ConvocaUR
=======================================================================
Rol: Ingesta y ETL

HUB-UR (research-hub.urosario.edu.co) es una instalacion de VIVO (Comunidad
UR, Areas UR, Laboratorios, Mapa de capacidades). Estado actualizado tras
revisar el HTML real de dos tipos de pagina distintos:

  - La pagina de inicio SI trae, en el HTML inicial (sin JS), unos KPIs
    agregados de toda la universidad ("613 Comunidad UR", "194 Programas
    academicos", "90 Laboratorios", "15.157 Publicaciones" al momento de
    escribir esto -> ver intentar_kpis_homepage()).
  - El LISTADO (`/people`, `/search`) SI requiere JS: `requests` sin
    navegador headless solo trae el HTML de layout (menu, footer), no las
    tarjetas de docentes. Confirmado de nuevo al escribir este modulo.
    Para obtener ese HTML hace falta renderizarlo con un navegador
    (Selenium/Playwright headless) o interceptar, desde las DevTools del
    navegador (pestaña Network), el endpoint AJAX que la pagina llama para
    pintar las tarjetas -> si se encuentra ese endpoint, se puede pedir
    directo con requests y ahorrarse el navegador headless por completo.
  - El PERFIL INDIVIDUAL (`/display/{slug}`) **SI es accesible con
    requests normal, sin JS** -- verificado con un perfil real (Abello
    Galvis, Ricardo): trae cargos/afiliaciones, areas de investigacion,
    formacion academica, publicaciones (con DOI y anio), proyectos, premios,
    y la seccion "Identidad" con ORCID/Scopus/CvLAC/Pure. Esta es la fuente
    real de "informacion de docentes" mas rica que hay disponible sin
    scraping avanzado.

Flujo recomendado (dos pasos, no uno):
  1. Conseguir la lista de slugs de perfil (`/display/{slug}`) -> requiere
     JS (parsear_lista_docentes() ya sabe leer esas tarjetas UNA VEZ que
     se le pasa el HTML ya renderizado; el como conseguir ese HTML es lo
     pendiente: navegador headless o el endpoint AJAX real).
  2. Por cada slug, pedir el perfil con requests normal y parsearlo con
     obtener_perfil_docente() -- esto SI esta listo y probado.

Si el paso 1 sigue bloqueado cuando haga falta el dato completo, la via de
respaldo sigue siendo pedir el extracto al CRAI
(investigacion_crai@urosario.edu.co) -- ver stub_capacidad_institucional().
"""

import re
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://research-hub.urosario.edu.co"
HEADERS = {"User-Agent": "ConvocaUR-ETL/0.1 (proyecto academico Universidad del Rosario)"}
REQUEST_DELAY_SECONDS = 1.0  # cortesia con el servidor de la universidad

# Etiqueta HTML -> nombre de columna en el resultado
KPI_PATRONES = {
    "Comunidad UR": "num_comunidad_ur",
    "Programas académicos": "num_programas_academicos",
    "Laboratorios": "num_laboratorios",
    "Publicaciones": "num_publicaciones",
}


def intentar_kpis_homepage() -> dict:
    """Extrae los KPIs agregados que SI vienen server-side en el HTML de
    inicio de HUB-UR (no requieren JS). Si la estructura de la pagina
    cambia y no encuentra ninguno, devuelve un dict vacio en vez de fallar,
    para que el notebook pueda decidir si insistir o no."""
    resp = requests.get(BASE_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    texto = BeautifulSoup(resp.text, "html.parser").get_text(" ", strip=True)

    kpis = {}
    for etiqueta_html, columna in KPI_PATRONES.items():
        m = re.search(r"([\d.,]+)\s+" + re.escape(etiqueta_html), texto)
        if m:
            valor_texto = m.group(1).replace(".", "").replace(",", "")
            kpis[columna] = int(valor_texto) if valor_texto.isdigit() else m.group(1)
    return kpis


def intentar_listado_comunidad() -> pd.DataFrame:
    """Prueba si /search trae contenido real de investigadores/grupos en
    el HTML inicial. Devuelve un DataFrame vacio (con las columnas que se
    esperaria tener) si, como se confirmo al construir este modulo, el
    listado viene vacio por ser inyectado via JS."""
    resp = requests.get(f"{BASE_URL}/search", headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    tarjetas_resultado = soup.select("[class*='result'], [class*='card']")
    filas = []
    for tarjeta in tarjetas_resultado:
        nombre = tarjeta.get_text(strip=True)
        if nombre:
            filas.append({"nombre_o_titulo": nombre})

    return pd.DataFrame(filas, columns=["nombre_o_titulo"])


def parsear_lista_docentes(html: str) -> pd.DataFrame:
    """Parsea las tarjetas de docentes de la pagina /people, UNA VEZ que se
    consiguio el HTML ya renderizado (navegador headless, o guardado desde
    el navegador con JS habilitado). Estructura real de cada tarjeta:

        <li role="listitem"><div class="card">
            <img class="card-img-top" src="..." alt="Apellidos, Nombres">
            <div class="card-body">
              <h5 class="card-title"><a href="/display/slug">Apellidos, Nombres</a></h5>
              <section class="card-text"><a href="...individual/n...">Facultad</a></section>
              <div class="card-footer">Cargo</div>
            </div>
        </div></li>

    Una persona puede tener mas de un <section class="card-text"> si esta
    afiliada a mas de una facultad/escuela -> se devuelve una fila por
    persona con la lista de afiliaciones, no una fila por afiliacion.
    """
    soup = BeautifulSoup(html, "html.parser")
    filas = []

    for tarjeta in soup.select("li[role='listitem'] .card"):
        link_nombre = tarjeta.select_one(".card-title a")
        if link_nombre is None:
            continue

        nombre_completo = link_nombre.get_text(strip=True)
        apellido, _, nombre_pila = nombre_completo.partition(",")

        img = tarjeta.select_one("img.card-img-top")
        cargo_el = tarjeta.select_one(".card-footer")

        afiliaciones = [
            {"facultad_escuela": a.get_text(strip=True), "url_organizacion": a.get("href")}
            for a in tarjeta.select(".card-text a")
        ]

        filas.append({
            "nombre_completo": nombre_completo,
            "apellido": apellido.strip(),
            "nombre_pila": nombre_pila.strip(),
            "url_perfil": BASE_URL + link_nombre.get("href", ""),
            "slug": link_nombre.get("href", "").strip("/").split("/")[-1],
            "cargo": cargo_el.get_text(strip=True) if cargo_el else None,
            "facultades_escuelas": [a["facultad_escuela"] for a in afiliaciones],
            "url_imagen": (BASE_URL + img["src"]) if img and img.get("src") else None,
        })

    return pd.DataFrame(filas)


def obtener_perfil_docente(url_perfil: str) -> dict:
    """Scrapea un perfil individual /display/{slug} -- SI funciona con
    requests normal (sin JS), verificado contra un perfil real. Devuelve un
    dict lardo con lo que alimenta capacidad_institucional: cargos, areas
    de investigacion, formacion, conteos de publicaciones/proyectos, e
    identidad (ORCID/Scopus/CvLAC/Pure), ademas de contacto si esta
    publicado."""
    resp = requests.get(url_perfil, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    perfil = {"url_perfil": url_perfil}

    h1 = soup.find("h1")
    perfil["nombre_completo"] = h1.get_text(strip=True) if h1 else None

    # Contacto: primer <a href="mailto:..."> y un patron simple de telefono
    # cerca del inicio de la pagina (no siempre publico).
    mailto = soup.select_one("a[href^='mailto:']")
    perfil["email"] = mailto.get_text(strip=True) if mailto else None
    m_tel = re.search(r"\(\d{1,4}\)\s?\d{6,8}(?:\s?Ext\.?\s?\d+)?", soup.get_text(" ", strip=True))
    perfil["telefono"] = m_tel.group(0) if m_tel else None

    # Cargos/afiliaciones: lista justo debajo del <h1>, cada item tipo
    # "Cargo, Facultad, Universidad del Rosario NNNN -"
    cargos = []
    contenedor_cargos = h1.find_next("ul") if h1 else None
    if contenedor_cargos:
        for li in contenedor_cargos.find_all("li", recursive=False):
            enlaces = [a.get_text(strip=True) for a in li.find_all("a")]
            cargos.append({"texto_completo": li.get_text(" ", strip=True), "organizaciones": enlaces})
    perfil["cargos"] = cargos

    # Areas de investigacion: bajo el encabezado "Áreas De Investigación"
    areas = []
    encabezado_areas = soup.find(string=re.compile(r"Áreas De Investigación", re.IGNORECASE))
    if encabezado_areas:
        contenedor = encabezado_areas.find_parent().find_next("ul")
        if contenedor:
            areas = [a.get_text(strip=True) for a in contenedor.find_all("a")]
    perfil["areas_investigacion"] = areas

    # Formacion academica: bullets "YYYY, Titulo, Institucion" bajo esa seccion
    formacion = []
    encabezado_formacion = soup.find(lambda tag: tag.name in ("h2", "h3") and "Formación Académica" in tag.get_text())
    if encabezado_formacion:
        contenedor = encabezado_formacion.find_next("ul")
        if contenedor:
            formacion = [li.get_text(" ", strip=True) for li in contenedor.find_all("li", recursive=False)]
    perfil["formacion_academica"] = formacion

    # Conteos rapidos (no el detalle completo linea por linea, para no
    # sobrecargar la tabla con una fila por publicacion/proyecto/premio):
    perfil["num_publicaciones"] = _contar_bullets_bajo_encabezado(soup, "Publicaciones Seleccionadas")
    perfil["num_proyectos"] = _contar_bullets_bajo_encabezado(soup, "Investigador Principal En") + \
        _contar_bullets_bajo_encabezado(soup, "Coinvestigador Principal En")
    perfil["num_premios"] = _contar_bullets_bajo_encabezado(soup, "Premios Y Honores")

    # Identidad: ORCID / Scopus / CvLAC / Pure / Google Scholar
    perfil["orcid"] = _extraer_href_por_titulo_imagen(soup, "ORCID")
    perfil["scopus_url"] = _extraer_href_por_titulo_imagen(soup, "Scopus")
    perfil["cvlac_url"] = _extraer_href_por_titulo_imagen(soup, "CVLAC")
    perfil["pure_url"] = _extraer_href_por_titulo_imagen(soup, "Pure")
    perfil["google_scholar_url"] = _extraer_href_por_titulo_imagen(soup, "Google Scholar")

    return perfil


def _contar_bullets_bajo_encabezado(soup: BeautifulSoup, texto_encabezado: str) -> int:
    """Cuenta los <li> de la primera <ul>/lista despues de un encabezado o
    texto que contenga `texto_encabezado`. Devuelve 0 si no lo encuentra,
    para no romper el resto del parseo por un cambio menor de estructura."""
    nodo = soup.find(string=re.compile(re.escape(texto_encabezado), re.IGNORECASE))
    if not nodo:
        return 0
    contenedor = nodo.find_parent().find_next(["ul", "ol"])
    if not contenedor:
        return 0
    return len(contenedor.find_all("li", recursive=False))


def _extraer_href_por_titulo_imagen(soup: BeautifulSoup, titulo_img: str) -> str | None:
    """Busca <img title="ORCID"> (o Scopus/CVLAC/Pure/Google Scholar) y
    devuelve el href del <a> que la envuelve, si existe."""
    img = soup.find("img", title=re.compile(re.escape(titulo_img), re.IGNORECASE))
    if img is None:
        return None
    a = img.find_parent("a")
    return a.get("href") if a else None


def construir_tabla_docentes(html_listado: str, max_perfiles: int | None = None) -> pd.DataFrame:
    """Combina el listado (parsear_lista_docentes) con el detalle de cada
    perfil (obtener_perfil_docente) en una sola tabla. `max_perfiles` sirve
    para probar con pocos docentes antes de correr contra los 615."""
    docentes = parsear_lista_docentes(html_listado)
    if max_perfiles is not None:
        docentes = docentes.head(max_perfiles)

    detalles = []
    for _, fila in docentes.iterrows():
        try:
            detalle = obtener_perfil_docente(fila["url_perfil"])
        except Exception as exc:
            detalle = {"url_perfil": fila["url_perfil"], "error": str(exc)}
        detalles.append(detalle)
        time.sleep(REQUEST_DELAY_SECONDS)

    df_detalle = pd.DataFrame(detalles)
    return docentes.merge(df_detalle, on="url_perfil", how="left", suffixes=("", "_perfil"))


# Esquema esperado del extracto que entregaria el CRAI (a definir con ellos
# exactamente, esto es una hipotesis de trabajo basada en lo que muestra la
# interfaz de HUB-UR: Comunidad UR, Areas UR, Laboratorios, Mapa de
# capacidades). Alimenta una futura tabla `capacidad_institucional` en
# schema_secop.sql.
COLUMNAS_CAPACIDAD_INSTITUCIONAL = [
    "investigador_id",
    "nombre",
    "grupo_investigacion",
    "categoria_minciencias_grupo",
    "area_conocimiento",
    "laboratorio_asociado",
    "num_publicaciones",
    "nivel_formacion",
]


def stub_capacidad_institucional() -> pd.DataFrame:
    """Placeholder vacio con el esquema esperado, para dejar el pipeline
    listo y que reemplazar esto por el extracto real del CRAI sea solo
    cambiar la fuente, no rehacer el resto del notebook/pipeline."""
    return pd.DataFrame(columns=COLUMNAS_CAPACIDAD_INSTITUCIONAL)
