"""Genera el informe de punta a punta en dos comandos, sin que el modelo
escriba código ni ejecute el notebook más de una vez.

    run_python.bat -m encuesta_hogares.generar_informe construir --anio 2025 \
        --metricas 1,2,8,13 --bloques brecha_digital,hogares,territorio [--extra celdas.py]

    run_python.bat -m encuesta_hogares.generar_informe entregar --anio 2025

`construir`: arma el notebook con `notebook_builder` (más las celdas a
medida del archivo `--extra`, si lo hay), lo VERIFICA antes de ejecutarlo
(`verificacion_notebook.verificar_antes_de_ejecutar`: gráficas duplicadas,
métricas sin gráfica o sin cita, texto sin completar, encabezados
repetidos), lo ejecuta una sola vez con `jupyter nbconvert`, verifica lo
que solo se sabe después (celdas con error, gráficas sin imagen) y deja
las cifras de cada métrica en un JSON al lado del notebook. Cada corrida
escribe su propia edición, `notebooks/ediciones/Informe_ECH_<año>_<fecha-hora>.*`,
así que dos corridas del mismo año nunca se pisan.
Imprime un JSON con las rutas.

El resumen analítico final lo arma el propio notebook, dentro de
`construir`, con una plantilla de frase por métrica evaluada sobre las
variables que cada métrica dejó (`notebook_builder._RESUMEN_POR_METRICA`,
helpers en `resumen.py`): el número del resumen es el mismo que muestra la
gráfica y ningún modelo redacta ni transcribe cifras. La lista de fuentes
de consulta de los bloques presentes se agrega en el mismo paso.

`entregar`: genera el HTML sin código y el PDF con portada del notebook ya
construido, con copia en Descargas, e imprime un JSON con `pdf_path` y
`html_path` para `formularios.mostrar_finalizacion`. Acepta un
`--comentario` opcional (markdown) que se agrega después del resumen con
cada cifra validada contra los resultados ejecutados (misma regla que
`_lib_check_resumen_cifras_inventadas.cjs`).

Por qué dos comandos y no uno: la pantalla final necesita las rutas y la
persona puede querer revisar el notebook entre un paso y otro; ninguno
de los dos vuelve a ejecutar el notebook (1,68 ejecuciones por corrida en
la bitácora real hasta la v0.13.6, 150 s cada una).

Cada paso pesado queda medido en la bitácora con los mismos nombres de
siempre (`ejecucion_notebook`, `generacion_html`, `conversion_pdf`), así
que `tools/resumen_sesiones.py` sigue leyendo las corridas igual. Si se
vuelve a construir el mismo año dentro de las dos horas, se registra
`reejecucion_notebook` con el motivo (`--motivo`, u "(no indicado)").
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import runpy
import shutil
import subprocess
import sys
import time
from pathlib import Path

import nbformat

from . import bitacora, config, entrega, verificacion_catalogo, verificacion_notebook, verificacion_plausibilidad
from . import notebook_builder as nb

NOTEBOOKS = config.PROJECT_ROOT / "notebooks"
# Cada corrida guiada escribe su propia edición, con fecha y hora en el
# nombre, en esta carpeta (ignorada por git): dos corridas del mismo año
# nunca se pisan y no hace falta ningún respaldo "(anterior)". Hasta la
# v0.15.0 el informe iba a notebooks/Informe_ECH_<año>.* con un único
# respaldo del anterior; con más de dos corridas de un año, la primera se
# perdía.
EDICIONES = NOTEBOOKS / "ediciones"
ESTILO_CSS = config.PROJECT_ROOT / "docs" / "informe_estilo.css"
BLOQUES_VALIDOS = tuple(verificacion_catalogo.BLOQUES)
HORAS_PARA_CONSIDERAR_REEJECUCION = 2


class InformeInvalido(Exception):
    """El notebook no pasa una verificación. El mensaje lista los problemas
    con su celda; el agente corrige la causa y vuelve a correr `construir`."""


def nombre_edicion(anio: int, momento: dt.datetime | None = None) -> str:
    """`Informe_ECH_2025_20260909-1732`: el año de los datos y el instante
    de la corrida, para que el nombre diga de qué es y de cuándo es."""
    momento = momento or dt.datetime.now()
    return f"Informe_ECH_{anio}_{momento:%Y%m%d-%H%M}"


def ruta_notebook(anio: int, momento: dt.datetime | None = None) -> Path:
    """La ruta de una edición NUEVA del año."""
    return EDICIONES / f"{nombre_edicion(anio, momento)}.ipynb"


def ultima_edicion(anio: int) -> Path | None:
    """El notebook de la edición más reciente del año, o None si nunca se
    construyó una. Es lo que `entregar` toma cuando no se le indica una."""
    candidatas = [p for p in EDICIONES.glob(f"Informe_ECH_{anio}_*.ipynb") if not p.name.startswith("_")]
    return max(candidatas, key=lambda p: p.stat().st_mtime) if candidatas else None


# ---------------------------------------------------------------------------
# construir
# ---------------------------------------------------------------------------


def _cargar_extras(ruta: Path | None) -> tuple[dict[int, list[nb.Celda]], list[nb.Celda]]:
    """Las celdas a medida (comparaciones entre años, métricas propias)
    vienen de un archivo Python que define `celdas_extra` (dict número →
    lista de Celda, colgadas de esa métrica) y/o `celdas_finales` (lista de
    Celda, al final antes de la nota metodológica)."""
    if ruta is None:
        return {}, []
    espacio = runpy.run_path(str(ruta))
    extra = espacio.get("celdas_extra") or {}
    finales = espacio.get("celdas_finales") or []
    if not isinstance(extra, dict) or not all(isinstance(v, list) for v in extra.values()):
        raise InformeInvalido(f"{ruta}: `celdas_extra` tiene que ser un dict {{numero: [Celda, ...]}}")
    if not isinstance(finales, list):
        raise InformeInvalido(f"{ruta}: `celdas_finales` tiene que ser una lista de Celda")
    return {int(k): v for k, v in extra.items()}, finales


def _bloques_de(metricas: list[int]) -> list[str]:
    return [b for b, (rango, _n) in verificacion_catalogo.BLOQUES.items() if any(n in rango for n in metricas)]


def construir(
    anio: int,
    metricas: list[int],
    bloques: list[str],
    extra: Path | None = None,
    motivo: str | None = None,
    destino: Path | None = None,
) -> dict:
    desconocidos = sorted(set(bloques) - set(BLOQUES_VALIDOS))
    if desconocidos:
        raise InformeInvalido(f"bloques desconocidos: {desconocidos}; válidos: {list(BLOQUES_VALIDOS)}")

    if destino is None:
        _registrar_reejecucion_si_corresponde(ultima_edicion(anio), motivo)
        destino = ruta_notebook(anio)
    destino.parent.mkdir(parents=True, exist_ok=True)

    with bitacora.medir("construir_notebook"):
        celdas_extra, celdas_finales = _cargar_extras(extra)
        celdas = nb.construir_celdas_notebook(
            anio_base=anio,
            metricas=metricas,
            incluir_brecha_digital="brecha_digital" in bloques,
            incluir_fies="fies" in bloques,
            incluir_empleo="empleo" in bloques,
            incluir_seguridad="seguridad" in bloques,
            celdas_extra=celdas_extra or None,
        )
        # Las celdas finales van antes de la nota metodológica (la última
        # de `construir_celdas_notebook`), como indica el paso 5 del agente.
        nota = celdas.pop()
        celdas.extend(celdas_finales)
        celdas.append(nota)
        # El resumen analítico se arma dentro del notebook, desde las
        # variables de cada métrica, y las fuentes de consulta salen de los
        # bloques presentes: nada de esto lo redacta el modelo.
        celdas.extend(nb.celdas_resumen_analitico(metricas))
        celdas.append(nb.celda_cifras(destino))
        nb.escribir_notebook(celdas, destino)

    notebook = _leer(destino)
    problemas = verificacion_notebook.verificar_antes_de_ejecutar(notebook)
    if problemas:
        bitacora.registrar("verificacion_notebook_bloqueo", etapa="antes_de_ejecutar", problemas=problemas)
        raise InformeInvalido("El notebook no se ejecutó porque no pasa la verificación previa:\n- " + "\n- ".join(problemas))

    try:
        bitacora.medir_comando("ejecucion_notebook", [
            sys.executable, "-m", "jupyter", "nbconvert", "--to", "notebook", "--execute", "--inplace", str(destino),
        ])
    except subprocess.CalledProcessError:
        # nbconvert corta en la primera celda con error y deja el notebook
        # escrito hasta ahí: se informa la celda y el error, no el traceback
        # de subprocess.
        errores = verificacion_notebook.celdas_con_error(_leer(destino)) or ["la ejecución falló sin dejar una celda con error legible"]
        bitacora.registrar("verificacion_notebook_bloqueo", etapa="ejecucion", problemas=errores)
        raise InformeInvalido("El notebook falló al ejecutarse:\n- " + "\n- ".join(errores)) from None

    notebook = _leer(destino)
    problemas = verificacion_notebook.verificar_despues_de_ejecutar(notebook)
    if problemas:
        bitacora.registrar("verificacion_notebook_bloqueo", etapa="despues_de_ejecutar", problemas=problemas)
        raise InformeInvalido("El notebook se ejecutó pero tiene problemas:\n- " + "\n- ".join(problemas))

    cifras = nb.ruta_cifras(destino)
    hallazgos = _revisar_plausibilidad(cifras)
    if hallazgos:
        bitacora.registrar("verificacion_notebook_bloqueo", etapa="plausibilidad", hallazgos=hallazgos)
        raise InformeInvalido(
            "El notebook se ejecutó pero alguna cifra no es plausible o rompe una identidad estadística "
            "(no se compara contra el INE: se verifica que el resultado no sea imposible):\n- " + "\n- ".join(hallazgos)
        )
    return {
        "notebook": str(destino),
        "cifras": str(cifras) if cifras.exists() else None,
        "metricas": len(metricas),
        "bloques": _bloques_de(metricas),
        "celdas": len(notebook["cells"]),
    }


def _revisar_plausibilidad(ruta_cifras: Path) -> list[str]:
    """Las cifras ejecutadas que `verificacion_plausibilidad` sabe juzgar:
    identidades que se cumplen siempre (empleo ≤ actividad, indigencia ≤
    pobreza...) y rangos anchos anclados en magnitudes del INE. Antes solo
    corría en `tools/validar_con_datos_reales.py`, es decir, nunca en una
    corrida real; un disparate podía llegar a un informe entregado."""
    if not ruta_cifras.exists():
        return []
    cifras = json.loads(ruta_cifras.read_text(encoding="utf-8"))
    indicadores = verificacion_notebook.indicadores_para_plausibilidad(cifras)
    return [str(h) for h in verificacion_plausibilidad.revisar(indicadores)]


def _registrar_reejecucion_si_corresponde(anterior: Path | None, motivo: str | None) -> None:
    """Volver a construir el mismo año poco después de la edición anterior
    es una re-ejecución: queda registrada con su motivo, como exige el
    paso 7 del agente — antes dependía de que el modelo se acordara, y en
    la bitácora real había 3 motivos para ~17 ejecuciones extra."""
    if anterior is None or not anterior.exists():
        return
    antiguedad = time.time() - anterior.stat().st_mtime
    if antiguedad < HORAS_PARA_CONSIDERAR_REEJECUCION * 3600:
        bitacora.registrar("reejecucion_notebook", motivo=motivo or "(no indicado)", notebook=anterior.name)


def _leer(ruta: Path) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# entregar
# ---------------------------------------------------------------------------


def _agregar_comentario(destino: Path, markdown_resumen: str) -> list[str]:
    """Valida el comentario opcional contra los resultados ejecutados y lo
    agrega al final del notebook (sin ejecutar). Devuelve los bloques
    presentes. El resumen analítico en sí ya lo armó el propio notebook."""
    notebook = nbformat.read(str(destino), as_version=4)
    crudo = _leer(destino)
    if verificacion_notebook.celdas_con_error(crudo):
        raise InformeInvalido("El notebook tiene celdas con error: corregir y volver a `construir` antes de entregar.")
    if not any(c.get("outputs") for c in crudo["cells"] if c.get("cell_type") == "code"):
        raise InformeInvalido("El notebook no está ejecutado: correr `construir` antes de `entregar`.")

    placeholders = verificacion_notebook.placeholders_en_el_texto({"cells": [{"cell_type": "markdown", "source": markdown_resumen}]})
    if placeholders:
        raise InformeInvalido("El comentario tiene texto sin completar: " + "; ".join(placeholders))

    extra: list[float] = []
    cifras = nb.ruta_cifras(destino)
    if cifras.exists():
        extra = verificacion_notebook.numeros_de_cifras(json.loads(cifras.read_text(encoding="utf-8")))
    reales = verificacion_notebook.numeros_reales(crudo, extra)
    sospechosas = verificacion_notebook.cifras_sin_respaldo(markdown_resumen, reales)
    if sospechosas:
        bitacora.registrar("verificacion_notebook_bloqueo", etapa="resumen", cifras=sospechosas)
        raise InformeInvalido(
            "El comentario cita cifras que no aparecen en ningún resultado del notebook ni en el JSON de cifras: "
            + ", ".join(sospechosas)
            + ". Sacar cada número del archivo de cifras, con los mismos decimales o redondeado."
        )

    metricas = sorted({int(m.group(1)) for c in crudo["cells"] if c.get("cell_type") == "markdown"
                       for m in [re.match(r"^###\s+(\d{1,2})\.", "".join(c.get("source", "")).strip())] if m})
    bloques = _bloques_de(metricas)

    # Si ya había un comentario (entrega repetida), se reemplaza en vez de duplicarlo.
    indice = next((i for i, c in enumerate(notebook.cells)
                   if c.cell_type == "markdown" and c.source.strip().startswith("### Comentario")), None)
    if indice is not None:
        notebook.cells = notebook.cells[:indice]
    notebook.cells.append(nbformat.v4.new_markdown_cell(nb.celda_comentario(markdown_resumen).markdown))
    nbformat.write(notebook, str(destino))
    return bloques


def _generar_html(destino: Path, anio: int, salida: Path) -> Path:
    """HTML sin código: copia del notebook sin los `stderr` de matplotlib,
    `nbconvert --to html --no-input`, título corregido."""
    notebook = nbformat.read(str(destino), as_version=4)
    for celda in notebook.cells:
        if celda.cell_type == "code":
            celda.outputs = [o for o in celda.outputs if not (o.get("output_type") == "stream" and o.get("name") == "stderr")]
    copia = destino.with_name(f"_{destino.stem}_sin_stderr.ipynb")
    nbformat.write(notebook, str(copia))
    try:
        bitacora.medir_comando("generacion_html", [
            sys.executable, "-m", "jupyter", "nbconvert", "--to", "html", "--no-input",
            str(copia), "--output", copia.stem, "--output-dir", str(copia.parent),
        ])
        generado = copia.with_suffix(".html")
        texto = generado.read_text(encoding="utf-8")
        titulo = html.escape(f"Encuesta Continua de Hogares — Informe {anio}")
        texto = re.sub(r"<title>.*?</title>", f"<title>{titulo}</title>", texto, count=1, flags=re.S)
        entrega.respaldar_si_existe(salida)
        salida.write_text(texto, encoding="utf-8")
        generado.unlink(missing_ok=True)
    finally:
        copia.unlink(missing_ok=True)
    return salida


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def portada(anio: int) -> str:
    """La portada del PDF: título, subtítulo que describe el contenido y
    solo la fecha como pie. Es texto visible que no pasa por las celdas del
    notebook, así que tiene su test."""
    hoy = dt.date.today()
    fecha = f"{hoy.day} de {MESES[hoy.month - 1]} de {hoy.year}"
    return f"""
<div class="portada">
  <h1>Encuesta Continua de Hogares {anio} &mdash; Informe</h1>
  <div class="subtitulo">M&eacute;tricas calculadas sobre los microdatos del INE, con cada cifra
  respaldada por los resultados de este informe</div>
  <div class="meta">Generado el {fecha}</div>
</div>
"""


def _html_para_imprimir(ruta_html: Path, anio: int) -> Path:
    """Portada + hoja de estilos del informe, en un HTML intermedio al lado
    del final, con nombre derivado (sección 2 de docs/FLUJO_DE_TRABAJO.md)."""
    texto = ruta_html.read_text(encoding="utf-8")
    css = ESTILO_CSS.read_text(encoding="utf-8")
    texto = texto.replace("</head>", f"<style>\n{css}\n</style>\n</head>", 1)
    texto = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + portada(anio), texto, count=1)
    intermedio = ruta_html.with_name(f"_{ruta_html.stem}_impresion.html")
    intermedio.write_text(texto, encoding="utf-8")
    return intermedio


def _generar_pdf(ruta_html: Path, anio: int, salida: Path) -> Path:
    from playwright.sync_api import sync_playwright

    intermedio = _html_para_imprimir(ruta_html, anio)
    entrega.respaldar_si_existe(salida)
    try:
        with bitacora.medir("conversion_pdf"):
            with sync_playwright() as p:
                navegador = p.chromium.launch()
                pagina = navegador.new_page()
                pagina.goto(intermedio.resolve().as_uri())
                pagina.pdf(
                    path=str(salida),
                    format="A4",
                    print_background=True,
                    display_header_footer=True,
                    header_template="<span></span>",
                    footer_template=(
                        '<div style="font-size:8pt; width:100%; text-align:center; color:#8b949e;">'
                        'P&aacute;gina <span class="pageNumber"></span> de <span class="totalPages"></span></div>'
                    ),
                    margin={"top": "20mm", "bottom": "16mm", "left": "18mm", "right": "18mm"},
                )
                navegador.close()
    finally:
        intermedio.unlink(missing_ok=True)
    return salida


def _copiar_a_descargas(pdf: Path) -> Path | None:
    descargas = Path.home() / "Downloads"
    if not descargas.is_dir():
        return None
    copia = descargas / pdf.name
    entrega.respaldar_si_existe(copia)
    shutil.copy(pdf, copia)
    return copia


def entregar(anio: int, comentario: Path | None = None, destino: Path | None = None) -> dict:
    destino = destino or ultima_edicion(anio)
    if destino is None or not destino.exists():
        raise InformeInvalido(f"No hay ninguna edición de {anio} en {EDICIONES}: correr `construir` primero.")
    crudo = _leer(destino)
    if verificacion_notebook.celdas_con_error(crudo):
        raise InformeInvalido("El notebook tiene celdas con error: corregir y volver a `construir` antes de entregar.")
    if not any(c.get("outputs") for c in crudo["cells"] if c.get("cell_type") == "code"):
        raise InformeInvalido("El notebook no está ejecutado: correr `construir` antes de `entregar`.")
    if verificacion_notebook.resumen_sin_texto(crudo):
        raise InformeInvalido("El notebook no tiene el resumen analítico armado: volver a `construir`.")
    if comentario is not None:
        markdown = comentario.read_text(encoding="utf-8")
        if markdown.strip():
            _agregar_comentario(destino, markdown)
    bloques = _bloques_de(sorted({int(m.group(1)) for c in crudo["cells"] if c.get("cell_type") == "markdown"
                                  for m in [re.match(r"^###\s+(\d{1,2})\.", "".join(c.get("source", "")).strip())] if m}))
    salida_html = _generar_html(destino, anio, destino.with_suffix(".html"))
    salida_pdf = _generar_pdf(salida_html, anio, destino.with_suffix(".pdf"))
    copia = _copiar_a_descargas(salida_pdf)
    return {
        "edicion": destino.stem,
        "pdf_path": str(salida_pdf.resolve()),
        "html_path": str(salida_html.resolve()),
        "copia_descargas": str(copia) if copia else None,
        "pdf_bytes": salida_pdf.stat().st_size,
        "bloques": bloques,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _lista_enteros(texto: str) -> list[int]:
    return sorted({int(x) for x in texto.split(",") if x.strip()})


def _lista(texto: str) -> list[str]:
    return [x.strip() for x in texto.split(",") if x.strip()]


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="generar_informe", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="comando", required=True)

    c = sub.add_parser("construir", help="arma, verifica y ejecuta el notebook (una sola vez)")
    c.add_argument("--anio", type=int, required=True)
    c.add_argument("--metricas", type=_lista_enteros, required=True, help="números del catálogo, separados por coma")
    c.add_argument("--bloques", type=_lista, default=[], help="bloques elegidos en el paso 3.5, separados por coma")
    c.add_argument("--extra", type=Path, default=None, help="archivo .py con celdas_extra y/o celdas_finales")
    c.add_argument("--motivo", default=None, help="por qué se vuelve a construir el mismo año (si aplica)")

    e = sub.add_parser("entregar", help="genera HTML y PDF de la última edición construida del año")
    e.add_argument("--anio", type=int, required=True)
    e.add_argument("--edicion", type=Path, default=None, help="opcional: notebook de una edición concreta (por defecto, la más reciente del año)")
    e.add_argument("--comentario", type=Path, default=None,
                   help="opcional: archivo markdown con un comentario adicional; cada cifra se valida contra los resultados")

    args = parser.parse_args(argumentos)
    try:
        if args.comando == "construir":
            resultado = construir(args.anio, args.metricas, args.bloques, args.extra, args.motivo)
        else:
            resultado = entregar(args.anio, args.comentario, args.edicion)
    except InformeInvalido as e:
        print(f"INFORME NO GENERADO: {e}", file=sys.stderr)
        return 2
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
