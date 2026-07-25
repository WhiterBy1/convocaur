"""
Verifica elegibilidad de Universidad del Rosario sobre extracciones NLP de TdR.

Uso:
    python verificar_elegibilidad_urosario.py
    python verificar_elegibilidad_urosario.py --convocatorias 48,45,976
    python verificar_elegibilidad_urosario.py --sin-llm   # solo reglas
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from convocaur.nlp.elegibilidad_urosario import evaluar_elegibilidad_urosario
from convocaur.paths import PROC_ELEGIBILIDAD, PROC_NLP

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("verificar_elegibilidad_urosario")

NLP_DIR = PROC_NLP
OUT_DIR = PROC_ELEGIBILIDAD


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--convocatorias", default="48,45,976")
    parser.add_argument("--sin-llm", action="store_true")
    parser.add_argument("--nlp-dir", type=Path, default=NLP_DIR)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    convs = [c.strip() for c in args.convocatorias.split(",") if c.strip()]
    args.out_dir.mkdir(parents=True, exist_ok=True)

    filas = []
    for conv in convs:
        path = args.nlp_dir / f"convocatoria_{conv}_nlp.json"
        if not path.exists():
            log.error("No existe %s (corre antes nlp_tdr_piloto.py)", path)
            continue

        extraccion = json.loads(path.read_text(encoding="utf-8"))
        log.info("Evaluando conv %s …", conv)
        resultado = evaluar_elegibilidad_urosario(extraccion, usar_llm=not args.sin_llm)

        # Enriquecer el JSON NLP original
        extraccion["elegibilidad_urosario"] = resultado
        path.write_text(json.dumps(extraccion, ensure_ascii=False, indent=2), encoding="utf-8")

        out_path = args.out_dir / f"convocatoria_{conv}_elegibilidad.json"
        out_path.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")

        vf = resultado["veredicto_final"]
        filas.append({
            "convocatoria": conv,
            "puede_postularse": vf.get("puede_postularse"),
            "modo": vf.get("modo"),
            "rol_sugerido": vf.get("rol_sugerido"),
            "resumen": vf.get("resumen"),
            "fuente": vf.get("fuente"),
        })
        print(f"\n=== Conv {conv} ===")
        print(f"  puede_postularse: {vf.get('puede_postularse')}")
        print(f"  modo: {vf.get('modo')}")
        print(f"  rol: {vf.get('rol_sugerido')}")
        print(f"  {vf.get('resumen')}")

    resumen_path = args.out_dir / "resumen_elegibilidad.json"
    resumen_path.write_text(json.dumps(filas, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResumen: {resumen_path}")


if __name__ == "__main__":
    main()
