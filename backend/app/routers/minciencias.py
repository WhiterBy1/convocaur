from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.jobs import get_job, start_job

router = APIRouter(tags=["minciencias"])


class SyncBody(BaseModel):
    paginas: int = Field(default=8, ge=1, le=30)


@router.post("/sync")
def sync_listado(body: SyncBody) -> dict:
    """Scrapea Minciencias y detecta convocatorias nuevas."""

    def work(progress):
        from app.services.minciencias_sync import sync_minciencias

        return sync_minciencias(paginas=body.paginas, on_progress=progress)

    job_id = start_job("minciencias_sync", work)
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
