"""Configuración: rutas, nombres de archivo y mapeos de clasificación.

Los nombres de columna (HOGARES_COLUMNS, PERSONAS_COLUMNS,
CONDICIONES_VIVIENDA_COLUMNS) reflejan los códigos de variable de la ECH 2019.
Antes de usar datos de otro año, el agente (ver .claude/agents/encuesta-hogares.md)
verifica con pyreadstat que esos códigos sigan existiendo y con el mismo
significado; si algo cambió, actualiza este archivo y lo deja documentado en
docs/METODOLOGIA.md.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"

# Cuánto espera un formulario a que la persona responda antes de tratarlo
# como salida del flujo (30 minutos). Un solo lugar: hasta la v0.13.6 el
# mismo 1800 estaba escrito en arranque.py y dos veces en formularios.py.
TIMEOUT_FORMULARIO_SEGUNDOS = 1800

# Cada año de datos vive en su propia subcarpeta: data/{año}/H_....sav y
# data/{año}/P_....sav. El agente crea esa subcarpeta antes de pedirle al
# usuario que guarde los archivos ahí (ver .claude/agents/encuesta-hogares.md).


# No hay ninguna constante "archivo de Hogares por defecto" a propósito.
# Existió (`HOGARES_FILE`/`PERSONAS_FILE`, resolviendo "el .sav más
# reciente de data/") y era una trampa que nadie usaba: desde que el INE
# pasó al CSV combinado (2023 en adelante), el único año con .sav es 2019,
# así que `load_hogares()` sin argumentos cargaba 2019 en silencio aunque
# hubiera años más nuevos instalados — un análisis del año equivocado sin
# ningún error, en un proyecto donde la fidelidad estadística es lo
# innegociable. El año se elige siempre explícito: `hogares_csv_file(anio)`
# para 2023+, o los `H_*.sav`/`P_*.sav` de `data/{año}/` para 2019.

# Año de referencia: los datos con los que se construyó y validó todo el
# análisis original. Nunca se borran ni se mueven — sirven para comparar
# la estructura de cualquier año nuevo contra un caso ya conocido y
# confiable, además de contra la lista fija de columnas de más abajo.
REFERENCE_YEAR = 2019


def _reference_file(prefix: str) -> Path:
    carpeta = DATA_DIR / str(REFERENCE_YEAR)
    candidatos = sorted(carpeta.glob(f"{prefix}_*.sav"))
    return candidatos[0] if candidatos else carpeta / f"{prefix}_{REFERENCE_YEAR}.sav"


def reference_hogares_file() -> Path:
    return _reference_file("H")


def reference_personas_file() -> Path:
    return _reference_file("P")

# Columnas relevantes de la base de Hogares (H) y su nuevo nombre legible
HOGARES_COLUMNS = {
    "numero": "id_hogar",
    "nomdpto": "departamento",
    "nombarrio": "barrio",
    "estred13": "estrato_tipo",  # estrato socioeconómico 1 (bajo) a 5 (alto)
    "d25": "total_personas",
    # --- Ampliación: brecha digital, pobreza e ingresos del hogar ---
    "d21_16": "tiene_internet",       # 1=Sí/2=No/99=Sin dato
    "d21_16_1": "internet_fija",
    "d21_16_2": "internet_movil",
    "d21_15": "tiene_pc",
    "d21_21": "tiene_streaming",
    "pobre06": "pobre",               # 0=No pobre, 1=Pobre
    "indigente06": "indigente",       # 0=No indigente, 1=Indigente
    "YSVL": "ingreso_hogar",          # ingreso del hogar sin valor locativo
    "ht3": "menores_14",
    "ht5": "ocupados_hogar",
    # --- Ampliación: hogares (sin tecnología) y brecha digital "real" ---
    "d9": "cantidad_habitaciones",         # excluye baño y cocina (definición CEPAL de "cuarto")
    "d21_15_5": "tiene_tablet_ibirapita",  # 1=Sí/2=No/99=Sin dato
    # Ponderador anual de expansión muestral (idéntico para todas las personas
    # de un mismo hogar, verificado). Hasta ahora el proyecto solo ponderaba
    # FIES/Empleo/Victimización (que traen su propio ponderador de módulo) y
    # calculaba todo lo demás (pobreza, hacinamiento, tipos de hogar, vivienda,
    # territorio, brecha digital) como proporción simple sin ponderar - un
    # sesgo real: con datos de 2019, la pobreza da 4.79% sin ponderar contra
    # 5.87% ponderada, casi 1.1 puntos porcentuales de diferencia. Ver
    # docs/METODOLOGIA.md, sección de ponderación.
    "pesoano": "ponderador_hogar",
}

# Variables de estado estructural de la vivienda (todas 1=Sí/2=No/99=Sin dato).
CONDICIONES_VIVIENDA_COLUMNS = {
    "c5_1": "humedad_techos",
    "c5_2": "goteras",
    "c5_3": "muros_agrietados",
    "c5_4": "puertas_ventanas_deterioradas",
    "c5_5": "grietas_pisos",
    "c5_6": "caida_revoque",
    "c5_7": "cielorraso_desprendido",
    "c5_8": "poca_luz_solar",
    "c5_9": "escasa_ventilacion",
    "c5_10": "se_inunda",
    "c5_11": "peligro_derrumbe",
    "c5_12": "humedad_cimientos",
}
HOGARES_COLUMNS.update(CONDICIONES_VIVIENDA_COLUMNS)

# Columnas relevantes de la base de Personas (P) y su nuevo nombre legible
PERSONAS_COLUMNS = {
    "numero": "id_hogar",
    "nper": "id_persona",
    "e26": "sexo",
    "e27": "edad",
    "PT1": "ingresos_personales",
    "pobpcoac": "condicion_actividad_cod",
    # "e60" (tenencia de celular por persona) se dejó de mapear en la
    # limpieza final: nada la usaba y el INE sacó la pregunta desde 2024.
    "e30": "parentesco_jefe",        # relación de parentesco con el jefe/a de hogar (14 categorías)
    # OJO: "pesoano" (ponderador) a propósito NO se mapea acá, aunque
    # también está en este archivo con el mismo valor que en Hogares
    # (verificado). Si se mapeara en los dos lados, cualquier merge entre
    # Hogares y Personas por id_hogar duplicaría la columna como
    # "ponderador_hogar_x"/"_y". El ponderador viaja siempre desde el lado
    # de Hogares (ver HOGARES_COLUMNS) y llega a las tablas de personas
    # vía merge (ver preprocessing.merge_personas) - nunca se lee dos veces.
}

# ============================================================================
# Hogares/Personas a partir de un único CSV combinado (formato usado desde
# 2024 en adelante: el INE dejó de publicar H_....sav y P_....sav por
# separado y pasó a publicar un solo archivo ECH_{año}.csv, una fila por
# persona, con las columnas de hogar repetidas para cada persona del mismo
# hogar). Los códigos de columna también cambiaron de nombre en varios
# casos, y algunas variables se discontinuaron — todo esto se verificó
# contra el diccionario oficial "Diccionario ECH 2024.pdf" y confirmado con
# el usuario (ver .claude/agents/encuesta-hogares.md, paso 3):
#
# - id_hogar viene en "ID" (antes "numero"); departamento en "nom_dpto"
#   (antes "nomdpto"); estrato en "ESTRED13" (antes "estred13", misma
#   escala 1-5 para Montevideo); indigencia en "indig06" (antes
#   "indigente06"); menores de 14 en "d24" (antes "ht3").
# - "barrio" en este formato es un CÓDIGO NUMÉRICO, no el nombre del barrio
#   (el .sav de 2019 traía "nombarrio" como texto aparte; ese campo no
#   existe en el CSV combinado). El agente no tiene forma de traducir ese
#   código a un nombre real, así que las gráficas de este año identifican
#   cada barrio por su número — decisión confirmada con el usuario.
# - "ocupados_hogar" (antes "ht5") ya no viene precalculado a nivel de
#   hogar: se calcula aparte contando, por hogar, cuántas personas tienen
#   condicion_actividad_cod == 2 (Ocupados) — ver
#   data_loader.load_hogares_personas_csv().
# - La pregunta sobre tenencia de celular (e60) no está en el
#   cuestionario desde 2024 (confirmado con el usuario en su momento);
#   en la limpieza final se dejó de mapear también para .sav, porque
#   ninguna métrica del catálogo la usaba.
HOGARES_COLUMNS_CSV = {
    "ID": "id_hogar",
    "nom_dpto": "departamento",
    "barrio": "barrio",
    "ESTRED13": "estrato_tipo",
    "d25": "total_personas",
    "d21_16": "tiene_internet",
    "d21_16_1": "internet_fija",
    "d21_16_2": "internet_movil",
    "d21_15": "tiene_pc",
    "d21_21": "tiene_streaming",
    "pobre06": "pobre",
    "indig06": "indigente",
    "YSVL": "ingreso_hogar",
    "d24": "menores_14",
    "d9": "cantidad_habitaciones",
    "d21_15_5": "tiene_tablet_ibirapita",
    "W_ANO": "ponderador_hogar",  # mismo ponderador que "pesoano" en 2019, solo cambia el nombre
    # El INE reemplazó la metodología de pobreza/ingreso (canasta de 2006 por
    # la de 2017) — verificado contra los datos reales: 2025 ya no trae
    # pobre06/indig06/YSVL, solo pobre17/indig17/YDA_SVL. 2024 resultó ser
    # un año de transición: trae LAS DOS a la vez (no "nunca las dos juntas"
    # como se pensó en un primer momento) — confirmado con el usuario que
    # ante esa situación se prefiere la metodología nueva (canasta 2017)
    # para 2024 también, no solo para 2025 en adelante, porque da
    # comparabilidad hacia adelante entre 2024 y 2025 (2019 queda como el
    # único año con la metodología vieja, sin alternativa — se documenta
    # como diferencia metodológica, igual que ya se hace con Vivienda entre
    # 12 y 4 carencias). Ver `config.PREFERENCIA_METODOLOGIA_HOGARES` y
    # `data_loader.load_hogares_personas_csv`, que aplican esa preferencia.
    # YDA_SVL verificado con los datos reales de 2025: mediana $64.309,
    # mismo orden de magnitud que la mediana de ingreso de hogar que
    # publicó el propio INE para 2025 ($72.600, cuarto trimestre) — la
    # diferencia es esperable, no un desvío de criterio (nuestro dato es el
    # promedio del año completo contra un trimestre puntual, además de la
    # exclusión de valor locativo que ya tenía YSVL). pobre17/indig17 no
    # son una inferencia propia — son la clasificación de pobreza que ya
    # calcula el INE con la metodología vigente, solo cambió el nombre de
    # la columna.
    "pobre17": "pobre",
    "indig17": "indigente",
    "YDA_SVL": "ingreso_hogar",
}

# Cuando un archivo trae las dos variantes de una misma columna a la vez
# (año de transición — pasó de verdad con 2024, ver la nota de arriba),
# `data_loader.load_hogares_personas_csv` descarta la columna vieja (clave)
# y se queda con la nueva (valor) — decisión confirmada con el usuario, no
# tomada en silencio por el código.
PREFERENCIA_METODOLOGIA_HOGARES = {
    "pobre06": "pobre17",
    "indig06": "indig17",
    "YSVL": "YDA_SVL",
}

# Solo las 4 preguntas de "problemas de la vivienda" (módulo C5) que el INE
# siguió relevando durante todo 2024 — las otras 8 se discontinuaron a
# partir del segundo semestre (marcadas con (*) en el diccionario oficial),
# así que no hay dato completo de año para ellas. Se reutilizan los mismos
# nombres legibles que CONDICIONES_VIVIENDA_COLUMNS para que el resto del
# código (CONDICION_VIVIENDA_LABELS, condiciones_vivienda_por, etc.) no
# necesite saber que es un subconjunto.
CONDICIONES_VIVIENDA_COLUMNS_CSV = {
    "c5_2": "goteras",
    "c5_10": "se_inunda",
    "c5_11": "peligro_derrumbe",
    "c5_12": "humedad_cimientos",
}
HOGARES_COLUMNS_CSV.update(CONDICIONES_VIVIENDA_COLUMNS_CSV)

PERSONAS_COLUMNS_CSV = {
    "ID": "id_hogar",
    "nper": "id_persona",
    "e26": "sexo",
    "e27": "edad",
    "PT1": "ingresos_personales",
    "POBPCOAC": "condicion_actividad_cod",
    "e30": "parentesco_jefe",
    # Mismo motivo que en PERSONAS_COLUMNS: W_ANO a propósito no se mapea
    # acá, para no duplicar la columna al mergear con el lado de Hogares.
}


def hogares_csv_file(anio: int | str) -> Path:
    """Ruta al archivo combinado de Hogares/Personas de un año.

    El nombre cambió entre años: hasta 2024 es exactamente `ECH_{año}.csv`;
    desde 2025 el INE lo publica como `ECH_{año}_implantacion.csv` —
    verificado contra los archivos reales que bajó el usuario, no una
    suposición. Se prueban los patrones "implantación" primero (en ese
    orden) y se usa el que exista en disco; si ninguno existe, se cae al
    patrón simple (exista o no todavía) — así un año recién creado, sin
    descargar, sigue mostrando un nombre de archivo esperado en vez de
    romper. `datos_disponibles()` reutiliza esta misma función como
    fuente única de verdad, para que los dos no puedan quedar
    desincronizados.

    El archivo real de 2023 vino con el orden de palabras invertido —
    `ECH_implantacion_2023.csv`, no `ECH_2023_implantacion.csv` — mismo
    tipo de inconsistencia de nombres del INE que ya obliga a
    `empleo_files()` a reconocer `ECH_MM_AA.csv` y `ECH_MM_AAAA.csv`
    dentro del mismo año. Sin esto, el archivo quedaba invisible para el
    código: `hogares_csv_file(2023)` devolvía una ruta que no existe, y
    como para 2023 tampoco hay `H_*.sav`/`P_*.sav`, el año entero parecía
    no tener datos de Hogares/Personas (la base de todo el análisis
    estándar) pese a que el archivo estaba ahí con el nombre real.
    """
    carpeta = DATA_DIR / str(anio)
    for nombre in (f"ECH_{anio}_implantacion.csv", f"ECH_implantacion_{anio}.csv"):
        candidato = carpeta / nombre
        if candidato.exists():
            return candidato
    return carpeta / f"ECH_{anio}.csv"

NIVEL_ECONOMICO_LABELS = {
    1: "1-Bajo",
    2: "2-Medio-Bajo",
    3: "3-Medio",
    4: "4-Medio-Alto",
    5: "5-Alto",
}
NIVEL_ECONOMICO_DEFAULT = "6-No Definido"

SEXO_LABELS = {1: "1-Hombre", 2: "2-Mujer"}
SEXO_DEFAULT = "3-Otro"

EDAD_BINS = [0, 15, 65, float("inf")]
EDAD_LABELS = ["1-Niños-Jovenes", "2-Adultos", "3-Adultos_mayores"]

# Corrige un problema de codificación presente en las etiquetas de barrio del
# archivo .sav original: el caracter 'ñ' puede quedar guardado como '¦' (U+00A6).
MOJIBAKE_FIX = {"¦": "ñ"}

# Variables 1=Sí/2=No/99=Sin dato -> booleano (99 queda como NaN, no se asume).
SI_NO_MAP = {1.0: True, 2.0: False}

# TV cable salió del proyecto por completo: era el eje del análisis
# original de 2019 y quedó como herencia cuando el foco pasó a ser la
# conectividad. Medir "acceso a TV cable" no dice nada sobre si un hogar
# está conectado — decisión del dueño del proyecto, ver CHANGELOG 0.9.0.
TECNOLOGIAS_LABELS = {
    "tiene_internet": "Internet",
    "tiene_pc": "Computadora",
    "tiene_streaming": "Streaming",
}

# pobpcoac (Población por condición de actividad) colapsado a 3 grupos.
# La categoría 1 (Menores de 14 años) se excluye: no aplica a la fuerza laboral.
POBPCOAC_GRUPOS = {
    2.0: "Ocupados",
    3.0: "Desocupados",
    4.0: "Desocupados",
    5.0: "Desocupados",
    6.0: "Inactivos",
    7.0: "Inactivos",
    8.0: "Inactivos",
    9.0: "Inactivos",
    10.0: "Inactivos",
    11.0: "Inactivos",
}

# ============================================================================
# Hogares (composición, sin ninguna variable de tecnología) y Brecha Digital
# (con marco internacional, más allá de "tiene/no tiene"). Fuentes: CEPAL/
# CELADE (jefatura de hogar, tipos de hogar, hacinamiento, dependencia
# demográfica), UIT/ITU + A4AI ("Meaningful Connectivity"), y el paper de
# Muñoz (UdelaR, Revista de Ciencias Sociales) que aplica el enfoque de
# cohorte generacional a esta misma encuesta. Ver
# .claude/agents/encuesta-hogares.md para el detalle y los links.
# ============================================================================

# Relación de parentesco con el jefe/a de hogar (e30) — 14 categorías del
# cuestionario, usadas para clasificar el tipo de hogar (ver
# preprocessing.clasificar_tipo_hogar). Mismos códigos en .sav y CSV.
PARENTESCO_LABELS = {
    1: "Jefe/a de hogar",
    2: "Esposo/a o compañero/a",
    3: "Hijo/a de ambos",
    4: "Hijo/a solo del jefe/a",
    5: "Hijo/a solo del esposo/a o compañero/a",
    6: "Yerno/nuera",
    7: "Padre/madre",
    8: "Suegro/a",
    9: "Hermano/a",
    10: "Cuñado/a",
    11: "Nieto/a",
    12: "Otro pariente",
    13: "Otro no pariente",
    14: "Servicio doméstico o familiar del mismo",
}

# Códigos de e30 usados para clasificar el tipo de hogar (taxonomía CELADE):
# núcleo familiar básico (cónyuge o hijos), parientes fuera del núcleo, y
# no parientes. El jefe/a (código 1) no entra en ningún grupo — está
# siempre presente por definición y no aporta información de clasificación.
PARENTESCO_CODIGOS_NUCLEO = {2, 3, 4, 5}
PARENTESCO_CODIGOS_EXTENSO = {6, 7, 8, 9, 10, 11, 12}
PARENTESCO_CODIGOS_NO_PARIENTE = {13, 14}

# Umbral de hacinamiento: más de 2 personas por cuarto (cantidad_habitaciones,
# que ya excluye baño y cocina — ver HOGARES_COLUMNS). Es el criterio clásico
# usado históricamente por INE/CEPAL para la región - existe un método más
# reciente (UE/OCDE, adoptado por CEPAL) que ajusta el umbral según la
# composición del hogar en vez de un número fijo; no se implementó todavía
# por su complejidad, queda como mejora futura documentada en
# docs/METODOLOGIA.md.
UMBRAL_HACINAMIENTO = 2.0

# Cortes generacionales estándar (año de nacimiento), para aproximar
# "cohorte" a partir de la edad del jefe/a de hogar y el año de la encuesta
# (ver preprocessing.compute_cohorte_generacional). Es una aproximación de
# corte transversal - agrupa por año de nacimiento estimado dentro de esta
# única corrida, no sigue a las mismas personas a través de varios años
# como sí hace el estudio de referencia (Muñoz, UdelaR, con la ECH
# 2009-2019 en panel).
COHORTE_BINS = [-float("inf"), 1945, 1964, 1980, 1996, float("inf")]
COHORTE_LABELS = [
    "Generación silenciosa (hasta 1945)",
    "Baby boomers (1946-1964)",
    "Generación X (1965-1980)",
    "Millennials (1981-1996)",
    "Generación Z (1997 en adelante)",
]

# ============================================================================
# FIES (seguridad alimentaria) — solo disponible para algunos años, y solo
# para una submuestra de hogares (no el total). A diferencia de Hogares y
# Personas, viene en CSV, no en .sav.
# ============================================================================


def fies_file(anio: int | str) -> Path:
    """Ruta al archivo FIES de un año determinado (`data/{año}/base_FIES_{año}.csv`).
    No tiene resolución automática al "año más reciente" a propósito: FIES no
    existe para todos los años, así que el año siempre se pasa explícito.
    """
    carpeta = DATA_DIR / str(anio)
    candidatos = sorted(carpeta.glob(f"base_FIES_{anio}.csv"))
    return candidatos[0] if candidatos else carpeta / f"base_FIES_{anio}.csv"


def datos_disponibles(anio: int | str) -> dict:
    """Qué tipos de datos existen para un año determinado, para que el agente
    sepa qué ofrecerle al usuario (ver .claude/agents/encuesta-hogares.md).
    "empleo" requiere los 12 archivos mensuales completos, no unos pocos —
    con menos de 12 no se puede promediar el año correctamente.
    """
    carpeta = DATA_DIR / str(anio)
    return {
        "hogares": bool(list(carpeta.glob("H_*.sav")) or hogares_csv_file(anio).exists()),
        "fies": fies_file(anio).exists(),
        "empleo": all(archivo.exists() for archivo in empleo_files(anio)),
        "seguridad": victimizacion_file(anio).exists(),
    }


# Solo las columnas cuyo significado se verificó contra el diccionario de
# datos oficial del INE (catálogo ANDA, ficha URY-INE-ECH-2024-v02,
# archivo base_FIES_2024) — deliberadamente no incluye HT19 ni ing_pc
# todavía: HT19 es "cantidad de personas SIN servicio doméstico" (una
# definición distinta de total_personas, no intercambiable sin más
# análisis) e ing_pc no se necesitó para ninguna métrica del catálogo por
# ahora.
FIES_COLUMNS = {
    "ID": "id_hogar",
    "region": "region_cod",
    "quintiles": "quintil_ingreso",
    "menores18": "tiene_menores_18",   # 0/1: hogar con menores de 18 años
    "menores6": "tiene_menores_6",     # 0/1: hogar con niños de 0 a 5 años
    "prob.mod.h": "prob_inseguridad_moderada",
    "prob.sev.h": "prob_inseguridad_severa",
    "w": "ponderador_fies",
}

# Confirmado cruzando IDs contra ECH_2024.csv: region=1 son 100% hogares de
# Montevideo.
REGION_FIES_LABELS = {1: "Montevideo", 2: "Interior"}

# Umbral estándar de la metodología FIES (FAO): un hogar se clasifica en una
# categoría de inseguridad alimentaria cuando su probabilidad (prob.mod.h /
# prob.sev.h, un puntaje continuo de un modelo Rasch) supera 0.5.
UMBRAL_FIES = 0.5

# ============================================================================
# Empleo (ECH_seguimiento) — panel rotativo mensual, no un corte anual como
# Hogares. Cada hogar permanece en el panel 6 meses seguidos, así que las
# métricas se calculan mes a mes (ponderadas por `w`) y se promedian entre
# los 12 meses — nunca juntando los 12 CSV en un solo pool antes de
# ponderar (ver .claude/agents/encuesta-hogares.md, sección de empleo).
# ============================================================================


def empleo_files(anio: int | str) -> list[Path]:
    """Los 12 archivos mensuales de un año determinado, ordenados de enero a
    diciembre. `anio` es el año completo (ej. 2024).

    El patrón de nombre cambió entre años: hasta 2024 el INE usa los
    últimos dos dígitos del año (`ECH_01_24.csv`); desde 2025 usa el año
    completo (`ECH_01_2025.csv`) — verificado contra los archivos reales
    que bajó el INE para 2025, no una suposición. Se prueba el patrón
    largo primero y se usa si existe en disco; si no, se cae al patrón
    corto (exista o no todavía — así un año recién creado, sin descargar,
    sigue mostrando un nombre de archivo esperado en vez de romper).
    """
    carpeta = DATA_DIR / str(anio)
    sufijo_anio = str(anio)[-2:]
    archivos = []
    for mes in range(1, 13):
        patron_largo = carpeta / f"ECH_{mes:02d}_{anio}.csv"
        patron_corto = carpeta / f"ECH_{mes:02d}_{sufijo_anio}.csv"
        archivos.append(patron_largo if patron_largo.exists() else patron_corto)
    return archivos


# Para mostrarle el mes (columna `mes`, 1-12) a un lector en vez del número
# crudo — ej. en el chequeo de "meses cubiertos" de la preparación de datos
# de Empleo. Es una conversión de calendario universal, no depende de
# ninguna fuente del INE ni de la configuración regional/locale del sistema
# (que es frágil entre Windows/Mac y entre computadoras) — encontrado en una
# corrida real donde ese chequeo se imprimió como
# `[np.int64(1), np.int64(2), ...]` en vez de nombres de mes legibles.
MESES_LABELS = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


# Solo las columnas cuyo significado se verificó contra el diccionario de
# datos oficial del INE (archivo ECH_seguimiento_2024) y/o contra los datos
# reales. POBPCOAC usa los mismos códigos que HOGARES/PERSONAS de 2019 (ver
# POBPCOAC_GRUPOS más abajo) — se reutiliza el mismo mapeo.
EMPLEO_COLUMNS = {
    "ID": "id_hogar",
    "nper": "id_persona",
    "mes": "mes",
    "nom_dpto": "departamento",
    "e26": "sexo",
    "e27": "edad",
    "POBPCOAC": "condicion_actividad_cod",
    "SIT_OCUP": "situacion_ocupacional",     # ya viene con etiquetas de texto
    "SECTOR_F": "sector_formalidad",         # ya viene con etiquetas de texto
    "NIV_EDU": "nivel_educativo",            # ya viene con etiquetas de texto
    "INFORMAL": "es_informal",               # 0/1 — solo válido si condicion_actividad == "Ocupados"
    "SUBEMPLEO": "es_subempleo",             # 0/1 — solo válido si condicion_actividad == "Ocupados"
    "W": "ponderador_empleo",                # ponderador MENSUAL, no anual
    # INFORMAL, SECTOR_F y SIT_OCUP desaparecieron de los archivos mensuales
    # desde 2025 (verificado contra los datos reales que bajó el usuario, no
    # una suposición). f82 ("aporte a fondo de pensión") sigue estando, y es
    # la variable que usa `employment_restrictions()` del paquete oficial de
    # R para la ECH (autoría conjunta INE, github.com/calcita/ech, archivo
    # R/employment.R) para calcular informalidad — el criterio estándar en
    # la región: no aportar a la seguridad social = informal. Verificado con
    # los datos reales de enero 2025: f82==2 (no aporta) da 21.8% de
    # informalidad entre ocupados, muy cerca del 22.8% que el propio INE
    # publicó para todo 2025 (ver `preprocessing.prepare_empleo`, que hace
    # el cálculo real). SECTOR_F y SIT_OCUP siguen sin variable de
    # reemplazo identificada — no se les asume ninguna.
    "f82": "aporta_seguridad_social",        # 0/1/2 — 1=Sí aporta, 2=No aporta, 0=no aplica (fuera de Ocupados)
}

# Definición estándar de "población joven" para indicadores de empleo (14 a
# 24 años) — es la que reportan INE/prensa para el desempleo juvenil de
# Uruguay. Distinta de EDAD_BINS/EDAD_LABELS de más abajo, que clasifica
# edad para el análisis de Hogares con otro criterio (niños/adultos/adultos
# mayores) y no aplica acá.
EDAD_JOVEN_MIN = 14
EDAD_JOVEN_MAX = 24

# ============================================================================
# Seguridad y Victimización (ECH_VICTIMIZACION_S2). A diferencia de Empleo,
# no es un panel rotativo mensual — es un corte del segundo semestre, se
# pondera directo por W_SEM sin promediar meses. El archivo no trae
# departamento propio: hay que cruzarlo por ID contra los meses de
# julio-diciembre del mismo año (ver data_loader.load_victimizacion).
# ============================================================================


def victimizacion_file(anio: int | str) -> Path:
    """Ruta al archivo de victimización de un año determinado
    (`data/{año}/ECH_VICTIMIZACION_S2_{año}.csv`)."""
    carpeta = DATA_DIR / str(anio)
    candidatos = sorted(carpeta.glob(f"ECH_VICTIMIZACION_S2_{anio}.csv"))
    return candidatos[0] if candidatos else carpeta / f"ECH_VICTIMIZACION_S2_{anio}.csv"


VICTIMIZACION_COLUMNS = {
    "ID": "id_hogar",
    "nper": "id_persona",
    "e26": "sexo",
    "v3": "v3", "v3_4": "v3_4", "v3_6": "v3_6", "v3_8": "v3_8",
    "v4": "v4", "v4_4": "v4_4", "v4_6": "v4_6", "v4_8": "v4_8",
    "v5": "v5", "v5_4": "v5_4", "v5_6": "v5_6", "v5_8": "v5_8",
    "v6": "v6", "v6_2": "v6_2", "v6_4": "v6_4",
    "v7": "v7", "v7_4": "v7_4", "v7_6": "v7_6",
    "W_SEM": "ponderador_victimizacion",
}

# Cada tipo de delito, con sus columnas de seguimiento propias — no todas
# tienen la misma estructura de sub-preguntas: "violencia" solo se pregunta
# para v3/v4/v5 (delitos con contacto directo), no para v6 (estafa) ni v7
# (robo/asalto en la calle) — verificado contra el diccionario del INE, no
# es un descuido nuestro, así viene el cuestionario. v1 (percepción de
# seguridad, escala de 6 niveles) queda deliberadamente afuera del catálogo:
# no hay diccionario de valores publicado para esa variable en ningún
# material del INE, así que no se puede etiquetar con confianza todavía.
TIPOS_DELITO = {
    "v3": {"nombre": "Robo total de vehículo", "comunicacion": "v3_6", "denuncia": "v3_8", "violencia": "v3_4"},
    "v4": {"nombre": "Robo de objetos del vehículo", "comunicacion": "v4_6", "denuncia": "v4_8", "violencia": "v4_4"},
    "v5": {"nombre": "Robo en la vivienda", "comunicacion": "v5_6", "denuncia": "v5_8", "violencia": "v5_4"},
    "v6": {"nombre": "Estafa", "comunicacion": "v6_2", "denuncia": "v6_4", "violencia": None},
    "v7": {"nombre": "Robo o asalto fuera de la vivienda", "comunicacion": "v7_4", "denuncia": "v7_6", "violencia": None},
}

CONDICION_VIVIENDA_LABELS = {
    "humedad_techos": "Humedad en techos",
    "goteras": "Goteras en techos",
    "muros_agrietados": "Muros agrietados",
    "puertas_ventanas_deterioradas": "Puertas/ventanas en mal estado",
    "grietas_pisos": "Grietas en pisos",
    "caida_revoque": "Caída de revoque",
    "cielorraso_desprendido": "Cielorrasos desprendidos",
    "poca_luz_solar": "Poca luz solar",
    "escasa_ventilacion": "Escasa ventilación",
    "se_inunda": "Se inunda cuando llueve",
    "peligro_derrumbe": "Peligro de derrumbe",
    "humedad_cimientos": "Humedad en cimientos",
}
