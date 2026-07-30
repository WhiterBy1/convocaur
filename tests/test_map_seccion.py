from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from convocaur.nlp.map_seccion import mapear_seccion, seleccionar_secciones_p0


def test_mapear_seccion_reconoce_titulos_reales():
    assert mapear_seccion("OBJETIVOS") == "objetivo"
    assert mapear_seccion("MECANISMOS DE PARTICIPACIÓN") == "dirigida_a"
    assert mapear_seccion("MECANISMOS DE PARTICIPACION") == "dirigida_a"
    assert mapear_seccion("DURACIÓN Y FINANCIACIÓN") == "financiacion"
    assert mapear_seccion("CRITERIOS DE EVALUACIÓN") == "criterios"


def test_mapear_seccion_reconoce_sinonimos_detectados_en_auditoria():
    """OBJETO (conv. 960/964) y TEMÁTICAS / EJES TEMÁTICOS (conv. 24, 25,
    936, 938) son títulos reales que no coincidían con ningún patrón antes
    de esta auditoría, dejando esas claves vacías aunque la sección sí
    existía en el TdR."""
    assert mapear_seccion("OBJETO") == "objetivo"
    assert mapear_seccion("TEMÁTICAS") == "lineas_tematicas"
    assert mapear_seccion("EJES TEMÁTICOS") == "lineas_tematicas"


def test_no_hijack_lineas_tematicas_por_demandas_territoriales():
    """DEMANDAS TERRITORIALES suele aparecer antes que LÍNEAS TEMÁTICAS en la
    plantilla SGR/Minciencias. Si el regex de lineas_tematicas la absorbiera,
    seleccionar_secciones_p0 (primera coincidencia gana) le robaría la clave
    a la sección real y rica en contenido. Ver convocatoria 48 (regresión
    detectada: n_lineas 18 -> 1) antes de este fix."""
    secciones = [
        {"titulo": "DEMANDAS TERRITORIALES", "titulo_norm": "DEMANDAS TERRITORIALES", "texto": "Reto genérico del departamento."},
        {"titulo": "LÍNEAS TEMÁTICAS", "titulo_norm": "LÍNEAS TEMÁTICAS", "texto": "5.1.1 Línea específica con varios subnumerales."},
    ]
    p0 = seleccionar_secciones_p0(secciones)
    assert p0["lineas_tematicas"]["titulo"] == "LÍNEAS TEMÁTICAS"


def test_no_hijack_criterios_por_procedimiento_evaluacion():
    secciones = [
        {"titulo": "PROCEDIMIENTO DE EVALUACIÓN", "titulo_norm": "PROCEDIMIENTO DE EVALUACIÓN", "texto": "Pasos del proceso."},
        {"titulo": "CRITERIOS DE EVALUACIÓN", "titulo_norm": "CRITERIOS DE EVALUACIÓN", "texto": "Puntajes y ponderaciones."},
    ]
    p0 = seleccionar_secciones_p0(secciones)
    assert p0["criterios"]["titulo"] == "CRITERIOS DE EVALUACIÓN"


def test_no_hijack_financiacion_por_cronograma():
    secciones = [
        {"titulo": "CRONOGRAMA", "titulo_norm": "CRONOGRAMA", "texto": "Fechas del proceso."},
        {"titulo": "DURACIÓN Y FINANCIACIÓN", "titulo_norm": "DURACIÓN Y FINANCIACIÓN", "texto": "Monto y plazos del proyecto."},
    ]
    p0 = seleccionar_secciones_p0(secciones)
    assert p0["financiacion"]["titulo"] == "DURACIÓN Y FINANCIACIÓN"
