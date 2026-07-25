"""Schemas Pydantic para extracción estructurada de TdR Minciencias."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ActorElegible(BaseModel):
    tipo: str = Field(description="Ej: IES, centro de investigacion, empresa, alianzas SNCTI")
    rol: str | None = Field(default=None, description="proponente, aliado, ejecutor, etc.")
    condicion: str | None = Field(default=None, description="Requisito adicional del actor")


class LineaTematica(BaseModel):
    nombre: str
    modalidad: str | None = None
    descripcion_corta: str | None = None


class Requisito(BaseModel):
    texto: str
    tipo: Literal["habilitante", "documental", "tecnico", "financiero", "alianza", "otro"] = "otro"
    severidad: Literal["obligatorio", "deseable", "desconocido"] = "obligatorio"


class CausalRechazo(BaseModel):
    texto: str


class CriterioEvaluacion(BaseModel):
    nombre: str
    puntaje_max: float | None = None
    peso_pct: float | None = None
    descripcion: str | None = None


class Financiacion(BaseModel):
    monto_total_texto: str | None = None
    monto_total_cop: float | None = Field(default=None, description="Monto numerico en COP si es claro")
    plazo_min_meses: int | None = None
    plazo_max_meses: int | None = None
    contrapartida_pct_min: float | None = None
    contrapartida_pct_max: float | None = None
    fuente_recursos: str | None = None
    notas: str | None = None


class ExtraccionTdr(BaseModel):
    """Salida consolidada por convocatoria."""

    convocatoria: str
    objetivo: str | None = None
    actores_elegibles: list[ActorElegible] = Field(default_factory=list)
    alianza_obligatoria: bool | None = None
    lineas_tematicas: list[LineaTematica] = Field(default_factory=list)
    requisitos: list[Requisito] = Field(default_factory=list)
    causales_rechazo: list[CausalRechazo] = Field(default_factory=list)
    criterios_evaluacion: list[CriterioEvaluacion] = Field(default_factory=list)
    financiacion: Financiacion | None = None
    meta: dict = Field(default_factory=dict)
