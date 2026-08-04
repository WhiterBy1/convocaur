from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.jobs import get_job, start_job

router = APIRouter(tags=["minciencias"])


class SyncBody(BaseModel):
    paginas: int = Field(default=1, ge=1, le=30)
    procesar_nuevas: bool = True
    matching_si_elegible: bool = True
    borrar_pdf: bool = True
    sin_embeddings: bool = False
    max_nuevas: int = Field(default=3, ge=0, le=20)
    top: int = Field(default=15, ge=5, le=50)


class IngestBody(BaseModel):
    numero: str | None = None
    url_detalle: str
    titulo: str | None = None
    matching_si_elegible: bool = True
    borrar_pdf: bool = True
    sin_embeddings: bool = False
    top: int = Field(default=15, ge=5, le=50)


@router.post("/sync")
def sync_listado(body: SyncBody) -> dict:
    """Scrapea Minciencias, detecta nuevas y opcionalmente las ingesta (TdR→NLP→match→borra PDF)."""

    def work(progress):
        from app.services.minciencias_sync import sync_minciencias

        return sync_minciencias(
            paginas=body.paginas,
            procesar_nuevas=body.procesar_nuevas,
            matching_si_elegible=body.matching_si_elegible,
            borrar_pdf=body.borrar_pdf,
            sin_embeddings=body.sin_embeddings,
            max_nuevas=body.max_nuevas,
            top_k=body.top,
            on_progress=progress,
        )

    job_id = start_job("minciencias_sync", work)
    return {"job_id": job_id, "status": "running", "poll": f"/api/minciencias/jobs/{job_id}"}


@router.post("/ingest")
def ingest_una(body: IngestBody) -> dict:
    """Ingesta una convocatoria por URL (útil para probar el pipeline local)."""

    def work(progress):
        from app.services.ingest_convocatoria import ingest_convocatoria

        return ingest_convocatoria(
            numero=body.numero,
            url_detalle=body.url_detalle,
            titulo=body.titulo,
            matching_si_elegible=body.matching_si_elegible,
            borrar_pdf=body.borrar_pdf,
            sin_embeddings=body.sin_embeddings,
            top_k=body.top,
            on_progress=progress,
        )

    job_id = start_job("minciencias_ingest", work)
    return {"job_id": job_id, "status": "running", "poll": f"/api/minciencias/jobs/{job_id}"}


@router.get("/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job no encontrado")
    return job


@router.get("/ultimo-sync")
def ultimo_sync() -> dict:
    from pathlib import Path
    import json

    path = (
        Path(__file__).resolve().parents[3]
        / "data"
        / "processed"
        / "minciencias"
        / "ultimo_sync_minciencias.json"
    )
    if not path.exists():
        return {"ok": False, "mensaje": "Aún no se ha corrido un sync."}
    return json.loads(path.read_text(encoding="utf-8"))
