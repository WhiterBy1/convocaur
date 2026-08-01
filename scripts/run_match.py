#!/usr/bin/env python
"""
Match docente ↔ convocatoria.

Uso:
  python scripts/run_match.py --convocatorias 45,48,976 --top 10
  python scripts/run_match.py --sin-embeddings   # solo TF-IDF
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from convocaur.cargar_datos import guardar_salida  # noqa: E402
from convocaur.matching.corpus import (  # noqa: E402
    cargar_docentes_json,
    cargar_nlp_dir,
    texto_docente,
)
from convocaur.matching.embedders import OpenRouterEmbedder, TfidfEmbedder, _load_env  # noqa: E402
from convocaur.matching.ranker import rankear_convocatoria  # noqa: E402
from convocaur.paths import (  # noqa: E402
    JSON_PROFESORES,
    PROC_MATCHING,
    PROC_MATCHING_CACHE,
    PROC_NLP,
    PROJECT_ROOT,
    ensure_data_dirs,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("run_match")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--convocatorias", default="45,48,976")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--limite-docentes", type=int, default=None)
    parser.add_argument("--sin-embeddings", action="store_true")
    parser.add_argument("--w-emb", type=float, default=0.7)
    parser.add_argument("--w-tfidf", type=float, default=0.3)
    args = parser.parse_args()

    ensure_data_dirs()
    convs = [c.strip() for c in args.convocatorias.split(",") if c.strip()]
    conv_keys = [
        f"convocatoria_{c}" if not c.startswith("convocatoria_") else c for c in convs
    ]

    out_dir = PROC_MATCHING
    cache_dir = PROC_MATCHING_CACHE
    out_dir.mkdir(parents=True, exist_ok=True)

    _load_env(PROJECT_ROOT)

    nlp_all = cargar_nlp_dir(PROC_NLP)
    missing = [k for k in conv_keys if k not in nlp_all]
    if missing:
        raise SystemExit(f"Faltan NLP JSON: {missing}. Disponibles: {list(nlp_all)}")

    log.info("Cargando docentes desde %s", JSON_PROFESORES)
    docentes = cargar_docentes_json(JSON_PROFESORES, limite=args.limite_docentes)
    doc_texts = [texto_docente(d) for d in docentes]
    log.info("Docentes con texto usable: %s", len(docentes))

    tfidf = TfidfEmbedder()
    tfidf.fit_transform(doc_texts)

    or_emb = None
    doc_emb = None
    if not args.sin_embeddings:
        try:
            or_emb = OpenRouterEmbedder(cache_dir=cache_dir)
            doc_emb = or_emb.embed_texts(doc_texts, show_progress=True)
        except Exception as exc:
            log.error("Embeddings OpenRouter no disponibles (%s). Sigo solo con TF-IDF.", exc)
            or_emb = None
            doc_emb = None

    resumen = []
    for key in conv_keys:
        log.info("Rankeando %s …", key)
        df = rankear_convocatoria(
            nlp_all[key],
            docentes,
            or_embedder=or_emb,
            tfidf=tfidf,
            doc_texts=doc_texts,
            doc_emb=doc_emb,
            w_emb=args.w_emb,
            w_tfidf=args.w_tfidf,
            top_k=args.top,
        )
        csv_name = f"ranking_{key}.csv"
        path = out_dir / csv_name
        df.to_csv(path, index=False, encoding="utf-8")
        guardar_salida(csv_name, df)

        top = df.head(3)[
            ["rank", "nombre", "facultad", "categoria", "score_final", "score_emb", "score_tfidf"]
        ]
        log.info("Top 3 %s:\n%s", key, top.to_string(index=False))
        resumen.append({
            "convocatoria": key,
            "n_candidatos_pool": len(docentes),
            "top1_id": df.iloc[0]["id"] if len(df) else None,
            "top1_nombre": df.iloc[0]["nombre"] if len(df) else None,
            "top1_score": float(df.iloc[0]["score_final"]) if len(df) else None,
            "uso_embeddings": or_emb is not None,
            "archivo": str(path),
        })

    resumen_path = out_dir / "resumen_match.json"
    resumen_path.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    print(f"\nSalidas en: {out_dir}")


if __name__ == "__main__":
    main()
