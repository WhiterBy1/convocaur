"""Ingesta de una convocatoria nueva: detalle → TdR → NLP → elegibilidad → matching → borrar PDF."""

from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import requests

from convocaur.minciencias.coleccionar_tdr import (
    es_tdr,
    extension_desde_url,
    slug_convocatoria,
    url_preferida,
)
from convocaur.minciencias.descargar import HEADERS, REQUEST_DELAY_SECONDS, carpeta_convocatoria
from convocaur.minciencias.scrape import extraer_detalle, id_desde_url
from convocaur.minciencias.secciones_tdr import procesar_pdf
from convocaur.paths import (
    ACTIVIDADES_CSV,
    DOCUMENTOS_CSV,
    LISTADO_CSV,
    PROC_ELEGIBILIDAD,
    PROC_NLP,
    PROC_SECCIONES,
    PROJECT_ROOT,
    RAW_MINCIENCIAS_ARCHIVOS,
    RAW_MINCIENCIAS_TDR,
    ensure_data_dirs,
)

log = logging.getLogger("ingest_convocatoria")

ProgressCb = Callable[[dict[str, Any]], None]


def _progress(cb: ProgressCb | None, **payload: Any) -> None:
    if cb:
        cb(payload)


def _norm_numero(n: str | int | None) -> str:
    s = str(n or "").strip().replace(".0", "")
    try:
        return str(int(float(s)))
    except (ValueError, TypeError):
        return s


def _upsert_csv(path: Path, rows: list[dict], key_cols: list[str]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    nuevo = pd.DataFrame(rows)
    if path.exists():
        try:
            old = pd.read_csv(path, dtype=str)
            combo = pd.concat([old, nuevo], ignore_index=True)
        except Exception:
            combo = nuevo
    else:
        combo = nuevo
    # Dedup suave por columnas clave si existen
    cols = [c for c in key_cols if c in combo.columns]
    if cols:
        combo = combo.drop_duplicates(subset=cols, keep="last")
    combo.to_csv(path, index=False, encoding="utf-8")


def _elegir_tdr_doc(documentos: list[dict]) -> dict | None:
    if not documentos:
        return None
    df = pd.DataFrame(documentos)
    mask = df.apply(es_tdr, axis=1)
    tdr = df[mask]
    if tdr.empty:
        return None
    return tdr.iloc[0].to_dict()


def _descargar_tdr(numero: str, doc: dict, tdr_dir: Path) -> Path:
    tdr_dir.mkdir(parents=True, exist_ok=True)
    url, _formato = url_preferida(pd.Series(doc))
    if not url:
        raise RuntimeError(f"Convocatoria {numero}: TdR detectado pero sin URL descargable.")

    dest = tdr_dir / f"convocatoria_{numero}_tdr{extension_desde_url(url)}"
    if dest.exists() and dest.stat().st_size > 0:
        log.info("TdR ya existe: %s", dest.name)
        return dest

    session = requests.Session()
    resp = session.get(url, headers=HEADERS, timeout=90)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    time.sleep(REQUEST_DELAY_SECONDS)
    log.info("TdR descargado (%s bytes): %s", len(resp.content), dest.name)
    return dest


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(p)


def _borrar_temporales(numero: str, tdr_path: Path | None) -> list[str]:
    borrados: list[str] = []
    if tdr_path and tdr_path.exists():
        tdr_path.unlink(missing_ok=True)
        borrados.append(_rel(tdr_path))
    for p in RAW_MINCIENCIAS_TDR.glob(f"convocatoria_{numero}_tdr.*"):
        p.unlink(missing_ok=True)
        borrados.append(_rel(p))
    carpeta = carpeta_convocatoria(RAW_MINCIENCIAS_ARCHIVOS, numero)
    if carpeta.exists():
        shutil.rmtree(carpeta, ignore_errors=True)
        borrados.append(_rel(carpeta))
    return borrados


def _guardar_secciones(numero: str, pdf_path: Path) -> Path:
    PROC_SECCIONES.mkdir(parents=True, exist_ok=True)
    res = procesar_pdf(pdf_path, ocr_si_vacio=True)
    # Forzar id de convocatoria del número pedido
    res["convocatoria"] = numero
    out = {k: v for k, v in res.items() if k != "texto_completo"}
    path = PROC_SECCIONES / f"convocatoria_{numero}_secciones.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _correr_nlp_y_elegibilidad(numero: str, usar_llm_eleg: bool = True) -> dict[str, Any]:
    from convocaur.nlp.elegibilidad_urosario import evaluar_elegibilidad_urosario
    from convocaur.nlp.extract_llm import get_client
    from convocaur.nlp.piloto_tdr import procesar_convocatoria

    PROC_NLP.mkdir(parents=True, exist_ok=True)
    PROC_ELEGIBILIDAD.mkdir(parents=True, exist_ok=True)

    client = get_client()
    ext = procesar_convocatoria(numero, client)
    payload = json.loads(ext.model_dump_json())
    eleg = evaluar_elegibilidad_urosario(payload, usar_llm=usar_llm_eleg)
    payload["elegibilidad_urosario"] = eleg

    nlp_path = PROC_NLP / f"convocatoria_{numero}_nlp.json"
    nlp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    eleg_path = PROC_ELEGIBILIDAD / f"convocatoria_{numero}_elegibilidad.json"
    eleg_path.write_text(json.dumps(eleg, ensure_ascii=False, indent=2), encoding="utf-8")

    vf = eleg.get("veredicto_final") or {}
    return {
        "nlp_path": str(nlp_path.relative_to(PROJECT_ROOT)),
        "elegibilidad_path": str(eleg_path.relative_to(PROJECT_ROOT)),
        "puede_postularse": vf.get("puede_postularse"),
        "modo": vf.get("modo"),
        "resumen_elegibilidad": vf.get("resumen"),
    }


def ingest_convocatoria(
    *,
    numero: str | None = None,
    url_detalle: str,
    titulo: str | None = None,
    matching_si_elegible: bool = True,
    borrar_pdf: bool = True,
    sin_embeddings: bool = False,
    top_k: int = 15,
    on_progress: ProgressCb | None = None,
) -> dict[str, Any]:
    """
    Pipeline local (y listo para Fly):
      detalle → descargar TdR → secciones → NLP+elegibilidad → matching (si aplica) → borrar PDF
    """
    ensure_data_dirs()
    RAW_MINCIENCIAS_TDR.mkdir(parents=True, exist_ok=True)

    result: dict[str, Any] = {
        "ok": False,
        "numero": None,
        "fases": [],
        "borrados": [],
        "error": None,
    }

    try:
        _progress(on_progress, fase="detalle", mensaje="Scrapeando detalle Minciencias…", hecho=0, total=6)
        detalle = extraer_detalle(url_detalle)
        num = _norm_numero(numero or detalle.numero)
        if not num:
            num = id_desde_url(url_detalle) or ""
        if not num:
            raise RuntimeError(
                "No se pudo determinar el número/id de convocatoria "
                "(ni en listado, ni en la página, ni en la URL)."
            )
        result["numero"] = num
        result["titulo"] = titulo or detalle.titulo
        result["url_detalle"] = url_detalle
        result["fases"].append("detalle")

        # Asegurar que docs/actividades lleven el id resuelto
        for doc in detalle.documentos:
            if not doc.get("convocatoria_numero"):
                doc["convocatoria_numero"] = num
        for act in detalle.actividades:
            if not act.get("convocatoria_numero"):
                act["convocatoria_numero"] = num

        # Persistencia mínima en CSVs canónicos
        list_row = {
            "numero": num,
            "titulo": detalle.titulo or titulo or "",
            "url_detalle": url_detalle,
            "descripcion": (detalle.objetivo or "")[:500],
            "total_recursos_texto": detalle.recursos_disponibles_texto or "",
            "fecha_apertura_texto": "",
        }
        _upsert_csv(LISTADO_CSV, [list_row], ["numero"])
        if detalle.documentos:
            _upsert_csv(
                DOCUMENTOS_CSV,
                detalle.documentos,
                ["convocatoria_numero", "nombre_documento", "tipo_actividad"],
            )
        if detalle.actividades:
            _upsert_csv(
                ACTIVIDADES_CSV,
                detalle.actividades,
                ["convocatoria_numero", "tipo_actividad", "fecha_texto"],
            )

        _progress(on_progress, fase="tdr", mensaje=f"Descargando TdR de #{num}…", hecho=1, total=6)
        doc_tdr = _elegir_tdr_doc(detalle.documentos)
        if not doc_tdr:
            raise RuntimeError(
                f"Convocatoria {num}: no se encontró documento de Términos de Referencia en la página."
            )
        tdr_path = _descargar_tdr(num, doc_tdr, RAW_MINCIENCIAS_TDR)
        result["tdr_path"] = str(tdr_path)
        result["fases"].append("tdr")

        _progress(on_progress, fase="secciones", mensaje="Extrayendo secciones del PDF…", hecho=2, total=6)
        sec_path = _guardar_secciones(num, tdr_path)
        result["secciones_path"] = str(sec_path.relative_to(PROJECT_ROOT))
        result["fases"].append("secciones")

        _progress(on_progress, fase="nlp", mensaje="NLP + elegibilidad (OpenRouter)…", hecho=3, total=6)
        nlp_info = _correr_nlp_y_elegibilidad(num, usar_llm_eleg=True)
        result.update(nlp_info)
        result["fases"].append("nlp")

        matching_info = None
        if matching_si_elegible and nlp_info.get("puede_postularse") is True:
            _progress(on_progress, fase="matching", mensaje="Calculando ranking de docentes…", hecho=4, total=6)
            from convocaur.matching.runner import run_matching

            matching_info = run_matching(
                [num],
                top_k=top_k,
                sin_embeddings=sin_embeddings,
                solo_faltantes=False,
            )
            result["matching"] = {
                "ok": matching_info.get("ok"),
                "procesadas": matching_info.get("procesadas"),
                "mensaje": matching_info.get("mensaje"),
                "uso_embeddings": matching_info.get("uso_embeddings"),
            }
            result["fases"].append("matching")
        else:
            result["matching"] = {
                "ok": True,
                "omitido": True,
                "motivo": (
                    "no_elegible"
                    if nlp_info.get("puede_postularse") is False
                    else "matching_desactivado_o_sin_veredicto"
                ),
            }
            result["fases"].append("matching_omitido")

        if borrar_pdf:
            _progress(on_progress, fase="limpieza", mensaje="Borrando PDF temporal…", hecho=5, total=6)
            result["borrados"] = _borrar_temporales(num, tdr_path)
            result["fases"].append("limpieza")

        result["ok"] = True
        matched = bool(
            result.get("matching")
            and not result["matching"].get("omitido")
            and result["matching"].get("ok")
        )
        result["mensaje"] = (
            f"Convocatoria #{num} ingestada"
            + (" con ranking de docentes." if matched else " (sin ranking).")
        )
        _progress(on_progress, fase="listo", mensaje=result["mensaje"], hecho=6, total=6)
        return result

    except Exception as exc:
        log.exception("Ingesta falló")
        result["error"] = str(exc)
        result["mensaje"] = f"Error en ingesta: {exc}"
        _progress(on_progress, fase="error", mensaje=str(exc), hecho=0, total=6)
        return result


def ingest_nuevas(
    nuevas_detalle: list[dict[str, Any]],
    *,
    matching_si_elegible: bool = True,
    borrar_pdf: bool = True,
    sin_embeddings: bool = False,
    top_k: int = 15,
    max_nuevas: int = 3,
    on_progress: ProgressCb | None = None,
) -> dict[str, Any]:
    """Procesa hasta max_nuevas convocatorias detectadas por el sync."""
    items = list(nuevas_detalle or [])[: max(0, max_nuevas)]
    resultados: list[dict[str, Any]] = []
    for i, item in enumerate(items):
        num = _norm_numero(item.get("numero"))
        url = (item.get("url_detalle") or "").strip()
        if not url:
            resultados.append({"ok": False, "numero": num, "error": "sin url_detalle"})
            continue
        _progress(
            on_progress,
            fase="ingest",
            mensaje=f"Ingestando nueva {i + 1}/{len(items)}: #{num}",
            hecho=i,
            total=len(items),
        )
        one = ingest_convocatoria(
            numero=num,
            url_detalle=url,
            titulo=item.get("titulo"),
            matching_si_elegible=matching_si_elegible,
            borrar_pdf=borrar_pdf,
            sin_embeddings=sin_embeddings,
            top_k=top_k,
            on_progress=on_progress,
        )
        resultados.append(one)

    ok_n = sum(1 for r in resultados if r.get("ok"))
    return {
        "ok": ok_n == len(resultados) if resultados else True,
        "n_solicitadas": len(items),
        "n_ok": ok_n,
        "n_error": len(resultados) - ok_n,
        "resultados": resultados,
        "mensaje": f"Ingestadas {ok_n}/{len(resultados)} convocatorias nuevas."
        if resultados
        else "No había convocatorias nuevas para ingerir.",
    }
