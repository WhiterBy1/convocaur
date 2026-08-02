#!/usr/bin/env python
"""
Match docente ↔ convocatoria.

Uso:
  python scripts/run_match.py --todas
  python scripts/run_match.py --solo-faltantes
  python scripts/run_match.py --convocatorias 45,48,976 --top 15
  python scripts/run_match.py --sin-embeddings
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from convocaur.matching.runner import run_matching  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--convocatorias", default=None, help="Lista 45,48,976")
    parser.add_argument("--todas", action="store_true", help="Todas las NLP disponibles")
    parser.add_argument("--solo-faltantes", action="store_true", help="Solo sin ranking CSV")
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument("--limite-docentes", type=int, default=None)
    parser.add_argument("--sin-embeddings", action="store_true")
    parser.add_argument("--w-emb", type=float, default=0.7)
    parser.add_argument("--w-tfidf", type=float, default=0.3)
    args = parser.parse_args()

    if args.todas or (args.solo_faltantes and not args.convocatorias):
        convs = None
    elif args.convocatorias:
        convs = [c.strip() for c in args.convocatorias.split(",") if c.strip()]
    else:
        convs = ["45", "48", "976"]

    result = run_matching(
        convs,
        top_k=args.top,
        limite_docentes=args.limite_docentes,
        sin_embeddings=args.sin_embeddings,
        solo_faltantes=args.solo_faltantes,
        w_emb=args.w_emb,
        w_tfidf=args.w_tfidf,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
