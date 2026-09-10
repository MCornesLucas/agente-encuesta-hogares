# Flujo de trabajo: verificación, entrega del informe y casos operativos

Este documento reúne los procedimientos paso a paso del proyecto —
distinto de [`METODOLOGIA.md`](METODOLOGIA.md), que reúne las reglas y
principios (qué es correcto o incorrecto), este archivo es sobre *cómo
ejecutar* el trabajo una vez que las reglas ya están claras.

## 1. Flujo de verificación (seguir siempre, sin saltarse pasos)

1. Escribir o editar el código en `src/encuesta_hogares/` (nunca directamente
   en el notebook si la lógica se puede poner en una función reutilizable
   y testeable).
2. Si se agrega una función nueva en `analysis.py`, agregarle un test en
   `tests/`.
3. Correr `pytest -q` y confirmar que todo pasa.
4. Generar el informe con el pipeline del paquete, nunca editando el
   notebook a mano ni invocando `jupyter nbconvert` suelto:
   ```bash
   ./run_python.bat -m encuesta_hogares.generar_informe construir --anio <año> --metricas <lista> --bloques <lista>
   ```
   Las métricas y cruces a medida y las comparaciones entre años van en el
   archivo `--extra` (`celdas_extra`, `celdas_finales`, `frases_resumen`) y
   se verifican con los mismos estándares que el catálogo antes de
   ejecutar: encabezado numerado desde 43, pregunta guía, gráfica,
   justificación que cita la bibliografía, frase para el resumen, sin
   estadísticas crudas sin ponderar.
   Arma el notebook (`notebook_builder`), lo verifica antes de ejecutarlo
   (`verificacion_notebook.verificar_antes_de_ejecutar`: gráficas
   duplicadas, métricas sin gráfica o sin cita de un autor de
   `BIBLIOGRAFIA.md`, estadísticas crudas sin ponderar, texto sin
   completar, encabezados repetidos), lo ejecuta **una sola vez**
   cronometrado en la bitácora (`ejecucion_notebook`), verifica el
   resultado (celdas con error, gráficas sin imagen, cifras imposibles
   según `verificacion_plausibilidad`) y deja las cifras de cada métrica en
   `notebooks/_cifras_Informe_ECH_<año>.json`.
5. El resumen analítico final lo arma el propio notebook en el paso
   anterior: una frase por métrica (`notebook_builder._RESUMEN_POR_METRICA`,
   helpers en `resumen.py`) evaluada sobre las variables de la métrica, más
   las fuentes de consulta de los bloques presentes. Después, entregar:
   ```bash
   ./run_python.bat -m encuesta_hogares.generar_informe entregar --anio <año>
   ```
   Genera el HTML sin código (`generacion_html`) y el PDF (`conversion_pdf`,
   ver sección 2) con copia en Descargas. `--comentario <markdown>` es
   opcional y valida cada cifra que cite contra los resultados ejecutados.
6. Para cualquier gráfica nueva o modificada de una plantilla del
   catálogo, extraer el PNG embebido del output de la celda y mirarlo —
   no asumir que "si no tiró error, se ve bien". Revisar que los números
   y el orden de las barras tengan sentido. Los borrados de PNGs viejos
   del scratchpad se hacen con Python (`pathlib`), nunca con un comodín
   en `rm`: la herramienta de Bash rechaza los patrones glob en
   operaciones de borrado.
7. Cada corrida es una edición propia:
   `notebooks/ediciones/Informe_ECH_<año>_<fecha-hora>.ipynb`, `.html` y
   `.pdf`, con el instante de la corrida en el nombre — dos corridas nunca
   se pisan y no hace falta respaldar nada. `entregar` toma la edición más
   reciente del año (o la que se indique con `--edicion`).
8. Si hay que volver a construir el mismo año tras una corrección, pasar
   `--motivo` a `construir`: queda en la bitácora como
   `reejecucion_notebook`.
9. Verificar que el PDF existe, tiene un tamaño razonable y la portada
   correcta antes de darlo por terminado.
10. Publicar (ver sección 3).

## 2. Generación del informe PDF profesional

El objetivo es un PDF con aspecto de informe real (portada, tipografía
cuidada, gráficas que nunca se cortan ni se salen de la hoja), no una
impresión cruda del notebook. Lo genera `generar_informe.entregar` a
partir del HTML sin código, así no hay que mantener dos fuentes de verdad.

**Por qué no usar `jupyter nbconvert --to pdf`:** ese exportador depende de
una instalación de LaTeX completa, que es pesada, lenta de instalar y
frágil en Windows — mala idea para un usuario no técnico. En su lugar se
usa Chromium sin interfaz (a través de Playwright) para "imprimir" el HTML
a PDF, igual que haría un navegador común.

Qué hace `entregar` (todo en `src/encuesta_hogares/generar_informe.py`):

1. Playwright tiene que estar listo (una sola vez por instalación):
   `playwright install chromium`, que ya corre `instalar.bat`.
2. Toma el HTML sin código y le antepone al `<body>` una portada
   (`generar_informe.portada`): título con el año, subtítulo que describe
   el contenido y la fecha de generación como único pie. Es texto visible
   que no pasa por las celdas del notebook, así que tiene su propio test.
3. Inyecta `docs/informe_estilo.css` dentro de un `<style>` en el `<head>`.
   Esa hoja define tamaño A4, márgenes, tipografía y, sobre todo,
   `max-width`/`max-height` + `page-break-inside: avoid` en las imágenes —
   es lo que evita que una gráfica quede cortada entre dos páginas o se
   salga del ancho de la hoja. No simplificarla: cada regla resuelve un
   problema real de paginación.
4. Escribe ese HTML intermedio al lado del final, con nombre derivado
   (`_Informe_ECH_<año>_impresion.html`), lo imprime con Chromium
   (`page.pdf`, formato A4, `print_background`, numeración "Página N de
   M" en el pie con `footer_template` — Chromium no soporta las cajas de
   margen de `@page`, solo esas plantillas de Playwright — y márgenes
   20/16/18/18 mm), cronometrado como `conversion_pdf`, y borra el
   intermedio.
5. El PDF lleva el mismo nombre que la edición
   (`Informe_ECH_<año>_<fecha-hora>.pdf`), así nunca pisa a otro.
6. Copia el PDF a la carpeta de Descargas del usuario (`Path.home() /
   "Downloads"`, igual en Windows y en Mac), respaldando también ahí el de
   una corrida anterior. Si esa carpeta no existe, lo informa en el JSON
   de salida (`copia_descargas: null`) en vez de fallar.

## 3. Publicación (no es parte del flujo del agente)

El agente **nunca** publica nada en GitHub ni se lo ofrece al usuario —
ver el paso 9 de `.claude/instrucciones/encuesta-hogares.md`. La mayoría de
quienes usan el agente no tienen permiso de escritura sobre el
repositorio, y mezclar código puntual de sesiones de usuario con el
repositorio compartido lo llenaría de funciones muy específicas que no le
sirven a nadie más.

Decidir qué código o qué métrica de una sesión vale la pena incorporar al
catálogo permanente es una decisión del dueño del proyecto — pero no una
tarea que tenga que hacer a mano: se lo puede pedir directamente al
agente por chat (nunca a través de un formulario, ver "Curación del
catálogo" en `.claude/instrucciones/encuesta-hogares.md`), y el agente hace el
trabajo de generalizar el código, agregarlo al catálogo y testearlo. Esa
posibilidad no existe para nadie más que esté usando el flujo guiado.

Publicar cambios en GitHub, en cambio, es siempre una acción aparte, con
sus propios cuidados:

- Nunca commitear los archivos `.sav` (ya están en `.gitignore`).
- Nunca hacer `git push` sin confirmarlo explícitamente antes.
- Usar Plotly con `pio.renderers.default = "png"` (requiere el paquete
  `kaleido`) desde la primera celda del notebook — si no, las gráficas
  interactivas no se ven en GitHub ni en el HTML exportado.

## 4. Cómo manejar un año de datos nuevo (lo específico de este proyecto)

> Esta sección estuvo escrita para la era `.sav` ("qué archivos .sav puso
> en data/", inspeccionar con pyreadstat) hasta la v0.13.x, cuando ya
> hacía dos años que todo llegaba como CSV — el mismo tipo de prosa
> desactualizada que en su momento fueron "las 43 métricas". Lo que sigue
> es el proceso real, para ambos formatos.

1. Confirmar con el usuario qué archivos puso en `data/{año}/` y de qué
   año son. El formato depende del año, y **el INE tampoco es consistente
   con los nombres** (los tres casos son reales, no hipotéticos):
   - hasta 2019: dos `.sav` separados (`H_*.sav` Hogares, `P_*.sav`
     Personas);
   - 2023: un CSV combinado con el orden de palabras invertido
     (`ECH_implantacion_2023.csv`);
   - 2024: `ECH_2024.csv`; desde 2025: `ECH_{año}_implantacion.csv`.

   `config.hogares_csv_file(anio)` ya reconoce las tres variantes de
   nombre, y `config.datos_disponibles(anio)` resuelve qué módulos
   opcionales (FIES, Empleo, Victimización) existen de verdad para el
   año. Si el INE inventa un cuarto nombre, el lugar para contemplarlo
   es esa función — no renombrar el archivo del usuario a mano.
2. Correr `verificacion_estructura.verificar_anio(anio)` (o
   `tools/verificar_estructura_datos.py`): compara las columnas reales
   del año — en cualquiera de los dos formatos — contra lo que
   `config.py` espera, y reporta qué falta y qué sobra.
   `verificacion_catalogo.metricas_no_disponibles_del_anio(anio)`
   complementa: dice qué métricas del catálogo quedan afuera para ese
   año y por qué columna o módulo. Para un `.sav` también sirve
   inspeccionar las etiquetas de variable con `pyreadstat`
   (`column_labels`) sin cargar los datos.
3. Si algún código cambió de nombre o desapareció, **nunca asumir un
   reemplazo por cuenta propia**: proponerle al usuario la columna
   candidata (por su etiqueta, o por el diccionario de variables que el
   INE publica con cada año) y esperar su confirmación antes de tocar
   `config.py`. Es lo que pasó de verdad con la canasta 2006 → 2017
   (`pobre06`/`pobre17`, año de transición 2024): la preferencia quedó
   en `config.PREFERENCIA_METODOLOGIA_HOGARES` como decisión confirmada
   con el usuario, no elegida en silencio por el código.
4. Una vez validado el mapeo, correr el pipeline estándar completo (armar
   el notebook, verificarlo, generar HTML y PDF — secciones 1 y 2 de este
   documento) y regenerar los cortes/cuartiles reales para ese año — nunca
   reusar los cortes del año anterior, seguramente hayan cambiado.
5. Presentarle el catálogo de métricas por categoría para que elija qué
   incluir en la Ampliación, y dejar espacio para que proponga una métrica
   propia si ninguna del catálogo le sirve (ver el paso 5 del archivo del
   agente).
