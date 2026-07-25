"""
Colecciona todos los TdR (Términos de Referencia) de Minciencias
================================================================
Rol: Ingesta

Los archivos en disco NO tienen un nombre uniforme. En el extracto actual
aparecen patrones como:

  tdr_fortalecimiento_....pdf
  terminos_de_referencia_convocatoria_48.pdf
  terminos_referencia_convocatoria_apoyo_....pdf
  02-10-2025_tdr_conv_ia_rev_1.pdf

Además, scrape_minciencias clasifica solo el texto largo
"términos de referencia"; los que salen como "TdR Convocatoria N"
quedan en tipo_documento=otro. Este script los detecta por tipo Y por
nombre/URL.

Salida (nombres normalizados):
    data/raw/minciencias/tdr/
      convocatoria_978_tdr.pdf
      convocatoria_48_tdr.pdf
      ...
      manifest_tdr.csv

Uso:
    python coleccionar_tdr.py              # copia/descarga todos los TdR del CSV
    python coleccionar_tdr.py --piloto     # solo las 5 convocatorias más recientes
"""

from __future__ import annotations

import argparse
import logging
import re
import shutil
from pathlib import Path
from urllib.parse import unquote, urlparse

import pandas as pd
import requests

from convocaur.minciencias.descargar import (
    HEADERS,
    REQUEST_DELAY_SECONDS,
    carpeta_convocatoria,
    nombre_desde_url,
)
from convocaur.paths import (
    DOCUMENTOS_CSV,
    LISTADO_CSV,
    RAW_MINCIENCIAS_ARCHIVOS,
    RAW_MINCIENCIAS_TDR,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("coleccionar_tdr")

DEFAULT_DOCS_CSV = DOCUMENTOS_CSV
DEFAULT_LISTADO_CSV = LISTADO_CSV
DEFAULT_OUT_DIR = RAW_MINCIENCIAS_ARCHIVOS
DEFAULT_TDR_DIR = RAW_MINCIENCIAS_TDR

# Detecta TdR aunque el scraper los haya marcado como "otro"
PATRON_NOMBRE_TDR = re.compile(
    r"t[eé]rminos?\s+de\s+referencia|\btdr\b",
    re.IGNORECASE,
)
PATRON_URL_TDR = re.compile(
    r"(?:^|/)(?:tdr[_-]|terminos?(?:_de)?_referencia)",
    re.IGNORECASE,
)


def es_tdr(fila: pd.Series) -> bool:
    if fila.get("tipo_documento") == "terminos_referencia":
        return True
    nombre = str(fila.get("nombre_documento") or "")
    if PATRON_NOMBRE_TDR.search(nombre):
        return True
    for campo in ("url_pdf", "url_editable"):
        url = fila.get(campo)
        if pd.notna(url) and PATRON_URL_TDR.search(str(url)):
            return True
    return False


def slug_convocatoria(numero) -> str:
    if pd.isna(numero) or str(numero).strip() == "":
        return "sin_numero"
    try:
        return str(int(float(numero)))
    except (ValueError, TypeError):
        return re.sub(r"[^\w\-]+", "_", str(numero)).strip("_") or "sin_numero"


def extension_desde_url(url: str) -> str:
    nombre = nombre_desde_url(url)
    suf = Path(nombre).suffix.lower()
    return suf if suf else ".pdf"


def url_preferida(fila: pd.Series) -> tuple[str | None, str | None]:
    """Prefiere PDF; si no hay, editable."""
    for campo, formato in (("url_pdf", "pdf"), ("url_editable", "editable")):
        url = fila.get(campo)
        if pd.notna(url) and str(url).strip():
            return str(url).strip(), formato
    return None, None


def localizar_descarga_previa(archivos_dir: Path, numero, url: str) -> Path | None:
    carpeta = carpeta_convocatoria(archivos_dir, numero)
    candidato = carpeta / nombre_desde_url(url)
    if candidato.exists() and candidato.stat().st_size > 0:
        return candidato
    return None


def seleccionar_tdr(
    docs_csv: Path,
    listado_csv: Path | None,
    max_convocatorias: int | None,
) -> pd.DataFrame:
    df = pd.read_csv(docs_csv)
    tdr = df[df.apply(es_tdr, axis=1)].copy()
    log.info("TdR detectados en CSV: %s (de %s documentos)", len(tdr), len(df))

    tdr["_num_str"] = tdr["convocatoria_numero"].apply(slug_convocatoria)

    if listado_csv and listado_csv.exists():
        listado = pd.read_csv(listado_csv)
        orden = (
            listado["numero"]
            .dropna()
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .tolist()
        )
        ranking = {n: i for i, n in enumerate(orden)}
        tdr["_rank"] = tdr["_num_str"].map(lambda n: ranking.get(n, 10_000))
        tdr = tdr.sort_values("_rank", kind="stable")
    else:
        tdr["_rank"] = range(len(tdr))

    if max_convocatorias is not None:
        vistas = []
        for num in tdr["_num_str"]:
            if num not in vistas:
                vistas.append(num)
            if len(vistas) >= max_convocatorias:
                break
        tdr = tdr[tdr["_num_str"].isin(vistas)].copy()
        log.info("Piloto: %s convocatorias -> %s TdR", len(vistas), len(tdr))

    # Una fila por convocatoria (si hay varios, se queda el primero del orden)
    tdr = tdr.drop_duplicates(subset=["_num_str"], keep="first")
    return tdr


def coleccionar(
    tdr: pd.DataFrame,
    tdr_dir: Path,
    archivos_dir: Path,
    descargar_faltantes: bool = True,
) -> pd.DataFrame:
    tdr_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    registros = []

    for _, fila in tdr.iterrows():
        slug = fila["_num_str"]
        url, formato = url_preferida(fila)
        registro = {
            "convocatoria_numero": fila.get("convocatoria_numero"),
            "nombre_documento": fila.get("nombre_documento"),
            "tipo_documento_csv": fila.get("tipo_documento"),
            "url": url,
            "formato": formato,
            "nombre_original_url": nombre_desde_url(url) if url else None,
            "ruta_tdr": None,
            "origen": None,
            "estado": None,
            "error": None,
        }

        if not url:
            registro["estado"] = "sin_url"
            registros.append(registro)
            log.warning("Conv %s sin URL de TdR", slug)
            continue

        destino = tdr_dir / f"convocatoria_{slug}_tdr{extension_desde_url(url)}"
        registro["ruta_tdr"] = str(destino)

        if destino.exists() and destino.stat().st_size > 0:
            registro["origen"] = "ya_en_tdr"
            registro["estado"] = "omitido_existe"
            log.info("omitido: %s", destino.name)
            registros.append(registro)
            continue

        previo = localizar_descarga_previa(archivos_dir, fila.get("convocatoria_numero"), url)
        if previo is not None:
            shutil.copy2(previo, destino)
            registro["origen"] = "copiado_desde_archivos"
            registro["estado"] = "ok"
            log.info("copiado %s -> %s", previo.name, destino.name)
            registros.append(registro)
            continue

        if not descargar_faltantes:
            registro["estado"] = "faltante_sin_descarga"
            registros.append(registro)
            continue

        try:
            resp = session.get(url, headers=HEADERS, timeout=60)
            resp.raise_for_status()
            destino.write_bytes(resp.content)
            registro["origen"] = "descargado"
            registro["estado"] = "ok"
            log.info("descargado (%s bytes): %s", len(resp.content), destino.name)
            import time
            time.sleep(REQUEST_DELAY_SECONDS)
        except Exception as exc:
            registro["estado"] = "error"
            registro["error"] = str(exc)
            log.error("error conv %s: %s", slug, exc)
            if destino.exists():
                destino.unlink(missing_ok=True)

        registros.append(registro)

    return pd.DataFrame(registros)


def main():
    parser = argparse.ArgumentParser(description="Colecciona TdR de Minciencias en una sola carpeta")
    parser.add_argument("--piloto", action="store_true", help="Solo 5 convocatorias más recientes")
    parser.add_argument("--max-convocatorias", type=int, default=None)
    parser.add_argument("--docs-csv", type=Path, default=DEFAULT_DOCS_CSV)
    parser.add_argument("--listado-csv", type=Path, default=DEFAULT_LISTADO_CSV)
    parser.add_argument("--archivos-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--tdr-dir", type=Path, default=DEFAULT_TDR_DIR)
    parser.add_argument(
        "--sin-descarga",
        action="store_true",
        help="Solo copiar los que ya estén en archivos/; no pedir a Minciencias",
    )
    args = parser.parse_args()

    max_conv = args.max_convocatorias
    if args.piloto and max_conv is None:
        max_conv = 5

    tdr = seleccionar_tdr(args.docs_csv, args.listado_csv, max_conv)
    if tdr.empty:
        raise SystemExit("No se encontraron TdR en el CSV.")

    print("\n=== Nombres originales (URL) vs destino normalizado ===")
    for _, fila in tdr.iterrows():
        url, _ = url_preferida(fila)
        orig = nombre_desde_url(url) if url else "(sin url)"
        dest = f"convocatoria_{fila['_num_str']}_tdr{extension_desde_url(url) if url else '.pdf'}"
        print(f"  {fila['_num_str']:>12} | {orig}")
        print(f"               -> {dest}")
    print()

    manifest = coleccionar(
        tdr,
        tdr_dir=args.tdr_dir,
        archivos_dir=args.archivos_dir,
        descargar_faltantes=not args.sin_descarga,
    )
    manifest_path = args.tdr_dir / "manifest_tdr.csv"
    manifest.to_csv(manifest_path, index=False, encoding="utf-8")

    ok = (manifest["estado"] == "ok").sum()
    omit = (manifest["estado"] == "omitido_existe").sum()
    err = (manifest["estado"] == "error").sum()
    log.info("Listo. ok=%s omitidos=%s errores=%s | %s", ok, omit, err, manifest_path)


if __name__ == "__main__":
    main()
