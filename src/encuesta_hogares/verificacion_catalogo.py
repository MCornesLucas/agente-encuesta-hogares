"""Manifiesto métrica → función: detecta métricas "huérfanas" del catálogo.

`formularios.py` define el catálogo que ve el usuario (número, título,
descripción) pero **nunca dice qué función de `analysis.py`/
`preprocessing.py`/`visualization.py` la implementa** — esa asociación
solo existe en la cabeza de quien construye el notebook (el agente
`encuesta-hogares`, siguiendo el paso 5 de su instrucción: "leé
analysis.py y visualization.py, y llamá a las funciones que ya
identificaste"). Nada verifica automáticamente que esa asociación siga
siendo válida.

Construyendo este manifiesto se encontraron 4 métricas del catálogo
activo de ese momento (calidad de conexión, relación entre barrio y
nivel económico, streaming vs. cable, y situación ocupacional por
sector) que **no tenían ninguna función de análisis propia, ponderada y
testeada** — el cálculo quedaba librado a que el agente lo improvisara
dentro del notebook en cada corrida, sin test, sin revisión, y en al
menos un caso directamente sin ponderar. Se corrigieron agregando las
funciones que faltaban (ver `analysis.composicion_categorica_ponderada_por`
y sus usos concretos) — este módulo existe para que la próxima métrica
en esa misma situación falle un test en vez de esperar a que alguien la
note en una corrida real.

(Dos de esas cuatro — relación entre barrio y nivel económico, y
streaming vs. cable — se sacaron después del catálogo por completo
junto con "Montevideo frente al resto del país" y "Suscripción a TV
cable por barrio"; sus funciones, ya sin ningún uso real, se borraron
con ellas. Ver CHANGELOG.md para cuándo y por qué.)

MANIFEST no pretende ser el ÚNICO camino válido para cada métrica —
varias reutilizan un mismo helper genérico (`pct_ponderado_por`,
`tasa_mensual_promedio_por`, etc.) con distintos argumentos, y más de
una función podría servir igual de bien. La garantía que da esta
verificación es más modesta pero igual de útil: cada métrica tiene AL
MENOS UNA función real, existente y llamable que la implementa — no que
el manifiesto documente el único camino verdadero.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import analysis, config, formularios, preprocessing, visualization
from .verificacion_estructura import columnas_csv, columnas_sav

_MODULOS = {"analysis": analysis, "preprocessing": preprocessing, "visualization": visualization}

# numero -> {"funciones": [referencias "modulo.nombre" que calculan los
# datos], "visualizacion": referencia "modulo.nombre" que la grafica}.
# Ver la nota en el docstring del módulo sobre por qué "funciones" no
# pretende ser la única lista posible.
MANIFEST: dict[int, dict] = {
    # 1 · Brecha Digital
    1: {"funciones": ["analysis.brecha_digital_por_nivel_economico"], "visualizacion": "visualization.plot_brecha_digital"},
    2: {"funciones": ["analysis.brecha_digital_por_cohorte"], "visualizacion": "visualization.plot_brecha_digital_por_cohorte"},
    3: {"funciones": ["analysis.calidad_conexion_por"], "visualizacion": "visualization.plot_calidad_conexion_por"},
    4: {"funciones": ["analysis.brecha_digital_por_jefatura"], "visualizacion": "visualization.plot_brecha_digital_por_jefatura"},
    5: {"funciones": ["analysis.indice_acceso_digital_por"], "visualizacion": "visualization.plot_indice_acceso_digital_por"},
    6: {"funciones": ["analysis.adopcion_tablet_ibirapita_por"], "visualizacion": "visualization.plot_adopcion_tablet_ibirapita"},
    # 2 · Hogares
    7: {"funciones": ["analysis.pct_pobres_indigentes"], "visualizacion": "visualization.plot_pct_pobres_indigentes"},
    8: {"funciones": ["analysis.tasa_jefatura_femenina"], "visualizacion": "visualization.plot_tasa_jefatura_femenina"},
    9: {"funciones": ["analysis.pct_hacinamiento_por", "preprocessing.compute_hacinamiento"], "visualizacion": "visualization.plot_hacinamiento_por"},
    10: {"funciones": ["analysis.tipos_hogar_resumen"], "visualizacion": "visualization.plot_tipos_hogar"},
    11: {"funciones": ["analysis.razon_dependencia_por"], "visualizacion": "visualization.plot_razon_dependencia_por"},
    12: {"funciones": ["analysis.pct_unipersonales_mayores"], "visualizacion": "visualization.plot_pct_unipersonales_mayores"},
    # 3 · Territorio
    13: {"funciones": ["analysis.indice_desarrollo_territorial"], "visualizacion": "visualization.plot_indice_desarrollo_territorial"},
    14: {"funciones": ["analysis.indice_desarrollo_territorial"], "visualizacion": "visualization.plot_perfil_territorial"},
    15: {"funciones": ["analysis.diferencia_entre_categorias"], "visualizacion": "visualization.plot_dumbbell"},
    # 4 · Vivienda
    16: {"funciones": ["analysis.precariedad_estructural"], "visualizacion": "visualization.plot_precariedad_estructural"},
    17: {"funciones": ["analysis.precariedad_estructural_por"], "visualizacion": "visualization.plot_precariedad_estructural_por"},
    18: {"funciones": ["analysis.precariedad_estructural_por"], "visualizacion": "visualization.plot_precariedad_estructural_por"},
    19: {"funciones": ["analysis.diferencia_entre_categorias"], "visualizacion": "visualization.plot_dumbbell"},
    20: {"funciones": ["analysis.carencias_estructurales_mas_frecuentes"], "visualizacion": "visualization.plot_carencias_estructurales_mas_frecuentes"},
    # 5 · Seguridad alimentaria (FIES)
    21: {"funciones": ["analysis.prevalencia_inseguridad_alimentaria"], "visualizacion": "visualization.plot_prevalencia_inseguridad_alimentaria"},
    22: {"funciones": ["analysis.inseguridad_alimentaria_por"], "visualizacion": "visualization.plot_inseguridad_alimentaria_por"},
    23: {"funciones": ["analysis.inseguridad_alimentaria_por"], "visualizacion": "visualization.plot_inseguridad_alimentaria_por"},
    24: {"funciones": ["analysis.diferencia_entre_categorias"], "visualizacion": "visualization.plot_dumbbell"},
    25: {"funciones": ["analysis.inseguridad_alimentaria_por"], "visualizacion": "visualization.plot_inseguridad_alimentaria_por"},
    26: {"funciones": ["analysis.inseguridad_alimentaria_por"], "visualizacion": "visualization.plot_inseguridad_alimentaria_por"},
    27: {"funciones": ["analysis.inseguridad_alimentaria_por"], "visualizacion": "visualization.plot_inseguridad_alimentaria_por"},
    # 6 · Empleo
    28: {"funciones": ["analysis.tasas_actividad_empleo_desempleo"], "visualizacion": "visualization.plot_tasas_actividad_empleo_desempleo"},
    29: {"funciones": ["analysis.tasas_actividad_empleo_desempleo_por", "analysis.brecha_por_grupo"], "visualizacion": "visualization.plot_tasas_por_grupo"},
    30: {"funciones": ["analysis.tasa_mensual_promedio_por"], "visualizacion": "visualization.plot_tasa_mensual_promedio_por"},
    31: {"funciones": ["analysis.tasa_mensual_promedio_por"], "visualizacion": "visualization.plot_tasa_mensual_promedio_por"},
    32: {"funciones": ["analysis.tasa_mensual_promedio_por"], "visualizacion": "visualization.plot_tasa_mensual_promedio_por"},
    33: {"funciones": ["analysis.tasa_mensual_promedio_por"], "visualizacion": "visualization.plot_tasa_mensual_promedio_por"},
    34: {"funciones": ["analysis.tasas_actividad_empleo_desempleo_por", "analysis.brecha_por_grupo"], "visualizacion": "visualization.plot_tasas_por_grupo"},
    35: {"funciones": ["analysis.composicion_categorica_por_mes_promedio"], "visualizacion": "visualization.plot_composicion_categorica"},
    # 7 · Seguridad y victimización
    36: {"funciones": ["analysis.pct_ponderado_por"], "visualizacion": "visualization.plot_pct_por"},
    37: {"funciones": ["analysis.pct_ponderado_por"], "visualizacion": "visualization.plot_pct_por"},
    38: {"funciones": ["analysis.pct_ponderado_por"], "visualizacion": "visualization.plot_pct_por"},
    39: {"funciones": ["analysis.pct_ponderado_por"], "visualizacion": "visualization.plot_pct_por"},
    40: {"funciones": ["analysis.pct_ponderado_por"], "visualizacion": "visualization.plot_pct_por"},
    41: {"funciones": ["analysis.pct_ponderado_por"], "visualizacion": "visualization.plot_dumbbell"},
    42: {"funciones": ["analysis.pct_ponderado_por"], "visualizacion": "visualization.plot_pct_por"},
}


@dataclass
class ReferenciaRota:
    numero: int
    referencia: str


def numeros_del_catalogo() -> dict[int, str]:
    """Recorre el catálogo real de `formularios.py` (los 4 bloques:
    permanentes + FIES + Empleo + Seguridad) y devuelve {número: título} —
    la fuente de verdad contra la que se valida MANIFEST, para que un
    número agregado/quitado del catálogo se note acá sin duplicar la
    lista a mano.
    """
    numeros: dict[int, str] = {}
    for _clave, (_titulo_bloque, _nota, metricas) in formularios._CATEGORIAS_METRICAS.items():
        for numero, titulo, _descripcion in metricas:
            numeros[numero] = titulo
    for bloque in (formularios._CATEGORIA_FIES, formularios._CATEGORIA_EMPLEO, formularios._CATEGORIA_SEGURIDAD):
        _titulo_bloque, _nota, metricas = bloque
        for numero, titulo, _descripcion in metricas:
            numeros[numero] = titulo
    return numeros


def _resolver(referencia: str):
    modulo_nombre, _, funcion_nombre = referencia.partition(".")
    modulo = _MODULOS.get(modulo_nombre)
    if modulo is None:
        return None
    return getattr(modulo, funcion_nombre, None)


def metricas_sin_manifiesto(catalogo: dict[int, str]) -> set[int]:
    """Números del catálogo real que no tienen entrada en MANIFEST."""
    return set(catalogo) - set(MANIFEST)


def entradas_manifiesto_obsoletas(catalogo: dict[int, str]) -> set[int]:
    """Números de MANIFEST que ya no existen en el catálogo real (métrica
    renumerada o eliminada, entrada no limpiada)."""
    return set(MANIFEST) - set(catalogo)


_VALIDADOR_DATOS_REALES = Path(__file__).resolve().parents[2] / "tools" / "validar_con_datos_reales.py"


def metricas_sin_funcion_validada_con_datos_reales() -> dict[int, list[str]]:
    """Números de MANIFEST cuya(s) función(es) de "funciones" nunca se
    invocan en `tools/validar_con_datos_reales.py` — la garantía de
    `referencias_rotas()` es solo que la función *existe*, no que alguien
    la haya corrido de verdad contra datos reales del INE.

    Nace de una evaluación de rigor real de este proyecto: 31 de las 47
    métricas del catálogo activo no tenían ninguna de sus funciones
    invocada ahí — esa brecha no la detectaba ni la suite sintética
    (que no usa datos reales) ni "el pipeline no explota" (un test
    sintético puede pasar aunque el cálculo esté mal para un caso real
    que ese sintético no reproduce). Se cerró para las 47 en esa
    evaluación; este chequeo existe para que la próxima métrica que se
    agregue sin ejercitarla ahí falle un test en vez de sumarse en
    silencio a la lista.

    Solo mira coincidencia de nombre de función en el texto del archivo
    (no ejecuta nada) — no reemplaza correr el script de verdad contra
    datos reales, que sigue siendo manual (`./run_python.bat
    tools/validar_con_datos_reales.py`, cuando hay datos en `data/`).
    """
    if not _VALIDADOR_DATOS_REALES.exists():
        return {}
    texto = _VALIDADOR_DATOS_REALES.read_text(encoding="utf-8")
    faltantes: dict[int, list[str]] = {}
    for numero, entrada in MANIFEST.items():
        nombres = [ref.split(".")[-1] for ref in entrada["funciones"]]
        invocada = any(re.search(rf"\b{re.escape(nombre)}\s*\(", texto) for nombre in nombres)
        if not invocada:
            faltantes[numero] = nombres
    return faltantes


def referencias_rotas() -> list[ReferenciaRota]:
    """Toda referencia de MANIFEST (en "funciones" o "visualizacion") que
    apunta a una función que no existe de verdad en su módulo — la señal
    concreta de una métrica huérfana: catalogada, pero sin implementación
    real detrás (o con una que se borró/renombró después)."""
    rotas = []
    for numero, entrada in MANIFEST.items():
        referencias = list(entrada["funciones"]) + [entrada["visualizacion"]]
        for referencia in referencias:
            if _resolver(referencia) is None:
                rotas.append(ReferenciaRota(numero, referencia))
    return rotas


# ============================================================================
# Disponibilidad por año: MANIFEST/referencias_rotas() verifica que el
# CÓDIGO exista — esto verifica que los DATOS del año elegido tengan las
# columnas que ese código necesita. Nace de un caso real: en 2025 el INE
# dejó de publicar INFORMAL/SECTOR_F/SIT_OCUP en los archivos mensuales de
# Empleo, y nada avisaba de eso hasta que la métrica correspondiente
# reventaba a mitad de una corrida — después de que el usuario ya la había
# elegido en el catálogo (paso 4). Este chequeo corre antes, con solo leer
# el encabezado de un archivo (sin cargar los datos completos), para poder
# avisar en el catálogo mismo en vez de con un traceback.
#
# Solo tiene entradas para métricas con un riesgo real y ya observado de
# que su columna de origen varíe entre años — no las 47, para no acumular
# un mapeo enorme que nadie mantiene. Si otro bloque tiene alguna vez el
# mismo problema, sumale su entrada acá cuando pase, no antes.
#
# numero -> lista de "opciones": cada opción es una lista de columnas
# CRUDAS (nombre tal cual viene en el archivo del INE, antes de
# config.EMPLEO_COLUMNS) que alcanzan, todas juntas, para calcular esa
# métrica. Basta con que UNA opción esté completa. Ej. informalidad
# (36/37) tiene dos caminos posibles (INFORMAL directo, o f82 si no está
# — ver preprocessing.prepare_empleo); situación ocupacional (40) por
# ahora solo tiene un camino conocido.
COLUMNAS_REQUERIDAS: dict[int, list[list[str]]] = {
    31: [["INFORMAL"], ["f82"]],
    32: [["INFORMAL"], ["f82"]],
    35: [["SIT_OCUP", "SECTOR_F"]],
    # Territorio + Vivienda (14-21): TODA la sección depende, directa o
    # indirectamente, de analysis.precariedad_estructural/_por (y
    # carencias_estructurales_mas_frecuentes en 21) - ver
    # `analysis._condiciones_vivienda_disponibles`. No es solo 17-19/21
    # (las que MANIFEST asocia directamente con esas funciones): 14/15
    # arman el índice territorial con precariedad como uno de sus 3
    # componentes fijos (notebook_builder._COMPONENTES_TERRITORIO), 16
    # reutiliza ese mismo índice para "mejor vs. peor departamento", y 20
    # compara precariedad entre nivel económico bajo y alto - MANIFEST
    # solo lista su función "oficial" (diferencia_entre_categorias en
    # ambos casos), no esta dependencia real de datos. Basta con que UNA
    # columna del módulo C5 esté presente para que las funciones de
    # precariedad tengan algo que calcular.
    #
    # Encontrado con datos reales de 2023: ese año el INE no relevó el
    # módulo C5 en absoluto (no es un cambio de nombre de columna, el
    # módulo entero no está en el cuestionario), y nada avisaba de eso
    # hasta que la métrica reventaba a mitad de una corrida - mismo tipo
    # de caso que ya motivó este mapeo para Empleo. El dueño del proyecto
    # eligió avisar explícitamente en vez de recalcular el índice
    # territorial con menos componentes (ver la nota en
    # tools/validar_con_datos_reales.py).
    13: [[c] for c in config.CONDICIONES_VIVIENDA_COLUMNS_CSV],
    14: [[c] for c in config.CONDICIONES_VIVIENDA_COLUMNS_CSV],
    15: [[c] for c in config.CONDICIONES_VIVIENDA_COLUMNS_CSV],
    16: [[c] for c in config.CONDICIONES_VIVIENDA_COLUMNS_CSV],
    17: [[c] for c in config.CONDICIONES_VIVIENDA_COLUMNS_CSV],
    18: [[c] for c in config.CONDICIONES_VIVIENDA_COLUMNS_CSV],
    19: [[c] for c in config.CONDICIONES_VIVIENDA_COLUMNS_CSV],
    20: [[c] for c in config.CONDICIONES_VIVIENDA_COLUMNS_CSV],
}

# Qué números de COLUMNAS_REQUERIDAS le corresponde chequear a cada fuente
# de datos (Empleo vs. Hogares) - sin esto, `metricas_empleo_no_disponibles`
# marcaría las métricas de Vivienda como "no disponibles" solo porque el
# archivo de Empleo (obviamente) no tiene columnas de vivienda, y viceversa.
_METRICAS_EMPLEO = {31, 32, 35}
_METRICAS_HOGARES = {13, 14, 15, 16, 17, 18, 19, 20}


def metricas_no_disponibles(columnas_presentes: set[str], numeros: set[int] | None = None) -> dict[int, list[str]]:
    """De `COLUMNAS_REQUERIDAS`, qué métricas no se pueden calcular con
    `columnas_presentes` (las columnas crudas que de verdad trae el
    archivo de un año — ver `metricas_empleo_no_disponibles`/
    `metricas_hogares_no_disponibles` para obtenerlas solas con leer el
    encabezado). `numeros` restringe la revisión a esas entradas de
    COLUMNAS_REQUERIDAS (todas por defecto) - necesario porque cada fuente
    de datos solo puede hablar de sus propias columnas, no de las de otra
    fuente. Devuelve `{número: columnas que le faltarían a la opción más
    cercana}` — solo para las métricas donde NINGUNA opción está completa.
    """
    resultado = {}
    entradas = COLUMNAS_REQUERIDAS if numeros is None else {n: COLUMNAS_REQUERIDAS[n] for n in numeros}
    for numero, opciones in entradas.items():
        if any(all(c in columnas_presentes for c in opcion) for opcion in opciones):
            continue
        mejor_opcion = min(opciones, key=lambda op: sum(1 for c in op if c not in columnas_presentes))
        resultado[numero] = [c for c in mejor_opcion if c not in columnas_presentes]
    return resultado


def metricas_empleo_no_disponibles(anio: int | str) -> dict[int, list[str]]:
    """Igual que `metricas_no_disponibles`, pero mirando directo los
    archivos mensuales de Empleo de `anio` — solo lee el encabezado del
    primer archivo que exista (los 12 deberían compartir estructura;
    `verificacion_estructura.verificar_empleo` ya audita eso por
    separado). Diccionario vacío si el año no tiene ningún archivo de
    Empleo todavía, o si no falta nada.
    """
    primero = next((a for a in config.empleo_files(anio) if a.exists()), None)
    if primero is None:
        return {}
    return metricas_no_disponibles(columnas_csv(primero), _METRICAS_EMPLEO)


def metricas_hogares_no_disponibles(anio: int | str) -> dict[int, list[str]]:
    """Igual que `metricas_empleo_no_disponibles`, pero mirando el archivo
    de Hogares/Personas de `anio` - CSV combinado (2024 en adelante, y
    2023 con `config.hogares_csv_file`) o `H_*.sav` (2019 y anteriores).
    Diccionario vacío si el año no tiene ningún archivo de Hogares
    todavía, o si no falta nada.
    """
    csv_path = config.hogares_csv_file(anio)
    if csv_path.exists():
        return metricas_no_disponibles(columnas_csv(csv_path), _METRICAS_HOGARES)
    candidatos = sorted((config.DATA_DIR / str(anio)).glob("H_*.sav"))
    if not candidatos:
        return {}
    return metricas_no_disponibles(columnas_sav(candidatos[0]), _METRICAS_HOGARES)


def aviso_metricas_no_disponibles(anio: int | str) -> list[str]:
    """Mensajes ya redactados, uno por métrica de Empleo o de Vivienda no
    disponible para `anio` — para mostrarle al usuario ANTES de que elija
    el catálogo (paso 4 de `.claude/agents/encuesta-hogares.md`), no
    después de que la corrida falle. Lista vacía si no hay nada para
    avisar.
    """
    catalogo = numeros_del_catalogo()
    faltantes_por_metrica = {**metricas_empleo_no_disponibles(anio), **metricas_hogares_no_disponibles(anio)}
    avisos = []
    for numero, faltantes in sorted(faltantes_por_metrica.items()):
        titulo = catalogo.get(numero, "?")
        plural = "n" if len(faltantes) > 1 else ""
        avisos.append(
            f"Métrica {numero} — {titulo}: no disponible para este año, "
            f"falta{plural} {', '.join(faltantes)} en los datos del INE."
        )
    return avisos


# ============================================================================
# Qué bloques temáticos tiene sentido ofrecerle a la persona para un año.
#
# Nace de una corrida real: alguien eligió 2023 y marcó solo "Territorio",
# que para ese año está COMPLETAMENTE vacío (el INE no relevó el módulo C5,
# del que depende la precariedad de vivienda, uno de los componentes del
# índice). El catálogo quedaba sin ninguna métrica y el flujo volvía al
# formulario de áreas sin explicar nada — parecía un error del programa.
#
# El caso silencioso era peor: eligiendo Territorio junto con otro bloque,
# el informe salía sin ninguna métrica territorial y sin ningún aviso.
#
# `plantilla_areas` no puede calcular esto por su cuenta porque este módulo
# ya importa `formularios` — invertirlo sería un import circular. Por eso la
# función vive acá y el formulario recibe los flags ya resueltos.
# ============================================================================

# bloque -> (numeros de metrica, nombre visible en el formulario)
# Nombre visible de cada bloque (el de los encabezados del informe). Los
# NÚMEROS de cada bloque no se escriben acá: salen del catálogo real de
# plantillas.py, así agregar o quitar una métrica no exige actualizar un
# rango literal (hasta la v0.14.1 vivían duplicados en tres lugares).
_NOMBRES_DE_BLOQUE: dict[str, str] = {
    "brecha_digital": "Brecha Digital",
    "hogares": "Hogares",
    "territorio": "Territorio",
    "vivienda": "Vivienda",
    "fies": "Seguridad alimentaria",
    "empleo": "Empleo",
    "seguridad": "Seguridad y victimización",
}


def _catalogo_por_bloque() -> dict[str, list[int]]:
    """{clave de bloque: números de sus métricas}, en el orden del catálogo."""
    fuentes = dict(formularios._CATEGORIAS_METRICAS)
    fuentes["fies"] = formularios._CATEGORIA_FIES
    fuentes["empleo"] = formularios._CATEGORIA_EMPLEO
    fuentes["seguridad"] = formularios._CATEGORIA_SEGURIDAD
    return {clave: sorted(n for n, _t, _d in metricas) for clave, (_titulo, _nota, metricas) in fuentes.items()}


def _rangos_del_catalogo() -> dict[str, tuple[range, str]]:
    bloques: dict[str, tuple[range, str]] = {}
    for clave, numeros in _catalogo_por_bloque().items():
        if numeros != list(range(numeros[0], numeros[-1] + 1)):
            raise ValueError(f"las métricas del bloque {clave!r} no son contiguas en el catálogo: {numeros}")
        if clave not in _NOMBRES_DE_BLOQUE:
            raise ValueError(f"el bloque {clave!r} del catálogo no tiene nombre en _NOMBRES_DE_BLOQUE")
        bloques[clave] = (range(numeros[0], numeros[-1] + 1), _NOMBRES_DE_BLOQUE[clave])
    return bloques


BLOQUES: dict[str, tuple[range, str]] = _rangos_del_catalogo()


def metricas_no_disponibles_del_anio(anio: int | str) -> dict[int, str]:
    """Todas las métricas que no se pueden calcular para `anio`, con el
    motivo — juntando las tres razones posibles: falta una columna en
    Hogares, falta una columna en Empleo, o directamente no existe el
    archivo de ese módulo para el año."""
    disponibles = config.datos_disponibles(anio)
    motivos: dict[int, str] = {}

    for numero, faltantes in metricas_hogares_no_disponibles(anio).items():
        motivos[numero] = f"falta {', '.join(faltantes)} en los datos del INE"
    for numero, faltantes in metricas_empleo_no_disponibles(anio).items():
        motivos[numero] = f"falta {', '.join(faltantes)} en los datos del INE"

    for bloque, clave in (("fies", "fies"), ("empleo", "empleo"), ("seguridad", "seguridad")):
        if not disponibles[clave]:
            for numero in BLOQUES[bloque][0]:
                motivos.setdefault(numero, "el INE no publicó ese módulo para este año")

    # El índice de desarrollo territorial lleva la tasa de empleo como uno
    # de sus cuatro componentes desde la v0.10.0, así que sin datos de
    # Empleo tampoco se puede calcular (el caso real es 2019).
    if not disponibles["empleo"]:
        for numero in BLOQUES["territorio"][0]:
            motivos.setdefault(numero, "necesita datos de Empleo, que el INE no publicó para este año")

    return motivos


def bloques_disponibles(anio: int | str) -> dict:
    """Los argumentos que `formularios.plantilla_areas` necesita para no
    ofrecer un bloque que quedaría vacío. Un bloque está disponible si al
    menos una de sus métricas se puede calcular este año.

    Se usa así:

        formularios.plantilla_areas(**verificacion_catalogo.bloques_disponibles(anio))
    """
    sin_datos = metricas_no_disponibles_del_anio(anio)
    argumentos: dict = {}
    no_disponibles: dict[str, str] = {}

    for bloque, (numeros, nombre_visible) in BLOQUES.items():
        vivas = [n for n in numeros if n not in sin_datos]
        argumentos[f"{bloque}_disponible"] = bool(vivas)
        if not vivas:
            # Todas las métricas del bloque comparten motivo en la
            # práctica; se toma el del primero para no repetirlo siete veces.
            no_disponibles[nombre_visible] = sin_datos[numeros[0]]

    argumentos["no_disponibles"] = no_disponibles
    return argumentos
