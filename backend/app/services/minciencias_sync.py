"""Sync de listado Minciencias vs estado local."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

import pandas as pd

from convocaur.paths import LISTADO_CSV, PROC_MINCIENCIAS, PROC_NLP, PROJECT_ROOT


def _local_numeros() -> set[str]:
    nums: set[str] = set()
    if LISTADO_CSV.exists():
        df = pd.read_csv(LISTADO_CSV, dtype=str)
        if "numero" in df.columns:
            nums |= {str(x).strip().replace(".0", "") for x in df["numero"].dropna()}
    proc = PROC_MINCIENCIAS / "minciencias_convocatorias_processed.csv"
    if proc.exists():
        df = pd.read_csv(proc, dtype=str)
        if "numero" in df.columns:
            nums |= {str(x).strip().replace(".0", "") for x in df["numero"].dropna()}
    if PROC_NLP.exists():
        for f in PROC_NLP.glob("convocatoria_*_nlp.json"):
            nums.add(f.stem.replace("convocatoria_", "").replace("_nlp", ""))
    return {n for n in nums if n and n.lower() != "nan"}


def sync_minciencias(
    paginas: int = 1,
    *,
    procesar_nuevas: bool = True,
    matching_si_elegible: bool = True,
    borrar_pdf: bool = True,
    sin_embeddings: bool = False,
    max_nuevas: int = 3,
    top_k: int = 15,
    on_progress: Callable[[dict], None] | None = None,
) -> dict[str, Any]:
    """Scrapea el listado público, reporta nuevas y opcionalmente las ingesta (TdR→NLP→match→borrar PDF)."""
    from convocaur.minciencias.scrape import extraer_listado

    def progress(payload: dict) -> None:
        if on_progress:
            on_progress(payload)

    progress({"fase": "scrape", "mensaje": f"Scrapeando hasta {paginas} páginas…", "hecho": 0, "total": paginas})
    remoto = extraer_listado(paginas)
    if remoto.empty:
        raise RuntimeError("El listado remoto de Minciencias vino vacío.")

    remoto["numero"] = remoto["numero"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    # Concursos sin número: usar id estable desde la URL (/node/9339 → node_9339)
    if "url_detalle" in remoto.columns:
        from convocaur.minciencias.scrape import id_desde_url

        mask_vacio = remoto["numero"].isna() | (remoto["numero"] == "") | (remoto["numero"].str.lower() == "nan")
        remoto.loc[mask_vacio, "numero"] = remoto.loc[mask_vacio, "url_detalle"].map(
            lambda u: id_desde_url(u) or ""
        )
    remoto = remoto[remoto["numero"].astype(str).str.len() > 0].copy()
    local = _local_numeros()
    remotos = set(remoto["numero"].tolist())
    nuevas = sorted(remotos - local, key=lambda x: int(x) if x.isdigit() else 0)
    ya = sorted(remotos & local, key=lambda x: int(x) if x.isdigit() else 0)

    # Guardar snapshot del sync
    out_dir = PROC_MINCIENCIAS
    out_dir.mkdir(parents=True, exist_ok=True)
    snap_csv = out_dir / "listado_minciencias_sync.csv"
    remoto.to_csv(snap_csv, index=False, encoding="utf-8")

    # Si existe listado raw, fusionar nuevas filas
    merged_n = len(remoto)
    if LISTADO_CSV.exists():
        try:
            old = pd.read_csv(LISTADO_CSV, dtype=str)
            old["numero"] = old["numero"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
            combo = pd.concat([old, remoto], ignore_index=True)
            combo = combo.drop_duplicates(subset=["numero"], keep="last")
            LISTADO_CSV.parent.mkdir(parents=True, exist_ok=True)
            combo.to_csv(LISTADO_CSV, index=False, encoding="utf-8")
            merged_n = len(combo)
        except Exception:
            # Si no había listado, crear uno con el remoto
            try:
                LISTADO_CSV.parent.mkdir(parents=True, exist_ok=True)
                remoto.to_csv(LISTADO_CSV, index=False, encoding="utf-8")
                merged_n = len(remoto)
            except Exception:
                pass
    else:
        LISTADO_CSV.parent.mkdir(parents=True, exist_ok=True)
        remoto.to_csv(LISTADO_CSV, index=False, encoding="utf-8")
        merged_n = len(remoto)

    nuevas_detalle = (
        remoto[remoto["numero"].isin(nuevas)][
            ["numero", "titulo", "url_detalle", "fecha_apertura_texto", "total_recursos_texto"]
        ]
        .fillna("")
        .to_dict(orient="records")
        if nuevas
        else []
    )

    report: dict[str, Any] = {
        "ok": True,
        "fecha": datetime.now(timezone.utc).isoformat(),
        "n_remotos": int(len(remoto)),
        "n_locales_previos": len(local),
        "n_nuevas": len(nuevas),
        "n_ya_conocidas": len(ya),
        "nuevas": nuevas,
        "nuevas_detalle": nuevas_detalle,
        "snapshot_csv": str(snap_csv.relative_to(PROJECT_ROOT)),
        "listado_merged_filas": merged_n,
        "mensaje": (
            f"Encontradas {len(nuevas)} convocatorias nuevas en Minciencias."
            if nuevas
            else "No hay convocatorias nuevas respecto al inventario local."
        ),
    }

    if procesar_nuevas and nuevas_detalle:
        progress(
            {
                "fase": "ingest",
                "mensaje": f"Procesando hasta {min(len(nuevas_detalle), max_nuevas)} nuevas…",
                "hecho": 0,
                "total": min(len(nuevas_detalle), max_nuevas),
            }
        )
        from app.services.ingest_convocatoria import ingest_nuevas

        ingest = ingest_nuevas(
            nuevas_detalle,
            matching_si_elegible=matching_si_elegible,
            borrar_pdf=borrar_pdf,
            sin_embeddings=sin_embeddings,
            top_k=top_k,
            max_nuevas=max_nuevas,
            on_progress=progress,
        )
        report["ingest"] = ingest
        report["mensaje"] = (
            f"{report['mensaje']} {ingest.get('mensaje', '')}".strip()
        )
    elif procesar_nuevas:
        report["ingest"] = {
            "ok": True,
            "n_solicitadas": 0,
            "n_ok": 0,
            "n_error": 0,
            "resultados": [],
            "mensaje": "Sin nuevas que ingerir.",
        }

    report_path = out_dir / "ultimo_sync_minciencias.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    progress({"fase": "listo", "mensaje": report["mensaje"], "hecho": len(remoto), "total": len(remoto)})
    return report
