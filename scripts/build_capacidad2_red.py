"""Construye grafo Cap.2 entidad↔proveedor (red de mercado) para viz estilo Obsidian.

Lee lineas adjudicadas, agrega aristas y recorta un subgrafo navegable (~200 nodos).
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "analisis" / "secop" / "secop_ctei_lineas_limpio.csv"
CAP2 = ROOT / "data" / "processed" / "secop" / "capacidad2_mercado.json"
OUT = ROOT / "data" / "processed" / "secop" / "capacidad2_red.json"
DASH = ROOT / "data" / "processed" / "secop" / "resumen_dashboard.json"

MAX_ENTIDADES_SEMILLA = 35
TOP_PROV_POR_ENTIDAD = 7
MAX_PROVEEDORES_HUB = 25
TOP_ENT_POR_HUB = 4
MAX_NODOS = 220
MAX_EDGES = 380


def _slug(kind: str, raw: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", (raw or "").strip().upper())[:48]
    return f"{kind}:{s or 'X'}"


def _short(name: str, n: int = 42) -> str:
    name = (name or "").strip()
    if len(name) <= n:
        return name
    return name[: n - 1] + "…"


def _load_edges() -> pd.DataFrame:
    usecols = [
        "entidad",
        "nit_entidad",
        "nit_del_proveedor_adjudicado",
        "nombre_del_proveedor",
        "valor_total_adjudicacion",
        "id_del_proceso",
        "adjudicado_bool",
        "segmento_unspsc",
        "departamento_entidad",
    ]
    header = pd.read_csv(CSV, nrows=0).columns.tolist()
    cols = [c for c in usecols if c in header]
    chunks = []
    for chunk in pd.read_csv(CSV, usecols=cols, chunksize=100_000, low_memory=True):
        if "adjudicado_bool" in chunk.columns:
            ab = chunk["adjudicado_bool"]
            if ab.dtype == object:
                chunk = chunk[ab.astype(str).str.lower().isin(["1", "true", "si", "sí", "yes"])]
            else:
                chunk = chunk[ab.fillna(False).astype(bool)]
        chunk["valor"] = pd.to_numeric(chunk.get("valor_total_adjudicacion"), errors="coerce").fillna(0)
        chunk = chunk[chunk["valor"] > 0]
        chunk["entidad"] = chunk["entidad"].astype(str).str.strip()
        chunk = chunk[chunk["entidad"].ne("") & chunk["entidad"].ne("nan")]
        nit = chunk.get("nit_del_proveedor_adjudicado")
        nom = chunk.get("nombre_del_proveedor")
        chunk["proveedor_id"] = (
            nit.astype(str).str.strip().replace({"nan": "", "None": ""})
            if nit is not None
            else ""
        )
        nombres = nom.astype(str).str.strip() if nom is not None else ""
        chunk.loc[chunk["proveedor_id"].eq(""), "proveedor_id"] = nombres
        chunk["proveedor"] = nombres.where(nombres.ne("") & nombres.ne("nan"), chunk["proveedor_id"])
        chunk = chunk[chunk["proveedor_id"].ne("") & chunk["proveedor_id"].ne("nan")]
        chunks.append(chunk[["entidad", "proveedor_id", "proveedor", "valor", "id_del_proceso", "segmento_unspsc", "departamento_entidad"]])
    raw = pd.concat(chunks, ignore_index=True)
    g = (
        raw.groupby(["entidad", "proveedor_id"], as_index=False)
        .agg(
            proveedor=("proveedor", "first"),
            valor=("valor", "sum"),
            n_procesos=("id_del_proceso", "nunique"),
            segmento_modo=("segmento_unspsc", lambda s: str(s.mode().iloc[0]) if len(s.mode()) else ""),
            depto=("departamento_entidad", lambda s: str(s.mode().iloc[0]) if len(s.mode()) else ""),
        )
    )
    return g


def _build_subgraph(edges: pd.DataFrame) -> dict[str, Any]:
    # valor por entidad / proveedor
    val_ent = edges.groupby("entidad")["valor"].sum().sort_values(ascending=False)
    val_prov = edges.groupby("proveedor_id")["valor"].sum().sort_values(ascending=False)
    name_prov = edges.groupby("proveedor_id")["proveedor"].first().to_dict()

    # semillas: top entidades + nichos concentrados si existen
    semillas = set(val_ent.head(MAX_ENTIDADES_SEMILLA).index.tolist())
    if CAP2.exists():
        cap2 = json.loads(CAP2.read_text(encoding="utf-8"))
        for n in (cap2.get("nichos_concentrados") or [])[:15]:
            if n.get("entidad"):
                semillas.add(n["entidad"])

    keep_edges: list[dict[str, Any]] = []
    keep_prov: set[str] = set()
    keep_ent: set[str] = set(semillas)

    # por cada entidad semilla: top proveedores
    for ent in semillas:
        sub = edges[edges["entidad"] == ent].nlargest(TOP_PROV_POR_ENTIDAD, "valor")
        for _, r in sub.iterrows():
            keep_prov.add(r["proveedor_id"])
            keep_edges.append(r.to_dict())

    # hubs: proveedores globales que conectan varias entidades
    for pid in val_prov.head(MAX_PROVEEDORES_HUB).index.tolist():
        keep_prov.add(pid)
        sub = edges[edges["proveedor_id"] == pid].nlargest(TOP_ENT_POR_HUB, "valor")
        for _, r in sub.iterrows():
            keep_ent.add(r["entidad"])
            keep_edges.append(r.to_dict())

    # dedupe edges
    seen = set()
    uniq = []
    for r in keep_edges:
        key = (r["entidad"], r["proveedor_id"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    uniq.sort(key=lambda x: -float(x["valor"]))
    uniq = uniq[:MAX_EDGES]

    # restringir nodos a los que aparecen en edges finales
    keep_ent = {r["entidad"] for r in uniq}
    keep_prov = {r["proveedor_id"] for r in uniq}

    # grados en subgrafo
    deg_ent: dict[str, int] = defaultdict(int)
    deg_prov: dict[str, int] = defaultdict(int)
    for r in uniq:
        deg_ent[r["entidad"]] += 1
        deg_prov[r["proveedor_id"]] += 1

    # dependencia: % del valor del proveedor que viene de esa entidad (en grafo completo)
    val_prov_total = val_prov.to_dict()
    val_ent_total = val_ent.to_dict()

    nodes = []
    for ent in keep_ent:
        nodes.append({
            "id": _slug("e", ent),
            "kind": "entidad",
            "label": _short(ent, 40),
            "nombre": ent,
            "valor": float(val_ent_total.get(ent, 0)),
            "degree": int(deg_ent[ent]),
            "group": "comprador",
        })
    for pid in keep_prov:
        nodes.append({
            "id": _slug("p", pid),
            "kind": "proveedor",
            "label": _short(name_prov.get(pid, pid), 40),
            "nombre": name_prov.get(pid, pid),
            "nit": pid,
            "valor": float(val_prov_total.get(pid, 0)),
            "degree": int(deg_prov[pid]),
            "group": "vendedor",
        })

    # si hay demasiados nodos, quedarnos con los de mayor valor
    if len(nodes) > MAX_NODOS:
        nodes.sort(key=lambda n: -n["valor"])
        nodes = nodes[:MAX_NODOS]
        keep_ids = {n["id"] for n in nodes}
    else:
        keep_ids = {n["id"] for n in nodes}

    links = []
    for r in uniq:
        sid = _slug("e", r["entidad"])
        tid = _slug("p", r["proveedor_id"])
        if sid not in keep_ids or tid not in keep_ids:
            continue
        v = float(r["valor"])
        pv = float(val_prov_total.get(r["proveedor_id"], 0) or 1)
        ev = float(val_ent_total.get(r["entidad"], 0) or 1)
        links.append({
            "source": sid,
            "target": tid,
            "valor": v,
            "n_procesos": int(r["n_procesos"]),
            "peso": max(v / 1e9, 0.05),  # para force link
            "dependencia_proveedor_pct": round(100 * v / pv, 1),
            "participacion_entidad_pct": round(100 * v / ev, 1),
            "segmento": str(r.get("segmento_modo") or ""),
            "depto": str(r.get("depto") or ""),
        })

    # recortar nodos huérfanos
    linked = set()
    for L in links:
        linked.add(L["source"])
        linked.add(L["target"])
    nodes = [n for n in nodes if n["id"] in linked]

    # clusters / "palacios": entidades con más vecinos en el subgrafo
    palacios = sorted(
        [n for n in nodes if n["kind"] == "entidad"],
        key=lambda n: (-n["degree"], -n["valor"]),
    )[:12]
    for i, p in enumerate(palacios):
        p["palacio"] = i + 1

    return {
        "titulo": "Red del mercado CTeI",
        "subtitulo": (
            "Grafo bipartito entidad ↔ proveedor (adjudicaciones). "
            "Cada nodo es un actor; cada arista, dinero y procesos compartidos. "
            "Navega como un mapa de relaciones — estilo palacio mental."
        ),
        "lectura": (
            f"Subgrafo navegable: {len(nodes)} actores y {len(links)} vínculos "
            f"(semillas = top entidades + nichos concentrados). "
            "Un proveedor con muchas aristas es un hub; una entidad con pocos vínculos "
            "fuertes suele ser un nicho dependiente."
        ),
        "meta": {
            "n_nodos": len(nodes),
            "n_aristas": len(links),
            "n_entidades": sum(1 for n in nodes if n["kind"] == "entidad"),
            "n_proveedores": sum(1 for n in nodes if n["kind"] == "proveedor"),
            "fuente": CSV.name,
            "n_edges_universo": int(len(edges)),
        },
        "leyenda": [
            {"kind": "entidad", "color": "#c4a35a", "nombre": "Entidad (comprador)"},
            {"kind": "proveedor", "color": "#5ec4a8", "nombre": "Proveedor (vendedor)"},
        ],
        "como_leer": [
            "Arrastra nodos; scroll para zoom; clic para fijar y ver detalle.",
            "Al pasar el mouse se iluminan solo los vecinos (como en Obsidian).",
            "El tamaño del nodo ≈ valor adjudicado en el universo Cap.2.",
            "Aristas más gruesas = más valor entre esa entidad y ese proveedor.",
        ],
        "nodes": nodes,
        "links": links,
        "palacios": [
            {
                "id": p["id"],
                "nombre": p["nombre"],
                "degree": p["degree"],
                "valor": p["valor"],
            }
            for p in palacios
        ],
    }


def main() -> None:
    print("Agregando aristas entidad-proveedor...")
    edges = _load_edges()
    print(f"  universo edges={len(edges)} entidades={edges['entidad'].nunique()} prov={edges['proveedor_id'].nunique()}")
    graph = _build_subgraph(edges)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", OUT, "nodes", graph["meta"]["n_nodos"], "links", graph["meta"]["n_aristas"])

    # fusionar en Cap.2 + dashboard
    if CAP2.exists():
        cap2 = json.loads(CAP2.read_text(encoding="utf-8"))
    else:
        cap2 = {"titulo": "Mercado"}
    cap2["red_mercado"] = {
        "titulo": graph["titulo"],
        "subtitulo": graph["subtitulo"],
        "lectura": graph["lectura"],
        "meta": graph["meta"],
        "leyenda": graph["leyenda"],
        "como_leer": graph["como_leer"],
        "palacios": graph["palacios"],
        # grafo completo (nodos/links) va en archivo dedicado para no inflar Cap2 si se lee aparte;
        # igual lo embebemos para que el dashboard lo sirva en un solo GET
        "nodes": graph["nodes"],
        "links": graph["links"],
    }
    CAP2.write_text(json.dumps(cap2, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Updated", CAP2)

    if DASH.exists():
        dash = json.loads(DASH.read_text(encoding="utf-8"))
        if "capacidad_2" not in dash:
            dash["capacidad_2"] = {}
        dash["capacidad_2"]["red_mercado"] = cap2["red_mercado"]
        DASH.write_text(json.dumps(dash, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Updated", DASH)


if __name__ == "__main__":
    main()
