"""
Piloto NLP: extrae campos P0 de TdR ya seccionados vía OpenRouter.
=================================================================
Uso:
    python nlp_tdr_piloto.py
    python nlp_tdr_piloto.py --convocatorias 48,45,976
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
import unicodedata
from pathlib import Path

# Permitir imports desde src/
from pydantic import BaseModel, ValidationError

from convocaur.nlp.extract_llm import extraer_seccion, get_client, get_model
from convocaur.nlp.map_seccion import seleccionar_secciones_p0
from convocaur.nlp.schemas import (
    ActorElegible,
    CausalRechazo,
    CriterioEvaluacion,
    ExtraccionTdr,
    Financiacion,
    LineaTematica,
    Requisito,
)
from convocaur.nlp.elegibilidad_urosario import evaluar_elegibilidad_urosario
from convocaur.paths import PROC_NLP, PROC_SECCIONES

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("nlp_tdr_piloto")

SECCIONES_DIR = PROC_SECCIONES
OUT_DIR = PROC_NLP

ORDEN_CLAVES = [
    "objetivo",
    "dirigida_a",
    "lineas_tematicas",
    "requisitos",
    "rechazo",
    "financiacion",
    "criterios",
]


# Alias de campos que el LLM a veces devuelve con otro nombre (observado:
# "text" en vez de "texto" en requisitos/causales de rechazo). Se normalizan
# antes de validar cada item por separado.
_ALIAS_ITEM = {"text": "texto"}


def _validar_items(modelo: type[BaseModel], items: list, convocatoria: str, clave: str) -> list[dict]:
    """Valida cada item de una lista contra su modelo Pydantic por separado.

    Un solo campo mal formado del LLM (ej. clave "text" en vez de "texto" en
    un requisito) no debe invalidar toda la convocatoria — antes,
    ExtraccionTdr.model_validate(base) fallaba entero por un ítem suelto y se
    perdían también objetivo/dirigida_a/financiación/etc. que sí habían
    quedado bien. Aquí se descarta solo el ítem problemático.
    """
    validos = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        item_norm = dict(item)
        for viejo, nuevo in _ALIAS_ITEM.items():
            if viejo in item_norm and nuevo not in item_norm:
                item_norm[nuevo] = item_norm.pop(viejo)
        try:
            modelo.model_validate(item_norm)
        except ValidationError as exc:
            log.warning("Conv %s: item de %s descartado (no valida): %s", convocatoria, clave, exc)
            continue
        validos.append(item_norm)
    return validos


def merge_parciales(convocatoria: str, parciales: dict[str, dict]) -> ExtraccionTdr:
    base: dict = {
        "convocatoria": convocatoria,
        "objetivo": None,
        "actores_elegibles": [],
        "alianza_obligatoria": None,
        "lineas_tematicas": [],
        "requisitos": [],
        "causales_rechazo": [],
        "criterios_evaluacion": [],
        "financiacion": None,
        "meta": {"secciones": {}},
    }

    for clave, res in parciales.items():
        base["meta"]["secciones"][clave] = res.get("meta", {})
        if not res.get("ok"):
            continue
        data = res.get("data") or {}
        if clave == "objetivo":
            base["objetivo"] = data.get("objetivo")
        elif clave == "dirigida_a":
            base["actores_elegibles"] = _validar_items(
                ActorElegible, data.get("actores_elegibles") or [], convocatoria, clave
            )
            base["alianza_obligatoria"] = data.get("alianza_obligatoria")
        elif clave == "lineas_tematicas":
            base["lineas_tematicas"] = _validar_items(
                LineaTematica, data.get("lineas_tematicas") or [], convocatoria, clave
            )
        elif clave == "requisitos":
            base["requisitos"] = _validar_items(
                Requisito, data.get("requisitos") or [], convocatoria, clave
            )
        elif clave == "rechazo":
            base["causales_rechazo"] = _validar_items(
                CausalRechazo, data.get("causales_rechazo") or [], convocatoria, clave
            )
        elif clave == "financiacion":
            fin = data.get("financiacion")
            if fin:
                try:
                    Financiacion.model_validate(fin)
                    base["financiacion"] = fin
                except ValidationError as exc:
                    log.warning("Conv %s: financiacion descartada (no valida): %s", convocatoria, exc)
        elif clave == "criterios":
            base["criterios_evaluacion"] = _validar_items(
                CriterioEvaluacion, data.get("criterios_evaluacion") or [], convocatoria, clave
            )

    return ExtraccionTdr.model_validate(base)


def _normalizar_titulo(texto: str | None) -> str:
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().upper()


def construir_texto_para_clave(doc: dict, clave: str, sec: dict | None) -> tuple[str, str]:
    if sec and (sec.get("texto") or "").strip():
        return sec.get("texto") or "", sec.get("titulo") or clave

    secciones = doc.get("secciones") or []
    if not secciones:
        return "", clave

    keywords_por_clave = {
        "objetivo": ["OBJETIVO", "OBJETIVOS", "PRESENTACION"],
        "dirigida_a": ["DIRIGID", "PARTICIPACION", "MECANISMO", "ACTORES", "ELEGIBLE", "PRESENTACION"],
        "lineas_tematicas": ["OBJETIVO", "OBJETIVOS", "PARTICIPACION", "DEMANDA", "TERRITORIAL", "TEMATIC", "LINEA", "EJE"],
        "requisitos": ["REQUISITO", "HABILITANTE", "DOCUMENTO"],
        "criterios": ["EVALUACION", "EVALUACI", "CRITERIO", "PUNTAJE", "CALIFIC"],
        "rechazo": ["RECHAZO", "INHABIL", "CAUSAL", "CONDICION"],
        "financiacion": ["FINANCI", "RECURSO", "PRESUP", "CRONOGRAMA", "PLAZO", "DURACION", "MONTO"],
    }

    keywords = keywords_por_clave.get(clave, [])
    candidatos = []
    if keywords:
        candidatos = [
            s for s in secciones
            if any(k in _normalizar_titulo(s.get("titulo")) for k in keywords)
        ]
    if not candidatos:
        candidatos = secciones

    texto = "\n\n".join(
        f"Sección: {s.get('titulo') or 'Sin título'}\n{(s.get('texto') or '').strip()}"
        for s in candidatos
        if (s.get('texto') or '').strip()
    )
    return texto, f"{clave} (contexto completo)"


def procesar_convocatoria(conv: str, client) -> ExtraccionTdr:
    path = SECCIONES_DIR / f"convocatoria_{conv}_secciones.json"
    if not path.exists():
        raise FileNotFoundError(path)

    doc = json.loads(path.read_text(encoding="utf-8"))
    p0 = seleccionar_secciones_p0(doc.get("secciones") or [])
    log.info("Conv %s: secciones P0 encontradas: %s", conv, list(p0.keys()))

    parciales = {}
    for clave in ORDEN_CLAVES:
        sec = p0.get(clave)
        texto, titulo = construir_texto_para_clave(doc, clave, sec)
        if not sec:
            log.warning("Conv %s: falta sección %s; usando contexto completo", conv, clave)
        if not texto.strip():
            parciales[clave] = {"ok": False, "data": {}, "meta": {"clave": clave, "error": "texto_ausente"}}
            continue
        log.info("  LLM %s (%s chars) …", clave, len(texto))
        parciales[clave] = extraer_seccion(
            clave=clave,
            texto=texto,
            titulo=titulo,
            client=client,
        )
        ok = parciales[clave]["ok"]
        log.info("  → %s", "ok" if ok else f"FAIL {parciales[clave]['meta']}")
        time.sleep(0.4)

    return merge_parciales(conv, parciales)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--convocatorias",
        default="48,45,976",
        help="IDs separados por coma (piloto default: 48,45,976)",
    )
    parser.add_argument(
        "--sin-elegibilidad",
        action="store_true",
        help="No evaluar elegibilidad Universidad del Rosario",
    )
    args = parser.parse_args()
    convs = [c.strip() for c in args.convocatorias.split(",") if c.strip()]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    client = get_client()
    model = get_model()
    log.info("Modelo: %s | convocatorias: %s", model, convs)

    resumen = []
    for conv in convs:
        try:
            ext = procesar_convocatoria(conv, client)
        except Exception as exc:
            log.error("Conv %s error fatal: %s", conv, exc)
            resumen.append({"convocatoria": conv, "error": str(exc)})
            continue

        payload = json.loads(ext.model_dump_json())
        if not args.sin_elegibilidad:
            log.info("  Elegibilidad URosario …")
            eleg = evaluar_elegibilidad_urosario(payload, usar_llm=True)
            payload["elegibilidad_urosario"] = eleg
            vf = eleg["veredicto_final"]
            log.info(
                "  → puede_postularse=%s modo=%s",
                vf.get("puede_postularse"),
                vf.get("modo"),
            )

        out_path = OUT_DIR / f"convocatoria_{conv}_nlp.json"
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        fin = payload.get("financiacion") or {}
        eleg_vf = (payload.get("elegibilidad_urosario") or {}).get("veredicto_final") or {}
        resumen.append({
            "convocatoria": conv,
            "objetivo_len": len(payload.get("objetivo") or ""),
            "n_actores": len(payload.get("actores_elegibles") or []),
            "alianza_obligatoria": payload.get("alianza_obligatoria"),
            "n_lineas": len(payload.get("lineas_tematicas") or []),
            "n_requisitos": len(payload.get("requisitos") or []),
            "n_rechazo": len(payload.get("causales_rechazo") or []),
            "n_criterios": len(payload.get("criterios_evaluacion") or []),
            "monto_cop": fin.get("monto_total_cop"),
            "urosario_puede_postularse": eleg_vf.get("puede_postularse"),
            "urosario_modo": eleg_vf.get("modo"),
            "urosario_rol": eleg_vf.get("rol_sugerido"),
            "archivo": str(out_path),
        })
        log.info(
            "Guardado %s | actores=%s req=%s crit=%s monto=%s urosario=%s",
            out_path.name,
            len(payload.get("actores_elegibles") or []),
            len(payload.get("requisitos") or []),
            len(payload.get("criterios_evaluacion") or []),
            fin.get("monto_total_cop"),
            eleg_vf.get("puede_postularse"),
        )

    resumen_path = OUT_DIR / "piloto_resumen.json"
    resumen_path.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== Resumen piloto ===")
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    print(f"\nSalida: {OUT_DIR}")


if __name__ == "__main__":
    main()
