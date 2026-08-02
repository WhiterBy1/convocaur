from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.cap3_predict import ModelUnavailable, models_status, predict, predict_meta
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


@router.get("/predict/status")
def predict_status() -> dict:
    return models_status()


@router.get("/predict/meta")
def predict_meta_route() -> dict:
    return predict_meta()


class PredictBody(BaseModel):
    precio_base_cop: float = Field(..., ge=0)
    duracion_meses: float = Field(6, ge=0, le=120)
    numero_de_lotes: float = Field(1, ge=0, le=50)
    mes_publicacion: int = Field(6, ge=1, le=12)
    anio_publicacion: int = Field(2025, ge=2018, le=2030)
    modalidad: str = "Licitación pública"
    departamento: str = "Distrito Capital de Bogotá"
    entidad: str = ""


@router.post("/predict")
def predict_route(body: PredictBody) -> dict:
    try:
        return predict(body.model_dump())
    except ModelUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
