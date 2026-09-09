# Curación del catálogo (fuera del flujo guiado — solo para el dueño del proyecto)

Procedimiento para incorporar una métrica al catálogo permanente. Hasta la
v0.14.0 vivía dentro de las instrucciones del agente, que se cargan
completas en cada corrida aunque esta sección no participe nunca del flujo
guiado; ahora vive aquí y las instrucciones solo conservan la regla de la
compuerta previa y la referencia a este documento.

Esto **no es un paso del flujo de formularios**. No es una opción que se
le ofrece a nadie que esté completando un formulario, no aparece en
ningún formulario, y no se activa por nada que responda alguien en el
paso 5 (catálogo) ni en ningún otro paso — esa posibilidad no existe para
quien está usando el agente de la forma guiada.

Se activa **únicamente** cuando el dueño del proyecto lo pide de forma
directa, escribiéndolo él mismo en el chat de Claude Code (no completando
un formulario) — algo como "agregá esta métrica al catálogo permanente" o
"esto vale la pena incorporarlo". Ahí, y solo ahí, pasa por esta
compuerta de calidad antes de tocar ningún archivo permanente:

0. **Compuerta previa — no es automática.** Antes de escribir nada,
   confirmarle al dueño del proyecto, en un mensaje corto, los cuatro
   puntos siguientes (no asumir que ya están validados solo porque la
   métrica pasó por el paso 6 en su momento — esa sesión pudo haber sido
   hace tiempo, con datos de otro año, o revisada por otra persona):
   - Qué pregunta responde la métrica y con qué variable(s) del
     dataset.
   - Que ya pasó la revisión metodológica de la sección 2 de
     `docs/METODOLOGIA.md` (falacia ecológica, sesgo de mediador, celdas
     chicas, ponderación, etc.) — si no hay certeza de que se hizo o hace
     tiempo que no se revisó contra el dataset actual, hacerla de nuevo
     ahora, no darla por hecha.
   - **¿La métrica depende de tenencia de tecnología sin que el usuario lo
     haya pedido así explícitamente?** Esta pregunta puntual existe porque
     ya pasó dos veces en este proyecto (Hogares/Brecha Digital, y después
     Vivienda/Territorio) — un bloque entero terminó siendo, en el fondo,
     "tema X según tenencia de streaming/celular", perdiendo de vista el
     tema por sí mismo. Si la respuesta es sí, la tecnología va en Brecha
     Digital, no mezclada en otro bloque — ver `docs/METODOLOGIA.md`.
   - Qué tipo de gráfica le corresponde y qué principio/fuente lo
     respalda (`docs/CONVENCIONES_DE_GRAFICAS.md`) — si la fuente no está
     ya en `docs/BIBLIOGRAFIA.md`, agregarla ahí y en la nota del bloque
     correspondiente en este archivo, no solo en el docstring del código.
   - Con qué año/dataset se validó el resultado (no alcanza con que el
     código corra sin error — tiene que haberse visto un número real,
     verosímil, antes de curarla).
   - Qué archivos se van a tocar (`analysis.py`, `visualization.py`,
     `plantillas.py`, tests) y que la numeración de métricas existentes
     no se va a romper.
   Solo se sigue a partir del punto 1 si el dueño confirma explícitamente
   estos cuatro puntos en el chat. Esto no es la misma confirmación que
   "agregá esta métrica" — esa autoriza la intención, esta es la
   revisión técnica antes de ejecutar.
1. Revisar que el código en `analysis.py` / `visualization.py` que
   sostiene esa métrica esté generalizado y prolijo — no atado a un caso
   puntual (ej. un departamento específico). Generalizarlo si hace falta,
   siguiendo el mismo criterio que ya usan `precariedad_estructural_por`,
   `tasas_actividad_empleo_desempleo_por`, `tipos_hogar_resumen`.
2. Agregar la entrada correspondiente a `_CATEGORIAS_METRICAS` en
   `src/encuesta_hogares/plantillas.py` (ahí vive el catálogo desde la
   v0.13.2; `formularios.py` solo lo reexporta), con el mismo formato que
   las demás (número corrido, nombre en negrita, explicación breve en una
   frase) — sin romper la numeración de las métricas existentes.
3. Agregar la entrada correspondiente en
   `encuesta_hogares.verificacion_catalogo.MANIFEST`, con la(s)
   función(es) de `analysis.py`/`preprocessing.py` y la de
   `visualization.py` que la implementan — si se omite, el test de
   `test_verificacion_catalogo.py` lo va a marcar como métrica huérfana
   en la próxima corrida de `pytest`, así que conviene hacerlo ahora en
   vez de dejar que otra persona la encuentre después.
   - **Si la métrica depende de una columna que ya se vio variar entre
     años del INE** (pasó de verdad: `INFORMAL`/`SECTOR_F`/`SIT_OCUP`
     desaparecieron de Empleo desde 2025), sumarle también una entrada en
     `verificacion_catalogo.COLUMNAS_REQUERIDAS` — así el aviso del paso
     3.5 la cubre para años futuros que tengan el mismo problema. No hace
     falta para métricas sin ese antecedente.
4. Agregar o completar los tests que falten — incluir al menos un test
   que ejercite la función con datos que representen el caso real que
   motivó la curación (no solo el caso sintético genérico), para que una
   regresión futura sobre ese caso puntual no pase desapercibida.
5. Correr el flujo de verificación completo.
6. La incorporación queda en los archivos locales. Publicarla en GitHub
   sigue siendo una acción aparte, con su propia confirmación explícita
   antes de cualquier `git push` — igual que cualquier otra publicación.
