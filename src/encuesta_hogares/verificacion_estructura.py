"""Comparación de la estructura de un año de datos contra lo que config.py espera.

Nace del incidente real del cambio de formato entre 2019 (.sav por módulo)
y 2024 (CSV combinado): ese cambio se descubrió en vivo, a los tumbos,
durante una sesión de más de media hora, porque nada comparaba
automáticamente las columnas reales del archivo nuevo contra lo que el
resto del código asumía que existía. Esta verificación no reemplaza la
revisión humana contra el diccionario oficial del INE (el significado de
una columna puede cambiar aunque el nombre no cambie), pero sí adelanta
en segundos la señal más barata y más costosa de perderse: "esta columna
que el código necesita ya no está en el archivo".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import config


@dataclass
class ResultadoComparacion:
    nombre: str
    archivo: Path
    columnas_esperadas: int
    faltantes: list[str] = field(default_factory=list)
    no_mapeadas: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.faltantes


def comparar_columnas(esperadas: dict[str, str], presentes: set[str]) -> tuple[list[str], list[str]]:
    """Compara las columnas que `config.py` espera (`esperadas`, un dict
    columna_origen -> nombre_legible) contra las que de verdad están en el
    archivo (`presentes`).

    Devuelve (faltantes, no_mapeadas):
    - faltantes: columnas que el código necesita y no están - esto rompe
      algo, es la señal que importa.
    - no_mapeadas: columnas del archivo que config.py todavía no usa - no
      es un error, es solo informativo (puede ser una variable nueva que
      vale la pena incorporar más adelante).
    """
    faltantes = sorted(c for c in esperadas if c not in presentes)
    no_mapeadas = sorted(presentes - set(esperadas))
    return faltantes, no_mapeadas


def columnas_csv(path: Path) -> set[str]:
    return set(pd.read_csv(path, nrows=0, encoding="latin1").columns)


def _sin_equivalente_metodologico(faltantes: list[str], presentes: set[str]) -> list[str]:
    """Saca de `faltantes` las columnas "nuevas" (canasta 2017) que en
    realidad no faltan - el año trae la variante "vieja" (canasta 2006)
    equivalente, y `data_loader.load_hogares_personas_csv` ya sabe usarla
    (ver `config.PREFERENCIA_METODOLOGIA_HOGARES`).

    Nace de un falso positivo real: 2023 reporta pobre17/indig17/YDA_SVL
    como columnas faltantes, pero trae pobre06/indig06/YSVL (mismo dato,
    metodología anterior) - el cargador real ya las usa sin problema, así
    que no es una alerta real, y como tal no debería aparecer junto a las
    que sí lo son (ej. el módulo entero de condiciones de vivienda
    ausente ese año).
    """
    equivalencia_inversa = {nueva: vieja for vieja, nueva in config.PREFERENCIA_METODOLOGIA_HOGARES.items()}
    return [
        c for c in faltantes if not (c in equivalencia_inversa and equivalencia_inversa[c] in presentes)
    ]


def columnas_sav(path: Path) -> set[str]:
    import pyreadstat

    _, meta = pyreadstat.read_sav(str(path), metadataonly=True)
    return set(meta.column_names)


def verificar_hogares_personas(anio: int | str) -> list[ResultadoComparacion]:
    """A diferencia de FIES/Empleo/Victimización (legítimamente opcionales,
    ver `verificar_anio`), Hogares/Personas es la base de todo el análisis
    estándar - un año sin esto no tiene nada que analizar. Por eso, si no
    se encuentra ni el CSV combinado ni los .sav, esta función devuelve un
    resultado explícito marcado como error en vez de una lista vacía que
    se pierde en silencio junto a las categorías que sí son opcionales.

    Nace de un caso real: el CSV combinado de 2023 vino con el nombre
    `ECH_implantacion_2023.csv` (orden de palabras invertido respecto al
    patrón que reconocía `config.hogares_csv_file`), así que esta función
    no encontraba nada para ese año - y como devolvía `[]`, el chequeo de
    estructura completo (`verificar_anio`) pasaba en silencio sin ninguna
    fila de Hogares, dando la falsa impresión de que no había nada que
    reportar en vez de "no se encontró el archivo".
    """
    carpeta = config.DATA_DIR / str(anio)
    csv_path = config.hogares_csv_file(anio)
    if csv_path.exists():
        presentes = columnas_csv(csv_path)
        faltantes, no_mapeadas = comparar_columnas(config.HOGARES_COLUMNS_CSV, presentes)
        faltantes = _sin_equivalente_metodologico(faltantes, presentes)
        resultados = [
            ResultadoComparacion(
                "Hogares (CSV combinado)", csv_path, len(config.HOGARES_COLUMNS_CSV), faltantes, no_mapeadas
            )
        ]
        faltantes_p, no_mapeadas_p = comparar_columnas(config.PERSONAS_COLUMNS_CSV, presentes)
        resultados.append(
            ResultadoComparacion(
                "Personas (dentro del CSV combinado)",
                csv_path,
                len(config.PERSONAS_COLUMNS_CSV),
                faltantes_p,
                no_mapeadas_p,
            )
        )
        return resultados

    resultados = []
    h_candidatos = sorted(carpeta.glob("H_*.sav"))
    if h_candidatos:
        presentes_h = columnas_sav(h_candidatos[0])
        faltantes, no_mapeadas = comparar_columnas(config.HOGARES_COLUMNS, presentes_h)
        resultados.append(
            ResultadoComparacion("Hogares (.sav)", h_candidatos[0], len(config.HOGARES_COLUMNS), faltantes, no_mapeadas)
        )
    p_candidatos = sorted(carpeta.glob("P_*.sav"))
    if p_candidatos:
        presentes_p = columnas_sav(p_candidatos[0])
        faltantes, no_mapeadas = comparar_columnas(config.PERSONAS_COLUMNS, presentes_p)
        resultados.append(
            ResultadoComparacion("Personas (.sav)", p_candidatos[0], len(config.PERSONAS_COLUMNS), faltantes, no_mapeadas)
        )

    if not resultados:
        resultados.append(
            ResultadoComparacion(
                "Hogares/Personas",
                carpeta,
                0,
                faltantes=[
                    "no se encontró ningún archivo - ni CSV combinado "
                    f"({config.hogares_csv_file(anio).name}) ni H_*.sav/P_*.sav en {carpeta}"
                ],
            )
        )
    return resultados


def verificar_fies(anio: int | str) -> ResultadoComparacion | None:
    path = config.fies_file(anio)
    if not path.exists():
        return None
    presentes = columnas_csv(path)
    faltantes, no_mapeadas = comparar_columnas(config.FIES_COLUMNS, presentes)
    return ResultadoComparacion("FIES (seguridad alimentaria)", path, len(config.FIES_COLUMNS), faltantes, no_mapeadas)


def verificar_empleo(anio: int | str) -> list[ResultadoComparacion]:
    resultados: list[ResultadoComparacion] = []
    columnas_por_mes: dict[str, set[str]] = {}
    for path in config.empleo_files(anio):
        if not path.exists():
            continue
        presentes = columnas_csv(path)
        columnas_por_mes[path.name] = presentes
        faltantes, no_mapeadas = comparar_columnas(config.EMPLEO_COLUMNS, presentes)
        resultados.append(
            ResultadoComparacion(f"Empleo ({path.name})", path, len(config.EMPLEO_COLUMNS), faltantes, no_mapeadas)
        )

    # El panel mensual debería tener la misma estructura los 12 meses - si un
    # mes difiere de los demás, promediar el año mezclaría cosas distintas
    # sin que nadie lo note (ver la regla de promediar mes a mes en
    # .claude/instrucciones/encuesta-hogares.md).
    if len(columnas_por_mes) > 1:
        primer_nombre, primeras_cols = next(iter(columnas_por_mes.items()))
        for nombre, cols in columnas_por_mes.items():
            if cols != primeras_cols:
                diferencia = sorted(primeras_cols.symmetric_difference(cols))
                resultados.append(
                    ResultadoComparacion(
                        f"Consistencia mensual: {nombre} difiere de {primer_nombre}",
                        config.DATA_DIR / str(anio) / nombre,
                        0,
                        diferencia,
                        [],
                    )
                )
    return resultados


def verificar_victimizacion(anio: int | str) -> ResultadoComparacion | None:
    path = config.victimizacion_file(anio)
    if not path.exists():
        return None
    presentes = columnas_csv(path)
    faltantes, no_mapeadas = comparar_columnas(config.VICTIMIZACION_COLUMNS, presentes)
    return ResultadoComparacion(
        "Seguridad y Victimización", path, len(config.VICTIMIZACION_COLUMNS), faltantes, no_mapeadas
    )


def verificar_anio(anio: int | str) -> list[ResultadoComparacion]:
    """Punto de entrada único: corre todas las verificaciones disponibles
    para un año (solo las de los archivos que de verdad existen en
    `data/{año}/`) y devuelve la lista completa de resultados."""
    resultados = list(verificar_hogares_personas(anio))
    fies = verificar_fies(anio)
    if fies is not None:
        resultados.append(fies)
    resultados.extend(verificar_empleo(anio))
    victimizacion = verificar_victimizacion(anio)
    if victimizacion is not None:
        resultados.append(victimizacion)
    return resultados
