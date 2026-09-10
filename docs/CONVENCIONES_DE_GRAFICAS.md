# Convenciones de gráficas: justificar el tipo elegido, con fundamento estadístico

Este documento reúne las convenciones para justificar el tipo de gráfica
elegido en cada métrica — distinto de
[`METODOLOGIA.md`](METODOLOGIA.md), que reúne las reglas de rigor
estadístico y terminología. Las citas completas de cada fuente
mencionada acá están en [`BIBLIOGRAFIA.md`](BIBLIOGRAFIA.md).

**Cada gráfica del informe va acompañada de una justificación con
fundamento, no solo una frase intuitiva.** El público al que está
orientado este proyecto —académico, profesional, técnico o no técnico—
tiene que poder leer una cita, una fórmula o un gráfico y entender con
claridad qué significan, los números que respaldan el análisis, las
preguntas que lo originan, y la fuente estadística que justifica la
elección.

Toda métrica lleva, además de su nombre y de la pregunta guía:

1. **La fórmula o definición exacta**, cuando la métrica la tenga (ej. una
   tasa, un índice compuesto, una razón) — no alcanza con describirla en
   palabras si existe una notación estándar. Ejemplo: "Razón de
   dependencia demográfica = (población de 0 a 14 + población de 65 y
   más) / población de 15 a 64 × 100". Va **antes** de la gráfica, salvo
   que ese término ya lo haya explicado la presentación del tema (ver
   `METODOLOGIA.md`, sección 1).
2. **Por qué ese tipo de gráfica** — con el principio de visualización que
   lo respalda y, cuando aplique, el autor/fuente (Cleveland & McGill
   sobre comparación visual de formas; Tufte sobre slopegraphs; Knaflic,
   *Storytelling with Data*; Few sobre simplicidad — ver la guía de
   referencia más abajo con la cita concreta de cada patrón). Va
   **después** de la gráfica: primero se ve el dato, después se entiende
   por qué está presentado así.

**Esto aplica a todas las métricas, sin excepción — no hay métrica
"demasiado simple" como para saltearse la gráfica o la justificación.**
Un solo número o una diferencia entre dos grupos siguen necesitando su
gráfica (ver la entrada de "dumbbell chart" más abajo) y su fundamento,
igual que cualquier otra.

## Formato y color, iguales en todo el informe

Reglas mecánicas que aplica `visualization.py` a toda gráfica (nacieron de
la revisión del PDF real de 2024; los guardianes de clase de
`tests/test_visualization.py` las hacen cumplir):

- **Cifras con el formato del texto**: coma decimal y punto de miles
  (`resumen.fmt` en la prosa, `layout.separators` en Plotly), un decimal y
  el símbolo `%` en toda barra de porcentaje, siempre vía `texttemplate` y
  nunca con etiquetas armadas a mano en un f-string (esas no pasan por el
  separador). Cinco gráficas decían «89.99» o «61.05» mientras el resumen
  decía «65,2%».
- **Un solo color por gráfica** salvo que el color signifique algo: una
  leyenda con varias series, o un mapa explícito con significado (la
  inseguridad alimentaria severa en rojo). Ocho gráficas pintaban cada
  barra de un color distinto sin que significara nada. Fundamento: Tufte,
  data-ink ratio (misma entrada de abajo).
- **Departamentos siempre en barras horizontales ordenadas y con el nombre
  como se escribe** («Treinta y Tres», no «TREINTA Y TRES»), sea cual sea
  el archivo del INE del que vengan (`resumen.nombre_propio`).
- **Un grupo con pocos casos se ve en gris** (`COLOR_POCO_CONFIABLE`) y la
  celda lo explica en una nota; no desaparece ni se lee como un dato más
  (ver `METODOLOGIA.md`, sección 2, «Celdas chicas»).
- **Títulos de hasta 65 caracteres** en las figuras de 800 px, también en
  las celdas a medida (`generar_informe._validar_celdas_a_medida` lo
  comprueba antes de ejecutar).

## Guía de referencia, con la fuente de cada patrón

- **Barras horizontales** (en vez de verticales): cuando las categorías
  tienen nombres largos (barrios, condiciones de vivienda) — se leen sin
  inclinar la cabeza. Fundamento: Cleveland & McGill (1984), sobre
  precisión en la percepción de posición vs. longitud en distintas
  orientaciones. El orden de las categorías (`categoryorder: "total
  ascending"`, ya usado en todo el proyecto) aplica además el principio
  Gestalt de continuidad — Ware, *Information Visualization: Perception
  for Design*: una secuencia ordenada se procesa como una sola tendencia,
  no como valores sueltos sin relación entre sí.
- **Barras agrupadas** (en vez de una sola barra con todo mezclado): para
  comparar el mismo dato entre 2 o más grupos lado a lado. Fundamento:
  principio de comparación directa (Few, *Show Me the Numbers*).
- **Líneas con marcadores, eje x numérico real (no categórico)**: para
  comparar la misma métrica entre corridas de 3 años o más que no son
  necesariamente consecutivas (ej. 2019, 2024, 2025 — ver
  `analysis.combinar_por_anio` / `visualization.plot_serie_por_anio`,
  genéricas para cualquier métrica del catálogo; `Empleo` tiene además su
  propio par especializado ya existente,
  `tasas_actividad_empleo_desempleo_por_anio` /
  `plot_tasas_por_anio`, con las 3 tasas fijas). El año tiene que quedar en su
  escala real, no parejo espaciado como una categoría — si no, un salto de
  5 años (2019→2024) se ve visualmente igual de "cerca" que uno de 1 año
  (2024→2025), y la línea sugiere una tendencia continua e interpolada
  entre años sin encuesta propia, que no se midió. Fundamento: mismo
  principio de precisión perceptiva de posición en una escala común de
  Cleveland & McGill (1984), aplicado al eje temporal en vez de solo al de
  categorías. Los marcadores explícitos en cada punto son parte de la
  misma idea: distinguen "acá hay una medición real" de "esto es una
  interpolación visual".
- **Nunca gráfico de torta con más de 3-4 categorías**: el ojo humano
  compara longitudes y posiciones con mayor precisión que ángulos
  (Cleveland & McGill, 1984) — con muchas porciones, un gráfico de torta
  se vuelve difícil de leer con precisión. Fundamento adicional: Cohen et
  al. (2016), sobre el límite de la atención perceptiva — más porciones
  que ese límite no se retienen como categorías distintas, se perciben
  como ruido.
- **Heatmap (mapa de calor)**: cuando se cruzan dos variables categóricas
  y lo que importa es la magnitud relativa de la concentración, no el
  valor exacto de cada celda. Fundamento: principio Gestalt de similitud
  — Ware, *Information Visualization: Perception for Design*: celdas de
  color parecido se agrupan visualmente solas, sin necesidad de leer cada
  valor individual.
- **Gráfico de puntos/dispersión ordenado**: cuando hay muchas categorías
  (ej. 62 barrios) y lo que importa es el orden y la distancia entre
  ellas, no compararlas de a pares.
- **Barras 100% apiladas**: cuando cada categoría se reparte en partes que
  suman exactamente 100% (ej. ocupados/desocupados/inactivos) — deja ver
  la composición completa en una sola barra por grupo. Fundamento: Wilke,
  *Fundamentals of Data Visualization*, capítulo sobre proporciones.
- **Barras de diferencia** (puntos porcentuales, no barras apiladas):
  cuando se comparan varios grupos que NO suman 100% entre sí — apilarlos
  daría una impresión de proporción que no existe (ver
  `docs/METODOLOGIA.md`, sección 2; mismo fundamento de Wilke sobre
  proporciones que la entrada anterior, aplicado al caso donde no
  corresponde apilar).
- **Nunca agregar a una gráfica un elemento que no aporte información**
  (grillas de fondo densas, bordes gruesos, colores decorativos sin
  significado, sombras): cada elemento visual compite por la atención de
  quien lee, así que solo debería estar ahí lo que ayuda a leer el dato.
  Fundamento: Tufte, principio de "data-ink ratio" (*The Visual Display
  of Quantitative Information*, 1983).
- **Dumbbell chart (o "barbell"/slopegraph)** — dos puntos por categoría,
  conectados por una línea, en vez de una barra con la resta ya calculada:
  para cualquier métrica que compare **dos grupos específicos** dentro de
  una variable más amplia (ej. "quintil 1 vs. quintil 5", "comunicación
  informal vs. denuncia formal"). Es la práctica recomendada en la
  literatura de visualización por sobre una barra de diferencia simple,
  porque conserva los dos valores reales además de la brecha entre ellos
  — una barra de diferencia sola oculta si la brecha viene de un valor
  alto contra uno bajo, o de dos valores intermedios cercanos. Fuente:
  Tufte (slopegraphs, años 80); Knaflic, *storytellingwithdata.com*,
  "More on slopegraphs" (2014); Nightingale/Data Visualization Society,
  "Beyond the Bar: Alternative Methods for Visualizing Two Points of
  Change". Implementación: `visualization.plot_dumbbell`.
- **Comparar cualquier métrica del catálogo entre varios años (ej. "2024
  vs. 2025", o "2019 vs. 2024 vs. 2025")**: "año" es un grupo específico
  como cualquier otro, no hace falta código nuevo en ninguno de los dos
  casos. Es una opción de primera clase del catálogo
  (`formularios.plantilla_catalogo`, campo "¿Comparar alguna métrica con
  otros años?", con una casilla propia por métrica — se puede pedir para
  una sola, para todas, o cualquier combinación), no algo que la persona
  tenga que pedir escribiéndolo en "otra métrica". Calcular la métrica
  una vez por año con la función que ya exista (la misma que usa el
  informe de un solo año) y después:
  - **Exactamente 2 años**: cruzar las dos tablas con
    `analysis.diferencia_entre_tablas` y graficar con
    `visualization.plot_dumbbell` — confirmado en una corrida real
    (Seguridad y Victimización, 41-47, comparando 2024 con 2025).
  - **3 años o más**: combinar los resultados con
    `analysis.combinar_por_anio` y graficar con el patrón de líneas con
    eje numérico real de más arriba (`visualization.plot_serie_por_anio`)
    — generaliza a cualquier métrica el mismo patrón que antes solo
    existía, especializado, para las tasas de Empleo.
  En los dos casos se resuelve entero reusando funciones ya existentes,
  sin escribir ninguna función nueva por corrida.

Si una gráfica no encaja claramente en ninguno de estos patrones, aplicar
el mismo criterio general: identificar el principio de percepción visual
o de rigor estadístico que está en juego, y citarlo — nunca elegir el
tipo de gráfica "porque sí" o "porque se ve bien".
