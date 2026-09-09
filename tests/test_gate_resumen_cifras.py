"""El "Resumen analítico final" no puede citar cifras que el notebook no
calculó — se prueba invocando el hook de verdad con Node.

Nace del único lugar del informe donde el modelo TRANSCRIBE números a
prosa. Todo el resto calcula con pandas y muestra el resultado; el resumen
final es texto escrito citando porcentajes. Aunque los saque con Python
(que es lo que mandan sus instrucciones), entre leerlos y escribirlos hay
un paso a mano sin ningún control — y es la parte que más gente lee.

El equilibrio que se busca: atrapar un número inventado o mal transcripto,
**sin** bloquear un redondeo legítimo ("cerca del 40%" cuando el dato es
40,13%), que es buena redacción y no un error. Un falso positivo acá sería
peor que el problema: dejaría el informe sin poder generarse.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "_lib_check_resumen_cifras_inventadas.cjs"
_NODE_DISPONIBLE = subprocess.run(["node", "--version"], capture_output=True).returncode == 0


def _notebook(resumen: str, salida: str = "Pobreza (ponderada): 14.14%\nDesempleo: 7.45\n") -> dict:
    return {
        "cells": [
            {
                "cell_type": "code",
                "source": ["print('algo')"],
                "outputs": [{"output_type": "stream", "name": "stdout", "text": [salida]}],
            },
            {"cell_type": "markdown", "source": ["## Resumen analítico final\n"]},
            {"cell_type": "markdown", "source": [resumen]},
        ]
    }


def _correr(tmp_path, resumen: str, salida: str | None = None):
    ruta = tmp_path / "informe.ipynb"
    contenido = _notebook(resumen) if salida is None else _notebook(resumen, salida)
    ruta.write_text(json.dumps(contenido), encoding="utf-8")
    script = tmp_path / "ejecutar.py"
    script.write_text(
        f'import subprocess\nsubprocess.run(["jupyter","nbconvert","--execute","{ruta.name}"])\n',
        encoding="utf-8",
    )
    entrada = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": f'run_python.bat "{script.name}"'},
    })
    resultado = subprocess.run(
        ["node", str(_HOOK)], input=entrada, capture_output=True, text=True, cwd=str(tmp_path),
        env={**os.environ, "ENCUESTA_HOGARES_BITACORA": str(tmp_path / "b.jsonl")},
    )
    salida_hook = resultado.stdout.strip()
    return json.loads(salida_hook) if salida_hook else None


@pytest.mark.skipif(not _NODE_DISPONIBLE, reason="node no está disponible en esta máquina")
class TestResumenCifras:
    def test_bloquea_una_cifra_que_el_notebook_nunca_calculo(self, tmp_path):
        r = _correr(tmp_path, "La pobreza alcanzó al 31,7% de los hogares.")
        assert r is not None, "una cifra inventada tiene que bloquear"
        assert r["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "31,7" in r["hookSpecificOutput"]["permissionDecisionReason"]

    def test_acepta_la_cifra_exacta(self, tmp_path):
        assert _correr(tmp_path, "La pobreza alcanzó al 14.14% de los hogares.") is None

    def test_acepta_la_misma_cifra_escrita_con_coma(self, tmp_path):
        # El informe está en español: 14,14% y 14.14% son el mismo número.
        assert _correr(tmp_path, "La pobreza alcanzó al 14,14% de los hogares.") is None

    def test_acepta_un_redondeo_legitimo(self, tmp_path):
        # "cerca del 14,1%" cuando el dato real es 14,14% es buena redacción.
        assert _correr(tmp_path, "La pobreza rondó el 14,1% de los hogares.") is None

    def test_acepta_un_redondeo_a_entero(self, tmp_path):
        assert _correr(tmp_path, "La pobreza afectó a cerca del 14% de los hogares.") is None

    def test_no_confunde_un_año_con_una_estadistica(self, tmp_path):
        assert _correr(tmp_path, "En 2025 la pobreza fue del 14,14%.") is None

    def test_no_mira_el_texto_de_antes_del_resumen(self, tmp_path):
        """Las métricas del cuerpo del informe citan sus propias cifras en
        la pregunta guía; el hook solo controla el resumen final."""
        ruta = tmp_path / "informe.ipynb"
        ruta.write_text(json.dumps({
            "cells": [
                {"cell_type": "markdown", "source": ["### 1. Algo con 99,9% escrito antes\n"]},
                {
                    "cell_type": "code",
                    "source": ["print('x')"],
                    "outputs": [{"output_type": "stream", "name": "stdout", "text": ["14.14\n"]}],
                },
                {"cell_type": "markdown", "source": ["## Resumen analítico final\n"]},
                {"cell_type": "markdown", "source": ["Cerró en 14,14%.\n"]},
            ]
        }), encoding="utf-8")
        script = tmp_path / "ejecutar.py"
        script.write_text(
            f'import subprocess\nsubprocess.run(["jupyter","nbconvert","--execute","{ruta.name}"])\n',
            encoding="utf-8",
        )
        entrada = json.dumps({"tool_name": "Bash", "tool_input": {"command": f'run_python.bat "{script.name}"'}})
        r = subprocess.run(
            ["node", str(_HOOK)], input=entrada, capture_output=True, text=True, cwd=str(tmp_path),
            env={**os.environ, "ENCUESTA_HOGARES_BITACORA": str(tmp_path / "b.jsonl")},
        )
        assert r.stdout.strip() == "", "el 99,9% está antes del resumen, no le corresponde a este hook"

    def test_no_bloquea_un_notebook_sin_ejecutar(self, tmp_path):
        """Sin outputs todavía no hay con qué comparar — bloquear ahí sería
        un falso positivo que trabaría el flujo."""
        ruta = tmp_path / "informe.ipynb"
        ruta.write_text(json.dumps({
            "cells": [
                {"cell_type": "code", "source": ["print('x')"], "outputs": []},
                {"cell_type": "markdown", "source": ["## Resumen analítico final\n"]},
                {"cell_type": "markdown", "source": ["Cerró en 31,7%.\n"]},
            ]
        }), encoding="utf-8")
        script = tmp_path / "ejecutar.py"
        script.write_text(
            f'import subprocess\nsubprocess.run(["jupyter","nbconvert","--execute","{ruta.name}"])\n',
            encoding="utf-8",
        )
        entrada = json.dumps({"tool_name": "Bash", "tool_input": {"command": f'run_python.bat "{script.name}"'}})
        r = subprocess.run(
            ["node", str(_HOOK)], input=entrada, capture_output=True, text=True, cwd=str(tmp_path),
            env={**os.environ, "ENCUESTA_HOGARES_BITACORA": str(tmp_path / "b.jsonl")},
        )
        assert r.stdout.strip() == ""
