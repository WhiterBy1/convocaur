from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.data import PROC_MATCHING, matching_summary
from app.services.jobs import get_job, list_jobs, start_job
from app.services.matching_graph import boost_detalle, build_grafo

router = APIRouter(tags=["matching"])


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


class RunMatchBody(BaseModel):
    convocatorias: list[str] | None = Field(
        default=None,
        description="IDs o números. None = todas las NLP.",
    )
    solo_faltantes: bool = True
    sin_embeddings: bool = False
    top: int = 15


@router.get("/summary")
def summary() -> dict:
    return matching_summary()


@router.get("/convocatorias")
def listar_convocatorias() -> list[dict]:
    return matching_summary().get("convocatorias", [])


@router.get("/jobs")
def jobs() -> list[dict]:
    return list_jobs()


@router.get("/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job no encontrado")
    return job


@router.post("/run")
def run_match(body: RunMatchBody) -> dict:
    """Lanza ranking en background (todas / faltantes / selección)."""

    def work(progress):
        from convocaur.matching.runner import run_matching

        return run_matching(
            body.convocatorias,
            top_k=body.top,
            sin_embeddings=body.sin_embeddings,
            solo_faltantes=body.solo_faltantes,
            on_progress=progress,
        )

    job_id = start_job("matching", work)
    return {"job_id": job_id, "status": "running", "poll": f"/api/matching/jobs/{job_id}"}


@router.get("/convocatorias/{conv_id}")
def detalle_convocatoria(conv_id: str) -> dict:
    from convocaur.matching.corpus import texto_convocatoria
    from convocaur.paths import PROC_ELEGIBILIDAD, PROC_NLP

    if not conv_id.startswith("convocatoria_"):
        conv_id = f"convocatoria_{conv_id}"

    nlp_path = PROC_NLP / f"{conv_id}_nlp.json"
    if not nlp_path.exists():
        raise HTTPException(404, f"Sin NLP para {conv_id}")

    nlp = _load_json(nlp_path)
    nlp_view = {k: v for k, v in nlp.items() if k != "elegibilidad_urosario"}

    eleg = None
    eleg_path = PROC_ELEGIBILIDAD / f"{conv_id}_elegibilidad.json"
    if eleg_path.exists():
        eleg_raw = _load_json(eleg_path)
        eleg = eleg_raw.get("veredicto_final") or eleg_raw

    return {
        "id": conv_id,
        "tiene_ranking": (PROC_MATCHING / f"ranking_{conv_id}.csv").exists(),
        "texto_matching": texto_convocatoria(nlp),
        "nlp": {
            "objetivo": nlp_view.get("objetivo"),
            "alianza_obligatoria": nlp_view.get("alianza_obligatoria"),
            "actores_elegibles": nlp_view.get("actores_elegibles") or [],
            "lineas_tematicas": nlp_view.get("lineas_tematicas") or [],
            "requisitos": (nlp_view.get("requisitos") or [])[:8],
            "criterios_evaluacion": (nlp_view.get("criterios_evaluacion") or [])[:6],
            "financiacion": nlp_view.get("financiacion"),
        },
        "elegibilidad_urosario": eleg,
    }


@router.get("/convocatorias/{conv_id}/ranking")
def ranking(conv_id: str, top: int = 15) -> dict:
    if not conv_id.startswith("convocatoria_"):
        conv_id = f"convocatoria_{conv_id}"
    path = PROC_MATCHING / f"ranking_{conv_id}.csv"
    if not path.exists():
        raise HTTPException(
            404,
            f"No hay ranking para {conv_id}. Usa POST /api/matching/run",
        )

    df = pd.read_csv(path)
    full_n = len(df)
    if top > 0:
        df = df.head(top)
    records = json.loads(df.to_json(orient="records", force_ascii=False))
    for r in records:
        r["caracteristicas"] = boost_detalle(r)

    numero = conv_id.replace("convocatoria_", "")
    return {
        "convocatoria": conv_id,
        "n": len(records),
        "n_pool": full_n,
        "rows": records,
        "grafo": build_grafo(conv_id, numero, records),
    }


@router.get("/profesores/{profesor_id}")
def profesor(profesor_id: str) -> dict:
    from convocaur.matching.corpus import meta_docente, texto_docente
    from convocaur.paths import JSON_PROFESORES

    path = JSON_PROFESORES / f"{profesor_id}.json"
    if not path.exists():
        raise HTTPException(404, f"Profesor no encontrado: {profesor_id}")
    doc = _load_json(path)
    if not doc.get("id"):
        doc["id"] = profesor_id
    return {
        "meta": meta_docente(doc),
        "texto_matching": texto_docente(doc),
        "areas_investigacion": doc.get("areas_investigacion") or [],
        "perfil_profesional": (doc.get("perfil_profesional") or "")[:1200],
        "tiene_cvlac": bool(doc.get("cvlac")),
        "cvlac_datos_generales": (doc.get("cvlac") or {}).get("datos_generales"),
        "cvlac_lineas": ((doc.get("cvlac") or {}).get("lineas_investigacion") or [])[:12],
        "url": doc.get("url"),
    }
