# Instrucciones para la sesión principal de Claude Code

Este proyecto tiene un único agente especializado: `encuesta-hogares` (ver
`.claude/agents/encuesta-hogares.md`). Cualquier pedido relacionado con
analizar la Encuesta Continua de Hogares (ECH) del INE Uruguay —sin
importar cuánto detalle traiga el pedido original ("hacé el análisis
2024", "análisis estándar", "agregá una pregunta sobre X")— se delega
entero a ese agente.

**Al delegar la tarea, pasar el pedido del usuario tal cual lo escribió,
palabra por palabra, sin resumir, sin completar el año, sin interpretar
qué quiso decir con "estándar", y sin agregar contexto adicional.** No
armar un resumen de alcance ni una lista de lo entendido —eso es
exactamente lo que el agente tiene que volver a preguntar él mismo, a
través de su propio formulario, y un resumen ya armado compite con esa
regla en vez de ayudarla.

No responder ninguna pregunta de alcance (año, métricas, formato de
salida) antes de delegar —todas esas preguntas las hace el agente con
sus propios formularios visuales.

## Mantenimiento del proyecto (para la sesión principal, no para el agente)

**Una sola copia** (esta, en Documents) —hasta la versión 0.3.0 existía
también una copia aparte para desarrollo; se eliminó porque generaba
riesgo real de perder trabajo sin publicar (pasó de verdad: una función
nueva en `analysis.py` quedó casi dos días sin subir a GitHub). Ahora se
desarrolla, se prueba y se corre el agente todo en el mismo lugar
—commitear y publicar directo desde acá.

El agente `encuesta-hogares` sigue sin permiso de usar git (ver
`.claude/settings.json`). Si escribe código nuevo y reutilizable durante
una corrida real (ej. una función para una métrica propuesta por el
usuario), ese código queda en el disco pero sin commitear —**antes de
dar por cerrada una sesión de trabajo** (sobre todo si el usuario
mencionó haber corrido el agente), ejecutar:

```bash
./run_python.bat tools/verificar_sincronizacion.py
```

Si encuentra diferencias contra `origin/main`, revisarlas —puede ser
trabajo real del agente sin publicar (commitearlo y hacer `git push`) o
simplemente que esta copia está atrasada respecto a lo último subido.

### Qué es y qué no es la lista de permisos

**`.claude/settings.json` es una lista de conveniencia, no una frontera de
seguridad.** Conviene tenerlo claro antes de apoyarse en ella para
razonar sobre qué puede o no puede hacer el agente.

Lo que sí hace: evitar que a alguien sin conocimientos técnicos le
aparezcan prompts de aprobación de terminal en medio del flujo —que es
justamente lo que todo el diseño de formularios existe para evitar.

Lo que **no** hace: acotar lo que el agente puede ejecutar.
`Bash(run_python.bat *)` deja correr cualquier archivo `.py` o cualquier
`-c "..."`, y `Write` no tiene restricción de ruta. Sumados, equivalen a
ejecución de código arbitrario ya aprobada. **Y es a propósito**: el paso
5 corre un módulo del paquete con `run_python.bat`, y las celdas a medida
se escriben en un `.py` que ese módulo carga. Una lista de permisos que
impidiera eso impediría el flujo entero.

Tampoco tiene sentido "arreglarlo" restringiendo `Write` a rutas del
proyecto: los archivos de scratch van, por regla explícita del agente, a
la carpeta de scratchpad que provee Claude Code —fuera del repositorio, y
con una ruta distinta en cada sesión, imposible de anotar en un
`settings.json` estático—. Una regla así rompería el flujo documentado sin
agregar seguridad real.

Lo que de verdad acota el riesgo en este proyecto es otra cosa, y conviene
no confundirlo con la lista de permisos:

- Corre localmente, en la computadora de la persona, sobre sus propios
  datos ya descargados. No hay servicio de terceros ni cuenta de por
  medio (ver el docstring de `formularios.py`).
- La única salida a internet permitida es `WebFetch` al dominio del INE.
- git está denegado de forma directa (`Bash(git *)`) e indirecta
  (`.claude/hooks/gate-no-git-indirecto.cjs`, que cubre el caso de
  invocarlo desde adentro de otro intérprete).
- El servidor de formularios solo acepta respuestas de su propia página
  (ver `formularios._origen_es_propio`).
- `Edit`/`Write` están denegados sobre `.claude/**` y sobre los tres
  `.bat` del lanzador. El motivo: todos los guardianes de este proyecto
  (hooks, permisos, instrucciones del agente) viven ahí, así que un
  agente que pudiera editarlos podría desarmarlos — y `run_python.bat`
  en particular es el ancla de la regla de permisos más amplia, así que
  reescribirlo sería ejecutar cualquier cosa bajo un permiso ya
  aprobado. **Con la misma honestidad que el resto de esta sección**:
  esto solo cierra las herramientas Edit/Write, no un `.py` que escriba
  en esas rutas — es protección contra el desvío accidental, no una
  frontera. La frontera, si hiciera falta, sigue siendo el sandbox.

Si alguna vez hiciera falta una frontera real —por ejemplo, si el agente
pasara a correr sobre datos o pedidos que no son de la propia persona—,
el camino no es la lista de permisos: es sandboxear el proceso entero.

**Un usuario real nunca va a tener `.git` en su copia.** La instalación
rápida del README (pensada para gente sin conocimientos técnicos) baja
el proyecto con el botón "Download ZIP" de GitHub, que nunca incluye
`.git` —es el comportamiento esperado, no un problema para diagnosticar
ni reparar. Si esta misma carpeta (Documents) aparece sin `.git` en
algún momento, lo más probable es que se haya probado esa instalación
rápida ahí encima —confirmar con el dueño del proyecto antes de asumir
nada, y nunca intentar "arreglarlo" corriendo `git init` sobre esa
copia: para seguir desarrollando/publicando, clonar aparte (ej. en el
scratchpad) en vez de tocar la copia de prueba.

**Antes de publicar un cambio en `analysis.py`/`preprocessing.py` que
toque cómo se leen o combinan los datos**, ejecutar también:

```bash
./run_python.bat tools/validar_con_datos_reales.py
```

Ejercita el pipeline completo contra los datos reales que haya en `data/`
(si hay alguno) —atajó bugs reales esta sesión que los tests con datos
sintéticos no detectaban (columnas de vivienda que cambian de 12 a 4 según
el año, formato .sav vs .csv, base nacional vs. filtrada a Montevideo).
