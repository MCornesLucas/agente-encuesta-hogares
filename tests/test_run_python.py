"""El envoltorio run_python.bat: la salida de todo lo que corre el agente va
en UTF-8, sin depender de la codificación de la consola de Windows.

Nace de una corrida real (2026-09-09): una herramienta imprimió un nombre
de columna de los datos del INE con un carácter que cp1252 no puede
representar y terminó en UnicodeEncodeError en medio del flujo. La
consola de Windows sigue en cp1252; el envoltorio fija la codificación de
salida de Python para que eso no vuelva a pasar en ninguna herramienta.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parents[1]
_BAT = _RAIZ / "run_python.bat"


def test_el_envoltorio_fija_la_salida_en_utf8():
    texto = _BAT.read_text(encoding="latin-1")
    assert 'set "PYTHONIOENCODING=utf-8"' in texto
    assert texto.index("PYTHONIOENCODING") < texto.index('"%PYEXE%" %*'), "antes de invocar a Python"


@pytest.mark.skipif(not (_RAIZ / ".claude" / "python_path.txt").exists() or shutil.which("cmd") is None,
                    reason="sin Python configurado por instalar.bat o sin cmd.exe")
def test_un_caracter_fuera_de_cp1252_se_imprime_sin_error():
    resultado = subprocess.run(
        ["cmd", "/c", str(_BAT), "-c", "print('\ufffd \u2014 ok')"],
        capture_output=True, cwd=str(_RAIZ),
    )
    assert resultado.returncode == 0, resultado.stderr.decode("utf-8", errors="replace")
    assert resultado.stdout.decode("utf-8").strip() == "\ufffd \u2014 ok"
