"""Cálculos analíticos sobre las tablas ya preparadas."""

from dataclasses import dataclass

import pandas as pd

from . import config

@dataclass
class ResumenConectividad:
    total_hogares: int
    hogares_con_internet: int
    hogares_sin_internet: int
    pct_con_internet: float
    pct_sin_internet: float


def resumen_conectividad(hogares_ext: pd.DataFrame) -> ResumenConectividad:
    """Totales (tamaño de muestra, sin ponderar — para transparencia sobre
    cuántos casos hay detrás de cada número) y porcentajes (ponderados por
    `ponderador_hogar`, representativos de la población) de hogares con/sin
    conexión a internet en Montevideo.

    Hasta la versión 0.9.0 esta función medía TV cable, no conectividad:
    era el eje del análisis original de 2019 y quedó como herencia cuando
    el foco del proyecto pasó a ser la brecha digital. Tener o no TV cable
    no dice nada sobre si un hogar está conectado — se reemplazó por
    `tiene_internet`, que es lo que la sección dice medir.

    `hogares_ext` tiene que venir de
    `preprocessing.prepare_hogares_extendido` (que es donde `tiene_internet`
    se decodifica de 1/2/99 a booleano).
    """
    total = len(hogares_ext)
    con_internet_bool = hogares_ext["tiene_internet"].fillna(False)
    con_internet = int(con_internet_bool.sum())
    pct_con = pct_ponderado(hogares_ext.assign(_con_internet=con_internet_bool), "_con_internet")
    return ResumenConectividad(
        total_hogares=total,
        hogares_con_internet=con_internet,
        hogares_sin_internet=total - con_internet,
        pct_con_internet=pct_con,
        pct_sin_internet=round(100 - pct_con, 2),
    )


# ============================================================================
# Ampliación de métricas
# ============================================================================

def _brecha_digital_por(df_extendido: pd.DataFrame, columna_grupo: str) -> pd.DataFrame:
    """% ponderado de penetración de cada tecnología (internet, PC,
    streaming), por una columna de grupo cualquiera — compartida por
    `brecha_digital_por_nivel_economico`, `_por_cohorte` y `_por_jefatura`.
    """
    tecnologias = list(config.TECNOLOGIAS_LABELS.keys())
    partes = []
    for tecnologia in tecnologias:
        parte = pct_ponderado_por(df_extendido, columna_grupo, tecnologia, "ponderador_hogar")
        parte["tecnologia"] = config.TECNOLOGIAS_LABELS[tecnologia]
        partes.append(parte.rename(columns={"pct": "pct_penetracion"}))
    return pd.concat(partes, ignore_index=True)[[columna_grupo, "tecnologia", "pct_penetracion"]]


def brecha_digital_por_nivel_economico(df_extendido: pd.DataFrame) -> pd.DataFrame:
    """% ponderado de penetración de cada tecnología (internet, PC, streaming), por nivel económico."""
    return _brecha_digital_por(df_extendido, "nivel_economico")


def _condiciones_vivienda_disponibles(hogares_condiciones: pd.DataFrame) -> list[str]:
    """Columnas de CONDICIONES_VIVIENDA_COLUMNS que de verdad están en
    `hogares_condiciones` - varía de año a año (12 en 2019, 4 desde 2024).

    Encontrado con datos reales de 2023: ese año no tiene NINGUNA de las
    variables del módulo C5 (no es que cambiaron de nombre - el módulo no
    se relevó ese año, verificado contra el archivo real completo, no una
    suposición). Sin este chequeo, las tres funciones de precariedad
    calculaban silenciosamente "0% de hogares con carencia" - `df[[]]`
    (una selección de cero columnas) hace que `.any(axis=1)` dé `False`
    para todas las filas, un resultado que parece válido pero no significa
    nada: no es que ningún hogar tenga carencias, es que no se preguntó.
    Ese número entraba después al índice de desarrollo territorial como si
    fuera un dato real. Se prefiere fallar fuerte y explícito (que quien
    llama decida cómo avisar que el módulo no está disponible ese año -
    ver `verificacion_catalogo.aviso_metricas_no_disponibles`) a devolver
    un número que parece un cálculo real y no lo es.
    """
    condiciones_cols = [c for c in config.CONDICIONES_VIVIENDA_COLUMNS.values() if c in hogares_condiciones.columns]
    if not condiciones_cols:
        raise ValueError(
            "Ninguna columna del módulo de condiciones de vivienda (C5) está disponible - "
            "ese año el INE no relevó este módulo. No calcules precariedad estructural ni el "
            "índice territorial con ese componente para este año; avisá explícitamente que no "
            "está disponible en vez de mostrar un 0% que no representa nada real."
        )
    return condiciones_cols


def precariedad_estructural(hogares_condiciones: pd.DataFrame) -> dict:
    """% ponderado de hogares con al menos una carencia estructural (de las
    variables de CONDICIONES_VIVIENDA_COLUMNS disponibles este año — 12 en
    2019, 4 desde 2024). `hogares_condiciones` tiene que venir de
    `preprocessing.decode_condiciones_vivienda` (columnas ya booleanas, y
    con `ponderador_hogar` presente).

    Es un índice de conteo de carencias ("≥1 carencia = vivienda
    deficitaria"), la práctica estándar para agregar variables de
    deficiencia booleanas de este tipo: metadatos del indicador SDG 11.1.1
    de UN-Habitat (2020, "durability of housing"), el Adequate Housing
    Index del Banco Mundial (Bramati et al., Policy Research Working Paper
    9830, 2021), y el criterio operacional de NBI-vivienda del INE Uruguay
    (Atlas Sociodemográfico y de la Desigualdad del Uruguay, Fascículo 1,
    coord. Calvo, 2013): basta una carencia crítica para clasificar la
    vivienda como deficitaria, sin necesidad de un puntaje ponderado por
    dimensión — el % de hogares en esa situación sí se pondera por
    muestreo, como cualquier otra estadística de Hogares.
    """
    condiciones_cols = _condiciones_vivienda_disponibles(hogares_condiciones)
    df = hogares_condiciones.assign(_tiene_carencia=hogares_condiciones[condiciones_cols].any(axis=1))
    total = len(df)
    con_carencia = int(df["_tiene_carencia"].sum())
    return {
        "pct_con_carencia": pct_ponderado(df, "_tiene_carencia"),
        "total_hogares": total,
        "hogares_con_carencia": con_carencia,
    }


def precariedad_estructural_por(hogares_condiciones: pd.DataFrame, columna_grupo: str) -> pd.DataFrame:
    """% ponderado de hogares con al menos una carencia estructural (mismo
    criterio que `precariedad_estructural`), agrupado por una columna
    cualquiera (nivel económico, departamento).
    """
    condiciones_cols = _condiciones_vivienda_disponibles(hogares_condiciones)
    df = hogares_condiciones.copy()
    df["_tiene_carencia"] = df[condiciones_cols].any(axis=1)
    resumen = pct_ponderado_por(df, columna_grupo, "_tiene_carencia", "ponderador_hogar")
    return resumen.rename(columns={"pct": "pct_precariedad"})


def carencias_estructurales_mas_frecuentes(hogares_condiciones: pd.DataFrame) -> pd.DataFrame:
    """% ponderado de hogares con cada carencia estructural puntual (de las
    disponibles este año), de mayor a menor — para identificar cuáles son
    las más comunes, no solo si hay o no al menos una (eso ya lo responde
    `precariedad_estructural`).
    """
    condiciones_cols = _condiciones_vivienda_disponibles(hogares_condiciones)
    filas = [
        {"carencia_codigo": col, "pct_hogares": pct_ponderado(hogares_condiciones, col)}
        for col in condiciones_cols
    ]
    resumen = pd.DataFrame(filas)
    resumen["carencia"] = resumen["carencia_codigo"].map(config.CONDICION_VIVIENDA_LABELS)
    return resumen[["carencia", "pct_hogares"]].sort_values("pct_hogares", ascending=False).reset_index(drop=True)


def ingreso_hogar_mediano_por_departamento(hogares: pd.DataFrame, departamentos: list) -> pd.Series:
    """Ingreso típico (mediana ponderada, más robusta a valores extremos
    que el promedio) del hogar, sin valor locativo, para los departamentos
    indicados. No requiere filtrar a Montevideo — usa la tabla de hogares
    completa.

    No pertenece a ninguna métrica del catálogo fijo — existe (con su test
    y su gráfica, `viz.plot_ingreso_hogar_departamento`) para las métricas
    a medida del paso 6: "ingreso por departamento" es un pedido natural, y
    tenerlo ya escrito y ponderado evita que el modelo lo reinvente mal.
    """
    subset = hogares[hogares["departamento"].isin(departamentos)]
    # Sin include_groups=False a propósito (requiere pandas>=2.2; el
    # proyecto declara pandas>=2.0) - en pandas 2.2+ tira un
    # DeprecationWarning inofensivo, la función solo usa las dos columnas
    # que necesita explícitamente.
    resultado = subset.groupby("departamento").apply(
        lambda g: mediana_ponderada(g["ingreso_hogar"], g["ponderador_hogar"])
    )
    return resultado.round(0)


def diferencia_entre_categorias(
    resumen: pd.DataFrame, columna_grupo: str, categoria_a, categoria_b, columna_valor: str
) -> float:
    """Diferencia en puntos porcentuales (categoria_a menos categoria_b) para
    dos categorías cualquiera de una misma tabla ya calculada (ej. el
    quintil de ingreso más rico contra el más pobre, en una tabla armada con
    `inseguridad_alimentaria_por`). Mismo patrón que `brecha_por_grupo` y
    `condiciones_vivienda_diferencia`, pero para tablas con una sola columna
    de valor por categoría en vez de una columna por grupo.

    Este número no reemplaza la gráfica: armar un `visualization.plot_dumbbell`
    con los dos valores originales de `tabla` (no solo esta diferencia), para
    no perder cuánto vale cada categoría por separado — ver
    docs/CONVENCIONES_DE_GRAFICAS.md.
    """
    tabla = resumen.set_index(columna_grupo)
    return round(tabla.loc[categoria_a, columna_valor] - tabla.loc[categoria_b, columna_valor], 2)


def prevalencia_inseguridad_alimentaria(fies_clasificado: pd.DataFrame) -> dict:
    """% de hogares (ponderado por `ponderador_fies`, no por el ponderador
    general de la encuesta) en inseguridad alimentaria moderada-o-severa y
    severa, a nivel nacional. FIES cubre una submuestra de hogares, no el
    total del año — este cálculo ya lo tiene en cuenta vía el ponderador.
    """
    total_ponderado = fies_clasificado["ponderador_fies"].sum()
    moderada_o_severa = (
        fies_clasificado.loc[fies_clasificado["inseguridad_moderada_o_severa"], "ponderador_fies"].sum()
        / total_ponderado * 100
    )
    severa = (
        fies_clasificado.loc[fies_clasificado["inseguridad_severa"], "ponderador_fies"].sum()
        / total_ponderado * 100
    )
    return {"moderada_o_severa": round(moderada_o_severa, 2), "severa": round(severa, 2)}


def inseguridad_alimentaria_por(
    fies_clasificado: pd.DataFrame, columna_grupo: str, columna_clasificacion: str = "inseguridad_moderada_o_severa"
) -> pd.DataFrame:
    """% de hogares en inseguridad alimentaria (ponderado por `ponderador_fies`),
    agrupado por una columna cualquiera (ej. quintil de ingreso, región).
    `columna_clasificacion` permite reutilizar la función tanto para
    moderada-o-severa como para severa.
    """
    df = fies_clasificado.copy()
    df["_ponderador_positivo"] = df["ponderador_fies"].where(df[columna_clasificacion], 0.0)
    resumen = df.groupby(columna_grupo).agg(
        total_ponderado=("ponderador_fies", "sum"),
        positivo_ponderado=("_ponderador_positivo", "sum"),
    )
    resumen["pct_inseguridad"] = (resumen["positivo_ponderado"] / resumen["total_ponderado"] * 100).round(2)
    return resumen[["pct_inseguridad"]].reset_index()


def tasas_actividad_empleo_desempleo(empleo: pd.DataFrame) -> dict:
    """Tasas de actividad, empleo y desempleo (definiciones estándar del
    INE), ponderadas por `ponderador_empleo`. Se calculan mes a mes y se
    promedian entre los 12 meses — nunca sobre el pool de los 12 CSV juntos,
    porque cada hogar permanece en el panel 6 meses seguidos y eso pesaría
    de más a quien lleva más tiempo en la muestra (ver nota en config.py).
    Tasa de desempleo = desocupados / (ocupados + desocupados), no sobre el
    total de personas.
    """
    df = empleo.copy()
    df["_ocupado_pond"] = df["ponderador_empleo"].where(df["condicion_actividad"] == "Ocupados", 0.0)
    df["_desocupado_pond"] = df["ponderador_empleo"].where(df["condicion_actividad"] == "Desocupados", 0.0)
    df["_activo_pond"] = df["ponderador_empleo"].where(
        df["condicion_actividad"].isin(["Ocupados", "Desocupados"]), 0.0
    )

    por_mes = df.groupby("mes").agg(
        total=("ponderador_empleo", "sum"),
        ocupados=("_ocupado_pond", "sum"),
        desocupados=("_desocupado_pond", "sum"),
        activos=("_activo_pond", "sum"),
    )
    por_mes["tasa_actividad"] = por_mes["activos"] / por_mes["total"] * 100
    por_mes["tasa_empleo"] = por_mes["ocupados"] / por_mes["total"] * 100
    por_mes["tasa_desempleo"] = por_mes["desocupados"] / por_mes["activos"] * 100

    return {
        "tasa_actividad": round(por_mes["tasa_actividad"].mean(), 2),
        "tasa_empleo": round(por_mes["tasa_empleo"].mean(), 2),
        "tasa_desempleo": round(por_mes["tasa_desempleo"].mean(), 2),
    }


def tasas_actividad_empleo_desempleo_por(empleo: pd.DataFrame, columna_grupo: str) -> pd.DataFrame:
    """Igual que `tasas_actividad_empleo_desempleo`, pero desagregado por una
    columna cualquiera (`sexo_grupo`, `grupo_edad_laboral`) — sirve tanto
    para la brecha de género como para comparar el desempleo juvenil contra
    el resto. Mismo cálculo mes a mes y promedio entre los 12 meses, ahora
    dentro de cada grupo.
    """
    df = empleo.copy()
    df["_ocupado_pond"] = df["ponderador_empleo"].where(df["condicion_actividad"] == "Ocupados", 0.0)
    df["_desocupado_pond"] = df["ponderador_empleo"].where(df["condicion_actividad"] == "Desocupados", 0.0)
    df["_activo_pond"] = df["ponderador_empleo"].where(
        df["condicion_actividad"].isin(["Ocupados", "Desocupados"]), 0.0
    )

    por_mes_grupo = df.groupby(["mes", columna_grupo]).agg(
        total=("ponderador_empleo", "sum"),
        ocupados=("_ocupado_pond", "sum"),
        desocupados=("_desocupado_pond", "sum"),
        activos=("_activo_pond", "sum"),
    )
    por_mes_grupo["tasa_actividad"] = por_mes_grupo["activos"] / por_mes_grupo["total"] * 100
    por_mes_grupo["tasa_empleo"] = por_mes_grupo["ocupados"] / por_mes_grupo["total"] * 100
    por_mes_grupo["tasa_desempleo"] = por_mes_grupo["desocupados"] / por_mes_grupo["activos"] * 100

    resumen = por_mes_grupo.groupby(columna_grupo)[["tasa_actividad", "tasa_empleo", "tasa_desempleo"]].mean().round(2)
    return resumen.reset_index()


def tasas_actividad_empleo_desempleo_por_anio(tasas_por_anio: dict[int, dict]) -> pd.DataFrame:
    """Combina resultados ya calculados de `tasas_actividad_empleo_desempleo`
    (uno por año, ej. `{2019: {...}, 2024: {...}, 2025: {...}}`, cada dict
    con `tasa_actividad`/`tasa_empleo`/`tasa_desempleo`) en una sola tabla
    con el año como columna, para comparar la evolución entre corridas de
    años que no necesariamente son consecutivos.

    A propósito NO trata a "año" como una categoría más: la columna queda
    numérica (`int`), para que `visualization.plot_tasas_por_anio` la
    grafique en su escala real — 2019 a 2024 son 5 años de salto, 2024 a
    2025 es apenas 1, y esa diferencia tiene que verse en el gráfico. Un
    eje categórico (o una línea que trata cada año como "el siguiente
    punto", parejo espaciado) sugeriría visualmente una tendencia continua
    que no se midió en los años sin encuesta — la misma falacia, en
    espíritu, que ya evita `docs/METODOLOGIA.md` para otros casos.
    """
    filas = [{"anio": anio, **valores} for anio, valores in sorted(tasas_por_anio.items())]
    return pd.DataFrame(filas)


def tabla_a_dict(tabla: pd.DataFrame, columna_indice: str, columna_valor: str) -> dict:
    """Convierte una tabla de una sola columna de valor por categoría (ej.
    el resultado de `tipos_hogar_resumen`, índice=tipo_hogar,
    valor=pct_hogares) en el dict `{categoría: valor}` que
    `combinar_por_anio` espera para el caso de "más de una serie" — para
    poder comparar entre 3 años o más una métrica que a nivel de un solo
    año se ve como tabla, no como dict. Antes esta conversión se
    reescribía a mano en cada notebook; ahora es una función real, con
    test, en vez de un fragmento que se reinventaba cada corrida.
    """
    return tabla.set_index(columna_indice)[columna_valor].to_dict()


def combinar_por_anio(valores_por_anio: dict[int, float | dict]) -> pd.DataFrame:
    """Generaliza `tasas_actividad_empleo_desempleo_por_anio` a cualquier
    métrica del catálogo, no solo a las tasas de Empleo: combina un
    resultado ya calculado, una vez por año (`{2019: 8.14, 2024: 12.99,
    2025: 14.14}` para una métrica de un solo número, o `{2019: {...},
    2024: {...}}` para una con varias series, como jefatura por sexo) en
    una sola tabla con el año como columna numérica — para graficar la
    evolución entre 3 años o más (no necesariamente consecutivos) con
    `visualization.plot_serie_por_anio`. Para exactamente 2 años, usar en
    cambio `diferencia_entre_tablas` + `visualization.plot_dumbbell` (ver
    `docs/CONVENCIONES_DE_GRAFICAS.md`) — es la práctica recomendada por
    sobre una línea de dos puntos.

    Mismo criterio que la función que generaliza: el año queda numérico
    (`int`), nunca una categoría, por la misma razón (ver el docstring de
    `tasas_actividad_empleo_desempleo_por_anio`).
    """
    filas = []
    for anio, valor in sorted(valores_por_anio.items()):
        fila: dict = {"anio": anio}
        if isinstance(valor, dict):
            fila.update(valor)
        else:
            fila["valor"] = valor
        filas.append(fila)
    return pd.DataFrame(filas)


def brecha_por_grupo(resumen_por_grupo: pd.DataFrame, columna_grupo: str, grupo_a: str, grupo_b: str) -> pd.Series:
    """Diferencia en puntos porcentuales (grupo_a menos grupo_b) de cada
    tasa, a partir de una tabla ya calculada con
    `tasas_actividad_empleo_desempleo_por` — mismo patrón que
    `condiciones_vivienda_diferencia`, para el texto de síntesis.
    """
    tabla = resumen_por_grupo.set_index(columna_grupo)
    columnas_tasas = [c for c in tabla.columns if c.startswith("tasa_")]
    return (tabla.loc[grupo_a, columnas_tasas] - tabla.loc[grupo_b, columnas_tasas]).round(2)


def tasa_mensual_promedio_por(
    df: pd.DataFrame, columna_grupo: str, columna_positivo: str, columna_ponderador: str = "ponderador_empleo"
) -> pd.DataFrame:
    """% ponderado de `columna_positivo` (una columna booleana), agrupado
    por `columna_grupo`, calculado mes a mes y promediado entre los 12
    meses — misma lógica que `tasas_actividad_empleo_desempleo`, pero
    genérica para reutilizar en cualquier corte (departamento, nivel
    educativo, sexo). El `df` que se le pasa ya tiene que venir filtrado al
    universo correcto (ej. solo Ocupados, para informalidad o subempleo).
    """
    df = df.copy()
    df["_positivo_pond"] = df[columna_ponderador].where(df[columna_positivo], 0.0)
    por_mes_grupo = df.groupby(["mes", columna_grupo]).agg(
        total=(columna_ponderador, "sum"),
        positivo=("_positivo_pond", "sum"),
    )
    por_mes_grupo["pct"] = por_mes_grupo["positivo"] / por_mes_grupo["total"] * 100
    resumen = por_mes_grupo.groupby(columna_grupo)["pct"].mean().round(2).reset_index()
    return resumen.rename(columns={"pct": "pct_promedio"})


def composicion_categorica_por_mes_promedio(
    df: pd.DataFrame, columna_grupo: str, columna_categoria: str, columna_ponderador: str = "ponderador_empleo"
) -> pd.DataFrame:
    """% ponderado de cada categoría de `columna_categoria` (una variable con
    más de dos valores posibles, ej. situación ocupacional:
    patrón/cuentapropista/asalariado), dentro de cada `columna_grupo`,
    calculado mes a mes y promediado entre los 12 meses — mismo patrón que
    `tasas_actividad_empleo_desempleo_por` y `tasa_mensual_promedio_por`,
    generalizado a una variable categórica de más de dos valores en vez de
    un booleano. Cada fila (grupo) del resultado suma ~100%, apta para
    graficar con barras 100% apiladas.
    """
    df = df.copy()
    total_pond_mes_grupo = df.groupby(["mes", columna_grupo])[columna_ponderador].transform("sum")
    df["_pct_pond"] = df[columna_ponderador] / total_pond_mes_grupo * 100
    por_mes = df.groupby(["mes", columna_grupo, columna_categoria])["_pct_pond"].sum().reset_index()
    resumen = por_mes.groupby([columna_grupo, columna_categoria])["_pct_pond"].mean().round(2)
    return resumen.unstack(columna_categoria).fillna(0.0)


def pct_ponderado_por(df: pd.DataFrame, columna_grupo: str, columna_positivo: str, columna_ponderador: str) -> pd.DataFrame:
    """% ponderado de `columna_positivo` (booleana), agrupado por
    `columna_grupo` — sin promedio mensual, a diferencia de
    `tasa_mensual_promedio_por`. Sirve para datos que no vienen en panel
    rotativo mensual: Victimización (un corte del semestre) y, con
    `columna_ponderador="ponderador_hogar"`, cualquier estadística de
    Hogares/Personas (pobreza, hacinamiento, brecha digital, etc.).
    """
    df = df.copy()
    df["_positivo_pond"] = df[columna_ponderador].where(df[columna_positivo], 0.0)
    resumen = df.groupby(columna_grupo).agg(
        total=(columna_ponderador, "sum"),
        positivo=("_positivo_pond", "sum"),
    )
    resumen["pct"] = (resumen["positivo"] / resumen["total"] * 100).round(2)
    return resumen[["pct"]].reset_index()


def pct_ponderado(df: pd.DataFrame, columna_positivo: str, columna_ponderador: str = "ponderador_hogar") -> float:
    """% ponderado de `columna_positivo` (booleana) a nivel nacional/del
    universo completo de `df` — versión sin agrupar de `pct_ponderado_por`,
    para el mismo caso a nivel de un solo número (ej. % de hogares pobres
    en todo el país).
    """
    positivo_pond = df[columna_ponderador].where(df[columna_positivo], 0.0)
    return round(positivo_pond.sum() / df[columna_ponderador].sum() * 100, 2)


def media_ponderada_por(
    df: pd.DataFrame, columna_grupo: str, columna_valor: str, columna_ponderador: str = "ponderador_hogar"
) -> pd.DataFrame:
    """Media ponderada de `columna_valor` (numérica), agrupada por
    `columna_grupo` — mismo criterio de ponderación que `pct_ponderado_por`,
    para una variable continua en vez de una proporción (ej. estrato
    socioeconómico promedio, índice de acceso digital promedio).
    """
    df = df.copy()
    df["_valor_pond"] = df[columna_valor] * df[columna_ponderador]
    resumen = df.groupby(columna_grupo, observed=True).agg(
        _total_pond=(columna_ponderador, "sum"),
        _valor_pond=("_valor_pond", "sum"),
    )
    resumen["media"] = (resumen["_valor_pond"] / resumen["_total_pond"]).round(2)
    return resumen[["media"]].reset_index()


def proporcion_ponderada(
    df: pd.DataFrame, columna_categoria: str, columna_ponderador: str = "ponderador_hogar"
) -> pd.DataFrame:
    """% ponderado de cada categoría de `columna_categoria` sobre el total
    — equivalente ponderado de `serie.value_counts(normalize=True)`, para
    variables con más de dos categorías (ej. tipo de hogar).
    """
    resumen = (
        df.groupby(columna_categoria, observed=True)[columna_ponderador]
        .sum()
        .div(df[columna_ponderador].sum())
        .mul(100)
        .round(2)
        .rename("pct")
        .reset_index()
    )
    return resumen.sort_values("pct", ascending=False).reset_index(drop=True)


def composicion_categorica_ponderada_por(
    df: pd.DataFrame, columna_grupo: str, columna_categoria: str, columna_ponderador: str = "ponderador_hogar"
) -> pd.DataFrame:
    """% ponderado de cada categoría de `columna_categoria` (más de dos
    valores posibles), dentro de cada `columna_grupo` — versión sin panel
    mensual de `composicion_categorica_por_mes_promedio`, para datos de
    Hogares que no vienen en panel rotativo. Cada fila (grupo) del
    resultado suma ~100%, apta para graficar con barras 100% apiladas o
    heatmap (ej. calidad de conexión por nivel económico — ver
    `calidad_conexion_por`).
    """
    total_pond_grupo = df.groupby(columna_grupo, observed=True)[columna_ponderador].transform("sum")
    df = df.assign(_pct_pond=df[columna_ponderador] / total_pond_grupo * 100)
    resumen = df.groupby([columna_grupo, columna_categoria], observed=True)["_pct_pond"].sum().round(2)
    return resumen.unstack(columna_categoria).fillna(0.0)


def calidad_conexion_por(df_con_calidad: pd.DataFrame, columna_grupo: str) -> pd.DataFrame:
    """% ponderado de cada nivel de calidad de conexión (Sin conexión /
    Solo móvil / Banda ancha fija — ver
    `preprocessing.clasificar_calidad_conexion`), dentro de cada categoría
    de `columna_grupo` (en la práctica, siempre nivel económico). Apta
    para `visualization.plot_calidad_conexion_por` (barras 100% apiladas).
    """
    return composicion_categorica_ponderada_por(df_con_calidad, columna_grupo, "calidad_conexion")


def mediana_ponderada(valores: pd.Series, pesos: pd.Series) -> float:
    """Mediana ponderada: el valor donde el peso acumulado (ordenando de
    menor a mayor) cruza el 50% del peso total — a diferencia de una
    media ponderada, no hay una fórmula cerrada simple, hay que ordenar y
    acumular. Más robusta a valores extremos que una media, igual que la
    mediana simple ya lo es (ver `ingreso_hogar_mediano_por_departamento`).

    Si el peso acumulado pasa por EXACTAMENTE la mitad del total (empate),
    la mediana es el promedio de ese valor y el siguiente — mismo criterio
    que la mediana simple para una cantidad par de valores con igual peso
    (si no se hiciera este ajuste, pesos uniformes no coincidirían con
    `pd.Series.median()`).
    """
    orden = valores.sort_values().index
    valores_ordenados = valores.loc[orden].reset_index(drop=True)
    pesos_ordenados = pesos.loc[orden].reset_index(drop=True)
    peso_acumulado = pesos_ordenados.cumsum()
    punto_medio = pesos_ordenados.sum() / 2

    empate = peso_acumulado[peso_acumulado == punto_medio].index
    if len(empate) > 0 and empate[0] + 1 < len(valores_ordenados):
        i = empate[0]
        return float((valores_ordenados.iloc[i] + valores_ordenados.iloc[i + 1]) / 2)

    idx = peso_acumulado[peso_acumulado >= punto_medio].index[0]
    return float(valores_ordenados.iloc[idx])


def grupos_con_muestra_chica(df: pd.DataFrame, columna_grupo: str, n_minimo: int = 30) -> pd.Series:
    """Cuenta cuántas filas hay por cada valor de `columna_grupo` en `df`
    (conteo de la MUESTRA, sin ponderar — la ponderación corrige la
    representatividad, no el tamaño real de muestra detrás de cada
    estimación) y devuelve solo los grupos con menos de `n_minimo`
    observaciones. Serie vacía si ningún grupo está por debajo del umbral.

    Operacionaliza la regla de "celdas chicas" de docs/METODOLOGIA.md,
    sección 2: antes de reportar cualquier métrica "por" algo (nivel
    económico, departamento, tipo de delito, etc.), correr esto sobre el
    dataframe ANTES de agrupar. n=30 es el umbral clásico usado por
    institutos de estadística (INE incluido) para desconfiar de una
    estimación — no hay una regla universal más precisa sin conocer el
    diseño muestral completo. Si algún grupo aparece acá, aclarar en el
    texto que esa estimación puntual tiene poca base muestral, no
    ocultarlo ni tratarlo como un número más.
    """
    conteo = df[columna_grupo].value_counts()
    return conteo[conteo < n_minimo].sort_values()


def grupos_con_pocos_casos(df: pd.DataFrame, columna_grupo: str, columna_positivo: str, n_minimo: int = 30) -> pd.Series:
    """Como `grupos_con_muestra_chica`, pero contando los CASOS POSITIVOS de
    la muestra por grupo (filas donde `columna_positivo` es verdadera), no
    el tamaño del grupo. Devuelve los grupos con menos de `n_minimo` casos.

    Es la regla que corresponde a un evento raro: la precisión de un
    porcentaje chico depende de cuántos casos lo sostienen, no de cuánta
    gente se encuestó. En la corrida real de 2024, la victimización por
    departamento tenía 694 personas en Cerro Largo y 0 víctimas, y 229 en
    Flores con 3 víctimas: `grupos_con_muestra_chica` no marcaba ninguno
    (todos superan las 30 personas) y el informe afirmaba que la
    victimización «va de 0,0% (Cerro Largo) a 7,7% (Treinta y Tres)» sobre
    un puñado de casos. Ver docs/METODOLOGIA.md, sección 2 (celdas chicas).
    """
    positivos = df.loc[df[columna_positivo].astype(bool), columna_grupo].value_counts()
    conteo = positivos.reindex(df[columna_grupo].unique(), fill_value=0)
    return conteo[conteo < n_minimo].sort_values()


def diferencia_entre_tablas(
    tabla_a: pd.DataFrame, tabla_b: pd.DataFrame, columna_indice: str, columna_valor: str
) -> pd.Series:
    """Diferencia en puntos porcentuales (tabla_a menos tabla_b) para la
    misma columna de valor, cruzando dos tablas por su columna de índice
    (ej. comunicación a la policía vs denuncia formal, ambas por tipo de
    delito) — mismo patrón que `condiciones_vivienda_diferencia` y
    `brecha_por_grupo`.

    Este número no reemplaza la gráfica: armar un `visualization.plot_dumbbell`
    con `tabla_a` y `tabla_b` completas (no solo esta diferencia), una fila
    por categoría de `columna_indice` — ver docs/CONVENCIONES_DE_GRAFICAS.md.
    """
    a = tabla_a.set_index(columna_indice)[columna_valor]
    b = tabla_b.set_index(columna_indice)[columna_valor]
    return (a - b).round(2)


# ============================================================================
# Hogares (composición, sin tecnología) y Brecha Digital (con marco
# internacional) — ver la nota de fuentes en config.py y el detalle
# metodológico en .claude/instrucciones/encuesta-hogares.md.
# ============================================================================

def pct_pobres_indigentes(hogares_extendido: pd.DataFrame) -> dict:
    """% ponderado de hogares pobres y % en indigencia (el grado más
    severo, un subconjunto de los pobres)."""
    return {
        "pct_pobres": pct_ponderado(hogares_extendido, "pobre"),
        "pct_indigentes": pct_ponderado(hogares_extendido, "indigente"),
    }


def tasa_jefatura_femenina(tipo_hogar: pd.DataFrame) -> dict:
    """% ponderado de hogares cuyo jefe/a es mujer, sobre el total de
    hogares con jefatura identificada. Indicador estándar CEPAL/CELADE."""
    con_jefatura = tipo_hogar[tipo_hogar["jefe_sexo"].notna()].copy()
    con_jefatura["_es_mujer"] = con_jefatura["jefe_sexo"] == "2-Mujer"
    total = int(len(con_jefatura))
    return {"pct_jefatura_femenina": pct_ponderado(con_jefatura, "_es_mujer"), "total_hogares": total}


def tipos_hogar_resumen(tipo_hogar: pd.DataFrame) -> pd.DataFrame:
    """% ponderado de hogares de cada tipo (Unipersonal/Nuclear/Extendido/
    Compuesto/Sin núcleo — ver preprocessing.clasificar_tipo_hogar), de
    mayor a menor."""
    resumen = proporcion_ponderada(tipo_hogar, "tipo_hogar")
    return resumen.rename(columns={"pct": "pct_hogares"})


def pct_hacinamiento_por(hogares_hacinamiento: pd.DataFrame, columna_grupo: str) -> pd.DataFrame:
    """% ponderado de hogares en situación de hacinamiento (ver
    preprocessing.compute_hacinamiento), agrupado por una columna cualquiera."""
    resumen = pct_ponderado_por(hogares_hacinamiento, columna_grupo, "hacinado", "ponderador_hogar")
    return resumen.rename(columns={"pct": "pct_hacinamiento"})


def razon_dependencia_demografica(personas: pd.DataFrame) -> float:
    """(menores de 15 + mayores de 65) / población en edad activa (15-64) x 100,
    ponderado por `ponderador_hogar` (llega a Personas vía
    `preprocessing.merge_personas`). Indicador demográfico estándar
    CEPAL/CELADE — es una relación *potencial* (por edad), no mide
    actividad económica real."""
    pond = personas["ponderador_hogar"]
    menores = pond.where(personas["edad"] < 15, 0.0).sum()
    mayores = pond.where(personas["edad"] >= 65, 0.0).sum()
    activos = pond.where(personas["edad"].between(15, 64), 0.0).sum()
    return round((menores + mayores) / activos * 100, 2)


def razon_dependencia_por(personas_con_grupo: pd.DataFrame, columna_grupo: str) -> pd.DataFrame:
    """Razón de dependencia demográfica ponderada (ver
    `razon_dependencia_demografica`), agrupada por una columna cualquiera
    (ej. departamento)."""
    filas = []
    for grupo, sub in personas_con_grupo.groupby(columna_grupo):
        razon = razon_dependencia_demografica(sub) if sub["ponderador_hogar"].sum() > 0 else None
        filas.append({columna_grupo: grupo, "razon_dependencia": razon})
    return pd.DataFrame(filas)


def pct_pobres_por(hogares_nacional: pd.DataFrame, columna_grupo: str) -> pd.DataFrame:
    """% ponderado de hogares pobres, por una columna cualquiera (ej.
    departamento) — mismo criterio que `pct_pobres_indigentes`. Componente
    del índice de desarrollo territorial (ver `indice_desarrollo_territorial`).
    """
    resumen = pct_ponderado_por(hogares_nacional, columna_grupo, "pobre", "ponderador_hogar")
    return resumen.rename(columns={"pct": "pct_pobres"})


def estrato_promedio_por(hogares: pd.DataFrame, columna_grupo: str) -> pd.DataFrame:
    """Estrato socioeconómico promedio ponderado (1 a 5, más alto = mejor
    posición relativa), por una columna cualquiera (ej. departamento).
    Componente del índice de desarrollo territorial (ver
    `indice_desarrollo_territorial`).
    """
    resumen = media_ponderada_por(hogares, columna_grupo, "estrato_tipo")
    return resumen.rename(columns={"media": "estrato_promedio"})


def indice_desarrollo_territorial(componentes: pd.DataFrame, invertir: list) -> pd.DataFrame:
    """Índice sintético 0-1 por unidad territorial, combinando varias
    dimensiones ya calculadas (ej. pobreza, empleo, precariedad de
    vivienda, estrato) en un único indicador comparable. Una métrica
    territorial "de verdad" sintetiza varias dimensiones a la vez, en vez
    de ser la misma tasa de siempre solo cortada por departamento — mismo
    método (normalización min-max con polaridad ajustada: los indicadores
    "negativos" se invierten antes de promediar) que el Índice de
    Desarrollo Regional de CEPAL/ILPES ("Panorama del desarrollo
    territorial de América Latina y el Caribe", 2010-2024, siguiendo la
    "Guía metodológica para el diseño de indicadores compuestos de
    desarrollo sostenible", CEPAL, 2009) y el IDERE-UY (Rodríguez Miranda,
    Vial Cossani, Centurión y Pérez Fernández, IECON-FCEA/UdelaR,
    financiado por ANII Fondo María Viñas, 2024) — el antecedente directo
    para Uruguay, construido también a nivel de los 19 departamentos.

    `componentes`: indexado por la unidad territorial (ej. departamento),
    una columna por dimensión ya calculada (sin la columna de
    agrupación). `invertir`: nombres de columna donde un valor más alto
    es peor (ej. pobreza, precariedad) — se invierten antes de
    normalizar, para que en el resultado "más alto" siempre signifique
    "mejor" en todas las dimensiones.

    Devuelve las dimensiones normalizadas 0-1 (0 = peor unidad territorial
    en esa dimensión, 1 = mejor) más una columna "indice" con su
    promedio, ordenado de mejor a peor.
    """
    normalizado = pd.DataFrame(index=componentes.index)
    for columna in componentes.columns:
        valores = componentes[columna]
        if columna in invertir:
            valores = valores.max() - valores
        rango = valores.max() - valores.min()
        normalizado[columna] = ((valores - valores.min()) / rango).round(3) if rango > 0 else 0.5
    normalizado["indice"] = normalizado[list(componentes.columns)].mean(axis=1).round(3)
    return normalizado.sort_values("indice", ascending=False)


def pct_unipersonales_mayores(tipo_hogar: pd.DataFrame) -> dict:
    """De los hogares unipersonales, qué % ponderado tiene 65 años o más
    (su único integrante es, por definición, el jefe/a). CEPAL: en América
    Latina esto puede señalar vulnerabilidad, a diferencia de países
    desarrollados donde suele leerse como autonomía — ver nota en
    .claude/instrucciones/encuesta-hogares.md."""
    unipersonales = tipo_hogar[tipo_hogar["tipo_hogar"] == "Unipersonal"].copy()
    total = len(unipersonales)
    if not total:
        return {"pct_unipersonales_mayores": 0.0, "total_unipersonales": 0}
    unipersonales["_es_mayor"] = unipersonales["jefe_edad"] >= 65
    return {
        "pct_unipersonales_mayores": pct_ponderado(unipersonales, "_es_mayor"),
        "total_unipersonales": total,
    }


def brecha_digital_por_cohorte(df_extendido_con_cohorte: pd.DataFrame) -> pd.DataFrame:
    """% ponderado de penetración de cada tecnología, por cohorte
    generacional del jefe/a de hogar (ver
    preprocessing.compute_cohorte_generacional). Mismo cálculo que
    `brecha_digital_por_nivel_economico`, agrupado por cohorte."""
    return _brecha_digital_por(df_extendido_con_cohorte, "cohorte")


def brecha_digital_por_jefatura(df_extendido_con_jefatura: pd.DataFrame) -> pd.DataFrame:
    """% ponderado de penetración de cada tecnología, según si el hogar
    tiene jefe o jefa mujer. CEPAL documenta que en la región la brecha de
    género ya casi no está en la tenencia del hogar sino en el uso
    individual — no encontrar diferencia acá es un resultado consistente
    con esa literatura, no un resultado vacío (ver
    .claude/instrucciones/encuesta-hogares.md)."""
    return _brecha_digital_por(df_extendido_con_jefatura, "jefe_sexo")


def indice_acceso_digital_por(df_con_indice: pd.DataFrame, columna_grupo: str) -> pd.DataFrame:
    """Promedio ponderado del índice de acceso digital (0-4, ver
    preprocessing.compute_indice_acceso_digital), agrupado por una columna
    cualquiera."""
    resumen = media_ponderada_por(df_con_indice, columna_grupo, "indice_acceso_digital")
    return resumen.rename(columns={"media": "indice_promedio"})


def adopcion_tablet_ibirapita_por(hogares_extendido: pd.DataFrame, columna_grupo: str) -> pd.DataFrame:
    """% ponderado de hogares con tablet del Plan Ibirapitá (programa
    estatal de inclusión digital para personas mayores), agrupado por una
    columna cualquiera (ej. si el jefe/a de hogar es adulto mayor).

    `tiene_tablet_ibirapita` sale de `decode_si_no` en dtype `object`
    (True/False/NaN) — se pasa el "sin dato" a `False` antes de ponderar
    (mismo criterio que ya usa `compute_indice_acceso_digital`: un "sin
    dato" cuenta como que no tiene la tablet, no se descarta el hogar
    entero).
    """
    df = hogares_extendido.assign(tiene_tablet_ibirapita=hogares_extendido["tiene_tablet_ibirapita"].eq(True))
    resumen = pct_ponderado_por(df, columna_grupo, "tiene_tablet_ibirapita", "ponderador_hogar")
    return resumen.rename(columns={"pct": "pct_con_tablet"})
