"""CLI local: ingerir una convocatoria (TdR → NLP → eleg → match → borrar PDF).

Ejemplos:
  set PYTHONPATH=src;backend
  py -3.12 scripts/run_ingest_nueva.py --url "https://minciencias.gov.co/convocatorias/...."
  py -3.12 scripts/run_ingest_nueva.py --url "..." --numero 1044 --sin-borrar-pdf
  py -3.12 scripts/run_ingest_nueva.py --sync   # sync página 1 + ingerir hasta 1 nueva
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingesta convocatoria Minciencias (pipeline completo)")
    parser.add_argument("--url", help="URL de detalle de la convocatoria")
    parser.add_argument("--numero", default=None, help="Número (opcional si viene en la página)")
    parser.add_argument("--titulo", default=None)
    parser.add_argument("--sync", action="store_true", help="Sync listado + ingerir nuevas")
    parser.add_argument("--paginas", type=int, default=1)
    parser.add_argument("--max-nuevas", type=int, default=1)
    parser.add_argument("--sin-matching", action="store_true")
    parser.add_argument("--sin-borrar-pdf", action="store_true", help="Dejar el TdR en disco (debug)")
    parser.add_argument("--sin-embeddings", action="store_true")
    parser.add_argument("--top", type=int, default=15)
    args = parser.parse_args()

    def progress(p: dict) -> None:
        print(f"  [{p.get('fase')}] {p.get('mensaje')} ({p.get('hecho')}/{p.get('total')})")

    if args.sync:
        from app.services.minciencias_sync import sync_minciencias

        report = sync_minciencias(
            paginas=args.paginas,
            procesar_nuevas=True,
            matching_si_elegible=not args.sin_matching,
            borrar_pdf=not args.sin_borrar_pdf,
            sin_embeddings=args.sin_embeddings,
            max_nuevas=args.max_nuevas,
            top_k=args.top,
            on_progress=progress,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    if not args.url:
        parser.error("Pasa --url o usa --sync")

    from app.services.ingest_convocatoria import ingest_convocatoria

    result = ingest_convocatoria(
        numero=args.numero,
        url_detalle=args.url,
        titulo=args.titulo,
        matching_si_elegible=not args.sin_matching,
        borrar_pdf=not args.sin_borrar_pdf,
        sin_embeddings=args.sin_embeddings,
        top_k=args.top,
        on_progress=progress,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
