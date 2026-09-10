"""Gráficos del análisis de conectividad. Los gráficos interactivos usan
Plotly; los gráficos estadísticos (heatmap, grillas comparativas) usan
matplotlib/seaborn.
"""

import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns

from . import resumen as _res
from .analysis import ResumenConectividad

# ============================================================================
# Convenciones comunes a todas las gráficas (ver docs/CONVENCIONES_DE_GRAFICAS.md,
# «Formato y color»). Nacen de la revisión del PDF real de 2024:
#
# - Las cifras salen con coma decimal y punto de miles, como el texto del
#   informe (`resumen.fmt`), y con un decimal y el símbolo «%» en toda barra
#   de porcentaje. Cinco gráficas mostraban «89.99» o «61.05» y el resto
#   «65.2%»; el resumen decía «65,2%». `SEPARADORES` es el formato de Plotly
#   (decimal, miles) que aplica a etiquetas y ejes; las etiquetas se
#   formatean con `texttemplate`, nunca a mano con f-strings (esas no pasan
#   por el separador).
# - El color no decora: una barra por categoría lleva UN color (`COLOR_BASE`)
#   salvo que el color signifique algo (una leyenda, la severidad). Ocho
#   gráficas pintaban cada barra de un color distinto sin que significara
#   nada (Tufte, data-ink ratio).
# - Los departamentos se leen como se escriben («Treinta y Tres», no
#   «TREINTA Y TRES» en unas gráficas y «Treinta y Tres» en otras) y siempre
#   en barras horizontales ordenadas (19 categorías con nombres largos).
# - Un grupo con pocos casos se dibuja en `COLOR_POCO_CONFIABLE` (gris) y la
#   celda lo dice en una nota; no desaparece ni se muestra como un dato más.
# ============================================================================

SEPARADORES = ",."
COLOR_BASE = "#5a7fa6"
COLOR_POCO_CONFIABLE = "#c9ced6"
# El título más largo que pasó una revisión visual real en una figura de 800
# px tiene 65 caracteres; lo comparten el test de clase de
# test_visualization.py y la validación previa de las celdas a medida.
LARGO_MAXIMO_TITULO = 65


def _formato_local(fig):
    """Última parada de toda gráfica de Plotly: coma decimal y punto de
    miles en etiquetas y ejes. Las de matplotlib se devuelven tal cual."""
    if isinstance(fig, go.Figure):
        fig.update_layout(separators=SEPARADORES)
    return fig


def _legible(valores) -> list[str]:
    """Nombres en mayúsculas sostenidas («ARTIGAS», «TREINTA Y TRES») tal
    como se leen; el resto queda igual."""
    return [_res.nombre_propio(v) for v in valores]


def _con_etiquetas_legibles(resumen: pd.DataFrame, columna: str) -> pd.DataFrame:
    return resumen.assign(**{columna: _legible(resumen[columna])})


def plot_dumbbell(categorias: list, valores_a: list, valores_b: list, nombre_a: str, nombre_b: str, titulo: str, xlabel: str = "%"):
    """Dumbbell chart (dos puntos por categoría, conectados por una línea):
    compara dos series de valores a través de una o más categorías —
    ej. "quintil 1" vs. "quintil 5", o "comunicación informal" vs.
    "denuncia formal" para varios tipos de delito a la vez.

    Es la práctica recomendada por la literatura de visualización de
    datos (Tufte; Knaflic, storytellingwithdata.com; Nightingale/Data
    Visualization Society) para comparar dos grupos específicos, en vez
    de una barra con la diferencia ya calculada — conserva los dos
    valores reales además de la brecha entre ellos, algo que una sola
    barra de "diferencia" no muestra (ver docs/CONVENCIONES_DE_GRAFICAS.md).

    Plotly no trae este tipo de gráfica nativo (ni Plotly Express ni
    ninguna librería especializada mejor mantenida vale la pena sumar
    como dependencia nueva solo para esto) — se arma a mano con
    `go.Scatter`: una traza de líneas (los segmentos que conectan cada
    par) y dos trazas de marcadores (una por serie).
    """
    categorias = _legible(categorias)
    line_x, line_y = [], []
    for categoria, valor_a, valor_b in zip(categorias, valores_a, valores_b):
        line_x += [valor_a, valor_b, None]
        line_y += [categoria, categoria, None]

    fig = go.Figure(
        data=[
            go.Scatter(x=line_x, y=line_y, mode="lines", line=dict(color="#8b949e", width=2), showlegend=False, hoverinfo="skip"),
            go.Scatter(x=valores_a, y=categorias, mode="markers", name=_res.nombre_propio(nombre_a), marker=dict(color="#d1495b", size=14)),
            go.Scatter(x=valores_b, y=categorias, mode="markers", name=_res.nombre_propio(nombre_b), marker=dict(color="#66a182", size=14)),
        ]
    )
    altura = max(300, 80 * len(categorias) + 150)
    fig.update_layout(
        title=titulo,
        title_x=0.5,
        xaxis_title=xlabel,
        yaxis_title="",
        # Un scatter autoescala al rango de los datos y exagera visualmente
        # las diferencias: el eje de un valor (acá, %) tiene que arrancar en
        # cero, y hay que fijarlo a mano porque Plotly no lo hace solo (a
        # diferencia de las barras).
        xaxis_range=[0, max(max(valores_a), max(valores_b)) * 1.15],
        width=850,
        height=altura,
    )
    return _formato_local(fig)


# ============================================================================
# Panorama general de conectividad
# ============================================================================

def plot_distribucion_conectividad(resumen: ResumenConectividad):
    """Barras: % de hogares de Montevideo con y sin conexión a internet.

    Hasta la 0.9.0 esto graficaba TV cable — ver `analysis.resumen_conectividad`.
    """
    data = {
        "Tipo de Hogar": ["Con internet", "Sin internet"],
        "Porcentaje": [resumen.pct_con_internet, resumen.pct_sin_internet],
    }
    fig = px.bar(
        data,
        y="Tipo de Hogar",
        x="Porcentaje",
        orientation="h",
        title="Conexión a internet en los hogares de Montevideo",
        width=800,
        height=400,
        color_discrete_sequence=px.colors.qualitative.Pastel,
    )
    fig.update_traces(width=0.5, text=data["Porcentaje"], texttemplate="%{text:.1f}%", textposition="auto")
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, title_x=0.5, title_y=0.85)
    return _formato_local(fig)


# ============================================================================
# Ampliación de métricas
# ============================================================================

def plot_brecha_digital(brecha_df: pd.DataFrame):
    """Barras agrupadas: penetración de cada tecnología por nivel económico."""
    fig = px.bar(
        brecha_df, x="nivel_economico", y="pct_penetracion", color="tecnologia",
        barmode="group", title="Brecha digital por nivel económico",
        color_discrete_sequence=px.colors.qualitative.Safe,
    )
    fig.update_layout(
        xaxis_title="Nivel económico", yaxis_title="Penetración (%)",
        legend_title="Tecnología", width=900, height=500, title_x=0.5,
    )
    return _formato_local(fig)


def _plot_barras_100_apiladas(tabla_pct: pd.DataFrame, titulo: str, xlabel: str):
    """Barras 100% apiladas: proporción de una variable dentro de categorías de otra."""
    fig, ax = plt.subplots(figsize=(8, 5))
    tabla_pct.plot(kind="bar", stacked=True, ax=ax, colormap="viridis", width=0.6)
    # `pad`: sin él, el título quedaba pegado al borde superior del área de
    # dibujo (visto en el PDF real de 2024, métrica 3).
    ax.set_title(titulo, fontsize=13, pad=14)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("% dentro de cada grupo")
    ax.set_ylim(0, 100)
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", frameon=False)
    ax.tick_params(axis="x", rotation=0)
    sns.despine(ax=ax)
    fig.tight_layout()
    return _formato_local(fig)


def plot_ingreso_hogar_departamento(serie: pd.Series):
    """Barras horizontales: ingreso típico del hogar por departamento (19
    categorías, algunas con nombres largos) — horizontales para que se
    lean sin inclinar la cabeza (Cleveland & McGill, 1984), mismo criterio
    que `plot_razon_dependencia_por` para el mismo tipo de comparación.

    No pertenece al catálogo fijo: es el par de
    `analysis.ingreso_hogar_mediano_por_departamento`, disponible para las
    métricas a medida del paso 6 (ver el docstring de esa función).
    """
    fig = px.bar(
        y=_legible(serie.index), x=serie.values, orientation="h",
        title="Ingreso típico del hogar por departamento",
        color_discrete_sequence=[COLOR_BASE],
        text=serie.values,
    )
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    fig.update_layout(
        yaxis_title="", xaxis_title="Ingreso típico del hogar (UYU, sin valor locativo)",
        yaxis={"categoryorder": "total ascending"},
        # Mismo margen que todas las barras horizontales con etiqueta
        # afuera — era la única de las siete que no lo tenía; la encontró
        # el test de clase de test_visualization.py antes de que saliera
        # recortada en un informe real, que es exactamente para lo que
        # ese test existe.
        xaxis_range=[0, float(serie.max()) * 1.15],
        showlegend=False, width=800, height=550, title_x=0.5,
    )
    return _formato_local(fig)


def plot_precariedad_estructural(resultado: dict):
    """Barras horizontales: % de hogares con y sin al menos una carencia
    estructural (índice de conteo de carencias — ver
    docs/CONVENCIONES_DE_GRAFICAS.md, o analysis.precariedad_estructural).
    """
    data = {
        "Condición": ["Con carencia estructural", "Sin carencia estructural"],
        "Porcentaje": [resultado["pct_con_carencia"], round(100 - resultado["pct_con_carencia"], 2)],
    }
    fig = px.bar(
        data, y="Condición", x="Porcentaje", orientation="h",
        title="Precariedad estructural de la vivienda",
        width=800, height=350, color_discrete_sequence=["#d1495b"],
    )
    fig.update_traces(width=0.5, text=data["Porcentaje"], texttemplate="%{text:.1f}%", textposition="auto")
    fig.update_layout(xaxis_title="% de hogares", yaxis_title="", title_x=0.5)
    return _formato_local(fig)


def plot_precariedad_estructural_por(resumen: pd.DataFrame, criterio: str):
    """Barras horizontales: % de hogares con al menos una carencia
    estructural, según un criterio cualquiera (nivel económico,
    departamento). Horizontales para que se lean sin inclinar la cabeza
    cuando el criterio es departamento (19 categorías, algunas con
    nombres largos — Cleveland & McGill, 1984).
    """
    columna_y = resumen.columns[0]
    resumen = _con_etiquetas_legibles(resumen, columna_y)
    fig = px.bar(
        resumen, y=columna_y, x="pct_precariedad", orientation="h",
        title=f"Precariedad estructural de la vivienda según {criterio}", text="pct_precariedad",
        color_discrete_sequence=["#d1495b"],
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(
        yaxis_title="", xaxis_title="% de hogares con carencia",
        yaxis={"categoryorder": "total ascending"},
        # Margen a la derecha de la barra más larga para que su etiqueta no
        # quede cortada por el borde (mismo motivo, y mismo arreglo, que
        # plot_pct_por y plot_tasa_mensual_promedio_por) — encontrado en una
        # corrida real con datos de 2025: "ARTIGAS, 65.0%" salía recortado.
        xaxis_range=[0, resumen["pct_precariedad"].max() * 1.15],
        width=850, height=550, title_x=0.5, showlegend=False,
    )
    return _formato_local(fig)


def plot_carencias_estructurales_mas_frecuentes(resumen: pd.DataFrame):
    """Barras horizontales ordenadas: % de hogares con cada carencia
    estructural puntual, de mayor a menor prevalencia.
    """
    fig = px.bar(
        resumen, y="carencia", x="pct_hogares", orientation="h",
        title="Carencias estructurales más frecuentes", text="pct_hogares",
        color_discrete_sequence=["#8d6ab8"],
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(
        yaxis_title="", xaxis_title="% de hogares",
        yaxis={"categoryorder": "total ascending"},
        # Mismo margen que plot_precariedad_estructural_por, por el mismo
        # motivo: sin él, la etiqueta de la carencia más frecuente queda
        # cortada por el borde derecho del gráfico.
        xaxis_range=[0, resumen["pct_hogares"].max() * 1.15],
        width=850, height=500, title_x=0.5, showlegend=False,
    )
    return _formato_local(fig)


# ============================================================================
# Hogares (composición, sin tecnología) y Brecha Digital (con marco
# internacional) — ver la nota de fuentes en config.py.
# ============================================================================

def plot_pct_pobres_indigentes(resultado: dict):
    """Barras horizontales: % de hogares pobres y % en indigencia."""
    data = {"Condición": ["Pobres", "Indigentes"], "Porcentaje": [resultado["pct_pobres"], resultado["pct_indigentes"]]}
    fig = px.bar(
        data, y="Condición", x="Porcentaje", orientation="h",
        title="Hogares en situación de pobreza e indigencia",
        width=800, height=350, color_discrete_sequence=["#d1495b"],
    )
    fig.update_traces(width=0.5, text=data["Porcentaje"], texttemplate="%{text:.1f}%", textposition="auto")
    fig.update_layout(xaxis_title="% de hogares", yaxis_title="", title_x=0.5)
    return _formato_local(fig)


def plot_tasa_jefatura_femenina(resultado: dict):
    """Barras horizontales: % de hogares con jefe hombre vs. jefa mujer."""
    pct_mujer = resultado["pct_jefatura_femenina"]
    data = {"Jefatura": ["Jefe hombre", "Jefa mujer"], "Porcentaje": [round(100 - pct_mujer, 2), pct_mujer]}
    fig = px.bar(
        data, y="Jefatura", x="Porcentaje", orientation="h",
        title="Jefatura de hogar por sexo",
        width=800, height=350, color_discrete_sequence=["#5a7fa6"],
    )
    fig.update_traces(width=0.5, text=data["Porcentaje"], texttemplate="%{text:.1f}%", textposition="auto")
    fig.update_layout(xaxis_title="% de hogares", yaxis_title="", title_x=0.5)
    return _formato_local(fig)


def plot_tipos_hogar(resumen: pd.DataFrame):
    """Barras horizontales: % de hogares de cada tipo (taxonomía CELADE), de mayor a menor."""
    fig = px.bar(
        resumen, x="pct_hogares", y="tipo_hogar", orientation="h",
        title="Tipos de hogar", text="pct_hogares",
        color_discrete_sequence=["#66a182"],
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(
        xaxis_title="% de hogares", yaxis_title="", yaxis={"categoryorder": "total ascending"},
        # Mismo margen a la derecha que plot_pct_por y compañía, por el mismo
        # motivo: sin él, la etiqueta del tipo de hogar más frecuente queda
        # cortada por el borde — encontrado en una corrida real con datos de
        # 2023 ("Nuclear, 65.7%" salía recortado).
        xaxis_range=[0, resumen["pct_hogares"].max() * 1.15],
        width=800, height=450, title_x=0.5, showlegend=False,
    )
    return _formato_local(fig)


def plot_hacinamiento_por(resumen: pd.DataFrame, criterio: str):
    """Barras: % de hogares en situación de hacinamiento, según un criterio cualquiera."""
    columna_x = resumen.columns[0]
    fig = px.bar(
        resumen, x=columna_x, y="pct_hacinamiento",
        title=f"Hacinamiento según {criterio}", text="pct_hacinamiento",
        color_discrete_sequence=["#d1495b"],
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(
        xaxis_title=criterio.capitalize(), yaxis_title="% de hogares hacinados",
        yaxis_range=[0, max(resumen["pct_hacinamiento"].max() * 1.3, 5)],
        width=800, height=500, title_x=0.5, showlegend=False,
    )
    return _formato_local(fig)


def plot_razon_dependencia_por(resumen: pd.DataFrame, criterio: str):
    """Barras horizontales: razón de dependencia demográfica, según un
    criterio cualquiera (en la práctica, siempre departamento — 19
    categorías, algunas con nombres largos como "TREINTA Y TRES"). Barras
    horizontales, no verticales, por el mismo motivo que
    `plot_condiciones_vivienda`: se leen sin inclinar la cabeza (Cleveland
    & McGill, 1984).
    """
    columna_y = resumen.columns[0]
    resumen = _con_etiquetas_legibles(resumen, columna_y)
    fig = px.bar(
        resumen, y=columna_y, x="razon_dependencia", orientation="h",
        title=f"Razón de dependencia demográfica según {criterio}", text="razon_dependencia",
        color_discrete_sequence=["#5a7fa6"],
    )
    fig.update_traces(texttemplate="%{text:.1f}", textposition="outside")
    fig.update_layout(
        yaxis_title="", xaxis_title="Razón de dependencia (%)",
        yaxis={"categoryorder": "total ascending"},
        # Mismo margen a la derecha que plot_precariedad_estructural_por, por
        # el mismo motivo: sin él, la etiqueta del departamento con la razón
        # más alta queda cortada por el borde — encontrado en una corrida real
        # con datos de 2023 ("ROCHA, 65.0" salía recortado).
        xaxis_range=[0, resumen["razon_dependencia"].max() * 1.15],
        width=850, height=550, title_x=0.5, showlegend=False,
    )
    return _formato_local(fig)


def plot_indice_desarrollo_territorial(resultado: pd.DataFrame):
    """Barras horizontales ordenadas: ranking del índice sintético de
    desarrollo territorial por departamento (ver
    analysis.indice_desarrollo_territorial).
    """
    df_plot = resultado.reset_index().rename(columns={resultado.index.name or "index": "departamento"})
    df_plot = _con_etiquetas_legibles(df_plot, "departamento")
    fig = px.bar(
        df_plot, y="departamento", x="indice", orientation="h",
        title="Índice de desarrollo territorial por departamento", text="indice",
        color_discrete_sequence=["#5a7fa6"],
    )
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    fig.update_layout(
        yaxis_title="", xaxis_title="Índice (0 a 1, más alto = mejor)",
        yaxis={"categoryorder": "total ascending"},
        xaxis_range=[0, 1.1],
        width=850, height=550, title_x=0.5, showlegend=False,
    )
    return _formato_local(fig)


def plot_perfil_territorial(resultado: pd.DataFrame):
    """Heatmap: perfil normalizado (0-1) de cada dimensión del índice de
    desarrollo territorial, por departamento — el detalle que explica por
    qué un departamento queda arriba o abajo en el ranking (ver
    plot_indice_desarrollo_territorial), no solo el promedio final.
    """
    columnas_dimensiones = [c for c in resultado.columns if c != "indice"]
    tabla = resultado[columnas_dimensiones].sort_values(columnas_dimensiones[0])
    tabla.index = _legible(tabla.index)
    # Las cifras de cada celda con coma decimal, como el resto del informe
    # (seaborn solo sabe formatear con punto).
    anotaciones = tabla.apply(lambda columna: columna.map(lambda v: f"{v:.2f}".replace(".", ",")))
    fig, ax = plt.subplots(figsize=(7, 8))
    sns.heatmap(tabla, annot=anotaciones, fmt="", cmap="viridis", cbar_kws={"label": "0 a 1 (más alto = mejor)"}, ax=ax)
    ax.set_title("Perfil territorial por departamento", fontsize=13)
    ax.set_xlabel("")
    ax.set_ylabel("")
    fig.tight_layout()
    return _formato_local(fig)


def plot_pct_unipersonales_mayores(resultado: dict):
    """Barras horizontales: de los hogares unipersonales, % con jefe/a de 65+ vs. menor."""
    pct_mayores = resultado["pct_unipersonales_mayores"]
    data = {
        "Edad del integrante": ["65 años o más", "Menos de 65"],
        "Porcentaje": [pct_mayores, round(100 - pct_mayores, 2)],
    }
    fig = px.bar(
        data, y="Edad del integrante", x="Porcentaje", orientation="h",
        title="Hogares unipersonales según edad de su integrante",
        width=800, height=350, color_discrete_sequence=["#8d6ab8"],
    )
    fig.update_traces(width=0.5, text=data["Porcentaje"], texttemplate="%{text:.1f}%", textposition="auto")
    fig.update_layout(xaxis_title="% de hogares unipersonales", yaxis_title="", title_x=0.5)
    return _formato_local(fig)


def plot_brecha_digital_por_cohorte(brecha_df: pd.DataFrame):
    """Barras agrupadas: penetración de cada tecnología por cohorte generacional del jefe/a de hogar."""
    fig = px.bar(
        brecha_df, x="cohorte", y="pct_penetracion", color="tecnologia",
        barmode="group", title="Brecha digital por cohorte generacional",
        color_discrete_sequence=px.colors.qualitative.Safe,
    )
    fig.update_layout(
        xaxis_title="Cohorte generacional (según edad del jefe/a de hogar)", yaxis_title="Penetración (%)",
        legend_title="Tecnología", width=950, height=500, title_x=0.5,
    )
    return _formato_local(fig)


def plot_brecha_digital_por_jefatura(brecha_df: pd.DataFrame):
    """Barras agrupadas: penetración de cada tecnología según el sexo del jefe/a de hogar."""
    fig = px.bar(
        brecha_df, x="jefe_sexo", y="pct_penetracion", color="tecnologia",
        barmode="group", title="Brecha digital según sexo del jefe/a de hogar",
        color_discrete_sequence=px.colors.qualitative.Safe,
    )
    fig.update_layout(
        xaxis_title="Sexo del jefe/a de hogar", yaxis_title="Penetración (%)",
        legend_title="Tecnología", width=800, height=500, title_x=0.5,
    )
    return _formato_local(fig)


def plot_calidad_conexion_por(tabla_pct: pd.DataFrame, criterio: str):
    """Barras 100% apiladas: calidad de conexión (sin conexión / solo móvil
    / banda ancha fija) según un criterio cualquiera (ej. nivel económico).
    """
    return _plot_barras_100_apiladas(
        tabla_pct,
        titulo=f"Calidad de la conexión a internet según {criterio}",
        xlabel=criterio.capitalize(),
    )


def plot_composicion_categorica(tabla_pct: pd.DataFrame, titulo: str, xlabel: str):
    """Barras 100% apiladas, genérica: para cualquier composición categórica
    ponderada (ver `analysis.composicion_categorica_ponderada_por`) que no
    tenga ya un wrapper específico como `plot_calidad_conexion_por` (ej.
    situación ocupacional por sector formal/informal).
    """
    return _plot_barras_100_apiladas(tabla_pct, titulo=titulo, xlabel=xlabel)


def plot_indice_acceso_digital_por(resumen: pd.DataFrame, criterio: str):
    """Barras: promedio del índice de acceso digital (0 a 3), según un
    criterio cualquiera.

    Graficar un promedio como barra, sin mostrar la dispersión alrededor,
    es el patrón de "dynamite plot" que Weissgerber et al. (2015, PLOS
    Biology) desaconsejan para datos continuos: dos grupos con la misma
    barra pueden tener distribuciones muy distintas. Acá el riesgo es
    acotado porque el índice toma solo cuatro valores posibles (0, 1, 2 o
    3 tecnologías — ver `preprocessing.compute_indice_acceso_digital`), no
    es una variable continua con cola larga; aun así el promedio esconde
    cuántos hogares están exactamente en 0, que es el dato más relevante
    de una brecha digital. Conviene acompañarlo de la métrica de
    penetración por tecnología (1) antes de sacar conclusiones.
    """
    columna_x = resumen.columns[0]
    fig = px.bar(
        resumen, x=columna_x, y="indice_promedio",
        title=f"Índice de acceso digital según {criterio}", text="indice_promedio",
        color_discrete_sequence=["#66a182"],
    )
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    fig.update_layout(
        xaxis_title=criterio.capitalize(), yaxis_title="Índice promedio (0 a 3)",
        yaxis_range=[0, 3.5],
        width=800, height=500, title_x=0.5, showlegend=False,
    )
    return _formato_local(fig)


def plot_adopcion_tablet_ibirapita(resumen: pd.DataFrame, criterio: str):
    """Barras: % de hogares con tablet del Plan Ibirapitá, según un criterio
    cualquiera. El título nombra la población (jefe/a de 65+) porque el
    catálogo la promete y el dato llega ya filtrado a esos hogares."""
    columna_x = resumen.columns[0]
    fig = px.bar(
        resumen, x=columna_x, y="pct_con_tablet",
        title="Tablets del Plan Ibirapitá en hogares con jefe/a de 65 años o más", text="pct_con_tablet",
        color_discrete_sequence=["#8d6ab8"],
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(
        xaxis_title=criterio.capitalize(), yaxis_title="% de hogares con tablet",
        yaxis_range=[0, max(resumen["pct_con_tablet"].max() * 1.3, 5)],
        width=800, height=500, title_x=0.5, showlegend=False,
    )
    return _formato_local(fig)


def plot_prevalencia_inseguridad_alimentaria(prevalencia: dict):
    """Barras simples: % de hogares (ponderado) en inseguridad alimentaria
    moderada-o-severa y severa, a nivel nacional."""
    categorias = ["Moderada o severa", "Severa"]
    valores = [prevalencia["moderada_o_severa"], prevalencia["severa"]]
    fig = px.bar(
        x=categorias, y=valores,
        title="Prevalencia de inseguridad alimentaria en los hogares",
        # El color sí significa acá: la severa es el caso más grave.
        color=categorias,
        color_discrete_map={"Moderada o severa": "#eeb95c", "Severa": "#d1495b"},
        text=valores,
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(
        xaxis_title="", yaxis_title="% de hogares (ponderado)",
        showlegend=False, width=650, height=500, title_x=0.5,
    )
    return _formato_local(fig)


def plot_inseguridad_alimentaria_por(resumen: pd.DataFrame, columna_grupo: str, titulo: str, xlabel: str):
    """Barras simples: % de hogares en inseguridad alimentaria (ponderado), por grupo."""
    fig = px.bar(
        resumen, x=columna_grupo, y="pct_inseguridad",
        title=titulo,
        color_discrete_sequence=[COLOR_BASE],
        text="pct_inseguridad",
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(
        xaxis_title=xlabel, yaxis_title="% de hogares en inseguridad alimentaria (ponderado)",
        showlegend=False, width=650, height=500, title_x=0.5,
    )
    return _formato_local(fig)


def plot_tasas_actividad_empleo_desempleo(tasas: dict):
    """Barras simples: tasas de actividad, empleo y desempleo a nivel nacional."""
    etiquetas = {"tasa_actividad": "Actividad", "tasa_empleo": "Empleo", "tasa_desempleo": "Desempleo"}
    categorias = [etiquetas[k] for k in ["tasa_actividad", "tasa_empleo", "tasa_desempleo"]]
    valores = [tasas["tasa_actividad"], tasas["tasa_empleo"], tasas["tasa_desempleo"]]
    fig = px.bar(
        x=categorias, y=valores,
        title="Tasas de actividad, empleo y desempleo (promedio de los 12 meses)",
        color_discrete_sequence=[COLOR_BASE],
        text=valores,
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(
        xaxis_title="", yaxis_title="% (ponderado, promedio mensual)",
        showlegend=False, width=650, height=500, title_x=0.5,
    )
    return _formato_local(fig)


def plot_tasas_por_grupo(resumen: pd.DataFrame, columna_grupo: str, titulo: str):
    """Barras agrupadas: tasas de actividad, empleo y desempleo comparando
    grupos (sexo, edad) — para la brecha de género y el desempleo juvenil."""
    df_plot = resumen.melt(
        id_vars=columna_grupo, value_vars=["tasa_actividad", "tasa_empleo", "tasa_desempleo"],
        var_name="tasa", value_name="valor",
    )
    etiquetas = {"tasa_actividad": "Actividad", "tasa_empleo": "Empleo", "tasa_desempleo": "Desempleo"}
    df_plot["tasa"] = df_plot["tasa"].map(etiquetas)
    fig = px.bar(
        df_plot, x="tasa", y="valor", color=columna_grupo, barmode="group",
        title=titulo,
        color_discrete_sequence=px.colors.qualitative.Safe,
        text="valor",
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(
        xaxis_title="", yaxis_title="% (ponderado, promedio mensual)",
        width=700, height=500, title_x=0.5, legend_title="",
    )
    return _formato_local(fig)


def plot_tasas_por_anio(tabla: pd.DataFrame):
    """Líneas con marcadores: evolución de las tasas de actividad, empleo y
    desempleo entre años no necesariamente consecutivos (ver
    `analysis.tasas_actividad_empleo_desempleo_por_anio`).

    El eje x usa los años en su escala numérica real, no una categoría
    pareja — Plotly ya hace esto solo si `tabla["anio"]` llega como `int`
    (que es como lo entrega esa función): la distancia visual entre 2019 y
    2024 queda 5 veces más ancha que entre 2024 y 2025, en vez de verse
    igual de "cerca" como pasaría con un eje categórico. Fundamento: mismo
    principio de precisión perceptiva de posición en una escala común de
    Cleveland & McGill (1984) que respalda el resto de los gráficos de
    este proyecto — acá aplicado al eje temporal, no solo al de categorías.
    Los marcadores explícitos en cada punto son a propósito: la línea entre
    ellos no representa datos interpolados, solo conecta visualmente años
    con encuesta propia.
    """
    df_plot = tabla.melt(
        id_vars="anio", value_vars=["tasa_actividad", "tasa_empleo", "tasa_desempleo"],
        var_name="tasa", value_name="valor",
    )
    etiquetas = {"tasa_actividad": "Actividad", "tasa_empleo": "Empleo", "tasa_desempleo": "Desempleo"}
    df_plot["tasa"] = df_plot["tasa"].map(etiquetas)
    fig = px.line(
        df_plot, x="anio", y="valor", color="tasa", markers=True,
        title="Tasas de actividad, empleo y desempleo por año",
        color_discrete_sequence=px.colors.qualitative.Safe,
    )
    fig.update_traces(marker=dict(size=10))
    fig.update_xaxes(type="linear", tickmode="array", tickvals=sorted(tabla["anio"].unique()))
    fig.update_layout(
        xaxis_title="Año", yaxis_title="% (ponderado, promedio mensual)",
        legend_title="", width=800, height=500, title_x=0.5,
    )
    return _formato_local(fig)


def plot_serie_por_anio(
    tabla: pd.DataFrame,
    columnas_valor: list[str] | None = None,
    etiquetas: dict[str, str] | None = None,
    titulo: str = "",
    ylabel: str = "%",
):
    """Generaliza `plot_tasas_por_anio` a cualquier métrica del catálogo
    (no solo Empleo): líneas con marcadores, eje x con los años en su
    escala numérica real — mismo fundamento (Cleveland & McGill 1984,
    aplicado al eje temporal en vez de solo al de categorías; ver
    `docs/CONVENCIONES_DE_GRAFICAS.md`) y misma razón para no tratar el
    año como categoría (ver `analysis.combinar_por_anio`).

    Para exactamente 2 años, usar en cambio `plot_dumbbell` — es la
    práctica recomendada por sobre una línea de dos puntos, y conserva
    mejor la comparación puntual.

    `columnas_valor` son las columnas de `tabla` a graficar como líneas
    (una por columna) — por defecto, todas menos `anio`. `etiquetas`
    traduce el nombre de columna a un nombre legible en la leyenda (ej.
    `{"valor": "Pobreza"}`); si no se pasa, usa el nombre de columna tal
    cual.
    """
    if columnas_valor is None:
        columnas_valor = [c for c in tabla.columns if c != "anio"]
    # value_name fijo ("_valor_") en vez del nombre real de la columna:
    # si la tabla ya tiene una sola columna de valor (caso común, ej.
    # "valor" de combinar_por_anio), pd.melt no permite que value_name
    # coincida con una columna existente.
    df_plot = tabla.melt(id_vars="anio", value_vars=columnas_valor, var_name="serie", value_name="_valor_")
    if etiquetas:
        df_plot["serie"] = df_plot["serie"].map(lambda c: etiquetas.get(c, c))
    fig = px.line(
        df_plot, x="anio", y="_valor_", color="serie", markers=True,
        title=titulo, color_discrete_sequence=px.colors.qualitative.Safe,
    )
    fig.update_traces(marker=dict(size=10))
    fig.update_xaxes(type="linear", tickmode="array", tickvals=sorted(tabla["anio"].unique()))
    fig.update_layout(
        xaxis_title="Año", yaxis_title=ylabel,
        legend_title="", showlegend=len(columnas_valor) > 1,
        width=800, height=500, title_x=0.5,
    )
    return _formato_local(fig)


def plot_tasa_mensual_promedio_por(resumen: pd.DataFrame, columna_grupo: str, titulo: str):
    """Barras horizontales: % ponderado (promedio mensual) por grupo —
    informalidad, subempleo, desempleo, lo que corresponda según el
    título. Horizontales para leerse sin inclinar la cabeza cuando el
    grupo es departamento (19 categorías, algunas con nombres largos —
    Cleveland & McGill, 1984); no perjudica los casos con pocas
    categorías (sexo, nivel educativo), que se leen igual de bien así.
    """
    resumen = _con_etiquetas_legibles(resumen, columna_grupo)
    fig = px.bar(
        resumen, y=columna_grupo, x="pct_promedio", orientation="h",
        title=titulo,
        color_discrete_sequence=[COLOR_BASE],
        text="pct_promedio",
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(
        yaxis_title="", xaxis_title="% (ponderado, promedio mensual)",
        yaxis={"categoryorder": "total ascending"},
        # Margen a la derecha de la barra más larga para que su etiqueta de
        # porcentaje no quede cortada por el borde del gráfico (mismo motivo
        # que plot_pct_por) — encontrado en una corrida real: sin este
        # margen, "Tasa de desempleo por departamento" (Treinta y Tres,
        # 14.9%, la barra más larga) recortaba el "%" final.
        xaxis_range=[0, resumen["pct_promedio"].max() * 1.15],
        showlegend=False, width=750, height=500, title_x=0.5,
    )
    return _formato_local(fig)


def plot_pct_por(
    resumen: pd.DataFrame,
    columna_grupo: str,
    titulo: str,
    xlabel: str,
    columna_valor: str = "pct",
    poco_confiables: list | None = None,
):
    """Barras simples: % ponderado por grupo — genérica para prevalencia de
    victimización, tasas de comunicación/denuncia/violencia por tipo de
    delito, o cualquier corte similar sin promedio mensual.

    Por departamento (o con más de seis categorías) las barras son
    horizontales y ordenadas, como toda gráfica por departamento del informe
    (Cleveland & McGill, 1984); en el PDF real de 2024 la victimización por
    departamento era la única vertical, sin ordenar y con 19 etiquetas
    rotadas.

    `poco_confiables`: grupos con menos de 30 casos en la muestra (ver
    `analysis.grupos_con_pocos_casos`). Se dibujan en gris, para que se vean
    pero no se lean como un dato más; la celda los explica en una nota.
    """
    resumen = _con_etiquetas_legibles(resumen, columna_grupo)
    grises = set(_legible(poco_confiables or []))
    colores = [COLOR_POCO_CONFIABLE if g in grises else COLOR_BASE for g in resumen[columna_grupo]]
    horizontal = columna_grupo == "departamento" or len(resumen) > 6
    if horizontal:
        fig = px.bar(resumen, y=columna_grupo, x=columna_valor, orientation="h", title=titulo, text=columna_valor)
        fig.update_layout(
            yaxis_title="", xaxis_title="% (ponderado)",
            yaxis={"categoryorder": "total ascending"},
            # Margen a la derecha de la barra más larga, como en toda barra
            # horizontal con etiqueta afuera (test de clase).
            xaxis_range=[0, resumen[columna_valor].max() * 1.15],
            showlegend=False, width=850, height=550, title_x=0.5,
        )
    else:
        fig = px.bar(resumen, x=columna_grupo, y=columna_valor, title=titulo, text=columna_valor)
        fig.update_layout(
            xaxis_title=xlabel, yaxis_title="% (ponderado)",
            showlegend=False, width=700, height=500, title_x=0.5,
            # Un poco de margen arriba de la barra más alta, para que la
            # etiqueta de porcentaje no quede cortada por el borde del gráfico
            # cuando el valor está cerca del máximo (ej. 86%).
            yaxis_range=[0, resumen[columna_valor].max() * 1.15],
        )
    fig.update_traces(marker_color=colores, texttemplate="%{text:.1f}%", textposition="outside")
    return _formato_local(fig)

