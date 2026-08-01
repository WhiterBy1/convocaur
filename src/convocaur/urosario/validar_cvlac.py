"""
Audita una muestra (o todos) de los docentes marcados como "sin CvLAC" en
sin_cvlac.csv, volviendo a pedir su perfil de HUB-UR en vivo y re-aplicando
la MISMA logica de produccion (scrape_profile + get_cvlac_url) para ver si
la clasificacion sigue siendo correcta.

No reimplementa el parseo por su cuenta -- reutiliza scrape_profile() de
scrape_docentes.py y get_cvlac_url() de scrape_cvlac.py, para que la
auditoria compare contra el mismo criterio que usa el pipeline real y no
contra una version simplificada que podria dar falsos positivos.

Tres resultados posibles por docente:
  - confirmado_sin_cvlac   -> perfil accesible, sigue sin link usable de CvLAC
  - discrepancia           -> perfil accesible, AHORA SI tiene un link usable
                               (probable actualizacion del docente en HUB-UR
                               despues del ultimo scrape; requiere reprocesar)
  - perfil_inalcanzable    -> el perfil no respondio (roto/removido del lado
                               de HUB-UR, no es un problema del scraper)

Uso:
    python validar_cvlac.py --muestra 20 --seed 42
    python validar_cvlac.py --todos
"""

from __future__ import annotations

import argparse
import csv
import logging
import random
import ssl
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))  # src/

from convocaur.paths import RAW_UROSARIO, DOCENTES_CSV  # noqa: E402
from convocaur.urosario.scrape_docentes import scrape_profile  # noqa: E402
from convocaur.urosario.scrape_cvlac import get_cvlac_url  # noqa: E402

# El bundle de certifi (el que usa requests por defecto) no trae la cadena
# completa del certificado de research-hub.urosario.edu.co en esta maquina
# -> SSLCertVerificationError. El almacen de certificados de Windows SI la
# tiene (verificado con ssl.create_default_context() sin cafile explicito).
# En vez de desactivar la verificacion (verify=False), forzamos a requests a
# usar el almacen de confianza del sistema en lugar del bundle estatico de
# certifi -- sigue validando la cadena, solo que contra una fuente distinta.
try:
    import requests.adapters

    class _AdaptadorAlmacenSistema(requests.adapters.HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            kwargs["ssl_context"] = ssl.create_default_context()
            return super().init_poolmanager(*args, **kwargs)

    def _get_con_almacen_sistema(url, **kwargs):
        with requests.Session() as s:
            s.mount("https://", _AdaptadorAlmacenSistema())
            return s.get(url, **kwargs)

    requests.get = _get_con_almacen_sistema
except Exception:
    pass  # si algo falla aca, sigue con el comportamiento normal de requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("validar_cvlac")

SIN_CVLAC_CSV = RAW_UROSARIO / "sin_cvlac.csv"
DELAY_SECONDS = 0.5


def _cargar_enlaces() -> dict[str, str]:
    """id -> enlace_perfil, desde el CSV maestro de docentes."""
    with open(DOCENTES_CSV, encoding="utf-8-sig", newline="") as f:
        return {row["id"]: row["enlace_perfil"] for row in csv.DictReader(f)}


def _cargar_sin_cvlac_ids() -> list[str]:
    with open(SIN_CVLAC_CSV, encoding="utf-8-sig", newline="") as f:
        return [row["id"] for row in csv.DictReader(f)]


def validar(ids: list[str], enlaces: dict[str, str]) -> list[dict]:
    resultados = []
    for i, id_ in enumerate(ids, 1):
        enlace = enlaces.get(id_)
        if not enlace:
            resultados.append({"id": id_, "resultado": "id_no_encontrado_en_csv_maestro", "detalle": ""})
            continue

        try:
            doc = scrape_profile(enlace)
        except Exception as exc:
            resultados.append({"id": id_, "resultado": "perfil_inalcanzable", "detalle": str(exc)})
            log.warning("[%s/%s] %s -> perfil inalcanzable (%s)", i, len(ids), id_, exc)
            time.sleep(DELAY_SECONDS)
            continue

        url = get_cvlac_url(doc)
        if url:
            resultados.append({"id": id_, "resultado": "discrepancia", "detalle": url})
            log.warning("[%s/%s] %s -> DISCREPANCIA, ahora tiene link: %s", i, len(ids), id_, url)
        else:
            resultados.append({"id": id_, "resultado": "confirmado_sin_cvlac", "detalle": ""})
            if i % 10 == 0:
                log.info("[%s/%s] procesados …", i, len(ids))

        time.sleep(DELAY_SECONDS)

    return resultados


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--muestra", type=int, default=20, help="Tamano de la muestra aleatoria (ignorado si --todos)")
    parser.add_argument("--seed", type=int, default=42, help="Semilla para que la muestra sea reproducible")
    parser.add_argument("--todos", action="store_true", help="Validar los 259 en vez de una muestra")
    parser.add_argument(
        "--salida",
        type=Path,
        default=RAW_UROSARIO / "validacion_sin_cvlac.csv",
        help="Ruta del CSV de auditoria a escribir",
    )
    args = parser.parse_args()

    enlaces = _cargar_enlaces()
    todos_ids = _cargar_sin_cvlac_ids()

    if args.todos:
        ids = todos_ids
    else:
        random.seed(args.seed)
        ids = random.sample(todos_ids, min(args.muestra, len(todos_ids)))

    log.info("Validando %s de %s docentes en sin_cvlac.csv (seed=%s)", len(ids), len(todos_ids), args.seed)
    resultados = validar(ids, enlaces)

    with open(args.salida, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "resultado", "detalle"])
        w.writeheader()
        w.writerows(resultados)

    conteo = {}
    for r in resultados:
        conteo[r["resultado"]] = conteo.get(r["resultado"], 0) + 1

    print(f"\n=== Resumen ({len(resultados)} validados) ===")
    for k, v in conteo.items():
        print(f"  {k}: {v}")
    print(f"\nDetalle en: {args.salida}")


if __name__ == "__main__":
    main()
