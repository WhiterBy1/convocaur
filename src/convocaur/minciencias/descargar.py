"""
Descarga de anexos/archivos Minciencias - ConvocaUR
===================================================
Rol: Ingesta

Lee el CSV de documentos (salida de scrape_minciencias) y descarga
cada archivo (PDF y/o editable) organizándolos por carpeta:

    data/raw/minciencias/archivos/
      convocatoria_{numero}/
        {nombre_archivo}.pdf
        {nombre_archivo}.docx
      ...

Modos:
  - Piloto (rápido): solo las N convocatorias más recientes ya extraídas.
  - Completo: todas las filas del CSV (todas las convocatorias/años
    presentes en el extracto).
  - Opcional: re-scrapear el listado antes de descargar.

Uso:
    # Piloto: 5 convocatorias más recientes del CSV ya extraído
    python descargar_anexos_minciencias.py --piloto

    # Todas las del CSV (TdR, resoluciones, anexos, etc.)
    python descargar_anexos_minciencias.py

    # Solo filas clasificadas como anexo
    python descargar_anexos_minciencias.py --solo-anexos

    # Scrapear más páginas y luego descargar
    python descargar_anexos_minciencias.py --scrapear --paginas 50
"""

from __future__ import annotations

import argparse
import logging
import re
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("descargar_anexos_minciencias")

HEADERS = {"User-Agent": "ConvocaUR-ETL/0.1 (proyecto academico Universidad del Rosario)"}
REQUEST_DELAY_SECONDS = 1.0

from convocaur.paths import DOCUMENTOS_CSV, LISTADO_CSV, RAW_MINCIENCIAS_ARCHIVOS

DEFAULT_DOCS_CSV = DOCUMENTOS_CSV
DEFAULT_LISTADO_CSV = LISTADO_CSV
DEFAULT_OUT_DIR = RAW_MINCIENCIAS_ARCHIVOS


def nombre_desde_url(url: str) -> str:
    path = unquote(urlparse(url).path)
    nombre = Path(path).name
    if not nombre:
        nombre = "archivo_sin_nombre"
    # Evitar caracteres problemáticos en Windows
    return re.sub(r'[<>:"/\\|?*]', "_", nombre)


def carpeta_convocatoria(out_dir: Path, numero) -> Path:
    if pd.isna(numero) or str(numero).strip() == "":
        slug = "sin_numero"
    else:
        # "978.0" -> "978"
        try:
            slug = str(int(float(numero)))
        except (ValueError, TypeError):
            slug = re.sub(r"[^\w\-]+", "_", str(numero)).strip("_") or "sin_numero"
    return out_dir / f"convocatoria_{slug}"


def descargar_archivo(url: str, destino: Path, session: requests.Session, timeout: int = 60) -> dict:
    """Descarga url -> destino. Si ya existe, lo omite."""
    resultado = {
        "url": url,
        "ruta_local": str(destino),
        "estado": None,
        "bytes": None,
        "error": None,
    }

    if destino.exists() and destino.stat().st_size > 0:
        resultado["estado"] = "omitido_existe"
        resultado["bytes"] = destino.stat().st_size
        log.info("  omitido (ya existe): %s", destino.name)
        return resultado

    try:
        resp = session.get(url, headers=HEADERS, timeout=timeout, stream=True)
        resp.raise_for_status()
        destino.parent.mkdir(parents=True, exist_ok=True)
        with open(destino, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
        resultado["estado"] = "ok"
        resultado["bytes"] = destino.stat().st_size
        log.info("  ok (%s bytes): %s", resultado["bytes"], destino.name)
    except Exception as exc:
        resultado["estado"] = "error"
        resultado["error"] = str(exc)
        log.error("  error %s -> %s", url, exc)
        if destino.exists():
            destino.unlink(missing_ok=True)

    time.sleep(REQUEST_DELAY_SECONDS)
    return resultado


def preparar_dataframe(
    docs_csv: Path,
    listado_csv: Path | None,
    solo_anexos: bool,
    max_convocatorias: int | None,
) -> pd.DataFrame:
    df = pd.read_csv(docs_csv)
    if solo_anexos:
        df = df[df["tipo_documento"] == "anexo"].copy()
        log.info("Filtrado a tipo_documento=anexo: %s filas", len(df))

    # Orden de convocatorias: el del listado (más recientes primero);
    # si no hay listado, el orden de aparición en el CSV de documentos.
    if listado_csv and listado_csv.exists():
        listado = pd.read_csv(listado_csv)
        orden = (
            listado["numero"]
            .dropna()
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .tolist()
        )
        # Incluir convocatorias sin número al final (ej. concursos)
        df["_num_str"] = (
            df["convocatoria_numero"]
            .apply(lambda x: "" if pd.isna(x) else str(int(float(x))) if str(x).replace(".", "", 1).isdigit() else str(x))
        )
        ranking = {n: i for i, n in enumerate(orden)}
        df["_rank"] = df["_num_str"].map(lambda n: ranking.get(n, 10_000))
        df = df.sort_values(["_rank", "numero_anexo"], kind="stable")
    else:
        df["_num_str"] = df["convocatoria_numero"].astype(str)
        df["_rank"] = range(len(df))

    if max_convocatorias is not None:
        # Primeras N convocatorias distintas en el orden ya establecido
        vistas = []
        for num in df["_num_str"]:
            if num not in vistas:
                vistas.append(num)
            if len(vistas) >= max_convocatorias:
                break
        df = df[df["_num_str"].isin(vistas)].copy()
        log.info(
            "Piloto: %s convocatorias -> %s documentos (%s)",
            len(vistas),
            len(df),
            ", ".join(v or "sin_numero" for v in vistas),
        )

    return df


def expandir_urls(df: pd.DataFrame) -> list[dict]:
    """Una fila del CSV puede tener url_pdf y/o url_editable -> varias descargas."""
    items = []
    for _, fila in df.iterrows():
        base = {
            "convocatoria_numero": fila.get("convocatoria_numero"),
            "nombre_documento": fila.get("nombre_documento"),
            "tipo_documento": fila.get("tipo_documento"),
            "numero_anexo": fila.get("numero_anexo"),
            "subtipo_anexo": fila.get("subtipo_anexo"),
            "tipo_actividad": fila.get("tipo_actividad"),
        }
        for campo in ("url_pdf", "url_editable"):
            url = fila.get(campo)
            if pd.notna(url) and str(url).strip():
                items.append({**base, "formato": campo.replace("url_", ""), "url": str(url).strip()})
    return items


def descargar_lote(items: list[dict], out_dir: Path) -> pd.DataFrame:
    session = requests.Session()
    registros = []
    total = len(items)
    for i, item in enumerate(items, 1):
        carpeta = carpeta_convocatoria(out_dir, item["convocatoria_numero"])
        nombre = nombre_desde_url(item["url"])
        destino = carpeta / nombre
        log.info("[%s/%s] conv %s | %s", i, total, item["convocatoria_numero"], item["nombre_documento"])
        res = descargar_archivo(item["url"], destino, session)
        registros.append({**item, **res})
    return pd.DataFrame(registros)


def scrapear_y_guardar(paginas: int, docs_csv: Path, listado_csv: Path) -> None:
    from scrape_minciencias import extraer_detalle, extraer_listado

    df_listado = extraer_listado(paginas)
    docs_csv.parent.mkdir(parents=True, exist_ok=True)
    df_listado.to_csv(listado_csv, index=False, encoding="utf-8")

    todas_actividades = []
    todos_documentos = []
    for _, fila in df_listado.iterrows():
        if not fila["url_detalle"]:
            continue
        try:
            detalle = extraer_detalle(fila["url_detalle"])
        except Exception as exc:
            log.error("Fallo detalle %s: %s", fila["url_detalle"], exc)
            continue
        todas_actividades.extend(detalle.actividades)
        todos_documentos.extend(detalle.documentos)
        log.info(
            "Convocatoria %s: %s docs",
            detalle.numero,
            len(detalle.documentos),
        )

    pd.DataFrame(todos_documentos).to_csv(docs_csv, index=False, encoding="utf-8")
    act_path = docs_csv.parent / "convocatorias_actividades_raw.csv"
    pd.DataFrame(todas_actividades).to_csv(act_path, index=False, encoding="utf-8")
    log.info("CSV actualizados en %s", docs_csv.parent)


def main():
    parser = argparse.ArgumentParser(description="Descarga anexos/archivos de convocatorias Minciencias")
    parser.add_argument(
        "--piloto",
        action="store_true",
        help="Descarga solo las 5 convocatorias más recientes del CSV (prueba rápida)",
    )
    parser.add_argument(
        "--max-convocatorias",
        type=int,
        default=None,
        help="Limitar a N convocatorias más recientes (sobrescribe el 5 de --piloto)",
    )
    parser.add_argument(
        "--solo-anexos",
        action="store_true",
        help="Descargar solo tipo_documento=anexo (por defecto baja todos: TdR, resoluciones, etc.)",
    )
    parser.add_argument("--docs-csv", type=Path, default=DEFAULT_DOCS_CSV)
    parser.add_argument("--listado-csv", type=Path, default=DEFAULT_LISTADO_CSV)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--scrapear",
        action="store_true",
        help="Antes de descargar, re-extraer listado/detalle de Minciencias",
    )
    parser.add_argument(
        "--paginas",
        type=int,
        default=50,
        help="Páginas del listado a scrapear si --scrapear (default 50 ~ todos los años recientes)",
    )
    args = parser.parse_args()

    max_conv = args.max_convocatorias
    if args.piloto and max_conv is None:
        max_conv = 5

    if args.scrapear:
        scrapear_y_guardar(args.paginas, args.docs_csv, args.listado_csv)

    if not args.docs_csv.exists():
        raise SystemExit(f"No existe el CSV de documentos: {args.docs_csv}")

    df = preparar_dataframe(
        docs_csv=args.docs_csv,
        listado_csv=args.listado_csv,
        solo_anexos=args.solo_anexos,
        max_convocatorias=max_conv,
    )
    items = expandir_urls(df)
    if not items:
        raise SystemExit("No hay URLs para descargar con los filtros dados.")

    log.info("Descargas pendientes: %s archivos -> %s", len(items), args.out_dir)
    manifest = descargar_lote(items, args.out_dir)

    manifest_path = args.out_dir / "manifest_descargas.csv"
    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(manifest_path, index=False, encoding="utf-8")

    ok = (manifest["estado"] == "ok").sum()
    omit = (manifest["estado"] == "omitido_existe").sum()
    err = (manifest["estado"] == "error").sum()
    log.info("Listo. ok=%s omitidos=%s errores=%s | manifest=%s", ok, omit, err, manifest_path)


if __name__ == "__main__":
    main()
