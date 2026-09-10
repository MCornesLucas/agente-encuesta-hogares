"""Detección automática de estadísticas de Hogares/Personas sin ponderar.

Nace de dos incidentes reales de este proyecto: primero, `pesoano`/`W_ANO`
(el factor de expansión muestral general de Hogares) no se usaba en casi
ningún lado salvo FIES/Empleo/Seguridad — se corrigió con un retrofit
grande de analysis.py. Después, al construir esta misma verificación, la
revisión encontró un segundo caso que ese retrofit no había tocado:
`compute_penetracion_por_barrio`, en preprocessing.py, seguía calculando
el % de hogares con TV cable con un `.mean()` sin ponderar — código que
alimenta directamente varias métricas del catálogo activo (Brecha
Digital). (La función hermana que tenía el mismo problema a nivel
nacional, `compute_penetracion_nacional`, se borró después junto con la
métrica del catálogo que la usaba — ver CHANGELOG.md.)

Ninguno de los dos casos lo encontró una revisión manual completa a
tiempo. Ese tipo de revisión no escala: cada función nueva agregada en
una corrida real puede repetir el mismo descuido sin que nadie la vuelva
a mirar entera.

Un tercer caso, encontrado en la misma revisión, ni siquiera vivía en una
función de cálculo: una función de `visualization.py` que se borró
después junto con su métrica del catálogo (ver CHANGELOG.md) calculaba un
`.value_counts(normalize=True)` sin ponderar directamente dentro de la
función de gráfica — nada en `analysis.py`/`preprocessing.py` lo hacía,
así que ninguna revisión que se limitara a esos dos módulos lo iba a
encontrar nunca. Por eso esta verificación también escanea
`visualization.py`.

Esta verificación automatiza la señal más barata de un descuido de
ponderación: un cálculo estadístico "crudo" (`.mean()`, `.median()`,
`.value_counts()` sobre una columna de datos, no sobre una tabla ya
agregada) en `analysis.py`, `preprocessing.py` o `visualization.py`,
fuera de los helpers ya ponderados (`pct_ponderado`, `media_ponderada_por`,
etc.). No reemplaza el criterio humano — hay usos legítimos de estos
métodos (ver ALLOWLIST) — pero convierte "nadie lo notó" en "el test
falla y alguien tiene que decidir conscientemente si es un caso legítimo
o un descuido".
"""

from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass
from types import ModuleType

METODOS_CRUDOS = {"mean", "median", "value_counts"}

# Cada función de analysis.py/preprocessing.py que llama a uno de
# METODOS_CRUDOS tiene que aparecer acá con la razón por la que NO es un
# descuido de ponderación. Si aparece una función nueva no listada, la
# verificación falla — esa es la señal de que hay que revisarla, no un
# error del checker. Agregar una entrada acá es una decisión consciente,
# no un trámite: si la razón no se sostiene, el fix es ponderar la
# estadística, no ampliar la lista.
ALLOWLIST: dict[str, str] = {
    "tasas_actividad_empleo_desempleo": (
        "mean() promedia una tasa YA ponderada (calculada mes a mes con "
        "ponderador_empleo) entre los 12 meses del año, no datos crudos — "
        "ver docstring de la función."
    ),
    "tasas_actividad_empleo_desempleo_por": (
        "mismo caso que tasas_actividad_empleo_desempleo, desagregado por grupo."
    ),
    "tasa_mensual_promedio_por": (
        "mismo patrón: mean() sobre un % ya ponderado mes a mes, no sobre datos crudos."
    ),
    "composicion_categorica_por_mes_promedio": (
        "mismo patrón: mean() sobre un % ya ponderado mes a mes, no sobre datos crudos."
    ),
    "grupos_con_muestra_chica": (
        "value_counts() es DELIBERADAMENTE sin ponderar — cuenta el tamaño de "
        "muestra real, no la población representada (ver docstring)."
    ),
    "grupos_con_pocos_casos": (
        "mismo caso: value_counts() cuenta los casos positivos reales de la "
        "muestra por grupo, que es lo que sostiene la precisión de un evento raro."
    ),
    "indice_desarrollo_territorial": (
        "mean() promedia columnas de un índice YA normalizado (0-1), no datos "
        "crudos de hogares/personas."
    ),
}


@dataclass
class UsoSinRevisar:
    modulo: str
    funcion: str
    linea: int
    metodo: str


def _arbol(modulo: ModuleType) -> ast.Module:
    return ast.parse(inspect.getsource(modulo))


def nombres_de_funciones(modulo: ModuleType) -> set[str]:
    """Nombres de todas las funciones de nivel superior definidas en `modulo`."""
    return {nodo.name for nodo in ast.walk(_arbol(modulo)) if isinstance(nodo, ast.FunctionDef)}


def _usos_en_arbol(arbol: ast.Module, nombre_modulo: str) -> list[UsoSinRevisar]:
    encontrados = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.FunctionDef) or nodo.name in ALLOWLIST:
            continue
        for sub in ast.walk(nodo):
            if isinstance(sub, ast.Attribute) and sub.attr in METODOS_CRUDOS:
                encontrados.append(UsoSinRevisar(nombre_modulo, nodo.name, sub.lineno, sub.attr))
    return encontrados


def usos_sin_revisar(modulo: ModuleType) -> list[UsoSinRevisar]:
    """Funciones de `modulo` que llaman a un método de METODOS_CRUDOS y no
    están en ALLOWLIST — ver docstring del módulo."""
    return _usos_en_arbol(_arbol(modulo), modulo.__name__)


def entradas_allowlist_obsoletas(*modulos: ModuleType) -> set[str]:
    """Entradas de ALLOWLIST que ya no corresponden a ninguna función real de
    `modulos` (typo, o la función se borró/renombró) — mantiene la lista
    honesta en vez de acumular exenciones muertas."""
    nombres_reales: set[str] = set()
    for modulo in modulos:
        nombres_reales |= nombres_de_funciones(modulo)
    return set(ALLOWLIST) - nombres_reales
