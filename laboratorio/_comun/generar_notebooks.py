"""Genera exploracion.ipynb para cada persona del laboratorio."""

from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]  # laboratorio/
PERSONAS = [
    ("josue", "Josue"),
    ("andres", "Andres"),
    ("victor", "Victor"),
    ("jose", "Jose"),
    ("rodolfo", "Rodolfo"),
]


def md(text: str) -> dict:
    lines = text.split("\n")
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [ln + "\n" for ln in lines],
    }


def code(text: str) -> dict:
    lines = text.split("\n")
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [ln + "\n" for ln in lines],
    }


def build(slug: str, nombre: str) -> dict:
    setup = f'''from pathlib import Path
import sys

# Raices
PERSONA = "{slug}"
NB_DIR = Path.cwd()
LAB_DIR = NB_DIR.parent
CONVOCAUR = LAB_DIR.parent

sys.path.insert(0, str(CONVOCAUR / "src"))
sys.path.insert(0, str(LAB_DIR / "_comun"))

from cargar_datos import (
    cargar_todo,
    cargar_profesor,
    guardar_salida,
    salidas_dir,
)

datos = cargar_todo(persona=PERSONA, cargar_json_profesores=False)
SALIDAS = datos["salidas"]

print("Proyecto:", datos["proyecto"])
print("Salidas :", SALIDAS)
print("Docentes:", None if datos["urosario"]["docentes"] is None else len(datos["urosario"]["docentes"]))
print("JSON prof disponibles:", datos["urosario"]["n_json_disponibles"])
print("NLP convocatorias:", list(datos["minciencias"]["nlp_por_convocatoria"].keys()))'''

    atajos = '''# --- Minciencias ---
listado = datos["minciencias"]["listado"]
actividades = datos["minciencias"]["actividades"]
documentos = datos["minciencias"]["documentos"]

nlp = datos["minciencias"]["nlp_por_convocatoria"]
secciones = datos["minciencias"]["secciones_por_convocatoria"]
elegibilidad = datos["minciencias"]["elegibilidad_por_convocatoria"]

# --- Rosario ---
docentes = datos["urosario"]["docentes"]
sin_cvlac = datos["urosario"]["sin_cvlac"]

print(listado.head(3) if listado is not None else None)
if "convocatoria_48" in nlp:
    print("Objetivo 48:", (nlp["convocatoria_48"].get("objetivo") or "")[:240])
    print("Elegibilidad 48:", elegibilidad.get("convocatoria_48", {}).get("veredicto_final"))'''

    ej_a = '''# Ejemplo A: explorar NLP de una convocatoria
conv = "convocatoria_48"
if conv in nlp:
    nlp_48 = nlp[conv]
    print("Alianza obligatoria:", nlp_48.get("alianza_obligatoria"))
    print("N actores:", len(nlp_48.get("actores_elegibles") or []))
    print("N requisitos:", len(nlp_48.get("requisitos") or []))
    print("N criterios:", len(nlp_48.get("criterios_evaluacion") or []))
    print("Financiacion:", nlp_48.get("financiacion"))'''

    ej_b = '''# Ejemplo B: docentes con/sin CvLAC
if docentes is not None and sin_cvlac is not None:
    print("Docentes:", len(docentes))
    print("Sin CvLAC:", len(sin_cvlac))
    # perfil = cargar_profesor("ricardo-abello-galvis")
    # print(perfil.keys())
    # print((perfil.get("cvlac") or {}).get("datos_generales"))
    pass'''

    ej_c = '''# Ejemplo C: guardar un resultado en TU carpeta salidas/
# df_demo = listado[["numero", "titulo"]].head(5) if listado is not None else None
# if df_demo is not None:
#     ruta = guardar_salida(PERSONA, "demo_listado_head.csv", df_demo)
#     print("Guardado en", ruta)
pass'''

    limpio = '''## 3. Sugerencias de codigo limpio (ConvocaUR)

1. **No mutar raw/processed.** Si transformas, guarda en `SALIDAS`.
2. **Una responsabilidad por celda** (cargar / transformar / visualizar / exportar).
3. **Nombres claros:** `df_docentes`, `nlp_48`, no `df`, `x`, `tmp2`.
4. **Paths via loader** (`cargar_datos` / `convocaur.paths`), no strings absolutos.
5. **Funciones pequenas** si reutilizas logica (>15 lineas -> `def` o PR a `src/`).
6. **Seeds** si hay muestreo aleatorio.
7. **No subir secretos** ni pegar API keys en el notebook.
8. **Exports reproducibles** con `guardar_salida(PERSONA, "archivo.csv", df)`.
9. Si algo sirve al equipo, muevelo a `src/convocaur/` con PR.'''

    cells = [
        md(
            f"""# Laboratorio ConvocaUR — {nombre}

Workspace personal. **Lee** desde `data/`, **escribe** solo en `salidas/`.

- Catalogo: [../catalogo_datos.md](../catalogo_datos.md)
- Normas del lab: [../README.md](../README.md)
- Docs del sistema: [../../docs/](../../docs/)"""
        ),
        md("## 1. Setup\n\nCarga automatica de datasets. No edites archivos en `data/`."),
        code(setup),
        md("## 2. Atajos a variables frecuentes"),
        code(atajos),
        md(limpio),
        md("## 4. Tu espacio de trabajo\n\nEjemplos de partida (borralos si no los usas)."),
        code(ej_a),
        code(ej_b),
        code(ej_c),
        md("## 5. Zona libre\n\nCeldas vacias para tu analisis."),
    ]
    for _ in range(6):
        cells.append(code(""))

    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "pygments_lexer": "ipython3"},
        },
        "cells": cells,
    }


def main() -> None:
    for slug, nombre in PERSONAS:
        path = BASE / slug / "exploracion.ipynb"
        path.write_text(json.dumps(build(slug, nombre), ensure_ascii=False, indent=1), encoding="utf-8")
        print("wrote", path)


if __name__ == "__main__":
    main()
