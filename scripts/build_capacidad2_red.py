"""Construye grafo Cap.2 entidad↔proveedor + análisis de red para U. Rosario.

Lee líneas adjudicadas CTeI, agrega aristas y produce:
  - red_mercado: subgrafo amplio navegable (no todo SECOP: ~20k nodos congelan el browser)
  - red_ego_rosario: 1-hop completo de Rosario + competidores en sus compradores
  - analisis_rosario: compradores, share of wallet, competidores, peers IES
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "analisis" / "secop" / "secop_ctei_lineas_limpio.csv"
CAP2 = ROOT / "data" / "processed" / "secop" / "capacidad2_mercado.json"
OUT = ROOT / "data" / "processed" / "secop" / "capacidad2_red.json"
OUT_ROS = ROOT / "data" / "processed" / "secop" / "capacidad2_rosario.json"
DASH = ROOT / "data" / "processed" / "secop" / "resumen_dashboard.json"

# Mercado ampliado (sigue siendo muestra; el universo completo va en meta + tablas Rosario)
MAX_ENTIDADES_SEMILLA = 55
TOP_PROV_POR_ENTIDAD = 10
MAX_PROVEEDORES_HUB = 40
TOP_ENT_POR_HUB = 5
MAX_NODOS = 480
MAX_EDGES = 720

# Ego Rosario: todos los compradores + top competidores en esos compradores
EGO_TOP_COMPETIDORES = 18
EGO_TOP_EDGES_COMP_POR_ENT = 3
TOP_COMPETIDORES_TABLA = 25
TOP_PEERS_IES = 20

# Siempre incluir (aunque no entren al top global): Universidad del Rosario y aliases
ANCLAS_PROVEEDOR = re.compile(
    r"COLEGIO\s+MAYOR\s+DE\s+NUESTRA\s+SE[NÑ]ORA\s+DEL\s+ROSARIO|"
    r"UNIVERSIDAD\s+DEL\s+ROSARIO|"
    r"COLEGIO\s+MAYOR\s+NUESTRA\s+SE[NÑ]ORA\s+DEL\s+ROSARIO",
    re.IGNORECASE,
)
ANCLAS_ENTIDAD = re.compile(
    r"UNIVERSIDAD\s+DEL\s+ROSARIO|"
    r"COLEGIO\s+MAYOR\s+DE\s+NUESTRA\s+SE[NÑ]ORA\s+DEL\s+ROSARIO|"
    r"COLEGIO\s+MAYOR\s+NUESTRA\s+SE[NÑ]ORA\s+DEL\s+ROSARIO",
    re.IGNORECASE,
)

# Otras IES / centros de formación (peers, no Rosario).
# Heurística por razón social SECOP: muchas IES llegan como sigla (UNISALLE, UPTC…).
_PEER_IES_WORDS = re.compile(
    r"\bUNIVERSIDAD\b|\bCOLEGIO\s+MAYOR\b|\bPOLIT[EÉ]CNICO\b|"
    r"\bESCUELA\s+SUPERIOR\b|\bINSTITUTO\s+TECNOL|\bFUNDACI[OÓ]N\s+UNIVERSIT|"
    r"\bCORPORACI[OÓ]N\s+UNIVERSIT|\bINSTITUCI[OÓ]N\s+UNIVERSIT|"
    r"\bCENTRO\s+DE\s+FORMACI",
    re.IGNORECASE,
)
# Siglas frecuentes en SECOP cuando el nombre no trae "UNIVERSIDAD"
_PEER_IES_ACRONYMS = {
    "UNISALLE",
    "UNIMINUTO",
    "UPTC",
    "UIS",
    "UDEA",
    "EAFIT",
    "ICESI",
    "JAVERIANA",
    "EXTERNADO",
    "CES",
    "ECCI",
    "UPB",
    "UTB",
    "USB",
    "UAN",
    "UDCA",
    "UCATOLICA",
    "CUN",
    "UNAB",
    "UNINORTE",
    "UNIVALLE",
    "UNAL",
    "UNIANDES",
    "UNBOSQUE",
    "UDES",
    "UMNG",
    "ESAP",
    "ITM",
    "PASCUAL BRAVO",
    "POLI",
}


def es_nombre_ies(nombre: str) -> bool:
    """True si el proveedor parece IES/centro de formación por razón social."""
    raw = (nombre or "").strip()
    if not raw:
        return False
    if _PEER_IES_WORDS.search(raw):
        return True
    key = re.sub(r"[^A-Z0-9ÁÉÍÓÚÑÜ\s]", "", raw.upper())
    key = re.sub(r"\s+", " ", key).strip()
    if key in _PEER_IES_ACRONYMS:
        return True
    for tok in key.split():
        if tok in _PEER_IES_ACRONYMS:
            return True
    compact = re.sub(r"\s+", "", key)
    if compact.startswith("UNI") and len(compact) >= 6 and compact.isalpha():
        return True
    return False


# Alias legacy por si queda alguna referencia
PEER_IES = _PEER_IES_WORDS


def _norm_nit(raw: str) -> str:
    s = (raw or "").strip()
    if not s or s.lower() in {"nan", "none"}:
        return ""
    # unificar "860007759.0" → "860007759"
    if re.fullmatch(r"\d+\.0+", s):
        return str(int(float(s)))
    if re.fullmatch(r"\d+", s):
        return s.lstrip("0") or "0"
    return s


def _slug(kind: str, raw: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", (raw or "").strip().upper())[:48]
    return f"{kind}:{s or 'X'}"


def _short(name: str, n: int = 42) -> str:
    name = (name or "").strip()
    if len(name) <= n:
        return name
    return name[: n - 1] + "…"


def _truthy_adjudicado(raw: str) -> bool:
    s = (raw or "").strip().lower()
    if not s or s in {"nan", "none"}:
        return True  # si no hay flag, no filtrar
    if s in {"0", "false", "no", "n"}:
        return False
    return s in {"1", "true", "si", "sí", "yes"}


def _mode_str(counter: Counter[str]) -> str:
    if not counter:
        return ""
    return counter.most_common(1)[0][0]


def _load_edges() -> list[dict[str, Any]]:
    """Agrega aristas entidad↔proveedor sin pandas (CSV ~400MB)."""
    agg: dict[tuple[str, str], dict[str, Any]] = {}
    with CSV.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if "adjudicado_bool" in row and not _truthy_adjudicado(row.get("adjudicado_bool") or ""):
                continue
            try:
                valor = float(str(row.get("valor_total_adjudicacion") or "0").replace(",", ""))
            except ValueError:
                valor = 0.0
            if valor <= 0:
                continue
            ent = (row.get("entidad") or "").strip()
            if not ent or ent.lower() == "nan":
                continue
            nit = _norm_nit(str(row.get("nit_del_proveedor_adjudicado") or ""))
            nom = (row.get("nombre_del_proveedor") or "").strip()
            if nom.lower() in {"", "nan", "none"}:
                nom = ""
            pid = nit or nom
            if not pid or pid.lower() == "nan":
                continue
            proveedor = nom or pid
            key = (ent, pid)
            slot = agg.get(key)
            if slot is None:
                slot = {
                    "entidad": ent,
                    "proveedor_id": pid,
                    "proveedor": proveedor,
                    "valor": 0.0,
                    "procesos": set(),
                    "segmentos": Counter(),
                    "deptos": Counter(),
                }
                agg[key] = slot
            slot["valor"] += valor
            proc = (row.get("id_del_proceso") or row.get("referencia_del_proceso") or "").strip()
            if proc:
                slot["procesos"].add(proc)
            seg = (row.get("segmento_unspsc") or "").strip()
            if seg and seg.lower() != "nan":
                slot["segmentos"][seg] += 1
            dep = (row.get("departamento_entidad") or "").strip()
            if dep and dep.lower() != "nan":
                slot["deptos"][dep] += 1
            # preferir nombre no vacío
            if nom and (not slot["proveedor"] or slot["proveedor"] == pid):
                slot["proveedor"] = nom

    out: list[dict[str, Any]] = []
    for slot in agg.values():
        out.append({
            "entidad": slot["entidad"],
            "proveedor_id": slot["proveedor_id"],
            "proveedor": slot["proveedor"],
            "valor": float(slot["valor"]),
            "n_procesos": len(slot["procesos"]),
            "segmento_modo": _mode_str(slot["segmentos"]),
            "depto": _mode_str(slot["deptos"]),
        })
    return out


def _build_subgraph(edges: list[dict[str, Any]]) -> dict[str, Any]:
    val_ent: dict[str, float] = defaultdict(float)
    val_prov: dict[str, float] = defaultdict(float)
    name_prov: dict[str, str] = {}
    by_ent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_prov: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for r in edges:
        ent = r["entidad"]
        pid = r["proveedor_id"]
        val_ent[ent] += r["valor"]
        val_prov[pid] += r["valor"]
        name_prov.setdefault(pid, r["proveedor"])
        by_ent[ent].append(r)
        by_prov[pid].append(r)

    val_ent_sorted = sorted(val_ent.items(), key=lambda kv: -kv[1])
    val_prov_sorted = sorted(val_prov.items(), key=lambda kv: -kv[1])

    ancla_prov_ids = {
        pid
        for pid, nom in name_prov.items()
        if ANCLAS_PROVEEDOR.search(str(nom or "")) or ANCLAS_PROVEEDOR.search(str(pid or ""))
    }
    ancla_ent_names = {e for e in val_ent if ANCLAS_ENTIDAD.search(str(e))}

    semillas = {e for e, _ in val_ent_sorted[:MAX_ENTIDADES_SEMILLA]}
    semillas |= ancla_ent_names
    if CAP2.exists():
        cap2 = json.loads(CAP2.read_text(encoding="utf-8"))
        for n in (cap2.get("nichos_concentrados") or [])[:15]:
            if n.get("entidad"):
                semillas.add(n["entidad"])

    keep_edges: list[dict[str, Any]] = []

    for ent in semillas:
        sub = sorted(by_ent.get(ent, []), key=lambda x: -x["valor"])[:TOP_PROV_POR_ENTIDAD]
        keep_edges.extend(sub)

    for pid, _ in val_prov_sorted[:MAX_PROVEEDORES_HUB]:
        sub = sorted(by_prov.get(pid, []), key=lambda x: -x["valor"])[:TOP_ENT_POR_HUB]
        keep_edges.extend(sub)

    if ancla_prov_ids:
        for pid in ancla_prov_ids:
            keep_edges.extend(by_prov.get(pid, []))
    if ancla_ent_names:
        for ent in ancla_ent_names:
            keep_edges.extend(by_ent.get(ent, []))

    seen: set[tuple[str, str]] = set()
    uniq: list[dict[str, Any]] = []
    for r in keep_edges:
        key = (r["entidad"], r["proveedor_id"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)

    def _edge_prio(r: dict) -> tuple:
        is_ancla = r["proveedor_id"] in ancla_prov_ids or r["entidad"] in ancla_ent_names
        return (0 if is_ancla else 1, -float(r["valor"]))

    uniq.sort(key=_edge_prio)
    uniq = uniq[:MAX_EDGES]

    keep_ent = {r["entidad"] for r in uniq}
    keep_prov = {r["proveedor_id"] for r in uniq}

    deg_ent: dict[str, int] = defaultdict(int)
    deg_prov: dict[str, int] = defaultdict(int)
    for r in uniq:
        deg_ent[r["entidad"]] += 1
        deg_prov[r["proveedor_id"]] += 1

    nodes = []
    for ent in keep_ent:
        nodes.append({
            "id": _slug("e", ent),
            "kind": "entidad",
            "label": _short(ent, 40),
            "nombre": ent,
            "valor": float(val_ent.get(ent, 0)),
            "degree": int(deg_ent[ent]),
            "group": "comprador",
            "ancla": ent in ancla_ent_names,
            "ancla_id": "urosario" if ent in ancla_ent_names else None,
        })
    for pid in keep_prov:
        is_ancla = pid in ancla_prov_ids
        nodes.append({
            "id": _slug("p", pid),
            "kind": "proveedor",
            "label": _short(name_prov.get(pid, pid), 40),
            "nombre": name_prov.get(pid, pid),
            "nit": pid,
            "valor": float(val_prov.get(pid, 0)),
            "degree": int(deg_prov[pid]),
            "group": "vendedor",
            "ancla": is_ancla,
            "ancla_id": "urosario" if is_ancla else None,
        })

    if len(nodes) > MAX_NODOS:
        anclas = [n for n in nodes if n.get("ancla")]
        ancla_ids = {n["id"] for n in anclas}
        vecinos_ancla: set[str] = set()
        for r in uniq:
            sid = _slug("e", r["entidad"])
            tid = _slug("p", r["proveedor_id"])
            if tid in ancla_ids:
                vecinos_ancla.add(sid)
            if sid in ancla_ids:
                vecinos_ancla.add(tid)
        protegidos = ancla_ids | vecinos_ancla
        keep_forced = [n for n in nodes if n["id"] in protegidos]
        otros = [n for n in nodes if n["id"] not in protegidos]
        otros.sort(key=lambda n: -n["valor"])
        nodes = keep_forced + otros[: max(0, MAX_NODOS - len(keep_forced))]
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
        pv = float(val_prov.get(r["proveedor_id"], 0) or 1)
        ev = float(val_ent.get(r["entidad"], 0) or 1)
        links.append({
            "source": sid,
            "target": tid,
            "valor": v,
            "n_procesos": int(r["n_procesos"]),
            "peso": max(v / 1e9, 0.05),
            "dependencia_proveedor_pct": round(100 * v / pv, 1),
            "participacion_entidad_pct": round(100 * v / ev, 1),
            "segmento": str(r.get("segmento_modo") or ""),
            "depto": str(r.get("depto") or ""),
        })

    linked = set()
    for L in links:
        linked.add(L["source"])
        linked.add(L["target"])
    nodes = [n for n in nodes if n["id"] in linked]

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
            f"Muestra navegable del mercado: {len(nodes)} actores / {len(links)} vínculos "
            f"de un universo de {len(edges)} aristas entidad↔proveedor. "
            "No se dibuja todo SECOP (congelaría el navegador); usa la vista Ego Rosario "
            "para el mapa completo de compradores y competidores de la universidad."
        ),
        "meta": {
            "n_nodos": len(nodes),
            "n_aristas": len(links),
            "n_entidades": sum(1 for n in nodes if n["kind"] == "entidad"),
            "n_proveedores": sum(1 for n in nodes if n["kind"] == "proveedor"),
            "n_anclas_urosario": sum(1 for n in nodes if n.get("ancla_id") == "urosario"),
            "fuente": CSV.name,
            "n_edges_universo": int(len(edges)),
            "modo": "mercado_muestra",
        },
        "leyenda": [
            {"kind": "entidad", "color": "#3e4b8e", "nombre": "Entidad (comprador)"},
            {"kind": "proveedor", "color": "#a6bcc9", "nombre": "Proveedor (vendedor)"},
            {"kind": "ancla", "color": "#3d1534", "nombre": "U. Rosario (ancla)"},
        ],
        "como_leer": [
            "Esto es una muestra de los mayores compradores/hubs + Rosario siempre anclada.",
            "Para ver TODOS los vínculos de Rosario, cambia a la vista Ego Rosario.",
            "Arrastra nodos; scroll para zoom; clic para fijar detalle.",
            "Tamaño del nodo ≈ valor adjudicado; arista gruesa = más valor.",
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


def _index_edges(edges: list[dict[str, Any]]) -> tuple[
    dict[str, float],
    dict[str, float],
    dict[str, str],
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
    set[str],
    set[str],
]:
    val_ent: dict[str, float] = defaultdict(float)
    val_prov: dict[str, float] = defaultdict(float)
    name_prov: dict[str, str] = {}
    by_ent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_prov: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in edges:
        val_ent[r["entidad"]] += r["valor"]
        val_prov[r["proveedor_id"]] += r["valor"]
        name_prov.setdefault(r["proveedor_id"], r["proveedor"])
        by_ent[r["entidad"]].append(r)
        by_prov[r["proveedor_id"]].append(r)
    ancla_prov = {
        pid
        for pid, nom in name_prov.items()
        if ANCLAS_PROVEEDOR.search(str(nom or "")) or ANCLAS_PROVEEDOR.search(str(pid or ""))
    }
    ancla_ent = {e for e in val_ent if ANCLAS_ENTIDAD.search(str(e))}
    return val_ent, val_prov, name_prov, by_ent, by_prov, ancla_prov, ancla_ent


def _pack_graph(
    *,
    titulo: str,
    subtitulo: str,
    lectura: str,
    nodes: list[dict[str, Any]],
    links: list[dict[str, Any]],
    n_edges_universo: int,
    como_leer: list[str] | None = None,
) -> dict[str, Any]:
    linked = {L["source"] for L in links} | {L["target"] for L in links}
    nodes = [n for n in nodes if n["id"] in linked]
    for n in nodes:
        n["degree"] = sum(1 for L in links if L["source"] == n["id"] or L["target"] == n["id"])
    palacios = sorted(
        [n for n in nodes if n["kind"] == "entidad"],
        key=lambda n: (-n["degree"], -n["valor"]),
    )[:12]
    for i, p in enumerate(palacios):
        p["palacio"] = i + 1
    return {
        "titulo": titulo,
        "subtitulo": subtitulo,
        "lectura": lectura,
        "meta": {
            "n_nodos": len(nodes),
            "n_aristas": len(links),
            "n_entidades": sum(1 for n in nodes if n["kind"] == "entidad"),
            "n_proveedores": sum(1 for n in nodes if n["kind"] == "proveedor"),
            "n_anclas_urosario": sum(1 for n in nodes if n.get("ancla_id") == "urosario"),
            "fuente": CSV.name,
            "n_edges_universo": n_edges_universo,
        },
        "leyenda": [
            {"kind": "entidad", "color": "#3e4b8e", "nombre": "Entidad (comprador)"},
            {"kind": "proveedor", "color": "#a6bcc9", "nombre": "Proveedor"},
            {"kind": "competidor", "color": "#8b3a4a", "nombre": "Competidor frecuente"},
            {"kind": "ancla", "color": "#3d1534", "nombre": "U. Rosario"},
        ],
        "como_leer": como_leer or [
            "Arrastra nodos; scroll para zoom; clic para fijar detalle.",
            "Tamaño ≈ valor adjudicado en el universo CTeI Cap.2.",
            "Arista más gruesa = más valor entre entidad y proveedor.",
        ],
        "nodes": nodes,
        "links": links,
        "palacios": [
            {"id": p["id"], "nombre": p["nombre"], "degree": p["degree"], "valor": p["valor"]}
            for p in palacios
        ],
    }


def _edge_link(r: dict[str, Any], val_ent: dict[str, float], val_prov: dict[str, float]) -> dict[str, Any]:
    v = float(r["valor"])
    pv = float(val_prov.get(r["proveedor_id"], 0) or 1)
    ev = float(val_ent.get(r["entidad"], 0) or 1)
    return {
        "source": _slug("e", r["entidad"]),
        "target": _slug("p", r["proveedor_id"]),
        "valor": v,
        "n_procesos": int(r["n_procesos"]),
        "peso": max(v / 1e9, 0.05),
        "dependencia_proveedor_pct": round(100 * v / pv, 1),
        "participacion_entidad_pct": round(100 * v / ev, 1),
        "segmento": str(r.get("segmento_modo") or ""),
        "depto": str(r.get("depto") or ""),
    }


def _analisis_y_ego_rosario(edges: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    val_ent, val_prov, name_prov, by_ent, by_prov, ancla_prov, ancla_ent = _index_edges(edges)
    if not ancla_prov and not ancla_ent:
        empty = {
            "titulo": "Universidad del Rosario en la red SECOP–CTeI",
            "aviso": "No se encontró el Colegio Mayor / U. Rosario en adjudicaciones CTeI.",
            "perfil": {},
            "compradores": [],
            "competidores_frecuentes": [],
            "peers_ies": [],
            "lecturas": [],
        }
        return empty, _pack_graph(
            titulo="Ego Rosario (vacío)",
            subtitulo="",
            lectura="Sin ancla Rosario en el CSV.",
            nodes=[],
            links=[],
            n_edges_universo=len(edges),
        )

    # Unificar NIT ancla (suele ser uno)
    ros_pids = set(ancla_prov)
    ros_edges = [r for pid in ros_pids for r in by_prov.get(pid, [])]
    if ancla_ent:
        ros_edges.extend(r for ent in ancla_ent for r in by_ent.get(ent, []))
    # dedupe
    seen_re = set()
    ros_edges_u = []
    for r in ros_edges:
        k = (r["entidad"], r["proveedor_id"])
        if k in seen_re:
            continue
        seen_re.add(k)
        ros_edges_u.append(r)
    ros_edges = ros_edges_u

    ros_valor = sum(r["valor"] for r in ros_edges if r["proveedor_id"] in ros_pids)
    if ros_valor <= 0 and ros_pids:
        ros_valor = sum(val_prov.get(pid, 0) for pid in ros_pids)
    ros_nombre = next((name_prov[pid] for pid in ros_pids if pid in name_prov), "Universidad del Rosario")
    ros_nit = next(iter(sorted(ros_pids)), "")
    buyers = sorted({r["entidad"] for r in ros_edges if r["proveedor_id"] in ros_pids})

    compradores = []
    for ent in buyers:
        edge = next((r for r in ros_edges if r["entidad"] == ent and r["proveedor_id"] in ros_pids), None)
        if not edge:
            continue
        ev = val_ent.get(ent, 0) or 1
        compradores.append({
            "entidad": ent,
            "valor_con_rosario_cop": float(edge["valor"]),
            "n_procesos": int(edge["n_procesos"]),
            "pct_ingresos_rosario": round(100 * edge["valor"] / (ros_valor or 1), 1),
            "share_of_wallet_pct": round(100 * edge["valor"] / ev, 2),
            "gasto_entidad_ctei_cop": float(val_ent.get(ent, 0)),
            "segmento": edge.get("segmento_modo") or "",
            "depto": edge.get("depto") or "",
        })
    compradores.sort(key=lambda x: -x["valor_con_rosario_cop"])

    # Competidores: otros proveedores en los mismos compradores
    buyer_set = set(buyers)
    rival_stats: dict[str, dict[str, Any]] = {}
    for ent in buyer_set:
        for r in by_ent.get(ent, []):
            pid = r["proveedor_id"]
            if pid in ros_pids:
                continue
            st = rival_stats.get(pid)
            if st is None:
                st = {
                    "proveedor_id": pid,
                    "nombre": name_prov.get(pid, pid),
                    "ents_compartidas": set(),
                    "valor_en_ents_compartidas": 0.0,
                    "procesos_en_ents": 0,
                }
                rival_stats[pid] = st
            st["ents_compartidas"].add(ent)
            st["valor_en_ents_compartidas"] += r["valor"]
            st["procesos_en_ents"] += int(r["n_procesos"])

    competidores = []
    for st in rival_stats.values():
        ents = sorted(st["ents_compartidas"])
        # valor Rosario en esas mismas entidades
        v_ros = sum(
            r["valor"]
            for r in ros_edges
            if r["entidad"] in st["ents_compartidas"] and r["proveedor_id"] in ros_pids
        )
        competidores.append({
            "nombre": st["nombre"],
            "nit": st["proveedor_id"],
            "n_entidades_compartidas": len(ents),
            "entidades_ejemplo": ents[:5],
            "valor_rival_en_compartidas_cop": float(st["valor_en_ents_compartidas"]),
            "valor_rosario_en_compartidas_cop": float(v_ros),
            "ratio_rival_vs_rosario": round(
                st["valor_en_ents_compartidas"] / (v_ros or 1), 2
            ),
            "valor_total_proveedor_cop": float(val_prov.get(st["proveedor_id"], 0)),
            "es_ies": es_nombre_ies(st["nombre"] or ""),
        })
    competidores.sort(
        key=lambda x: (-x["n_entidades_compartidas"], -x["valor_rival_en_compartidas_cop"])
    )
    competidores = competidores[:TOP_COMPETIDORES_TABLA]

    # Peers IES por valor total en CTeI
    peers = []
    for pid, nom in name_prov.items():
        if pid in ros_pids:
            continue
        if not es_nombre_ies(nom or ""):
            continue
        peers.append({
            "nombre": nom,
            "nit": pid,
            "valor_total_cop": float(val_prov.get(pid, 0)),
            "n_entidades": len(by_prov.get(pid, [])),
            "vs_rosario_pct": round(100 * val_prov.get(pid, 0) / (ros_valor or 1), 1),
        })
    peers.sort(key=lambda x: -x["valor_total_cop"])
    peers = peers[:TOP_PEERS_IES]
    ros_rank_ies = 1 + sum(1 for p in peers if p["valor_total_cop"] > ros_valor)
    # recount full IES rank
    all_ies_vals = [
        val_prov[pid]
        for pid, nom in name_prov.items()
        if pid not in ros_pids and es_nombre_ies(nom or "")
    ]
    ros_rank_ies = 1 + sum(1 for v in all_ies_vals if v > ros_valor)

    top1 = compradores[0] if compradores else None
    top_comp = competidores[0] if competidores else None
    lecturas = [
        (
            f"Como proveedor CTeI, {ros_nombre} suma ~${ros_valor/1e9:.1f}B en "
            f"{len(buyers)} entidades compradoras y {sum(c['n_procesos'] for c in compradores)} procesos."
        ),
    ]
    if top1:
        lecturas.append(
            f"El comprador más importante es {top1['entidad']}: "
            f"{top1['pct_ingresos_rosario']}% de los ingresos Rosario "
            f"(share of wallet en esa entidad: {top1['share_of_wallet_pct']}%)."
        )
    if top_comp:
        lecturas.append(
            f"Competidor más frecuente (más entidades en común): {top_comp['nombre']} "
            f"({top_comp['n_entidades_compartidas']} compradores compartidos)."
        )
    lecturas.append(
        f"Entre IES/centros de formación en este universo CTeI, Rosario queda en el puesto "
        f"#{ros_rank_ies} por valor adjudicado."
    )
    lecturas.append(
        "El grafo ego muestra todos los compradores de Rosario y los rivales que más se cruzan "
        "en esos mismos compradores — no es todo SECOP (serían ~17k proveedores)."
    )

    analisis = {
        "titulo": "Universidad del Rosario en la red SECOP–CTeI",
        "subtitulo": (
            "Análisis egocéntrico: quién le compra, qué tan dependiente es cada vínculo, "
            "quién compite en los mismos compradores, y cómo se compara con otras IES."
        ),
        "perfil": {
            "nombre": ros_nombre,
            "nit": ros_nit,
            "valor_adjudicado_cop": float(ros_valor),
            "n_entidades_compradoras": len(buyers),
            "n_procesos": int(sum(c["n_procesos"] for c in compradores)),
            "n_competidores_con_overlap": len(rival_stats),
            "ranking_entre_ies": ros_rank_ies,
            "n_ies_en_universo": len(all_ies_vals) + 1,
        },
        "compradores": compradores,
        "competidores_frecuentes": competidores,
        "peers_ies": peers,
        "lecturas": lecturas,
        "nota": (
            "Universo = adjudicaciones UNSPSC 80/81/86 (proxy CTeI) en el CSV limpio Cap.2. "
            "Competidor frecuente = proveedor que también gana contratos en entidades "
            "donde Rosario ya es proveedor. Share of wallet = valor Rosario / gasto CTeI "
            "total de esa entidad."
        ),
    }

    # --- Ego graph ---
    top_rival_ids = {c["nit"] for c in competidores[:EGO_TOP_COMPETIDORES]}
    keep_edges: list[dict[str, Any]] = list(ros_edges)
    for ent in buyer_set:
        rivs = [
            r for r in by_ent.get(ent, [])
            if r["proveedor_id"] in top_rival_ids
        ]
        rivs.sort(key=lambda x: -x["valor"])
        keep_edges.extend(rivs[:EGO_TOP_EDGES_COMP_POR_ENT])

    seen = set()
    uniq = []
    for r in keep_edges:
        k = (r["entidad"], r["proveedor_id"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)

    keep_ent = {r["entidad"] for r in uniq}
    keep_prov = {r["proveedor_id"] for r in uniq}
    nodes = []
    for ent in keep_ent:
        nodes.append({
            "id": _slug("e", ent),
            "kind": "entidad",
            "label": _short(ent, 40),
            "nombre": ent,
            "valor": float(val_ent.get(ent, 0)),
            "degree": 0,
            "group": "comprador",
            "ancla": ent in ancla_ent,
            "ancla_id": "urosario" if ent in ancla_ent else None,
            "rol": "comprador_rosario" if ent in buyer_set else "entidad",
        })
    for pid in keep_prov:
        is_ancla = pid in ros_pids
        is_comp = pid in top_rival_ids
        nodes.append({
            "id": _slug("p", pid),
            "kind": "proveedor",
            "label": _short(name_prov.get(pid, pid), 40),
            "nombre": name_prov.get(pid, pid),
            "nit": pid,
            "valor": float(val_prov.get(pid, 0)),
            "degree": 0,
            "group": "vendedor",
            "ancla": is_ancla,
            "ancla_id": "urosario" if is_ancla else None,
            "competidor": is_comp,
            "rol": "rosario" if is_ancla else ("competidor" if is_comp else "proveedor"),
        })
    links = [_edge_link(r, val_ent, val_prov) for r in uniq]
    ego = _pack_graph(
        titulo="Red ego · Universidad del Rosario",
        subtitulo=(
            "Todos los compradores de Rosario + competidores frecuentes en esos mismos "
            "compradores. Ideal para ver dependencia y rivalidad local."
        ),
        lectura=(
            f"Ego-red: {len(nodes)} actores / {len(links)} vínculos. "
            f"Incluye {len(buyers)} entidades que le compran a Rosario y "
            f"{len(top_rival_ids)} rivales con overlap."
        ),
        nodes=nodes,
        links=links,
        n_edges_universo=len(edges),
        como_leer=[
            "Midnight Violet = Rosario. Granate = competidor frecuente. French Blue = entidad. Powder = proveedor.",
            "Clic en un rival para ver en qué entidades se cruza con Rosario.",
            "Esto NO es todo SECOP: es la vecindad útil para decisión comercial de Rosario.",
        ],
    )
    return analisis, ego


def main() -> None:
    print("Agregando aristas entidad-proveedor...")
    edges = _load_edges()
    n_ent = len({r["entidad"] for r in edges})
    n_prov = len({r["proveedor_id"] for r in edges})
    print(f"  universo edges={len(edges)} entidades={n_ent} prov={n_prov}")

    print("Construyendo red de mercado ampliada...")
    graph = _build_subgraph(edges)
    print("  mercado nodes", graph["meta"]["n_nodos"], "links", graph["meta"]["n_aristas"])

    print("Análisis + ego Rosario...")
    analisis, ego = _analisis_y_ego_rosario(edges)
    print(
        "  compradores",
        analisis.get("perfil", {}).get("n_entidades_compradoras"),
        "competidores",
        len(analisis.get("competidores_frecuentes") or []),
        "ego nodes",
        ego["meta"]["n_nodos"],
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    ros_payload = {
        "analisis_rosario": analisis,
        "red_ego_rosario": ego,
        "red_mercado_meta": graph["meta"],
    }
    OUT_ROS.write_text(json.dumps(ros_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", OUT)
    print("Wrote", OUT_ROS)

    if CAP2.exists():
        cap2 = json.loads(CAP2.read_text(encoding="utf-8"))
    else:
        cap2 = {"titulo": "Mercado"}
    cap2["red_mercado"] = graph
    cap2["red_ego_rosario"] = ego
    cap2["analisis_rosario"] = analisis
    # actualizar cierre con lecturas cuantitativas
    if analisis.get("lecturas"):
        cap2["cierre_rosario"] = {
            "titulo": "Qué implica para la Universidad del Rosario",
            "puntos": analisis["lecturas"][:5],
        }
    CAP2.write_text(json.dumps(cap2, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Updated", CAP2)

    if DASH.exists():
        dash = json.loads(DASH.read_text(encoding="utf-8"))
        if "capacidad_2" not in dash:
            dash["capacidad_2"] = {}
        dash["capacidad_2"]["red_mercado"] = graph
        dash["capacidad_2"]["red_ego_rosario"] = ego
        dash["capacidad_2"]["analisis_rosario"] = analisis
        if analisis.get("lecturas"):
            dash["capacidad_2"]["cierre_rosario"] = {
                "titulo": "Qué implica para la Universidad del Rosario",
                "puntos": analisis["lecturas"][:5],
            }
        DASH.write_text(json.dumps(dash, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Updated", DASH)


if __name__ == "__main__":
    main()
