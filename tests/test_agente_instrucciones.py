"""Chequeos estructurales sobre .claude/instrucciones/encuesta-hogares.md.

No valida contenido (eso lo hace un humano leyéndolo) - valida que la
estructura no se rompa por una edición futura, como pasó una vez: el paso
3.5 quedó físicamente después del paso 4 en el archivo, aunque el texto
decía "antes del paso 4". Un test no puede evitar una mala instrucción,
pero sí puede evitar que el orden de los pasos quede contradictorio.
"""

import re
from pathlib import Path

AGENTE_MD = Path(__file__).resolve().parents[1] / ".claude" / "instrucciones" / "encuesta-hogares.md"


def _pasos_en_orden_de_aparicion() -> list[float]:
    texto = AGENTE_MD.read_text(encoding="utf-8")
    numeros = re.findall(r"^### (\d+(?:\.\d+)?)\. ", texto, flags=re.MULTILINE)
    return [float(n) for n in numeros]


def test_el_archivo_del_agente_existe():
    assert AGENTE_MD.exists(), f"No se encontró {AGENTE_MD}"


def test_los_pasos_aparecen_en_orden_numerico_ascendente():
    pasos = _pasos_en_orden_de_aparicion()
    assert pasos, "No se encontró ningún paso con el patrón '### N. ...' en el archivo"
    assert pasos == sorted(pasos), (
        f"Los pasos no están en orden ascendente en el archivo: {pasos}. "
        "Esto es exactamente el bug que hizo que una corrida real se saltara "
        "el formulario de áreas y se fuera a explorar código - revisá el "
        "orden físico de las secciones '### N. Título', no solo el texto."
    )


def test_el_paso_de_bienvenida_es_el_primero():
    pasos = _pasos_en_orden_de_aparicion()
    assert pasos[0] == 1.0, (
        "El paso 1 (bienvenida) tiene que ser la primera sección numerada "
        "del archivo - es la regla innegociable de todo el flujo."
    )


def test_la_curacion_del_catalogo_tiene_compuerta_previa():
    texto = AGENTE_MD.read_text(encoding="utf-8")
    seccion = texto.split("## Curación del catálogo")[-1]
    assert "Compuerta previa" in seccion, (
        "La sección de curación del catálogo perdió su compuerta de "
        "calidad (punto 0: confirmación explícita del dueño del proyecto "
        "sobre revisión metodológica, validación con datos reales y "
        "archivos a tocar, antes de escribir nada permanente). No basta "
        "con el pedido de 'agregá esta métrica' - eso autoriza la "
        "intención, la compuerta es la revisión técnica antes de "
        "ejecutar."
    )


def test_el_nombre_del_notebook_esta_atado_al_anio_sin_variantes():
    texto = AGENTE_MD.read_text(encoding="utf-8")
    assert "notebooks/Informe_ECH_{año}.ipynb" in texto, (
        "La regla de que el notebook se llama siempre "
        "'notebooks/Informe_ECH_{año}.ipynb', sin sufijos ni variantes, "
        "desapareció del archivo. Es lo que evita que dos años choquen "
        "entre sí y que el respaldo automático (entrega.py) se dispare "
        "solo cuando de verdad se repite el mismo año."
    )


def test_la_pantalla_final_ramifica_por_nuevo_informe():
    texto = AGENTE_MD.read_text(encoding="utf-8")
    assert '"nuevo_informe"' in texto, (
        "La instrucción de ramificar según la respuesta de "
        "mostrar_finalizacion() ('terminar' vs 'nuevo_informe', volviendo "
        "al paso 1) desapareció del archivo."
    )


def test_maneja_la_salida_anticipada_del_flujo():
    texto = AGENTE_MD.read_text(encoding="utf-8")
    assert '"salir_del_flujo"' in texto, (
        "La instrucción de revisar respuesta.get('salir_del_flujo') después "
        "de cada mostrar_formulario() desapareció del archivo - sin eso, el "
        "agente sigue con el flujo (o queda esperando el timeout) aunque la "
        "persona haya pedido salir explícitamente."
    )


def test_prohibe_correr_bash_en_segundo_plano():
    texto = AGENTE_MD.read_text(encoding="utf-8")
    assert "run_in_background: true" in texto, (
        "La regla de no correr Bash con run_in_background desapareció del "
        "archivo. Nace de un incidente real: correr mostrar_finalizacion() "
        "en segundo plano llevó a inventar un comando powershell no "
        "permitido para leer el resultado, mostrándole al usuario un "
        "prompt de aprobación de terminal."
    )


# ============================================================================
# Modelo fijado. Sin `--model` en abrir_agente.bat la sesión toma el default
# de la cuenta: el modelo con el que se genera un informe podía cambiar sin
# que nadie tocara el proyecto. Para algo que se publica con respaldo
# metodológico, esa variabilidad silenciosa no sirve — y como los cálculos
# libres (comparación entre años y métricas a medida) los escribe el modelo
# en cada corrida, el modelo es parte de la reproducibilidad del resultado.
# ============================================================================

_BAT_ARRANQUE = Path(__file__).resolve().parents[1] / "abrir_agente.bat"


def _modelo_del_frontmatter() -> str | None:
    """El modelo declarado en las instrucciones ("Modelo fijado para las
    corridas: `claude-opus-5`"). Ya no hay subagente ni frontmatter: la
    sesión principal corre con el modelo que fija abrir_agente.bat, y las
    instrucciones lo declaran para que el test los mantenga iguales."""
    texto = AGENTE_MD.read_text(encoding="utf-8")
    encontrado = re.search(r"Modelo fijado para las corridas: `([^`]+)`", texto)
    return encontrado.group(1) if encontrado else None


def test_las_instrucciones_declaran_el_modelo_con_id_completo():
    modelo = _modelo_del_frontmatter()
    assert modelo is not None, (
        ".claude/instrucciones/encuesta-hogares.md no declara el modelo fijado "
        "(«Modelo fijado para las corridas: `...`»): sin eso nada ata el modelo "
        "de abrir_agente.bat a las instrucciones y el informe deja de ser reproducible."
    )
    assert modelo not in ("opus", "sonnet", "haiku", "fable", "inherit"), (
        f"`model: {modelo}` es un alias — se mueve solo a la próxima generación "
        "del modelo. Este proyecto pide el id completo (ej. claude-opus-5) para "
        "que ese cambio sea una decisión explícita, con validación de por medio."
    )


def test_el_bat_de_arranque_usa_el_mismo_modelo_que_las_instrucciones():
    """Si los dos se despistan, la corrida usa un modelo distinto del que
    las instrucciones declaran, sin que nadie lo note."""
    modelo = _modelo_del_frontmatter()
    bat = _BAT_ARRANQUE.read_text(encoding="latin-1")
    assert f"--model {modelo}" in bat, (
        f"abrir_agente.bat no fija el mismo modelo que declaran las instrucciones ({modelo}). "
        "Al actualizar uno hay que actualizar el otro."
    )


# ============================================================================
# Los números de métrica que citan las instrucciones tienen que existir en el
# catálogo real. Nace de un desfasaje que pasó de verdad: al renumerar el
# catálogo de 43 a 42 métricas (v0.9.0) se actualizó el código y los tests,
# pero NO este archivo — quedó citando "métricas 37-43" cuando el catálogo
# llega hasta 42, y "métrica 36" para algo que pasó a ser la 35. El agente
# lee estas instrucciones, así que un número corrido lo manda a la métrica
# equivocada.
# ============================================================================

def test_las_instrucciones_no_citan_metricas_fuera_del_catalogo():
    from encuesta_hogares import verificacion_catalogo as vc

    catalogo = set(vc.numeros_del_catalogo())
    maximo = max(catalogo)
    texto = AGENTE_MD.read_text(encoding="utf-8")

    citados = set()
    for rango in re.findall(r"métricas (\d+)-(\d+)\)", texto):
        citados.update({int(rango[0]), int(rango[1])})
    citados.update(int(n) for n in re.findall(r"la métrica (\d+)", texto))

    fuera = sorted(n for n in citados if n not in catalogo)
    assert not fuera, (
        f"Las instrucciones del agente citan métricas que no existen en el "
        f"catálogo (que va de 1 a {maximo}): {fuera} — quedaron con la "
        f"numeración vieja después de renumerar."
    )


def test_la_regla_de_registrar_reejecuciones_existe_y_tiene_su_contraparte():
    """El paso 7 obliga a registrar `reejecucion_notebook` con motivo antes
    de re-ejecutar el notebook, y `bitacora.resumir_sesion` tiene que
    saber mostrarlo.

    Nace de una corrida real: el notebook corrió dos veces (~4 min, 23% de
    la corrida) y la bitácora no decía por qué. Este test ata las dos
    puntas — si alguien borra la instrucción o el campo del resumen, la
    otra mitad queda muda sin que nadie lo note.
    """
    from encuesta_hogares import bitacora

    assert "reejecucion_notebook" in AGENTE_MD.read_text(encoding="utf-8"), (
        "el paso 7 tiene que exigir registrar el motivo antes de re-ejecutar"
    )
    resumen = bitacora.resumir_sesion([
        {"timestamp": "2026-08-17T00:00:00+00:00", "tipo": "reejecucion_notebook", "motivo": "prueba"},
    ])
    assert resumen.reejecuciones and resumen.reejecuciones[0]["motivo"] == "prueba"


def test_la_cantidad_de_metricas_que_dice_la_documentacion_es_la_real():
    """"Las 43 métricas fijas del catálogo" decían las instrucciones y el
    README, cuando son 42 desde que se sacó TV cable.

    Es una frase de prosa que nadie verificaba, igual que las referencias a
    secciones inexistentes. Sale barato atarla al catálogo real.
    """
    from encuesta_hogares import verificacion_catalogo as vc

    reales = len(vc.MANIFEST)
    raiz = AGENTE_MD.parents[2]
    equivocados = []
    for archivo in (AGENTE_MD, raiz / "README.md", raiz / "tools" / "validar_con_datos_reales.py"):
        for cantidad in re.findall(r"las (\d+) métricas (?:fijas )?del catálogo", archivo.read_text(encoding="utf-8")):
            if int(cantidad) != reales:
                equivocados.append(f"{archivo.name}: dice {cantidad}, son {reales}")
    assert not equivocados, "\n".join(equivocados)


def test_los_pasos_5_y_8_usan_el_pipeline_y_no_scripts_sueltos():
    """Desde la v0.14.0 el informe se genera con dos comandos del paquete
    (`generar_informe construir` y `generar_informe entregar`): el modelo
    no escribe el script que arma el notebook, no invoca `nbconvert` por
    su cuenta y no vuelve a ejecutar el notebook para agregar el resumen.
    Si las instrucciones vuelven al camino manual, esto lo delata."""
    texto = AGENTE_MD.read_text(encoding="utf-8")
    assert "encuesta_hogares.generar_informe construir --anio" in texto
    assert "encuesta_hogares.generar_informe entregar --anio" in texto
    assert "_RESUMEN_POR_METRICA" in texto, "el resumen lo arma el notebook, no el modelo"
    paso_5 = texto.split("### 5. ")[1].split("### Las cinco partes")[0]
    assert "paso5_checkpoint" not in paso_5 and "medir_comando" not in paso_5
