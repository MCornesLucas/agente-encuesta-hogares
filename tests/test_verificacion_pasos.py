from encuesta_hogares import verificacion_pasos as vp


def test_encuentra_varias_referencias_reales_a_pasos_en_formularios():
    referencias = vp.referencias_a_pasos_en_formularios()
    # Confirma que el parseo funciona contra el archivo real, no solo
    # contra un caso sintético - si estas funciones cambian de nombre,
    # actualizar la lista.
    for esperada in ("plantilla_bienvenida", "plantilla_catalogo", "plantilla_revision"):
        assert esperada in referencias, f"no se encontró referencia a paso en '{esperada}'"


def test_ninguna_referencia_a_paso_en_formularios_quedo_desactualizada():
    desactualizadas = vp.referencias_a_pasos_inexistentes()
    detalle = "\n".join(f"  - {funcion}: dice 'Paso {paso}'" for funcion, paso in desactualizadas.items())
    assert not desactualizadas, (
        "Hay docstrings en formularios.py que mencionan un número de paso "
        "que ya no existe en .claude/instrucciones/encuesta-hogares.md — "
        "revisar a qué paso corresponde de verdad la función y corregir "
        "el docstring:\n\n" + detalle
    )
