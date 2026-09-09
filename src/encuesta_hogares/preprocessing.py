"""Limpieza, clasificación y combinación de las bases de Hogares y Personas."""

import pandas as pd

from . import config


def classify_nivel_economico(estrato_tipo: pd.Series) -> pd.Series:
    """Clasifica el estrato socioeconómico (1-5) en una etiqueta legible."""
    return (
        estrato_tipo.astype("Int64")
        .map(config.NIVEL_ECONOMICO_LABELS)
        .fillna(config.NIVEL_ECONOMICO_DEFAULT)
    )


def classify_sexo(sexo: pd.Series) -> pd.Series:
    """Clasifica el sexo (1/2) en una etiqueta legible."""
    return sexo.astype("Int64").map(config.SEXO_LABELS).fillna(config.SEXO_DEFAULT)


def classify_edad_grupo(edad: pd.Series) -> pd.Series:
    """Agrupa la edad en tramos: niños/jóvenes, adultos y adultos mayores."""
    return pd.cut(edad, bins=config.EDAD_BINS, labels=config.EDAD_LABELS, right=False)


def normalizar_departamento(df: pd.DataFrame) -> pd.DataFrame:
    """Deja "departamento" en mayúsculas, consistente entre años — no se
    escribe igual en todos ("MONTEVIDEO" en el .sav de 2019, "Montevideo"
    en el CSV combinado de 2024 en adelante). Sin esto, cruzar dos tablas
    de años distintos por departamento (para comparar cualquier métrica
    "por departamento" entre años) cruza cero filas en vez de fallar con
    un error claro — encontrado corriendo notebook_builder de verdad
    contra 2019 vs. 2024 (razón de dependencia por departamento).

    Llamar siempre apenas se carga `hogares` (o cualquier tabla derivada
    que traiga esta columna) y antes de cualquier comparación entre años
    — no solo en el camino mecánico de notebook_builder.py, también si
    se escribe el cruce a mano (paso 6 del agente).
    """
    df = df.copy()
    df["departamento"] = df["departamento"].str.upper()
    return df


def prepare_hogares_montevideo(hogares: pd.DataFrame) -> pd.DataFrame:
    """Filtra los hogares de Montevideo y agrega el nivel económico.

    La comparación ignora mayúsculas/minúsculas porque el nombre del
    departamento no se escribe igual en todos los años: en los .sav de 2019
    viene como "MONTEVIDEO" y en el CSV combinado de 2024 en adelante viene
    como "Montevideo" (ver config.HOGARES_COLUMNS_CSV).
    """
    hogares_mdeo = hogares.loc[hogares["departamento"].str.upper() == "MONTEVIDEO"].copy()
    hogares_mdeo["nivel_economico"] = classify_nivel_economico(hogares_mdeo["estrato_tipo"])
    return hogares_mdeo


def merge_personas(hogares_resumen: pd.DataFrame, personas: pd.DataFrame) -> pd.DataFrame:
    """Agrega datos de las personas del hogar (edad, sexo, ingresos) a la tabla de hogares."""
    combinado = hogares_resumen.merge(personas, on="id_hogar", how="left").sort_values("id_hogar")
    combinado["edad_grupo"] = classify_edad_grupo(combinado["edad"])
    combinado["sexo_grupo"] = classify_sexo(combinado["sexo"])
    return combinado


# ============================================================================
# Ampliación: brecha digital, pobreza, vivienda, composición del hogar y
# alcance nacional. Estas funciones no filtran a Montevideo salvo que se les
# pase un dataframe ya filtrado (ver notebook).
# ============================================================================

def decode_si_no(series: pd.Series) -> pd.Series:
    """Convierte una variable 1=Sí/2=No/99=Sin dato en booleano (99 -> NaN)."""
    return series.map(config.SI_NO_MAP)


def decode_condiciones_vivienda(hogares: pd.DataFrame) -> pd.DataFrame:
    """Decodifica a booleano las columnas de condiciones estructurales de la
    vivienda que estén presentes en `hogares` (12 en 2019, 4 desde 2024 en
    adelante — ver CONDICIONES_VIVIENDA_COLUMNS_CSV). A diferencia de
    `prepare_hogares_extendido`, no filtra a Montevideo ni decodifica nada
    más — las métricas de precariedad estructural necesitan la base
    nacional completa, para poder compararse por departamento.
    """
    df = hogares.copy()
    condiciones_cols = [c for c in config.CONDICIONES_VIVIENDA_COLUMNS.values() if c in df.columns]
    for col in condiciones_cols:
        df[col] = decode_si_no(df[col])
    return df


def prepare_hogares_extendido(hogares_mdeo: pd.DataFrame) -> pd.DataFrame:
    """A partir de hogares ya filtrados (ej. Montevideo), decodifica las variables
    de tecnología, pobreza y condiciones de vivienda.
    """
    df = hogares_mdeo.copy()

    for col in ["tiene_internet", "internet_fija", "internet_movil", "tiene_pc", "tiene_streaming"]:
        df[col] = decode_si_no(df[col])
    if "tiene_tablet_ibirapita" in df.columns:
        df["tiene_tablet_ibirapita"] = decode_si_no(df["tiene_tablet_ibirapita"])

    df["pobre"] = df["pobre"] == 1.0
    df["indigente"] = df["indigente"] == 1.0

    # No todos los años tienen las 12 columnas de "problemas de la vivienda"
    # (algunas se discontinuaron a partir de 2024 — ver
    # config.CONDICIONES_VIVIENDA_COLUMNS_CSV): solo se decodifican las que
    # de verdad están presentes en este dataframe.
    condiciones_cols = [c for c in config.CONDICIONES_VIVIENDA_COLUMNS.values() if c in df.columns]
    for col in condiciones_cols:
        df[col] = decode_si_no(df[col])

    return df


# Acá vivió compute_tiene_celular_hogar (tenencia de celular por hogar,
# variable e60 de Personas). Se eliminó en la limpieza final previa a
# producción: ninguna métrica del catálogo la usaba (era un resto del
# diseño anterior al rediseño de Brecha Digital), no tenía test, y solo
# podía funcionar con datos de 2019 — el INE sacó esa pregunta del
# cuestionario desde 2024 (decisión ya confirmada con el dueño en su
# momento). Si alguna vez vuelve la pregunta al cuestionario, el patrón
# era: decode_si_no + groupby("id_hogar").any().


def prepare_fies(fies: pd.DataFrame) -> pd.DataFrame:
    """Clasifica cada hogar en inseguridad alimentaria moderada-o-severa y
    severa, según el umbral estándar de la metodología FIES (ver
    config.UMBRAL_FIES), y agrega la etiqueta legible de región.
    """
    df = fies.copy()
    df["inseguridad_moderada_o_severa"] = df["prob_inseguridad_moderada"] >= config.UMBRAL_FIES
    df["inseguridad_severa"] = df["prob_inseguridad_severa"] >= config.UMBRAL_FIES
    df["region"] = df["region_cod"].map(config.REGION_FIES_LABELS)
    df["tiene_menores_18"] = df["tiene_menores_18"] == 1
    df["tiene_menores_6"] = df["tiene_menores_6"] == 1
    return df


def prepare_empleo(empleo: pd.DataFrame) -> pd.DataFrame:
    """Mapea la condición de actividad (POBPCOAC) a las mismas categorías
    que ya usa Hogares/Personas de 2019 (Ocupados/Desocupados/Inactivos), y
    decodifica INFORMAL/SUBEMPLEO a booleano.

    **Informalidad desde 2025**: la columna `INFORMAL` (pre-calculada por
    el INE) desapareció de los archivos mensuales desde 2025 en adelante
    — verificado contra los datos reales, no una suposición. En su lugar,
    si llega `aporta_seguridad_social` (columna original `f82`, "aporte a
    fondo de pensión", que sí sigue estando), `es_informal` se deriva de
    ahí: **no aportar a la seguridad social (f82 == 2) = informal**. No es
    un criterio inventado para esta ocasión — es el mismo que usa
    `employment_restrictions()` del paquete oficial de R para la ECH, de
    autoría conjunta del INE (github.com/calcita/ech, archivo
    `R/employment.R`). Verificado además contra los datos reales de enero
    2025: con este criterio da 21.8% de informalidad entre ocupados, muy
    cerca del 22.8% que el propio INE publicó para 2025 completo (la
    diferencia es esperable — acá es un solo mes sin ponderar contra el
    año entero ponderado del INE, no un desvío del criterio).

    Si ninguna de las dos columnas llegó, `es_informal` no está en el
    resultado — cualquier métrica que la use falla ahí con un error claro,
    no con un dato inventado.

    Ojo: `es_informal`/`es_subempleo` solo tienen sentido para quien está
    en condicion_actividad == "Ocupados" — para cualquier otro caso el 0
    no significa "formal" ni "sin subempleo", significa "no aplica"
    (verificado contra los datos reales: INFORMAL=1, SUBEMPLEO=1 y
    aporta_seguridad_social=2 nunca aparecen fuera de Ocupados). Cualquier
    métrica que las use tiene que filtrar a Ocupados primero.
    """
    df = empleo.copy()
    df["condicion_actividad"] = df["condicion_actividad_cod"].map(config.POBPCOAC_GRUPOS)
    if "es_informal" in df.columns:
        df["es_informal"] = df["es_informal"] == 1
    elif "aporta_seguridad_social" in df.columns:
        df["es_informal"] = df["aporta_seguridad_social"] == 2
    if "es_subempleo" in df.columns:
        df["es_subempleo"] = df["es_subempleo"] == 1
    df["sexo_grupo"] = classify_sexo(df["sexo"])
    es_joven = df["edad"].between(config.EDAD_JOVEN_MIN, config.EDAD_JOVEN_MAX)
    df["grupo_edad_laboral"] = es_joven.map({True: "Joven (14-24)", False: "Resto"})
    return df


def prepare_victimizacion(victimizacion: pd.DataFrame) -> pd.DataFrame:
    """Agrega sexo legible y un flag de "víctima de al menos un delito"
    (cualquiera de los 5 tipos), a nivel de persona.
    """
    df = victimizacion.copy()
    df["sexo_grupo"] = classify_sexo(df["sexo"])
    columnas_delito = list(config.TIPOS_DELITO)
    df["victimizado_algun_delito"] = (df[columnas_delito] == 1).any(axis=1)
    return df


def melt_delitos(victimizacion: pd.DataFrame) -> pd.DataFrame:
    """Convierte las columnas anchas (una por tipo de delito, con sus
    sub-preguntas propias) a formato largo — una fila por persona x tipo de
    delito — para poder calcular prevalencia, comunicación a la policía,
    denuncia formal y violencia con las mismas funciones genéricas para
    cualquier tipo. `comunicacion_policia`/`denuncia_formal`/`violencia`
    solo tienen sentido para quien fue víctima de ESE delito (`victimizado`
    True) — cualquier métrica que las use tiene que filtrar primero.
    """
    partes = []
    for codigo, info in config.TIPOS_DELITO.items():
        parte = pd.DataFrame({
            "id_persona": victimizacion["id_persona"],
            "sexo_grupo": victimizacion["sexo_grupo"],
            "departamento": victimizacion["departamento"],
            "ponderador_victimizacion": victimizacion["ponderador_victimizacion"],
            "tipo_delito": info["nombre"],
            "victimizado": victimizacion[codigo] == 1,
            "comunicacion_policia": victimizacion[info["comunicacion"]] == 1,
            "denuncia_formal": victimizacion[info["denuncia"]] == 1,
            "violencia": victimizacion[info["violencia"]] == 1 if info["violencia"] else False,
        })
        partes.append(parte)
    return pd.concat(partes, ignore_index=True)


def _clasificar_tipo_hogar_codigos(codigos: set) -> str:
    """Clasifica un hogar según los códigos de parentesco (e30) de sus
    integrantes que no son el jefe/a — ver config.PARENTESCO_CODIGOS_*.
    Taxonomía CELADE: Unipersonal, Nuclear, Extendido, Compuesto, Sin núcleo.
    """
    if not codigos:
        return "Unipersonal"
    if codigos & config.PARENTESCO_CODIGOS_NO_PARIENTE:
        return "Compuesto"
    tiene_nucleo = bool(codigos & config.PARENTESCO_CODIGOS_NUCLEO)
    tiene_extenso = bool(codigos & config.PARENTESCO_CODIGOS_EXTENSO)
    if tiene_nucleo and tiene_extenso:
        return "Extendido"
    if tiene_nucleo:
        return "Nuclear"
    return "Sin núcleo"


def clasificar_tipo_hogar(personas: pd.DataFrame, hogares: pd.DataFrame) -> pd.DataFrame:
    """Clasifica cada hogar por su composición (taxonomía CELADE/CEPAL,
    ver config.PARENTESCO_LABELS) a partir de `parentesco_jefe` (e30) de
    todas las personas del hogar. Devuelve una fila por hogar con:
    - `tipo_hogar`: Unipersonal / Nuclear / Extendido / Compuesto / Sin núcleo.
    - `monoparental`: hay hijos (parentesco 3/4/5) pero no cónyuge (2).
    - `jefe_sexo` / `jefe_edad`: sexo y edad de quien tiene parentesco_jefe == 1,
      para poder cruzar tipo de hogar con jefatura sin otro merge aparte.
    - `ponderador_hogar`: traído de `hogares` (solo se usan sus columnas
      `id_hogar`/`ponderador_hogar`) — sin esto, cualquier estadística que
      use el resultado (`tipos_hogar_resumen`, `tasa_jefatura_femenina`,
      `pct_unipersonales_mayores`) quedaría sin ponderar por muestreo.
      `personas` nunca trae su propio ponderador a propósito (ver
      PERSONAS_COLUMNS en config.py) para no duplicar la columna al
      mergear con el lado de Hogares.

    No depende de ninguna variable de tecnología — es composición del hogar
    pura, según la taxonomía estándar que usa CEPAL/CELADE en toda la región.
    """
    # Vectorizado: una sola pasada de `groupby(...).any()` sobre seis
    # indicadores booleanos por persona, en vez de tres `groupby().apply`
    # con lambdas de Python fila a fila (5,7 s sobre las 55.000 personas de
    # 2025; ahora décimas de segundo — medido 2026-09-09). La taxonomía es
    # exactamente la de `_clasificar_tipo_hogar_codigos`, que se conserva
    # como definición legible y como oráculo en los tests.
    parentesco = personas["parentesco_jefe"]
    indicadores = pd.DataFrame({
        "id_hogar": personas["id_hogar"],
        "_otro": parentesco.notna() & (parentesco != 1),
        "_no_pariente": parentesco.isin(config.PARENTESCO_CODIGOS_NO_PARIENTE),
        "_nucleo": parentesco.isin(config.PARENTESCO_CODIGOS_NUCLEO),
        "_extenso": parentesco.isin(config.PARENTESCO_CODIGOS_EXTENSO),
        "_tiene_conyuge": parentesco == 2,
        "_tiene_hijos": parentesco.isin([3, 4, 5]),
    }).groupby("id_hogar").any()

    tipo = pd.Series("Sin núcleo", index=indicadores.index, dtype=object)
    tipo[indicadores["_nucleo"]] = "Nuclear"
    tipo[indicadores["_nucleo"] & indicadores["_extenso"]] = "Extendido"
    tipo[indicadores["_no_pariente"]] = "Compuesto"
    tipo[~indicadores["_otro"]] = "Unipersonal"

    resultado = indicadores.reset_index()[["id_hogar"]]
    resultado["tipo_hogar"] = tipo.to_numpy()
    resultado["monoparental"] = (indicadores["_tiene_hijos"] & ~indicadores["_tiene_conyuge"]).to_numpy()

    jefes = personas.loc[personas["parentesco_jefe"] == 1, ["id_hogar", "sexo", "edad"]].copy()
    jefes["jefe_sexo"] = classify_sexo(jefes["sexo"])
    jefes = jefes.rename(columns={"edad": "jefe_edad"})[["id_hogar", "jefe_sexo", "jefe_edad"]]
    resultado = resultado.merge(jefes, on="id_hogar", how="left")
    return resultado.merge(hogares[["id_hogar", "ponderador_hogar"]], on="id_hogar", how="left")


def compute_hacinamiento(hogares: pd.DataFrame, umbral: float = config.UMBRAL_HACINAMIENTO) -> pd.DataFrame:
    """Marca cada hogar como hacinado si tiene más de `umbral` personas por
    cuarto (`cantidad_habitaciones`, que ya excluye baño y cocina — ver
    config.py). Umbral clásico usado por INE/CEPAL para la región (no es el
    método más nuevo de umbral ajustado por composición del hogar de la
    UE/OCDE — ver la nota en config.UMBRAL_HACINAMIENTO).
    """
    df = hogares.copy()
    df["personas_por_cuarto"] = (df["total_personas"] / df["cantidad_habitaciones"]).round(2)
    df["hacinado"] = df["personas_por_cuarto"] > umbral
    return df


def compute_cohorte_generacional(hogares_con_jefe: pd.DataFrame, anio: int) -> pd.Series:
    """Aproxima la cohorte generacional del HOGAR a partir de la edad del
    jefe/a (`jefe_edad`, ver clasificar_tipo_hogar) y el año de la encuesta
    — no de cada integrante, porque las variables de tecnología de este
    proyecto (internet/PC/streaming) son del hogar, no de cada
    persona: la única variable de tenencia individual (celular, e60) se
    discontinuó en el cuestionario 2024, así que basar esto en edad
    individual rompería para ese año (ver nota de "ruido de 2019" en
    .claude/instrucciones/encuesta-hogares.md).
    """
    anio_nacimiento = anio - hogares_con_jefe["jefe_edad"]
    return pd.cut(anio_nacimiento, bins=config.COHORTE_BINS, labels=config.COHORTE_LABELS)


def clasificar_calidad_conexion(df_extendido: pd.DataFrame) -> pd.Series:
    """Clasifica la conexión de cada hogar en 3 niveles ordinales, en vez
    de la variable binaria tiene/no tiene internet: "Sin conexión", "Solo
    móvil", "Banda ancha fija" — inspirado en el estándar "Meaningful
    Connectivity" de UIT/A4AI (ver .claude/instrucciones/encuesta-hogares.md).
    Si el hogar tiene banda ancha fija, esa gana aunque también tenga
    móvil (es la conexión de mejor calidad de las dos).
    """
    resultado = pd.Series("Sin conexión", index=df_extendido.index)
    resultado[df_extendido["internet_movil"] == True] = "Solo móvil"  # noqa: E712
    resultado[df_extendido["internet_fija"] == True] = "Banda ancha fija"  # noqa: E712
    return resultado


def compute_indice_acceso_digital(df_extendido: pd.DataFrame) -> pd.Series:
    """Suma 0-3 de tenencia de cada tecnología (internet, PC, streaming) —
    un puntaje compuesto simple de acceso digital del hogar, en vez de
    mirar cada tecnología por separado. Inspirado en el enfoque de
    "canasta digital básica" de CEPAL (desarrollodigital.cepal.org).

    El índice iba de 0 a 4 hasta la versión 0.9.0, cuando se sacó TV cable
    del proyecto (ver `config.TECNOLOGIAS_LABELS`): tener TV cable no dice
    nada sobre el acceso digital de un hogar, y lo inflaba con una
    tecnología que no es de conectividad. Los valores de este índice **no
    son comparables** con los de un informe generado antes de ese cambio.

    Las columnas ya decodificadas (`decode_si_no`) quedan en dtype
    `object` (True/False/NaN), no numérico — sumarlas tal cual falla o da
    un dtype no numérico si hay algún "sin dato" (99) en el medio.
    `.astype("boolean")` las pasa al tipo nullable de pandas antes de
    sumar: un "sin dato" en una tecnología cuenta como 0 para el índice de
    ese hogar (no falta el hogar entero), sin romper el tipo de dato.
    """
    columnas = list(config.TECNOLOGIAS_LABELS.keys())
    return df_extendido[columnas].astype("boolean").sum(axis=1).astype("Int64")


