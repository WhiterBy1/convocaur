"""Reclasifica es_ies en artefactos Cap.2 sin re-correr todo el grafo."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEC = ROOT / "data" / "processed" / "secop"

_PEER_IES_WORDS = re.compile(
    r"\bUNIVERSIDAD\b|\bCOLEGIO\s+MAYOR\b|\bPOLIT[EÉ]CNICO\b|"
    r"\bESCUELA\s+SUPERIOR\b|\bINSTITUTO\s+TECNOL|\bFUNDACI[OÓ]N\s+UNIVERSIT|"
    r"\bCORPORACI[OÓ]N\s+UNIVERSIT|\bINSTITUCI[OÓ]N\s+UNIVERSIT|"
    r"\bCENTRO\s+DE\s+FORMACI",
    re.IGNORECASE,
)
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
    "POLI",
}


def es_nombre_ies(nombre: str) -> bool:
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


def patch_analisis(a: dict) -> list[str]:
    flips: list[str] = []
    for c in a.get("competidores_frecuentes") or []:
        old = bool(c.get("es_ies"))
        new = es_nombre_ies(c.get("nombre") or "")
        if old != new:
            c["es_ies"] = new
            flips.append(f"{c.get('nombre')}: {old} -> {new}")
    return flips


def main() -> None:
    for name in ("UNISALLE", "UNIMINUTO", "UPTC", "ETB SA ESP", "UNIVERSIDAD NACIONAL"):
        print(f"test {name!r} -> {es_nombre_ies(name)}")

    ros = SEC / "capacidad2_rosario.json"
    data = json.loads(ros.read_text(encoding="utf-8"))
    ros_node = data.get("analisis_rosario") if "analisis_rosario" in data else data
    flips = patch_analisis(ros_node if isinstance(ros_node, dict) else data)
    ros.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("rosario flips:", *flips, sep="\n  ")

    merc = SEC / "capacidad2_mercado.json"
    m = json.loads(merc.read_text(encoding="utf-8"))
    flips_m = patch_analisis(m.get("analisis_rosario") or {})
    merc.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print("mercado flips:", *flips_m, sep="\n  ")

    dash = SEC / "resumen_dashboard.json"
    d = json.loads(dash.read_text(encoding="utf-8"))
    flips_d: list[str] = []

    def walk(o: object) -> None:
        if isinstance(o, dict):
            if "competidores_frecuentes" in o:
                flips_d.extend(patch_analisis(o))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(d)
    # dedupe identical messages from nested copies
    flips_d = list(dict.fromkeys(flips_d))
    dash.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    print("dashboard flips:", *flips_d, sep="\n  ")


if __name__ == "__main__":
    main()
