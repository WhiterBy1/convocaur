#!/usr/bin/env python
"""
Pruebas básicas del matching (sin pytest obligatorio).

Valida:
1) textos no vacíos
2) TF-IDF rankea algo
3) scores ordenados
4) comparación emb vs tfidf si hay API
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from convocaur.matching.corpus import (  # noqa: E402
    cargar_docentes_json,
    cargar_nlp_dir,
    texto_convocatoria,
    texto_docente,
)
from convocaur.matching.embedders import OpenRouterEmbedder, TfidfEmbedder, _load_env  # noqa: E402
from convocaur.matching.ranker import rankear_convocatoria  # noqa: E402
from convocaur.paths import JSON_PROFESORES, PROC_MATCHING, PROC_MATCHING_CACHE, PROC_NLP, PROJECT_ROOT  # noqa: E402


def assert_true(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)
    print("OK:", msg)


def main() -> None:
    _load_env(PROJECT_ROOT)
    nlp_all = cargar_nlp_dir(PROC_NLP)
    assert_true("convocatoria_48" in nlp_all, "existe NLP convocatoria_48")

    docentes = cargar_docentes_json(JSON_PROFESORES, limite=80)
    assert_true(len(docentes) >= 20, f"pool docentes suficiente ({len(docentes)})")

    texts = [texto_docente(d) for d in docentes]
    assert_true(all(len(t) > 40 for t in texts), "textos docente no vacíos")

    q = texto_convocatoria(nlp_all["convocatoria_48"])
    assert_true(len(q) > 80, "texto convocatoria 48 no vacío")

    tfidf = TfidfEmbedder()
    tfidf.fit_transform(texts)
    df_tf = rankear_convocatoria(
        nlp_all["convocatoria_48"],
        docentes,
        or_embedder=None,
        tfidf=tfidf,
        doc_texts=texts,
        doc_emb=None,
        top_k=5,
    )
    assert_true(len(df_tf) == 5, "TF-IDF devuelve top 5")
    assert_true(df_tf["score_final"].is_monotonic_decreasing, "scores TF-IDF ordenados desc")

    out = PROC_MATCHING
    out.mkdir(parents=True, exist_ok=True)
    df_tf.to_csv(out / "prueba_tfidf_48_top5.csv", index=False, encoding="utf-8")

    try:
        emb = OpenRouterEmbedder(cache_dir=PROC_MATCHING_CACHE)
        doc_emb = emb.embed_texts(texts, show_progress=True)
        df_h = rankear_convocatoria(
            nlp_all["convocatoria_48"],
            docentes,
            or_embedder=emb,
            tfidf=tfidf,
            doc_texts=texts,
            doc_emb=doc_emb,
            top_k=5,
        )
        assert_true(len(df_h) == 5, "híbrido devuelve top 5")
        df_h.to_csv(out / "prueba_hibrido_48_top5.csv", index=False, encoding="utf-8")

        set_tf = set(df_tf.head(3)["id"])
        set_h = set(df_h.head(3)["id"])
        overlap = len(set_tf & set_h)
        print(f"Overlap top3 TF-IDF vs híbrido: {overlap}/3")
        (out / "prueba_overlap.json").write_text(
            json.dumps({
                "tfidf_top3": df_tf.head(3)[["id", "nombre", "score_final"]].to_dict(orient="records"),
                "hibrido_top3": df_h.head(3)[["id", "nombre", "score_final", "score_emb"]].to_dict(
                    orient="records"
                ),
                "overlap_ids": list(set_tf & set_h),
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("Embeddings: OK")
    except Exception as exc:
        print("Embeddings: SKIP / FAIL ->", exc)
        print("(Las pruebas TF-IDF igual pasaron)")

    print("\nTodas las aserciones locales pasaron.")


if __name__ == "__main__":
    main()
