"""Jobs en background (sync Minciencias / matching masivo)."""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Callable

_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def list_jobs(limit: int = 20) -> list[dict[str, Any]]:
    with _lock:
        items = sorted(_jobs.values(), key=lambda j: j.get("created_at", 0), reverse=True)
        return [dict(j) for j in items[:limit]]


def _update(job_id: str, **kwargs: Any) -> None:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(kwargs)


def start_job(kind: str, fn: Callable[[Callable[[dict], None]], Any]) -> str:
    job_id = uuid.uuid4().hex[:12]
    with _lock:
        _jobs[job_id] = {
            "id": job_id,
            "kind": kind,
            "status": "running",
            "created_at": time.time(),
            "updated_at": time.time(),
            "progress": {"fase": "inicio", "mensaje": "Arrancando…", "hecho": 0, "total": 0},
            "result": None,
            "error": None,
        }

    def progress(payload: dict) -> None:
        _update(job_id, progress=payload, updated_at=time.time())

    def worker() -> None:
        try:
            result = fn(progress)
            _update(
                job_id,
                status="done",
                result=result,
                updated_at=time.time(),
                progress={
                    "fase": "listo",
                    "mensaje": "Completado",
                    "hecho": (result or {}).get("n_procesadas")
                    or (result or {}).get("n_remotos")
                    or 1,
                    "total": (result or {}).get("n_procesadas")
                    or (result or {}).get("n_remotos")
                    or 1,
                },
            )
        except Exception as exc:
            _update(
                job_id,
                status="error",
                error=str(exc),
                updated_at=time.time(),
                progress={"fase": "error", "mensaje": str(exc)},
            )

    threading.Thread(target=worker, daemon=True).start()
    return job_id
