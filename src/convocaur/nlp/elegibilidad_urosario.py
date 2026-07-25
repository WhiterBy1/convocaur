"""
Verifica si Universidad del Rosario (IES) puede postularse a una convocatoria
según actores_elegibles + alianza_obligatoria + condiciones extraídas por NLP.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from typing import Any

from convocaur.nlp.perfil_urosario import PATRONES_IES, PERFIL_UROSARIO

log = logging.getLogger("nlp.elegibilidad_urosario")


def _norm(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().lower()


def _es_actor_ies(tipo: str) -> bool:
    t = _norm(tipo)
    return any(re.search(p, t, re.IGNORECASE) for p in PATRONES_IES)


def match_actores_ies(actores: list[dict]) -> list[dict]:
    hits = []
    for a in actores or []:
        if _es_actor_ies(a.get("tipo") or ""):
            hits.append(a)
    return hits


def verdicto_reglas(extraccion: dict) -> dict[str, Any]:
    """Capa determinista (sin LLM)."""
    actores = extraccion.get("actores_elegibles") or []
    alianza = extraccion.get("alianza_obligatoria")
    hits = match_actores_ies(actores)

    if not actores:
        return {
            "puede_postularse": None,
            "modo": "desconocido",
            "rol_sugerido": None,
            "confianza": "baja",
            "motivo": "No hay actores_elegibles extraidos; no se puede decidir.",
            "actores_ies_match": [],
            "condiciones_pendientes": [],
            "capa": "reglas",
        }

    if not hits:
        return {
            "puede_postularse": False,
            "modo": "no_elegible",
            "rol_sugerido": None,
            "confianza": "alta",
            "motivo": (
                "La convocatoria no lista IES/universidades como actor elegible. "
                "Universidad del Rosario no encaja como proponente/ejecutora por tipo institucional."
            ),
            "actores_ies_match": [],
            "condiciones_pendientes": [],
            "capa": "reglas",
        }

    roles = [_norm(h.get("rol") or "") for h in hits]
    roles_no_vacios = [r for r in roles if r]
    es_ejecutora = any(
        r in ("ejecutora", "proponente", "ejecutor") or "ejecut" in r or "propon" in r
        for r in roles_no_vacios
    )
    # Importante: all([]) es True en Python; solo aplica si hay roles explícitos
    es_solo_aliado = bool(roles_no_vacios) and all(
        r in ("aliada", "aliado", "colaboradora", "colaborador") for r in roles_no_vacios
    )

    # Si la condición menciona "entidad ejecutora"/"proponente", tratar como ejecutora
    for h in hits:
        c = _norm(h.get("condicion") or "")
        if re.search(r"entidad ejecutora|proponente|como ejecutor", c):
            es_ejecutora = True
            es_solo_aliado = False
            break

    condiciones = [h.get("condicion") for h in hits if h.get("condicion")]
    pendientes = []
    for cond in condiciones:
        c = _norm(cond)
        if re.search(r"sede|municipio|regi[oó]n|departamento|sgr|domicilio", c):
            pendientes.append({
                "condicion": cond,
                "riesgo": "territorio",
                "nota": "Puede exigir sede/domicilio regional; Rosario tiene sede principal en Bogota.",
            })
        if re.search(r"acreditaci[oó]n", c):
            pendientes.append({
                "condicion": cond,
                "riesgo": "acreditacion",
                "nota": "Verificar vigencia de acreditacion institucional/programas.",
            })
        if re.search(r"grupo|categoriz|a1|\ba\b|\bb\b|\bc\b|957", c):
            pendientes.append({
                "condicion": cond,
                "riesgo": "grupos_minciencias",
                "nota": "Requiere grupos categorizados; cruzar con capacidad Rosario.",
            })
        if re.search(r"experiencia|sgr|50\s*%", c):
            pendientes.append({
                "condicion": cond,
                "riesgo": "experiencia",
                "nota": "Validar experiencia acreditada en CTeI/regiones.",
            })

    if es_solo_aliado and not es_ejecutora:
        modo = "solo_como_aliado"
        puede = True
        motivo = (
            "Las IES solo aparecen con rol de aliado/colaborador; "
            "Rosario no seria proponente/ejecutora principal."
        )
        rol_sugerido = hits[0].get("rol") or "aliado"
    elif alianza is True:
        modo = "solo_en_alianza"
        puede = True
        rol_sugerido = "ejecutora" if es_ejecutora or not roles_no_vacios else (hits[0].get("rol") or "participante")
        motivo = (
            "Rosario (IES) es actor elegible, pero la alianza es obligatoria: "
            "puede postularse como parte de una alianza, no en solitario."
        )
    elif alianza is False:
        modo = "puede_sola_o_alianza"
        puede = True
        rol_sugerido = "ejecutora" if es_ejecutora or not roles_no_vacios else (hits[0].get("rol") or "participante")
        motivo = "Rosario (IES) es actor elegible y la alianza no es obligatoria."
    else:
        modo = "elegible_alianza_indefinida"
        puede = True
        rol_sugerido = "ejecutora" if es_ejecutora or not roles_no_vacios else (hits[0].get("rol") or "participante")
        motivo = "Rosario (IES) aparece como elegible; no esta claro si la alianza es obligatoria."

    confianza = "media" if pendientes else "alta"

    return {
        "puede_postularse": puede,
        "modo": modo,
        "rol_sugerido": rol_sugerido,
        "confianza": confianza,
        "motivo": motivo,
        "actores_ies_match": hits,
        "condiciones_pendientes": pendientes,
        "capa": "reglas",
        "perfil_usado": {
            "nombre": PERFIL_UROSARIO["nombre"],
            "tipo_actor": PERFIL_UROSARIO["tipo_actor"],
            "ciudad_sede_principal": PERFIL_UROSARIO["ciudad_sede_principal"],
        },
    }


# Reutilizamos el cliente OpenRouter con un schema ad-hoc (no esta en SCHEMAS_POR_CLAVE)
def verdicto_llm(extraccion: dict, verdicto_base: dict, client: dict | None = None) -> dict[str, Any]:
    """Segunda opinion del LLM sobre elegibilidad Rosario, anclada al JSON ya extraido."""
    from convocaur.nlp import extract_llm as el

    client = client or el.get_client()
    model = el.get_model()

    payload_contexto = {
        "perfil_urosario": PERFIL_UROSARIO,
        "veredicto_reglas": {
            k: verdicto_base.get(k)
            for k in ("puede_postularse", "modo", "rol_sugerido", "motivo", "condiciones_pendientes")
        },
        "actores_elegibles": extraccion.get("actores_elegibles"),
        "alianza_obligatoria": extraccion.get("alianza_obligatoria"),
        "objetivo": extraccion.get("objetivo"),
        "requisitos_sample": (extraccion.get("requisitos") or [])[:8],
    }

    system = (
        "Eres analista de elegibilidad de convocatorias Minciencias. "
        "Decide si Universidad del Rosario (IES privada, sede Bogota, actor SNCTI) "
        "PUEDE POSTULARSE. Responde SOLO JSON."
    )
    user = (
        "Con el perfil y los datos extraidos, responde JSON con:\n"
        "{\n"
        '  "puede_postularse": true/false,\n'
        '  "modo": "sola"|"solo_en_alianza"|"solo_como_aliado"|"no_elegible"|"elegible_con_condiciones",\n'
        '  "rol_sugerido": "ejecutora"|"proponente"|"aliado"|"colaborador"|null,\n'
        '  "bloqueantes": ["..."],\n'
        '  "condiciones_a_verificar": ["..."],\n'
        '  "resumen": "1-3 oraciones en espanol"\n'
        "}\n"
        "No inventes sedes regionales ni grupos si no estan en el perfil.\n\n"
        f"DATOS:\n{json.dumps(payload_contexto, ensure_ascii=False)}"
    )

    resp = None
    try:
        import requests

        r = requests.post(
            el.OPENROUTER_URL,
            headers=client["headers"],
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            },
            timeout=120,
        )
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"] or "{}"
        data = el._parse_json(raw)
        return {"ok": True, "data": data, "model": model}
    except Exception as exc:
        log.warning("LLM elegibilidad fallo: %s", exc)
        return {"ok": False, "error": str(exc), "data": {}}


def evaluar_elegibilidad_urosario(extraccion: dict, usar_llm: bool = True) -> dict[str, Any]:
    base = verdicto_reglas(extraccion)
    out = {
        "institucion": PERFIL_UROSARIO["nombre"],
        "reglas": base,
        "llm": None,
        "veredicto_final": {
            "puede_postularse": base["puede_postularse"],
            "modo": base["modo"],
            "rol_sugerido": base["rol_sugerido"],
            "resumen": base["motivo"],
            "fuente": "reglas",
        },
    }

    if usar_llm:
        llm = verdicto_llm(extraccion, base)
        out["llm"] = llm
        if llm.get("ok") and llm.get("data"):
            d = llm["data"]
            out["veredicto_final"] = {
                "puede_postularse": d.get("puede_postularse", base["puede_postularse"]),
                "modo": d.get("modo") or base["modo"],
                "rol_sugerido": d.get("rol_sugerido") or base["rol_sugerido"],
                "bloqueantes": d.get("bloqueantes") or [],
                "condiciones_a_verificar": d.get("condiciones_a_verificar") or [],
                "resumen": d.get("resumen") or base["motivo"],
                "fuente": "reglas+llm",
            }

    return out
