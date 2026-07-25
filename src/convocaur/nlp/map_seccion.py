"""Mapeo de títulos de sección TdR → claves canónicas para NLP."""

from __future__ import annotations

import re
import unicodedata


CANONICAS = {
    "objetivo": "objetivo",
    "dirigida_a": "dirigida_a",
    "lineas_tematicas": "lineas_tematicas",
    "requisitos": "requisitos",
    "rechazo": "rechazo",
    "financiacion": "financiacion",
    "criterios": "criterios",
}

# Orden importa: primera coincidencia gana
REGLAS = [
    ("objetivo", re.compile(r"^OBJETIVO$")),
    ("dirigida_a", re.compile(r"^DIRIGID[AO] A$")),
    ("lineas_tematicas", re.compile(r"(LINEAS? TEMATICAS|EJES Y LINEAS|MODALIDADES DE PARTICIPACION)")),
    ("requisitos", re.compile(r"(REQUISITOS HABILITANTES|^REQUISITOS$)")),
    ("rechazo", re.compile(r"(CAUSALES DE RECHAZO|CONDICIONES DE RECHAZO|CONDICIONES INHABILITANTES)")),
    ("financiacion", re.compile(r"(DURACION Y FINANCIACION|DURACION Y RECURSOS|^FINANCIACION)")),
    ("criterios", re.compile(r"^CRITERIOS DE EVALUACION$")),
]


def _norm(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().upper()


def mapear_seccion(titulo_norm: str) -> str | None:
    t = _norm(titulo_norm)
    for clave, patron in REGLAS:
        if patron.search(t):
            return clave
    return None


def seleccionar_secciones_p0(secciones: list[dict]) -> dict[str, dict]:
    """Devuelve {clave_canonica: seccion} (primera coincidencia por clave)."""
    out: dict[str, dict] = {}
    for sec in secciones:
        clave = mapear_seccion(sec.get("titulo_norm") or sec.get("titulo") or "")
        if clave and clave not in out:
            out[clave] = sec
    return out
