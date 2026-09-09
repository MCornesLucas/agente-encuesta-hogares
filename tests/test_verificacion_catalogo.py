from encuesta_hogares import config, verificacion_catalogo as vc


def test_toda_metrica_del_catalogo_tiene_entrada_en_el_manifiesto():
    catalogo = vc.numeros_del_catalogo()
    faltantes = vc.metricas_sin_manifiesto(catalogo)
    detalle = "\n".join(f"  - {n}: {catalogo[n]}" for n in sorted(faltantes))
    assert not faltantes, (
        "Hay métricas en el catálogo (formularios.py) sin entrada en "
        "verificacion_catalogo.MANIFEST — agregales la(s) función(es) que "
        "las implementan:\n\n" + detalle
    )


def test_manifiesto_no_tiene_entradas_obsoletas():
    catalogo = vc.numeros_del_catalogo()
    obsoletas = vc.entradas_manifiesto_obsoletas(catalogo)
    assert not obsoletas, (
        f"MANIFEST tiene entradas para métricas que ya no están en el "
        f"catálogo: {sorted(obsoletas)} — revisar si se renumeraron o se "
        f"eliminaron, y limpiar la entrada."
    )


def test_toda_referencia_del_manifiesto_resuelve_a_una_funcion_real():
    rotas = vc.referencias_rotas()
    detalle = "\n".join(f"  - métrica {r.numero}: {r.referencia}" for r in rotas)
    assert not rotas, (
        "MANIFEST referencia funciones que no existen de verdad — la "
        "métrica quedó huérfana (nunca implementada, o la función se "
        "borró/renombró después):\n\n" + detalle
    )


def test_toda_metrica_del_manifiesto_tiene_su_funcion_validada_con_datos_reales():
    faltantes = vc.metricas_sin_funcion_validada_con_datos_reales()
    detalle = "\n".join(f"  - {n}: {nombres}" for n, nombres in sorted(faltantes.items()))
    assert not faltantes, (
        "Hay métricas cuya función nunca se invoca en "
        "tools/validar_con_datos_reales.py — el pipeline puede pasar la "
        "suite sintética y calcular mal contra datos reales sin que nada "
        "lo note. Agregá una llamada real (con datos de al menos un año) "
        "y un assert de invariante genérico (ej. 0 <= pct <= 100):\n\n" + detalle
    )


def test_numeros_del_catalogo_cubre_los_42_bloques_conocidos():
    catalogo = vc.numeros_del_catalogo()
    assert min(catalogo) == 1
    assert max(catalogo) == 42
    assert len(catalogo) == 42


def test_resolver_devuelve_none_para_una_referencia_inexistente():
    entrada_falsa = {"funciones": ["analysis.esta_funcion_no_existe"], "visualizacion": "visualization.plot_brecha_digital"}
    original = vc.MANIFEST.get(9999)
    vc.MANIFEST[9999] = entrada_falsa
    try:
        rotas = vc.referencias_rotas()
    finally:
        if original is None:
            del vc.MANIFEST[9999]
        else:
            vc.MANIFEST[9999] = original

    assert any(r.numero == 9999 and r.referencia == "analysis.esta_funcion_no_existe" for r in rotas)


def test_metricas_no_disponibles_acepta_cualquier_opcion_completa():
    # Caso real 2025: falta INFORMAL pero esta f82 - la 32/33 tienen que
    # quedar disponibles (segunda opcion completa), no marcadas.
    columnas = {"ID", "nper", "mes", "POBPCOAC", "f82", "SUBEMPLEO", "W"}
    no_disponibles = vc.metricas_no_disponibles(columnas)
    assert 31 not in no_disponibles
    assert 32 not in no_disponibles


def test_metricas_no_disponibles_marca_metrica_sin_ninguna_opcion_completa():
    # Caso real 2025: SIT_OCUP y SECTOR_F no estan, sin ningun camino
    # alternativo conocido para la metrica 36.
    columnas = {"ID", "nper", "mes", "POBPCOAC", "INFORMAL", "SUBEMPLEO", "W"}
    no_disponibles = vc.metricas_no_disponibles(columnas)
    assert 31 not in no_disponibles
    assert set(no_disponibles[35]) == {"SIT_OCUP", "SECTOR_F"}


def test_metricas_empleo_no_disponibles_lee_el_primer_archivo_existente(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    carpeta = tmp_path / "2025"
    carpeta.mkdir()
    columnas_2025 = [c for c in config.EMPLEO_COLUMNS if c not in ("INFORMAL", "SECTOR_F", "SIT_OCUP")]
    (carpeta / "ECH_01_2025.csv").write_text(",".join(columnas_2025) + "\n")

    no_disponibles = vc.metricas_empleo_no_disponibles("2025")

    assert 31 not in no_disponibles  # f82 esta en columnas_2025
    assert set(no_disponibles[35]) == {"SIT_OCUP", "SECTOR_F"}


def test_metricas_empleo_no_disponibles_vacio_si_no_hay_archivos(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    assert vc.metricas_empleo_no_disponibles("2030") == {}


def test_aviso_metricas_no_disponibles_redacta_mensaje_legible(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    carpeta = tmp_path / "2025"
    carpeta.mkdir()
    columnas_2025 = [c for c in config.EMPLEO_COLUMNS if c not in ("INFORMAL", "SECTOR_F", "SIT_OCUP")]
    (carpeta / "ECH_01_2025.csv").write_text(",".join(columnas_2025) + "\n")

    avisos = vc.aviso_metricas_no_disponibles("2025")

    assert len(avisos) == 1
    assert "Métrica 35" in avisos[0]
    assert "SIT_OCUP" in avisos[0] and "SECTOR_F" in avisos[0]


def test_metricas_empleo_no_disponibles_no_marca_metricas_de_vivienda(tmp_path, monkeypatch):
    # Caso real que este test evita repetir: al agregar las entradas de
    # Vivienda (17-21) a COLUMNAS_REQUERIDAS, metricas_empleo_no_disponibles
    # las marcaba igual como "no disponibles" solo porque el archivo de
    # Empleo (obviamente) no tiene columnas de vivienda - metricas_no_disponibles
    # ahora necesita saber que a un archivo de Empleo solo le corresponde
    # responder por las métricas de Empleo.
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    carpeta = tmp_path / "2025"
    carpeta.mkdir()
    (carpeta / "ECH_01_2025.csv").write_text(",".join(config.EMPLEO_COLUMNS) + "\n")

    no_disponibles = vc.metricas_empleo_no_disponibles("2025")

    assert not {13, 14, 15, 16, 17, 18, 19, 20} & set(no_disponibles)


def test_metricas_hogares_no_disponibles_detecta_modulo_vivienda_ausente(tmp_path, monkeypatch):
    # Caso real: 2023 no tiene ninguna columna del módulo C5 en el CSV
    # combinado de Hogares/Personas.
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    carpeta = tmp_path / "2023"
    carpeta.mkdir()
    columnas_sin_vivienda = [c for c in config.HOGARES_COLUMNS_CSV if c not in config.CONDICIONES_VIVIENDA_COLUMNS_CSV]
    (carpeta / "ECH_2023.csv").write_text(",".join(columnas_sin_vivienda) + "\n")

    no_disponibles = vc.metricas_hogares_no_disponibles("2023")

    assert set(no_disponibles) == {13, 14, 15, 16, 17, 18, 19, 20}
    # metricas de Empleo no deberian aparecer al chequear un archivo de Hogares
    assert 31 not in no_disponibles and 36 not in no_disponibles


def test_metricas_hogares_no_disponibles_ok_si_hay_al_menos_una_columna(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    carpeta = tmp_path / "2030"
    carpeta.mkdir()
    (carpeta / "ECH_2030.csv").write_text(",".join(config.HOGARES_COLUMNS_CSV) + "\n")

    assert vc.metricas_hogares_no_disponibles("2030") == {}


def test_aviso_metricas_no_disponibles_incluye_vivienda(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    carpeta = tmp_path / "2023"
    carpeta.mkdir()
    columnas_sin_vivienda = [c for c in config.HOGARES_COLUMNS_CSV if c not in config.CONDICIONES_VIVIENDA_COLUMNS_CSV]
    (carpeta / "ECH_2023.csv").write_text(",".join(columnas_sin_vivienda) + "\n")

    avisos = vc.aviso_metricas_no_disponibles("2023")

    numeros_avisados = {int(a.split(" ")[1]) for a in avisos}
    assert {13, 14, 15, 16, 17, 18, 19, 20} <= numeros_avisados


# ============================================================================
# Qué bloques se le ofrecen a la persona según el año. Nace de una corrida
# real: se eligió 2023 y se marcó solo "Territorio", que para ese año está
# completamente vacío (el INE no relevó el módulo C5). El catálogo quedaba
# sin ninguna métrica y el flujo volvía al formulario de áreas sin explicar
# nada — parecía un error del programa. Peor era el caso silencioso: con
# Territorio + otro bloque, el informe salía sin métricas territoriales y
# sin ningún aviso.
# ============================================================================

def _sin_datos(tmp_path, monkeypatch, anio, columnas_fuera=(), con_empleo=True):
    """Arma un año sintético al que le faltan ciertas columnas de Hogares."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    carpeta = tmp_path / anio
    carpeta.mkdir()
    columnas = [c for c in config.HOGARES_COLUMNS_CSV if c not in columnas_fuera]
    columnas += [c for c in config.PERSONAS_COLUMNS_CSV if c not in columnas]
    (carpeta / f"ECH_{anio}.csv").write_text(",".join(columnas) + "\n")
    if con_empleo:
        for archivo in config.empleo_files(anio):
            archivo.write_text(",".join(config.EMPLEO_COLUMNS) + "\n")


def test_no_se_ofrece_un_bloque_que_quedaria_vacio(tmp_path, monkeypatch):
    # Caso real 2023: sin el módulo C5 no hay Vivienda ni Territorio.
    _sin_datos(tmp_path, monkeypatch, "2030", columnas_fuera=set(config.CONDICIONES_VIVIENDA_COLUMNS_CSV))

    bloques = vc.bloques_disponibles("2030")

    assert bloques["vivienda_disponible"] is False
    assert bloques["territorio_disponible"] is False
    assert bloques["hogares_disponible"] is True, "Hogares no depende del módulo de vivienda"
    assert bloques["brecha_digital_disponible"] is True


def test_el_motivo_de_cada_bloque_ausente_llega_al_formulario(tmp_path, monkeypatch):
    _sin_datos(tmp_path, monkeypatch, "2030", columnas_fuera=set(config.CONDICIONES_VIVIENDA_COLUMNS_CSV))

    bloques = vc.bloques_disponibles("2030")

    assert "Vivienda" in bloques["no_disponibles"]
    assert "c5_2" in bloques["no_disponibles"]["Vivienda"], (
        "El motivo tiene que decir qué falta, no solo que no está"
    )


def test_territorio_necesita_empleo(tmp_path, monkeypatch):
    # Caso real 2019: tiene el módulo de vivienda pero no el de empleo, y
    # desde la v0.10.0 el índice territorial lleva la tasa de empleo.
    _sin_datos(tmp_path, monkeypatch, "2030", con_empleo=False)

    bloques = vc.bloques_disponibles("2030")

    assert bloques["territorio_disponible"] is False
    assert bloques["vivienda_disponible"] is True, "Vivienda no depende de Empleo"
    assert "Empleo" in bloques["no_disponibles"]["Territorio"]


def test_un_anio_completo_ofrece_los_siete_bloques(tmp_path, monkeypatch):
    _sin_datos(tmp_path, monkeypatch, "2030")
    carpeta = tmp_path / "2030"
    (carpeta / "base_FIES_2030.csv").write_text(",".join(config.FIES_COLUMNS) + "\n")
    config.victimizacion_file("2030").write_text(",".join(config.VICTIMIZACION_COLUMNS) + "\n")

    bloques = vc.bloques_disponibles("2030")

    faltan = [k for k, v in bloques.items() if k.endswith("_disponible") and not v]
    assert not faltan, f"con todos los datos no debería faltar ningún bloque: {faltan}"
    assert bloques["no_disponibles"] == {}


def test_bloques_disponibles_encaja_con_la_firma_de_plantilla_areas(tmp_path, monkeypatch):
    """Se usan juntas con **: si una cambia y la otra no, esto falla acá y
    no en medio de una corrida real."""
    import inspect

    from encuesta_hogares import formularios

    _sin_datos(tmp_path, monkeypatch, "2030")
    argumentos = set(vc.bloques_disponibles("2030"))
    parametros = set(inspect.signature(formularios.plantilla_areas).parameters)
    assert argumentos <= parametros, (
        f"bloques_disponibles() devuelve argumentos que plantilla_areas no acepta: "
        f"{sorted(argumentos - parametros)}"
    )


def test_los_bloques_y_las_plantillas_salen_del_catalogo_y_del_manifiesto():
    """Catálogo (plantillas.py), manifiesto (MANIFEST), bloques (BLOQUES) y
    plantillas del informe (notebook_builder.GENERADORES) describen el
    mismo conjunto de métricas. Antes los números vivían en tres lugares
    escritos a mano (un rango por bloque, `range(1, 43)` en el
    constructor); ahora se derivan del catálogo y este test lo ata."""
    from encuesta_hogares import notebook_builder as nb
    from encuesta_hogares import verificacion_catalogo as vc

    numeros_catalogo = set(vc.numeros_del_catalogo())
    en_bloques = [n for rango, _nombre in vc.BLOQUES.values() for n in rango]
    assert sorted(en_bloques) == sorted(numeros_catalogo), "cada métrica del catálogo está en exactamente un bloque"
    assert len(en_bloques) == len(set(en_bloques))
    assert set(vc.MANIFEST) == numeros_catalogo
    assert set(nb.GENERADORES) == numeros_catalogo
    assert list(vc.BLOQUES) == ["brecha_digital", "hogares", "territorio", "vivienda", "fies", "empleo", "seguridad"]
    assert vc.BLOQUES["territorio"] == (range(13, 16), "Territorio")
