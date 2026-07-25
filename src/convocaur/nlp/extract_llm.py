"""
Cliente OpenRouter (HTTP) para extracción estructurada de secciones TdR.
Sin dependencia del SDK openai (más liviano / estable en este entorno).
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from convocaur.paths import ENV_FILE, PROJECT_ROOT

log = logging.getLogger("nlp.openrouter")

load_dotenv(ENV_FILE)
load_dotenv(PROJECT_ROOT.parent / ".env")  # fallback: .env en la raíz del monorepo

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "deepseek/deepseek-v4-flash"
MAX_CHARS_SECCION = 14000


SYSTEM_PROMPT = """Eres un extractor de datos de Términos de Referencia (TdR) de Minciencias (Colombia).
Devuelves SOLO JSON válido, sin markdown ni comentarios.
Ignora encabezados/pies de página repetidos (direcciones, PBX, 'Página X de Y', códigos de versión).
No inventes datos: si no está en el texto, usa null o [].
Montos en COP como número sin puntos de miles cuando sea posible.
Porcentajes como número (ej. 30 no "30%").
Sé conciso en descripciones (máx 1-2 frases)."""


SCHEMAS_POR_CLAVE: dict[str, dict[str, Any]] = {
    "objetivo": {
        "type": "object",
        "properties": {"objetivo": {"type": ["string", "null"]}},
        "required": ["objetivo"],
    },
    "dirigida_a": {
        "type": "object",
        "properties": {
            "actores_elegibles": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "tipo": {"type": "string"},
                        "rol": {"type": ["string", "null"]},
                        "condicion": {"type": ["string", "null"]},
                    },
                    "required": ["tipo"],
                },
            },
            "alianza_obligatoria": {"type": ["boolean", "null"]},
        },
        "required": ["actores_elegibles", "alianza_obligatoria"],
    },
    "lineas_tematicas": {
        "type": "object",
        "properties": {
            "lineas_tematicas": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "nombre": {"type": "string"},
                        "modalidad": {"type": ["string", "null"]},
                        "descripcion_corta": {"type": ["string", "null"]},
                    },
                    "required": ["nombre"],
                },
            }
        },
        "required": ["lineas_tematicas"],
    },
    "requisitos": {
        "type": "object",
        "properties": {
            "requisitos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "texto": {"type": "string"},
                        "tipo": {
                            "type": "string",
                            "enum": ["habilitante", "documental", "tecnico", "financiero", "alianza", "otro"],
                        },
                        "severidad": {
                            "type": "string",
                            "enum": ["obligatorio", "deseable", "desconocido"],
                        },
                    },
                    "required": ["texto", "tipo", "severidad"],
                },
            }
        },
        "required": ["requisitos"],
    },
    "rechazo": {
        "type": "object",
        "properties": {
            "causales_rechazo": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"texto": {"type": "string"}},
                    "required": ["texto"],
                },
            }
        },
        "required": ["causales_rechazo"],
    },
    "financiacion": {
        "type": "object",
        "properties": {
            "financiacion": {
                "type": "object",
                "properties": {
                    "monto_total_texto": {"type": ["string", "null"]},
                    "monto_total_cop": {"type": ["number", "null"]},
                    "plazo_min_meses": {"type": ["integer", "null"]},
                    "plazo_max_meses": {"type": ["integer", "null"]},
                    "contrapartida_pct_min": {"type": ["number", "null"]},
                    "contrapartida_pct_max": {"type": ["number", "null"]},
                    "fuente_recursos": {"type": ["string", "null"]},
                    "notas": {"type": ["string", "null"]},
                },
            }
        },
        "required": ["financiacion"],
    },
    "criterios": {
        "type": "object",
        "properties": {
            "criterios_evaluacion": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "nombre": {"type": "string"},
                        "puntaje_max": {"type": ["number", "null"]},
                        "peso_pct": {"type": ["number", "null"]},
                        "descripcion": {"type": ["string", "null"]},
                    },
                    "required": ["nombre"],
                },
            }
        },
        "required": ["criterios_evaluacion"],
    },
}

INSTRUCCIONES_POR_CLAVE = {
    "objetivo": "Extrae el objetivo general de la convocatoria en 1-3 oraciones.",
    "dirigida_a": "Lista los tipos de actores/entidades que pueden participar y si la alianza es obligatoria.",
    "lineas_tematicas": "Lista modalidades y/o líneas temáticas mencionadas.",
    "requisitos": "Lista requisitos habilitantes o de participación (máx 25 items, los más importantes). No copies pies de página.",
    "rechazo": "Lista causales o condiciones de rechazo/inhabilidad (máx 20).",
    "financiacion": "Extrae monto total, plazos en meses, porcentajes de contrapartida y fuente de recursos.",
    "criterios": "Lista criterios de evaluación con puntaje máximo o peso si aparecen (máx 20).",
}


def get_api_key() -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or api_key.endswith("..."):
        raise RuntimeError(
            "Falta OPENROUTER_API_KEY en .env (raíz del repo). Ver .env.example"
        )
    return api_key


def get_model() -> str:
    return os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)


def get_client() -> dict:
    """Compat: el 'client' es un dict con headers reutilizables."""
    return {
        "api_key": get_api_key(),
        "headers": {
            "Authorization": f"Bearer {get_api_key()}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/servisquad-reto",
            "X-Title": "ConvocaUR-ETL-NLP",
        },
    }


def _truncar(texto: str, max_chars: int = MAX_CHARS_SECCION) -> tuple[str, bool]:
    texto = texto.strip()
    if len(texto) <= max_chars:
        return texto, False
    return texto[:max_chars] + "\n\n[TEXTO TRUNCADO]", True


def _parse_json(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    return json.loads(content)


def extraer_seccion(
    clave: str,
    texto: str,
    titulo: str,
    client: dict | None = None,
    model: str | None = None,
    max_retries: int = 2,
) -> dict[str, Any]:
    """Llama a OpenRouter y devuelve dict parcial + meta."""
    if clave not in SCHEMAS_POR_CLAVE:
        raise ValueError(f"Clave no soportada: {clave}")

    client = client or get_client()
    model = model or get_model()
    texto_envio, truncado = _truncar(texto)

    user = (
        f"Sección: {titulo}\n"
        f"Tarea: {INSTRUCCIONES_POR_CLAVE[clave]}\n"
        f"Schema esperado (campos): {json.dumps(SCHEMAS_POR_CLAVE[clave], ensure_ascii=False)}\n\n"
        f"TEXTO:\n{texto_envio}"
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    ultimo_error = None
    for intento in range(max_retries + 1):
        try:
            resp = requests.post(
                OPENROUTER_URL,
                headers=client["headers"],
                json=payload,
                timeout=120,
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
            body = resp.json()
            raw = body["choices"][0]["message"]["content"] or "{}"
            data = _parse_json(raw)
            usage = body.get("usage") or {}
            return {
                "ok": True,
                "data": data,
                "meta": {
                    "clave": clave,
                    "model": model,
                    "truncado": truncado,
                    "chars_enviados": len(texto_envio),
                    "intento": intento + 1,
                    "usage": {
                        "prompt_tokens": usage.get("prompt_tokens"),
                        "completion_tokens": usage.get("completion_tokens"),
                    },
                },
            }
        except Exception as exc:
            ultimo_error = exc
            log.warning("Intento %s falló (%s): %s", intento + 1, clave, exc)
            time.sleep(1.5 * (intento + 1))

    return {
        "ok": False,
        "data": {},
        "meta": {"clave": clave, "error": str(ultimo_error)},
    }
