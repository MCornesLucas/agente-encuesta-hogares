"""Que `notebook_builder` se mantenga sincronizado con el catálogo real.

Nace de una preocupación real planteada al construir este módulo: ahora
hay tres lugares que tienen que coincidir (el catálogo en
`formularios.py`, el manifiesto de `verificacion_catalogo.py`, y las
plantillas de este módulo) y nada avisaba automáticamente si alguno se
desincronizaba de los otros. Este archivo cierra esa parte del problema
para el número de métrica; `tools/validar_con_datos_reales.py` cierra la
otra parte (que el código que generan las plantillas siga corriendo de
verdad contra datos reales, no solo que exista una entrada para cada
número).

Solo cubre el año base — la comparación entre años se decidió dejarla en
código libre (ver el docstring de notebook_builder.py), así que no hay
nada de eso para probar acá.
"""

import pytest

from encuesta_hogares import notebook_builder as nb
from encuesta_hogares import verificacion_catalogo as vc


def test_generadores_cubre_exactamente_el_catalogo_actual():
    catalogo = set(vc.numeros_del_catalogo())
    generadores = set(nb.GENERADORES)
    faltantes = catalogo - generadores
    sobrantes = generadores - catalogo
    assert not faltantes, (
        f"Hay métricas en el catálogo sin plantilla en notebook_builder.GENERADORES: {sorted(faltantes)} "
        "— agregar un generador _mN, o si la métrica no se presta a mecanizarse, revisar el diseño."
    )
    assert not sobrantes, (
        f"notebook_builder.GENERADORES tiene entradas para métricas que ya no están en el catálogo: "
        f"{sorted(sobrantes)} — se renumeraron o se eliminaron; limpiar la(s) función(es) _mN correspondiente(s)."
    )


def test_todas_las_metricas_generan_markdown_y_codigo():
    for numero in nb.GENERADORES:
        celda = nb.construir_celdas_metrica(numero)
        assert celda.markdown.strip(), numero
        assert celda.codigo.strip(), numero


def test_todas_las_metricas_generan_codigo_python_valido():
    for numero in nb.GENERADORES:
        celda = nb.construir_celdas_metrica(numero)
        compile(celda.codigo, f"<metrica_{numero}>", "exec")


def test_construir_celdas_notebook_arma_la_estructura_completa():
    """Introducción + preparación + un tramo por tema + nota metodológica.

    Antes el informe abría con "Preparación de datos" y las métricas salían
    como una lista plana, sin nada que dijera a qué tema pertenecía cada una.
    """
    celdas = nb.construir_celdas_notebook(
        anio_base=2025,
        metricas=[1, 8, 22],
        incluir_brecha_digital=False,
        incluir_fies=True,
        incluir_empleo=False,
        incluir_seguridad=False,
    )
    cabezas = [c.markdown.split(chr(10))[0] for c in celdas]

    assert cabezas[0].startswith("# "), "el informe tiene que abrir con su título"
    assert "Informe 2025" in cabezas[0]
    assert cabezas[-1] == "## Nota metodológica", "la metodología va al final"

    # Un encabezado de tema antes de cada métrica, y las métricas agrupadas.
    assert cabezas.count("## Brecha Digital") == 1
    assert cabezas.count("## Hogares") == 1
    assert cabezas.count("## Seguridad alimentaria") == 1
    assert cabezas.index("## Brecha Digital") < cabezas.index("### 1. Brecha digital por nivel económico")
    assert cabezas.index("## Hogares") < cabezas.index("### 8. Jefatura de hogar femenina")


def test_las_metricas_se_agrupan_por_tema_no_en_el_orden_elegido():
    """Se eligen desordenadas a propósito: el informe tiene que ordenarlas
    por tema igual."""
    celdas = nb.construir_celdas_notebook(
        anio_base=2025, metricas=[22, 1, 8], incluir_brecha_digital=False,
        incluir_fies=True, incluir_empleo=False, incluir_seguridad=False,
    )
    cabezas = [c.markdown.split(chr(10))[0] for c in celdas]
    orden = [c for c in cabezas if c.startswith("### ")]
    assert orden == [
        "### 1. Brecha digital por nivel económico",
        "### 8. Jefatura de hogar femenina",
        "### 22. Inseguridad alimentaria por quintil de ingreso",
    ]


def test_el_ponderado_no_abre_el_informe_sino_que_cierra_en_metodologia():
    celdas = nb.construir_celdas_notebook(
        anio_base=2025, metricas=[1], incluir_brecha_digital=False,
        incluir_fies=False, incluir_empleo=False, incluir_seguridad=False,
    )
    preparacion = next(c for c in celdas if c.markdown.startswith("## Preparación de datos"))
    assert "ponderador" not in preparacion.markdown.lower(), (
        "la explicación de 'ponderado' es metodología, no la apertura del informe"
    )
    assert "ponderador" in celdas[-1].markdown.lower()


def test_el_panorama_abre_el_bloque_de_brecha_digital_y_no_el_informe():
    """El panorama de conectividad es contexto de ese tema, no del informe
    entero: va después de la presentación del bloque."""
    sin_brecha = nb.construir_celdas_notebook(
        anio_base=2025, metricas=[8], incluir_brecha_digital=False,
        incluir_fies=False, incluir_empleo=False, incluir_seguridad=False,
    )
    con_brecha = nb.construir_celdas_notebook(
        anio_base=2025, metricas=[1], incluir_brecha_digital=True,
        incluir_fies=False, incluir_empleo=False, incluir_seguridad=False,
    )
    assert not any("Panorama general" in c.markdown for c in sin_brecha)

    cabezas = [c.markdown.split(chr(10))[0] for c in con_brecha]
    assert cabezas.index("## Brecha Digital") < cabezas.index("### Panorama general de conectividad en Montevideo")


def test_la_preparacion_de_un_tema_abre_ese_tema_y_no_el_informe():
    """La preparación específica de Empleo y de Seguridad se carga dentro de
    su tema, no arriba de todo.

    Dejarlas arriba ponía un "## Empleo: preparación específica de este
    bloque" entre la preparación general y el primer tema, lejos del
    "## Empleo" al que pertenece. Ninguna métrica de otro bloque usa lo que
    definen, así que se pueden mover (el índice territorial también mira
    empleo, pero se lo carga por su cuenta).
    """
    celdas = nb.construir_celdas_notebook(
        anio_base=2025, metricas=[8, 28, 36], incluir_brecha_digital=False,
        incluir_fies=False, incluir_empleo=True, incluir_seguridad=True,
    )
    cabezas = [c.markdown.split(chr(10))[0] for c in celdas]
    preparaciones = [i for i, c in enumerate(cabezas) if c == "### Preparación de los datos de este tema"]
    assert len(preparaciones) == 2
    for i in preparaciones:
        assert cabezas[i - 1].startswith("## "), "cada preparación va justo debajo del título de su tema"
        assert cabezas[i + 1].startswith("### "), "y antes de la primera métrica del tema"


def test_el_empleo_se_carga_una_sola_vez_aunque_lo_usen_varias_metricas():
    """Hasta la v0.13.6, un informe con las 42 métricas llamaba a
    `load_empleo` cinco veces (preparación del bloque Empleo más una por
    cada métrica del índice territorial, 13, 14 y 15): los 12 archivos
    mensuales se leían y el índice se calculaba de nuevo en cada una.
    Ahora la preparación general lo carga una vez y las demás celdas
    derivan de `empleo_prep`."""
    from encuesta_hogares import verificacion_catalogo as vc

    for metricas in ([13, 14, 15], [28, 29], [13, 28], sorted(vc.MANIFEST)):
        celdas = nb.construir_celdas_notebook(
            anio_base=2025, metricas=metricas, incluir_brecha_digital=True,
            incluir_fies=True, incluir_empleo=True, incluir_seguridad=True,
        )
        codigo = "\n".join(c.codigo for c in celdas)
        assert codigo.count("load_empleo(") == 1, metricas
        assert codigo.count("analysis.indice_desarrollo_territorial(") == (1 if 13 in metricas else 0), metricas
        # Lo que se define antes se usa después: la carga va antes del primer uso.
        assert codigo.index("load_empleo(") < codigo.index("empleo_prep[") if "empleo_prep[" in codigo else True
        assert codigo.index("load_empleo(") < codigo.index("normalizar_departamento(empleo_prep)") if 13 in metricas else True


def test_no_se_carga_empleo_si_no_quedo_ninguna_metrica_de_empleo():
    """Consecuencia buena del cambio anterior: la preparación cuelga del
    tema, así que sin métricas de ese tema no se carga el archivo."""
    celdas = nb.construir_celdas_notebook(
        anio_base=2025, metricas=[8], incluir_brecha_digital=False,
        incluir_fies=False, incluir_empleo=True, incluir_seguridad=True,
    )
    assert not any("load_empleo" in c.codigo for c in celdas)
    assert not any("load_victimizacion" in c.codigo for c in celdas)


# ============================================================================
# celdas_extra: por dónde entran las comparaciones entre años y las métricas
# a medida, que se escriben a mano a propósito.
#
# Antes el agente armaba la lista de celdas él mismo para poder intercalar
# esas celdas, y esa libertad es justo la que hacía que el informe saliera
# distinto en cada corrida. Ahora la estructura la arma la función y el
# agente solo cuelga lo suyo de la métrica que acompaña.
# ============================================================================

def test_las_celdas_extra_van_pegadas_a_su_metrica_dentro_del_bloque():
    comparacion = nb.Celda(markdown="### Comparación 2023 vs 2025", codigo="pass")
    celdas = nb.construir_celdas_notebook(
        anio_base=2025, metricas=[8, 9], incluir_brecha_digital=False,
        incluir_fies=False, incluir_empleo=False, incluir_seguridad=False,
        celdas_extra={8: [comparacion]},
    )
    titulos = [c.markdown.split("\n")[0] for c in celdas]
    posicion = titulos.index("### Comparación 2023 vs 2025")

    # Justo después de la métrica 8 y antes de la 9, no al final del informe.
    assert titulos[posicion - 1].startswith("### 8.")
    assert titulos[posicion + 1].startswith("### 9.")


def test_una_celda_extra_de_una_metrica_no_elegida_es_un_error():
    # Si se dejara pasar, el informe saldría bien formado pero sin la
    # comparación que la persona pidió: un fallo invisible.
    with pytest.raises(ValueError, match="que no se eligieron"):
        nb.construir_celdas_notebook(
            anio_base=2025, metricas=[8], incluir_brecha_digital=False,
            incluir_fies=False, incluir_empleo=False, incluir_seguridad=False,
            celdas_extra={30: [nb.Celda(markdown="### Huérfana")]},
        )


# ============================================================================
# Estructura fija de toda métrica. Nace de un problema real encontrado por
# el dueño del proyecto leyendo un informe generado: las métricas de Empleo
# explicaban con la fórmula del INE qué es la tasa de actividad/empleo/
# desempleo, y otras métricas no explicaban ningún término. La diferencia
# no era una decisión — esas definiciones las escribía el modelo a mano
# durante la corrida, así que salían o no según se acordara.
# ============================================================================

def test_toda_metrica_del_catalogo_tiene_las_cinco_partes_en_orden():
    """Las cinco partes, en este orden exacto (definición del dueño del
    proyecto, v0.13.0):

    a. nombre de la métrica
    b. qué pregunta responde
    c. términos **propios** de la métrica, si corresponde — los del bloque
       ya se explicaron arriba y no se repiten, así que esta parte es la
       única opcional
    d. la gráfica
    e. la explicación académica de por qué esa gráfica, con su referencia
       bibliográfica

    El cambio de orden importa: antes la justificación iba ANTES de la
    gráfica. Ahora primero se ve el dato y después se entiende por qué está
    presentado así, que es como se lee un informe.
    """
    faltantes = []
    for numero in sorted(nb.GENERADORES):
        celda = nb.construir_celdas_metrica(numero)

        # (a) y (b) van en el markdown que precede a la gráfica.
        if not celda.markdown.startswith(f"### {numero}. "):
            faltantes.append(f"  - {numero}: no arranca con el nombre de la métrica")
        if "¿Qué pregunta responde?" not in celda.markdown:
            faltantes.append(f"  - {numero}: no dice qué pregunta responde")
        # (c) es opcional, pero si aparece tiene que ir DESPUÉS de la
        # pregunta y ANTES de la gráfica.
        if "Qué significa cada término" in celda.markdown:
            if celda.markdown.index("¿Qué pregunta responde?") > celda.markdown.index("Qué significa cada término"):
                faltantes.append(f"  - {numero}: los términos van después de la pregunta, no antes")
        # (d) la gráfica.
        if "viz.plot_" not in celda.codigo:
            faltantes.append(f"  - {numero}: no genera ninguna gráfica")
        # (e) la justificación, DESPUÉS de la gráfica.
        if "Por qué esta gráfica:" not in celda.markdown_final:
            faltantes.append(f"  - {numero}: la justificación académica no va después de la gráfica")
        if "Por qué esta gráfica:" in celda.markdown:
            faltantes.append(f"  - {numero}: la justificación quedó ANTES de la gráfica")

    assert not faltantes, (
        "Toda métrica lleva siempre las mismas cinco partes, en orden "
        "(nombre, pregunta, términos propios, gráfica, justificación "
        "académica):\n\n" + "\n".join(faltantes)
    )


def test_los_terminos_del_bloque_no_se_repiten_en_cada_metrica():
    """El caso que motivó el cambio: "índice de desarrollo territorial" se
    explicaba igual en las tres métricas de Territorio."""
    celdas = nb.construir_celdas_notebook(
        anio_base=2025, metricas=[13, 14, 15], incluir_brecha_digital=False,
        incluir_fies=False, incluir_empleo=False, incluir_seguridad=False,
    )
    veces = sum(1 for c in celdas if "Índice de desarrollo territorial**:" in c.markdown)
    assert veces == 1, f"el término se explica {veces} veces; tiene que explicarse una sola, en el bloque"

    bloque = next(c for c in celdas if c.markdown.startswith("## Territorio"))
    assert "Índice de desarrollo territorial**:" in bloque.markdown


def test_un_termino_de_una_sola_metrica_elegida_se_queda_en_la_metrica():
    """Dinámico: si la persona elige una sola métrica de Territorio, no
    tiene sentido explicar el término en una sección aparte."""
    celdas = nb.construir_celdas_notebook(
        anio_base=2025, metricas=[13], incluir_brecha_digital=False,
        incluir_fies=False, incluir_empleo=False, incluir_seguridad=False,
    )
    bloque = next(c for c in celdas if c.markdown.startswith("## Territorio"))
    metrica = next(c for c in celdas if c.markdown.startswith("### 13."))
    assert "Índice de desarrollo territorial**:" not in bloque.markdown
    assert "Índice de desarrollo territorial**:" in metrica.markdown


def test_un_termino_que_cruza_bloques_se_repite_en_cada_uno():
    """Decisión del dueño del proyecto: repetir, para que cada bloque se
    lea solo sin ir a buscar una definición a otra sección."""
    celdas = nb.construir_celdas_notebook(
        anio_base=2025, metricas=[1, 3, 5, 17, 19], incluir_brecha_digital=False,
        incluir_fies=False, incluir_empleo=False, incluir_seguridad=False,
    )
    bloques_con_nivel_economico = [
        c.markdown.split(chr(10))[0] for c in celdas
        if c.markdown.startswith("## ") and "Nivel económico**:" in c.markdown
    ]
    assert bloques_con_nivel_economico == ["## Brecha Digital", "## Vivienda"]


def test_el_informe_emite_todas_las_metricas_elegidas():
    """Ninguna métrica del catálogo puede quedarse fuera del informe.

    Las métricas se emiten recorriendo los bloques, así que una que no
    pertenezca a ninguno desaparecería: el informe saldría entero y sin
    ella, sin ningún aviso.
    """
    todas = sorted(vc.MANIFEST)
    celdas = nb.construir_celdas_notebook(
        anio_base=2025, metricas=todas, incluir_brecha_digital=True,
        incluir_fies=True, incluir_empleo=True, incluir_seguridad=True,
    )
    emitidas = {
        int(c.markdown.split(".")[0].removeprefix("### "))
        for c in celdas
        if c.markdown.startswith("### ") and c.markdown[4:5].isdigit()
    }
    assert emitidas == set(todas), f"quedaron fuera del informe: {sorted(set(todas) - emitidas)}"


def test_una_metrica_sin_bloque_no_se_pierde_en_silencio():
    with pytest.raises(ValueError, match="no pertenecen a ningún bloque"):
        nb.construir_celdas_notebook(
            anio_base=2025, metricas=[999], incluir_brecha_digital=False,
            incluir_fies=False, incluir_empleo=False, incluir_seguridad=False,
        )


def test_toda_metrica_justifica_su_grafica_citando_una_fuente():
    """El mismo criterio que hace cumplir
    `.claude/hooks/_lib_check_notebook_metrica_sin_grafica_o_cita.cjs`, pero del
    lado de Python, que es donde se escriben las justificaciones.

    Nace de que el hook estuvo un tiempo mirando un formato de encabezado
    que este módulo ya no emitía: encontraba cero métricas y pasaba en
    verde. Mientras tanto, dos familias de gráfica ("barras 100% apiladas"
    y "heatmap") quedaron sin cita. Un solo guardián, y en otro lenguaje,
    no alcanzaba.
    """
    autores = ("Cleveland", "McGill", "Tufte", "Knaflic", "Few", "Ware", "Wilke",
               "storytellingwithdata")
    sin_cita = [
        familia for familia, texto in nb._JUSTIFICACION_POR_FAMILIA.items()
        if not any(autor in texto for autor in autores)
    ]
    assert not sin_cita, f"familias de gráfica sin cita: {sin_cita}"


def test_la_pregunta_de_una_metrica_no_repite_su_glosario():
    """La parte b ("¿Qué pregunta responde?") y la parte c (términos) son
    cosas distintas: una es la pregunta, la otra la definición.

    Nace de un caso real encontrado por el dueño del proyecto leyendo el
    informe de 2023: la métrica 3 decía como "pregunta" casi textualmente
    lo mismo que su término del glosario ("no es solo tener o no tener:
    ... sin conexión, solo por celular, o banda ancha fija") — dos veces
    el mismo texto, ninguna pregunta. Habían quedado así ocho métricas.

    El chequeo es mecánico: ninguna secuencia de 6 palabras de la
    descripción puede aparecer también en el glosario de sus propios
    términos. No puede juzgar si la pregunta es buena — eso sigue siendo
    de humanos — pero sí que no sea un duplicado.
    """
    import re

    def palabras(texto):
        return re.sub(r"[*_¿?¡!():—·\-]", " ", texto.lower()).split()

    def ngramas(texto, n=6):
        p = palabras(texto)
        return {tuple(p[i:i + n]) for i in range(len(p) - n + 1)}

    duplicadas = []
    for numero in sorted(nb.GENERADORES):
        _titulo, descripcion = nb._TEXTO_CATALOGO[numero]
        del_glosario = set()
        for termino in nb._TERMINOS_POR_METRICA.get(numero, ()):
            del_glosario |= ngramas(nb._GLOSARIO[termino])
        repetidos = ngramas(descripcion) & del_glosario
        if repetidos:
            ejemplo = " ".join(next(iter(repetidos)))
            duplicadas.append(f"  - {numero}: repite del glosario «{ejemplo}...»")
    assert not duplicadas, (
        "La pregunta de estas métricas repite la definición de su propio "
        "glosario en vez de preguntar algo:\n" + "\n".join(duplicadas)
    )


def test_ningun_codigo_del_catalogo_imprime_un_objeto_crudo_de_pandas():
    """`print(f"...:\\n{algo}")` es el patrón de imprimir el repr de una
    Series/DataFrame en la línea siguiente: en el informe final sale
    "tasa_actividad 16.59 ... dtype: float64", el ruido técnico que
    prohíbe METODOLOGIA.md sección 3.

    Nace de una corrida real de 2023: las métricas 29 y 34 lo hacían, el
    agente lo detectó leyendo el informe generado y lo parchó a mano con
    nbformat — al costo de re-ejecutar el notebook entero (~96 s + ~2 min
    de modelo). Este test evita que el patrón vuelva a entrar al builder.

    En la corrida real de 2025 la métrica 41 volvió a pagar la
    re-ejecución: escribía el mismo patrón pero con el salto de línea
    escapado (`\\n` dentro del f-string generado), y este guardián solo
    buscaba el salto de línea real — pasaba en verde sin mirar ese caso.
    Por eso se buscan las dos formas.
    """
    infractoras = [
        numero for numero in sorted(nb.GENERADORES)
        if ":\n{" in nb.construir_celdas_metrica(numero).codigo
        or ":\\n{" in nb.construir_celdas_metrica(numero).codigo
    ]
    assert not infractoras, (
        f"estas métricas imprimen un objeto crudo de pandas (print de "
        f"`:\\n{{...}}`): {infractoras} — formatear el print, como en _m29/_m34"
    )


def test_ningun_print_interpola_un_resultado_de_analysis_sin_formato():
    """Generalización del guardián de arriba, pedida por el dueño tras la
    corrida 2025: el patrón `:\\n{...}` atrapa el repr multilínea, pero un
    `print(f"... {resultado}")` en línea mete el mismo ruido técnico al
    informe sin pasar por ese patrón. Regla mecánica: todo valor que venga
    de una llamada a `analysis.*` se imprime con format spec (`:.2f`,
    `:+.2f`, ...) — un escalar sin formato es un número sin redondear, y
    una Series sin formato es el repr crudo que prohíbe METODOLOGIA.md
    sección 3."""
    import ast

    infractoras = []
    for numero in sorted(nb.GENERADORES):
        arbol = ast.parse(nb.construir_celdas_metrica(numero).codigo)
        de_analysis = {
            objetivo.id
            for nodo in ast.walk(arbol)
            if isinstance(nodo, ast.Assign)
            and isinstance(nodo.value, ast.Call)
            and isinstance(nodo.value.func, ast.Attribute)
            and isinstance(nodo.value.func.value, ast.Name)
            and nodo.value.func.value.id == "analysis"
            for objetivo in nodo.targets
            if isinstance(objetivo, ast.Name)
        }
        for nodo in ast.walk(arbol):
            es_print = (
                isinstance(nodo, ast.Call)
                and isinstance(nodo.func, ast.Name)
                and nodo.func.id in ("print", "nota")
            )
            if not es_print:
                continue
            for arg in nodo.args:
                if not isinstance(arg, ast.JoinedStr):
                    continue
                for valor in arg.values:
                    if (
                        isinstance(valor, ast.FormattedValue)
                        and isinstance(valor.value, ast.Name)
                        and valor.value.id in de_analysis
                        and valor.format_spec is None
                    ):
                        infractoras.append(f"{numero}: {{{valor.value.id}}}")
    assert not infractoras, (
        f"estas métricas imprimen un resultado de analysis.* sin format spec "
        f"(si es una Series sale el repr crudo; si es un escalar, sin "
        f"redondear): {infractoras} — formatear como en _m19 (:.2f)"
    )


def test_las_edades_que_definen_la_poblacion_estan_en_el_codigo():
    """Generalización de la métrica 6 (corrida 2025): la pregunta definía la
    población con "65 años o más" y la plantilla calculaba sobre todos los
    hogares de Montevideo — el número que prometía la pregunta no aparecía
    en ninguna parte del cálculo, y descubrirlo costó dos re-ejecuciones
    completas del notebook.

    Regla mecánica: toda edad mencionada en el título o la pregunta de una
    métrica tiene que aparecer como número en el código de su plantilla, o
    en el fuente de las funciones declaradas en el MANIFEST (donde el filtro
    puede vivir encapsulado, como el 65 de `pct_unipersonales_mayores`).
    No valida la semántica completa — eso sigue siendo trabajo de la
    revisión del agente — pero cierra la clase "población prometida con un
    número que el cálculo nunca usa" sin pagar una corrida para enterarse.
    """
    import importlib
    import inspect
    import re

    faltantes = []
    for numero in sorted(nb.GENERADORES):
        titulo, descripcion = nb._TEXTO_CATALOGO[numero]
        texto = f"{titulo} {descripcion}"
        edades: set[str] = set()
        for frase in re.findall(r"(?:\d+\s+(?:a|y)\s+)?\d+\s+años?\b", texto):
            edades.update(re.findall(r"\d+", frase))
        if not edades:
            continue
        # Solo la plantilla y las funciones de análisis/preprocesamiento: la
        # visualización queda afuera a propósito — que el título de la
        # gráfica mencione la edad no prueba que el cálculo la use (era
        # exactamente el defecto de la métrica 6).
        fuentes = [nb.construir_celdas_metrica(numero).codigo]
        for referencia in vc.MANIFEST[numero]["funciones"]:
            modulo, funcion = referencia.split(".")
            objeto = getattr(importlib.import_module(f"encuesta_hogares.{modulo}"), funcion)
            fuentes.append(inspect.getsource(objeto))
        todo = "\n".join(fuentes)
        for edad in sorted(edades):
            if not re.search(rf"\b{edad}\b", todo):
                faltantes.append(
                    f"{numero}: la pregunta define la población con «{edad} años» "
                    f"y ese número no aparece en el cálculo"
                )
    assert not faltantes, (
        "La pregunta de estas métricas promete una población que el código "
        "no filtra (la clase del defecto de la métrica 6 en la corrida "
        "2025):\n" + "\n".join(f"  - {f}" for f in faltantes)
    )


def test_ningun_titulo_de_plantilla_excede_el_ancho_verificado_de_la_figura():
    """Gemelo del guardián de títulos de `test_visualization.py`, sobre los
    títulos que las plantillas de este módulo pasan a las gráficas
    (`titulo=`/`title=` dentro del código generado).

    Mismo origen: en la corrida real de 2025, el título de 77 caracteres de
    la métrica 6 salió pegado al borde de la figura de 800px y costó una
    re-ejecución completa acortarlo. El más largo verificado en una revisión
    visual real tiene 65 — de ahí el límite.
    """
    import inspect
    import re

    limite = 65  # ver LARGO_MAXIMO_TITULO_VERIFICADO en test_visualization.py
    fuente = inspect.getsource(nb)
    patron = re.compile(r'\btitle\s*=\s*f?"([^"\n]*)"|\btitulo\s*=\s*f?"([^"\n]*)"')
    largos = sorted(
        t for t in {m.group(1) or m.group(2) for m in patron.finditer(fuente)}
        if len(t) > limite
    )
    assert not largos, (
        f"títulos de plantilla más largos que los {limite} caracteres verificados "
        f"en figuras de 800px (van a salir cortados del informe): {largos} — acortar el título"
    )


def test_toda_metrica_del_catalogo_explica_sus_terminos():
    """Una métrica nueva no puede quedarse sin entrada en el glosario: si
    se agrega al catálogo y se olvida acá, esto falla en vez de generar un
    informe donde esa métrica es la única sin explicar su jerga."""
    del_catalogo = set(nb.GENERADORES)
    con_terminos = set(nb._TERMINOS_POR_METRICA)
    assert del_catalogo - con_terminos == set(), (
        f"Métricas sin términos declarados: {sorted(del_catalogo - con_terminos)}"
    )
    assert con_terminos - del_catalogo == set(), (
        f"_TERMINOS_POR_METRICA tiene métricas que ya no están en el catálogo: "
        f"{sorted(con_terminos - del_catalogo)}"
    )


def test_todos_los_terminos_declarados_existen_en_el_glosario():
    rotos = {
        numero: [t for t in terminos if t not in nb._GLOSARIO]
        for numero, terminos in nb._TERMINOS_POR_METRICA.items()
    }
    rotos = {n: ts for n, ts in rotos.items() if ts}
    assert not rotos, f"Términos declarados que no están en el glosario: {rotos}"


def test_el_glosario_no_tiene_terminos_que_nadie_use():
    usados = {t for terminos in nb._TERMINOS_POR_METRICA.values() for t in terminos}
    sin_usar = set(nb._GLOSARIO) - usados
    assert not sin_usar, (
        f"El glosario define términos que ninguna métrica usa: {sorted(sin_usar)} "
        f"— borrarlos o conectarlos a la métrica que corresponda."
    )


# ============================================================================
# Los componentes del índice territorial y lo que el informe dice de él
# tienen que coincidir. Nace de un defecto real encontrado por el dueño del
# proyecto mirando el heatmap del perfil territorial: el texto prometía
# "pobreza, empleo, precariedad de vivienda y nivel económico" y la gráfica
# mostraba tres columnas — empleo no estaba en el cálculo. Nada lo detectó
# porque los tests verificaban que el índice estuviera entre 0 y 1, no que
# su descripción coincidiera con sus componentes reales.
# ============================================================================

_COMPONENTES_ESPERADOS = ("Pobreza", "Precariedad de vivienda", "Empleo", "Nivel económico")


def test_el_indice_territorial_calcula_los_cuatro_componentes_que_promete():
    codigo = nb._COMPONENTES_TERRITORIO
    for componente in _COMPONENTES_ESPERADOS:
        assert f'"{componente}"' in codigo, (
            f"El índice territorial no calcula «{componente}», pero el catálogo y el "
            f"glosario dicen que sí. Si se saca un componente, hay que sacarlo también "
            f"del texto — no puede decir una cosa y calcular otra."
        )


def test_el_glosario_describe_los_mismos_componentes_que_se_calculan():
    definicion = nb._GLOSARIO["indice_territorial"].lower()
    for termino in ("pobreza", "empleo", "precariedad", "nivel económico"):
        assert termino in definicion, (
            f"El glosario del índice territorial no menciona «{termino}», que sí es "
            f"uno de los componentes calculados."
        )


def test_el_indice_territorial_normaliza_el_departamento_del_empleo():
    """Sin esto el cruce da cero filas y el índice queda vacío en silencio:
    los archivos de Empleo traen "Artigas" y los de Hogares "ARTIGAS".
    Verificado contra los datos reales de 2025 (0 de 19 coincidían)."""
    codigo = nb._COMPONENTES_TERRITORIO
    assert "normalizar_departamento" in codigo, (
        "El componente de empleo del índice territorial se cruza por departamento "
        "sin normalizar — eso deja el índice vacío sin ningún error visible."
    )
    assert "assert len(componentes_territorio) > 1" in codigo, (
        "Falta la red de seguridad que detecta un cruce vacío por departamento."
    )


def test_ninguna_celda_del_catalogo_imprime_por_consola():
    """Regla del dueño (2026-09-09): el texto que acompaña a una celda sale
    con el formato del informe (markdown vía `nota(...)`, números con coma
    decimal y punto de miles), nunca como salida cruda de consola con
    `print` — en el PDF esas líneas aparecían en tipografía de código y con
    separadores de miles en inglés ("23,292")."""
    from encuesta_hogares import verificacion_catalogo as vc

    celdas = nb.construir_celdas_notebook(
        anio_base=2025, metricas=sorted(vc.MANIFEST), incluir_brecha_digital=True,
        incluir_fies=True, incluir_empleo=True, incluir_seguridad=True,
    )
    con_print = [c.markdown.split(chr(10))[0][:50] for c in celdas if "print(" in c.codigo]
    assert con_print == [], con_print
    assert "def nota(" in nb._CABECERA
    # Ningún separador de miles a la inglesa en el texto que se muestra.
    assert not any(":,}" in c.codigo for c in celdas)


def test_toda_preparacion_de_tema_deja_texto_visible():
    """Visto por el dueño en una corrida real: en Territorio, el encabezado
    "Preparación de los datos de este tema" quedaba vacío en el informe sin
    código, porque la celda calculaba el índice pero no mostraba nada. Toda
    celda con ese encabezado tiene que dejar una nota visible."""
    for celda in (nb.celda_preparacion_empleo(2025), nb.celda_preparacion_seguridad(2025), nb.celda_preparacion_territorio()):
        assert celda.markdown == "### Preparación de los datos de este tema"
        assert "nota(" in celda.codigo, celda.markdown


def test_toda_descripcion_del_catalogo_es_una_pregunta():
    """Regla del dueño (2026-09-09): la celda de cada métrica presenta la
    descripción como «¿Qué pregunta responde?», así que el texto tiene que
    ser una pregunta — 30 de las 42 estaban en afirmativo ("compara el
    acceso...", "cuántos hogares son...") y en el informe se leían como
    respuestas. Se admite una frase aclaratoria después de la pregunta."""
    afirmativas = [
        (numero, descripcion) for numero, (_titulo, descripcion) in sorted(nb._TEXTO_CATALOGO.items())
        if not (descripcion.strip().startswith("¿") and "?" in descripcion)
    ]
    assert afirmativas == [], afirmativas


# ============================================================================
# El estrato socioeconómico del INE existe solo para Montevideo. Caso real
# (corrida 2024): la métrica 17 se calculaba sobre `hogares_cond` (todo el
# país) y mostraba una barra «6-No Definido» con el 43,7% de precariedad,
# que eran los 14.416 hogares del interior; el resumen decía «55,7% de los
# hogares del nivel económico bajo» sin acotar a Montevideo.
# ============================================================================

_MARCOS_DE_MONTEVIDEO = ("hogares_mdeo", "hogares_ext", "hogares_ext_con_jefe", "hogares_jefe_mayor",
                         "hogares_mdeo_hacinamiento", "hogares_cond_mdeo")


def test_todo_corte_por_nivel_economico_se_calcula_sobre_hogares_de_montevideo():
    import re

    fuera = []
    for numero in sorted(nb.GENERADORES):
        codigo = nb.construir_celdas_metrica(numero).codigo
        # Solo las funciones «_por»: reciben el marco de hogares sin agrupar y
        # el criterio; las que reciben una tabla ya agregada (diferencia entre
        # categorías) no eligen población.
        for marco in re.findall(r"analysis\.\w+_por\(\s*(\w+),\s*\"nivel_economico\"", codigo):
            if marco not in _MARCOS_DE_MONTEVIDEO:
                fuera.append(f"{numero}: agrupa {marco} por nivel económico")
    assert fuera == [], (
        "El estrato del INE solo existe para Montevideo; en el interior todo hogar queda "
        "«6-No Definido» y aparece como una barra más:\n" + "\n".join(fuera)
    )
    assert "hogares_cond_mdeo = hogares_cond.loc[" in nb.celda_preparacion_datos(2025, incluir_fies=False).codigo


def test_las_metricas_por_nivel_economico_de_vivienda_dicen_montevideo():
    for numero in (17, 19):
        titulo, descripcion = nb._TEXTO_CATALOGO[numero]
        assert "Montevideo" in descripcion, (numero, descripcion)
        assert "Montevideo" in nb._RESUMEN_POR_METRICA[numero], numero
    assert "Montevideo" in nb._GLOSARIO["nivel_economico"]


# ============================================================================
# Victimización es un evento raro: lo que sostiene cada porcentaje son los
# casos, no las personas encuestadas. Caso real (2024): 17 de 19
# departamentos con menos de 30 víctimas (Cerro Largo: 0 sobre 694) y el
# resumen decía «va de 0,0% (Cerro Largo) a 7,7% (Treinta y Tres)».
# ============================================================================

def test_la_victimizacion_por_departamento_marca_los_departamentos_con_pocos_casos():
    codigo = nb.construir_celdas_metrica(38).codigo
    assert 'grupos_con_pocos_casos(victimizacion_prep, "departamento", "victimizado_algun_delito")' in codigo
    assert "poco_confiables=list(pocos_casos_depto.index)" in codigo
    assert "victimizacion_depto_confiable" in codigo and "nota(" in codigo
    frase = nb._RESUMEN_POR_METRICA[38]
    assert "victimizacion_depto_confiable" in frase and "pocos_casos_depto" in frase
    compile(frase, "resumen_38", "eval")


def test_las_tasas_entre_victimas_avisan_si_un_delito_tiene_pocas_victimas():
    for numero in (39, 40, 42):
        codigo = nb.construir_celdas_metrica(numero).codigo
        assert 'grupos_con_muestra_chica(victimizados' in codigo, numero
        assert "nota(" in codigo, numero


def test_las_frases_del_resumen_no_anidan_parentesis_ni_dicen_n_de_los_n():
    """Del PDF real de 2024: «(generación silenciosa (hasta 1945))» y «En 5
    de los 5 tipos de delito»."""
    import pandas as pd

    from encuesta_hogares import resumen as res

    tabla = pd.DataFrame({"cohorte": ["Generación silenciosa (hasta 1945)", "Generación X (1965-1980)"], "pct": [81.2, 92.8]})
    frase = res.brecha(tabla, "cohorte", "pct", "El acceso a internet")
    assert "((" not in frase and "(generación silenciosa, hasta 1945)" in frase
    assert res.en_cuantos(5, 5, "tipos de delito") == "En los 5 tipos de delito"
    assert res.en_cuantos(3, 5, "tipos de delito") == "En 3 de los 5 tipos de delito"
    assert res.en_cuantos(0, 5, "tipos de delito") == "En ninguno de los 5 tipos de delito"
    assert res.nombre_sector("Hogares") == "hogares (servicio doméstico)"
    assert res.nombre_sector("Formal") == "formal"
    assert res.etiqueta("TREINTA Y TRES") == "Treinta y Tres"
    assert res.nombre_propio("RÍO NEGRO") == "Río Negro"
    assert res.nombre_propio("Treinta y Tres") == "Treinta y Tres"
    assert "sector_formalidad" in nb._TERMINOS_POR_METRICA[35]
