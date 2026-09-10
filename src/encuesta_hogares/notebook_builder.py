"""Arma mecánicamente las celdas de markdown+código del notebook para las
43 métricas fijas del catálogo, para el año base elegido — reemplaza,
para esas métricas, la parte de paso 5 donde el modelo escribía ese
código a mano en cada corrida.

Nace de una medición real: de los ~10 minutos que tardaba el paso 5 en
una corrida con 13 métricas y comparación de 3 años, 7m11s eran el modelo
generando el texto del script — no cómputo. Ese texto es, para las 43
métricas del catálogo, siempre la misma llamada a la misma función ya
testeada (ver `verificacion_catalogo.MANIFEST`) con el mismo criterio de
agrupación: no hay nada que "pensar" ahí que valga la pena volver a
escribir cada vez.

**Qué NO cubre este módulo — a propósito:**

- Las métricas a medida que la persona propone en el paso 6 (campo libre
  del catálogo, o una pregunta nueva a mitad de conversación). Esas no
  tienen entrada en MANIFEST ni texto fijo acá; siguen escribiéndose con
  el mismo criterio de rigor de siempre, en código Python libre.
- **La comparación entre años.** Se probó mecanizarla acá (con dos
  helpers genéricos para el patrón dumbbell/serie), y en una corrida
  completa contra datos reales encontró dos bugs de verdad — variables de
  un año pisando las de otro, y "departamento" escrito distinto entre
  años haciendo que un cruce diera cero filas en vez de un error claro.
  Los dos ya están corregidos, pero decidido en conjunto con el dueño del
  proyecto: cruzar datos de años distintos es justo el tipo de tarea
  donde conviene que seguir teniendo a alguien (o algo) que note que un
  resultado no cierra y lo investigue, no una plantilla fija — así que la
  comparación entre años se sigue escribiendo en código libre, con el
  mismo criterio ya documentado en `docs/CONVENCIONES_DE_GRAFICAS.md`
  (2 años → `diferencia_entre_tablas` + `plot_dumbbell`; 3+ →
  `combinar_por_anio` + `plot_serie_por_anio`) y las reglas de
  `preprocessing.normalizar_departamento`/`analysis.tabla_a_dict` que
  quedaron de esa prueba — ambas funciones reales, con test, para que el
  camino libre tampoco tenga que reinventarlas.

Mezclar plantillas fijas y código libre en el mismo notebook es
intencional: cada celda de este módulo es indistinguible, en el `.ipynb`
final, de una escrita a mano — el criterio de calidad (pregunta guía en
markdown antes del código, gráfica con eje anclado en cero, sin prints
crudos) es el mismo para las dos.

Cada llamada a `analysis.py`/`preprocessing.py`/`visualization.py` de
acá está tomada, sin modificar el criterio, de
`tools/validar_con_datos_reales.py` (ya validada contra datos reales de
verdad) — nunca inventada para este módulo.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

from . import entrega, formularios, verificacion_catalogo


@dataclass
class Celda:
    """Un tramo del informe: markdown, después código, y opcionalmente más
    markdown DESPUÉS del código.

    `markdown_final` existe porque el orden del informe lo pide: desde la
    v0.13.0, la justificación académica de por qué se eligió ese tipo de
    gráfica va **después** de la gráfica, no antes. Antes se explicaba
    primero y se mostraba después, que es al revés de como se lee un
    informe: primero se ve el dato, después se entiende por qué está
    presentado así.

    `codigo` vacío es válido: sirve para tramos que son solo texto (la
    introducción, la presentación de un bloque, la nota metodológica).
    """

    markdown: str
    codigo: str = ""
    markdown_final: str = ""


# ============================================================================
# Preparación de datos: siempre las mismas variables, para el año base
# elegido — nada de comparación entre años acá (ver docstring del módulo).
# ============================================================================

# Prosa suelta, no un literal de Python: hasta la v0.13.0 este texto se
# inyectaba dentro de una celda de código, envuelto en `"""`, y por eso
# arrastraba las comillas y una primera línea de contexto. Ahora es markdown
# de la nota metodológica y nada más.
_TEXTO_PONDERADO = '''\
La Encuesta Continua de Hogares no encuesta a todos los hogares del país en la
misma proporción en que existen en la realidad — un departamento chico, por
ejemplo, puede terminar levemente sub o sobrerrepresentado en la muestra real
respecto a su peso real en la población. Para corregir eso, el INE le asigna a
cada hogar encuestado un 'ponderador': un factor que ajusta cuánto pesa ese
hogar al calcular un promedio o porcentaje, para que el resultado final
represente a toda la población, no solo a quienes quedaron en la muestra tal
cual. Es el mismo criterio que usa el propio INE en sus publicaciones
oficiales, no una decisión de este informe.'''


def celda_preparacion_datos(anio_base: int, incluir_fies: bool, incluir_empleo: bool = False) -> Celda:
    """La única celda que siempre se genera — infraestructura, no un bloque
    temático (ver docs/METODOLOGIA.md, sección 1). Envuelve la carga con
    `bitacora.medir("carga_de_datos")`, como indica el paso 5 del agente.

    `incluir_empleo`: los 12 archivos mensuales de Empleo se cargan acá,
    **una sola vez**, cuando alguna métrica del informe los necesita (las
    del bloque Empleo o las del índice territorial). Hasta la v0.13.6 cada
    consumidor se los cargaba por su cuenta: en un informe con las 42
    métricas, `load_empleo` corría cinco veces (una en la preparación del
    bloque Empleo, una por cada una de las tres métricas del índice
    territorial y otra en la comparación) — medido en la bitácora real,
    63 cargas territoriales en 25 corridas.
    """
    # El párrafo de "ponderado" estaba acá y era lo primero que veía el
    # lector del informe. Es metodología, no apertura: se mudó a
    # `celda_nota_metodologica()`, al final.
    markdown = (
        "## Preparación de datos\n\n"
        "Carga de los microdatos del INE y armado de las variables que usan "
        "las métricas de este informe."
    )
    fies_extra = ""
    if incluir_fies:
        fies_extra = '''
    if config.datos_disponibles(ANIO).get("fies"):
        fies_clasificado = preprocessing.prepare_fies(data_loader.load_fies(config.fies_file(ANIO)))
        fies_clasificado["quintil_ingreso"] = (
            fies_clasificado["quintil_ingreso"].astype("Int64").map(lambda q: f"Quintil {q}")
        )
    else:
        fies_clasificado = None'''

    codigo = f'''ANIO = {anio_base}

with bitacora.medir("carga_de_datos"):
    # Detección de formato general (no solo "es 2019 o no") - el mismo
    # patrón que ya usa tools/validar_con_datos_reales.py: hasta 2023 es
    # .sav (uno por año, sin nombre de archivo fijo), desde 2024 es el CSV
    # combinado.
    if config.hogares_csv_file(ANIO).exists():
        hogares, personas = data_loader.load_hogares_personas_csv(ANIO)
    else:
        carpeta = config.DATA_DIR / str(ANIO)
        hogares = data_loader.load_hogares(sorted(carpeta.glob("H_*.sav"))[0])
        personas = data_loader.load_personas(sorted(carpeta.glob("P_*.sav"))[0])
    hogares = preprocessing.normalizar_departamento(hogares)
    hogares_mdeo = preprocessing.prepare_hogares_montevideo(hogares)
    hogares_cond = preprocessing.decode_condiciones_vivienda(hogares)
    hogares_cond["pobre"] = hogares_cond["pobre"] == 1.0
    hogares_cond["nivel_economico"] = preprocessing.classify_nivel_economico(hogares_cond["estrato_tipo"])
    # El estrato socioeconómico del INE existe solo para Montevideo: en el
    # interior todos los hogares quedan «6-No Definido». Cualquier corte de
    # vivienda por nivel económico se hace sobre este marco, no sobre el país.
    hogares_cond_mdeo = hogares_cond.loc[hogares_cond["departamento"].str.upper() == "MONTEVIDEO"].copy()
    hogares_ext = preprocessing.prepare_hogares_extendido(hogares_mdeo)
    hogares_ext["calidad_conexion"] = preprocessing.clasificar_calidad_conexion(hogares_ext)
    tipo_hogar = preprocessing.clasificar_tipo_hogar(personas, hogares)
    hogares_ext_con_jefe = hogares_ext.merge(
        tipo_hogar[["id_hogar", "jefe_sexo", "jefe_edad"]], on="id_hogar", how="left"
    )
    hogares_ext_con_jefe["cohorte"] = preprocessing.compute_cohorte_generacional(hogares_ext_con_jefe, ANIO)
    hogares_ext_con_jefe["indice_acceso_digital"] = preprocessing.compute_indice_acceso_digital(hogares_ext_con_jefe)
    hogares_mdeo_hacinamiento = preprocessing.compute_hacinamiento(hogares_mdeo)
    personas_con_depto = preprocessing.merge_personas(hogares, personas){fies_extra}

nota(f"Hogares en todo el país: {{_res.fmt(len(hogares), 0)}}",
     f"Hogares de Montevideo: {{_res.fmt(len(hogares_mdeo), 0)}}")'''
    if incluir_empleo:
        codigo += '''

with bitacora.medir("carga_de_datos_empleo"):
    empleo_prep = preprocessing.prepare_empleo(data_loader.load_empleo(ANIO))
nota(f"Registros de Empleo (12 meses): {_res.fmt(len(empleo_prep), 0)}")'''
    return Celda(markdown=markdown, codigo=codigo)


def celda_preparacion_empleo(anio_base: int) -> Celda:
    """Solo se genera si se eligió el bloque Empleo — procesar los 12
    meses es bastante más pesado que el resto (ver paso 3.5 del agente),
    por eso queda en su propia celda, separada de Preparación de datos."""
    # `empleo_prep` ya lo cargó la preparación general (una sola vez para
    # todo el informe): acá solo se derivan las vistas que usan las métricas.
    codigo = '''ocupados = empleo_prep[empleo_prep["condicion_actividad"] == "Ocupados"].copy()
activos = empleo_prep[empleo_prep["condicion_actividad"].isin(["Ocupados", "Desocupados"])].copy()
activos["es_desocupado"] = activos["condicion_actividad"] == "Desocupados"

meses_cubiertos = sorted(int(m) for m in empleo_prep["mes"].unique())
nota(f"Meses de Empleo cubiertos: {len(meses_cubiertos)}")'''
    # `###`, no `##`: cuelga del "## Empleo" que abre el tema, igual que las
    # métricas. Y sin repetir "Empleo" en el título, que ya está arriba.
    return Celda(markdown="### Preparación de los datos de este tema", codigo=codigo)


def celda_preparacion_seguridad(anio_base: int) -> Celda:
    """Solo se genera si se eligió el bloque Seguridad y Victimización."""
    codigo = '''with bitacora.medir("carga_de_datos_seguridad"):
    victimizacion_prep = preprocessing.prepare_victimizacion(data_loader.load_victimizacion(ANIO))
    victimizacion_largo = preprocessing.melt_delitos(victimizacion_prep)
    victimizados = victimizacion_largo[victimizacion_largo["victimizado"]]

nota(f"Personas por tipo de delito: {_res.fmt(len(victimizacion_largo), 0)}")'''
    return Celda(markdown="### Preparación de los datos de este tema", codigo=codigo)


# ============================================================================
# Texto fijo por métrica: reusa, sin reescribirlo, el título y la
# explicación que ya redactó `formularios.py` para el catálogo — la
# persona ya los vio al elegir la métrica, así que el informe usa las
# mismas palabras en vez de una segunda redacción que podría no coincidir.
# A propósito NO varía entre corridas ni entre personas: dos informes con
# la misma métrica elegida tienen que traer el mismo texto — confirmado
# explícitamente como lo deseado (si alguien quiere algo distinto, está
# el campo de propuesta libre del paso 4, que sigue yendo por el camino
# de redacción libre del paso 6).
# ============================================================================

def _texto_catalogo() -> dict[int, tuple[str, str]]:
    resultado: dict[int, tuple[str, str]] = {}
    for _clave, (_titulo_bloque, _nota, metricas) in formularios._CATEGORIAS_METRICAS.items():
        for numero, titulo, descripcion in metricas:
            resultado[numero] = (titulo, descripcion)
    for _titulo_bloque, _nota, metricas in (
        formularios._CATEGORIA_FIES,
        formularios._CATEGORIA_EMPLEO,
        formularios._CATEGORIA_SEGURIDAD,
    ):
        for numero, titulo, descripcion in metricas:
            resultado[numero] = (titulo, descripcion)
    return resultado


_TEXTO_CATALOGO = _texto_catalogo()

# Justificación fija del tipo de gráfica, por familia — no por métrica
# (la misma familia de gráfica se justifica siempre igual, ver
# docs/CONVENCIONES_DE_GRAFICAS.md). Ninguna de estas frases es nueva:
# son las mismas razones ya documentadas ahí, solo que ahora quedan
# escritas una vez acá en vez de que el modelo las redacte de nuevo en
# cada corrida.
_JUSTIFICACION_POR_FAMILIA = {
    "barras": "Barras, para comparar magnitudes entre categorías (Cleveland & McGill, 1984).",
    "barras_h": (
        "Barras horizontales, para que las categorías se lean sin inclinar "
        "la cabeza (Cleveland & McGill, 1984)."
    ),
    "barras_100": (
        "Barras 100% apiladas, para mostrar la composición completa de cada "
        "grupo en una sola barra cuando las partes suman exactamente 100% "
        "(Wilke, *Fundamentals of Data Visualization*, cap. proporciones)."
    ),
    "dumbbell": (
        "Gráfico de dos puntos conectados (dumbbell), para comparar dos grupos "
        "conservando el valor real de cada uno, no solo la diferencia entre "
        "ambos (Tufte; Knaflic, storytellingwithdata.com)."
    ),
    "heatmap": (
        "Heatmap, para cruzar dos variables categóricas cuando importa la "
        "magnitud relativa de la concentración y no el valor exacto de cada "
        "celda: por el principio Gestalt de similitud, las celdas de color "
        "parecido se agrupan solas a la vista (Ware, *Information "
        "Visualization: Perception for Design*)."
    ),
}

# Toda familia lleva su cita: el hook
# `.claude/hooks/_lib_check_notebook_metrica_sin_grafica_o_cita.cjs` bloquea la
# ejecución del notebook si alguna métrica no la tiene. "barras_100" y
# "heatmap" salieron sin cita hasta la v0.13.0 — el hook no las detectaba
# porque buscaba un formato de encabezado que este módulo ya no emite, así
# que nunca las miró. Las citas estaban desde antes en
# `docs/CONVENCIONES_DE_GRAFICAS.md`; lo que faltaba era traerlas acá.


# ============================================================================
# Glosario de terminos, para que toda metrica explique su jerga.
#
# Nace de un problema real encontrado por el dueno del proyecto leyendo un
# informe generado: las metricas de Empleo traian la formula del INE de
# "tasa de actividad/empleo/desempleo" y otras metricas no explicaban nada.
# La diferencia no era una decision: esas definiciones las escribia el
# modelo a mano durante la corrida, asi que aparecian o no segun se
# acordara. Igual que con los hooks y con el panorama de TV cable, una
# regla que depende de que el modelo se acuerde no se cumple pareja - por
# eso ahora el glosario es fijo y se arma solo.
#
# Cada definicion describe **lo que de verdad calcula este proyecto**
# (verificable contra analysis.py/preprocessing.py), siguiendo el criterio
# del INE. No se transcriben textos oficiales que no esten verificados.
# ============================================================================

_GLOSARIO = {
    "condicion_actividad": (
        "**Condición de actividad**: el INE clasifica a cada persona de 14 años o más como "
        "*ocupada* (trabajó en el período de referencia), *desocupada* (no trabajó, buscó "
        "trabajo y estaba disponible) o *inactiva* (ni trabaja ni busca). Los menores de 14 "
        "años quedan fuera de todo este bloque."
    ),
    "tasa_actividad": (
        "**Tasa de actividad** = (ocupados + desocupados) ÷ población de 14 años o más × 100. "
        "Qué parte de la población en edad de trabajar está en el mercado laboral, sea "
        "trabajando o buscando."
    ),
    "tasa_empleo": (
        "**Tasa de empleo** = ocupados ÷ población de 14 años o más × 100."
    ),
    "tasa_desempleo": (
        "**Tasa de desempleo** = desocupados ÷ (ocupados + desocupados) × 100. El denominador "
        "es la población *activa*, no la población total: por eso un 8% de desempleo **no** "
        "significa que el 8% de la gente no tenga trabajo, sino el 8% de quienes están "
        "trabajando o buscando."
    ),
    "informalidad": (
        "**Informalidad**: se considera informal a la persona ocupada que no aporta a la "
        "seguridad social por ese trabajo. Es el criterio estándar en la región y el mismo que "
        "usa el paquete oficial de R del INE para la ECH."
    ),
    "sector_formalidad": (
        "**Sector formal, informal y hogares**: clasifica la unidad económica donde trabaja "
        "la persona, según el marco de la OIT (17.ª CIET, 2003): *formal* (empresas y "
        "organismos registrados), *informal* (unidades productivas no registradas) y "
        "*hogares* (trabajo doméstico remunerado en hogares particulares). No es lo mismo que "
        "la informalidad de la persona, que mira si aporta a la seguridad social."
    ),
    "subempleo": (
        "**Subempleo**: personas ocupadas que trabajan menos horas de las que querrían y están "
        "disponibles para trabajar más."
    ),
    "pobreza": (
        "**Pobreza e indigencia**: clasificación que ya viene calculada por el INE, no estimada "
        "acá. Un hogar es *pobre* si su ingreso no alcanza la línea de pobreza (el costo de una "
        "canasta básica alimentaria y no alimentaria) para su composición, e *indigente* si no "
        "alcanza siquiera la canasta alimentaria."
    ),
    "nivel_economico": (
        "**Nivel económico**: agrupación del estrato socioeconómico que asigna el INE a cada "
        "hogar, de 1 (más bajo) a 5 (más alto). El INE lo define solo para Montevideo, así "
        "que toda comparación por nivel económico de este informe se calcula sobre los "
        "hogares de Montevideo."
    ),
    "hacinamiento": (
        "**Hacinamiento**: hogares con más de 2 personas por habitación."
    ),
    "jefe_hogar": (
        "**Jefe/a de hogar**: la persona que los propios integrantes del hogar reconocen como "
        "tal al responder la encuesta — no la determina el INE por ingreso ni por edad."
    ),
    "tipos_hogar": (
        "**Tipos de hogar** (taxonomía CELADE/CEPAL): *unipersonal* (una sola persona), "
        "*nuclear* (pareja y/o hijos), *extendido* (núcleo más otros parientes), *compuesto* "
        "(incluye personas sin parentesco) y *sin núcleo* (parientes sin pareja ni hijos)."
    ),
    "razon_dependencia": (
        "**Razón de dependencia demográfica** = personas menores de 15 más mayores de 65, "
        "dividido por las de 15 a 64, × 100. Cuántas personas en edades potencialmente "
        "dependientes hay por cada 100 en edad activa."
    ),
    "carencia_estructural": (
        "**Carencia estructural de la vivienda**: la vivienda tiene al menos uno de los "
        "problemas que releva el INE (humedad, goteras, grietas, riesgo de derrumbe, etc.). "
        "Basta una para contarla como deficitaria — el mismo criterio de conteo de carencias "
        "que usa el INE para NBI-vivienda. Qué problemas se relevan cambia según el año."
    ),
    "tecnologias": (
        "**Tecnologías del hogar**: tener conexión a internet, computadora y servicios de "
        "streaming. Son variables del hogar, no de cada persona."
    ),
    "calidad_conexion": (
        "**Calidad de la conexión**: no solo tener o no tener internet, sino cómo. *Banda ancha "
        "fija* (conexión del hogar), *solo móvil* (únicamente por datos de celular) o *sin "
        "conexión*. Si el hogar tiene las dos, cuenta como banda ancha fija."
    ),
    "indice_acceso_digital": (
        "**Índice de acceso digital**: puntaje de 0 a 3 según cuántas de las tres tecnologías "
        "tiene el hogar (internet, computadora, streaming). Es un conteo simple, inspirado en "
        "el enfoque de canasta digital básica de CEPAL."
    ),
    "cohorte": (
        "**Cohorte generacional**: agrupa a los hogares según el año de nacimiento del jefe/a "
        "(baby boomers, generación X, millennials, etc.), calculado sobre el año de la encuesta."
    ),
    "indice_territorial": (
        "**Índice de desarrollo territorial**: combina pobreza, empleo, precariedad de vivienda "
        "y nivel económico en un puntaje de 0 a 1 por departamento, normalizando cada componente "
        "e invirtiendo los negativos para que más alto siempre signifique mejor. Es una medida "
        "del departamento, nunca de un hogar puntual."
    ),
    "fies": (
        "**Inseguridad alimentaria (escala FIES de FAO)**: se construye con preguntas sobre "
        "haber tenido que saltear comidas o reducirlas por falta de dinero. *Moderada* implica "
        "haber comprometido la calidad o la cantidad de la comida; *severa*, haber pasado hambre."
    ),
    "quintil": (
        "**Quintil de ingreso**: los hogares ordenados por ingreso y partidos en cinco grupos "
        "iguales. El quintil 1 es el 20% de menor ingreso y el 5 el 20% de mayor."
    ),
    "victimizacion": (
        "**Victimización**: haber sufrido un delito en el mes anterior a la entrevista. Es una "
        "cifra mensual, no anual."
    ),
    "comunicacion_policia": (
        "**Comunicación a la policía**: haber avisado a la policía de cualquier modo, sin que "
        "eso implique una denuncia formal."
    ),
    "denuncia_formal": (
        "**Denuncia formal**: haber hecho la denuncia presencial en la comisaría. Es un "
        "subconjunto de quienes se comunicaron con la policía."
    ),
}

# numero de metrica -> terminos que usa. Toda metrica del catalogo tiene
# entrada; `test_toda_metrica_del_catalogo_explica_sus_terminos` lo hace
# cumplir, asi que una metrica nueva no puede quedarse sin glosario.
_TERMINOS_POR_METRICA = {
    1: ("tecnologias", "nivel_economico"),
    2: ("tecnologias", "cohorte"),
    3: ("calidad_conexion", "nivel_economico"),
    4: ("tecnologias", "jefe_hogar"),
    5: ("indice_acceso_digital", "nivel_economico"),
    6: ("jefe_hogar",),
    7: ("pobreza",),
    8: ("jefe_hogar", "pobreza"),
    9: ("hacinamiento", "nivel_economico"),
    10: ("tipos_hogar",),
    11: ("razon_dependencia",),
    12: ("tipos_hogar",),
    13: ("indice_territorial",),
    14: ("indice_territorial",),
    15: ("indice_territorial",),
    16: ("carencia_estructural",),
    17: ("carencia_estructural", "nivel_economico"),
    18: ("carencia_estructural",),
    19: ("carencia_estructural", "nivel_economico"),
    20: ("carencia_estructural",),
    21: ("fies",),
    22: ("fies", "quintil"),
    23: ("fies",),
    24: ("fies", "quintil"),
    25: ("fies", "quintil"),
    26: ("fies",),
    27: ("fies",),
    28: ("condicion_actividad", "tasa_actividad", "tasa_empleo", "tasa_desempleo"),
    29: ("tasa_actividad", "tasa_empleo", "tasa_desempleo"),
    30: ("tasa_desempleo",),
    31: ("informalidad",),
    32: ("informalidad",),
    33: ("subempleo",),
    34: ("condicion_actividad", "tasa_desempleo"),
    35: ("sector_formalidad",),
    36: ("victimizacion",),
    37: ("victimizacion",),
    38: ("victimizacion",),
    39: ("victimizacion", "comunicacion_policia"),
    40: ("victimizacion", "denuncia_formal"),
    41: ("comunicacion_policia", "denuncia_formal"),
    42: ("victimizacion",),
}


def terminos_de_bloque(metricas_elegidas: list[int] | set[int]) -> dict[str, list[str]]:
    """Qué términos corresponden a la presentación de cada bloque, según
    las métricas que la persona **eligió de verdad** en esta corrida.

    Un término es "de bloque" si lo usa más de una de las métricas
    elegidas de ese bloque: explicarlo una vez arriba y no repetirlo en
    cada métrica. Si solo lo usa una, se queda en su métrica.

    Es dinámico y no fijo por catálogo (decisión del dueño del proyecto):
    quien elige una sola métrica de Territorio no tiene por qué leer el
    índice explicado en una sección aparte, y quien elige las tres no
    tiene por qué leerlo tres veces. Sigue siendo 100% mecánico — lo
    calcula esta función, no el modelo.

    Un término que cruza bloques (nivel económico y jefe/a de hogar
    aparecen en Brecha Digital y también en Hogares/Vivienda) se **repite**
    en cada bloque que lo use, también por decisión del dueño: así cada
    bloque se lee solo, sin tener que ir a buscar una definición a otra
    sección.
    """

    elegidas = set(metricas_elegidas)
    resultado: dict[str, list[str]] = {}
    for bloque, (numeros, _nombre) in verificacion_catalogo.BLOQUES.items():
        del_bloque = [n for n in numeros if n in elegidas]
        cuenta: dict[str, int] = {}
        for numero in del_bloque:
            for termino in _TERMINOS_POR_METRICA.get(numero, ()):
                cuenta[termino] = cuenta.get(termino, 0) + 1
        compartidos = [t for t, veces in cuenta.items() if veces > 1]
        if compartidos:
            # Orden estable: el del glosario, no el de aparición.
            resultado[bloque] = [t for t in _GLOSARIO if t in compartidos]
    return resultado


def _bloque_de(numero: int) -> str:

    for bloque, (numeros, _nombre) in verificacion_catalogo.BLOQUES.items():
        if numero in numeros:
            return bloque
    return ""


def _markdown(numero: int, terminos_ya_explicados: set[str] | None = None) -> str:
    """Partes a, b y c de la métrica: nombre, la pregunta que responde y
    los términos **propios** de esta métrica.

    Los términos que ya explicó la presentación del bloque no se repiten
    acá (`terminos_ya_explicados`), y si no queda ninguno propio, la
    sección de términos directamente no aparece — no se deja un título
    vacío.
    """
    titulo, descripcion = _TEXTO_CATALOGO[numero]
    ya = terminos_ya_explicados or set()
    propios = [t for t in _TERMINOS_POR_METRICA[numero] if t not in ya]

    partes = [f"### {numero}. {titulo}", f"**¿Qué pregunta responde?** {descripcion}"]
    if propios:
        detalle = "\n".join(f"- {_GLOSARIO[t]}" for t in propios)
        partes.append(f"**Qué significa cada término (criterio del INE):**\n{detalle}")
    return "\n\n".join(partes)


def _markdown_justificacion(familia_grafica: str) -> str:
    """Parte e: por qué esta gráfica, con la referencia bibliográfica.

    Va DESPUÉS de la gráfica (parte d) y no antes: primero se ve el dato,
    después se entiende por qué está presentado así.
    """
    return f"*Por qué esta gráfica: {_JUSTIFICACION_POR_FAMILIA[familia_grafica]}*"


# ============================================================================
# Estructura del informe: introduccion, presentacion de cada bloque y nota
# metodologica.
#
# Nace de una revision del dueño del proyecto leyendo un informe generado.
# Tres problemas, todos de estructura y no de calculo:
#
# 1. No habia introduccion. Lo primero que veia el lector era "Preparacion
#    de datos" con el parrafo que explica que significa "ponderado" - una
#    explicacion metodologica, no una apertura. Y como no habia ninguna
#    introduccion mecanizada, la que apareciera la escribia el modelo, asi
#    que cambiaba de una corrida a otra.
# 2. No habia estructura por bloque. Las metricas salian como una lista
#    plana en el orden en que la persona las habia elegido: la 1, la 8, la
#    22 y la 28 una detras de otra, sin nada que dijera a que tema
#    pertenecia cada una.
# 3. Los terminos se repetian. "Indice de desarrollo territorial" se
#    explicaba igual en las tres metricas de Territorio; FIES, en las
#    siete de Seguridad alimentaria.
# ============================================================================

_PRESENTACION_BLOQUE = {
    "brecha_digital": (
        "Qué tan conectados están los hogares y quiénes quedan afuera. No alcanza con "
        "contar cuántos tienen internet: el bloque mira también la calidad de esa "
        "conexión y cómo cambia el acceso según el nivel económico, la generación del "
        "jefe o jefa de hogar y el equipamiento disponible. Se calcula sobre Montevideo."
    ),
    "hogares": (
        "Cómo están compuestos los hogares y en qué condiciones viven. Reúne pobreza e "
        "indigencia, quién encabeza el hogar, cuántas personas conviven por habitación y "
        "qué proporción de la población depende económicamente del resto."
    ),
    "territorio": (
        "Cómo se compara el desarrollo entre los 19 departamentos. En vez de repetir una "
        "misma tasa cortada por departamento, este bloque combina varias dimensiones en "
        "un único indicador comparable, y después abre ese indicador para mostrar qué "
        "dimensión explica que un departamento quede arriba o abajo."
    ),
    "vivienda": (
        "En qué estado están las viviendas. Se releva un conjunto de problemas "
        "estructurales (humedad, goteras, grietas, riesgo de derrumbe) y se mira cuántos "
        "hogares tienen al menos uno, y si esa carga se reparte parejo entre departamentos "
        "y, dentro de Montevideo, entre niveles económicos. Qué problemas se preguntan "
        "cambia según el año."
    ),
    "fies": (
        "Si los hogares tuvieron dificultades para acceder a alimentos por falta de "
        "dinero. Se mide con una escala internacional de la FAO, sobre una submuestra de "
        "hogares y no sobre todos los encuestados, y se compara entre niveles de ingreso, "
        "regiones y hogares con y sin menores a cargo."
    ),
    "empleo": (
        "La situación laboral del año. El INE releva empleo todos los meses, así que cada "
        "número de este bloque es el promedio de los 12 meses: se calcula el valor de cada "
        "mes por separado y después se promedian, de modo que ningún mes pesa más que "
        "otro. No es una foto de un mes suelto ni una medición única de todo el año."
    ),
    "seguridad": (
        "Qué delitos sufrieron las personas y qué hicieron después. **Todas las preguntas "
        "de este bloque se refieren al mes anterior a la entrevista, no al año entero**: "
        "si un número dice 5%, significa que el 5% sufrió ese delito en un solo mes. No "
        "se puede leer como una cifra anual ni compararlo con estadísticas anuales de "
        "otras fuentes."
    ),
}


def celda_introduccion(anio_base: int, metricas: list[int], bloques: list[str]) -> Celda:
    """Apertura del informe: qué se analizó, de dónde salen los datos y qué
    contiene. Fija y mecanizada, para que no cambie de una corrida a otra.

    La explicación de "ponderado" **no** va acá: es metodología, y vive en
    `celda_nota_metodologica()`, al final. Acá solo queda la advertencia de
    una línea, para que quien lea un porcentaje sepa dónde buscar el detalle.
    """

    nombres = [verificacion_catalogo.BLOQUES[b][1] for b in bloques if b in verificacion_catalogo.BLOQUES]
    listado = "\n".join(f"- {nombre}" for nombre in nombres)
    cuantas = len(metricas)
    plural = "s" if cuantas != 1 else ""
    return Celda(
        markdown=(
            f"# Encuesta Continua de Hogares — Informe {anio_base}\n\n"
            f"Este informe analiza los microdatos de la **Encuesta Continua de Hogares "
            f"(ECH) {anio_base}** del Instituto Nacional de Estadística (INE) de Uruguay, "
            f"la fuente oficial sobre condiciones de vida de los hogares del país.\n\n"
            f"Incluye **{cuantas} métrica{plural}** distribuida{plural} en los siguientes "
            f"temas:\n\n{listado}\n\n"
            f"Cada tema se presenta con una explicación de qué mide y de los términos "
            f"técnicos que usa, según el criterio del INE. Cada métrica indica qué "
            f"pregunta responde, muestra su gráfica y explica por qué se eligió ese tipo "
            f"de gráfica.\n\n"
            f"> Todos los porcentajes de este informe están **ponderados** por el factor "
            f"de expansión del INE, para que representen a toda la población y no solo a "
            f"los hogares encuestados. El detalle está en la nota metodológica del final."
        )
    )


def celda_presentacion_bloque(bloque: str, terminos: list[str]) -> Celda:
    """Presentación de un bloque: su nombre, qué mide, y los términos del
    INE que van a aparecer en varias de sus métricas.

    `terminos` viene de `terminos_de_bloque()`, que los calcula según lo que
    la persona eligió: acá van los que usa más de una métrica del bloque, y
    los que usa una sola se quedan en esa métrica.
    """

    _numeros, nombre = verificacion_catalogo.BLOQUES[bloque]
    partes = [f"## {nombre}", _PRESENTACION_BLOQUE[bloque]]
    if terminos:
        detalle = "\n".join(f"- {_GLOSARIO[t]}" for t in terminos)
        partes.append(
            "**Términos que aparecen en varias métricas de este tema "
            f"(criterio del INE):**\n{detalle}"
        )
    return Celda(markdown="\n\n".join(partes))


def celda_nota_metodologica() -> Celda:
    """Cierre del informe: la explicación de "ponderado".

    Estaba al principio, dentro de "Preparación de datos", y es lo primero
    que veía el lector. Es metodología: su lugar es el final, que es donde
    la busca quien la necesita.
    """
    return Celda(
        markdown=(
            "## Nota metodológica\n\n"
            "**Qué significa que un porcentaje esté \"ponderado\".** "
            "La palabra aparece en casi todos los porcentajes de este informe. "
            + _TEXTO_PONDERADO.strip()
        )
    )


# ============================================================================
# Generadores por métrica (1-43), año base únicamente. El número de cada
# función es el número del catálogo — ver `verificacion_catalogo.MANIFEST`
# para qué función de analysis.py/visualization.py implementa cada una
# (la fuente de verdad de esa asociación es esa, no este módulo).
# ============================================================================

def _m1() -> Celda:
    codigo = (
        "brecha_nivel_economico = analysis.brecha_digital_por_nivel_economico(hogares_ext)\n"
        "fig = viz.plot_brecha_digital(brecha_nivel_economico)\nfig.show()"
    )
    return Celda(_markdown(1), codigo, _markdown_justificacion("barras"))


def _m2() -> Celda:
    codigo = (
        "brecha_cohorte = analysis.brecha_digital_por_cohorte(hogares_ext_con_jefe)\n"
        "fig = viz.plot_brecha_digital_por_cohorte(brecha_cohorte)\nfig.show()"
    )
    return Celda(_markdown(2), codigo, _markdown_justificacion("barras"))


def _m3() -> Celda:
    codigo = (
        'calidad_nivel_economico = analysis.calidad_conexion_por(hogares_ext, "nivel_economico")\n'
        'fig = viz.plot_calidad_conexion_por(calidad_nivel_economico, "nivel económico")\nfig.show()'
    )
    return Celda(_markdown(3), codigo, _markdown_justificacion("barras_100"))


def _m4() -> Celda:
    codigo = (
        "brecha_jefatura = analysis.brecha_digital_por_jefatura(hogares_ext_con_jefe)\n"
        "fig = viz.plot_brecha_digital_por_jefatura(brecha_jefatura)\nfig.show()"
    )
    return Celda(_markdown(4), codigo, _markdown_justificacion("barras"))


def _m5() -> Celda:
    codigo = (
        'indice_acceso_nivel = analysis.indice_acceso_digital_por(hogares_ext_con_jefe, "nivel_economico")\n'
        'fig = viz.plot_indice_acceso_digital_por(indice_acceso_nivel, "nivel económico")\nfig.show()'
    )
    return Celda(_markdown(5), codigo, _markdown_justificacion("barras"))


def _m6() -> Celda:
    codigo = (
        "# El Plan Ibirapitá entrega tablets a personas mayores, y la pregunta de\n"
        "# esta métrica es sobre esos hogares: se filtra a los que tienen jefe/a de\n"
        "# 65 años o más antes de calcular, para que el porcentaje sea sobre la\n"
        "# población a la que el programa está dirigido.\n"
        'hogares_jefe_mayor = hogares_ext_con_jefe[hogares_ext_con_jefe["jefe_edad"] >= 65]\n'
        'adopcion_tablet_nivel = analysis.adopcion_tablet_ibirapita_por(hogares_jefe_mayor, "nivel_economico")\n'
        'fig = viz.plot_adopcion_tablet_ibirapita(adopcion_tablet_nivel, "nivel económico")\nfig.show()'
    )
    return Celda(_markdown(6), codigo, _markdown_justificacion("barras"))


def _m7() -> Celda:
    codigo = (
        "pobreza = analysis.pct_pobres_indigentes(hogares_ext)\n"
        "fig = viz.plot_pct_pobres_indigentes(pobreza)\nfig.show()"
    )
    return Celda(_markdown(7), codigo, _markdown_justificacion("barras_h"))


def _m8() -> Celda:
    codigo = (
        "jefatura = analysis.tasa_jefatura_femenina(tipo_hogar)\n"
        "fig = viz.plot_tasa_jefatura_femenina(jefatura)\nfig.show()"
    )
    return Celda(_markdown(8), codigo, _markdown_justificacion("barras_h"))


def _m9() -> Celda:
    codigo = (
        'chicos_hacinamiento_nivel = analysis.grupos_con_muestra_chica(hogares_mdeo_hacinamiento, "nivel_economico")\n'
        "if len(chicos_hacinamiento_nivel):\n"
        '    nota("Niveles económicos con menos de 30 casos en la muestra (estimación poco confiable): "\n'
        '         + ", ".join(f"{nivel} ({n} casos)" for nivel, n in chicos_hacinamiento_nivel.items()))\n\n'
        'hacinamiento_nivel = analysis.pct_hacinamiento_por(hogares_mdeo_hacinamiento, "nivel_economico")\n'
        'fig = viz.plot_hacinamiento_por(hacinamiento_nivel, "nivel económico")\nfig.show()'
    )
    return Celda(_markdown(9), codigo, _markdown_justificacion("barras"))


def _m10() -> Celda:
    codigo = (
        "tipos_hogar_resumen = analysis.tipos_hogar_resumen(tipo_hogar)\n"
        "fig = viz.plot_tipos_hogar(tipos_hogar_resumen)\nfig.show()"
    )
    return Celda(_markdown(10), codigo, _markdown_justificacion("barras_h"))


def _m11() -> Celda:
    codigo = (
        'chicos_depto_dependencia = analysis.grupos_con_muestra_chica(personas_con_depto, "departamento")\n'
        "if len(chicos_depto_dependencia):\n"
        '    nota("Departamentos con menos de 30 casos en la muestra (estimación poco confiable): "\n'
        '         + ", ".join(f"{depto} ({n} casos)" for depto, n in chicos_depto_dependencia.items()))\n\n'
        'dependencia_depto = analysis.razon_dependencia_por(personas_con_depto, "departamento")\n'
        'fig = viz.plot_razon_dependencia_por(dependencia_depto, "departamento")\nfig.show()'
    )
    return Celda(_markdown(11), codigo, _markdown_justificacion("barras_h"))


def _m12() -> Celda:
    codigo = (
        "unipersonales_mayores = analysis.pct_unipersonales_mayores(tipo_hogar)\n"
        "fig = viz.plot_pct_unipersonales_mayores(unipersonales_mayores)\nfig.show()"
    )
    return Celda(_markdown(12), codigo, _markdown_justificacion("barras_h"))


# Los CUATRO componentes del indice de desarrollo territorial.
#
# Empleo se sumo en la version 0.10.0: hasta entonces el catalogo y el
# glosario decian que el indice combinaba "pobreza, empleo, precariedad de
# vivienda y nivel economico", pero el calculo usaba solo tres - empleo no
# estaba. Lo encontro el dueño del proyecto mirando el heatmap del perfil
# territorial, que mostraba tres columnas donde el texto prometia cuatro.
# Se eligio agregar el componente que faltaba, y no corregir el texto,
# porque la definicion con empleo es la que se queria (y es la que usa el
# IDERE-UY, el antecedente que este proyecto cita para Uruguay).
#
# Se usa la TASA DE EMPLEO y no la de desempleo a proposito: es el
# indicador en positivo (mas alto = mejor), asi no hay que invertirlo y
# queda alineado con el resto de la escala del indice.
#
# `normalizar_departamento` sobre el empleo NO es opcional: los archivos
# de Empleo traen el departamento como "Artigas" y los de Hogares como
# "ARTIGAS". Verificado contra los datos reales de 2025: sin normalizar,
# de 19 departamentos coinciden 0, y el `.dropna()` de abajo dejaria el
# indice COMPLETAMENTE VACIO en silencio, sin ningun error. Es exactamente
# el modo de falla que documenta `preprocessing.normalizar_departamento`.
#
# `empleo_prep` lo carga la preparación general del informe cuando alguna
# métrica del índice está elegida (ver `celda_preparacion_datos`), así que
# acá no se vuelve a leer ningún archivo. Y este código corre UNA vez, en
# la apertura del bloque Territorio (`celda_preparacion_territorio`), no
# repetido dentro de cada una de las métricas 13, 14 y 15 como hasta la
# v0.13.6 — eso triplicaba la carga de los 12 archivos de Empleo y el
# cálculo del índice en el mismo informe.
_COMPONENTES_TERRITORIO = (
    'pobreza_depto = analysis.pct_pobres_por(hogares_cond, "departamento").set_index("departamento")\n'
    'estrato_depto = analysis.estrato_promedio_por(hogares, "departamento").set_index("departamento")\n'
    'precariedad_depto = analysis.precariedad_estructural_por(hogares_cond, "departamento").set_index("departamento")\n'
    "empleo_territorial = preprocessing.normalizar_departamento(empleo_prep)\n"
    'empleo_depto = analysis.tasas_actividad_empleo_desempleo_por(empleo_territorial, "departamento").set_index("departamento")\n'
    "componentes_territorio = pd.DataFrame({\n"
    '    "Pobreza": pobreza_depto["pct_pobres"],\n'
    '    "Precariedad de vivienda": precariedad_depto["pct_precariedad"],\n'
    '    "Empleo": empleo_depto["tasa_empleo"],\n'
    '    "Nivel económico": estrato_depto["estrato_promedio"],\n'
    "}).dropna()\n"
    "assert len(componentes_territorio) > 1, (\n"
    '    "El indice territorial quedo con %d departamentos: casi seguro que el cruce "\n'
    '    "por departamento no coincidio entre fuentes." % len(componentes_territorio)\n'
    ")\n"
    'indice_territorial = analysis.indice_desarrollo_territorial(\n'
    '    componentes_territorio, invertir=["Pobreza", "Precariedad de vivienda"]\n'
    ")\n"
    # Sin esta nota, el encabezado "Preparación de los datos de este tema"
    # quedaba vacío en el informe sin código (visto por el dueño en una
    # corrida real): la celda calcula pero no muestra nada.
    'nota(f"Índice de desarrollo territorial calculado para {len(indice_territorial)} departamentos a partir de "\n'
    '     "cuatro componentes: pobreza, precariedad de vivienda, empleo y nivel económico "\n'
    '     "(los dos primeros invertidos, para que un valor más alto sea siempre mejor).")'
)


def celda_preparacion_territorio() -> Celda:
    """Abre el bloque Territorio: calcula los cuatro componentes y el
    índice una sola vez; las métricas 13, 14 y 15 solo lo grafican."""
    return Celda(markdown="### Preparación de los datos de este tema", codigo=_COMPONENTES_TERRITORIO)


def _m13() -> Celda:
    codigo = "fig = viz.plot_indice_desarrollo_territorial(indice_territorial)\nfig.show()"
    return Celda(_markdown(13), codigo, _markdown_justificacion("barras_h"))


def _m14() -> Celda:
    codigo = "fig = viz.plot_perfil_territorial(indice_territorial)"
    return Celda(_markdown(14), codigo, _markdown_justificacion("heatmap"))


def _m15() -> Celda:
    codigo = (
        'mejor_depto = indice_territorial.index[0]\n'
        'peor_depto = indice_territorial.index[-1]\n'
        'brecha_territorial = indice_territorial.loc[mejor_depto, "indice"] - indice_territorial.loc[peor_depto, "indice"]\n'
        'nota(f"Brecha territorial: {_res.etiqueta(mejor_depto)} ({_res.fmt(indice_territorial.loc[mejor_depto, \'indice\'], 2)}) frente a '
        '{_res.etiqueta(peor_depto)} ({_res.fmt(indice_territorial.loc[peor_depto, \'indice\'], 2)}) — diferencia de {_res.fmt(brecha_territorial, 2)}")\n\n'
        "fig = viz.plot_dumbbell(\n"
        '    categorias=["Índice de desarrollo territorial"],\n'
        '    valores_a=[indice_territorial.loc[mejor_depto, "indice"]],\n'
        '    valores_b=[indice_territorial.loc[peor_depto, "indice"]],\n'
        "    nombre_a=mejor_depto, nombre_b=peor_depto,\n"
        '    titulo="Brecha territorial: mejor vs. peor departamento", xlabel="Índice (0 a 1)",\n'
        ")\nfig.show()"
    )
    return Celda(_markdown(15), codigo, _markdown_justificacion("dumbbell"))


def _m16() -> Celda:
    codigo = (
        "precariedad = analysis.precariedad_estructural(hogares_cond)\n"
        "fig = viz.plot_precariedad_estructural(precariedad)\nfig.show()"
    )
    return Celda(_markdown(16), codigo, _markdown_justificacion("barras_h"))


def _m17() -> Celda:
    codigo = (
        'precariedad_nivel = analysis.precariedad_estructural_por(hogares_cond_mdeo, "nivel_economico")\n'
        'fig = viz.plot_precariedad_estructural_por(precariedad_nivel, "nivel económico")\nfig.show()'
    )
    return Celda(_markdown(17), codigo, _markdown_justificacion("barras_h"))


def _m18() -> Celda:
    codigo = (
        'precariedad_depto = analysis.precariedad_estructural_por(hogares_cond, "departamento")\n'
        'fig = viz.plot_precariedad_estructural_por(precariedad_depto, "departamento")\nfig.show()'
    )
    return Celda(_markdown(18), codigo, _markdown_justificacion("barras_h"))


def _m19() -> Celda:
    codigo = (
        'precariedad_nivel = analysis.precariedad_estructural_por(hogares_cond_mdeo, "nivel_economico")\n'
        'brecha_precariedad = analysis.diferencia_entre_categorias(\n'
        '    precariedad_nivel, "nivel_economico", "1-Bajo", "5-Alto", "pct_precariedad"\n'
        ")\n"
        'nota(f"Diferencia en Montevideo entre el nivel económico bajo y el alto: {_res.fmt(brecha_precariedad, 2)} puntos porcentuales")\n\n'
        'fila_bajo = precariedad_nivel.set_index("nivel_economico").loc["1-Bajo", "pct_precariedad"]\n'
        'fila_alto = precariedad_nivel.set_index("nivel_economico").loc["5-Alto", "pct_precariedad"]\n'
        "fig = viz.plot_dumbbell(\n"
        '    categorias=["Precariedad estructural"],\n'
        "    valores_a=[fila_bajo], valores_b=[fila_alto],\n"
        '    nombre_a="1-Bajo", nombre_b="5-Alto",\n'
        '    titulo="Precariedad estructural: nivel económico bajo vs. alto", xlabel="% de hogares con carencia",\n'
        ")\nfig.show()"
    )
    return Celda(_markdown(19), codigo, _markdown_justificacion("dumbbell"))


def _m20() -> Celda:
    codigo = (
        "carencias_frecuentes = analysis.carencias_estructurales_mas_frecuentes(hogares_cond)\n"
        "fig = viz.plot_carencias_estructurales_mas_frecuentes(carencias_frecuentes)\nfig.show()"
    )
    return Celda(_markdown(20), codigo, _markdown_justificacion("barras_h"))


def _m21() -> Celda:
    codigo = (
        "prevalencia_fies = analysis.prevalencia_inseguridad_alimentaria(fies_clasificado)\n"
        "fig = viz.plot_prevalencia_inseguridad_alimentaria(prevalencia_fies)\nfig.show()"
    )
    return Celda(_markdown(21), codigo, _markdown_justificacion("barras"))


def _m22() -> Celda:
    codigo = (
        'chicos_quintil = analysis.grupos_con_muestra_chica(fies_clasificado, "quintil_ingreso")\n'
        "if len(chicos_quintil):\n"
        '    nota("Quintiles con menos de 30 casos en la muestra (estimación poco confiable): "\n'
        '         + ", ".join(f"{quintil} ({n} casos)" for quintil, n in chicos_quintil.items()))\n\n'
        'inseguridad_quintil = analysis.inseguridad_alimentaria_por(fies_clasificado, "quintil_ingreso")\n'
        "fig = viz.plot_inseguridad_alimentaria_por(\n"
        '    inseguridad_quintil, "quintil_ingreso",\n'
        '    titulo="Inseguridad alimentaria moderada o severa por quintil de ingreso", xlabel="Quintil de ingreso",\n'
        ")\nfig.show()"
    )
    return Celda(_markdown(22), codigo, _markdown_justificacion("barras"))


def _m23() -> Celda:
    codigo = (
        'inseguridad_region = analysis.inseguridad_alimentaria_por(fies_clasificado, "region")\n'
        "fig = viz.plot_inseguridad_alimentaria_por(\n"
        '    inseguridad_region, "region",\n'
        '    titulo="Inseguridad alimentaria moderada o severa por región", xlabel="Región",\n'
        ")\nfig.show()"
    )
    return Celda(_markdown(23), codigo, _markdown_justificacion("barras"))


def _m24() -> Celda:
    codigo = (
        'inseguridad_quintil = analysis.inseguridad_alimentaria_por(fies_clasificado, "quintil_ingreso")\n'
        "diferencia_quintiles = analysis.diferencia_entre_categorias(\n"
        '    inseguridad_quintil, "quintil_ingreso", "Quintil 1", "Quintil 5", "pct_inseguridad"\n'
        ")\n"
        'nota(f"Diferencia entre el quintil 1 y el quintil 5: {_res.fmt(diferencia_quintiles, 2)} puntos porcentuales")\n\n'
        'fila_q1 = inseguridad_quintil.set_index("quintil_ingreso").loc["Quintil 1", "pct_inseguridad"]\n'
        'fila_q5 = inseguridad_quintil.set_index("quintil_ingreso").loc["Quintil 5", "pct_inseguridad"]\n'
        "fig = viz.plot_dumbbell(\n"
        '    categorias=["Inseguridad alimentaria"],\n'
        "    valores_a=[fila_q1], valores_b=[fila_q5],\n"
        '    nombre_a="Quintil 1", nombre_b="Quintil 5",\n'
        '    titulo="Inseguridad alimentaria: quintil más pobre vs. más rico", xlabel="% de hogares (ponderado)",\n'
        ")\nfig.show()"
    )
    return Celda(_markdown(24), codigo, _markdown_justificacion("dumbbell"))


def _m25() -> Celda:
    codigo = (
        "inseguridad_severa_quintil = analysis.inseguridad_alimentaria_por(\n"
        '    fies_clasificado, "quintil_ingreso", columna_clasificacion="inseguridad_severa"\n'
        ")\n"
        "fig = viz.plot_inseguridad_alimentaria_por(\n"
        '    inseguridad_severa_quintil, "quintil_ingreso",\n'
        '    titulo="Inseguridad alimentaria severa por quintil de ingreso", xlabel="Quintil de ingreso",\n'
        ")\nfig.show()"
    )
    return Celda(_markdown(25), codigo, _markdown_justificacion("barras"))


def _m26() -> Celda:
    codigo = (
        "fies_con_menores18 = fies_clasificado.assign(\n"
        '    tiene_menores_18=fies_clasificado["tiene_menores_18"].map(\n'
        '        {True: "Con menores de 18", False: "Sin menores de 18"}\n'
        "    )\n"
        ")\n"
        'inseguridad_menores18 = analysis.inseguridad_alimentaria_por(fies_con_menores18, "tiene_menores_18")\n'
        "fig = viz.plot_inseguridad_alimentaria_por(\n"
        '    inseguridad_menores18, "tiene_menores_18",\n'
        '    titulo="Inseguridad alimentaria en hogares con y sin menores de 18 años", xlabel="",\n'
        ")\nfig.show()"
    )
    return Celda(_markdown(26), codigo, _markdown_justificacion("barras"))


def _m27() -> Celda:
    codigo = (
        "fies_con_menores6 = fies_clasificado.assign(\n"
        '    tiene_menores_6=fies_clasificado["tiene_menores_6"].map(\n'
        '        {True: "Con niños de 0 a 5", False: "Sin niños de 0 a 5"}\n'
        "    )\n"
        ")\n"
        'inseguridad_menores6 = analysis.inseguridad_alimentaria_por(fies_con_menores6, "tiene_menores_6")\n'
        "fig = viz.plot_inseguridad_alimentaria_por(\n"
        '    inseguridad_menores6, "tiene_menores_6",\n'
        '    titulo="Inseguridad alimentaria en hogares con y sin niños de 0 a 5 años", xlabel="",\n'
        ")\nfig.show()"
    )
    return Celda(_markdown(27), codigo, _markdown_justificacion("barras"))


def _m28() -> Celda:
    codigo = (
        "tasas_nacionales = analysis.tasas_actividad_empleo_desempleo(empleo_prep)\n"
        "fig = viz.plot_tasas_actividad_empleo_desempleo(tasas_nacionales)\nfig.show()"
    )
    return Celda(_markdown(28), codigo, _markdown_justificacion("barras"))


def _m29() -> Celda:
    codigo = (
        'tasas_sexo = analysis.tasas_actividad_empleo_desempleo_por(empleo_prep, "sexo_grupo")\n'
        'brecha_genero = analysis.brecha_por_grupo(tasas_sexo, "sexo_grupo", "Hombre", "Mujer")\n'
        # print formateado, nunca la Series cruda: imprimir el objeto de
        # pandas mete "tasa_actividad 16.59 ... dtype: float64" en el
        # informe final - el ruido tecnico que prohibe METODOLOGIA.md
        # seccion 3. Encontrado por el agente en una corrida real de 2023
        # (lo parcho a mano y costo re-ejecutar el notebook entero).
        'nota("Brecha de género (hombre menos mujer, en puntos porcentuales): "\n'
        '     f"actividad {_res.fmt_signo(brecha_genero[\'tasa_actividad\'], 2)} · "\n'
        '     f"empleo {_res.fmt_signo(brecha_genero[\'tasa_empleo\'], 2)} · "\n'
        '     f"desempleo {_res.fmt_signo(brecha_genero[\'tasa_desempleo\'], 2)}")\n\n'
        'fig = viz.plot_tasas_por_grupo(tasas_sexo, "sexo_grupo", "Tasas de actividad, empleo y desempleo por sexo")\n'
        "fig.show()"
    )
    return Celda(_markdown(29), codigo, _markdown_justificacion("barras"))


def _m30() -> Celda:
    codigo = (
        'desempleo_depto = analysis.tasa_mensual_promedio_por(activos, "departamento", "es_desocupado")\n'
        'fig = viz.plot_tasa_mensual_promedio_por(desempleo_depto, "departamento", "Tasa de desempleo por departamento")\n'
        "fig.show()"
    )
    return Celda(_markdown(30), codigo, _markdown_justificacion("barras_h"))


def _m31() -> Celda:
    codigo = (
        'informalidad_sexo = analysis.tasa_mensual_promedio_por(ocupados, "sexo_grupo", "es_informal")\n'
        'fig = viz.plot_tasa_mensual_promedio_por(informalidad_sexo, "sexo_grupo", "Informalidad laboral por sexo")\n'
        "fig.show()"
    )
    return Celda(_markdown(31), codigo, _markdown_justificacion("barras_h"))


def _m32() -> Celda:
    codigo = (
        'informalidad_educacion = analysis.tasa_mensual_promedio_por(ocupados, "nivel_educativo", "es_informal")\n'
        'fig = viz.plot_tasa_mensual_promedio_por(informalidad_educacion, "nivel_educativo", "Informalidad laboral por nivel educativo")\n'
        "fig.show()"
    )
    return Celda(_markdown(32), codigo, _markdown_justificacion("barras_h"))


def _m33() -> Celda:
    codigo = (
        'subempleo_sexo = analysis.tasa_mensual_promedio_por(ocupados, "sexo_grupo", "es_subempleo")\n'
        'fig = viz.plot_tasa_mensual_promedio_por(subempleo_sexo, "sexo_grupo", "Subempleo por sexo")\n'
        "fig.show()"
    )
    return Celda(_markdown(33), codigo, _markdown_justificacion("barras_h"))


def _m34() -> Celda:
    codigo = (
        'tasas_edad_laboral = analysis.tasas_actividad_empleo_desempleo_por(empleo_prep, "grupo_edad_laboral")\n'
        'brecha_edad = analysis.brecha_por_grupo(tasas_edad_laboral, "grupo_edad_laboral", "Joven (14-24)", "Resto")\n'
        # Mismo criterio que _m29: nunca imprimir la Series cruda.
        'nota("Brecha juvenil (jóvenes menos resto, en puntos porcentuales): "\n'
        '     f"actividad {_res.fmt_signo(brecha_edad[\'tasa_actividad\'], 2)} · "\n'
        '     f"empleo {_res.fmt_signo(brecha_edad[\'tasa_empleo\'], 2)} · "\n'
        '     f"desempleo {_res.fmt_signo(brecha_edad[\'tasa_desempleo\'], 2)}")\n\n'
        'fig = viz.plot_tasas_por_grupo(\n'
        '    tasas_edad_laboral, "grupo_edad_laboral",\n'
        '    "Tasas de actividad, empleo y desempleo: jóvenes vs. resto",\n'
        ")\nfig.show()"
    )
    return Celda(_markdown(34), codigo, _markdown_justificacion("barras"))


def _m35() -> Celda:
    codigo = (
        'situacion_por_sector = analysis.composicion_categorica_por_mes_promedio(\n'
        '    ocupados, "sector_formalidad", "situacion_ocupacional"\n'
        ")\n"
        "fig = viz.plot_composicion_categorica(\n"
        "    situacion_por_sector,\n"
        '    titulo="Situación ocupacional dentro de cada sector (formal / informal)", xlabel="Sector",\n'
        ")\nfig.show()"
    )
    return Celda(_markdown(35), codigo, _markdown_justificacion("barras_100"))


def _m36() -> Celda:
    codigo = (
        'prevalencia_delito = analysis.pct_ponderado_por(\n'
        '    victimizacion_largo, "tipo_delito", "victimizado", "ponderador_victimizacion"\n'
        ")\n"
        "fig = viz.plot_pct_por(\n"
        '    prevalencia_delito, "tipo_delito",\n'
        '    titulo="Prevalencia de victimización por tipo de delito", xlabel="Tipo de delito",\n'
        ")\nfig.show()"
    )
    return Celda(_markdown(36), codigo, _markdown_justificacion("barras"))


def _m37() -> Celda:
    codigo = (
        'victimizacion_sexo = analysis.pct_ponderado_por(\n'
        '    victimizacion_prep, "sexo_grupo", "victimizado_algun_delito", "ponderador_victimizacion"\n'
        ")\n"
        "fig = viz.plot_pct_por(\n"
        '    victimizacion_sexo, "sexo_grupo",\n'
        '    titulo="Victimización general por sexo", xlabel="Sexo",\n'
        ")\nfig.show()"
    )
    return Celda(_markdown(37), codigo, _markdown_justificacion("barras"))


# Victimización es un evento raro (1-3% de las personas en un mes): la
# precisión de cada porcentaje la sostienen los CASOS, no las personas
# encuestadas. En la corrida real de 2024, 17 de los 19 departamentos tenían
# menos de 30 víctimas (Cerro Largo: 0 sobre 694 personas) y el resumen decía
# «va de 0,0% (Cerro Largo) a 7,7% (Treinta y Tres)». Los departamentos con
# pocos casos se marcan en gris en la gráfica y quedan fuera de la comparación
# de extremos del resumen (ver docs/METODOLOGIA.md, sección 2).
_AVISO_POCOS_CASOS = (
    'if len(pocos_casos_depto):\n'
    '    nota("Departamentos con menos de 30 víctimas en la muestra (estimación poco confiable, en gris en la gráfica): "\n'
    '         + ", ".join(f"{_res.etiqueta(depto)} ({n} casos)" for depto, n in pocos_casos_depto.items()))\n\n'
)

# Las tasas entre víctimas (comunicación, denuncia, violencia) se calculan
# sobre las víctimas de cada delito: ese es el grupo cuyo tamaño importa.
_AVISO_VICTIMAS_CHICAS = (
    'chicos_victimas_delito = analysis.grupos_con_muestra_chica(victimizados, "tipo_delito")\n'
    'if len(chicos_victimas_delito):\n'
    '    nota("Tipos de delito con menos de 30 víctimas en la muestra (estimación poco confiable): "\n'
    '         + ", ".join(f"{delito} ({n} casos)" for delito, n in chicos_victimas_delito.items()))\n\n'
)


def _m38() -> Celda:
    codigo = (
        'pocos_casos_depto = analysis.grupos_con_pocos_casos(victimizacion_prep, "departamento", "victimizado_algun_delito")\n'
        + _AVISO_POCOS_CASOS
        + 'victimizacion_depto = analysis.pct_ponderado_por(\n'
        '    victimizacion_prep, "departamento", "victimizado_algun_delito", "ponderador_victimizacion"\n'
        ")\n"
        'victimizacion_depto_confiable = victimizacion_depto[~victimizacion_depto["departamento"].isin(pocos_casos_depto.index)]\n'
        "fig = viz.plot_pct_por(\n"
        '    victimizacion_depto, "departamento",\n'
        '    titulo="Victimización general por departamento", xlabel="Departamento",\n'
        "    poco_confiables=list(pocos_casos_depto.index),\n"
        ")\nfig.show()"
    )
    return Celda(_markdown(38), codigo, _markdown_justificacion("barras_h"))


def _m39() -> Celda:
    codigo = (
        _AVISO_VICTIMAS_CHICAS
        + 'comunicacion_delito = analysis.pct_ponderado_por(\n'
        '    victimizados, "tipo_delito", "comunicacion_policia", "ponderador_victimizacion"\n'
        ")\n"
        "fig = viz.plot_pct_por(\n"
        '    comunicacion_delito, "tipo_delito",\n'
        '    titulo="Tasa de comunicación a la policía por tipo de delito", xlabel="Tipo de delito",\n'
        ")\nfig.show()"
    )
    return Celda(_markdown(39), codigo, _markdown_justificacion("barras"))


def _m40() -> Celda:
    codigo = (
        _AVISO_VICTIMAS_CHICAS
        + 'denuncia_delito = analysis.pct_ponderado_por(\n'
        '    victimizados, "tipo_delito", "denuncia_formal", "ponderador_victimizacion"\n'
        ")\n"
        "fig = viz.plot_pct_por(\n"
        '    denuncia_delito, "tipo_delito",\n'
        '    titulo="Tasa de denuncia formal por tipo de delito", xlabel="Tipo de delito",\n'
        ")\nfig.show()"
    )
    return Celda(_markdown(40), codigo, _markdown_justificacion("barras"))


def _m41() -> Celda:
    codigo = (
        'comunicacion_delito = analysis.pct_ponderado_por(\n'
        '    victimizados, "tipo_delito", "comunicacion_policia", "ponderador_victimizacion"\n'
        ")\n"
        'denuncia_delito = analysis.pct_ponderado_por(\n'
        '    victimizados, "tipo_delito", "denuncia_formal", "ponderador_victimizacion"\n'
        ")\n"
        "\nfig = viz.plot_dumbbell(\n"
        '    categorias=comunicacion_delito["tipo_delito"].tolist(),\n'
        '    valores_a=comunicacion_delito["pct"].tolist(),\n'
        '    valores_b=denuncia_delito.set_index("tipo_delito").loc[comunicacion_delito["tipo_delito"], "pct"].tolist(),\n'
        '    nombre_a="Comunicación a la policía", nombre_b="Denuncia formal",\n'
        '    titulo="Comunicación informal vs. denuncia formal, por tipo de delito", xlabel="% de víctimas (ponderado)",\n'
        ")\nfig.show()"
    )
    return Celda(_markdown(41), codigo, _markdown_justificacion("dumbbell"))


def _m42() -> Celda:
    codigo = (
        "tipos_con_violencia = [info[\"nombre\"] for info in config.TIPOS_DELITO.values() if info[\"violencia\"]]\n"
        'victimizados_violencia = victimizados[victimizados["tipo_delito"].isin(tipos_con_violencia)]\n'
        'chicos_victimas_violencia = analysis.grupos_con_muestra_chica(victimizados_violencia, "tipo_delito")\n'
        'if len(chicos_victimas_violencia):\n'
        '    nota("Tipos de delito con menos de 30 víctimas en la muestra (estimación poco confiable): "\n'
        '         + ", ".join(f"{delito} ({n} casos)" for delito, n in chicos_victimas_violencia.items()))\n\n'
        "violencia_delito = analysis.pct_ponderado_por(\n"
        '    victimizados_violencia, "tipo_delito", "violencia", "ponderador_victimizacion"\n'
        ")\n"
        "fig = viz.plot_pct_por(\n"
        '    violencia_delito, "tipo_delito",\n'
        '    titulo="Casos con violencia por tipo de delito", xlabel="Tipo de delito",\n'
        ")\nfig.show()"
    )
    return Celda(_markdown(42), codigo, _markdown_justificacion("barras"))


# ============================================================================
# Registro y orquestación
# ============================================================================

# Una plantilla por métrica del manifiesto: el catálogo (plantillas.py),
# el manifiesto (verificacion_catalogo.MANIFEST) y estas plantillas se
# mantienen alineados por construcción y por test, no por un rango literal
# escrito acá (hasta la v0.14.1 decía `range(1, 43)` a mano).
GENERADORES: dict[int, Callable[[], Celda]] = {n: globals()[f"_m{n}"] for n in verificacion_catalogo.MANIFEST}


def construir_celdas_metrica(numero: int, terminos_ya_explicados: set[str] | None = None) -> Celda:
    """Punto de entrada para una métrica del catálogo (1-42), año base
    únicamente. Si la persona pidió comparar esta métrica entre años, eso
    se resuelve en código libre (paso 5, criterio ya documentado en
    docs/CONVENCIONES_DE_GRAFICAS.md), no acá.

    `terminos_ya_explicados` son los que ya explicó la presentación del
    bloque: no se repiten en la métrica. Si no queda ninguno propio, la
    métrica directamente no trae sección de términos.
    """
    celda = GENERADORES[numero]()
    if terminos_ya_explicados:
        return Celda(
            markdown=_markdown(numero, terminos_ya_explicados),
            codigo=celda.codigo,
            markdown_final=celda.markdown_final,
        )
    return celda


# ============================================================================
# Panorama general de Brecha Digital: siempre se muestra si se eligió ese
# bloque, sin importar qué métricas puntuales del 1 al 6 se hayan marcado
# — ver paso 5 en .claude/instrucciones/encuesta-hogares.md. No tiene número de
# catálogo propio.
# ============================================================================

def celdas_intro_brecha_digital() -> list[Celda]:
    """Apertura del bloque de Brecha Digital: una sola celda con el
    panorama de conectividad.

    Hasta la 0.9.0 esto traía tres secciones heredadas del análisis
    original de 2019 —"Panorama general" contando hogares con y sin TV
    cable, "Distribución por barrio" con el % de abonados al cable, y
    "Composición de los hogares con y sin cable"— que aparecían en TODO
    informe que incluyera el bloque, sin importar qué métricas hubiera
    elegido la persona. Por vivir acá y no en el catálogo, sobrevivieron a
    la limpieza de métricas de cable de la 0.6.0 y llegaron a un informe
    real. Se eliminaron junto con la dimensión barrio completa (decisión
    del dueño del proyecto), y el panorama que queda mide internet, que es
    lo que la sección siempre dijo medir.
    """
    panorama = Celda(
        # `###` para que cuelgue del "## Brecha Digital" que abre el tema.
        markdown="### Panorama general de conectividad en Montevideo",
        codigo=(
            "resumen_conectividad_mdeo = analysis.resumen_conectividad(hogares_ext)\n"
            'nota(f"Hogares con internet: {_res.fmt(resumen_conectividad_mdeo.hogares_con_internet, 0)} '
            '({_res.fmt(resumen_conectividad_mdeo.pct_con_internet)}%)",\n'
            '     f"Hogares sin internet: {_res.fmt(resumen_conectividad_mdeo.hogares_sin_internet, 0)} '
            '({_res.fmt(resumen_conectividad_mdeo.pct_sin_internet)}%)")\n\n'
            "fig = viz.plot_distribucion_conectividad(resumen_conectividad_mdeo)\nfig.show()"
        ),
    )
    return [panorama]


# ============================================================================
# Orquestación: arma el notebook completo y lo escribe a disco. Es lo
# único de este módulo que el agente invoca directamente en el paso 5,
# para las métricas del catálogo fijo sin comparación entre años — las
# métricas a medida del paso 6 y cualquier comparación entre años se
# siguen agregando aparte, con `nbformat.v4.new_markdown_cell`/
# `new_code_cell` escritos a mano, antes de `nbformat.write`.
# ============================================================================

_CABECERA = '''%matplotlib inline
import warnings

import kaleido
import pandas as pd
import plotly.io as pio

from IPython.display import Markdown as _Markdown, display as _display

from encuesta_hogares import analysis, bitacora, config, data_loader, entrega, preprocessing
from encuesta_hogares import resumen as _res
from encuesta_hogares import visualization as viz


def nota(*lineas):
    """Texto breve bajo una celda, con el formato del informe (markdown) y no
    como salida cruda de consola. Cada argumento es una línea."""
    _display(_Markdown("  \\n".join(str(linea) for linea in lineas)))


pio.renderers.default = "png"
# Un solo Chromium para todas las gráficas: sin esto, kaleido 1.x lanza uno
# nuevo por imagen y cada gráfica tarda ~2,3 s en vez de ~0,1 s (medido el
# 2026-09-09: 47 gráficas eran 140 de los 150 s de ejecución del informe).
if hasattr(kaleido, "start_sync_server"):
    kaleido.start_sync_server(silence_warnings=True)
warnings.filterwarnings("ignore")'''


def construir_celdas_notebook(
    anio_base: int,
    metricas: list[int],
    incluir_brecha_digital: bool,
    incluir_fies: bool,
    incluir_empleo: bool,
    incluir_seguridad: bool,
    celdas_extra: dict[int, list[Celda]] | None = None,
) -> list[Celda]:
    """Arma el informe completo, en el orden en que se lee — sin escribir
    nada a disco todavía.

    La estructura es fija (v0.13.0):

    1. **Introducción**: qué se analizó, de dónde salen los datos, qué
       contiene.
    2. **Preparación de datos**: la infraestructura técnica.
    3. **Un tramo por tema**, agrupando las métricas elegidas: nombre del
       bloque, qué mide, los términos del INE que usan varias de sus
       métricas, y después cada métrica.
    4. **Nota metodológica**: qué significa "ponderado".

    Las métricas se **agrupan por bloque**, no se emiten en el orden en que
    la persona las marcó: antes salían como una lista plana (la 1, la 8, la
    22 y la 28 una detrás de otra) sin nada que dijera a qué tema pertenecía
    cada una.

    Las comparaciones entre años y las métricas a medida las escribe el
    agente a mano — se probó mecanizarlas y no funcionó. Van en
    `celdas_extra`: `{numero: [celdas]}` inserta esas celdas **justo
    después** de la métrica `numero`, dentro de su bloque. Así el agente
    agrega lo suyo sin rearmar la estructura por su cuenta, que es donde se
    perderían la introducción y la presentación de cada tema.
    """

    elegidas = list(metricas)
    extra = celdas_extra or {}

    # Un extra colgado de una métrica que no se eligió no tendría dónde ir y
    # desaparecería sin dejar rastro: el informe saldría bien formado, sin la
    # comparación que la persona pidió. Mejor cortar acá.
    huerfanas = sorted(set(extra) - set(elegidas))
    if huerfanas:
        raise ValueError(
            f"celdas_extra apunta a métricas que no se eligieron: {huerfanas}. "
            f"Elegidas: {sorted(set(elegidas))}."
        )
    # Las métricas se emiten recorriendo los bloques, así que una que no
    # pertenezca a ninguno no se emitiría: el informe saldría entero y sin
    # ella, sin ningún aviso. Puede pasar si se agrega una métrica al
    # catálogo y se olvida el rango en `verificacion_catalogo.BLOQUES`.
    sin_bloque = sorted(n for n in set(elegidas) if not _bloque_de(n))
    if sin_bloque:
        raise ValueError(
            f"estas métricas no pertenecen a ningún bloque de "
            f"verificacion_catalogo.BLOQUES y quedarían fuera del informe: {sin_bloque}"
        )
    del_bloque = terminos_de_bloque(elegidas)

    # Orden de los bloques: el del catálogo (1 · Brecha Digital, 2 ·
    # Hogares, ...), no el orden en que la persona marcó las métricas.
    bloques_presentes = [
        bloque for bloque in verificacion_catalogo.BLOQUES
        if any(_bloque_de(n) == bloque for n in elegidas)
    ]

    # Los 12 archivos de Empleo se cargan una sola vez, en la preparación
    # general, si alguna métrica elegida los usa: las del bloque Empleo o
    # las del índice territorial (13-15). Ninguna otra celda vuelve a leerlos.
    necesita_empleo = "empleo" in bloques_presentes or "territorio" in bloques_presentes
    celdas = [celda_introduccion(anio_base, elegidas, bloques_presentes)]
    celdas.append(celda_preparacion_datos(anio_base, incluir_fies, incluir_empleo=necesita_empleo))

    # La preparación de Empleo, la de Seguridad y la del índice territorial
    # abren su propio tema, no el informe: dejarlas arriba ponía un "## Empleo:
    # preparación específica de este bloque" entre la preparación general y el
    # primer tema, lejos del "## Empleo" que le corresponde. Lo que definen
    # solo lo usan las métricas de su tema (el dato crudo compartido, el
    # empleo, ya quedó cargado arriba).
    apertura_de_bloque = {}
    if "empleo" in bloques_presentes:
        apertura_de_bloque["empleo"] = [celda_preparacion_empleo(anio_base)]
    if "territorio" in bloques_presentes:
        apertura_de_bloque["territorio"] = [celda_preparacion_territorio()]
    if "seguridad" in bloques_presentes:
        apertura_de_bloque["seguridad"] = [celda_preparacion_seguridad(anio_base)]
    if incluir_brecha_digital:
        # El panorama de conectividad es contexto de su tema, no de todos.
        apertura_de_bloque["brecha_digital"] = celdas_intro_brecha_digital()

    for bloque in bloques_presentes:
        terminos = del_bloque.get(bloque, [])
        celdas.append(celda_presentacion_bloque(bloque, terminos))
        celdas.extend(apertura_de_bloque.get(bloque, []))
        for numero in [n for n in elegidas if _bloque_de(n) == bloque]:
            celdas.append(construir_celdas_metrica(numero, set(terminos)))
            celdas.extend(extra.get(numero, []))

    celdas.append(celda_nota_metodologica())
    return celdas


def escribir_notebook(celdas: list[Celda], ruta: Path | str) -> Path:
    """Convierte las celdas ya armadas a un notebook real y lo escribe a
    disco, respaldando el de la misma ruta si ya existía (mismo criterio
    que el resto del flujo — ver `entrega.respaldar_si_existe`)."""
    ruta = Path(ruta)
    nb = new_notebook()
    nb["cells"].append(new_code_cell(_CABECERA))
    for celda in celdas:
        if celda.markdown:
            nb["cells"].append(new_markdown_cell(celda.markdown))
        # Un tramo puede ser solo texto (introducción, presentación de un
        # bloque, nota metodológica): ahí no se agrega una celda de código
        # vacía, que en el informe final se vería como un hueco.
        if celda.codigo:
            nb["cells"].append(new_code_cell(celda.codigo))
        if celda.markdown_final:
            nb["cells"].append(new_markdown_cell(celda.markdown_final))
    entrega.respaldar_si_existe(ruta)
    nbformat.write(nb, str(ruta))
    return ruta

# ============================================================================
# Cierre del informe: cifras para el resumen, resumen analítico y fuentes.
#
# Hasta la v0.13.6 el "Resumen analítico final" lo escribía el modelo
# después de ejecutar el notebook, sacando los números "con Python, no de
# memoria" — es decir, recalculando a mano — y lo insertaba con nbformat
# para volver a ejecutar todo. Ahora el propio notebook deja las cifras de
# cada métrica en un JSON (`celda_cifras`), el modelo redacta el resumen
# leyendo ese archivo, y `generar_informe.entregar` lo agrega como
# markdown SIN volver a ejecutar nada (agregar texto a un notebook ya
# ejecutado no requiere kernel). La lista de fuentes por bloque, que el
# modelo copiaba de las instrucciones del agente, sale de acá.
# ============================================================================

def ruta_cifras(ruta_notebook: Path | str) -> Path:
    """El JSON de cifras vive al lado del notebook, con su mismo nombre:
    `notebooks/_cifras_Informe_ECH_2025.json`."""
    ruta_notebook = Path(ruta_notebook)
    return ruta_notebook.with_name(f"_cifras_{ruta_notebook.stem}.json")


def celda_cifras(ruta_notebook: Path | str) -> Celda:
    """Última celda de código del informe: vuelca a JSON toda tabla o valor
    que las métricas dejaron definido (DataFrames y Series de hasta 200
    filas, dicts de números, escalares), redondeado a dos decimales. No
    imprime nada — en el informe sin código es invisible — y no puede
    romper el informe: cualquier variable que no se pueda serializar se
    salta. Es la fuente de la que el modelo saca los números del resumen y
    contra la que `generar_informe.entregar` valida cada cifra."""
    destino = str(ruta_cifras(ruta_notebook)).replace("\\", "/")
    codigo = f"""import dataclasses as _dataclasses
import json as _json
import numbers as _numbers

_cifras = {{}}
for _nombre, _valor in list(globals().items()):
    if _nombre.startswith("_") or _nombre in ("hogares", "personas", "personas_con_depto"):
        continue
    try:
        if isinstance(_valor, pd.DataFrame) and 0 < len(_valor) <= 200:
            _cifras[_nombre] = _json.loads(_valor.round(2).to_json(orient="records", force_ascii=False, date_format="iso"))
        elif isinstance(_valor, pd.Series) and 0 < len(_valor) <= 200:
            _cifras[_nombre] = _json.loads(_valor.round(2).to_json(force_ascii=False, date_format="iso"))
        elif isinstance(_valor, dict) and _valor and all(isinstance(v, _numbers.Number) for v in _valor.values()):
            _cifras[_nombre] = {{str(k): round(float(v), 2) for k, v in _valor.items()}}
        elif isinstance(_valor, _numbers.Number) and not isinstance(_valor, bool):
            _cifras[_nombre] = round(float(_valor), 2)
        elif hasattr(_valor, "_asdict") or (_dataclasses.is_dataclass(_valor) and not isinstance(_valor, type)):
            _campos = _valor._asdict() if hasattr(_valor, "_asdict") else _dataclasses.asdict(_valor)
            _cifras[_nombre] = {{k: (round(float(v), 2) if isinstance(v, _numbers.Number) else str(v)) for k, v in _campos.items()}}
    except Exception:
        continue
with open(r"{destino}", "w", encoding="utf-8") as _f:
    _json.dump(_cifras, _f, ensure_ascii=False, indent=1, default=str)"""
    return Celda(markdown="", codigo=codigo)


# Fuentes consultadas para diseñar cada bloque (las mismas que listan las
# instrucciones del agente, paso 4). FIES no lleva: sale de la metodología
# original del proyecto, no de investigación externa.
_FUENTES_POR_BLOQUE: dict[str, list[str]] = {
    "brecha_digital": [
        "CEPAL — Observatorio de Desarrollo Digital de América Latina y el Caribe: "
        "https://desarrollodigital.cepal.org/es/indicadores",
        "UIT/ITU — ICT Development Index: https://www.itu.int/en/ITU-D/Statistics/Pages/IDI/default.aspx",
        "A4AI (Alliance for Affordable Internet) — estándar «Meaningful Connectivity»: "
        "https://adi.a4ai.org/meaningful-connectivity/",
        "Pandolfi, J. (2024) — «Brechas de acceso digital: cambio histórico y ciclo vital», Revista de Ciencias "
        "Sociales, 37(54), UdelaR: https://doi.org/10.26489/rvs.v37i54.5",
        "CEPAL — «La brecha digital de género: reflejo de la desigualdad social», Nota para la Igualdad N°10: "
        "https://oig.cepal.org/sites/default/files/notas_para_la_igualdad_ndeg10_-_brecha_digital_de_genero.pdf",
        "CEPALSTAT (CEPAL/CELADE) — jefatura de hogar, tipos de hogar, hacinamiento, razón de dependencia "
        "demográfica: https://statistics.cepal.org/portal/cepalstat/",
    ],
    "territorio": [
        "Rodríguez Miranda, A.; Vial Cossani, C.; Centurión, I.; Pérez Fernández, M. — «Índice de Desarrollo "
        "Regional Uruguay 2006-2022 (IDERE-UY)», IECON-FCEA/UdelaR, ANII, 2024: "
        "https://ideas.repec.org/p/ulr/wpaper/dt-01-24.html",
        "CEPAL/ILPES (2025) — «Panorama del desarrollo territorial de América Latina y el Caribe, 2024»: "
        "https://www.cepal.org/es/publicaciones/81240-panorama-desarrollo-territorial-america-latina-caribe-2024-nuevas-capacidades-la",
        "CEPAL — «Guía metodológica para el diseño de indicadores compuestos de desarrollo sostenible», 2009: "
        "https://repositorio.cepal.org/handle/11362/3663",
    ],
    "vivienda": [
        "UN-Habitat/UNSD — Metadatos del indicador SDG 11.1.1 («durability of housing»), 2020: "
        "https://unhabitat.org/sites/default/files/2020/06/metadata_on_sdg_indicator_11.1.1.pdf",
        "Bramati, M. et al. — «Introducing the Adequate Housing Index (AHI)», World Bank Policy Research "
        "Working Paper 9830, 2021: "
        "https://documents.worldbank.org/en/publication/documents-reports/documentdetail/936291631846076967",
        "INE Uruguay, FCS-UdelaR, IECON, MIDES (coord. Calvo, J.J.) — «Atlas Sociodemográfico y de la "
        "Desigualdad del Uruguay», Fascículo 1 (NBI), 2013: "
        "https://www.ine.gub.uy/atlas-sociodemografico-y-de-la-desigualdad-del-uruguay",
        "Arriagada, C. — «Perfil de déficit y políticas de vivienda de interés social», CELADE/CEPAL, 2003: "
        "https://repositorio.cepal.org/handle/11362/5711",
    ],
    "empleo": [
        "Key Indicators of the Labour Market (KILM), novena edición — OIT (2016): "
        "https://www.ilo.org/publications/key-indicators-labour-market-kilm-ninth-edition",
        "«Se profundizó la brecha de género en el mercado laboral» — Ámbito: "
        "https://www.ambito.com/uruguay/se-profundizo-la-brecha-genero-el-mercado-laboral-n6096977",
        "«El desempleo entre los más jóvenes cerró cerca del 25% en 2024» — Ámbito: "
        "https://www.ambito.com/uruguay/el-desempleo-los-mas-jovenes-cerro-cerca-del-25-2024-n6108458",
        "«Subempleo e informalidad afectan a casi 3 de cada 10 ocupados en Uruguay» — La Mañana: "
        "https://www.xn--lamaana-7za.uy/actualidad/trabajo-subempleo-e-informalidad-afectan-a-casi-3-de-cada-10-ocupados-en-uruguay/",
    ],
    "seguridad": [
        "Manual para Encuestas de Victimización — UNODC/UNECE (2010): "
        "https://unece.org/statistics/publications/manual-victimization-surveys",
        "«Qué porcentaje de delitos son denunciados a la Policía, según informe del INE» — Montevideo Portal: "
        "https://www.montevideo.com.uy/Noticias/Que-porcentaje-de-delitos-son-denunciados-a-la-Policia-segun-informe-del-INE-uc914924",
    ],
}
# Hogares comparte las fuentes de Brecha Digital (así lo listan las
# instrucciones del agente: "Brecha Digital y Hogares").
_FUENTES_POR_BLOQUE["hogares"] = _FUENTES_POR_BLOQUE["brecha_digital"]


def fuentes_de_consulta(bloques: list[str]) -> list[str]:
    """Las fuentes de los bloques presentes, sin repetir y en el orden del
    catálogo. Lista vacía si solo hay FIES (no lleva sección)."""
    vistas: list[str] = []
    for bloque in bloques:
        for fuente in _FUENTES_POR_BLOQUE.get(bloque, []):
            if fuente not in vistas:
                vistas.append(fuente)
    return vistas


def celda_comentario(markdown_comentario: str) -> Celda:
    """Comentario opcional que `generar_informe.entregar --comentario`
    agrega después del resumen automático, con cada cifra verificada
    contra los resultados ejecutados. No reemplaza al resumen."""
    return Celda(markdown="### Comentario\n\n" + markdown_comentario.strip())

# ============================================================================
# Resumen analítico final, armado dentro del notebook.
#
# Una frase por métrica del catálogo, escrita UNA vez acá como expresión de
# Python que se evalúa en el kernel sobre las variables que la propia
# métrica dejó definidas (`_res` es `encuesta_hogares.resumen`). El número
# que dice el resumen es, por construcción, el mismo que muestra la
# gráfica: ningún modelo redacta ni transcribe cifras, y el texto es
# idéntico corrida a corrida. Si una plantilla falla (una columna cambió
# de nombre, una categoría no existe ese año), la celda levanta un error
# con el número de la métrica y el pipeline no entrega el informe —
# preferible a un resumen con un hueco silencioso.
#
# Estilo: lenguaje simple, sin jerga; "ponderado" ya lo explica la nota
# metodológica. Los porcentajes se formatean con coma decimal.
# ============================================================================

_RESUMEN_POR_METRICA: dict[int, str] = {
    1: ('f"El acceso a internet en los hogares de Montevideo sube con el nivel económico: "'
        'f"{_f(_v(brecha_nivel_economico, \'pct_penetracion\', nivel_economico=\'1-Bajo\', tecnologia=\'Internet\'))}% "'
        'f"en el nivel bajo frente a {_f(_v(brecha_nivel_economico, \'pct_penetracion\', nivel_economico=\'5-Alto\', tecnologia=\'Internet\'))}% en el alto"'),
    2: ('_b(brecha_cohorte[brecha_cohorte[\'tecnologia\'] == \'Internet\'], \'cohorte\', \'pct_penetracion\', '
        '\'Según la generación de quien encabeza el hogar, el acceso a internet\')'),
    3: ('f"La conexión solo por celular alcanza al {_f(calidad_nivel_economico.loc[\'1-Bajo\', \'Solo móvil\'])}% de los hogares "'
        'f"del nivel económico bajo y al {_f(calidad_nivel_economico.loc[\'5-Alto\', \'Solo móvil\'])}% del alto"'),
    4: ('f"Con jefatura masculina, el {_f(_v(brecha_jefatura, \'pct_penetracion\', jefe_sexo=\'Hombre\', tecnologia=\'Internet\'))}% de los hogares tiene internet; "'
        'f"con jefatura femenina, el {_f(_v(brecha_jefatura, \'pct_penetracion\', jefe_sexo=\'Mujer\', tecnologia=\'Internet\'))}%"'),
    5: ('f"El índice de acceso digital (cantidad de tecnologías en el hogar) promedia "'
        'f"{_f(_v(indice_acceso_nivel, \'indice_promedio\', nivel_economico=\'1-Bajo\'), 2)} en el nivel económico bajo y "'
        'f"{_f(_v(indice_acceso_nivel, \'indice_promedio\', nivel_economico=\'5-Alto\'), 2)} en el alto"'),
    6: '_b(adopcion_tablet_nivel, \'nivel_economico\', \'pct_con_tablet\', \'Entre los hogares con jefe o jefa de 65 años o más, la tenencia de una tablet del Plan Ibirapitá\')',
    7: 'f"El {_f(pobreza[\'pct_pobres\'])}% de los hogares de Montevideo está en situación de pobreza y el {_f(pobreza[\'pct_indigentes\'])}% en indigencia"',
    8: 'f"El {_f(jefatura[\'pct_jefatura_femenina\'])}% de los hogares del país con jefatura identificada tiene una jefa mujer"',
    9: '_b(hacinamiento_nivel, \'nivel_economico\', \'pct_hacinamiento\', \'El hacinamiento en Montevideo\')',
    10: ('f"El tipo de hogar más frecuente es el {tipos_hogar_resumen.loc[tipos_hogar_resumen[\'pct_hogares\'].idxmax(), \'tipo_hogar\'].lower()} "'
         'f"({_f(tipos_hogar_resumen[\'pct_hogares\'].max())}% de los hogares)"'),
    11: '_b(dependencia_depto, \'departamento\', \'razon_dependencia\', \'La razón de dependencia demográfica (personas menores de 15 o de 65 y más por cada 100 en edad activa)\', unidad=\'\')',
    12: 'f"El {_f(unipersonales_mayores[\'pct_unipersonales_mayores\'])}% de los hogares unipersonales corresponde a personas de 65 años o más"',
    13: ('f"En el índice de desarrollo territorial (0 a 1), el departamento mejor posicionado es {_res.etiqueta(indice_territorial.index[0])} "'
         'f"({_f(indice_territorial[\'indice\'].iloc[0], 2)}) y el más rezagado {_res.etiqueta(indice_territorial.index[-1])} ({_f(indice_territorial[\'indice\'].iloc[-1], 2)})"'),
    14: ('f"El componente que más separa a los departamentos entre sí es «{(componentes_territorio.max() - componentes_territorio.min()).idxmax()}»"'),
    15: 'f"La brecha entre el mejor y el peor departamento del índice territorial es de {_f(brecha_territorial, 2)} puntos"',
    16: 'f"El {_f(precariedad[\'pct_con_carencia\'])}% de los hogares del país vive en una vivienda con al menos una carencia estructural"',
    17: ('f"En Montevideo, la precariedad de la vivienda alcanza al {_f(_v(precariedad_nivel, \'pct_precariedad\', nivel_economico=\'1-Bajo\'))}% de los hogares del nivel económico bajo "'
         'f"y al {_f(_v(precariedad_nivel, \'pct_precariedad\', nivel_economico=\'5-Alto\'))}% del alto"'),
    18: '_b(precariedad_depto, \'departamento\', \'pct_precariedad\', \'Por departamento, la precariedad de la vivienda\')',
    19: 'f"En Montevideo, la diferencia de precariedad entre el nivel económico bajo y el alto es de {_f(brecha_precariedad)} puntos porcentuales"',
    20: 'f"La carencia estructural más frecuente es «{carencias_frecuentes.iloc[0][\'carencia\'].lower()}», presente en el {_f(carencias_frecuentes.iloc[0][\'pct_hogares\'])}% de los hogares"',
    21: 'f"El {_f(prevalencia_fies[\'moderada_o_severa\'])}% de los hogares vive inseguridad alimentaria moderada o severa, y el {_f(prevalencia_fies[\'severa\'])}% severa (calculado sobre la submuestra de hogares que respondió el módulo)"',
    22: ('f"La inseguridad alimentaria moderada o severa afecta al {_f(_v(inseguridad_quintil, \'pct_inseguridad\', quintil_ingreso=\'Quintil 1\'))}% de los hogares del quintil de menores ingresos "'
         'f"y al {_f(_v(inseguridad_quintil, \'pct_inseguridad\', quintil_ingreso=\'Quintil 5\'))}% del de mayores"'),
    23: ('f"La inseguridad alimentaria moderada o severa es de {_f(_v(inseguridad_region, \'pct_inseguridad\', region=\'Montevideo\'))}% en Montevideo "'
         'f"y de {_f(_v(inseguridad_region, \'pct_inseguridad\', region=\'Interior\'))}% en el interior"'),
    24: 'f"Entre el quintil 1 y el quintil 5 la diferencia de inseguridad alimentaria es de {_f(diferencia_quintiles)} puntos porcentuales"',
    25: ('f"La inseguridad alimentaria severa llega al {_f(_v(inseguridad_severa_quintil, \'pct_inseguridad\', quintil_ingreso=\'Quintil 1\'))}% en el quintil 1 "'
         'f"y al {_f(_v(inseguridad_severa_quintil, \'pct_inseguridad\', quintil_ingreso=\'Quintil 5\'))}% en el quintil 5"'),
    26: '_b(inseguridad_menores18, \'tiene_menores_18\', \'pct_inseguridad\', \'Según haya o no menores de 18 años en el hogar, la inseguridad alimentaria\')',
    27: '_b(inseguridad_menores6, \'tiene_menores_6\', \'pct_inseguridad\', \'Según haya o no niños de 0 a 5 años en el hogar, la inseguridad alimentaria\')',
    28: ('f"La tasa de actividad promedio del año fue {_f(tasas_nacionales[\'tasa_actividad\'])}%, la de empleo {_f(tasas_nacionales[\'tasa_empleo\'])}% "'
         'f"y la de desempleo {_f(tasas_nacionales[\'tasa_desempleo\'])}%"'),
    29: ('f"La tasa de empleo fue {_f(_v(tasas_sexo, \'tasa_empleo\', sexo_grupo=\'Hombre\'))}% entre los hombres y {_f(_v(tasas_sexo, \'tasa_empleo\', sexo_grupo=\'Mujer\'))}% entre las mujeres; "'
         'f"el desempleo, {_f(_v(tasas_sexo, \'tasa_desempleo\', sexo_grupo=\'Hombre\'))}% y {_f(_v(tasas_sexo, \'tasa_desempleo\', sexo_grupo=\'Mujer\'))}%"'),
    30: '_b(desempleo_depto, \'departamento\', \'pct_promedio\', \'La tasa de desempleo por departamento\')',
    31: 'f"La informalidad alcanza al {_f(_v(informalidad_sexo, \'pct_promedio\', sexo_grupo=\'Hombre\'))}% de los hombres ocupados y al {_f(_v(informalidad_sexo, \'pct_promedio\', sexo_grupo=\'Mujer\'))}% de las mujeres ocupadas"',
    32: '_b(informalidad_educacion, \'nivel_educativo\', \'pct_promedio\', \'Según el nivel educativo, la informalidad\')',
    33: 'f"El subempleo afecta al {_f(_v(subempleo_sexo, \'pct_promedio\', sexo_grupo=\'Hombre\'))}% de los hombres ocupados y al {_f(_v(subempleo_sexo, \'pct_promedio\', sexo_grupo=\'Mujer\'))}% de las mujeres ocupadas"',
    34: ('f"El desempleo juvenil (14 a 24 años) es de {_f(_v(tasas_edad_laboral, \'tasa_desempleo\', grupo_edad_laboral=\'Joven (14-24)\'))}%, "'
         'f"frente a {_f(_v(tasas_edad_laboral, \'tasa_desempleo\', grupo_edad_laboral=\'Resto\'))}% en el resto de la población activa"'),
    35: ('f"La proporción de asalariados (empleados) va de {_f(situacion_por_sector[\'Empleado\'].min())}% en el sector {_res.nombre_sector(situacion_por_sector[\'Empleado\'].idxmin())} "'
         'f"a {_f(situacion_por_sector[\'Empleado\'].max())}% en el sector {_res.nombre_sector(situacion_por_sector[\'Empleado\'].idxmax())}"'),
    36: '_b(prevalencia_delito, \'tipo_delito\', \'pct\', \'En el último mes, la proporción de personas víctimas de cada tipo de delito\')',
    37: 'f"Fueron víctimas de algún delito en el último mes el {_f(_v(victimizacion_sexo, \'pct\', sexo_grupo=\'Hombre\'))}% de los hombres y el {_f(_v(victimizacion_sexo, \'pct\', sexo_grupo=\'Mujer\'))}% de las mujeres"',
    # Los departamentos con menos de 30 víctimas no entran en la comparación
    # de extremos: con 0 casos sobre 694 personas el «0,0%» no es un dato.
    38: ('(_b(victimizacion_depto, \'departamento\', \'pct\', \'Por departamento, la victimización en el último mes\') '
         'if not len(pocos_casos_depto) else '
         '(f"Entre los {len(victimizacion_depto_confiable)} departamentos con al menos 30 víctimas en la muestra, " '
         '+ _b(victimizacion_depto_confiable, \'departamento\', \'pct\', \'la victimización en el último mes\') '
         '+ f"; en los otros {len(pocos_casos_depto)} la estimación no es confiable por tener menos de 30 víctimas" '
         'if len(victimizacion_depto_confiable) >= 2 else '
         'f"Solo {len(victimizacion_depto_confiable)} departamento reúne 30 víctimas o más en la muestra, así que la victimización no se compara entre departamentos"))'),
    39: '_b(comunicacion_delito, \'tipo_delito\', \'pct\', \'Entre las víctimas, la comunicación a la policía\')',
    40: '_b(denuncia_delito, \'tipo_delito\', \'pct\', \'Entre las víctimas, la denuncia formal\')',
    41: ('_res.en_cuantos(int((comunicacion_delito.set_index(\'tipo_delito\')[\'pct\'] > denuncia_delito.set_index(\'tipo_delito\')[\'pct\']).sum()), '
         'len(comunicacion_delito), "tipos de delito") + ", más víctimas comunican el hecho a la policía de las que lo denuncian formalmente"'),
    42: '_b(violencia_delito, \'tipo_delito\', \'pct\', \'La proporción de casos con violencia\')',
}


BLOQUE_A_MEDIDA = "Métricas y cruces a medida"


def celdas_resumen_analitico(metricas: list[int], frases_extra: dict[int, str] | None = None) -> list[Celda]:
    """La sección que cierra el informe: encabezado, una celda de código que
    arma el resumen por bloque desde las variables de cada métrica presente
    (salida en markdown; el código no se ve en el informe sin código), y la
    lista de fuentes de consulta de los bloques presentes.

    `frases_extra`: {número de la celda a medida: expresión de Python}, con
    el mismo contrato que `_RESUMEN_POR_METRICA` — la escribe el agente en
    el archivo `--extra` junto con la celda, sobre las variables de esa
    celda, y se evalúa acá bajo el bloque «Métricas y cruces a medida». Así
    las métricas a medida entran al resumen con sus cifras reales, sin que
    nadie las transcriba después de ejecutar."""
    elegidas = sorted(set(metricas))
    lineas = [
        "from IPython.display import Markdown as _Markdown, display as _display",
        "from encuesta_hogares import resumen as _res",
        "_f, _v, _b = _res.fmt, _res.valor, _res.brecha",
        "_frases = {}",
    ]
    for bloque, (rango, nombre) in verificacion_catalogo.BLOQUES.items():
        for numero in elegidas:
            if numero in rango and numero in _RESUMEN_POR_METRICA:
                lineas += [
                    "try:",
                    f"    _frases.setdefault({nombre!r}, []).append({_RESUMEN_POR_METRICA[numero]})",
                    "except Exception as _e:",
                    f"    raise RuntimeError(f\"resumen de la métrica {numero}: {{_e}}\") from _e",
                ]
    for numero, expresion in sorted((frases_extra or {}).items()):
        lineas += [
            "try:",
            f"    _frases.setdefault({BLOQUE_A_MEDIDA!r}, []).append({expresion})",
            "except Exception as _e:",
            f"    raise RuntimeError(f\"resumen de la métrica a medida {numero}: {{_e}}\") from _e",
        ]
    lineas.append("_display(_Markdown(_res.armar_markdown(_frases)))")
    celdas = [
        Celda(markdown="## Resumen analítico final\n\nLas cifras de esta sección son las mismas que muestran "
                       "las gráficas de cada métrica.", codigo="\n".join(lineas)),
    ]
    bloques_presentes = [b for b, (rango, _n) in verificacion_catalogo.BLOQUES.items() if any(n in rango for n in elegidas)]
    fuentes = fuentes_de_consulta(bloques_presentes)
    if fuentes:
        celdas.append(Celda(markdown="### Fuentes de consulta para alineación de métricas\n\n" + "\n".join(f"- {f}" for f in fuentes)))
    return celdas
