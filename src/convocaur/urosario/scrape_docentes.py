"""
Recorre el CSV de docentes de la Universidad del Rosario, le asigna un id
único a cada uno (el slug de su enlace_perfil) y descarga el perfil completo
de research-hub.urosario.edu.co guardándolo como json_profesores/{id}.json.

- El CSV de salida tiene una columna nueva "id" y una columna "json_file"
  que apunta al archivo json_profesores/{id}.json correspondiente, así que
  cruzar CSV <-> JSON es directo: fila -> id -> json_profesores/<id>.json.
- Es reanudable: si json_profesores/<id>.json ya existe, esa fila se salta.
  Se puede volver a correr el script las veces que haga falta (por cortes
  de red, timeouts, etc.) y solo procesará lo que falte.
- Los docentes que fallan (perfil no encontrado, timeout, etc.) quedan
  registrados en scrape_failures.csv para reintentarlos aparte.

Uso:
    python scrape_all_docentes.py <csv_entrada> <carpeta_salida> [--limit N]
"""

import csv
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://research-hub.urosario.edu.co"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}
DELAY_SECONDS = 0.2
TIMEOUT = 20


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def slug_from_url(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


def scrape_profile(url: str) -> dict:
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    data = {"url": url}

    ld = soup.find("script", type="application/ld+json")
    if ld and ld.string:
        try:
            person = json.loads(ld.string)
        except json.JSONDecodeError:
            person = {}
        data["nombre"] = person.get("name", "")
        data["cargo_principal"] = person.get("jobTitle", "")
        data["email"] = person.get("email", "")
        data["telefono"] = person.get("telephone", "")
        data["imagen"] = person.get("image", "")

        afiliaciones = []
        for aff in person.get("affiliation", []) or []:
            nombre_org = aff.get("name", "")
            rol = aff.get("startDate", "")
            afiliaciones.append(f"{rol} - {nombre_org}".strip(" -"))
        data["afiliaciones"] = afiliaciones

        enlaces = {}
        for u in person.get("sameAs", []) or []:
            lu = u.lower()
            if "cvlac" in lu or "minciencias" in lu:
                enlaces["cvlac"] = u
            elif "orcid" in lu:
                enlaces["orcid"] = u
            elif "scholar" in lu:
                enlaces["google_scholar"] = u
            elif "scopus" in lu:
                enlaces["scopus"] = u
            elif "pure" in lu:
                enlaces["pure"] = u
            elif "linkedin" in lu:
                enlaces["linkedin"] = u
            else:
                enlaces.setdefault("otros", []).append(u)
        data["enlaces_externos"] = enlaces

    areas_ul = soup.find("ul", id="individual-hasResearchArea")
    if areas_ul:
        data["areas_investigacion"] = [clean(li.get_text()) for li in areas_ul.find_all("li", role="listitem")]

    perfil_tab = soup.find("div", id="Perfil")
    if perfil_tab:
        textos = [clean(li.get_text()) for li in perfil_tab.select(".property-list li")]
        data["perfil_profesional"] = " ".join(t for t in textos if t)

    formacion_tab = soup.find("div", id="Formación_académica")
    if formacion_tab:
        items = []
        for panel in formacion_tab.find_all("div", class_="panel-default"):
            items.extend(clean(li.get_text()) for li in panel.select(".property-list li"))
        data["formacion_academica"] = [i for i in items if i]

    pub_tab = soup.find("div", id="publicaciones")
    if pub_tab:
        publicaciones = []
        for subclass in pub_tab.select("li.subclass"):
            h3 = subclass.find("h3")
            tipo = clean(h3.get_text()) if h3 else ""
            for li in subclass.select("ul.subclass-property-list > li"):
                a = li.find("a")
                if not a:
                    continue
                titulo = clean(a.get_text())
                if not titulo:
                    continue
                fecha_span = li.find("span", class_="listDateTime")
                fecha = clean(fecha_span.get_text()) if fecha_span else ""
                enlace = urljoin(BASE_URL, a.get("href", ""))
                publicaciones.append({"tipo": tipo, "titulo": titulo, "fecha": fecha, "enlace": enlace})
        data["publicaciones"] = publicaciones
        data["total_publicaciones"] = len(publicaciones)

    proy_tab = soup.find("div", id="Proyectos")
    if proy_tab:
        proyectos = []
        for panel in proy_tab.find_all("div", class_="panel-default"):
            heading = panel.find("h3", class_="panel-title")
            rol = clean(heading.get_text()) if heading else ""
            for li in panel.select(".property-list li"):
                a = li.find("a")
                titulo = clean(a.get_text()) if a else clean(li.get_text())
                fecha_span = li.find("span", class_="listDateTime")
                fecha = clean(fecha_span.get_text()) if fecha_span else ""
                enlace = urljoin(BASE_URL, a.get("href", "")) if a else ""
                if titulo:
                    proyectos.append({"rol": rol, "titulo": titulo, "fecha": fecha, "enlace": enlace})
        data["proyectos"] = proyectos

    serv_tab = soup.find("div", id="Servicios")
    if serv_tab:
        servicios = []
        for panel in serv_tab.find_all("div", class_="panel-default"):
            heading = panel.find("h3", class_="panel-title")
            tipo = clean(heading.get_text()) if heading else ""
            for li in panel.select(".property-list li"):
                a = li.find("a")
                titulo = clean(a.get_text()) if a else clean(li.get_text())
                if titulo:
                    servicios.append({"tipo": tipo, "titulo": titulo})
        data["servicios"] = servicios

    recon_tab = soup.find("div", id="Reconocimientos")
    if recon_tab:
        reconocimientos = []
        for panel in recon_tab.find_all("div", class_="panel-default"):
            for li in panel.select(".property-list li"):
                a = li.find("a")
                nombre_premio = clean(a.get_text()) if a else ""
                fecha_span = li.find("span", class_="listDateTime")
                fecha = clean(fecha_span.get_text()) if fecha_span else ""
                if nombre_premio:
                    reconocimientos.append({"premio": nombre_premio, "fecha": fecha})
        data["reconocimientos"] = reconocimientos

    ident_tab = soup.find("div", id="identidad")
    if ident_tab:
        identidad = {}
        for panel in ident_tab.find_all("div", class_="panel-default"):
            heading = panel.find("h3", class_="panel-title")
            clave = clean(heading.get_text()).lower().replace(" ", "_") if heading else "otro"
            identidad[clave] = [clean(li.get_text()) for li in panel.select(".property-list li")]
        data["identidad"] = identidad

    return data


def main():
    if len(sys.argv) < 3:
        print("Uso: python scrape_all_docentes.py <csv_entrada> <carpeta_salida> [--limit N]")
        sys.exit(1)

    csv_in = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    json_dir = out_dir / "json_profesores"
    json_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "docentes_urosario_con_id.csv"
    failures_csv = out_dir / "scrape_failures.csv"

    with open(csv_in, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    # Asignar id (slug del enlace_perfil) y ruta del json a cada fila.
    for row in rows:
        row["id"] = slug_from_url(row["enlace_perfil"])
        row["json_file"] = f"json_profesores/{row['id']}.json"

    fieldnames = list(rows[0].keys())
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"CSV con id escrito: {out_csv} ({len(rows)} filas)")

    if limit:
        rows = rows[:limit]

    failures = []
    procesados = 0
    saltados = 0
    for i, row in enumerate(rows, 1):
        target = json_dir / f"{row['id']}.json"
        if target.exists() and target.stat().st_size > 0:
            saltados += 1
            continue
        try:
            data = scrape_profile(row["enlace_perfil"])
            data["id"] = row["id"]
            data["facultad_csv"] = row.get("facultad", "")
            data["cargo_csv"] = row.get("cargo", "")
            tmp_target = target.with_suffix(".json.tmp")
            with open(tmp_target, "w", encoding="utf-8") as jf:
                json.dump(data, jf, ensure_ascii=False, indent=2)
            tmp_target.replace(target)  # escritura atómica: evita jsons corruptos si el proceso se corta
            procesados += 1
            if i % 25 == 0:
                print(f"[{i}/{len(rows)}] procesados={procesados} saltados={saltados} fallos={len(failures)}")
        except Exception as e:
            failures.append({"id": row["id"], "enlace_perfil": row["enlace_perfil"], "error": str(e)})
            print(f"FALLO {row['id']}: {e}")
        time.sleep(DELAY_SECONDS)

    if failures:
        with open(failures_csv, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "enlace_perfil", "error"])
            writer.writeheader()
            writer.writerows(failures)
        print(f"Fallos guardados en {failures_csv} ({len(failures)})")

    print(f"Listo. Nuevos procesados: {procesados}, saltados (ya existían): {saltados}, fallos: {len(failures)}")


if __name__ == "__main__":
    main()
