"""Prueba los tres hooks que gatean sobre `jupyter nbconvert --execute`
(_lib_check_notebook_sin_duplicados.cjs, _lib_check_notebook_metrica_sin_grafica_o_cita.cjs,
gate-notebook-graficas-faltantes.cjs) invocándolos de verdad con Node (pipe
de stdin, igual que lo hace Claude Code) — no una reimplementación en
Python de su lógica. Mismo enfoque que test_gate_primer_paso.py y
test_gate_no_git_indirecto.py.

Nace de un bug real encontrado replicando el patrón que documenta
docs/FLUJO_DE_TRABAJO.md (pasos 5 y 8): `nbconvert --execute` nunca se
invoca suelto por Bash, siempre envuelto en un archivo `.py` con
`bitacora.medir_comando(...)` y corrido con `run_python.bat archivo.py`
(el mismo patrón "Write + run_python.bat" cuyo bug ya arregló
gate-primer-paso.cjs). Los tres hooks buscaban "nbconvert"/"--execute" y
la ruta del notebook solo en el texto CRUDO del comando Bash — con el
patrón real, ese texto es apenas `run_python.bat archivo.py`, así que
ninguno de los tres se disparaba nunca. La detección ahora vive en
.claude/hooks/_lib_notebook_ejecutado.cjs, compartida por los tres, que
también busca dentro de cualquier archivo `.py` que el comando referencie.
"""

import json
import subprocess
from pathlib import Path

import pytest

_HOOKS = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
_NODE_DISPONIBLE = subprocess.run(["node", "--version"], capture_output=True).returncode == 0

_NOTEBOOK_CON_DUPLICADO = {
    "cells": [
        {"cell_type": "code", "source": ["fig = viz.plot_bar(df)\n", "fig"], "outputs": [], "metadata": {}},
    ],
    "metadata": {},
    "nbformat": 4,
    "nbformat_minor": 5,
}

_NOTEBOOK_LIMPIO = {
    "cells": [
        {
            "cell_type": "code",
            "source": ["fig2 = viz.plot_bar(df)\n", "fig2.show()"],
            "outputs": [{"output_type": "display_data", "data": {"text/plain": ["<img>"]}, "metadata": {}}],
            "metadata": {},
        },
    ],
    "metadata": {},
    "nbformat": 4,
    "nbformat_minor": 5,
}

_NOTEBOOK_SIN_OUTPUT = {
    "cells": [
        {"cell_type": "code", "source": ["fig2 = viz.plot_bar(df)\n", "fig2.show()"], "outputs": [], "metadata": {}},
    ],
    "metadata": {},
    "nbformat": 4,
    "nbformat_minor": 5,
}


def _correr_hook(hook_nombre: str, comando: str, cwd: Path) -> dict | None:
    """Corre el hook de verdad con Node, con cwd = carpeta del notebook
    (así resuelve igual que en una sesión real, donde el cwd del proceso
    del hook es la raíz del proyecto y las rutas del comando son relativas
    a ella).

    `encoding="utf-8"` explícito: Node escribe UTF-8, pero en Windows
    `text=True` decodifica con la codepage local (cp1252) y los mensajes
    del hook vuelven con los acentos rotos — un test que compare texto con
    tildes falla sin que el hook tenga nada malo."""
    entrada = json.dumps({"tool_name": "Bash", "tool_input": {"command": comando}})
    resultado = subprocess.run(
        ["node", str(_HOOKS / hook_nombre)], input=entrada, capture_output=True,
        text=True, encoding="utf-8", cwd=str(cwd),
    )
    salida = resultado.stdout.strip()
    return json.loads(salida) if salida else None


def _escribir_notebook(tmp_path: Path, nombre: str, contenido: dict) -> None:
    (tmp_path / nombre).write_text(json.dumps(contenido), encoding="utf-8")


def _escribir_script_ejecutor(tmp_path: Path, nombre_script: str, nombre_notebook: str) -> str:
    """Reproduce el patrón real de FLUJO_DE_TRABAJO.md paso 5: nbconvert
    envuelto en bitacora.medir_comando(), en un archivo .py, nunca suelto
    por Bash. Devuelve el comando Bash tal como lo correría la sesión real
    (`run_python.bat archivo.py`)."""
    script = tmp_path / nombre_script
    script.write_text(
        "import sys\n"
        "from encuesta_hogares import bitacora\n"
        "bitacora.medir_comando('ejecucion_notebook', [\n"
        "    sys.executable, '-m', 'jupyter', 'nbconvert',\n"
        "    '--to', 'notebook', '--execute', '--inplace',\n"
        f"    {nombre_notebook!r},\n"
        "])\n",
        encoding="utf-8",
    )
    return f'run_python.bat "{nombre_script}"'


@pytest.mark.skipif(not _NODE_DISPONIBLE, reason="node no está disponible en esta máquina")
class TestDeteccionDeNbconvertOcultoEnPy:
    """El bug: los tres hooks ignoraban nbconvert cuando vivía dentro de un
    .py referenciado por el comando Bash, en vez de en el texto del comando."""

    def test_sin_duplicados_bloquea_via_write_y_run_python_bat(self, tmp_path):
        _escribir_notebook(tmp_path, "nb.ipynb", _NOTEBOOK_CON_DUPLICADO)
        comando = _escribir_script_ejecutor(tmp_path, "ejecutar.py", "nb.ipynb")
        resultado = _correr_hook("_lib_check_notebook_sin_duplicados.cjs", comando, tmp_path)
        assert resultado is not None
        assert resultado["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_sin_duplicados_permite_notebook_limpio_via_write_y_run_python_bat(self, tmp_path):
        _escribir_notebook(tmp_path, "nb.ipynb", _NOTEBOOK_LIMPIO)
        comando = _escribir_script_ejecutor(tmp_path, "ejecutar.py", "nb.ipynb")
        assert _correr_hook("_lib_check_notebook_sin_duplicados.cjs", comando, tmp_path) is None

    def test_graficas_faltantes_bloquea_celda_sin_output_via_write_y_run_python_bat(self, tmp_path):
        _escribir_notebook(tmp_path, "nb.ipynb", _NOTEBOOK_SIN_OUTPUT)
        comando = _escribir_script_ejecutor(tmp_path, "ejecutar.py", "nb.ipynb")
        resultado = _correr_hook("gate-notebook-graficas-faltantes.cjs", comando, tmp_path)
        assert resultado is not None
        assert resultado["decision"] == "block"

    def test_graficas_faltantes_permite_notebook_con_output_via_write_y_run_python_bat(self, tmp_path):
        _escribir_notebook(tmp_path, "nb.ipynb", _NOTEBOOK_LIMPIO)
        comando = _escribir_script_ejecutor(tmp_path, "ejecutar.py", "nb.ipynb")
        assert _correr_hook("gate-notebook-graficas-faltantes.cjs", comando, tmp_path) is None

    def test_metrica_sin_grafica_o_cita_no_revienta_via_write_y_run_python_bat(self, tmp_path):
        # Este notebook de prueba no tiene celdas "#### Métrica N", así que
        # no hay ninguna métrica que revisar - lo que importa acá es que
        # detecte el nbconvert oculto en el .py y no reviente ni bloquee a
        # ciegas por falta de encabezados de métrica.
        _escribir_notebook(tmp_path, "nb.ipynb", _NOTEBOOK_LIMPIO)
        comando = _escribir_script_ejecutor(tmp_path, "ejecutar.py", "nb.ipynb")
        assert _correr_hook("_lib_check_notebook_metrica_sin_grafica_o_cita.cjs", comando, tmp_path) is None

    def test_ningun_hook_se_dispara_sin_mencion_a_nbconvert(self, tmp_path):
        for hook in (
            "_lib_check_notebook_sin_duplicados.cjs",
            "_lib_check_notebook_metrica_sin_grafica_o_cita.cjs",
            "gate-notebook-graficas-faltantes.cjs",
        ):
            assert _correr_hook(hook, "run_python.bat tools/validar_con_datos_reales.py", tmp_path) is None


@pytest.mark.skipif(not _NODE_DISPONIBLE, reason="node no está disponible en esta máquina")
class TestElHookReconoceLosEncabezadosQueEmiteNotebookBuilder:
    """El hook buscaba encabezados "#### Métrica N", que es como se escribían
    las celdas a mano. Desde que las arma `notebook_builder` salen como
    "### N. Título", así que el hook encontraba cero métricas y dejaba pasar
    cualquier notebook: verde por no mirar nada.

    Estos dos tests son el par que faltaba — que bloquee cuando tiene que
    bloquear, sobre el formato real."""

    def _celda_md(self, texto):
        return {"cell_type": "markdown", "source": texto, "metadata": {}}

    def _celda_codigo(self, texto):
        return {
            "cell_type": "code", "source": texto, "metadata": {},
            "execution_count": 1, "outputs": [],
        }

    def _notebook(self, celdas):
        return {"cells": celdas, "metadata": {}, "nbformat": 4, "nbformat_minor": 5}

    def test_bloquea_una_metrica_sin_cita_con_el_encabezado_del_builder(self, tmp_path):
        _escribir_notebook(tmp_path, "nb.ipynb", self._notebook([
            self._celda_md("### 8. Jefatura de hogar femenina"),
            self._celda_codigo("viz.plot_barras(datos)"),
            self._celda_md("*Por qué esta gráfica: porque se ve lindo.*"),
        ]))
        comando = _escribir_script_ejecutor(tmp_path, "ejecutar.py", "nb.ipynb")
        resultado = _correr_hook("_lib_check_notebook_metrica_sin_grafica_o_cita.cjs", comando, tmp_path)
        assert resultado is not None
        assert resultado["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "Métrica 8" in resultado["hookSpecificOutput"]["permissionDecisionReason"]

    def test_permite_una_metrica_con_grafica_y_cita_despues_de_la_grafica(self, tmp_path):
        # La justificación va DESPUÉS del código (v0.13.0): el hook la tiene
        # que seguir encontrando ahí.
        _escribir_notebook(tmp_path, "nb.ipynb", self._notebook([
            self._celda_md("### 8. Jefatura de hogar femenina"),
            self._celda_codigo("viz.plot_barras(datos)"),
            self._celda_md("*Por qué esta gráfica: comparar longitudes es más preciso "
                           "que comparar ángulos (Cleveland & McGill, 1984).*"),
        ]))
        comando = _escribir_script_ejecutor(tmp_path, "ejecutar.py", "nb.ipynb")
        assert _correr_hook("_lib_check_notebook_metrica_sin_grafica_o_cita.cjs", comando, tmp_path) is None

    def test_la_cita_del_tema_siguiente_no_tapa_una_metrica_sin_cita(self, tmp_path):
        # Sin cortar en el "## " del tema siguiente, la cita de la métrica 9
        # contaba como si fuera de la 8 y la dejaba pasar.
        _escribir_notebook(tmp_path, "nb.ipynb", self._notebook([
            self._celda_md("### 8. Jefatura de hogar femenina"),
            self._celda_codigo("viz.plot_barras(datos)"),
            self._celda_md("## Territorio"),
            self._celda_md("### 13. Perfil territorial"),
            self._celda_codigo("viz.plot_barras(otros)"),
            self._celda_md("*Por qué esta gráfica: (Cleveland & McGill, 1984).*"),
        ]))
        comando = _escribir_script_ejecutor(tmp_path, "ejecutar.py", "nb.ipynb")
        resultado = _correr_hook("_lib_check_notebook_metrica_sin_grafica_o_cita.cjs", comando, tmp_path)
        assert resultado is not None
        motivo = resultado["hookSpecificOutput"]["permissionDecisionReason"]
        assert "Métrica 8" in motivo and "Métrica 13" not in motivo

    def test_el_catalogo_entero_pasa_el_hook(self, tmp_path):
        """Las dos puntas atadas: el hook de Node corriendo sobre el notebook
        que arma `notebook_builder` con las 42 métricas.

        Es el test que faltaba. El hook y el generador vivían cada uno con
        su propia idea del formato y de qué autores cuentan como cita, y
        nada los comparaba: el hook pasaba en verde por no reconocer ningún
        encabezado, y dos familias de gráfica quedaron sin cita. Si alguien
        agrega una familia nueva sin fuente, o cambia el encabezado que
        emite el generador, esto se pone rojo acá y no en producción.
        """
        from encuesta_hogares import notebook_builder as nb
        from encuesta_hogares import verificacion_catalogo as vc

        celdas = nb.construir_celdas_notebook(
            anio_base=2025, metricas=sorted(vc.MANIFEST),
            incluir_brecha_digital=True, incluir_fies=True,
            incluir_empleo=True, incluir_seguridad=True,
        )
        nb.escribir_notebook(celdas, tmp_path / "nb.ipynb")
        comando = _escribir_script_ejecutor(tmp_path, "ejecutar.py", "nb.ipynb")
        resultado = _correr_hook("_lib_check_notebook_metrica_sin_grafica_o_cita.cjs", comando, tmp_path)
        assert resultado is None, resultado


@pytest.mark.skipif(not _NODE_DISPONIBLE, reason="node no está disponible en esta máquina")
class TestGateNotebookUnificado:
    """`gate-notebook.cjs` es el único hook de notebook registrado en
    settings.json: corre las tres verificaciones leyendo el .ipynb una
    sola vez (antes eran tres procesos por cada llamada Bash). Se prueba
    contra el notebook real que arma `notebook_builder` y contra copias
    saboteadas — nunca contra un dict de una celda solamente."""

    def _notebook_real(self, tmp_path):
        from encuesta_hogares import notebook_builder as nb
        from encuesta_hogares import verificacion_catalogo as vc

        celdas = nb.construir_celdas_notebook(
            anio_base=2025, metricas=sorted(vc.MANIFEST),
            incluir_brecha_digital=True, incluir_fies=True, incluir_empleo=True, incluir_seguridad=True,
        )
        nb.escribir_notebook(celdas, tmp_path / "nb.ipynb")
        return json.loads((tmp_path / "nb.ipynb").read_text(encoding="utf-8"))

    def test_deja_pasar_el_informe_real_completo(self, tmp_path):
        self._notebook_real(tmp_path)
        comando = _escribir_script_ejecutor(tmp_path, "ejecutar.py", "nb.ipynb")
        assert _correr_hook("gate-notebook.cjs", comando, tmp_path) is None

    def test_bloquea_el_informe_real_con_una_grafica_duplicada_y_una_metrica_sin_cita(self, tmp_path):
        notebook = self._notebook_real(tmp_path)
        # Sabotaje 1: la primera gráfica termina con la variable suelta.
        celda = next(c for c in notebook["cells"] if c["cell_type"] == "code" and "viz.plot_" in "".join(c["source"]))
        celda["source"] = "".join(celda["source"]).replace("fig.show()", "fig")
        # Sabotaje 2: la métrica 8 pierde su justificación con la cita.
        i8 = next(i for i, c in enumerate(notebook["cells"]) if c["cell_type"] == "markdown"
                  and "".join(c["source"]).startswith("### 8."))
        for c in notebook["cells"][i8 + 1:]:
            if c["cell_type"] == "markdown":
                if "".join(c["source"]).startswith("### "):
                    break
                c["source"] = "Sin referencia."
        _escribir_notebook(tmp_path, "nb.ipynb", notebook)
        comando = _escribir_script_ejecutor(tmp_path, "ejecutar.py", "nb.ipynb")
        resultado = _correr_hook("gate-notebook.cjs", comando, tmp_path)
        razon = resultado["hookSpecificOutput"]["permissionDecisionReason"]
        assert resultado["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "duplicar su gráfica" in razon and "Métrica 8" in razon

    def test_ignora_comandos_que_no_ejecutan_un_notebook(self, tmp_path):
        assert _correr_hook("gate-notebook.cjs", "run_python.bat -m encuesta_hogares.generar_informe construir --anio 2025 --metricas 1", tmp_path) is None
