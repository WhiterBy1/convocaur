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
#
# Nota: términos ambiguos que pueden aparecer en secciones distintas a la
# canónica (p. ej. "DEMANDAS TERRITORIALES" vs "LÍNEAS TEMÁTICAS", o
# "PROCEDIMIENTO DE EVALUACIÓN" vs "CRITERIOS DE EVALUACIÓN") NO se agregan
# aquí a propósito: en la plantilla estándar SGR/Minciencias la sección débil
# siempre aparece antes que la sección específica en el documento, y
# `seleccionar_secciones_p0` se queda con la primera coincidencia — agregarlos
# aquí le robaría la clave a la sección correcta en convocatorias que ya la
# tienen completa. Esos términos siguen cubiertos como último recurso en
# `piloto_tdr.construir_texto_para_clave`, que solo actúa cuando la sección
# canónica está ausente o vacía.
REGLAS = [
    ("objetivo", re.compile(r"^(OBJETIVO|OBJETIVOS|OBJETO)$")),
    ("dirigida_a", re.compile(r"^(DIRIGID[AO] A|MECANISMOS DE PARTICIPACION)$")),
    (
        "lineas_tematicas",
        re.compile(r"(LINEAS? TEMATICAS|EJES Y LINEAS|EJES TEMATICOS|MODALIDADES DE PARTICIPACION|LINEAS? DE ACCION|^TEMATICAS$)"),
    ),
    ("requisitos", re.compile(r"(REQUISITOS HABILITANTES|^REQUISITOS$)")),
    ("rechazo", re.compile(r"(CAUSALES DE RECHAZO|CONDICIONES DE RECHAZO|CONDICIONES INHABILITANTES|INHABILIDADES)")),
    ("financiacion", re.compile(r"(DURACION Y FINANCIACION|DURACION Y RECURSOS|^FINANCIACION)")),
    ("criterios", re.compile(r"CRITERIOS DE EVALUACION")),
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
