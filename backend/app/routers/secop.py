from fastapi import APIRouter

from app.services.data import load_bitacora, load_dashboard, load_manifest

router = APIRouter(tags=["secop"])


@router.get("/dashboard")
def dashboard() -> dict:
    return load_dashboard()


@router.get("/bitacora")
def bitacora() -> list[dict]:
    return load_bitacora()


@router.get("/manifest")
def manifest() -> dict:
    return load_manifest()


@router.get("/capacidad/{n}")
def capacidad(n: int) -> dict:
    dash = load_dashboard()
    key = f"capacidad_{n}"
    if key not in dash:
        return {"error": f"Capacidad {n} no encontrada", "disponibles": [1, 2, 3]}
    return {"capacidad": n, "data": dash[key], "meta": dash.get("meta")}
