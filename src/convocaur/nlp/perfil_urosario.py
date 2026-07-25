"""Perfil institucional fijo de Universidad del Rosario para match de elegibilidad."""

from __future__ import annotations

PERFIL_UROSARIO = {
    "nombre": "Universidad del Rosario",
    "tipo_actor": "Institucion de Educacion Superior (IES)",
    "subtipo": "Universidad privada",
    "es_ies": True,
    "es_universidad": True,
    "reconocida_sncti": True,
    "acreditacion_institucional": True,  # asumir vigente; validar periodicamente
    "ciudad_sede_principal": "Bogota D.C.",
    "departamento_sede_principal": "Bogota D.C.",
    "tiene_sedes_regionales": False,  # no asumimos sedes fuera de Bogota sin dato
    "es_centro_investigacion_autonomo": False,
    "es_empresa": False,
    "es_entidad_territorial": False,
    "notas": (
        "Perfil base para elegibilidad. Condiciones especificas "
        "(grupos Minciencias, experiencia regional SGR, contrapartida) "
        "requieren validacion adicional con capacidad institucional."
    ),
}

# Patrones que indican que una IES/universidad es actor elegible
PATRONES_IES = [
    r"instituci[oó]n(?:es)?\s+de\s+educaci[oó]n\s+superior",
    r"\bies\b",
    r"universidades?",
    r"instituci[oó]n(?:es)?\s+universitaria",
]

# Actores que NO son Rosario (si la convocatoria SOLO admite estos, Rosario no entra como proponente)
PATRONES_NO_IES_PROPIO = [
    r"centros?\s+e?\s*institutos?\s+de\s+investigaci[oó]n",
    r"centros?\s+de\s+desarrollo\s+tecnol[oó]gico",
    r"centros?\s+de\s+ciencia",
    r"empresa",
    r"organizaci[oó]n(?:es)?\s+(?:comunitaria|local|campesina)",
    r"entidades?\s+territoriales?",
]
