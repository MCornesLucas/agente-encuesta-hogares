"""El pipeline `generar_informe` y las verificaciones deterministas del
notebook (`verificacion_notebook`).

Regla del proyecto (la misma de los hooks): cada verificación se prueba en
las dos direcciones — deja pasar el informe real que arma
`notebook_builder` y bloquea una copia saboteada. Y el pipeline no ejecuta
el notebook si la verificación previa falla: acá se comprueba que
`nbconvert` ni se invoca en ese caso.
"""

from __future__ import annotations

import json
from pathlib import Path

import nbformat
import pytest

from encuesta_hogares import generar_informe as gi
from encuesta_hogares import notebook_builder as nb
from encuesta_hogares import verificacion_catalogo as vc
from encuesta_hogares import verificacion_notebook as vn


def _notebook_real(tmp_path: Path, metricas=None, **kw) -> dict:
    celdas = nb.construir_celdas_notebook(
        anio_base=2025, metricas=metricas or sorted(vc.MANIFEST),
        incluir_brecha_digital=kw.get("brecha", True), incluir_fies=kw.get("fies", True),
        incluir_empleo=kw.get("empleo", True), incluir_seguridad=kw.get("seguridad", True),
    )
    ruta = tmp_path / "real.ipynb"
    nb.escribir_notebook(celdas, ruta)
    return json.loads(ruta.read_text(encoding="utf-8"))


def _celda_md(texto):
    return {"cell_type": "markdown", "source": texto, "metadata": {}}


def _celda_code(texto, outputs=None):
    return {"cell_type": "code", "source": texto, "metadata": {}, "outputs": outputs or []}


# --- antes de ejecutar --------------------------------------------------------


def test_el_informe_real_completo_pasa_la_verificacion_previa(tmp_path):
    notebook = _notebook_real(tmp_path)
    assert vn.verificar_antes_de_ejecutar(notebook) == []


def test_detecta_la_grafica_duplicada_por_variable_suelta(tmp_path):
    notebook = _notebook_real(tmp_path, metricas=[1, 2])
    celda = next(c for c in notebook["cells"] if c["cell_type"] == "code" and "viz.plot_" in "".join(c["source"]))
    celda["source"] = "".join(celda["source"]).replace("fig.show()", "fig")
    problemas = vn.celdas_que_duplican_grafica(notebook)
    assert len(problemas) == 1 and "«fig»" in problemas[0]


def test_detecta_una_metrica_sin_cita_y_otra_sin_grafica(tmp_path):
    notebook = _notebook_real(tmp_path, metricas=[7, 8])
    # Métrica 7: se le borra la justificación (la cita vive ahí).
    indices = [i for i, c in enumerate(notebook["cells"]) if c["cell_type"] == "markdown"
               and "".join(c["source"]).startswith("### 7.")]
    i7 = indices[0]
    for j in range(i7 + 1, len(notebook["cells"])):
        c = notebook["cells"][j]
        if c["cell_type"] == "markdown" and "".join(c["source"]).startswith("### "):
            break
        if c["cell_type"] == "markdown":
            c["source"] = "Texto sin ninguna referencia."
    # Métrica 8: se le borra la gráfica.
    i8 = next(i for i, c in enumerate(notebook["cells"]) if c["cell_type"] == "markdown"
              and "".join(c["source"]).startswith("### 8."))
    for c in notebook["cells"][i8 + 1:]:
        if c["cell_type"] == "code":
            c["source"] = "x = 1"
            break
    problemas = vn.metricas_sin_grafica_o_cita(notebook)
    assert any(p.startswith("métrica 7:") and "cita" in p for p in problemas), problemas
    assert any(p.startswith("métrica 8:") and "gráfica" in p for p in problemas), problemas


def test_un_notebook_sin_metricas_reconocibles_no_pasa_en_silencio():
    notebook = {"cells": [_celda_md("## Algo"), _celda_code("x = 1")]}
    problemas = vn.metricas_sin_grafica_o_cita(notebook)
    assert len(problemas) == 1 and "no se reconoció ninguna métrica" in problemas[0]


def test_detecta_placeholders_y_encabezados_repetidos():
    notebook = {"cells": [
        _celda_md("### 1. Métrica\n\nPregunta."),
        _celda_md("Resumen (pendiente) de la sección."),
        _celda_md("### 1. Métrica\n\nOtra vez."),
    ]}
    assert vn.placeholders_en_el_texto(notebook) == ["celda 1: texto sin completar («(pendiente)»)"]
    repetidos = vn.encabezados_repetidos(notebook)
    assert len(repetidos) == 1 and "celda 2" in repetidos[0]


# --- después de ejecutar ------------------------------------------------------


def test_detecta_errores_y_graficas_sin_imagen():
    con_imagen = [{"output_type": "display_data", "data": {"image/png": "..."}, "metadata": {}}]
    notebook = {"cells": [
        _celda_code("fig = viz.plot_a(df)\nfig.show()", con_imagen),
        _celda_code("fig = viz.plot_b(df)\nfig.show()", []),
        _celda_code("1/0", [{"output_type": "error", "ename": "ZeroDivisionError", "evalue": "division by zero"}]),
    ]}
    assert vn.graficas_faltantes(notebook) == ["celda 1: llama a viz.plot_... y no produjo ninguna imagen"]
    assert vn.celdas_con_error(notebook) == ["celda 2: ZeroDivisionError: division by zero"]
    assert vn.verificar_despues_de_ejecutar({"cells": [_celda_code("fig = viz.plot_a(df)\nfig.show()", con_imagen)]}) == []


# --- cifras del resumen -------------------------------------------------------


def test_cifras_del_resumen_se_validan_con_redondeo_y_sin_anios():
    reales = [45.31, 7.4, 1234.0]
    assert vn.cifras_sin_respaldo("En 2025 el 45,3% de los hogares y una tasa de 7,4.", reales) == []
    assert vn.cifras_sin_respaldo("El 12,5% de los hogares.", reales) == ["12,5%"]
    assert vn.cifras_sin_respaldo("Unos 1.234 hogares.", reales) == []  # separador de miles: 1234
    assert vn.cifras_sin_respaldo("Unos 1.235 hogares.", reales) == ["1.235"]
    assert vn.placeholders_en_el_texto({"cells": [{"cell_type": "markdown", "source": "todo el país"}]}) == []


def test_los_numeros_del_json_de_cifras_respaldan_al_resumen():
    cifras = {"tabla": [{"departamento": "Colonia", "pct": 23.46}], "tasas": {"tasa_empleo": 58.1}, "n": 12}
    numeros = vn.numeros_de_cifras(cifras)
    assert 23.46 in numeros and 58.1 in numeros and 12.0 in numeros
    assert vn.cifras_sin_respaldo("Colonia tiene 23,5% y la tasa de empleo es 58,1%.", numeros) == []


def test_texto_del_resumen_toma_desde_el_encabezado_hasta_el_final():
    notebook = {"cells": [_celda_md("### 1. Algo"), _celda_md("## Resumen analítico final"), _celda_md("Primer párrafo."), _celda_md("Segundo.")]}
    assert vn.texto_del_resumen(notebook) == "Primer párrafo.\nSegundo."


# --- el pipeline --------------------------------------------------------------


def test_construir_no_ejecuta_el_notebook_si_la_verificacion_previa_falla(tmp_path, monkeypatch):
    def no_deberia_correr(*a, **k):
        raise AssertionError("nbconvert no debe invocarse si la verificación previa falla")
    monkeypatch.setattr(gi.bitacora, "medir_comando", no_deberia_correr)

    extra = tmp_path / "extra.py"
    extra.write_text(
        "from encuesta_hogares.notebook_builder import Celda\n"
        "celdas_extra = {1: [Celda(markdown='### 99. A medida\\n\\nPregunta.', codigo='fig = viz.plot_x(df)\\nfig', "
        "markdown_final='Justificación (Cleveland & McGill, 1984).')]}\n",
        encoding="utf-8",
    )
    with pytest.raises(gi.InformeInvalido, match="no pasa la verificación previa"):
        gi.construir(2025, [1], ["brecha_digital"], extra=extra, destino=tmp_path / "Informe_ECH_2025.ipynb")
    # El notebook se escribió igual (para poder mirarlo), con la celda de cifras al final.
    escrito = json.loads((tmp_path / "Informe_ECH_2025.ipynb").read_text(encoding="utf-8"))
    assert "_cifras" in "".join(escrito["cells"][-1]["source"])


def test_construir_rechaza_bloques_desconocidos(tmp_path):
    with pytest.raises(gi.InformeInvalido, match="bloques desconocidos"):
        gi.construir(2025, [1], ["brecha"], destino=tmp_path / "x.ipynb")


def test_cargar_extras_exige_la_forma_correcta(tmp_path):
    malo = tmp_path / "malo.py"
    malo.write_text("celdas_extra = [1, 2]\n", encoding="utf-8")
    with pytest.raises(gi.InformeInvalido, match="celdas_extra"):
        gi._cargar_extras(malo)
    assert gi._cargar_extras(None) == ({}, [])


def _notebook_ejecutado_falso(ruta: Path, con_resumen_viejo=False) -> None:
    notebook = nbformat.v4.new_notebook()
    notebook.cells.append(nbformat.v4.new_markdown_cell("## Hogares"))
    notebook.cells.append(nbformat.v4.new_markdown_cell("### 8. Tipos de hogar\n\n**¿Qué pregunta responde?** X"))
    celda = nbformat.v4.new_code_cell("fig = viz.plot_a(df)\nfig.show()")
    celda.outputs = [nbformat.v4.new_output("stream", name="stdout", text="Hogares: 23,544\n"),
                     nbformat.v4.new_output("display_data", data={"image/png": "AAAA"})]
    notebook.cells.append(celda)
    notebook.cells.append(nbformat.v4.new_markdown_cell("Justificación (Cleveland & McGill, 1984)."))
    if con_resumen_viejo:
        notebook.cells.append(nbformat.v4.new_markdown_cell("## Resumen analítico final"))
        notebook.cells.append(nbformat.v4.new_markdown_cell("Texto viejo con 99,9%."))
    nbformat.write(notebook, str(ruta))
    nb.ruta_cifras(ruta).write_text(json.dumps({"tipos": [{"tipo_hogar": "Nuclear", "pct": 41.27}]}), encoding="utf-8")


def test_entregar_agrega_el_resumen_verificado_y_las_fuentes_del_bloque(tmp_path):
    ruta = tmp_path / "Informe_ECH_2025.ipynb"
    _notebook_ejecutado_falso(ruta, con_resumen_viejo=True)
    bloques = gi._agregar_resumen(ruta, "Los hogares nucleares son el 41,3% del total (23.544 hogares).")
    assert bloques == ["hogares"]
    notebook = nbformat.read(str(ruta), as_version=4)
    textos = [c.source for c in notebook.cells if c.cell_type == "markdown"]
    assert textos.count("## Resumen analítico final") == 1, "el resumen viejo se reemplaza, no se duplica"
    assert not any("99,9%" in t for t in textos)
    assert any("41,3%" in t for t in textos)
    assert any(t.startswith("### Fuentes de consulta para alineación de métricas") and "CEPALSTAT" in t for t in textos)


def test_entregar_rechaza_una_cifra_que_no_esta_en_los_resultados(tmp_path):
    ruta = tmp_path / "Informe_ECH_2025.ipynb"
    _notebook_ejecutado_falso(ruta)
    with pytest.raises(gi.InformeInvalido, match="57,2%"):
        gi._agregar_resumen(ruta, "Los hogares nucleares son el 57,2% del total.")
    with pytest.raises(gi.InformeInvalido, match="sin completar"):
        gi._agregar_resumen(ruta, "Resumen (pendiente).")


def test_entregar_exige_un_notebook_ejecutado(tmp_path):
    ruta = tmp_path / "Informe_ECH_2025.ipynb"
    notebook = nbformat.v4.new_notebook()
    notebook.cells.append(nbformat.v4.new_code_cell("x = 1"))
    nbformat.write(notebook, str(ruta))
    with pytest.raises(gi.InformeInvalido, match="no está ejecutado"):
        gi._agregar_resumen(ruta, "Texto.")


def test_main_devuelve_2_y_explica_cuando_el_informe_no_se_genera(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(gi, "ruta_notebook", lambda anio: tmp_path / f"Informe_ECH_{anio}.ipynb")
    codigo = gi.main(["entregar", "--anio", "2025", "--resumen", str(tmp_path / "no_existe.md")])
    assert codigo == 2
    assert "INFORME NO GENERADO" in capsys.readouterr().err


def test_las_fuentes_por_bloque_cubren_todos_los_bloques_menos_fies():
    assert set(nb._FUENTES_POR_BLOQUE) == set(vc.BLOQUES) - {"fies"}
    assert nb.fuentes_de_consulta(["fies"]) == []
    # Sin repetir: Brecha Digital y Hogares comparten la lista.
    assert len(nb.fuentes_de_consulta(["brecha_digital", "hogares"])) == len(nb._FUENTES_POR_BLOQUE["hogares"])


def test_la_celda_de_cifras_es_la_ultima_y_no_imprime_nada(tmp_path):
    celda = nb.celda_cifras(tmp_path / "Informe_ECH_2025.ipynb")
    compile(celda.codigo, "cifras", "exec")
    assert "print(" not in celda.codigo
    assert celda.markdown == ""
    assert nb.ruta_cifras(tmp_path / "Informe_ECH_2025.ipynb").name == "_cifras_Informe_ECH_2025.json"


def test_la_portada_del_pdf_lleva_titulo_subtitulo_y_solo_la_fecha():
    """La portada es texto visible que no pasa por las celdas del notebook:
    título con el año, subtítulo que describe el contenido y solo la fecha
    como pie (sin nombres de programas ni de proyectos)."""
    import html
    import re
    texto = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", gi.portada(2025))))
    assert "Encuesta Continua de Hogares 2025 — Informe" in texto
    assert "microdatos del INE" in texto
    assert re.search(r"Generado el \d{1,2} de [a-z]+ de \d{4}", texto)
    assert "proyecto" not in texto.lower() and "agente" not in texto.lower()
    assert ".portada" in gi.ESTILO_CSS.read_text(encoding="utf-8")


# --- rigor: bibliografía y ponderación ----------------------------------------


def test_los_autores_citables_salen_de_la_bibliografia_real():
    autores = vn.autores_de_la_bibliografia()
    for esperado in ("Cleveland", "McGill", "Tufte", "Knaflic", "Ware", "Wilke", "Healy"):
        assert esperado in autores, (esperado, autores)


def test_una_cita_con_forma_correcta_pero_fuera_de_la_bibliografia_no_alcanza():
    assert vn.tiene_cita_con_fundamento("Barras horizontales (Cleveland & McGill, 1984).")
    assert vn.tiene_cita_con_fundamento("Dumbbell (Tufte; Knaflic, storytellingwithdata.com).")
    assert not vn.tiene_cita_con_fundamento("Barras porque sí (Pérez, 2004).")
    assert not vn.tiene_cita_con_fundamento("Sin ninguna fuente.")


def test_toda_metrica_del_catalogo_cita_a_alguien_de_la_bibliografia(tmp_path):
    notebook = _notebook_real(tmp_path)
    assert vn.metricas_sin_grafica_o_cita(notebook) == []


def test_un_calculo_crudo_en_una_celda_a_mano_bloquea_antes_de_ejecutar(tmp_path):
    notebook = _notebook_real(tmp_path, metricas=[1])
    assert vn.calculos_sin_ponderar(notebook) == [], "las plantillas del catálogo no calculan nada crudo"
    notebook["cells"].append(_celda_code("tasa = hogares['pobre'].mean() * 100\nfig = viz.plot_x(tasa)\nfig.show()"))
    problemas = vn.calculos_sin_ponderar(notebook)
    assert len(problemas) == 1 and ".mean()" in problemas[0] and "pondera" in problemas[0]
    assert any(".mean()" in p for p in vn.verificar_antes_de_ejecutar(notebook))


def test_las_cifras_ejecutadas_se_mapean_a_los_indicadores_de_plausibilidad():
    from encuesta_hogares import verificacion_plausibilidad as vp
    cifras = {
        "tasas_nacionales": {"tasa_actividad": 64.5, "tasa_empleo": 59.7, "tasa_desempleo": 7.4},
        "pobreza": {"pct_pobres": 14.1, "pct_indigentes": 0.3},
        "resumen_conectividad_mdeo": {"total_hogares": 9000, "pct_con_internet": 89.2},
        "prevalencia_fies": {"moderada_o_severa": 13.0, "severa": 3.1},
        "otra_tabla": [{"x": 1}],
    }
    indicadores = vn.indicadores_para_plausibilidad(cifras)
    assert indicadores["tasa_desempleo"] == 7.4 and indicadores["pct_inseguridad_severa"] == 3.1
    assert vp.revisar(indicadores) == []
    # Un disparate real (proporción confundida con porcentaje) o una identidad rota se detectan.
    cifras["pobreza"]["pct_pobres"] = 0.14
    cifras["tasas_nacionales"]["tasa_empleo"] = 70.0
    hallazgos = vp.revisar(vn.indicadores_para_plausibilidad(cifras))
    assert any(h.indicador == "pct_pobres" for h in hallazgos)
    assert any(h.indicador == "tasa_empleo" and "actividad" in h.motivo for h in hallazgos)


def test_construir_corta_si_las_cifras_ejecutadas_no_son_plausibles(tmp_path, monkeypatch):
    ruta_cifras = tmp_path / "_cifras_x.json"
    ruta_cifras.write_text(json.dumps({"tasas_nacionales": {"tasa_actividad": 64.0, "tasa_empleo": 80.0, "tasa_desempleo": 7.0}}), encoding="utf-8")
    hallazgos = gi._revisar_plausibilidad(ruta_cifras)
    assert hallazgos and "tasa_empleo" in hallazgos[0]
    assert gi._revisar_plausibilidad(tmp_path / "no_existe.json") == []
