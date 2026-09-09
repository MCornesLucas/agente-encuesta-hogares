"""Detecta citas de `docs/BIBLIOGRAFIA.md` que quedaron sin conectar a
ningún patrón real de `docs/CONVENCIONES_DE_GRAFICAS.md`.

Nace de un descuido real de este proyecto: al agregar varias fuentes
nuevas a la sección "Visualización de datos" de BIBLIOGRAFIA.md (Cohen,
Ware, Wilke, Tufte), quedaron como afirmaciones sueltas — el texto decía
qué patrón respaldaban, pero esa cita nunca se escribió en la entrada
real de la guía de referencia de CONVENCIONES_DE_GRAFICAS.md. Nada lo
detectó hasta una revisión manual. Este módulo lo convierte en un chequeo
automático: si un autor de esa sección no aparece ni una vez en
CONVENCIONES_DE_GRAFICAS.md, la cita quedó sin conectar.

Mismo criterio que `verificacion_catalogo` para métricas huérfanas: no
verifica que la cita esté bien aplicada (eso sigue siendo criterio
humano), solo que el nombre del autor aparezca en algún lado del
documento — la señal mínima de que alguien la escribió en un punto de
uso real, no solo en el índice.
"""

from __future__ import annotations

import re
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[2]
_DOCS = _RAIZ / "docs"
_BIBLIOGRAFIA = _DOCS / "BIBLIOGRAFIA.md"

# Dónde puede vivir la conexión real de una cita de "Visualización de
# datos": la guía de referencia de tipos de gráfica (el caso más común),
# las reglas de rigor estadístico cuando la cita respalda una regla en vez
# de una elección de gráfica puntual (ej. Healy, integridad del eje — ver
# METODOLOGIA.md sección 2), o el docstring de una función específica
# cuando la cita justifica un detalle muy puntual de una sola gráfica (ej.
# Weissgerber, "dynamite plot", en el docstring de
# visualization.plot_composicion_edades). Alcanza con que aparezca en
# CUALQUIERA de estos — no hace falta que esté en los cuatro.
_LUGARES_DE_CONEXION = [
    _DOCS / "CONVENCIONES_DE_GRAFICAS.md",
    _DOCS / "METODOLOGIA.md",
    _RAIZ / "src" / "encuesta_hogares" / "visualization.py",
    _RAIZ / "src" / "encuesta_hogares" / "analysis.py",
]

# Autores de la sección "Visualización de datos" que a propósito todavía no
# están conectados a ningún patrón de CONVENCIONES_DE_GRAFICAS.md — cada
# uno con la razón, igual que verificacion_ponderacion.ALLOWLIST. No agregar
# un autor acá solo para hacer pasar el chequeo: la razón tiene que ser
# real y estar también en la propia entrada de BIBLIOGRAFIA.md.
EXENTOS_DE_CONEXION: dict[str, str] = {
    "Hofmann": (
        "referencia para el día que el catálogo incluya una métrica de "
        "distribución continua con muestra grande — todavía no existe esa "
        "métrica, ver su propia entrada en BIBLIOGRAFIA.md."
    ),
}


def _seccion_visualizacion_de_datos(texto_bibliografia: str) -> str:
    """Recorta solo la sección "## Visualización de datos" (hasta el
    próximo "## ") — las demás secciones de BIBLIOGRAFIA.md son fuentes
    específicas de un bloque temático, citadas desde
    `.claude/instrucciones/encuesta-hogares.md` en vez de desde
    CONVENCIONES_DE_GRAFICAS.md (ver el propio encabezado de
    BIBLIOGRAFIA.md) — no les aplica este chequeo.
    """
    inicio = texto_bibliografia.find("## Visualización de datos")
    if inicio == -1:
        return ""
    resto = texto_bibliografia[inicio:]
    fin = resto.find("\n## ", 1)
    return resto if fin == -1 else resto[:fin]


def autores_citados_en_visualizacion_de_datos() -> list[str]:
    """Apellido (o nombre de organismo) de cada fuente de la sección
    "Visualización de datos" de BIBLIOGRAFIA.md — una por viñeta de primer
    nivel ("- Autor, ...")."""
    if not _BIBLIOGRAFIA.exists():
        return []
    seccion = _seccion_visualizacion_de_datos(_BIBLIOGRAFIA.read_text(encoding="utf-8"))
    return re.findall(r"^- ([A-ZÀ-Ý][a-zà-ÿ]+)", seccion, flags=re.MULTILINE)


def citas_sin_conectar() -> dict[str, str]:
    """Autores de `autores_citados_en_visualizacion_de_datos()` que no
    aparecen en ninguno de `_LUGARES_DE_CONEXION` y no están en
    `EXENTOS_DE_CONEXION` — devuelve `{autor: razón}`, con una razón
    genérica para los que no están exentos."""
    textos = [p.read_text(encoding="utf-8") for p in _LUGARES_DE_CONEXION if p.exists()]
    faltantes = {}
    for autor in autores_citados_en_visualizacion_de_datos():
        if autor in EXENTOS_DE_CONEXION:
            continue
        patron = rf"\b{re.escape(autor)}\b"
        if not any(re.search(patron, texto) for texto in textos):
            lugares = ", ".join(p.name for p in _LUGARES_DE_CONEXION)
            faltantes[autor] = (
                f"aparece en BIBLIOGRAFIA.md pero no en ninguno de estos "
                f"lugares donde puede vivir la conexión real ({lugares}) — "
                "escribir la cita en el punto concreto que respalda, o "
                "agregarlo a EXENTOS_DE_CONEXION con la razón real si "
                "todavía no corresponde a ningún patrón existente."
            )
    return faltantes
