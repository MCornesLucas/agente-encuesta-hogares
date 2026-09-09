# Agente de Análisis: Encuesta Continua de Hogares (ECH, INE Uruguay)

[![Tests](https://github.com/MCornesLucas/agente-encuesta-hogares/actions/workflows/tests.yml/badge.svg)](https://github.com/MCornesLucas/agente-encuesta-hogares/actions/workflows/tests.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![Licencia: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/licencia-PolyForm%20Noncommercial%201.0.0-blue)](LICENSE)

Este proyecto permite generar un informe de la Encuesta Continua de
Hogares del INE Uruguay, tanto a usuarios técnicos (con conocimientos
estadísticos) como a usuarios sin experiencia en programación, y
reproducirlo cada vez que se disponga de un nuevo año de datos, sin
necesidad de reconfigurar el análisis desde cero. El catálogo se define
en dos pasos: primero se seleccionan los **bloques temáticos** a incluir
(Brecha Digital, Hogares, Territorio, Vivienda y, cuando el año elegido
cuenta con esos datos, Seguridad Alimentaria, Empleo, y Seguridad y
Victimización — ninguno se incluye por defecto), y luego las métricas
puntuales dentro de cada bloque.

El análisis lo ejecuta un **agente**: un asistente de inteligencia
artificial (Claude) que carga los datos, construye las gráficas, redacta
las conclusiones y verifica la consistencia del resultado, guiando todo
el proceso mediante **formularios visuales que se abren automáticamente
en el navegador** — sin comandos ni ventanas de terminal. El usuario
selecciona el año, marca las métricas de interés en el catálogo y
confirma con un clic. También es posible proponer una métrica propia que
no figure en el catálogo; el agente advierte si detecta un problema
metodológico antes de construirla y ofrece una alternativa válida.

El resto de este documento está pensado para seguirse paso a paso, sin
necesidad de conocimientos técnicos previos.

---

## Cómo instalar

Hay dos caminos para llegar al mismo resultado — elija el que le quede
más cómodo:

- **Instalación rápida**, más abajo en esta misma sección: descargar el
  proyecto como un archivo comprimido (ZIP) desde la propia página de
  GitHub y hacer doble clic en dos archivos ya incluidos. No hace falta
  instalar Git ni abrir una terminal.
- **Instalación manual (con conocimientos técnicos)**, a partir de
  "Requisitos previos": clonar el repositorio con Git y correr cada paso
  por su cuenta. Pensada para quien va a modificar el código o prefiere
  tener control de cada paso.

Los dos caminos terminan en el mismo lugar: el "Paso 3: Obtener los
datos del año a analizar" y todo lo que sigue después es igual para
ambos.

### Instalación rápida

1. Instale [Anaconda](https://www.anaconda.com/download) (incluye
   Python) — es el único programa que hay que instalar a mano antes de
   empezar. Use las opciones por defecto del instalador.
2. Descargue este proyecto desde este enlace directo:
   <https://github.com/MCornesLucas/agente-encuesta-hogares/releases/latest/download/agente-encuesta-hogares.zip>
   — se descarga un archivo `agente-encuesta-hogares.zip`
   (normalmente a la carpeta Descargas).
3. Descomprímalo: haga clic derecho sobre el archivo ZIP descargado →
   **"Extraer todo..."** (Windows lo hace sin necesidad de instalar
   nada aparte) → elija como destino la carpeta **Documentos** y
   confirme. Esto crea la carpeta
   `Documentos\agente-encuesta-hogares` con el proyecto adentro.
4. Abra esa carpeta y haga doble clic en **`instalar.bat`**. Se abre una
   ventana que verifica qué falta e instala automáticamente lo
   necesario (puede tardar unos minutos la primera vez). Si en el
   camino pide instalar Node.js, instálelo con las opciones por defecto
   y vuelva a hacer doble clic en `instalar.bat` para continuar donde
   quedó.
5. Cuando termine, haga doble clic en **`abrir_agente.bat`**, dentro de
   esa misma carpeta.

Listo — continúe en el "Paso 3: Obtener los datos del año a analizar",
más abajo.

### Instalación manual (con conocimientos técnicos)

#### Requisitos previos (instalación única)

Los siguientes programas se instalan una sola vez. Si ya cuenta con
alguno instalado, puede omitir ese paso.

| Programa | Función | Dónde obtenerlo |
|---|---|---|
| **Git** | Descargar y actualizar este proyecto | https://git-scm.com/downloads |
| **Anaconda** | Incluye Python y las librerías de análisis de datos | https://www.anaconda.com/download |
| **Visual Studio Code** | Editor para abrir el proyecto | https://code.visualstudio.com/ |
| **Node.js** | Requerido por Claude Code | https://nodejs.org (versión LTS) |
| **Claude Code** | Herramienta que ejecuta al agente | https://claude.com/claude-code (instrucciones de instalación incluidas) |
| **7-Zip** | Para descomprimir el archivo `.RAR` que distribuye el INE | https://www.7-zip.org/ |

Instale cada programa con las opciones por defecto del instalador; no se
requiere configuración adicional.

---

## Paso 1: Descargar el proyecto

Abra una terminal (en Windows: busque "Git Bash" en el menú de inicio, si
lo instaló junto con Git) y ejecute:

```bash
git clone https://github.com/MCornesLucas/agente-encuesta-hogares.git
cd agente-encuesta-hogares
```

Esto crea una carpeta `agente-encuesta-hogares` con el contenido completo
del proyecto.

## Paso 2: Instalar las dependencias (Node.js, Claude Code y Python)

La forma más simple es hacer **doble clic en `instalar.bat`**, dentro de
la carpeta `agente-encuesta-hogares`. Se abre una ventana que verifica
qué falta e instala automáticamente lo necesario. Si solicita instalar
Node.js, abrirá la página de descarga en el navegador; instálelo con las
opciones por defecto y vuelva a ejecutar `instalar.bat` para continuar
donde quedó.

Alternativamente, desde una terminal, dentro de la carpeta del proyecto:

```bash
pip install -e ".[dev]"
```

Y verifique tener instalados [Node.js](https://nodejs.org) y Claude Code
(`npm install -g @anthropic-ai/claude-code`) — ver la tabla de
requisitos previos.

Este paso instala las librerías de Python necesarias para el análisis
(lectura de datos, generación de gráficas, etc.). Puede demorar uno o dos
minutos.

## Paso 3: Obtener los datos del año a analizar

En resumen: acceda al catálogo del INE, acepte sus términos de uso,
descargue la base del año de interés, y copie los archivos a la carpeta
`data/` del proyecto. El formato exacto varía según el año (2019, dos
archivos `.sav`; desde 2023, un único CSV combinado, cuyo nombre exacto
también varía según el año); el proyecto admite ambos formatos
automáticamente.

La guía completa, con el detalle de cada paso, está en
[`data/README.md`](data/README.md) — se recomienda seguirla, ya que
amplía este resumen. También es posible pedirle al agente que guíe este
proceso directamente (ver Paso 5).

> Estos archivos de datos **nunca se suben a GitHub**: su uso es personal,
> conforme a las condiciones del INE. El proyecto ya está configurado
> para excluirlos automáticamente.

## Paso 4: Abrir el proyecto en Claude Code

La forma más simple es hacer doble clic en **`abrir_agente.bat`**, en la
raíz del proyecto. Se abre una terminal ya ubicada en la carpeta
correspondiente y lanza Claude Code directamente — listo para continuar
con el Paso 5.

Alternativamente, para hacerlo manualmente o si se va a editar el
proyecto:

1. Abra Visual Studio Code y abra la carpeta `agente-encuesta-hogares`
   (`Archivo > Abrir Carpeta...`).
2. Abra una terminal integrada (`Terminal > Nueva Terminal`, o `` Ctrl+` ``).
3. Escriba `claude` y presione Enter. Esto abre Claude Code, ya ubicado en
   la carpeta del proyecto.

## Paso 5: Solicitar el análisis al agente

En la conversación con Claude Code, describa lo que necesita con sus
propias palabras. Por ejemplo:

> Quiero hacer el análisis de la Encuesta de Hogares con los datos de 2024
> que puse en la carpeta data/

Claude reconocerá que la solicitud corresponde al agente de este
proyecto y comenzará a trabajar. Si en algún momento no se activa
automáticamente, puede solicitarlo de forma explícita:

> Usá el agente encuesta-hogares para analizar los datos de 2024

## Paso 6: Completar los formularios

A partir de este punto, **no es necesario escribir nada más en la
terminal**: el agente abrirá en el navegador una serie de pantallas
(bienvenida, ubicación de los datos, contenido del informe, etc.), que se
completan con clics y algún campo de texto breve; al confirmar cada una,
continúa automáticamente con la siguiente. La terminal de Claude Code
permanece en segundo plano; no requiere supervisión. Cada pantalla
incluye, además, un enlace para **salir sin terminar el informe**, por si
se decide no continuar.

La primera pantalla permite elegir qué **bloques temáticos** incluir en
el informe — Brecha Digital, Hogares, Territorio, Vivienda y, si hay
datos disponibles para el año elegido, Seguridad Alimentaria, Empleo, y
Seguridad y Victimización. Ninguno viene preseleccionado, ni siquiera
Brecha Digital: se elige uno, varios, o todos.

A continuación, otra pantalla presenta el catálogo de métricas puntuales
disponibles dentro de los bloques elegidos (organizadas por tema, cada
una con una breve explicación), y permite proponer una métrica adicional
que no figure en la lista. Si el agente detecta un problema con algo
propuesto (por ejemplo, un cruce que no puede calcularse de forma
confiable con los datos disponibles), lo indicará en otra pantalla junto
con una alternativa válida, para aceptarla, proponer otra, o descartar
esa métrica del informe.

**Tras confirmar el catálogo, el proceso demora algunos minutos — no es
instantáneo.** Las 42 métricas fijas del catálogo se arman y se calculan
de forma mecánica: con los datos reales de 2025, el notebook completo de
41 métricas se ejecuta en unos 25 segundos y el HTML y el PDF se generan
en unos 15 segundos más. Lo que agrega tiempo es la redacción del resumen
analítico a partir de las cifras calculadas y cualquier comparación entre
años o métrica a medida que se haya pedido — esas dos últimas las sigue
escribiendo el modelo en el momento, no son mecánicas. Que la terminal
permanezca sin novedades visibles durante un rato es esperable, no indica
un error.

**Si preocupa llegar al límite de uso del plan a mitad de una corrida
con bastante comparación entre años o varias métricas a medida**, es
preferible generar el informe en varias corridas más chicas —
encadenándolas con el botón "crear un nuevo informe" del Paso 7 — en vez
de arriesgarse a que una corrida larga se corte a mitad de camino. Cada
corrida produce su propio informe (notebook, HTML y PDF); si se eligen
bloques distintos en cada una, quedan varios informes parciales para el
mismo año, no uno solo combinado.

## Paso 7: Revisar los resultados

Se generan tres archivos nuevos en `notebooks/`, todos identificados con
el año elegido (por ejemplo, `Informe_ECH_2024.ipynb/.html/.pdf`; si se
repite la corrida para el mismo año, el informe anterior no se pierde,
queda guardado con el sufijo "(anterior)"):

- El notebook, con el análisis completo y el código incluido, para quien
  desee revisar el detalle técnico.
- Un informe en HTML, sin código, pensado para compartir con cualquier
  persona.
- Un **informe en PDF**, con formato de documento profesional (portada,
  tipografía cuidada, gráficas ajustadas a la página). El agente genera
  siempre ambos formatos, y copia el PDF automáticamente a la **carpeta
  de Descargas** — no es necesario buscarlo dentro del proyecto.

La pantalla final incluye un botón para abrir cada formato directamente,
además de un botón para **crear un nuevo informe** (otro año, u otra
selección de métricas) sin cerrar la ventana ni volver a ejecutar
`abrir_agente.bat` — retoma directamente el primer formulario, dentro de
la misma conversación.

Con esto concluye el trabajo del agente: el análisis queda guardado
localmente; nada se publica automáticamente ni el agente ofrecerá
hacerlo.

---

## Limitaciones metodológicas

Para leer el informe con criterio, conviene saber esto de antemano — cada
punto está desarrollado con más detalle en
[`docs/METODOLOGIA.md`](docs/METODOLOGIA.md):

- **Sin margen de error ni test de significancia.** Los microdatos
  públicos del INE no incluyen las variables de diseño muestral
  (conglomerado/estrato) necesarias para calcular un error estándar
  correcto. Calcularlo igual, asumiendo muestreo aleatorio simple,
  daría una precisión falsa — por eso el informe no lo hace. Los
  porcentajes son estimaciones puntuales ponderadas, no inferencia con
  incertidumbre cuantificada.
- **Hacinamiento** usa el umbral clásico (más de 2 personas por cuarto),
  no el método más nuevo de umbral ajustado por composición del hogar
  que usan algunos países de la UE/OCDE.
- **Seguridad alimentaria (FIES)** se releva sobre una submuestra de
  hogares, no sobre el total de la encuesta — los resultados de ese
  bloque representan a esa submuestra, no a la población completa con
  la misma precisión que el resto del informe.
- **Razón de dependencia demográfica** es una relación *potencial*, calculada
  a partir de tramos de edad — no mide si esas personas efectivamente
  trabajan o no.
- **Cohorte generacional** (cuando el informe incluye esa métrica) es una
  aproximación de corte transversal a partir de la edad del jefe/a de
  hogar en esta única corrida, no un panel que siga a las mismas
  personas a través de los años.
- **Celdas con pocos casos.** Cuando un cruce (ej. un tipo de delito
  específico en un departamento chico) tiene pocas observaciones detrás,
  el agente lo aclara en el texto — esa estimación puntual es menos
  confiable que el resto, aunque el cálculo esté bien hecho.
- **Los porcentajes están ponderados** por el factor de expansión
  muestral del INE (para que representen a la población, no solo a
  quienes fueron encuestados) desde la versión 0.3.0 del proyecto — un
  informe generado con una versión anterior puede diferir levemente en
  sus números respecto a uno generado ahora para el mismo año. Ver
  [`CHANGELOG.md`](CHANGELOG.md).

---

## Preguntas frecuentes

**¿Es necesario saber programar?**
No. Toda la interacción ocurre mediante formularios en el navegador, en
español, sin exposición a código ni comandos. El código existe, pero no
es necesario modificarlo ni comprenderlo para usar el agente.

**¿Qué ocurre si el INE modificó el formato o los nombres de las
preguntas de la encuesta entre 2019 y el año utilizado?**
El agente lo detecta automáticamente al validar los datos nuevos, y
solicita confirmación antes de asumir cualquier cambio — nunca infiere en
silencio.

**¿Es posible analizar más de un año y compararlos?**
Sí — el propio formulario del catálogo permite marcar qué métricas
comparar y con qué años (dos años se muestran como comparación directa;
tres o más, como serie por año). También puede pedirse por chat con las
propias palabras, por ejemplo: "quiero comparar el análisis de 2019 con
el de 2024".

**¿Dónde se documentan los criterios de rigor que sigue el agente?**
En [`docs/METODOLOGIA.md`](docs/METODOLOGIA.md), que reúne las reglas de
rigor estadístico y claridad definidas durante la construcción del
análisis original. Los procedimientos paso a paso (verificación,
generación del PDF, publicación) están en
[`docs/FLUJO_DE_TRABAJO.md`](docs/FLUJO_DE_TRABAJO.md), y las
convenciones para justificar cada tipo de gráfica en
[`docs/CONVENCIONES_DE_GRAFICAS.md`](docs/CONVENCIONES_DE_GRAFICAS.md).
Las fuentes académicas e institucionales detrás de cada métrica y cada
tipo de gráfica están consolidadas en
[`docs/BIBLIOGRAFIA.md`](docs/BIBLIOGRAFIA.md).

**¿El agente registra la actividad del usuario?**
Sí, un registro mínimo y local: qué pantallas se mostraron, cuándo, qué
se respondió en cada una (el año, las métricas marcadas — necesario para
poder diagnosticar un "marqué X y el informe trajo otra cosa"), cuánto
demoró cada paso, y si algo falló. Los formularios no piden datos
personales, así que el registro tampoco los contiene — es una regla
documentada en el propio código (`bitacora.py`). Se guarda en
`logs/bitacora.jsonl`, **en la propia computadora**, sin subirse ni
compartirse automáticamente. Su propósito es permitir que, ante un
problema reportado, quien mantiene el proyecto pueda diagnosticarlo a
partir de ese archivo, en lugar de depender de una descripción de
memoria.

**¿Cómo se ejecutan los tests automáticos?**

Desde la terminal, en la carpeta del proyecto:

```bash
python -m pytest -q
```

O desde Visual Studio Code, en el panel de Testing (ícono de matraz en la
barra lateral).

---

## Estructura del proyecto

```
agente-encuesta-hogares/
├── instalar.bat                 # Instala lo que falte (Node.js, Claude Code, dependencias)
├── abrir_agente.bat             # Abre el agente
├── .claude/
│   └── instrucciones/
│       └── encuesta-hogares.md  # El flujo guiado: instrucciones que sigue la sesión (importadas por CLAUDE.md)
├── docs/
│   ├── METODOLOGIA.md              # Reglas de rigor estadístico y claridad
│   ├── FLUJO_DE_TRABAJO.md         # Procedimientos: verificación, PDF, publicación, año nuevo
│   ├── CONVENCIONES_DE_GRAFICAS.md # Qué tipo de gráfica usar y con qué fundamento
│   ├── BIBLIOGRAFIA.md             # Fuentes académicas consolidadas
│   └── CURACION_DEL_CATALOGO.md    # Cómo incorporar una métrica al catálogo permanente (dueño)
├── src/
│   └── encuesta_hogares/        # Código de análisis, reutilizable año a año
│       ├── generar_informe.py      # Pipeline: construir (verificar, ejecutar una vez) y entregar (HTML, PDF)
│       ├── notebook_builder.py     # Arma las celdas del informe para las métricas del catálogo
│       └── verificacion_notebook.py # Verificaciones del notebook antes y después de ejecutarlo
├── notebooks/                   # Informes generados (uno por año)
├── tests/                       # Tests automáticos de la lógica de análisis
├── data/                        # Archivos de datos del usuario (no se suben a git)
└── pyproject.toml
```

## Fuente de los datos

Instituto Nacional de Estadística (INE) — Encuesta Continua de Hogares (ECH).
https://www4.ine.gub.uy/Anda5/index.php/catalog/Encuestas_a_hogares

## Licencia

Este proyecto se distribuye bajo [PolyForm Noncommercial 1.0.0](LICENSE):
permite usar, copiar, modificar y compartir el código libremente para
fines académicos, educativos, de investigación, y cualquier otro uso no
comercial. Ver el archivo [`LICENSE`](LICENSE) para el texto completo.

## Contribuir

Ver [`CONTRIBUTING.md`](CONTRIBUTING.md): cómo correr los tests, las
reglas no negociables del proyecto (ponderación, gráficas, citas), y cómo
agregar una métrica nueva al catálogo.
