"""
Extractor de contenido de anexos - ConvocaUR (prototipo Nivel 2)
=================================================================
Rol: Ingesta y ETL

A diferencia de scrape_minciencias.py (que solo guarda METADATOS del
documento: nombre, tipo, link), este script SÍ abre el PDF y extrae:
  1. El texto completo
  2. Las tablas que el PDF tenga con líneas reales (si las tiene)
  3. Reglas de porcentaje obligatorio/máximo mencionadas en el texto
     (ej. "mínimo el 5% del proyecto", "no podrá ser mayor al 50%")
  4. Montos de dinero mencionados

Esto es lo que llamamos "Nivel 2" en la conversación con el equipo: no
intenta entender cada anexo como un formulario completo (Nivel 3, poco
viable porque no hay una plantilla fija), pero sí saca señales puntuales
que la Calculadora puede usar sin que alguien tenga que leer el PDF a mano.

IMPORTANTE - limitaciones reales que hay que validar con el equipo:
  - `extraer_tablas` solo funciona si el PDF tiene líneas de tabla
    dibujadas (pdfplumber detecta *rejillas visuales*, no columnas de
    texto alineado). Varios anexos de Minciencias usan un layout de dos
    columnas SIN líneas dibujadas -> en ese caso `tablas` puede salir
    vacío aunque visualmente se vea como tabla. Si eso pasa, hay que
    usar `extraer_reglas_financieras` sobre el texto plano en su lugar,
    o ajustar la estrategia (heurística de texto por posición X del
    layout con pdfplumber.chars, más avanzado).
  - Los patrones de porcentaje están calibrados sobre el lenguaje típico
    de estos documentos ("mínimo al X%", "no podrá ser mayor al X%", "no
    supere el X%"). Si aparecen variantes de redacción no capturadas,
    hay que ampliar PATRONES_REGLAS.
  - Este script no se pudo probar contra el PDF real descargado por bytes
    en este entorno (sandbox sin salida de red hacia minciencias.gov.co).
    Las funciones de regex sí están probadas con texto de ejemplo
    representativo (ver `test_extractor.py`).

Uso:
    python extraer_contenido_anexo.py --url <URL_DEL_PDF_DEL_ANEXO>
"""

import argparse
import io
import logging
import re

import pdfplumber
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("extraer_contenido_anexo")


def descargar_pdf(url: str) -> bytes:
    resp = requests.get(url, timeout=30, headers={"User-Agent": "ConvocaUR-ETL/0.1"})
    resp.raise_for_status()
    return resp.content


def extraer_texto_y_tablas(pdf_bytes: bytes) -> tuple[str, list]:
    paginas_texto = []
    tablas = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for pagina in pdf.pages:
            paginas_texto.append(pagina.extract_text() or "")
            tablas.extend(pagina.extract_tables())
    return "\n".join(paginas_texto), tablas


# Patrones formulaicos de reglas de porcentaje que se repiten en varios
# anexos financieros de Minciencias (no son texto creativo, son fórmulas
# administrativas estándar tipo "no podrá exceder el X%").
PATRONES_REGLAS = [
    ("minimo_obligatorio_pct", re.compile(
        r"m[íi]nimo\s+al?\s+(\d+)\s*%.{0,100}?obligatoria",
        re.IGNORECASE | re.DOTALL,
    )),
    ("maximo_pct", re.compile(
        r"no\s+podr[áa]\s+ser\s+mayor\s+al\s+(\d+)\s*%",
        re.IGNORECASE,
    )),
    ("tope_pct", re.compile(
        r"no\s+(?:debe\s+)?super(?:e|a)(?:r)?\s+el\s+(\d+)\s*%",
        re.IGNORECASE,
    )),
]


def extraer_reglas_financieras(texto: str) -> list[dict]:
    """Busca reglas de porcentaje (mínimos obligatorios, máximos, topes)."""
    hallazgos = []
    for tipo_regla, patron in PATRONES_REGLAS:
        for m in patron.finditer(texto):
            inicio = max(0, m.start() - 60)
            contexto = texto[inicio:m.start()].strip().replace("\n", " ")
            hallazgos.append({
                "tipo_regla": tipo_regla,
                "valor_pct": int(m.group(1)),
                "contexto_previo": contexto[-60:],
            })
    return hallazgos


def extraer_montos(texto: str) -> list[str]:
    return re.findall(r"\$\s?[\d.,]{4,}", texto)


def rubros_desde_tabla(tablas: list) -> list[dict]:
    """Convierte filas de tabla (columna 1 = rubro, columna 2 = descripción)
    en una lista de diccionarios. Solo funciona si pdfplumber detectó una
    tabla real (ver limitación en el docstring del módulo)."""
    rubros = []
    encabezados_a_saltar = {"rubros", "rubro", "descripción / exclusiones", "descripcion"}
    for tabla in tablas:
        for fila in tabla:
            if fila and len(fila) >= 2 and fila[0] and fila[1]:
                nombre = fila[0].strip().replace("\n", " ")
                descripcion = fila[1].strip().replace("\n", " ")
                if nombre.lower() not in encabezados_a_saltar:
                    rubros.append({"rubro": nombre, "descripcion": descripcion})
    return rubros


def analizar_anexo(url: str) -> dict:
    log.info("Descargando %s", url)
    pdf_bytes = descargar_pdf(url)

    texto, tablas = extraer_texto_y_tablas(pdf_bytes)
    log.info("Texto extraído: %s caracteres | tablas detectadas: %s", len(texto), len(tablas))

    resultado = {
        "reglas_porcentaje": extraer_reglas_financieras(texto),
        "montos_detectados": extraer_montos(texto),
        "rubros_desde_tabla": rubros_desde_tabla(tablas),
        "longitud_texto": len(texto),
        "tablas_detectadas": len(tablas),
    }
    return resultado


def main():
    parser = argparse.ArgumentParser(description="Extractor de contenido de anexos Minciencias (Nivel 2)")
    parser.add_argument("--url", required=True, help="URL del PDF del anexo")
    args = parser.parse_args()

    resultado = analizar_anexo(args.url)

    print("\n=== Reglas de porcentaje detectadas ===")
    for r in resultado["reglas_porcentaje"]:
        print(f"  [{r['tipo_regla']}] {r['valor_pct']}%  (contexto: ...{r['contexto_previo']})")

    print(f"\n=== Montos detectados: {len(resultado['montos_detectados'])} ===")
    for m in resultado["montos_detectados"][:10]:
        print(" ", m)

    print(f"\n=== Rubros extraídos de tabla real: {len(resultado['rubros_desde_tabla'])} ===")
    if not resultado["rubros_desde_tabla"]:
        print("  (vacío -> probablemente el PDF no tiene líneas de tabla dibujadas;")
        print("   revisar si el layout es de dos columnas sin rejilla)")
    for r in resultado["rubros_desde_tabla"]:
        print(f"  - {r['rubro']}: {r['descripcion'][:70]}...")


if __name__ == "__main__":
    main()
