"""Frases del "Resumen analítico final", armadas desde las tablas que ya
calculó cada métrica — sin que ningún modelo redacte ni transcriba números.

Hasta la v0.14.2 el resumen lo escribía el modelo leyendo el JSON de
cifras, y `entregar` validaba cada número contra los resultados. Eso
seguía dependiendo de una redacción distinta en cada corrida. Ahora cada
métrica del catálogo tiene su plantilla de frase en
`notebook_builder._RESUMEN_POR_METRICA`, que se evalúa dentro del propio
notebook sobre las variables de la métrica: el número que dice el
resumen es, por construcción, el mismo que muestra la gráfica.

Este módulo son los helpers que usan esas plantillas: leer un valor de
una tabla por filtro, encontrar extremos, formatear a la uruguaya (coma
decimal, punto de miles) y armar el markdown por bloque. Son funciones
puras sobre DataFrames/dicts ya calculados — no vuelven a tocar los
microdatos ni a calcular nada estadístico.
"""

from __future__ import annotations

import numbers
import re

import pandas as pd


def fmt(valor, decimales: int = 1) -> str:
    """45.31 → «45,3»; 23544 → «23.544»; None/NaN → «s/d»."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return "s/d"
    if isinstance(valor, numbers.Integral) or (isinstance(valor, float) and decimales == 0):
        return f"{int(round(valor)):,}".replace(",", ".")
    texto = f"{float(valor):,.{decimales}f}"
    # Intercambia separadores con un centinela: coma de miles → punto, punto decimal → coma.
    return texto.replace(",", "|").replace(".", ",").replace("|", ".")


def fmt_signo(valor, decimales: int = 1) -> str:
    """Como `fmt`, con el signo siempre explícito: «+16,9», «−2,2»."""
    texto = fmt(abs(float(valor)), decimales)
    return ("−" if float(valor) < 0 else "+") + texto


def valor(tabla: pd.DataFrame, columna_valor: str, **filtros) -> float:
    """El valor de `columna_valor` en la única fila que cumple `filtros`
    (`valor(df, "pct", nivel_economico="1-Bajo")`). Falla con un mensaje
    claro si no hay exactamente una fila: un resumen no puede elegir en
    silencio."""
    filas = tabla
    for columna, esperado in filtros.items():
        filas = filas[filas[columna] == esperado]
    if len(filas) != 1:
        raise ValueError(f"se esperaba una fila con {filtros} y hay {len(filas)}")
    return float(filas.iloc[0][columna_valor])


def extremos(tabla: pd.DataFrame, columna_categoria: str, columna_valor: str) -> tuple[str, float, str, float]:
    """(categoría con el valor máximo, máximo, categoría con el mínimo, mínimo)."""
    limpia = tabla.dropna(subset=[columna_valor])
    if limpia.empty:
        raise ValueError(f"la tabla no tiene valores en {columna_valor!r}")
    fila_max = limpia.loc[limpia[columna_valor].idxmax()]
    fila_min = limpia.loc[limpia[columna_valor].idxmin()]
    return str(fila_max[columna_categoria]), float(fila_max[columna_valor]), str(fila_min[columna_categoria]), float(fila_min[columna_valor])


_CONECTORES = {"y", "de", "del", "la", "las", "los", "e"}


def nombre_propio(texto) -> str:
    """Un nombre en mayúsculas sostenidas, como lo traen los archivos de
    Hogares del INE, escrito como se lee: «TREINTA Y TRES» → «Treinta y
    Tres», «RÍO NEGRO» → «Río Negro». Lo que no está en mayúsculas
    sostenidas se devuelve tal cual (los archivos de Empleo ya traen
    «Treinta y Tres»)."""
    texto = str(texto).strip()
    if not texto.isupper():
        return texto
    palabras = [p.capitalize() for p in texto.lower().split(" ")]
    return " ".join(p.lower() if i and p.lower() in _CONECTORES else p for i, p in enumerate(palabras))


def etiqueta(categoria) -> str:
    """Etiqueta legible de una categoría: sin el prefijo de orden que traen
    las del INE («1-Bajo» → «bajo», «4. Terciario completo» → «terciario
    completo») y sin mayúsculas sostenidas («TACUAREMBÓ» → «Tacuarembó»,
    «TREINTA Y TRES» → «Treinta y Tres»)."""
    texto = str(categoria).strip()
    texto = re.sub(r"^\d+\s*[-.]\s*", "", texto)
    if texto.isupper():
        texto = nombre_propio(texto)
    elif texto[:1].isupper() and " " in texto and not any(ch.isupper() for ch in texto[1:].replace("(", " ")):
        texto = texto[0].lower() + texto[1:]
    return texto


def _entre_parentesis(categoria) -> str:
    """La etiqueta lista para ir entre paréntesis: si ya trae un paréntesis
    («generación silenciosa (hasta 1945)») se convierte en una coma, para
    no anidar paréntesis en la frase."""
    return re.sub(r"\s*\((.*?)\)", r", \1", etiqueta(categoria))


def brecha(tabla: pd.DataFrame, columna_categoria: str, columna_valor: str, sujeto: str, unidad: str = "%") -> str:
    """«<sujeto> va de <mín> (<cat>) a <máx> (<cat>)» con los extremos de la tabla."""
    cat_max, v_max, cat_min, v_min = extremos(tabla, columna_categoria, columna_valor)
    return f"{sujeto} va de {fmt(v_min)}{unidad} ({_entre_parentesis(cat_min)}) a {fmt(v_max)}{unidad} ({_entre_parentesis(cat_max)})"


def en_cuantos(parte: int, total: int, sustantivo: str) -> str:
    """«En 3 de los 5 tipos de delito» — o «En los 5 tipos de delito» cuando
    son todos, y «En ninguno de los 5 tipos de delito» cuando ninguno."""
    if parte == total:
        return f"En los {total} {sustantivo}"
    if parte == 0:
        return f"En ninguno de los {total} {sustantivo}"
    return f"En {parte} de los {total} {sustantivo}"


_SECTORES = {"hogares": "hogares (servicio doméstico)"}


def nombre_sector(sector) -> str:
    """El sector de la unidad económica (formal, informal, hogares) tal como
    se nombra en el resumen: «hogares» solo, sin explicar, no se entiende."""
    nombre = etiqueta(sector).lower()
    return _SECTORES.get(nombre, nombre)


def nombre_mes(mes) -> str:
    from . import config
    return config.MESES_LABELS.get(int(mes), str(mes))


def armar_markdown(frases_por_bloque: dict[str, list[str]]) -> str:
    """Un párrafo por bloque, en el orden recibido, con el nombre del bloque
    en negrita y las frases de sus métricas encadenadas."""
    partes = []
    for bloque, frases in frases_por_bloque.items():
        limpias = [f.strip().rstrip(".") + "." for f in frases if f and f.strip()]
        if limpias:
            partes.append(f"**{bloque}.** " + " ".join(limpias))
    return "\n\n".join(partes)
