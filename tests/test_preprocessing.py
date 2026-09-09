import pandas as pd

from encuesta_hogares.preprocessing import (
    classify_edad_grupo,
    classify_nivel_economico,
    classify_sexo,
    clasificar_calidad_conexion,
    clasificar_tipo_hogar,
    compute_cohorte_generacional,
    compute_hacinamiento,
    compute_indice_acceso_digital,
    normalizar_departamento,
    decode_condiciones_vivienda,
    decode_si_no,
    melt_delitos,
    merge_personas,
    prepare_empleo,
    prepare_fies,
    prepare_hogares_extendido,
    prepare_hogares_montevideo,
    prepare_victimizacion,
)


def test_classify_nivel_economico():
    result = classify_nivel_economico(pd.Series([1, 3, 5, 9]))
    assert list(result) == ["1-Bajo", "3-Medio", "5-Alto", "6-No Definido"]


def test_classify_sexo():
    result = classify_sexo(pd.Series([1, 2, 9]))
    assert list(result) == ["1-Hombre", "2-Mujer", "3-Otro"]


def test_classify_edad_grupo():
    result = classify_edad_grupo(pd.Series([5, 14, 15, 64, 65, 90]))
    assert list(result.astype(str)) == [
        "1-Niños-Jovenes",
        "1-Niños-Jovenes",
        "2-Adultos",
        "2-Adultos",
        "3-Adultos_mayores",
        "3-Adultos_mayores",
    ]


def test_decode_si_no():
    result = decode_si_no(pd.Series([1.0, 2.0, 99.0]))
    assert result.tolist()[:2] == [True, False]
    assert pd.isna(result.iloc[2])


def _hogares_extendido_ejemplo():
    return pd.DataFrame(
        {
            "id_hogar": [1, 2, 3, 4],
            "departamento": ["MONTEVIDEO"] * 4,
            "estrato_tipo": [5.0, 1.0, 5.0, 1.0],
            "nivel_economico": ["5-Alto", "1-Bajo", "5-Alto", "1-Bajo"],
            "total_personas": [2.0, 4.0, 3.0, 5.0],
            "menores_14": [0.0, 2.0, 1.0, 2.0],
            "ocupados_hogar": [1.0, 1.0, 2.0, 1.0],
            "pobre": [2.0, 1.0, 2.0, 1.0],
            "indigente": [2.0, 2.0, 2.0, 2.0],
            "ingreso_hogar": [80000.0, 20000.0, 60000.0, 15000.0],
            "tiene_internet": [1.0, 2.0, 1.0, 2.0],
            "internet_fija": [1.0, 2.0, 1.0, 2.0],
            "internet_movil": [2.0, 2.0, 2.0, 1.0],
            "tiene_pc": [1.0, 2.0, 1.0, 1.0],
            "tiene_streaming": [1.0, 2.0, 2.0, 2.0],
            **{col: [1.0, 2.0, 1.0, 2.0] for col in [
                "humedad_techos", "goteras", "muros_agrietados", "puertas_ventanas_deterioradas",
                "grietas_pisos", "caida_revoque", "cielorraso_desprendido", "poca_luz_solar",
                "escasa_ventilacion", "se_inunda", "peligro_derrumbe", "humedad_cimientos",
            ]},
        }
    )


def test_prepare_hogares_extendido_decodes_booleanos():
    df = prepare_hogares_extendido(_hogares_extendido_ejemplo())
    assert df["pobre"].tolist() == [False, True, False, True]
    assert df["tiene_internet"].tolist() == [True, False, True, False]
    assert df["goteras"].tolist() == [True, False, True, False]


def test_merge_personas_no_duplica_el_ponderador():
    # hogares_resumen ya trae ponderador_hogar (viene del lado de Hogares,
    # ver config.HOGARES_COLUMNS) - personas nunca lo trae (a propósito,
    # ver config.PERSONAS_COLUMNS). Si algún día se agregara a los dos
    # lados, este merge lo duplicaría como "ponderador_hogar_x"/"_y" en vez
    # de conservar una sola columna.
    hogares_resumen = pd.DataFrame({"id_hogar": [1, 2], "ponderador_hogar": [100.0, 200.0]})
    personas = pd.DataFrame({"id_hogar": [1, 2], "edad": [30, 45], "sexo": [1, 2]})
    combinado = merge_personas(hogares_resumen, personas)
    assert "ponderador_hogar" in combinado.columns
    assert "ponderador_hogar_x" not in combinado.columns
    assert "ponderador_hogar_y" not in combinado.columns
    assert combinado.set_index("id_hogar").loc[1, "ponderador_hogar"] == 100.0
    assert combinado.set_index("id_hogar").loc[2, "ponderador_hogar"] == 200.0


def test_decode_condiciones_vivienda_no_filtra_a_montevideo():
    df = pd.DataFrame(
        {
            "departamento": ["MONTEVIDEO", "SALTO"],
            "goteras": [1.0, 2.0],
            "se_inunda": [2.0, 1.0],
        }
    )
    resultado = decode_condiciones_vivienda(df)
    assert resultado["goteras"].tolist() == [True, False]
    assert resultado["se_inunda"].tolist() == [False, True]
    # a diferencia de prepare_hogares_extendido, no descarta ni filtra filas
    assert resultado["departamento"].tolist() == ["MONTEVIDEO", "SALTO"]


def test_decode_condiciones_vivienda_tolera_columnas_faltantes():
    df = pd.DataFrame({"goteras": [1.0, 2.0]})
    resultado = decode_condiciones_vivienda(df)
    assert resultado["goteras"].tolist() == [True, False]


def test_prepare_hogares_extendido_tolera_columnas_de_vivienda_faltantes():
    # A partir de 2024 solo llegan 4 de las 12 columnas de "problemas de la
    # vivienda" (el resto se discontinuó a mitad de año, ver
    # config.CONDICIONES_VIVIENDA_COLUMNS_CSV) - la función no debe fallar
    # por eso, solo debe decodificar las que sí están presentes.
    ejemplo = _hogares_extendido_ejemplo().drop(
        columns=[
            "humedad_techos", "muros_agrietados", "puertas_ventanas_deterioradas",
            "grietas_pisos", "caida_revoque", "cielorraso_desprendido",
            "poca_luz_solar", "escasa_ventilacion",
        ]
    )
    df = prepare_hogares_extendido(ejemplo)
    assert df["goteras"].tolist() == [True, False, True, False]
    assert "humedad_techos" not in df.columns


def _personas_hogares_ejemplo():
    # Hogar 1: solo el jefe -> Unipersonal.
    # Hogar 2: jefe + conyuge + hijo -> Nuclear.
    # Hogar 3: jefe + conyuge + hijo + suegro -> Extendido.
    # Hogar 4: jefe + hijo, sin conyuge -> Nuclear y monoparental.
    # Hogar 5: jefe + otro no pariente -> Compuesto.
    # Hogar 6: jefe + hermano, sin nucleo -> Sin núcleo.
    return pd.DataFrame(
        {
            "id_hogar": [1, 2, 2, 2, 3, 3, 3, 3, 4, 4, 5, 5, 6, 6],
            "parentesco_jefe": [1, 1, 2, 3, 1, 2, 3, 8, 1, 3, 1, 13, 1, 9],
            "sexo": [1, 1, 2, 1, 2, 1, 2, 2, 2, 1, 1, 1, 1, 1],
            "edad": [70, 40, 38, 10, 55, 56, 20, 80, 35, 8, 45, 30, 60, 58],
        }
    )


def _hogares_ponderador_ejemplo():
    return pd.DataFrame({"id_hogar": [1, 2, 3, 4, 5, 6], "ponderador_hogar": [100.0, 200.0, 150.0, 80.0, 120.0, 90.0]})


def test_clasificar_tipo_hogar_taxonomia_celade():
    resultado = clasificar_tipo_hogar(_personas_hogares_ejemplo(), _hogares_ponderador_ejemplo()).set_index("id_hogar")
    assert resultado.loc[1, "tipo_hogar"] == "Unipersonal"
    assert resultado.loc[2, "tipo_hogar"] == "Nuclear"
    assert resultado.loc[3, "tipo_hogar"] == "Extendido"
    assert resultado.loc[4, "tipo_hogar"] == "Nuclear"
    assert resultado.loc[5, "tipo_hogar"] == "Compuesto"
    assert resultado.loc[6, "tipo_hogar"] == "Sin núcleo"


def test_clasificar_tipo_hogar_marca_monoparental():
    resultado = clasificar_tipo_hogar(_personas_hogares_ejemplo(), _hogares_ponderador_ejemplo()).set_index("id_hogar")
    assert bool(resultado.loc[2, "monoparental"]) is False  # tiene cónyuge
    assert bool(resultado.loc[4, "monoparental"]) is True  # hijo sin cónyuge


def test_clasificar_tipo_hogar_agrega_sexo_y_edad_del_jefe():
    resultado = clasificar_tipo_hogar(_personas_hogares_ejemplo(), _hogares_ponderador_ejemplo()).set_index("id_hogar")
    assert resultado.loc[1, "jefe_sexo"] == "1-Hombre"
    assert resultado.loc[1, "jefe_edad"] == 70
    assert resultado.loc[3, "jefe_sexo"] == "2-Mujer"


def test_clasificar_tipo_hogar_agrega_ponderador():
    resultado = clasificar_tipo_hogar(_personas_hogares_ejemplo(), _hogares_ponderador_ejemplo()).set_index("id_hogar")
    assert resultado.loc[1, "ponderador_hogar"] == 100.0
    assert resultado.loc[2, "ponderador_hogar"] == 200.0


def test_compute_hacinamiento_marca_por_encima_del_umbral():
    hogares = pd.DataFrame({"id_hogar": [1, 2, 3], "total_personas": [6.0, 4.0, 2.0], "cantidad_habitaciones": [2.0, 2.0, 2.0]})
    resultado = compute_hacinamiento(hogares)
    # 6/2=3.0 (>2, hacinado), 4/2=2.0 (no supera el umbral), 2/2=1.0 (no hacinado)
    assert resultado["hacinado"].tolist() == [True, False, False]


def test_compute_cohorte_generacional():
    hogares = pd.DataFrame({"jefe_edad": [80, 50, 30, 20]})
    resultado = compute_cohorte_generacional(hogares, anio=2024)
    # nacimientos aprox: 1944, 1974, 1994, 2004
    assert list(resultado.astype(str)) == [
        "Generación silenciosa (hasta 1945)",
        "Generación X (1965-1980)",
        "Millennials (1981-1996)",
        "Generación Z (1997 en adelante)",
    ]


def test_clasificar_calidad_conexion():
    df = pd.DataFrame(
        {
            "internet_fija": [True, False, False],
            "internet_movil": [False, True, False],
        }
    )
    resultado = clasificar_calidad_conexion(df)
    assert resultado.tolist() == ["Banda ancha fija", "Solo móvil", "Sin conexión"]


def test_clasificar_calidad_conexion_fija_gana_si_tiene_ambas():
    df = pd.DataFrame({"internet_fija": [True], "internet_movil": [True]})
    assert clasificar_calidad_conexion(df).tolist() == ["Banda ancha fija"]


def test_compute_indice_acceso_digital():
    # El índice va de 0 a 3 desde la 0.9.0: eran cuatro tecnologías hasta
    # que se sacó TV cable del proyecto (ver config.TECNOLOGIAS_LABELS).
    df = pd.DataFrame(
        {
            "tiene_internet": [True, True, False],
            "tiene_pc": [True, False, False],
            "tiene_streaming": [False, False, False],
        }
    )
    assert compute_indice_acceso_digital(df).tolist() == [2, 1, 0]


def test_prepare_hogares_montevideo_ignora_mayusculas():
    hogares = pd.DataFrame(
        {
            "id_hogar": [1, 2, 3],
            "departamento": ["Montevideo", "MONTEVIDEO", "Salto"],
            "estrato_tipo": [1, 2, 3],
        }
    )
    resultado = prepare_hogares_montevideo(hogares)
    assert sorted(resultado["id_hogar"].tolist()) == [1, 2]


def test_normalizar_departamento_deja_mayusculas_consistentes_entre_anios():
    hogares_2019 = pd.DataFrame({"departamento": ["MONTEVIDEO", "SALTO"]})
    hogares_2024 = pd.DataFrame({"departamento": ["Montevideo", "Salto"]})
    a = normalizar_departamento(hogares_2019)
    b = normalizar_departamento(hogares_2024)
    assert a["departamento"].tolist() == b["departamento"].tolist() == ["MONTEVIDEO", "SALTO"]


def test_prepare_fies_clasifica_por_umbral_y_etiqueta_region():
    df = pd.DataFrame(
        {
            "prob_inseguridad_moderada": [0.6, 0.4, 0.5],
            "prob_inseguridad_severa": [0.6, 0.1, 0.2],
            "region_cod": [1, 2, 1],
            "tiene_menores_18": [1, 0, 1],
            "tiene_menores_6": [0, 0, 1],
        }
    )
    resultado = prepare_fies(df)
    assert resultado["inseguridad_moderada_o_severa"].tolist() == [True, False, True]
    assert resultado["inseguridad_severa"].tolist() == [True, False, False]
    assert resultado["region"].tolist() == ["Montevideo", "Interior", "Montevideo"]
    assert resultado["tiene_menores_18"].tolist() == [True, False, True]
    assert resultado["tiene_menores_6"].tolist() == [False, False, True]


def test_prepare_empleo_mapea_actividad_sexo_y_edad():
    df = pd.DataFrame(
        {
            "condicion_actividad_cod": [2.0, 3.0, 6.0],
            "es_informal": [1, 0, 0],
            "es_subempleo": [0, 0, 0],
            "sexo": [1, 2, 1],
            "edad": [20, 40, 24],
        }
    )
    resultado = prepare_empleo(df)
    assert resultado["condicion_actividad"].tolist() == ["Ocupados", "Desocupados", "Inactivos"]
    assert resultado["es_informal"].tolist() == [True, False, False]
    assert resultado["es_subempleo"].tolist() == [False, False, False]
    assert resultado["sexo_grupo"].tolist() == ["1-Hombre", "2-Mujer", "1-Hombre"]
    assert resultado["grupo_edad_laboral"].tolist() == ["Joven (14-24)", "Resto", "Joven (14-24)"]


def test_prepare_empleo_tolera_es_informal_ausente():
    # INFORMAL desaparecio de los archivos mensuales desde 2025 (verificado
    # contra datos reales) - prepare_empleo no tiene que romper si esa
    # columna nunca llego. es_subempleo si esta en este caso, para probar
    # que cada columna se maneja de forma independiente.
    df = pd.DataFrame(
        {
            "condicion_actividad_cod": [2.0, 3.0],
            "es_subempleo": [0, 0],
            "sexo": [1, 2],
            "edad": [20, 40],
        }
    )
    resultado = prepare_empleo(df)
    assert "es_informal" not in resultado.columns
    assert resultado["es_subempleo"].tolist() == [False, False]
    assert resultado["condicion_actividad"].tolist() == ["Ocupados", "Desocupados"]


def test_prepare_empleo_deriva_es_informal_de_aporta_seguridad_social_si_no_hay_informal():
    # Desde 2025 INFORMAL ya no viene, pero si aporta_seguridad_social
    # (columna original f82, "aporte a fondo de pension") - se deriva
    # es_informal de ahi con el mismo criterio que el paquete oficial de R
    # del INE (employment_restrictions() en github.com/calcita/ech): no
    # aportar (valor 2) es informal. 0 = no aplica (fuera de Ocupados).
    df = pd.DataFrame(
        {
            "condicion_actividad_cod": [2.0, 2.0, 3.0],
            "aporta_seguridad_social": [1, 2, 0],
            "sexo": [1, 2, 1],
            "edad": [30, 35, 40],
        }
    )
    resultado = prepare_empleo(df)
    assert resultado["es_informal"].tolist() == [False, True, False]


def test_prepare_empleo_prefiere_es_informal_por_encima_de_aporta_seguridad_social():
    # Si por algun motivo llegaran ambas columnas (no deberia pasar hoy,
    # pero si algun año futuro las trae juntas), gana la precalculada del
    # INE (es_informal / INFORMAL), no la derivada.
    df = pd.DataFrame(
        {
            "condicion_actividad_cod": [2.0],
            "es_informal": [0],
            "aporta_seguridad_social": [2],  # diria informal si se usara esta
            "sexo": [1],
            "edad": [30],
        }
    )
    resultado = prepare_empleo(df)
    assert resultado["es_informal"].tolist() == [False]


def test_prepare_victimizacion_marca_victimizado_algun_delito():
    df = pd.DataFrame(
        {
            "sexo": [1, 2],
            "v3": [0, 0], "v4": [0, 1], "v5": [0, 0], "v6": [0, 0], "v7": [0, 0],
        }
    )
    resultado = prepare_victimizacion(df)
    assert resultado["sexo_grupo"].tolist() == ["1-Hombre", "2-Mujer"]
    assert resultado["victimizado_algun_delito"].tolist() == [False, True]


def test_melt_delitos_arma_formato_largo_con_subpreguntas_correctas():
    df = pd.DataFrame(
        {
            "id_persona": [1],
            "sexo_grupo": ["1-Hombre"],
            "departamento": ["MONTEVIDEO"],
            "ponderador_victimizacion": [100.0],
            "v3": [1], "v3_4": [1], "v3_6": [1], "v3_8": [2],
            "v4": [0], "v4_4": [0], "v4_6": [0], "v4_8": [0],
            "v5": [0], "v5_4": [0], "v5_6": [0], "v5_8": [0],
            "v6": [0], "v6_2": [0], "v6_4": [0],
            "v7": [0], "v7_4": [0], "v7_6": [0],
        }
    )
    largo = melt_delitos(df)

    fila_v3 = largo[largo["tipo_delito"] == "Robo total de vehículo"].iloc[0]
    assert fila_v3["victimizado"]
    assert fila_v3["comunicacion_policia"]
    assert not fila_v3["denuncia_formal"]
    assert fila_v3["violencia"]

    fila_v6 = largo[largo["tipo_delito"] == "Estafa"].iloc[0]
    # v6 (estafa) no tiene sub-pregunta de violencia en el cuestionario
    assert not fila_v6["violencia"]


def test_clasificar_tipo_hogar_coincide_con_la_taxonomia_de_referencia_en_hogares_al_azar():
    """La clasificación vectorizada (una pasada de groupby().any()) tiene
    que dar exactamente lo mismo que `_clasificar_tipo_hogar_codigos`,
    la definición legible de la taxonomía CELADE, hogar por hogar. Se
    prueba sobre mil hogares generados al azar con códigos de todo el
    rango (incluidos NaN y códigos fuera de todo conjunto), no solo sobre
    los seis casos de ejemplo — el cambio a vectorizado ahorró más de
    cinco segundos por corrida y este test es lo que impide que ese
    ahorro cambie un resultado en silencio."""
    import numpy as np
    from encuesta_hogares.preprocessing import _clasificar_tipo_hogar_codigos

    rng = np.random.default_rng(20260909)
    filas = []
    for id_hogar in range(1, 1001):
        n = int(rng.integers(1, 7))
        codigos = [1] + [int(c) for c in rng.choice([2, 3, 4, 5, 6, 8, 9, 12, 13, 14, 0, 99], size=n - 1)]
        for c in codigos:
            filas.append({"id_hogar": id_hogar, "parentesco_jefe": float(c) if rng.random() > 0.05 else np.nan,
                          "sexo": 1, "edad": 40})
    personas = pd.DataFrame(filas)
    hogares = pd.DataFrame({"id_hogar": range(1, 1001), "ponderador_hogar": 1.0})

    resultado = clasificar_tipo_hogar(personas, hogares).set_index("id_hogar")
    for id_hogar, grupo in personas.groupby("id_hogar")["parentesco_jefe"]:
        codigos = set(grupo.dropna().astype(int)) - {1}
        assert resultado.loc[id_hogar, "tipo_hogar"] == _clasificar_tipo_hogar_codigos(codigos), id_hogar
        esperado_mono = bool((grupo.isin([3, 4, 5])).any() and not (grupo == 2).any())
        assert bool(resultado.loc[id_hogar, "monoparental"]) is esperado_mono, id_hogar
