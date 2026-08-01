"""ConvocaUR API — SECOP insights + matching."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from app.routers import matching, minciencias, overview, secop  # noqa: E402

app = FastAPI(
    title="ConvocaUR API",
    version="1.0.0",
    description="Backend para el dashboard SECOP CTeI y el matching docente ↔ convocatoria.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(overview.router, prefix="/api")
app.include_router(secop.router, prefix="/api/secop")
app.include_router(matching.router, prefix="/api/matching")
app.include_router(minciencias.router, prefix="/api/minciencias")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "convocaur-api"}
