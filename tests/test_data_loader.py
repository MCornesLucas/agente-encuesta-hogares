import pytest

from encuesta_hogares import config
from encuesta_hogares.data_loader import (
    fix_doble_codificacion,
    fix_entidad_html_rota,
    fix_mojibake,
    load_empleo,
    load_hogares_personas_csv,
    load_victimizacion,
)


def test_fix_mojibake_replaces_broken_char():
    assert fix_mojibake("Ba¦ados de Carrasco") == "Bañados de Carrasco"


def test_fix_mojibake_leaves_clean_text_untouched():
    assert fix_mojibake("Pocitos") == "Pocitos"


def test_fix_mojibake_ignores_non_string_values():
    assert fix_mojibake(None) is None
    assert fix_mojibake(42) == 42


def test_fix_doble_codificacion_corrige_rio_negro():
    # Bytes reales encontrados en el CSV combinado 2024: la í de "Río Negro"
    # quedó en UTF-8 dentro de un archivo que en general es latin1.
    valor_roto = b"R\xc3\xado Negro".decode("latin1")
    assert fix_doble_codificacion(valor_roto) == "Río Negro"


def test_fix_doble_codificacion_deja_texto_ya_correcto_sin_tocar():
    assert fix_doble_codificacion("Paysandú") == "Paysandú"
    assert fix_doble_codificacion("Montevideo") == "Montevideo"


def test_fix_doble_codificacion_ignora_valores_no_string():
    assert fix_doble_codificacion(None) is None
    assert fix_doble_codificacion(42) == 42


def test_fix_entidad_html_rota_corrige_el_patron_encontrado_en_2025():
    # Bytes reales encontrados en el CSV combinado 2025 (ECH_2025_implantacion.csv,
    # verificado con xxd): el INE publico "San Jos<e9>", "Paysand<fa>" y
    # "Tacuaremb<f3>" en vez de los caracteres acentuados.
    assert fix_entidad_html_rota("San Jos<e9>") == "San José"
    assert fix_entidad_html_rota("Paysand<fa>") == "Paysandú"
    assert fix_entidad_html_rota("Tacuaremb<f3>") == "Tacuarembó"
    assert fix_entidad_html_rota("R<ed>o Negro") == "Río Negro"


def test_fix_entidad_html_rota_deja_texto_sin_el_patron_sin_tocar():
    assert fix_entidad_html_rota("Montevideo") == "Montevideo"
    assert fix_entidad_html_rota(None) is None
    assert fix_entidad_html_rota(42) == 42


def test_load_empleo_concatena_los_12_meses_y_renombra(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    carpeta = tmp_path / "2030"
    carpeta.mkdir()
    encabezado = ",".join(config.EMPLEO_COLUMNS)
    for mes in range(1, 13):
        fila = f"1,1,{mes},MONTEVIDEO,1,30,2,Empleado,Formal,1. CB incompleto o menos,0,0,150.5"
        (carpeta / f"ECH_{mes:02d}_30.csv").write_text(f"{encabezado}\n{fila}\n")

    df = load_empleo(2030)

    assert len(df) == 12
    assert sorted(df["mes"].unique()) == list(range(1, 13))
    assert "condicion_actividad_cod" in df.columns
    assert "ponderador_empleo" in df.columns
    assert "edad" in df.columns


def test_load_empleo_tolera_columnas_faltantes(tmp_path, monkeypatch):
    # INFORMAL/SECTOR_F/SIT_OCUP desaparecieron de los archivos mensuales
    # desde 2025 (verificado contra los datos reales que bajo el INE) -
    # load_empleo no tiene que romper por eso, solo no traer esas columnas.
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    carpeta = tmp_path / "2025"
    carpeta.mkdir()
    valores = {
        "ID": "1", "nper": "1", "mes": "1", "nom_dpto": "MONTEVIDEO", "e26": "1", "e27": "30",
        "POBPCOAC": "2", "SIT_OCUP": "Empleado", "SECTOR_F": "Formal",
        "NIV_EDU": "1. CB incompleto o menos", "INFORMAL": "0", "SUBEMPLEO": "0", "W": "150.5",
        "f82": "1",
    }
    columnas_2025 = [c for c in config.EMPLEO_COLUMNS if c not in ("INFORMAL", "SECTOR_F", "SIT_OCUP")]
    encabezado = ",".join(columnas_2025)
    for mes in range(1, 13):
        valores["mes"] = str(mes)
        fila = ",".join(valores[c] for c in columnas_2025)
        (carpeta / f"ECH_{mes:02d}_2025.csv").write_text(f"{encabezado}\n{fila}\n")

    df = load_empleo(2025)

    assert len(df) == 12
    assert "es_informal" not in df.columns
    assert "situacion_ocupacional" not in df.columns
    assert "sector_formalidad" not in df.columns
    assert "aporta_seguridad_social" in df.columns
    assert "es_subempleo" in df.columns


def test_load_hogares_personas_csv_corrige_departamento_mal_codificado(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    carpeta = tmp_path / "2030"
    carpeta.mkdir()

    # Excluye las columnas nuevas de 2025 (pobre17/indig17/YDA_SVL) a
    # propósito - este test simula un archivo estilo 2024 (solo la
    # variante vieja), no el caso de columnas faltantes/duplicadas, que
    # ya tienen sus propios tests.
    columnas = sorted(
        (set(config.HOGARES_COLUMNS_CSV) | set(config.PERSONAS_COLUMNS_CSV))
        - {"pobre17", "indig17", "YDA_SVL"}
    )
    # Marcador de texto (se reemplaza por los bytes reales más abajo, para no
    # depender de cómo este archivo fuente guarde caracteres no-ASCII).
    valores = {
        "ESTRED13": "1", "ID": "1", "POBPCOAC": "2", "PT1": "100", "YSVL": "50000",
        "barrio": "5", "c5_2": "1", "c5_10": "1", "c5_11": "2", "c5_12": "2", "d21_15": "1",
        "d21_16": "1", "d21_16_1": "1", "d21_16_2": "2", "d21_21": "2", "d21_7": "1",
        "d24": "0", "d25": "3", "d9": "3", "d21_15_5": "2", "e26": "1", "e27": "30", "e30": "1",
        "indig06": "0",
        "nom_dpto": "MARCADOR_DEPARTAMENTO",
        "nper": "1", "pobre06": "0", "W_ANO": "150.5",
    }
    encabezado = ",".join(columnas)
    fila = ",".join(valores[c] for c in columnas)
    contenido = f"{encabezado}\n{fila}\n".encode("ascii")
    # Bytes reales encontrados en el CSV combinado 2024 para "Río Negro"
    # (í en UTF-8 dentro de un archivo que en general está en latin1).
    contenido = contenido.replace(b"MARCADOR_DEPARTAMENTO", b"R\xc3\xado Negro")
    (carpeta / "ECH_2030.csv").write_bytes(contenido)

    hogares, personas = load_hogares_personas_csv(2030)

    assert hogares.loc[0, "departamento"] == "Río Negro"
    assert len(personas) == 1
    # El ponderador de muestreo llega a Hogares (viene de W_ANO). A
    # propósito NO se mapea también en Personas (ver la nota en
    # PERSONAS_COLUMNS_CSV en config.py): aunque el CSV combinado trae el
    # mismo valor repetido por persona, mapearlo en los dos lados
    # duplicaría la columna como "ponderador_hogar_x"/"_y" en cualquier
    # merge posterior entre Hogares y Personas. Llega a las tablas de
    # persona vía preprocessing.merge_personas, no desde acá.
    assert hogares.loc[0, "ponderador_hogar"] == 150.5
    assert "ponderador_hogar" not in personas.columns


def test_load_hogares_personas_csv_usa_pobre17_cuando_no_hay_pobre06(tmp_path, monkeypatch):
    # Caso real 2025: pobre06/indig06/YSVL ya no estan, en su lugar llegan
    # pobre17/indig17/YDA_SVL (nueva metodologia de canasta). El resultado
    # tiene que llegar igual a "pobre"/"indigente"/"ingreso_hogar" - no
    # romper ni quedar sin esas columnas.
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    carpeta = tmp_path / "2031"
    carpeta.mkdir()

    columnas = sorted(
        (set(config.HOGARES_COLUMNS_CSV) | set(config.PERSONAS_COLUMNS_CSV))
        - {"pobre06", "indig06", "YSVL"}
    )
    valores = {
        "ESTRED13": "1", "ID": "1", "POBPCOAC": "2", "PT1": "100", "YDA_SVL": "64309",
        "barrio": "5", "c5_2": "1", "c5_10": "1", "c5_11": "2", "c5_12": "2", "d21_15": "1",
        "d21_16": "1", "d21_16_1": "1", "d21_16_2": "2", "d21_21": "2", "d21_7": "1",
        "d24": "0", "d25": "3", "d9": "3", "d21_15_5": "2", "e26": "1", "e27": "30", "e30": "1",
        "indig17": "0",
        "nom_dpto": "Montevideo",
        "nper": "1", "pobre17": "1", "W_ANO": "150.5",
    }
    encabezado = ",".join(columnas)
    fila = ",".join(valores[c] for c in columnas)
    (carpeta / "ECH_2031.csv").write_text(f"{encabezado}\n{fila}\n")

    hogares, _personas = load_hogares_personas_csv(2031)

    assert hogares.loc[0, "pobre"] == 1
    assert hogares.loc[0, "indigente"] == 0
    assert hogares.loc[0, "ingreso_hogar"] == 64309


def test_load_hogares_personas_csv_prefiere_pobre17_cuando_llegan_las_dos_variantes(tmp_path, monkeypatch):
    # Caso real 2024: es un año de transición, trae pobre06/indig06/YSVL Y
    # pobre17/indig17/YDA_SVL a la vez. Confirmado con el usuario: se
    # queda con la metodología nueva (canasta 2017) también para 2024, no
    # solo para 2025 en adelante - ver config.PREFERENCIA_METODOLOGIA_HOGARES.
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    carpeta = tmp_path / "2024"
    carpeta.mkdir()

    columnas = sorted(set(config.HOGARES_COLUMNS_CSV) | set(config.PERSONAS_COLUMNS_CSV))
    valores = {
        "ESTRED13": "1", "ID": "1", "POBPCOAC": "2", "PT1": "100",
        "YSVL": "50000", "YDA_SVL": "64309",
        "barrio": "5", "c5_2": "1", "c5_10": "1", "c5_11": "2", "c5_12": "2", "d21_15": "1",
        "d21_16": "1", "d21_16_1": "1", "d21_16_2": "2", "d21_21": "2", "d21_7": "1",
        "d24": "0", "d25": "3", "d9": "3", "d21_15_5": "2", "e26": "1", "e27": "30", "e30": "1",
        "indig06": "1", "indig17": "0",
        "nom_dpto": "Montevideo",
        "nper": "1", "pobre06": "1", "pobre17": "0", "W_ANO": "150.5",
    }
    encabezado = ",".join(columnas)
    fila = ",".join(valores[c] for c in columnas)
    (carpeta / "ECH_2024.csv").write_text(f"{encabezado}\n{fila}\n")

    hogares, _personas = load_hogares_personas_csv(2024)

    # pobre17=0/indig17=0/YDA_SVL=64309 tienen que ganar, no pobre06=1/
    # indig06=1/YSVL=50000 (que darían un resultado distinto si se
    # hubiera elegido mal).
    assert hogares.loc[0, "pobre"] == 0
    assert hogares.loc[0, "indigente"] == 0
    assert hogares.loc[0, "ingreso_hogar"] == 64309


def test_load_hogares_personas_csv_corta_si_hay_una_colision_no_contemplada(tmp_path, monkeypatch):
    # Red de seguridad residual: si algún día aparece una colisión que
    # PREFERENCIA_METODOLOGIA_HOGARES no sepa resolver, tiene que cortar
    # con un error claro, no elegir en silencio ni duplicar una columna.
    # Se simula agregando a mano una entrada falsa a HOGARES_COLUMNS_CSV
    # que colisiona con "estrato_tipo", sin pasar por PREFERENCIA_*.
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setitem(config.HOGARES_COLUMNS_CSV, "OTRA_COLUMNA_ESTRATO", "estrato_tipo")
    carpeta = tmp_path / "2033"
    carpeta.mkdir()
    columnas = ["ID", "nper", "POBPCOAC", "ESTRED13", "OTRA_COLUMNA_ESTRATO"]
    (carpeta / "ECH_2033.csv").write_text(",".join(columnas) + "\n1,1,2,1,3\n")

    with pytest.raises(ValueError):
        load_hogares_personas_csv(2033)


def test_load_victimizacion_agrega_departamento_por_join(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    carpeta = tmp_path / "2030"
    carpeta.mkdir()

    encabezado_v = ",".join(config.VICTIMIZACION_COLUMNS)
    fila_v = "1,1,1," + ",".join(["0"] * 18) + ",120.0"
    (carpeta / "ECH_VICTIMIZACION_S2_2030.csv").write_text(f"{encabezado_v}\n{fila_v}\n")

    for mes in range(7, 13):
        (carpeta / f"ECH_{mes:02d}_30.csv").write_text("ID,nom_dpto\n1,MONTEVIDEO\n")

    df = load_victimizacion(2030)

    assert len(df) == 1
    assert df.loc[0, "departamento"] == "MONTEVIDEO"
    assert "ponderador_victimizacion" in df.columns
