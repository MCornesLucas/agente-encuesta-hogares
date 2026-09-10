import pandas as pd
import pytest

from encuesta_hogares.analysis import (
    adopcion_tablet_ibirapita_por,
    brecha_digital_por_cohorte,
    brecha_digital_por_jefatura,
    brecha_por_grupo,
    calidad_conexion_por,
    carencias_estructurales_mas_frecuentes,
    combinar_por_anio,
    composicion_categorica_por_mes_promedio,
    composicion_categorica_ponderada_por,
    diferencia_entre_categorias,
    diferencia_entre_tablas,
    estrato_promedio_por,
    grupos_con_muestra_chica,
    indice_acceso_digital_por,
    indice_desarrollo_territorial,
    ingreso_hogar_mediano_por_departamento,
    inseguridad_alimentaria_por,
    media_ponderada_por,
    mediana_ponderada,
    pct_hacinamiento_por,
    pct_pobres_indigentes,
    pct_pobres_por,
    pct_ponderado,
    pct_ponderado_por,
    pct_unipersonales_mayores,
    precariedad_estructural,
    precariedad_estructural_por,
    prevalencia_inseguridad_alimentaria,
    proporcion_ponderada,
    razon_dependencia_demografica,
    razon_dependencia_por,
    resumen_conectividad,
    tasa_mensual_promedio_por,
    tasas_actividad_empleo_desempleo,
    tasas_actividad_empleo_desempleo_por,
    tasas_actividad_empleo_desempleo_por_anio,
    tasa_jefatura_femenina,
    tipos_hogar_resumen,
)


def test_resumen_conectividad_mide_internet_y_pondera():
    # Hasta la 0.9.0 esta función medía TV cable. Pesos no uniformes a
    # propósito: prueba que el porcentaje pondera de verdad, no que solo
    # cuenta filas (eso ya lo cubren total_hogares/hogares_con_internet,
    # que siguen siendo conteos de muestra sin ponderar).
    hogares = pd.DataFrame(
        {
            "tiene_internet": [True, True, False, False, False],
            "ponderador_hogar": [10.0, 10.0, 10.0, 10.0, 60.0],
        }
    )
    resumen = resumen_conectividad(hogares)
    assert resumen.total_hogares == 5
    assert resumen.hogares_con_internet == 2
    assert resumen.hogares_sin_internet == 3
    # ponderado: 20 de 100 -> 20%, no el 40% que daría sin ponderar
    assert resumen.pct_con_internet == 20.0
    assert resumen.pct_sin_internet == 80.0


def test_pct_ponderado():
    df = pd.DataFrame({"positivo": [True, True, False, False], "ponderador_hogar": [10.0, 10.0, 10.0, 70.0]})
    assert pct_ponderado(df, "positivo") == 20.0


def test_media_ponderada_por():
    df = pd.DataFrame(
        {"grupo": ["A", "A", "B"], "valor": [3.0, 5.0, 1.0], "ponderador_hogar": [30.0, 10.0, 10.0]}
    )
    resumen = media_ponderada_por(df, "grupo", "valor").set_index("grupo")
    # A ponderado: (3*30 + 5*10)/40 = 3.5, no 4.0 (promedio simple)
    assert resumen.loc["A", "media"] == 3.5
    assert resumen.loc["B", "media"] == 1.0


def test_proporcion_ponderada():
    df = pd.DataFrame({"categoria": ["X", "X", "Y"], "ponderador_hogar": [10.0, 30.0, 20.0]})
    resumen = proporcion_ponderada(df, "categoria").set_index("categoria")
    assert resumen.loc["X", "pct"] == round(40 / 60 * 100, 2)
    assert resumen.loc["Y", "pct"] == round(20 / 60 * 100, 2)


def test_mediana_ponderada():
    valores = pd.Series([10000.0, 20000.0, 30000.0])
    # con pesos uniformes, coincide con la mediana simple
    assert mediana_ponderada(valores, pd.Series([1.0, 1.0, 1.0])) == 20000.0
    # con casi todo el peso en el valor más alto, la mediana ponderada se corre hacia ahí
    assert mediana_ponderada(valores, pd.Series([1.0, 1.0, 100.0])) == 30000.0


def test_grupos_con_muestra_chica_detecta_por_debajo_del_umbral():
    df = pd.DataFrame({"tipo_delito": ["Hurto"] * 40 + ["Abigeato"] * 5})
    resultado = grupos_con_muestra_chica(df, "tipo_delito", n_minimo=30)
    assert list(resultado.index) == ["Abigeato"]
    assert resultado["Abigeato"] == 5
    assert "Hurto" not in resultado.index


def test_grupos_con_muestra_chica_vacio_si_todos_superan_el_umbral():
    df = pd.DataFrame({"grupo": ["A"] * 40 + ["B"] * 35})
    resultado = grupos_con_muestra_chica(df, "grupo", n_minimo=30)
    assert resultado.empty


def test_composicion_categorica_ponderada_por_pondera_y_suma_100_por_grupo():
    df = pd.DataFrame(
        {
            "grupo": ["A", "A", "B", "B"],
            "categoria": ["X", "Y", "X", "Y"],
            "ponderador_hogar": [10.0, 30.0, 20.0, 20.0],
        }
    )
    tabla = composicion_categorica_ponderada_por(df, "grupo", "categoria")
    # Sin ponderar, A daría 50/50 (1 fila de cada categoría) - ponderado,
    # Y pesa el triple, queda 25/75.
    assert tabla.loc["A", "X"] == 25.0
    assert tabla.loc["A", "Y"] == 75.0
    assert tabla.loc["B", "X"] == 50.0
    for grupo in tabla.index:
        assert round(tabla.loc[grupo].sum(), 2) == 100.0


def test_calidad_conexion_por_usa_la_columna_calidad_conexion():
    df = pd.DataFrame(
        {
            "nivel_economico": ["1-Bajo", "1-Bajo", "5-Alto"],
            "calidad_conexion": ["Sin conexión", "Solo móvil", "Banda ancha fija"],
            "ponderador_hogar": [10.0, 10.0, 50.0],
        }
    )
    tabla = calidad_conexion_por(df, "nivel_economico")
    assert tabla.loc["1-Bajo", "Sin conexión"] == 50.0
    assert tabla.loc["5-Alto", "Banda ancha fija"] == 100.0




def test_precariedad_estructural_cuenta_con_al_menos_una_carencia():
    df = pd.DataFrame(
        {
            "goteras": [True, False, False, False],
            "se_inunda": [False, False, True, False],
            "ponderador_hogar": [10.0, 10.0, 10.0, 70.0],
        }
    )
    resultado = precariedad_estructural(df)
    # con carencia: filas 0 y 2 (peso 10+10=20) sobre 100 -> 20%, no 50%
    assert resultado["pct_con_carencia"] == 20.0
    assert resultado["total_hogares"] == 4
    assert resultado["hogares_con_carencia"] == 2


def test_precariedad_estructural_tolera_columnas_faltantes():
    # A partir de 2024 solo hay 4 de las 12 columnas de vivienda (ver
    # config.CONDICIONES_VIVIENDA_COLUMNS_CSV) - la función solo debe usar
    # las que están presentes en el dataframe, sin fallar por las demás.
    df = pd.DataFrame({"goteras": [True, False], "ponderador_hogar": [10.0, 10.0]})
    resultado = precariedad_estructural(df)
    assert resultado["pct_con_carencia"] == 50.0


def test_precariedad_estructural_explota_si_no_hay_ninguna_columna_de_vivienda():
    # Caso real: 2023 no tiene NINGUNA columna del módulo C5 (no cambió de
    # nombre, el módulo entero no se relevó ese año). Antes, con la lista
    # de columnas vacía, `df[[]].any(axis=1)` da False para todas las
    # filas y la función devolvía silenciosamente "0% con carencia" - un
    # número que parece un cálculo real y no lo es. Tiene que fallar
    # fuerte en vez de eso, para que quien llama avise explícitamente que
    # el módulo no está disponible (ver
    # verificacion_catalogo.aviso_metricas_no_disponibles) en vez de
    # mostrar ese 0% fantasma en un informe real.
    df = pd.DataFrame({"ponderador_hogar": [10.0, 10.0]})
    with pytest.raises(ValueError):
        precariedad_estructural(df)


def test_precariedad_estructural_por_explota_si_no_hay_ninguna_columna_de_vivienda():
    df = pd.DataFrame({"departamento": ["MONTEVIDEO", "SALTO"], "ponderador_hogar": [10.0, 10.0]})
    with pytest.raises(ValueError):
        precariedad_estructural_por(df, "departamento")


def test_carencias_estructurales_mas_frecuentes_explota_si_no_hay_ninguna_columna_de_vivienda():
    df = pd.DataFrame({"ponderador_hogar": [10.0, 10.0]})
    with pytest.raises(ValueError):
        carencias_estructurales_mas_frecuentes(df)


def test_precariedad_estructural_por_agrupa_correctamente():
    df = pd.DataFrame(
        {
            "departamento": ["MONTEVIDEO", "MONTEVIDEO", "SALTO", "SALTO"],
            "goteras": [True, False, True, True],
            "ponderador_hogar": [10.0, 10.0, 10.0, 10.0],
        }
    )
    resumen = precariedad_estructural_por(df, "departamento").set_index("departamento")
    assert resumen.loc["MONTEVIDEO", "pct_precariedad"] == 50.0
    assert resumen.loc["SALTO", "pct_precariedad"] == 100.0


def test_carencias_estructurales_mas_frecuentes_ordena_de_mayor_a_menor():
    df = pd.DataFrame(
        {
            "goteras": [True, True, True, False],
            "se_inunda": [True, False, False, False],
            "ponderador_hogar": [10.0, 10.0, 10.0, 10.0],
        }
    )
    resumen = carencias_estructurales_mas_frecuentes(df)
    assert resumen.iloc[0]["carencia"] == "Goteras en techos"
    assert resumen.iloc[0]["pct_hogares"] == 75.0
    assert resumen.iloc[1]["carencia"] == "Se inunda cuando llueve"
    assert resumen.iloc[1]["pct_hogares"] == 25.0


def test_pct_pobres_por():
    df = pd.DataFrame(
        {
            "departamento": ["MONTEVIDEO", "MONTEVIDEO", "SALTO"],
            "pobre": [True, False, True],
            "ponderador_hogar": [10.0, 10.0, 10.0],
        }
    )
    resumen = pct_pobres_por(df, "departamento").set_index("departamento")
    assert resumen.loc["MONTEVIDEO", "pct_pobres"] == 50.0
    assert resumen.loc["SALTO", "pct_pobres"] == 100.0


def test_estrato_promedio_por():
    df = pd.DataFrame(
        {
            "departamento": ["MONTEVIDEO", "MONTEVIDEO", "SALTO"],
            "estrato_tipo": [3, 5, 1],
            "ponderador_hogar": [30.0, 10.0, 10.0],
        }
    )
    resumen = estrato_promedio_por(df, "departamento").set_index("departamento")
    # MONTEVIDEO ponderado: (3*30 + 5*10)/40 = 3.5, no 4.0 (promedio simple)
    assert resumen.loc["MONTEVIDEO", "estrato_promedio"] == 3.5
    assert resumen.loc["SALTO", "estrato_promedio"] == 1.0


def test_indice_desarrollo_territorial_invierte_y_normaliza():
    componentes = pd.DataFrame(
        {"pct_pobreza": [40.0, 0.0], "tasa_empleo": [30.0, 60.0]},
        index=pd.Index(["Peor", "Mejor"], name="departamento"),
    )
    resultado = indice_desarrollo_territorial(componentes, invertir=["pct_pobreza"])
    # "Mejor" tiene menos pobreza (invertida: mejor puntaje) y mas empleo -> indice mas alto
    assert resultado.loc["Mejor", "indice"] > resultado.loc["Peor", "indice"]
    assert resultado.loc["Mejor", "pct_pobreza"] == 1.0  # 0% pobreza, invertido -> el mejor valor posible
    assert resultado.loc["Mejor", "indice"] == 1.0
    assert resultado.loc["Peor", "indice"] == 0.0
    # queda ordenado de mejor a peor
    assert resultado.index.tolist() == ["Mejor", "Peor"]


def test_ingreso_hogar_mediano_por_departamento():
    # pesos uniformes a propósito: la mediana ponderada coincide con la
    # mediana simple cuando todos pesan igual (la ponderación no uniforme
    # de la mediana ya se prueba aparte en test_mediana_ponderada).
    hogares = pd.DataFrame(
        {
            "departamento": ["RIVERA", "RIVERA", "RIVERA", "MONTEVIDEO", "MONTEVIDEO", "SALTO"],
            "ingreso_hogar": [10000.0, 20000.0, 30000.0, 50000.0, 70000.0, 999999.0],
            "ponderador_hogar": [10.0, 10.0, 10.0, 10.0, 10.0, 10.0],
        }
    )
    resultado = ingreso_hogar_mediano_por_departamento(hogares, ["RIVERA", "MONTEVIDEO"])
    assert resultado["RIVERA"] == 20000.0
    assert resultado["MONTEVIDEO"] == 60000.0
    assert "SALTO" not in resultado.index


def test_prevalencia_inseguridad_alimentaria_pondera_correctamente():
    df = pd.DataFrame(
        {
            "inseguridad_moderada_o_severa": [True, True, False, False],
            "inseguridad_severa": [True, False, False, False],
            "ponderador_fies": [100.0, 100.0, 100.0, 100.0],
        }
    )
    resultado = prevalencia_inseguridad_alimentaria(df)
    assert resultado["moderada_o_severa"] == 50.0
    assert resultado["severa"] == 25.0


def test_inseguridad_alimentaria_por_pondera_por_grupo_no_solo_cuenta_filas():
    df = pd.DataFrame(
        {
            "quintil_ingreso": [1, 1, 5, 5],
            "inseguridad_moderada_o_severa": [True, False, False, False],
            "ponderador_fies": [300.0, 100.0, 50.0, 50.0],
        }
    )
    resumen = inseguridad_alimentaria_por(df, "quintil_ingreso").set_index("quintil_ingreso")
    # quintil 1: 300 de ponderador "inseguro" sobre 400 totales -> 75%, no 50%
    # (que seria el resultado si se contaran filas en vez de ponderar)
    assert resumen.loc[1, "pct_inseguridad"] == 75.0
    assert resumen.loc[5, "pct_inseguridad"] == 0.0


def test_inseguridad_alimentaria_por_usa_la_columna_de_clasificacion_indicada():
    df = pd.DataFrame(
        {
            "region": ["Montevideo", "Montevideo"],
            "inseguridad_moderada_o_severa": [True, True],
            "inseguridad_severa": [True, False],
            "ponderador_fies": [100.0, 100.0],
        }
    )
    resumen = inseguridad_alimentaria_por(df, "region", columna_clasificacion="inseguridad_severa")
    assert resumen.iloc[0]["pct_inseguridad"] == 50.0


def test_tasas_actividad_empleo_desempleo_promedia_por_mes():
    df = pd.DataFrame(
        {
            "mes": [1, 1, 1, 2, 2, 2],
            "condicion_actividad": ["Ocupados", "Desocupados", "Inactivos"] * 2,
            "ponderador_empleo": [80.0, 20.0, 100.0, 80.0, 20.0, 100.0],
        }
    )
    tasas = tasas_actividad_empleo_desempleo(df)
    # cada mes: total=200, activos=100 (ocupados 80 + desocupados 20)
    assert tasas["tasa_actividad"] == 50.0
    assert tasas["tasa_empleo"] == 40.0
    assert tasas["tasa_desempleo"] == 20.0


def test_tasa_mensual_promedio_por_promedia_meses_en_vez_de_hacer_pool():
    df = pd.DataFrame(
        {
            "mes": [1, 1, 1, 1, 2, 2],
            "departamento": ["A", "A", "A", "A", "A", "A"],
            "positivo": [True, False, False, False, True, False],
            "ponderador_empleo": [10.0, 10.0, 10.0, 10.0, 100.0, 100.0],
        }
    )
    resumen = tasa_mensual_promedio_por(df, "departamento", "positivo")
    # mes 1: 10/40=25%, mes 2: 100/200=50% -> promedio 37.5%
    # el pool directo daria 110/240=45.83%, un numero distinto
    assert resumen.iloc[0]["pct_promedio"] == 37.5


def test_tasas_actividad_empleo_desempleo_por_desagrega_por_grupo():
    df = pd.DataFrame(
        {
            "mes": [1, 1, 1, 1, 1, 1],
            "sexo_grupo": ["Hombre", "Hombre", "Hombre", "Mujer", "Mujer", "Mujer"],
            "condicion_actividad": ["Ocupados", "Desocupados", "Inactivos"] * 2,
            "ponderador_empleo": [70.0, 30.0, 100.0, 50.0, 50.0, 100.0],
        }
    )
    resumen = tasas_actividad_empleo_desempleo_por(df, "sexo_grupo").set_index("sexo_grupo")
    assert resumen.loc["Hombre", "tasa_desempleo"] == 30.0
    assert resumen.loc["Mujer", "tasa_desempleo"] == 50.0


def test_tasas_actividad_empleo_desempleo_por_anio_ordena_y_deja_anio_numerico():
    # Deliberadamente fuera de orden y con años no consecutivos (2019, 2024,
    # 2025) - la funcion tiene que ordenar por año Y dejar la columna
    # numerica (no string/categorica), para que el grafico despues pueda
    # usar la escala real del eje x.
    tasas_por_anio = {
        2024: {"tasa_actividad": 64.28, "tasa_empleo": 59.02, "tasa_desempleo": 8.18},
        2019: {"tasa_actividad": 62.0, "tasa_empleo": 58.0, "tasa_desempleo": 6.5},
        2025: {"tasa_actividad": 65.0, "tasa_empleo": 60.0, "tasa_desempleo": 7.5},
    }
    tabla = tasas_actividad_empleo_desempleo_por_anio(tasas_por_anio)
    assert tabla["anio"].tolist() == [2019, 2024, 2025]
    assert pd.api.types.is_integer_dtype(tabla["anio"])
    assert tabla.set_index("anio").loc[2024, "tasa_desempleo"] == 8.18


def test_combinar_por_anio_con_metrica_de_un_solo_numero():
    # Caso simple: la métrica es un único porcentaje por año (ej. pobreza),
    # sin sub-series. Mismo criterio que la función que generaliza: orden
    # ascendente y año numérico.
    valores_por_anio = {2024: 12.99, 2019: 8.14, 2025: 14.14}
    tabla = combinar_por_anio(valores_por_anio)
    assert tabla["anio"].tolist() == [2019, 2024, 2025]
    assert pd.api.types.is_integer_dtype(tabla["anio"])
    assert tabla.set_index("anio").loc[2025, "valor"] == 14.14


def test_combinar_por_anio_con_metrica_de_varias_series():
    # Caso con sub-series (ej. jefatura por sexo) - mismo comportamiento
    # que tasas_actividad_empleo_desempleo_por_anio, generalizado a
    # cualquier dict de valores, no solo esas tres tasas puntuales.
    valores_por_anio = {
        2024: {"jefatura_hombre": 44.14, "jefatura_mujer": 55.86},
        2019: {"jefatura_hombre": 53.43, "jefatura_mujer": 46.57},
    }
    tabla = combinar_por_anio(valores_por_anio)
    assert tabla["anio"].tolist() == [2019, 2024]
    assert tabla.set_index("anio").loc[2024, "jefatura_mujer"] == 55.86


def test_brecha_por_grupo_calcula_diferencia_en_puntos():
    resumen = pd.DataFrame(
        {
            "sexo_grupo": ["Hombre", "Mujer"],
            "tasa_actividad": [73.0, 56.8],
            "tasa_empleo": [68.7, 51.6],
            "tasa_desempleo": [5.9, 9.3],
        }
    )
    brecha = brecha_por_grupo(resumen, "sexo_grupo", "Hombre", "Mujer")
    assert brecha["tasa_actividad"] == 16.2
    assert round(brecha["tasa_desempleo"], 1) == -3.4


def test_diferencia_entre_categorias_calcula_diferencia_en_puntos():
    resumen = pd.DataFrame(
        {
            "quintil_ingreso": [1, 2, 3, 4, 5],
            "pct_inseguridad": [45.0, 30.0, 20.0, 10.0, 5.0],
        }
    )
    diferencia = diferencia_entre_categorias(resumen, "quintil_ingreso", 1, 5, "pct_inseguridad")
    assert diferencia == 40.0


def test_composicion_categorica_por_mes_promedio_promedia_meses_y_no_hace_pool():
    df = pd.DataFrame(
        {
            "mes": [1, 1, 1, 1, 2, 2, 2, 2],
            "sector_formalidad": ["Formal", "Formal", "Informal", "Informal"] * 2,
            "situacion_ocupacional": ["Asalariado", "Cuentapropista", "Asalariado", "Cuentapropista"] * 2,
            "ponderador_empleo": [60.0, 40.0, 30.0, 70.0, 60.0, 40.0, 30.0, 70.0],
        }
    )
    tabla = composicion_categorica_por_mes_promedio(df, "sector_formalidad", "situacion_ocupacional")
    assert tabla.loc["Formal", "Asalariado"] == 60.0
    assert tabla.loc["Formal", "Cuentapropista"] == 40.0
    assert tabla.loc["Informal", "Cuentapropista"] == 70.0


def test_pct_ponderado_por_calcula_porcentaje_ponderado_no_conteo_de_filas():
    df = pd.DataFrame(
        {
            "grupo": ["A", "A", "B", "B"],
            "positivo": [True, False, True, True],
            "peso": [10.0, 10.0, 5.0, 15.0],
        }
    )
    resumen = pct_ponderado_por(df, "grupo", "positivo", "peso").set_index("grupo")
    assert resumen.loc["A", "pct"] == 50.0
    assert resumen.loc["B", "pct"] == 100.0


def test_diferencia_entre_tablas_cruza_por_indice():
    tabla_a = pd.DataFrame({"tipo": ["X", "Y"], "pct": [80.0, 60.0]})
    tabla_b = pd.DataFrame({"tipo": ["X", "Y"], "pct": [50.0, 60.0]})
    diferencia = diferencia_entre_tablas(tabla_a, tabla_b, "tipo", "pct")
    assert diferencia["X"] == 30.0
    assert diferencia["Y"] == 0.0


# ============================================================================
# Hogares y Brecha Digital
# ============================================================================

def test_pct_pobres_indigentes():
    df = pd.DataFrame(
        {
            "pobre": [True, True, False, False],
            "indigente": [True, False, False, False],
            "ponderador_hogar": [10.0, 10.0, 10.0, 70.0],
        }
    )
    resultado = pct_pobres_indigentes(df)
    # pobres ponderado: (10+10)/100 = 20%, no 50%; indigentes: 10/100 = 10%, no 25%
    assert resultado == {"pct_pobres": 20.0, "pct_indigentes": 10.0}


def test_tasa_jefatura_femenina():
    df = pd.DataFrame(
        {
            "jefe_sexo": ["Hombre", "Mujer", "Mujer", "Hombre", None],
            "ponderador_hogar": [10.0, 10.0, 10.0, 70.0, 10.0],
        }
    )
    resultado = tasa_jefatura_femenina(df)
    # de los 4 con jefatura identificada (peso 100): mujeres peso 20 -> 20%, no 50%
    assert resultado == {"pct_jefatura_femenina": 20.0, "total_hogares": 4}


def test_tipos_hogar_resumen_ordena_de_mayor_a_menor():
    df = pd.DataFrame(
        {
            "tipo_hogar": ["Nuclear", "Nuclear", "Nuclear", "Unipersonal", "Extendido"],
            "ponderador_hogar": [10.0, 10.0, 10.0, 10.0, 10.0],
        }
    )
    resumen = tipos_hogar_resumen(df)
    assert resumen.iloc[0]["tipo_hogar"] == "Nuclear"
    assert resumen.iloc[0]["pct_hogares"] == 60.0


def test_pct_hacinamiento_por():
    df = pd.DataFrame(
        {
            "nivel_economico": ["1-Bajo", "1-Bajo", "5-Alto"],
            "hacinado": [True, False, False],
            "ponderador_hogar": [10.0, 10.0, 10.0],
        }
    )
    resumen = pct_hacinamiento_por(df, "nivel_economico").set_index("nivel_economico")
    assert resumen.loc["1-Bajo", "pct_hacinamiento"] == 50.0
    assert resumen.loc["5-Alto", "pct_hacinamiento"] == 0.0


def test_razon_dependencia_demografica():
    # 2 menores de 15 (peso 10 c/u = 20), 1 mayor de 65 (peso 60), 3 activos
    # 15-64 (peso 10 c/u = 30) -> (20+60)/30*100 = 266.67, no el 100.0 que
    # daría contando personas sin ponderar.
    personas = pd.DataFrame(
        {
            "edad": [5, 10, 70, 20, 40, 60],
            "ponderador_hogar": [10.0, 10.0, 60.0, 10.0, 10.0, 10.0],
        }
    )
    assert razon_dependencia_demografica(personas) == round((20 + 60) / 30 * 100, 2)


def test_razon_dependencia_por():
    personas = pd.DataFrame(
        {
            "departamento": ["MONTEVIDEO", "MONTEVIDEO", "MONTEVIDEO", "SALTO", "SALTO"],
            "edad": [5, 30, 40, 30, 40],
            "ponderador_hogar": [10.0, 10.0, 10.0, 10.0, 10.0],
        }
    )
    resumen = razon_dependencia_por(personas, "departamento").set_index("departamento")
    assert resumen.loc["MONTEVIDEO", "razon_dependencia"] == 50.0
    assert resumen.loc["SALTO", "razon_dependencia"] == 0.0


def test_pct_unipersonales_mayores():
    df = pd.DataFrame(
        {
            "tipo_hogar": ["Unipersonal", "Unipersonal", "Unipersonal", "Nuclear"],
            "jefe_edad": [70, 30, 68, 40],
            "ponderador_hogar": [10.0, 10.0, 10.0, 10.0],
        }
    )
    resultado = pct_unipersonales_mayores(df)
    assert resultado == {"pct_unipersonales_mayores": round(2 / 3 * 100, 2), "total_unipersonales": 3}


def test_pct_unipersonales_mayores_sin_unipersonales():
    df = pd.DataFrame({"tipo_hogar": ["Nuclear"], "jefe_edad": [40]})
    resultado = pct_unipersonales_mayores(df)
    assert resultado == {"pct_unipersonales_mayores": 0.0, "total_unipersonales": 0}


def test_brecha_digital_por_cohorte():
    df = pd.DataFrame(
        {
            "cohorte": ["Millennials (1981-1996)", "Millennials (1981-1996)", "Baby boomers (1946-1964)"],
            "tiene_internet": [True, False, False],
            "tiene_pc": [True, True, False],
            "tiene_streaming": [True, False, False],
            "ponderador_hogar": [10.0, 10.0, 10.0],
        }
    )
    resumen = brecha_digital_por_cohorte(df)
    fila = resumen[(resumen["cohorte"] == "Millennials (1981-1996)") & (resumen["tecnologia"] == "Internet")]
    assert fila["pct_penetracion"].iloc[0] == 50.0


def test_brecha_digital_por_jefatura():
    df = pd.DataFrame(
        {
            "jefe_sexo": ["Hombre", "Hombre", "Mujer"],
            "tiene_internet": [True, False, True],
            "tiene_pc": [True, True, True],
            "tiene_streaming": [False, False, True],
            "ponderador_hogar": [10.0, 10.0, 10.0],
        }
    )
    resumen = brecha_digital_por_jefatura(df)
    fila = resumen[(resumen["jefe_sexo"] == "Hombre") & (resumen["tecnologia"] == "Internet")]
    assert fila["pct_penetracion"].iloc[0] == 50.0


def test_indice_acceso_digital_por():
    df = pd.DataFrame(
        {
            "nivel_economico": ["1-Bajo", "1-Bajo", "5-Alto"],
            "indice_acceso_digital": [1, 3, 4],
            "ponderador_hogar": [10.0, 10.0, 10.0],
        }
    )
    resumen = indice_acceso_digital_por(df, "nivel_economico").set_index("nivel_economico")
    assert resumen.loc["1-Bajo", "indice_promedio"] == 2.0
    assert resumen.loc["5-Alto", "indice_promedio"] == 4.0


def test_adopcion_tablet_ibirapita_por():
    df = pd.DataFrame(
        {
            "jefe_es_mayor": [True, True, False],
            "tiene_tablet_ibirapita": [True, False, False],
            "ponderador_hogar": [10.0, 10.0, 10.0],
        }
    )
    resumen = adopcion_tablet_ibirapita_por(df, "jefe_es_mayor").set_index("jefe_es_mayor")
    assert resumen.loc[True, "pct_con_tablet"] == 50.0
    assert resumen.loc[False, "pct_con_tablet"] == 0.0


def test_adopcion_tablet_ibirapita_por_trata_sin_dato_como_no_tiene():
    df = pd.DataFrame(
        {
            "jefe_es_mayor": [True, True, True],
            "tiene_tablet_ibirapita": [True, False, None],
            "ponderador_hogar": [10.0, 10.0, 10.0],
        }
    )
    resumen = adopcion_tablet_ibirapita_por(df, "jefe_es_mayor").set_index("jefe_es_mayor")
    assert resumen.loc[True, "pct_con_tablet"] == round(1 / 3 * 100, 2)


def test_grupos_con_pocos_casos_cuenta_los_positivos_y_no_el_tamano_del_grupo():
    """Caso real (2024): Cerro Largo tenía 694 personas encuestadas y 0
    víctimas — `grupos_con_muestra_chica` no lo marcaba y el informe decía
    «va de 0,0% (Cerro Largo)». Un grupo sin ningún positivo también
    cuenta (con cero), no desaparece de la lista."""
    from encuesta_hogares.analysis import grupos_con_muestra_chica, grupos_con_pocos_casos

    df = pd.DataFrame(
        {
            "departamento": ["A"] * 40 + ["B"] * 40 + ["C"] * 40,
            "victima": [True] * 35 + [False] * 5 + [True] * 3 + [False] * 37 + [False] * 40,
        }
    )
    assert list(grupos_con_muestra_chica(df, "departamento")) == []
    pocos = grupos_con_pocos_casos(df, "departamento", "victima")
    assert pocos.to_dict() == {"C": 0, "B": 3}
    assert list(pocos.index) == ["C", "B"]
