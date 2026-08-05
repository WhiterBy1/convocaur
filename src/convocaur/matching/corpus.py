"""Construye textos canónicos para matching convocatoria ↔ docente."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _clip(text: str, n: int = 800) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= n else text[: n - 1] + "…"


def texto_convocatoria(nlp: dict[str, Any]) -> str:
    partes = []
    if nlp.get("objetivo"):
        partes.append(f"Objetivo: {nlp['objetivo']}")

    lineas = nlp.get("lineas_tematicas") or []
    if lineas:
        nombres = []
        for ln in lineas[:12]:
            nom = ln.get("nombre") or ""
            mod = ln.get("modalidad") or ""
            nombres.append(f"{nom}" + (f" ({mod})" if mod else ""))
        partes.append("Líneas temáticas: " + "; ".join(nombres))

    reqs = nlp.get("requisitos") or []
    if reqs:
        partes.append(
            "Requisitos: "
            + "; ".join((r.get("texto") or "")[:180] for r in reqs[:8] if r.get("texto"))
        )

    crits = nlp.get("criterios_evaluacion") or []
    if crits:
        partes.append(
            "Criterios: "
            + "; ".join(
                (c.get("nombre") or "")
                + (f" ({c.get('puntaje_max')})" if c.get("puntaje_max") is not None else "")
                for c in crits[:6]
            )
        )

    if nlp.get("alianza_obligatoria") is True:
        partes.append("Alianza obligatoria: sí")
    elif nlp.get("alianza_obligatoria") is False:
        partes.append("Alianza obligatoria: no")

    text = _clip("\n".join(partes), 3500)
    return text if text.strip() else "Convocatoria sin texto NLP estructurado"


def _categoria_cvlac(doc: dict[str, Any]) -> str | None:
    cv = doc.get("cvlac") or {}
    dg = cv.get("datos_generales") or {}
    return dg.get("Categoría") or dg.get("Categoria")


def texto_docente(doc: dict[str, Any]) -> str:
    partes = []
    nombre = doc.get("nombre") or doc.get("id") or ""
    fac = doc.get("facultad_csv") or ""
    cargo = doc.get("cargo_csv") or doc.get("cargo_principal") or ""
    partes.append(f"Docente: {nombre}. Facultad: {fac}. Cargo: {cargo}.")

    cat = _categoria_cvlac(doc)
    if cat:
        partes.append(f"Categoría Minciencias: {cat}")

    areas = doc.get("areas_investigacion") or []
    if areas:
        partes.append("Áreas: " + "; ".join(str(a) for a in areas[:12]))

    if doc.get("perfil_profesional"):
        partes.append("Perfil: " + _clip(str(doc["perfil_profesional"]), 600))

    cv = doc.get("cvlac") or {}
    lineas = cv.get("lineas_investigacion") or []
    if lineas:
        partes.append("Líneas CvLAC: " + "; ".join(_clip(str(x), 120) for x in lineas[:10]))

    areas_act = cv.get("areas_actuacion") or []
    if areas_act:
        partes.append("Áreas actuación: " + "; ".join(_clip(str(x), 100) for x in areas_act[:8]))

    proyectos = cv.get("proyectos") or doc.get("proyectos") or []
    titulos = []
    for p in proyectos[:8]:
        if isinstance(p, dict):
            titulos.append(p.get("titulo") or str(p)[:120])
        else:
            titulos.append(_clip(str(p), 120))
    if titulos:
        partes.append("Proyectos: " + "; ".join(titulos))

    return _clip("\n".join(partes), 3500)


def _nombre_persona(nombre: str | None, *fallbacks: str | None) -> str:
    """Quita ORCID/URLs y humaniza slugs (para UI / matching)."""
    import re

    raw = str(nombre or "").strip()
    if not raw or raw.lower() in ("nan", "none"):
        for fb in fallbacks:
            raw = str(fb or "").strip()
            if raw and raw.lower() not in ("nan", "none"):
                break

    raw = re.sub(r"https?://(?:www\.)?orcid\.org/\S+", "", raw, flags=re.I)
    raw = re.sub(r"(?i)\s*[|/]\s*orcid\.org/\S+", "", raw)
    raw = re.sub(r"(?i)\borcid\.org/\S+", "", raw)
    raw = re.sub(r"(?i)\bORCID\s*[:=]?\s*\d{4}-\d{4}-\d{4}-\d{3}[\dXx]\b", "", raw)
    raw = re.sub(r"\b\d{4}-\d{4}-\d{4}-\d{3}[\dXx]\b", "", raw)
    raw = re.sub(r"\s*[|/]\s*$", "", raw)
    raw = re.sub(r"\s{2,}", " ", raw).strip(" -|/")

    if raw and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)+", raw):
        raw = raw.replace("-", " ").title()
    elif raw and "-" in raw and " " not in raw and raw.lower() == raw:
        raw = raw.replace("-", " ").title()
    else:
        raw = re.sub(
            r"([A-Za-zÁÉÍÓÚáéíóúÑñ])-([A-Za-zÁÉÍÓÚáéíóúÑñ])",
            r"\1 \2",
            raw,
        )

    if not raw:
        for fb in fallbacks:
            cand = str(fb or "").strip()
            if cand and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)+", cand):
                return cand.replace("-", " ").title()
            if cand:
                return cand
        return "Docente"
    return raw


def meta_docente(doc: dict[str, Any]) -> dict[str, Any]:
    nombre = doc.get("nombre") or ""
    if not str(nombre).strip():
        nombre = doc.get("nombre_completo") or doc.get("id") or ""
    return {
        "id": doc.get("id"),
        "nombre": _nombre_persona(nombre, doc.get("nombre_completo"), doc.get("id")),
        "facultad": doc.get("facultad_csv"),
        "cargo": doc.get("cargo_csv") or doc.get("cargo_principal"),
        "tiene_cvlac": bool(doc.get("cvlac")),
        "categoria": _categoria_cvlac(doc),
        "n_areas": len(doc.get("areas_investigacion") or []),
    }


def cargar_nlp_dir(nlp_dir: Path) -> dict[str, dict]:
    out = {}
    for f in sorted(nlp_dir.glob("convocatoria_*_nlp.json")):
        out[f.stem.replace("_nlp", "")] = json.loads(f.read_text(encoding="utf-8"))
    return out


def cargar_docentes_json(json_dir: Path, limite: int | None = None) -> list[dict]:
    files = sorted(json_dir.glob("*.json"))
    if limite is not None:
        files = files[:limite]
    docs = []
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        if not d.get("id"):
            d["id"] = f.stem
        txt = texto_docente(d)
        if len(txt) < 40:
            continue
        docs.append(d)
    return docs
