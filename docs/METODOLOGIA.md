# Metodología: cómo se construyó (y se debe mantener) este análisis

Este documento resume todo lo aprendido durante la construcción del análisis
original (ECH 2019, Montevideo), diseñado por el dueño del proyecto, para
que se pueda reproducir con la misma calidad en cualquier año futuro. No
es teoría abstracta: cada regla acá existe porque en el proyecto original
se encontró un problema concreto, se corrigió, y se busca evitar
repetirlo.

Las fuentes académicas e institucionales que respaldan cada métrica y cada
tipo de gráfica están consolidadas en [`BIBLIOGRAFIA.md`](BIBLIOGRAFIA.md)
— consultarlo antes de buscar una fuente nueva, puede que ya esté citada.

Este documento reúne los principios y reglas (qué es correcto o
incorrecto, y por qué) — para los procedimientos paso a paso ver
[`FLUJO_DE_TRABAJO.md`](FLUJO_DE_TRABAJO.md) (verificación, generación
del PDF, publicación, cómo manejar un año de datos nuevo) y, para cómo
justificar el tipo de gráfica elegido en cada métrica, ver
[`CONVENCIONES_DE_GRAFICAS.md`](CONVENCIONES_DE_GRAFICAS.md).

## 1. Estructura estándar del análisis

La estructura es fija y la arma `notebook_builder.construir_celdas_notebook`,
no el modelo durante la corrida. Antes cada informe salía distinto: la
introducción la escribía el modelo, y las métricas aparecían como una lista
plana en el orden en que la persona las había marcado, sin nada que dijera a
qué tema pertenecía cada una.

1. **Introducción**: qué se analizó, de dónde salen los datos, cuántas
   métricas trae y en qué temas. Texto fijo, idéntico corrida a corrida.
2. **Preparación de datos**: cargar Hogares y Personas, filtrar a Montevideo,
   clasificar nivel económico. Infraestructura, sin contenido temático.
3. **Un tramo por tema elegido** (Brecha Digital, Hogares, Territorio,
   Vivienda, y — si corresponde — Seguridad Alimentaria, Empleo, Seguridad y
   Victimización), en el orden del catálogo y no en el de selección. Cada
   tramo abre con el nombre del tema, qué mide, y **los términos del INE que
   usan varias de sus métricas**; después va lo que ese tema necesite cargar
   aparte (Empleo y Seguridad tienen su propio archivo; Brecha Digital, su
   panorama de conectividad), y después sus métricas.
4. **Nota metodológica**: qué significa que un porcentaje esté "ponderado".
   Va al final porque es metodología: estaba abriendo el informe, que era lo
   primero que leía quien lo recibía.
5. **Resumen analítico final**, organizado por los mismos bloques que terminó
   teniendo el informe, con cifras reales (nunca estimadas) y redactado para
   un lector no técnico. Lo arma el propio notebook: una frase por métrica
   presente, evaluada sobre las variables que esa métrica calculó
   (`notebook_builder._RESUMEN_POR_METRICA`), así el número del resumen es
   el mismo que muestra la gráfica y ningún modelo redacta ni transcribe
   cifras. La lista de fuentes de consulta de los bloques presentes se
   agrega en el mismo paso.

### Las cinco partes de cada métrica

Toda métrica —del catálogo, a medida, o una comparación entre años— lleva
las mismas cinco partes **en este orden**:

1. El nombre de la métrica.
2. Qué pregunta responde.
3. Qué significa cada término **propio de esta métrica**, según el criterio
   del INE. Es la única parte opcional: si todos sus términos ya los explicó
   la presentación del tema, no va.
4. La gráfica.
5. Por qué esa gráfica, con la referencia bibliográfica que lo respalda
   (Cleveland & McGill, Tufte, Knaflic — ver `CONVENCIONES_DE_GRAFICAS.md`).

La justificación va **después** de la gráfica, no antes: primero se ve el
dato, después se entiende por qué está presentado así.

### Términos: a nivel tema o a nivel métrica

Un término del INE se explica en la presentación del tema si más de una de
las métricas elegidas lo usa; si lo usa una sola, se queda dentro de esa
métrica. Lo decide `notebook_builder.terminos_de_bloque()` sobre lo que la
persona eligió de verdad, no una lista fija: elegir las tres métricas de
Territorio explica "índice de desarrollo territorial" una vez arriba; elegir
una sola lo explica dentro de ella. Un término que cruza temas (como "nivel
económico") se explica en cada tema que lo use, porque los tramos se leen
sueltos.

## 2. Reglas de rigor estadístico (no negociables)

Estas reglas surgieron de la revisión del análisis original, sumadas a
reglas nuevas incorporadas a partir de bibliografía de estadística y
normas internacionales especializadas (ver
[`BIBLIOGRAFIA.md`](BIBLIOGRAFIA.md)). Antes de agregar una gráfica o
sección nueva, revisarla contra esta lista:

- **Falacia ecológica**: no mezclar el nivel de agregación. Si una variable
  describe un territorio entero (ej. el índice de desarrollo territorial de
  un departamento, o su % de pobreza), no se puede usar para sacar
  conclusiones sobre hogares individuales de ese departamento, ni
  viceversa. Si se cruzan variables de distinto nivel (hogar vs.
  departamento vs. persona), **aclararlo explícitamente en el texto y en
  los títulos de las gráficas** (ver el caso ya resuelto de la sección 4).
- **Sesgo de mediador/selección**: no estratificar por una variable que es,
  en parte, resultado de la variable que se está explicando. Ejemplo:
  cruzar "ingreso del hogar" con un índice territorial que ya tiene la
  pobreza entre sus componentes mezcla causa y efecto de forma confusa y
  no aporta una conclusión clara.
- **Celdas chicas**: si un grupo tiene muy pocos casos, la comparación no es
  confiable. Antes de publicar una gráfica nueva agrupada por algo, ejecutar
  `analysis.grupos_con_muestra_chica(df, columna_grupo)` sobre el
  dataframe sin agrupar — si devuelve algún grupo, aclarar en el texto que
  esa estimación puntual tiene poca base muestral (umbral: n=30).
- **Ponderación por muestreo — no negociable, no es "un detalle técnico".**
  Toda estadística de Hogares/Personas (pobreza, hacinamiento, tipos de
  hogar, jefatura, razón de dependencia, vivienda, territorio, brecha
  digital) se calcula ponderada por `ponderador_hogar` (columna `pesoano`
  en 2019, `W_ANO` desde 2024 — mismo ponderador, verificado idéntico para
  todas las personas de un mismo hogar). Esto se agregó recién en esta
  versión: antes, todo lo que no fuera FIES/Empleo/Victimización (que ya
  traían su propio ponderador de módulo) se calculaba como proporción
  simple sobre la muestra — un sesgo real, no cosmético: con datos de
  2019, la pobreza de Montevideo da 6.71% sin ponderar contra 8.14%
  ponderada correctamente, y a nivel nacional 4.79% contra 5.87% — una
  diferencia de casi 1.1 puntos porcentuales, suficiente para cambiar una
  conclusión. Nunca calcular una proporción/media/mediana de Hogares con
  `.mean()`/`.median()`/`.value_counts()` simple — usar los helpers ya
  armados para esto: `analysis.pct_ponderado`/`pct_ponderado_por` (%),
  `media_ponderada_por` (promedio), `proporcion_ponderada` (value_counts
  ponderado), `mediana_ponderada` (mediana). Si se agrega una función
  nueva de Hogares/Personas y no se va a ponderar, dejar explícito por qué
  en el docstring — no que se haya olvidado. **Como "ponderado" aparece en
  casi todas las gráficas, el informe le explica ese término al lector una
  vez, en lenguaje simple**: lo hace
  `notebook_builder.celda_nota_metodologica()`, al final del informe, con un
  aviso de una línea en la introducción que dice dónde buscarlo.
- **Límite conocido: sin intervalos de confianza ni test de significancia.**
  Los microdatos públicos del INE no incluyen las variables de diseño
  muestral (conglomerado/estrato) necesarias para calcular un error
  estándar correcto en un diseño muestral complejo — calcularlo asumiendo
  muestreo aleatorio simple (la única opción sin esas variables)
  subestimaría el error real y daría una precisión falsa, peor que no
  mostrar nada. Por eso ningún número de este proyecto lleva margen de
  error ni "diferencia estadísticamente significativa": son estimaciones
  puntuales ponderadas, no inferencia con incertidumbre cuantificada. Si
  alguna vez el INE publica las variables de diseño, esto se puede
  reconsiderar — hasta entonces, no simular una precisión que no se puede
  respaldar.
- **Correlación vs. causación**: el lenguaje debe ser siempre observacional
  ("los hogares con X tienen más probabilidad de Y"), nunca causal ("X
  provoca Y"), salvo que el diseño del estudio lo permita (no es el caso
  acá: es una encuesta transversal).
- **Integridad visual del eje y la escala.** El eje y de un gráfico de
  barras siempre arranca en cero — nunca truncarlo para exagerar
  visualmente una diferencia real pero chica. Nunca usar gráficos 3D: la
  perspectiva distorsiona la percepción real de la magnitud de cada barra
  o sector. Fundamento: Healy, *Data Visualization: A Practical
  Introduction* (ver `docs/BIBLIOGRAFIA.md`).
- **Proporciones que no suman 100% entre sí no se apilan.** Si dos barras
  representan porcentajes calculados sobre bases distintas (ej. "% de
  ocupados" dentro de "hombres" y dentro de "mujeres"), no se pueden
  combinar en un gráfico de barras apiladas — eso implica una relación
  parte-todo que no existe. Para comparar varias categorías de este tipo a
  la vez, preferir barras agrupadas (cada valor real, lado a lado) — ver
  `tasas_por_grupo()` / `plot_tasas_por_grupo()` como ejemplo ya
  resuelto — y, para comparar solo dos grupos puntuales, el dumbbell chart
  de `docs/CONVENCIONES_DE_GRAFICAS.md`. En ambos casos se muestran los
  valores reales, nunca solo la resta ya calculada.

## 3. Reglas de terminología y claridad

- **Nunca nombrar una variable de forma que sugiera algo que no mide.**
  Caso real: la variable de estrato de muestreo del INE (`estred13`) se
  llamaba inicialmente "nivel de ingreso" en el código y el notebook, pero
  en realidad es una clasificación geográfica/socioeconómica usada para
  diseñar la muestra, no una medición directa del ingreso del hogar (que sí
  existe como variable aparte, `YSVL`/`ingreso_hogar`). Se renombró a
  "nivel económico" en todo el proyecto, con una aclaración de origen en la
  sección 1 del notebook.
- **Si una variable describe al barrio y no al hogar (o a la persona y no
  al hogar), decirlo en el título de la gráfica**, no solo en el texto de
  arriba — quien mira solo la gráfica también tiene que poder entenderla.
- **No amontonar preguntas ni encabezados con dos puntos y texto extra.**
  Un encabezado es un encabezado; la pregunta que responde la sección va en
  el párrafo de abajo, no pegada al título.
- **Cada gráfica necesita una razón de ser.** Si al mirar una gráfica no se
  puede explicar en una frase qué pregunta responde o qué decisión ayuda a
  tomar, no se incluye. (No hace falta *justificar por escrito* el tipo de
  gráfica elegido en el notebook — sí hace falta que la gráfica tenga
  sentido.)
- **No dejar huecos de numeración ni referencias a secciones eliminadas.**
  Cuando se borra o renombra una sección, revisar todo el notebook (y el
  README) buscando menciones cruzadas que hayan quedado colgando.
- **Nunca `print()` una estructura cruda de Python/pandas/numpy en una celda
  cuyo output sobrevive al informe** (el notebook oculta el *código* en la
  versión sin código, no el *output* de lo que ya se ejecutó). Un dict, una
  Series o un DataFrame impresos tal cual muestran ruido técnico que un
  lector no técnico no tiene por qué ver — `{'tasa_actividad':
  np.float64(64.28), ...}`, una columna `dtype: float64` al pie, un índice
  numérico 0/1/2 sin sentido, un valor `np.int64(1)` en vez de `1` (desde
  que numpy cambió el `repr()` de sus escalares). Encontrado en una corrida
  real: `sorted(serie.unique())` de una columna de meses (1-12) se imprimió
  como `[np.int64(1), np.int64(2), ...]` en vez de nombres de mes legibles
  (ver `config.MESES_LABELS`).
  - Si el dato **ya está en la gráfica que sigue** (lo normal — la gráfica
    ya trae las etiquetas con el valor exacto), no repetirlo con un
    `print()`: sacarlo directamente, no hace falta reformatearlo, alcanza
    con la gráfica.
  - Si de verdad hace falta reforzar un número en texto (porque la gráfica
    no lo deja lo bastante claro, o porque es la base de un cálculo
    posterior), escribirlo en prosa dentro de la celda de markdown de la
    métrica, o con un `print(f"...")` explícitamente formateado (`:.2f`,
    `:,`, nombres en vez de códigos) — nunca la variable sola.

## 4. Ejemplo real de ambigüedad ya resuelta: "nivel de suscripción"

**Este caso ya no existe en el código**: la dimensión barrio se eliminó
entera junto con TV cable en la versión 0.9.0 (ver `CHANGELOG.md`). Se
conserva documentado porque el patrón puede volver a aparecer con
cualquier otra variable de territorio.

`nivel_suscripcion` era una clasificación por **cuartiles del % de
abonados al cable de todo un barrio**, que después se le asignaba a **cada
hogar de ese barrio**, tuviera o no la tecnología. Cruzarla con
`tipo_abonado` (que sí era del hogar) producía combinaciones que a primera
vista parecían contradictorias ("Sin cable" + "barrio de Alta
suscripción"), pero eran válidas: describían un hogar que era la excepción
dentro de su barrio.

La lección que se conserva: cuando una variable es del territorio y otra
del hogar, la solución no es cambiar el cálculo — es dejar clarísimo en el
título y el texto de qué nivel es cada una. Hoy el caso vivo más parecido
es el índice de desarrollo territorial, que es por departamento y nunca
debe leerse como una propiedad de los hogares de ese departamento.
