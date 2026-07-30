"""
Extrae texto de TdR Minciencias separado por secciones de la tabla de contenido
================================================================================
Rol: Ingesta / ETL

Para cada PDF en data/raw/minciencias/tdr/:
  1. Extrae el texto completo
  2. Detecta la tabla de contenido (N. TITULO ..... página)
  3. Localiza esos mismos encabezados en el cuerpo del documento
  4. Parte el texto entre secciones
  5. Compara la secuencia de secciones entre convocatorias

Salida:
    data/processed/minciencias_tdr_secciones/
      convocatoria_48_secciones.json
      ...
      estructura_comparacion.csv
      estructura_resumen.json

Uso:
    python extraer_secciones_tdr.py
    python extraer_secciones_tdr.py --tdr-dir ../data/raw/minciencias/tdr
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import pdfplumber

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("extraer_secciones_tdr")

from convocaur.paths import PROC_SECCIONES, RAW_MINCIENCIAS_TDR

DEFAULT_TDR_DIR = RAW_MINCIENCIAS_TDR
DEFAULT_OUT_DIR = PROC_SECCIONES

# Plantilla del TOC que mostró el equipo (convocatoria tipo SGR, imagen)
PLANTILLA_SGR_BASE = [
    "PRESENTACION",
    "OBJETIVO",
    "DIRIGIDA A",
    "DEMANDAS TERRITORIALES",
    "LINEAS TEMATICAS",
    "ALCANCE DEL PROYECTO",
    "ENFOQUE TERRITORIAL",
    "ENFOQUE DIFERENCIAL E INTERSECCIONAL",
    "ORIENTACIONES PARA LA VINCULACION DE TALENTO HUMANO",
    "REQUISITOS HABILITANTES",
    "CAUSALES DE RECHAZO",
    "CONTENIDO DEL PROYECTO",
    "PROCEDIMIENTO DE INSCRIPCION",
    "DURACION Y FINANCIACION",
    "CRITERIOS DE EVALUACION",
    "PROCEDIMIENTO DE EVALUACION",
    "LISTADO DE ELEGIBLES",
    "OBSERVACIONES AL LISTADO DE HABILITADOS Y ELEGIBLES",
    "VIGILANCIA DE LOS PROYECTOS",
    "REVISION DE REQUISITOS DEL SISTEMA GENERAL DE REGALIAS",
    "CRONOGRAMA",
]

# Línea de TOC: "1. PRESENTACIÓN ..... 3", "1 PRESENTACIÓN ..... 3" (sin punto
# tras el número, visto en convocatorias tipo 917/932) o "1. PRESENTACIÓN 3"
RE_TOC = re.compile(
    r"^(\d{1,2})\.?\s*"
    r"([A-ZÁÉÍÓÚÑÜ][A-ZÁÉÍÓÚÑÜa-záéíóúñü\s,/()\-]{3,}?)"
    r"\s*(?:\.{2,}|\s+)\s*"
    r"(\d{1,3})\s*$"
)

# Encabezado de cuerpo: "1. PRESENTACIÓN" o "1 PRESENTACIÓN" (sin puntos
# líderes ni página al final)
RE_BODY = re.compile(
    r"^(\d{1,2})\.?\s*"
    r"([A-ZÁÉÍÓÚÑÜ][A-ZÁÉÍÓÚÑÜ\s,/()\-]{3,100}?)"
    r"(?:\s+\d{1,3})?\s*$"  # a veces el OCR/PDF pega el nº de página
)


def normalizar_titulo(texto: str) -> str:
    """Quita acentos, unifica espacios y pasa a mayúsculas sin puntuación final."""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.upper()
    texto = re.sub(r"[^\w\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    # Variantes frecuentes
    texto = texto.replace("DIRIGIDO A", "DIRIGIDA A")
    texto = texto.replace("LINEA TEMATICA", "LINEAS TEMATICAS")
    texto = re.sub(r"^OBSERVACIONES LISTADO\b", "OBSERVACIONES AL LISTADO DE HABILITADOS Y ELEGIBLES", texto)
    texto = re.sub(
        r"^OBSERVACIONES AL LISTADO DE ELEGIBLES\b",
        "OBSERVACIONES AL LISTADO DE HABILITADOS Y ELEGIBLES",
        texto,
    )
    return texto


def proporcion_mayusculas(texto: str) -> float:
    letras = [c for c in texto if c.isalpha()]
    if not letras:
        return 0.0
    return sum(1 for c in letras if c.isupper()) / len(letras)


# Palabras cortas y muy frecuentes en prosa en español. Si el texto está bien
# espaciado deberían aparecer decenas de veces como tokens sueltos; si el PDF
# pegó las palabras, prácticamente no aparecerán aisladas (quedan fundidas
# con la palabra vecina). Más confiable que el largo promedio de "palabra"
# (los puntos suspensivos de un TOC cuentan como una palabra larga y dan
# falsos positivos con ese otro método).
_STOPWORDS_RE = re.compile(r"\b(de|la|el|en|y|del|los|las|para|que|con|una|por)\b", re.IGNORECASE)


def _texto_pegado(texto: str, muestra_chars: int = 4000, minimo_stopwords: int = 15) -> bool:
    """Detecta texto sin espacios entre palabras (glitch de extracción de
    algunos PDF) contando stopwords cortas como tokens aislados."""
    muestra = texto[:muestra_chars]
    if not muestra.strip():
        return True
    return len(_STOPWORDS_RE.findall(muestra)) < minimo_stopwords


def _extraer_con_pdfplumber(path: Path) -> tuple[str, int]:
    with pdfplumber.open(str(path)) as pdf:
        paginas = [page.extract_text() or "" for page in pdf.pages]
        return "\n".join(paginas), len(pdf.pages)


def _extraer_con_pypdf(path: Path) -> tuple[str, int]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    paginas = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(paginas), len(reader.pages)


# PDF escaneados (sin capa de texto): ni pdfplumber ni pypdf extraen nada.
# Como último recurso se rasteriza cada página con pymupdf y se transcribe
# con un LLM de visión gratuito en OpenRouter. El pool gratuito comparte
# rate-limit entre todos los usuarios y falla de forma intermitente (se
# probó en piloto: 2 de 3 modelos fallaron por rate-limit/timeout en un
# intento), por eso la cadena de fallback entre varios modelos en vez de
# depender de uno solo. Configurable vía OPENROUTER_OCR_MODELS en .env
# (lista separada por comas, mismo patrón que OPENROUTER_MODEL para nlp).
# Orden por defecto según confiabilidad observada en el piloto.
_MODELOS_OCR_FALLBACK_DEFAULT = [
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
]


def _modelos_ocr_fallback() -> list[str]:
    import os

    valor = os.getenv("OPENROUTER_OCR_MODELS")
    if not valor:
        return _MODELOS_OCR_FALLBACK_DEFAULT
    return [m.strip() for m in valor.split(",") if m.strip()]

UMBRAL_TEXTO_VACIO = 200  # chars totales del documento; menos que esto -> intentar OCR

_OCR_PROMPT = (
    "Transcribe TODO el texto de esta imagen de un documento oficial en "
    "español, tal cual aparece, sin resumir ni omitir nada. No agregues "
    "comentarios tuyos, solo la transcripción."
)


# Límites para detectar transcripciones "degeneradas": algunos modelos
# gratuitos, sobre todo los de razonamiento, a veces filtran su cadena de
# pensamiento dentro del contenido final, o entran en un bucle repitiendo la
# misma oración hasta el límite de tokens (visto en piloto: una sola página
# devolvió 160k+ caracteres, casi todo el mismo fragmento repetido cientos de
# veces). Una página normal de este tipo de documento ronda 1.5k-6k chars.
MAX_CHARS_PAGINA_OCR = 9000
_LARGO_NGRAMA_REPETICION = 40
_MIN_REPETICIONES_SOSPECHOSAS = 4


def _ocr_texto_degenerado(texto: str) -> bool:
    """Detecta fuga de razonamiento (frases tipo "Self-Correction", "Draft &
    Refinement") o bucles de repetición, ademas del tope simple de longitud."""
    if len(texto) > MAX_CHARS_PAGINA_OCR:
        return True
    if re.search(r"self-correction|draft (&|and) refinement|as an ai", texto, re.IGNORECASE):
        return True
    if len(texto) > _LARGO_NGRAMA_REPETICION * _MIN_REPETICIONES_SOSPECHOSAS:
        muestra = texto[len(texto) // 3 : len(texto) // 3 + _LARGO_NGRAMA_REPETICION]
        if muestra.strip() and texto.count(muestra) >= _MIN_REPETICIONES_SOSPECHOSAS:
            return True
    return False


def _ocr_pagina(imagen_png: bytes, max_reintentos_por_modelo: int = 1) -> str:
    """Transcribe una página escaneada probando la cadena de modelos de OCR.

    Si un modelo devuelve un resultado degenerado (ver `_ocr_texto_degenerado`)
    se descarta como si hubiera fallado y se pasa al siguiente modelo de la
    cadena. Devuelve "" si todos fallan (no debe frenar el resto del
    documento por una sola página problemática).
    """
    import base64
    import time

    import requests

    from convocaur.nlp.extract_llm import OPENROUTER_URL, get_api_key

    b64 = base64.b64encode(imagen_png).decode("utf-8")
    headers = {"Authorization": f"Bearer {get_api_key()}", "Content-Type": "application/json"}

    for modelo in _modelos_ocr_fallback():
        for intento in range(max_reintentos_por_modelo + 1):
            payload = {
                "model": modelo,
                "reasoning": {"enabled": False},
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": _OCR_PROMPT},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                        ],
                    }
                ],
            }
            try:
                resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=150)
                data = resp.json()
            except Exception as exc:
                log.warning("OCR: fallo de red con %s (intento %s): %s", modelo, intento, exc)
                continue
            if "choices" in data:
                contenido = data["choices"][0]["message"]["content"]
                if _ocr_texto_degenerado(contenido):
                    log.warning(
                        "OCR: %s devolvió una transcripción degenerada (%s chars, intento %s), se descarta",
                        modelo, len(contenido), intento,
                    )
                    continue
                return contenido
            log.warning("OCR: %s no respondió (intento %s): %s", modelo, intento, data.get("error"))
            time.sleep(2)
    log.error("OCR: todos los modelos de la cadena de fallback fallaron para esta página")
    return ""


def _ocr_pdf(path: Path) -> tuple[str, int]:
    """OCR página por página vía LLM de visión, para PDF sin capa de texto."""
    import fitz

    doc = fitz.open(str(path))
    n_paginas = doc.page_count
    textos = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=200)
        log.info("  OCR %s página %s/%s ...", path.name, i + 1, n_paginas)
        textos.append(_ocr_pagina(pix.tobytes("png")))
    doc.close()
    return "\n".join(textos), n_paginas


def extraer_texto_pdf(path: Path, ocr_si_vacio: bool = True) -> tuple[str, int]:
    """Extrae el texto completo del PDF.

    pdfplumber suele preservar mejor los espacios entre palabras que pypdf,
    pero para algunos PDF específicos ocurre lo contrario (font/encoding
    particular). Se prueba pdfplumber primero y, si el resultado sale con
    palabras pegadas, se reintenta con pypdf y se usa el que no esté pegado
    (o el que tenga palabras más cortas, si ambos lo están).

    Si ninguno de los dos extrae texto real (PDF escaneado), se cae a OCR
    vía LLM de visión (ver `_ocr_pdf`), salvo que `ocr_si_vacio=False`.
    """
    try:
        texto, n_paginas = _extraer_con_pdfplumber(path)
    except Exception as exc:
        log.warning("pdfplumber falló en %s: %s", path.name, exc)
        texto, n_paginas = "", 0

    if _texto_pegado(texto):
        try:
            texto_alt, n_paginas_alt = _extraer_con_pypdf(path)
        except Exception as exc:
            log.warning("pypdf falló en %s: %s", path.name, exc)
            texto_alt, n_paginas_alt = "", 0

        if texto_alt.strip() and not _texto_pegado(texto_alt):
            log.info("%s: pdfplumber dio texto pegado, se usó pypdf en su lugar", path.name)
            texto, n_paginas = texto_alt, n_paginas_alt
        elif texto_alt.strip() and len(_STOPWORDS_RE.findall(texto_alt[:4000])) > len(
            _STOPWORDS_RE.findall(texto[:4000])
        ):
            # Ambos vienen pegados: nos quedamos con el que tenga más stopwords sueltas
            texto, n_paginas = texto_alt, n_paginas_alt

    if ocr_si_vacio and len(texto.strip()) < UMBRAL_TEXTO_VACIO:
        log.warning("%s: sin texto extraíble (%s chars), probando OCR vía LLM", path.name, len(texto.strip()))
        texto_ocr, n_paginas_ocr = _ocr_pdf(path)
        if len(texto_ocr.strip()) > len(texto.strip()):
            return texto_ocr, n_paginas_ocr

    return texto, n_paginas


def detectar_toc(texto: str, max_chars_busqueda: int = 18000) -> list[dict]:
    """Busca entradas de tabla de contenido al inicio del documento."""
    trozo = texto[:max_chars_busqueda]
    toc = []
    vistos = set()
    for line in trozo.splitlines():
        s = line.strip()
        m = RE_TOC.match(s)
        if not m:
            continue
        num = int(m.group(1))
        titulo = m.group(2).strip()
        pagina = int(m.group(3))
        if proporcion_mayusculas(titulo) < 0.7:
            continue
        # Evitar falsos positivos tipo "1. La implementación..." (minúsculas ya filtradas)
        # o listas cortas que no son TOC
        titulo_norm = normalizar_titulo(titulo)
        if len(titulo_norm) < 5:
            continue
        clave = (num, titulo_norm)
        if clave in vistos:
            continue
        vistos.add(clave)
        toc.append({
            "numero": num,
            "titulo": titulo,
            "titulo_norm": titulo_norm,
            "pagina_toc": pagina,
        })
    # Si el TOC está desordenado / con ruido, quedarnos con la secuencia
    # que empieza en 1 y avanza de forma monótona.
    return _secuencia_monotona(toc)


def _secuencia_monotona(items: list[dict]) -> list[dict]:
    if not items:
        return []
    # Preferir el tramo que empieza en número 1
    inicio = next((i for i, x in enumerate(items) if x["numero"] == 1), 0)
    secuencia = [items[inicio]]
    for item in items[inicio + 1 :]:
        if item["numero"] > secuencia[-1]["numero"]:
            secuencia.append(item)
        elif item["numero"] == 1 and len(secuencia) < 5:
            # Reinicio temprano: probablemente TOC real empieza aquí
            secuencia = [item]
    return secuencia


def detectar_encabezados_cuerpo(texto: str, toc: list[dict] | None = None) -> list[dict]:
    """Localiza posiciones de encabezados de sección en el cuerpo."""
    permitidos = None
    if toc:
        permitidos = {(e["numero"], e["titulo_norm"]) for e in toc}

    candidatos = []
    offset = 0
    for line in texto.splitlines(keepends=True):
        s = line.strip()
        # Saltar líneas de TOC (tienen puntos o página al final)
        if RE_TOC.match(s):
            offset += len(line)
            continue
        m = RE_BODY.match(s)
        if m and proporcion_mayusculas(m.group(2)) >= 0.85:
            num = int(m.group(1))
            titulo = m.group(2).strip()
            # Descartar si el "título" termina en dígitos sueltos (página pegada)
            titulo = re.sub(r"\s+\d{1,3}$", "", titulo).strip()
            titulo_norm = normalizar_titulo(titulo)
            if len(titulo_norm) < 4:
                offset += len(line)
                continue
            if permitidos is None or (num, titulo_norm) in permitidos or any(
                t == titulo_norm or titulo_norm.startswith(t) or t.startswith(titulo_norm)
                for _, t in permitidos
            ):
                candidatos.append({
                    "numero": num,
                    "titulo": titulo,
                    "titulo_norm": titulo_norm,
                    "posicion": offset,
                })
        offset += len(line)

    if not candidatos:
        return []

    # Quedarnos con la mejor secuencia monótona a partir del primer "1."
    return _secuencia_monotona_por_posicion(candidatos)


def _secuencia_monotona_por_posicion(items: list[dict]) -> list[dict]:
    # Empezar en el primer número 1; si no hay, en el primero
    inicio_idxs = [i for i, x in enumerate(items) if x["numero"] == 1]
    mejor = []
    for inicio in (inicio_idxs or [0]):
        seq = [items[inicio]]
        for item in items[inicio + 1 :]:
            if item["numero"] > seq[-1]["numero"] and item["posicion"] > seq[-1]["posicion"]:
                # Evitar duplicar mismo título
                if item["titulo_norm"] == seq[-1]["titulo_norm"]:
                    continue
                seq.append(item)
        if len(seq) > len(mejor):
            mejor = seq
    return mejor


def partir_por_secciones(texto: str, encabezados: list[dict]) -> list[dict]:
    secciones = []
    for i, enc in enumerate(encabezados):
        inicio = enc["posicion"]
        fin = encabezados[i + 1]["posicion"] if i + 1 < len(encabezados) else len(texto)
        bloque = texto[inicio:fin].strip()
        # Quitar la línea del encabezado del contenido
        lineas = bloque.splitlines()
        contenido = "\n".join(lineas[1:]).strip() if lineas else ""
        secciones.append({
            "numero": enc["numero"],
            "titulo": enc["titulo"],
            "titulo_norm": enc["titulo_norm"],
            "texto": contenido,
            "n_caracteres": len(contenido),
        })
    return secciones


def fingerprint_estructura(secciones: list[dict]) -> str:
    return " > ".join(f"{s['numero']}.{s['titulo_norm']}" for s in secciones)


def comparar_con_plantilla(titulos_norm: list[str], plantilla: list[str]) -> dict:
    set_doc = set(titulos_norm)
    set_plantilla = set(plantilla)
    return {
        "n_en_doc": len(titulos_norm),
        "n_plantilla": len(plantilla),
        "coinciden_exacto": titulos_norm == plantilla,
        "cobertura_plantilla": round(len(set_doc & set_plantilla) / len(plantilla), 3) if plantilla else 0,
        "faltan_vs_plantilla": [t for t in plantilla if t not in set_doc],
        "extra_vs_plantilla": [t for t in titulos_norm if t not in set_plantilla],
    }


def procesar_pdf(path: Path, ocr_si_vacio: bool = True) -> dict:
    log.info("Procesando %s", path.name)
    texto, n_paginas = extraer_texto_pdf(path, ocr_si_vacio=ocr_si_vacio)
    toc = detectar_toc(texto)
    encabezados = detectar_encabezados_cuerpo(texto, toc if toc else None)

    # Si hay TOC pero pocos encabezados de cuerpo, intentar sin filtro TOC
    if toc and len(encabezados) < max(5, len(toc) // 2):
        encabezados = detectar_encabezados_cuerpo(texto, toc=None)

    secciones = partir_por_secciones(texto, encabezados) if encabezados else []
    titulos = [s["titulo_norm"] for s in secciones]
    plantilla_cmp = comparar_con_plantilla(titulos, PLANTILLA_SGR_BASE)

    m = re.search(r"convocatoria_([^_]+)_tdr", path.stem)
    conv = m.group(1) if m else path.stem

    return {
        "archivo": path.name,
        "convocatoria": conv,
        "n_paginas": n_paginas,
        "n_caracteres_total": len(texto),
        "toc_detectado": toc,
        "n_secciones_toc": len(toc),
        "n_secciones_cuerpo": len(secciones),
        "fingerprint": fingerprint_estructura(secciones),
        "titulos_norm": titulos,
        "comparacion_plantilla_sgr": plantilla_cmp,
        "secciones": secciones,
        "texto_completo": texto,
    }


def resumen_comparacion(resultados: list[dict]) -> dict:
    por_fp = defaultdict(list)
    for r in resultados:
        por_fp[r["fingerprint"] or "(sin secciones)"].append(r["convocatoria"])

    # Secciones más frecuentes (para ver el "núcleo" común)
    freq = Counter()
    for r in resultados:
        freq.update(r["titulos_norm"])

    return {
        "n_documentos": len(resultados),
        "n_estructuras_distintas": len(por_fp),
        "todas_misma_estructura": len(por_fp) == 1 and bool(resultados),
        "grupos_estructura": [
            {"fingerprint": fp, "convocatorias": convs, "n": len(convs)}
            for fp, convs in sorted(por_fp.items(), key=lambda x: -len(x[1]))
        ],
        "secciones_mas_frecuentes": freq.most_common(40),
        "cobertura_plantilla_sgr": {
            r["convocatoria"]: r["comparacion_plantilla_sgr"]["cobertura_plantilla"]
            for r in resultados
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Extrae y compara secciones de TdR Minciencias")
    parser.add_argument("--tdr-dir", type=Path, default=DEFAULT_TDR_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--guardar-texto-completo", action="store_true",
                        help="Incluir texto_completo en cada JSON (archivos más pesados)")
    parser.add_argument(
        "--sin-ocr",
        action="store_true",
        help="No intentar OCR vía LLM en PDF sin capa de texto (mas rapido, deja esos documentos vacios)",
    )
    args = parser.parse_args()

    pdfs = sorted(args.tdr_dir.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No hay PDFs en {args.tdr_dir}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    resultados = []

    for pdf in pdfs:
        try:
            res = procesar_pdf(pdf, ocr_si_vacio=not args.sin_ocr)
        except Exception as exc:
            log.error("Error en %s: %s", pdf.name, exc)
            resultados.append({
                "archivo": pdf.name,
                "convocatoria": pdf.stem,
                "error": str(exc),
                "fingerprint": "",
                "titulos_norm": [],
                "n_secciones_cuerpo": 0,
                "comparacion_plantilla_sgr": comparar_con_plantilla([], PLANTILLA_SGR_BASE),
                "secciones": [],
                "toc_detectado": [],
                "n_paginas": 0,
                "n_caracteres_total": 0,
                "n_secciones_toc": 0,
            })
            continue

        out_json = {
            k: v for k, v in res.items()
            if k != "texto_completo" or args.guardar_texto_completo
        }
        # En el JSON de secciones no hace falta duplicar todo el texto crudo
        # salvo que se pida; el texto por sección ya va en secciones[].texto
        path_out = args.out_dir / f"convocatoria_{res['convocatoria']}_secciones.json"
        with open(path_out, "w", encoding="utf-8") as f:
            json.dump(out_json, f, ensure_ascii=False, indent=2)
        log.info(
            "  %s: toc=%s cuerpo=%s cobertura_plantilla=%.0f%%",
            res["convocatoria"],
            res["n_secciones_toc"],
            res["n_secciones_cuerpo"],
            100 * res["comparacion_plantilla_sgr"]["cobertura_plantilla"],
        )
        resultados.append(res)

    resumen = resumen_comparacion(resultados)
    with open(args.out_dir / "estructura_resumen.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)

    # CSV plano para revisar en Excel
    import pandas as pd

    filas = []
    for r in resultados:
        filas.append({
            "convocatoria": r.get("convocatoria"),
            "archivo": r.get("archivo"),
            "n_paginas": r.get("n_paginas"),
            "n_secciones_toc": r.get("n_secciones_toc"),
            "n_secciones_cuerpo": r.get("n_secciones_cuerpo"),
            "cobertura_plantilla_sgr": r.get("comparacion_plantilla_sgr", {}).get("cobertura_plantilla"),
            "coincide_plantilla_exacto": r.get("comparacion_plantilla_sgr", {}).get("coinciden_exacto"),
            "fingerprint": r.get("fingerprint"),
            "titulos": " | ".join(r.get("titulos_norm") or []),
        })
    df = pd.DataFrame(filas)
    df.to_csv(args.out_dir / "estructura_comparacion.csv", index=False, encoding="utf-8")

    print("\n=== ¿Todas tienen la misma estructura? ===")
    print("NO" if not resumen["todas_misma_estructura"] else "SÍ")
    print(f"Documentos: {resumen['n_documentos']} | estructuras distintas: {resumen['n_estructuras_distintas']}")
    print("\nGrupos:")
    for g in resumen["grupos_estructura"]:
        print(f"  [{g['n']} docs] {', '.join(g['convocatorias'])}")
        fp_corto = g["fingerprint"][:120] + ("..." if len(g["fingerprint"]) > 120 else "")
        print(f"     {fp_corto}")
    print("\nCobertura vs plantilla SGR (imagen TOC 1-21):")
    for conv, cov in resumen["cobertura_plantilla_sgr"].items():
        print(f"  {conv}: {cov:.0%}")
    print(f"\nSalida: {args.out_dir}")


if __name__ == "__main__":
    main()
