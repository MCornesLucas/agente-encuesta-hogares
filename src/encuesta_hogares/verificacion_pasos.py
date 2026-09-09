"""Detecta referencias a "Paso N" en los docstrings de `formularios.py`
que ya no coinciden con ningún paso real de `.claude/instrucciones/encuesta-hogares.md`.

Nace de una evaluación de calidad real de este proyecto: se encontraron
dos docstrings desactualizados — `plantilla_datos` decía "Pasos 2+3"
cuando el paso 3 (validación) no usa ese formulario, y `plantilla_revision`
decía "Paso 7" cuando en realidad corresponde al paso 6 (el paso 7 real,
"Revisión final de coherencia", no muestra ningún formulario). Nadie lo
notó porque ni la suite de tests ni una corrida real lo hubieran
detectado — el número solo se lee, nunca se ejecuta. Este chequeo lo
convierte en una comparación de texto automática.
"""

from __future__ import annotations

import re
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[2]
# Las funciones plantilla_* viven en plantillas.py desde la v0.13.2 (antes
# estaban en formularios.py, que las reexporta) — este chequeo escanea el
# archivo donde están los `def` de verdad.
_FORMULARIOS = _RAIZ / "src" / "encuesta_hogares" / "plantillas.py"
_AGENTE = _RAIZ / ".claude" / "instrucciones" / "encuesta-hogares.md"


def pasos_reales_del_agente() -> set[str]:
    """Números de paso ("1", "3.5", "6.5", ...) que existen de verdad
    como encabezado `### N.` en las instrucciones del agente."""
    if not _AGENTE.exists():
        return set()
    texto = _AGENTE.read_text(encoding="utf-8")
    return set(re.findall(r"(?m)^### (\d+(?:\.\d+)?)\.", texto))


def referencias_a_pasos_en_formularios() -> dict[str, str]:
    """{nombre de función: número de paso mencionado} para cada
    `def plantilla_*` de `formularios.py` cuyo docstring empieza citando
    un paso ("Paso N" o "Pasos N")."""
    if not _FORMULARIOS.exists():
        return {}
    texto = _FORMULARIOS.read_text(encoding="utf-8")
    referencias = {}
    for match in re.finditer(
        r'def (plantilla_\w+)\([^)]*\)[^:]*:\s*\n\s*"""Pasos? (\d+(?:\.\d+)?)', texto
    ):
        referencias[match.group(1)] = match.group(2)
    return referencias


def referencias_a_pasos_inexistentes() -> dict[str, str]:
    """De `referencias_a_pasos_en_formularios()`, las que mencionan un
    número de paso que no existe (ya no, o nunca existió) en
    `.claude/instrucciones/encuesta-hogares.md` — la señal concreta de un
    docstring que quedó desactualizado."""
    reales = pasos_reales_del_agente()
    return {
        funcion: paso
        for funcion, paso in referencias_a_pasos_en_formularios().items()
        if paso not in reales
    }
