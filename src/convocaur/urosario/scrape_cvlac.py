"""
Enriquece cada json_profesores/{id}.json ya existente con los datos de su
hoja de vida CvLAC (scienti.minciencias.gov.co), agregándolos bajo la clave
"cvlac". El cruce es directo: cada json de docente ya trae su URL de CvLAC
en identidad.cvlac / enlaces_externos.cvlac (sacada del research-hub), así
que no hace falta buscar nada nuevo: solo visitar esa URL y parsearla.

Reanudable: si el json ya tiene la clave "cvlac", se salta. Los docentes sin
enlace CvLAC quedan listados en sin_cvlac.csv; los que fallan al scrapear
(timeouts, etc.) en cvlac_failures.csv.

Uso:
    python scrape_all_cvlac.py <carpeta_json_profesores> [--limit N]
"""

import csv
import glob
import json
import re
import sys
import time
from pathlib import Path

from convocaur.urosario.cvlac_parser import scrape_cvlac

DELAY_SECONDS = 0.3


def get_cvlac_url(doc: dict) -> str:
    ident = doc.get("identidad", {}) or {}
    url = ""
    if ident.get("cvlac"):
        url = ident["cvlac"][0]
    elif (doc.get("enlaces_externos", {}) or {}).get("cvlac"):
        url = doc["enlaces_externos"]["cvlac"]

    if not url or not url.lower().startswith("http"):
        return ""  # placeholders tipo "No"/"no" u otros valores basura

    # dominio viejo (antes de que Colciencias se renombrara a Minciencias):
    # certificado SSL no cubre ese host -> reescribir al dominio actual.
    if "colciencias.gov.co" in url:
        m = re.search(r"cod_rh=(\d+)", url)
        if not m:
            return ""
        url = f"https://scienti.minciencias.gov.co/cvlac/visualizador/generarCurriculoCv.do?cod_rh={m.group(1)}"

    if "cod_rh=" not in url:
        return ""  # enlaces rotos que no apuntan a una hoja de vida (ej. .../query.do)

    return url


def main():
    if len(sys.argv) < 2:
        print("Uso: python scrape_all_cvlac.py <carpeta_json_profesores> [--limit N]")
        sys.exit(1)

    json_dir = Path(sys.argv[1])
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    out_root = json_dir.parent
    sin_cvlac_csv = out_root / "sin_cvlac.csv"
    failures_csv = out_root / "cvlac_failures.csv"

    files = sorted(glob.glob(str(json_dir / "*.json")))
    if limit:
        files = files[:limit]

    procesados = saltados = sin_url = 0
    failures = []
    sin_cvlac_rows = []

    for i, fp in enumerate(files, 1):
        path = Path(fp)
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)

        if "cvlac" in doc:
            saltados += 1
            continue

        url = get_cvlac_url(doc)
        if not url:
            sin_url += 1
            sin_cvlac_rows.append({"id": doc.get("id", path.stem)})
            continue

        try:
            cvlac_data = scrape_cvlac(url)
            doc["cvlac"] = cvlac_data
            tmp = path.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as jf:
                json.dump(doc, jf, ensure_ascii=False, indent=2)
            tmp.replace(path)  # escritura atómica
            procesados += 1
            if i % 20 == 0:
                print(f"[{i}/{len(files)}] procesados={procesados} saltados={saltados} "
                      f"sin_url={sin_url} fallos={len(failures)}")
        except Exception as e:
            failures.append({"id": doc.get("id", path.stem), "url": url, "error": str(e)})
            print(f"FALLO {doc.get('id', path.stem)}: {e}")

        time.sleep(DELAY_SECONDS)

    if sin_cvlac_rows:
        with open(sin_cvlac_csv, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["id"])
            w.writeheader()
            w.writerows(sin_cvlac_rows)

    if failures:
        with open(failures_csv, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["id", "url", "error"])
            w.writeheader()
            w.writerows(failures)

    print(f"Listo. Nuevos procesados: {procesados}, saltados (ya tenían cvlac): {saltados}, "
          f"sin url de cvlac: {sin_url}, fallos: {len(failures)}")


if __name__ == "__main__":
    main()
