"""Matching híbrido convocatoria ↔ docente (embeddings + TF-IDF + boost)."""

from convocaur.matching.corpus import (
    cargar_docentes_json,
    cargar_nlp_dir,
    meta_docente,
    texto_convocatoria,
    texto_docente,
)
from convocaur.matching.ranker import rankear_convocatoria

__all__ = [
    "cargar_docentes_json",
    "cargar_nlp_dir",
    "meta_docente",
    "rankear_convocatoria",
    "texto_convocatoria",
    "texto_docente",
]
