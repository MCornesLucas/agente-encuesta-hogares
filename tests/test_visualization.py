"""Tests de regresión para bugs de gráficas ya encontrados y corregidos.

No es un test exhaustivo de cada función de `visualization.py` (son
muchas y la mayoría son variaciones directas de `analysis.py`, ya
cubierto). Este caso puntual sí se testea porque ya falló una vez en un
informe real: un `px.scatter` no ancla el eje en cero solo (a diferencia
de un `px.bar`), así que si alguien edita esta función sin saberlo, puede
volver a exagerar visualmente las diferencias sin que nada lo note.
"""

import pandas as pd

from encuesta_hogares import visualization as viz


# ============================================================================
# Hogares y Brecha Digital: funciones nuevas, sin ninguna corrida real
# todavía - smoke tests simples (corren sin error, devuelven una figura) en
# vez de los tests de regresión de arriba, que existen para bugs ya vistos.
# ============================================================================

def test_plot_pct_pobres_indigentes_no_falla():
    fig = viz.plot_pct_pobres_indigentes({"pct_pobres": 5.3, "pct_indigentes": 0.2})
    assert fig is not None


def test_plot_tasa_jefatura_femenina_no_falla():
    fig = viz.plot_tasa_jefatura_femenina({"pct_jefatura_femenina": 42.0, "total_hogares": 100})
    assert fig is not None


def test_plot_tipos_hogar_no_falla():
    df = pd.DataFrame({"tipo_hogar": ["Nuclear", "Unipersonal"], "pct_hogares": [60.0, 40.0]})
    fig = viz.plot_tipos_hogar(df)
    assert fig is not None


def test_plot_hacinamiento_por_no_falla():
    df = pd.DataFrame({"nivel_economico": ["1-Bajo", "5-Alto"], "pct_hacinamiento": [15.0, 2.0]})
    fig = viz.plot_hacinamiento_por(df, "nivel económico")
    assert fig is not None


def test_plot_razon_dependencia_por_no_falla():
    df = pd.DataFrame({"departamento": ["MONTEVIDEO", "SALTO"], "razon_dependencia": [45.0, 55.0]})
    fig = viz.plot_razon_dependencia_por(df, "departamento")
    assert fig is not None


def test_plot_pct_unipersonales_mayores_no_falla():
    fig = viz.plot_pct_unipersonales_mayores({"pct_unipersonales_mayores": 60.0, "total_unipersonales": 50})
    assert fig is not None


def test_plot_brecha_digital_por_cohorte_no_falla():
    df = pd.DataFrame(
        {
            "cohorte": ["Millennials (1981-1996)", "Baby boomers (1946-1964)"],
            "tecnologia": ["Internet", "Internet"],
            "pct_penetracion": [90.0, 60.0],
        }
    )
    fig = viz.plot_brecha_digital_por_cohorte(df)
    assert fig is not None


def test_plot_brecha_digital_por_jefatura_no_falla():
    df = pd.DataFrame(
        {
            "jefe_sexo": ["Hombre", "Mujer"],
            "tecnologia": ["Internet", "Internet"],
            "pct_penetracion": [80.0, 78.0],
        }
    )
    fig = viz.plot_brecha_digital_por_jefatura(df)
    assert fig is not None


def test_plot_calidad_conexion_por_no_falla():
    df = pd.DataFrame(
        {"Sin conexión": [10.0, 2.0], "Solo móvil": [30.0, 8.0], "Banda ancha fija": [60.0, 90.0]},
        index=pd.Index(["1-Bajo", "5-Alto"], name="nivel_economico"),
    )
    fig = viz.plot_calidad_conexion_por(df, "nivel económico")
    assert fig is not None


def test_plot_composicion_categorica_no_falla():
    df = pd.DataFrame(
        {"Empleado": [70.0, 50.0], "Cuentapropista": [30.0, 50.0]},
        index=pd.Index(["Formal", "Informal"], name="sector"),
    )
    fig = viz.plot_composicion_categorica(df, "Situación ocupacional por sector", "Sector")
    assert fig is not None


def test_plot_indice_acceso_digital_por_no_falla():
    df = pd.DataFrame({"nivel_economico": ["1-Bajo", "5-Alto"], "indice_promedio": [1.5, 3.5]})
    fig = viz.plot_indice_acceso_digital_por(df, "nivel económico")
    assert fig is not None


def test_plot_adopcion_tablet_ibirapita_no_falla():
    df = pd.DataFrame({"jefe_es_mayor": [True, False], "pct_con_tablet": [25.0, 1.0]})
    fig = viz.plot_adopcion_tablet_ibirapita(df, "jefe es mayor")
    assert fig is not None


def test_plot_tasas_por_anio_usa_eje_x_numerico_con_los_anios_reales():
    tabla = pd.DataFrame(
        {
            "anio": [2019, 2024, 2025],
            "tasa_actividad": [62.0, 64.28, 65.0],
            "tasa_empleo": [58.0, 59.02, 60.0],
            "tasa_desempleo": [6.5, 8.18, 7.5],
        }
    )
    fig = viz.plot_tasas_por_anio(tabla)
    # Eje numerico real (no categorico) - 2019->2024 tiene que quedar mas
    # separado visualmente que 2024->2025, no parejo espaciado.
    assert fig.layout.xaxis.type == "linear"
    assert list(fig.layout.xaxis.tickvals) == [2019, 2024, 2025]
    # 3 series (actividad, empleo, desempleo), cada una con marcadores.
    assert len(fig.data) == 3
    assert all(trace.mode == "lines+markers" for trace in fig.data)


def test_plot_serie_por_anio_con_una_sola_serie():
    # Caso simple: una métrica de un solo número por año (ej. pobreza),
    # comparando 3 años no consecutivos.
    tabla = pd.DataFrame({"anio": [2019, 2024, 2025], "valor": [8.14, 12.99, 14.14]})
    fig = viz.plot_serie_por_anio(tabla, titulo="Pobreza por año", ylabel="% (ponderado)")
    assert fig.layout.xaxis.type == "linear"
    assert list(fig.layout.xaxis.tickvals) == [2019, 2024, 2025]
    assert len(fig.data) == 1
    assert fig.data[0].mode == "lines+markers"


def test_plot_serie_por_anio_con_varias_series_y_etiquetas():
    tabla = pd.DataFrame(
        {
            "anio": [2019, 2024],
            "jefatura_hombre": [53.43, 44.14],
            "jefatura_mujer": [46.57, 55.86],
        }
    )
    fig = viz.plot_serie_por_anio(
        tabla,
        etiquetas={"jefatura_hombre": "Hombre", "jefatura_mujer": "Mujer"},
        titulo="Jefatura por sexo",
    )
    assert len(fig.data) == 2
    nombres = {trace.name for trace in fig.data}
    assert nombres == {"Hombre", "Mujer"}


def test_plot_tasa_mensual_promedio_por_no_falla_y_es_horizontal():
    df = pd.DataFrame({"departamento": ["MONTEVIDEO", "TREINTA Y TRES"], "pct_promedio": [7.5, 9.2]})
    fig = viz.plot_tasa_mensual_promedio_por(df, "departamento", "Desempleo por departamento")
    assert fig is not None
    assert fig.data[0].orientation == "h"


def test_plot_dumbbell_no_falla_con_una_sola_categoria():
    fig = viz.plot_dumbbell(
        categorias=["FIES"],
        valores_a=[12.0],
        valores_b=[45.0],
        nombre_a="Quintil 1 (más pobre)",
        nombre_b="Quintil 5 (más rico)",
        titulo="Inseguridad alimentaria: quintil 1 vs. quintil 5",
    )
    assert fig is not None


def test_plot_dumbbell_ancla_el_eje_x_en_cero_con_varias_categorias():
    fig = viz.plot_dumbbell(
        categorias=["Hurto", "Rapiña", "Copamiento"],
        valores_a=[70.0, 55.0, 40.0],
        valores_b=[20.0, 35.0, 30.0],
        nombre_a="Comunicación informal",
        nombre_b="Denuncia formal",
        titulo="Brecha entre comunicación informal y denuncia formal",
    )
    assert fig.layout.xaxis.range[0] == 0
    # una línea + dos series de marcadores
    assert len(fig.data) == 3


def test_plot_precariedad_estructural_no_falla():
    fig = viz.plot_precariedad_estructural({"pct_con_carencia": 35.0, "total_hogares": 100, "hogares_con_carencia": 35})
    assert fig is not None


def test_plot_precariedad_estructural_por_es_horizontal():
    df = pd.DataFrame({"departamento": ["MONTEVIDEO", "SALTO"], "pct_precariedad": [20.0, 45.0]})
    fig = viz.plot_precariedad_estructural_por(df, "departamento")
    assert fig.data[0].orientation == "h"


def test_plot_carencias_estructurales_mas_frecuentes_no_falla():
    df = pd.DataFrame({"carencia": ["Goteras en techos", "Se inunda cuando llueve"], "pct_hogares": [40.0, 15.0]})
    fig = viz.plot_carencias_estructurales_mas_frecuentes(df)
    assert fig is not None


def test_plot_indice_desarrollo_territorial_ancla_el_eje_x_en_0_1():
    resultado = pd.DataFrame(
        {"pct_pobreza": [1.0, 0.0], "tasa_empleo": [0.0, 1.0], "indice": [0.5, 0.5]},
        index=pd.Index(["MONTEVIDEO", "SALTO"], name="departamento"),
    )
    fig = viz.plot_indice_desarrollo_territorial(resultado)
    assert fig.layout.xaxis.range[0] == 0


def test_plot_perfil_territorial_no_falla():
    resultado = pd.DataFrame(
        {"pct_pobreza": [1.0, 0.0], "tasa_empleo": [0.0, 1.0], "indice": [0.5, 0.5]},
        index=pd.Index(["MONTEVIDEO", "SALTO"], name="departamento"),
    )
    fig = viz.plot_perfil_territorial(resultado)
    assert fig is not None


# ============================================================================
# Guardián de clase: barras horizontales con etiqueta afuera SIEMPRE llevan
# margen a la derecha.
#
# El mismo defecto (la etiqueta de la barra más larga cortada por el borde)
# apareció en TRES corridas reales distintas, en seis funciones, de a dos
# por vez: plot_pct_por y plot_tasa_mensual_promedio_por primero,
# plot_precariedad_estructural_por y plot_carencias_estructurales_mas_
# frecuentes después, y plot_tipos_hogar y plot_razon_dependencia_por al
# final — cada una descubierta con datos reales, parchada en el notebook, y
# re-ejecutando el informe entero (~2 min por vez). Arreglarlo función por
# función garantiza que la séptima vuelva a costar una re-ejecución: esto
# corta la clase entera, incluida cualquier función futura.
# ============================================================================

def test_toda_barra_horizontal_con_etiqueta_afuera_fija_su_margen_derecho():
    import ast
    import inspect

    fuente = inspect.getsource(viz)
    arbol = ast.parse(fuente)
    sin_margen = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.FunctionDef) or not nodo.name.startswith("plot_"):
            continue
        cuerpo = ast.get_source_segment(fuente, nodo) or ""
        es_horizontal = 'orientation="h"' in cuerpo or "orientation='h'" in cuerpo
        etiqueta_afuera = '"outside"' in cuerpo or "'outside'" in cuerpo
        if es_horizontal and etiqueta_afuera and "xaxis_range" not in cuerpo:
            sin_margen.append(nodo.name)
    assert not sin_margen, (
        f"barras horizontales con etiqueta afuera y sin margen derecho "
        f"(la etiqueta más larga va a salir cortada del informe): {sin_margen} "
        f"— agregar xaxis_range=[0, maximo * 1.15] como en plot_tipos_hogar"
    )


# ============================================================================
# Guardián de clase: ningún título literal más largo que lo ya verificado en
# las figuras de 800px.
#
# En la corrida real de 2025 un título de 77 caracteres (métrica 6) salió
# pegado al borde derecho de la figura — la variante "título" del mismo
# defecto de etiqueta cortada de arriba — y costó una re-ejecución completa
# del notebook descubrirlo y acortarlo. El título más largo que pasó una
# revisión visual real tiene 65 caracteres: todo lo que se pase de ahí es
# territorio no verificado y se acorta antes de entrar, no en la corrida.
# ============================================================================

LARGO_MAXIMO_TITULO_VERIFICADO = 65


def test_ningun_titulo_literal_excede_el_ancho_verificado_de_la_figura():
    import inspect
    import re

    assert viz.LARGO_MAXIMO_TITULO == LARGO_MAXIMO_TITULO_VERIFICADO
    fuente = inspect.getsource(viz)
    patron = re.compile(r'\btitle\s*=\s*f?"([^"\n]*)"')
    largos = sorted(t for t in set(patron.findall(fuente)) if len(t) > LARGO_MAXIMO_TITULO_VERIFICADO)
    assert not largos, (
        f"títulos más largos que los {LARGO_MAXIMO_TITULO_VERIFICADO} caracteres verificados "
        f"en figuras de 800px (van a salir cortados del informe): {largos} — acortar el título"
    )


# ============================================================================
# Guardianes de clase nacidos de la revisión del PDF real de 2024 (ver la
# nota «Convenciones comunes» al inicio de visualization.py): cifras con el
# formato del informe, color solo cuando significa algo, departamentos
# legibles y horizontales, grupos con pocos casos en gris.
# ============================================================================

def _funciones_plot():
    import ast
    import inspect

    fuente = inspect.getsource(viz)
    for nodo in ast.walk(ast.parse(fuente)):
        if isinstance(nodo, ast.FunctionDef) and nodo.name.startswith("plot_"):
            yield nodo.name, (ast.get_source_segment(fuente, nodo) or "")


def test_toda_grafica_de_plotly_sale_con_coma_decimal():
    """Cinco gráficas del PDF real mostraban «89.99», «12.99», «61.05» y el
    resto «65.2%»; el texto del informe dice «65,2%»."""
    sin_formato = [
        nombre for nombre, cuerpo in _funciones_plot()
        if ("px." in cuerpo or "go.Figure" in cuerpo) and "return _formato_local(fig)" not in cuerpo
    ]
    assert sin_formato == [], f"gráficas que no pasan por _formato_local: {sin_formato}"
    df = pd.DataFrame({"tipo_hogar": ["Nuclear", "Unipersonal"], "pct_hogares": [65.25, 18.8]})
    fig = viz.plot_tipos_hogar(df)
    assert fig.layout.separators == ",."
    assert fig.data[0].texttemplate == "%{text:.1f}%"
    fig = viz.plot_pct_pobres_indigentes({"pct_pobres": 12.99, "pct_indigentes": 1.41})
    assert fig.data[0].texttemplate == "%{text:.1f}%"


def test_ninguna_etiqueta_de_barra_se_formatea_a_mano():
    """Una etiqueta armada con f-string («f"{v:.1f}%"») no pasa por el
    separador decimal de Plotly: siempre `texttemplate`."""
    a_mano = [nombre for nombre, cuerpo in _funciones_plot() if 'text=[f"' in cuerpo or "text=[f'" in cuerpo]
    assert a_mano == [], f"etiquetas formateadas a mano (usar text=<columna> + texttemplate): {a_mano}"


def test_una_barra_por_categoria_lleva_un_solo_color():
    """Ocho gráficas del PDF real pintaban cada barra de un color distinto
    sin que el color significara nada. Regla: sin leyenda, sin `color=`;
    la excepción es un mapa explícito de colores con significado."""
    import re

    decorativas = []
    for nombre, cuerpo in _funciones_plot():
        sin_leyenda = "showlegend=False" in cuerpo
        # `color=<columna o lista>` pinta por categoría; `color="#..."` es un
        # color fijo (los marcadores del dumbbell) y no cuenta.
        color_por_categoria = re.search(r"\bcolor=(?!_discrete|\")", cuerpo) is not None
        if sin_leyenda and color_por_categoria and "color_discrete_map" not in cuerpo:
            decorativas.append(nombre)
    assert decorativas == [], f"color por categoría sin significado: {decorativas}"


def test_los_departamentos_se_leen_como_se_escriben_en_toda_grafica():
    df = pd.DataFrame({"departamento": ["TREINTA Y TRES", "RÍO NEGRO", "MONTEVIDEO"], "razon_dependencia": [56.5, 61.2, 50.6]})
    fig = viz.plot_razon_dependencia_por(df, "departamento")
    assert list(fig.data[0].y) == ["Treinta y Tres", "Río Negro", "Montevideo"]
    df = pd.DataFrame({"departamento": ["TREINTA Y TRES", "SALTO"], "pct_precariedad": [50.2, 56.4]})
    assert list(viz.plot_precariedad_estructural_por(df, "departamento").data[0].y) == ["Treinta y Tres", "Salto"]
    resultado = pd.DataFrame({"pct_pobreza": [1.0, 0.0], "indice": [0.5, 0.5]}, index=pd.Index(["SAN JOSÉ", "SALTO"], name="departamento"))
    assert list(viz.plot_indice_desarrollo_territorial(resultado).data[0].y) == ["San José", "Salto"]
    fig = viz.plot_dumbbell(["Índice"], [0.83], [0.24], nombre_a="COLONIA", nombre_b="ARTIGAS", titulo="Brecha")
    assert [t.name for t in fig.data[1:]] == ["Colonia", "Artigas"]


def test_plot_pct_por_por_departamento_es_horizontal_ordenada_y_marca_los_poco_confiables():
    """Del PDF real de 2024: la victimización por departamento era la única
    gráfica por departamento vertical y sin ordenar, y mostraba «0,0%
    (Cerro Largo)» sobre 0 víctimas como un dato más."""
    df = pd.DataFrame({"departamento": ["Cerro Largo", "Montevideo", "Treinta y Tres"], "pct": [0.0, 3.2, 7.7]})
    fig = viz.plot_pct_por(df, "departamento", titulo="Victimización por departamento", xlabel="Departamento",
                           poco_confiables=["Cerro Largo", "Treinta y Tres"])
    assert fig.data[0].orientation == "h"
    assert fig.layout.yaxis.categoryorder == "total ascending"
    assert fig.layout.xaxis.range[0] == 0
    assert list(fig.data[0].marker.color) == [viz.COLOR_POCO_CONFIABLE, viz.COLOR_BASE, viz.COLOR_POCO_CONFIABLE]
    # Con pocas categorías sigue siendo vertical y de un solo color.
    df = pd.DataFrame({"sexo_grupo": ["Hombre", "Mujer"], "pct": [1.9, 2.8]})
    fig = viz.plot_pct_por(df, "sexo_grupo", titulo="Victimización por sexo", xlabel="Sexo")
    assert fig.data[0].orientation == "v"
    assert list(fig.data[0].marker.color) == [viz.COLOR_BASE, viz.COLOR_BASE]
