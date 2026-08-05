from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.plan_manejo import build_plan_manejo

router = APIRouter(tags=["plan"])


@router.get("/manejo")
def plan_manejo(top: int = Query(8, ge=1, le=20)) -> dict:
    """
    Resumen de convocatorias elegibles + docentes match + señal SECOP Cap.3
    y plan de manejo para las de mayor prioridad.
    """
    return build_plan_manejo(top_planes=top)
