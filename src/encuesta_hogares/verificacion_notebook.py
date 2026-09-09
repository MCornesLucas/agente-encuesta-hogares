"""Verificaciones deterministas del notebook del informe, antes y después
de ejecutarlo — las mismas que hasta la v0.13.6 hacían tres hooks de Node
sobre el comando `nbconvert` y una "revisión final de coherencia" que el
modelo hacía leyendo el notebook entero (paso 7 del agente).

Por qué existe este módulo: la bitácora real mostraba que el notebook se
ejecutaba 1,68 veces por corrida en promedio (tres veces en la corrida de
42 métricas del 2026-08-17, 150 s cada una) porque la revisión venía
DESPUÉS de ejecutar y cada corrección obligaba a ejecutar de nuevo. Todo
lo que se revisaba es estructural y se puede comprobar sobre el notebook
recién construido, antes de gastar un solo segundo de kernel — así que
`generar_informe.construir` llama a `verificar_antes_de_ejecutar` y solo
ejecuta si pasa. Después de ejecutar, `verificar_despues_de_ejecutar`
mira lo único que no se puede saber antes: celdas con error y gráficas
que no produjeron imagen.

Las funciones son puras (reciben el notebook como dict, devuelven listas
de problemas legibles) y se prueban en las dos direcciones: dejan pasar
el informe real que arma `notebook_builder` y bloquean copias saboteadas.
Los hooks `.claude/hooks/gate-notebook-*.cjs` siguen existiendo para el
camino manual (`nbconvert` invocado desde un `.py` propio); este módulo
es el equivalente para el pipeline.
"""

from __future__ import annotations

import re
from typing import Iterable

# Mismos autores que reconoce gate-notebook-metrica-sin-grafica-o-cita.cjs.
AUTORES_CONOCIDOS = (
    "Cleveland", "McGill", "Tufte", "Knaflic", "Few", "Ware", "Wilke",
    "Nightingale", "Data Visualization Society", "Hofmann", "Wickham",
    "Kafadar", "Weissgerber", "storytellingwithdata",
)
_CITA_GENERICA = re.compile(r"\([A-ZÀ-Ý][\wÀ-ÿ.]+(?:\s*(?:&|y|et al\.?)\s*[A-ZÀ-Ý][\wÀ-ÿ.]+)?,?\s*\d{4}\)")
_ENCABEZADO_METRICA = re.compile(r"^#{2,4}\s*(?:M[ée]trica\s+)?(\d{1,2})[.\s—-]")
_ENCABEZADO_SECCION = re.compile(r"^##\s+(?!\d)")
_VARIABLE_SOLA = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# "TODO"/"TBD"/"XXX" solo en mayúsculas: "todo" es una palabra normal en español.
_PLACEHOLDERS = re.compile(r"(?i:\(pendiente\)|\(se completa|lorem ipsum)|\bTODO\b|\bTBD\b|\bXXX\b")
_ENCABEZADO_RESUMEN = re.compile(r"resumen anal[ií]tico", re.IGNORECASE)


def _fuente(celda: dict) -> str:
    origen = celda.get("source", "")
    return "".join(origen) if isinstance(origen, list) else (origen or "")


def _texto_outputs(celda: dict) -> str:
    texto = ""
    for salida in celda.get("outputs", []) or []:
        if "text" in salida:
            t = salida["text"]
            texto += "".join(t) if isinstance(t, list) else t
        plano = (salida.get("data") or {}).get("text/plain")
        if plano:
            texto += "".join(plano) if isinstance(plano, list) else plano
    return texto


def _tiene_imagen(celda: dict) -> bool:
    return any(
        any(clave.startswith("image/") for clave in (salida.get("data") or {}))
        for salida in celda.get("outputs", []) or []
    )


# ---------------------------------------------------------------------------
# Antes de ejecutar
# ---------------------------------------------------------------------------


def celdas_que_duplican_grafica(nb: dict) -> list[str]:
    """Celdas de código que terminan con la variable sola después de
    asignarla con `viz.plot_...` — con el renderer PNG de Plotly eso
    muestra la gráfica dos veces (gate-notebook-sin-duplicados.cjs)."""
    problemas = []
    for i, celda in enumerate(nb.get("cells", [])):
        if celda.get("cell_type") != "code":
            continue
        lineas = [linea.strip() for linea in _fuente(celda).split("\n") if linea.strip()]
        if not lineas:
            continue
        ultima = lineas[-1]
        if not _VARIABLE_SOLA.match(ultima):
            continue
        patron = re.compile(r"^" + re.escape(ultima) + r"\s*=\s*viz\.")
        if any(patron.match(linea) for linea in lineas):
            problemas.append(f"celda {i}: termina con la variable «{ultima}» sola después de asignarla con viz.plot_...")
    return problemas


def _grupos_de_metrica(nb: dict) -> list[dict]:
    grupos: list[dict] = []
    actual: dict | None = None
    for celda in nb.get("cells", []):
        if celda.get("cell_type") == "markdown":
            texto = _fuente(celda)
            primera = next((linea for linea in texto.split("\n") if linea.strip()), "")
            m = _ENCABEZADO_METRICA.match(primera)
            if m:
                if actual:
                    grupos.append(actual)
                actual = {"numero": m.group(1), "markdown": [texto], "grafica": False}
                continue
            if _ENCABEZADO_SECCION.match(primera):
                if actual:
                    grupos.append(actual)
                actual = None
                continue
            if actual:
                actual["markdown"].append(texto)
        elif celda.get("cell_type") == "code" and actual and re.search(r"viz\.plot_\w+\(", _fuente(celda)):
            actual["grafica"] = True
    if actual:
        grupos.append(actual)
    return grupos


def tiene_cita_con_fundamento(texto: str) -> bool:
    return any(autor in texto for autor in AUTORES_CONOCIDOS) or bool(_CITA_GENERICA.search(texto))


def metricas_sin_grafica_o_cita(nb: dict) -> list[str]:
    """Cada métrica (encabezado `### N.`) necesita una gráfica `viz.plot_*`
    y una cita que respalde el tipo de gráfica (docs/CONVENCIONES_DE_GRAFICAS.md).
    Si el notebook no tiene ninguna métrica reconocible, también es un
    problema: el formato de encabezados cambió y la revisión quedó ciega."""
    grupos = _grupos_de_metrica(nb)
    if not grupos:
        return ["no se reconoció ninguna métrica (encabezados «### N. …»): el formato cambió o el informe está vacío"]
    problemas = []
    for g in grupos:
        faltas = []
        if not g["grafica"]:
            faltas.append("sin ninguna gráfica (viz.plot_...)")
        if not tiene_cita_con_fundamento("\n".join(g["markdown"])):
            faltas.append("sin cita/fuente en la justificación")
        if faltas:
            problemas.append(f"métrica {g['numero']}: " + " y ".join(faltas))
    return problemas


def placeholders_en_el_texto(nb: dict) -> list[str]:
    """Texto que quedó por completar — la revisión del paso 7 lo buscaba
    a ojo en el «Resumen analítico final»; acá se busca en todo el markdown."""
    problemas = []
    for i, celda in enumerate(nb.get("cells", [])):
        if celda.get("cell_type") != "markdown":
            continue
        m = _PLACEHOLDERS.search(_fuente(celda))
        if m:
            problemas.append(f"celda {i}: texto sin completar («{m.group(0)}»)")
    return problemas


def encabezados_repetidos(nb: dict) -> list[str]:
    """El mismo encabezado de métrica dos veces (p. ej. una métrica a medida
    numerada igual que una del catálogo) desordena el informe."""
    vistos: dict[str, int] = {}
    problemas = []
    for i, celda in enumerate(nb.get("cells", [])):
        if celda.get("cell_type") != "markdown":
            continue
        primera = next((linea.strip() for linea in _fuente(celda).split("\n") if linea.strip()), "")
        if _ENCABEZADO_METRICA.match(primera):
            if primera in vistos:
                problemas.append(f"celda {i}: encabezado repetido «{primera}» (ya estaba en la celda {vistos[primera]})")
            else:
                vistos[primera] = i
    return problemas


def verificar_antes_de_ejecutar(nb: dict) -> list[str]:
    return (
        celdas_que_duplican_grafica(nb)
        + metricas_sin_grafica_o_cita(nb)
        + placeholders_en_el_texto(nb)
        + encabezados_repetidos(nb)
    )


# ---------------------------------------------------------------------------
# Después de ejecutar
# ---------------------------------------------------------------------------


def celdas_con_error(nb: dict) -> list[str]:
    problemas = []
    for i, celda in enumerate(nb.get("cells", [])):
        if celda.get("cell_type") != "code":
            continue
        for salida in celda.get("outputs", []) or []:
            if salida.get("output_type") == "error":
                problemas.append(f"celda {i}: {salida.get('ename', 'Error')}: {salida.get('evalue', '')}"[:300])
    return problemas


def graficas_faltantes(nb: dict) -> list[str]:
    """Celdas que llaman a `viz.plot_*` y no dejaron ninguna imagen en el
    output (gate-notebook-graficas-faltantes.cjs)."""
    problemas = []
    for i, celda in enumerate(nb.get("cells", [])):
        if celda.get("cell_type") != "code":
            continue
        if re.search(r"viz\.plot_\w+\(", _fuente(celda)) and not _tiene_imagen(celda):
            problemas.append(f"celda {i}: llama a viz.plot_... y no produjo ninguna imagen")
    return problemas


def verificar_despues_de_ejecutar(nb: dict) -> list[str]:
    return celdas_con_error(nb) + graficas_faltantes(nb)


# ---------------------------------------------------------------------------
# Cifras del resumen analítico
# ---------------------------------------------------------------------------

_CIFRA = re.compile(r"(\d+(?:[.,]\d+)?)\s*%|(\d+[.,]\d+)")
# "23.544" es un separador de miles uruguayo, no un decimal: se lee 23544.
_MILES = re.compile(r"^\d{1,3}(?:\.\d{3})+$")
_NUMERO = re.compile(r"\d+(?:[.,]\d+)?")


def cifras_de(texto: str) -> list[tuple[str, float, int]]:
    """Números "de estadística" de un texto: con decimales, o enteros con %
    pegado. Devuelve (texto tal cual, valor, cantidad de decimales); los
    años 1900-2100 se ignoran."""
    encontradas = []
    for m in _CIFRA.finditer(texto):
        original = m.group(1) if m.group(1) is not None else m.group(2)
        if _MILES.match(original):
            crudo, decimales = original.replace(".", ""), 0
        else:
            crudo = original.replace(",", ".")
            decimales = len(crudo.split(".")[1]) if "." in crudo else 0
        try:
            valor = float(crudo)
        except ValueError:
            continue
        if valor.is_integer() and 1900 <= valor <= 2100:
            continue
        encontradas.append((m.group(0).strip(), valor, decimales))
    return encontradas


_MILES_CUALQUIERA = re.compile(r"^\d{1,3}(?:[.,]\d{3})+$")


def numeros_de(texto: str) -> list[float]:
    """Todos los números de un texto de output. Un token como «23,544» o
    «23.544» se lee de las dos formas (23.544 y 23544): los `print(f"{n:,}")`
    del notebook usan la coma de miles del inglés y el resumen la escribe
    con punto, a la uruguaya."""
    valores = []
    for m in _NUMERO.finditer(texto):
        token = m.group(0)
        try:
            valores.append(float(token.replace(",", ".")))
        except ValueError:
            continue
        if _MILES_CUALQUIERA.match(token):
            valores.append(float(re.sub(r"[.,]", "", token)))
    return valores


def numeros_reales(nb: dict, extra: Iterable[float] = ()) -> list[float]:
    """El conjunto contra el que se valida cada cifra del resumen: todo
    número que aparezca en un output ejecutado del notebook, más los que
    aporte `extra` (las tablas de la celda de cifras, ver
    `notebook_builder.celda_cifras`)."""
    reales: list[float] = list(extra)
    for celda in nb.get("cells", []):
        if celda.get("cell_type") == "code":
            reales.extend(numeros_de(_texto_outputs(celda)))
    return reales


def _numeros_anidados(valor) -> Iterable[float]:
    if isinstance(valor, bool):
        return
    if isinstance(valor, (int, float)):
        yield float(valor)
    elif isinstance(valor, dict):
        for v in valor.values():
            yield from _numeros_anidados(v)
    elif isinstance(valor, (list, tuple)):
        for v in valor:
            yield from _numeros_anidados(v)
    elif isinstance(valor, str):
        yield from numeros_de(valor)


def numeros_de_cifras(cifras: dict) -> list[float]:
    """Todos los números del JSON que escribe la celda de cifras."""
    return list(_numeros_anidados(cifras))


def cifras_sin_respaldo(texto_resumen: str, reales: Iterable[float]) -> list[str]:
    """Cifras del resumen que no coinciden, redondeadas a sus propios
    decimales, con ningún número real (gate-resumen-cifras-inventadas.cjs)."""
    reales = list(reales)
    sospechosas = []
    for texto, valor, decimales in cifras_de(texto_resumen):
        if not any(round(real, decimales) == valor for real in reales):
            sospechosas.append(texto)
    return sorted(set(sospechosas))


def texto_del_resumen(nb: dict) -> str:
    """El markdown desde el encabezado «Resumen analítico» hasta el final."""
    dentro = False
    partes = []
    for celda in nb.get("cells", []):
        if celda.get("cell_type") != "markdown":
            continue
        texto = _fuente(celda)
        if not dentro and _ENCABEZADO_RESUMEN.search(texto):
            dentro = True
            continue
        if dentro:
            partes.append(texto)
    return "\n".join(partes)
