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

import ast
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from . import verificacion_ponderacion

_BIBLIOGRAFIA = Path(__file__).resolve().parents[2] / "docs" / "BIBLIOGRAFIA.md"

# Nombres de organismos o sitios que la bibliografía cita sin apellido.
_ORGANISMOS_CITABLES = ("Data Visualization Society", "storytellingwithdata")


@lru_cache(maxsize=1)
def autores_de_la_bibliografia() -> tuple[str, ...]:
    """Apellidos y organismos citables según `docs/BIBLIOGRAFIA.md`: el
    primer apellido de cada viñeta más los coautores ("& McGill", "y
    Wickham"). Una justificación solo cuenta como fundamentada si cita a
    alguien que está ahí — la bibliografía es la fuente de verdad, no una
    lista escrita aparte en el código (regla del dueño: toda métrica se
    justifica con la bibliografía del proyecto)."""
    if not _BIBLIOGRAFIA.exists():
        return _ORGANISMOS_CITABLES
    texto = _BIBLIOGRAFIA.read_text(encoding="utf-8")
    autores: list[str] = []
    for viñeta in re.findall(r"^- (.+)$", texto, flags=re.MULTILINE):
        cabeza = viñeta.split("(")[0]  # hasta el año o el paréntesis
        # Apellidos con mayúscula interna (McGill) y compuestos (Rodríguez-Miranda) incluidos.
        autores += re.findall(r"(?:^|[&y,;]\s+)([A-ZÀ-Ý][A-Za-zà-ÿ]+(?:-[A-ZÀ-Ý][A-Za-zà-ÿ]+)?)(?=,|\s+[A-Z]\.|\s*$|\s+&|\s+y\s)", cabeza.strip())
    for organismo in _ORGANISMOS_CITABLES:
        if organismo.lower() in texto.lower():
            autores.append(organismo)
    return tuple(dict.fromkeys(a for a in autores if len(a) > 2))


_CITA_GENERICA = re.compile(r"\(([A-ZÀ-Ý][\wÀ-ÿ.]+)(?:\s*(?:&|y|et al\.?)\s*[A-ZÀ-Ý][\wÀ-ÿ.]+)?,?\s*\d{4}\)")
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
        for clave in ("text/plain", "text/markdown"):
            contenido = (salida.get("data") or {}).get(clave)
            if contenido:
                texto += "".join(contenido) if isinstance(contenido, list) else contenido
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
    muestra la gráfica dos veces (_lib_check_notebook_sin_duplicados.cjs)."""
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
    """La justificación cita a un autor u organismo que está en
    `docs/BIBLIOGRAFIA.md`. Un paréntesis con forma de cita («(Autor,
    2004)») cuyo autor no figura en la bibliografía NO alcanza: la fuente
    se agrega primero a la bibliografía y después se cita."""
    autores = autores_de_la_bibliografia()
    if any(re.search(rf"(?<![\wÀ-ÿ]){re.escape(autor)}(?![\wÀ-ÿ])", texto) for autor in autores):
        return True
    return any(m.group(1) in autores for m in _CITA_GENERICA.finditer(texto))


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


def calculos_sin_ponderar(nb: dict) -> list[str]:
    """Celdas de código que calculan una estadística cruda (`.mean()`,
    `.median()`, `.value_counts()`) en vez de pasar por los helpers
    ponderados de `analysis.py`. Es la misma señal que
    `verificacion_ponderacion` busca en los módulos, aplicada a las celdas
    del informe — sobre todo a las escritas a mano, que no pasan por los
    tests de la suite. Una estadística de la ECH sin ponderador de
    expansión no describe a la población: regla no negociable del
    proyecto (docs/METODOLOGIA.md, sección 2)."""
    problemas = []
    for i, celda in enumerate(nb.get("cells", [])):
        if celda.get("cell_type") != "code":
            continue
        codigo = "\n".join(
            linea for linea in _fuente(celda).split("\n") if not linea.lstrip().startswith(("%", "!"))
        )
        try:
            arbol = ast.parse(codigo)
        except SyntaxError as e:
            problemas.append(f"celda {i}: no es Python válido ({e.msg}, línea {e.lineno})")
            continue
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Attribute) and nodo.attr in verificacion_ponderacion.METODOS_CRUDOS:
                problemas.append(
                    f"celda {i}: usa .{nodo.attr}() crudo (línea {nodo.lineno}); toda estadística de la "
                    "encuesta se pondera con los helpers de analysis.py (pct_ponderado, media_ponderada_por, "
                    "pct_ponderado_por...)"
                )
    return problemas


def verificar_antes_de_ejecutar(nb: dict) -> list[str]:
    return (
        celdas_que_duplican_grafica(nb)
        + metricas_sin_grafica_o_cita(nb)
        + calculos_sin_ponderar(nb)
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


def resumen_sin_texto(nb: dict) -> list[str]:
    """El «Resumen analítico final» lo arma una celda de código dentro del
    notebook; si existe el encabezado, la celda que sigue tiene que haber
    dejado un output de markdown con texto."""
    celdas = nb.get("cells", [])
    for i, celda in enumerate(celdas):
        if celda.get("cell_type") == "markdown" and _fuente(celda).strip().startswith("## Resumen analítico final"):
            siguiente = celdas[i + 1] if i + 1 < len(celdas) else None
            if siguiente is None or siguiente.get("cell_type") != "code":
                return [f"celda {i}: el resumen analítico no tiene su celda de código a continuación"]
            textos = [
                "".join(s.get("data", {}).get("text/markdown", "")) if isinstance(s.get("data", {}).get("text/markdown", ""), list)
                else s.get("data", {}).get("text/markdown", "")
                for s in siguiente.get("outputs", []) or []
            ]
            if not any(t.strip() for t in textos):
                return [f"celda {i + 1}: el resumen analítico no produjo ningún texto"]
            return []
    return []


def verificar_despues_de_ejecutar(nb: dict) -> list[str]:
    return celdas_con_error(nb) + graficas_faltantes(nb) + resumen_sin_texto(nb)


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


# Variable del notebook → indicador de verificacion_plausibilidad.RANGOS.
# Cada entrada: (nombre de la variable en el JSON de cifras, clave dentro
# de esa variable, nombre del indicador). Solo se mapean variables cuyo
# significado es exactamente el del indicador; lo que no está acá no se
# opina (mejor no opinar que opinar mal).
_INDICADORES_PLAUSIBILIDAD = (
    ("tasas_nacionales", "tasa_actividad", "tasa_actividad"),
    ("tasas_nacionales", "tasa_empleo", "tasa_empleo"),
    ("tasas_nacionales", "tasa_desempleo", "tasa_desempleo"),
    ("pobreza", "pct_pobres", "pct_pobres"),
    ("pobreza", "pct_indigentes", "pct_indigentes"),
    ("resumen_conectividad_mdeo", "pct_con_internet", "pct_con_internet"),
    ("prevalencia_fies", "moderada_o_severa", "pct_inseguridad_alimentaria"),
    ("prevalencia_fies", "severa", "pct_inseguridad_severa"),
)


def indicadores_para_plausibilidad(cifras: dict) -> dict[str, float]:
    """Las cifras ejecutadas del informe que `verificacion_plausibilidad`
    sabe juzgar (identidades que siempre se cumplen y rangos anchos
    anclados en el INE). Toma solo lo presente en esta edición."""
    indicadores: dict[str, float] = {}
    for variable, clave, indicador in _INDICADORES_PLAUSIBILIDAD:
        valor = cifras.get(variable)
        if isinstance(valor, dict) and isinstance(valor.get(clave), (int, float)) and not isinstance(valor.get(clave), bool):
            indicadores[indicador] = float(valor[clave])
    return indicadores


def cifras_sin_respaldo(texto_resumen: str, reales: Iterable[float]) -> list[str]:
    """Cifras del resumen que no coinciden, redondeadas a sus propios
    decimales, con ningún número real (_lib_check_resumen_cifras_inventadas.cjs)."""
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
