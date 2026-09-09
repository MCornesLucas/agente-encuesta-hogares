# Datos

Los microdatos de la Encuesta Continua de Hogares (ECH) del INE Uruguay
**no están incluidos** en este repositorio, debido a restricciones de
redistribución de la fuente. El archivo `.gitignore` ya excluye los
archivos de datos para evitar que se suban por accidente.

## Cómo obtenerlos (paso a paso)

> **El formato del archivo varía según el año**: hasta 2019, el INE
> distribuye las bases de Hogares y Personas como dos archivos `.sav`
> separados; desde 2023, las combina en un único CSV (llamado "de
> implantación" en algunos años, con el nombre exacto cambiando de un año
> a otro). El proyecto admite ambos formatos y todas las variantes de
> nombre vistas hasta ahora automáticamente — solo cambia qué archivo se
> obtiene en el paso 5.

1. Acceda a **https://www4.ine.gub.uy/Anda5/index.php/catalog/Encuestas_a_hogares**,
   donde figura el listado de todas las ediciones de la ECH, por año.
2. Busque en la lista (o utilice el filtro de año) **"Encuesta Continua de
   Hogares, Año AAAA"**, correspondiente al año de interés, y acceda a esa
   ficha.
3. Dentro de la ficha del año, seleccione la pestaña **"OBTENER
   MICRODATOS"**.
4. Se mostrará el texto de **Términos y condiciones** del INE. Léalo y, si
   está de acuerdo, haga clic en **"Aceptar"**. Este paso debe realizarlo
   personalmente el usuario — es un acuerdo legal con el INE que no puede
   aceptarse en su nombre.
5. Se desplegará una lista de "Archivos de datos". La opción a buscar
   depende del año:
   - **2019 o anterior**: la opción denominada, aproximadamente, **"Bases
     ECH AAAA .SAV"**. Es un archivo comprimido (`.RAR`) de entre 15 y 20 MB.
   - **2023 en adelante**: la opción con el CSV combinado — el nombre del
     archivo varía según el año (casos reales: `ECH_implantacion_2023.csv`,
     `ECH_2024.csv`, `ECH_2025_implantacion.csv`) y también puede
     distribuirse dentro de un `.RAR`.

   Haga clic en el enlace de **Descargar** correspondiente.
6. **Si descargó un `.RAR`**, extráigalo — Windows no lo abre de forma
   nativa; se requiere un programa como [7-Zip](https://www.7-zip.org/)
   (gratuito) o WinRAR. Clic derecho sobre el archivo descargado →
   "Extraer aquí" (la opción exacta depende del programa instalado). Si el
   archivo ya es un `.csv` suelto, no es necesario extraer nada.
7. Identifique el contenido obtenido:
   - **Dos archivos `.sav`**: corresponden a las bases de **Hogares** y
     **Personas** (los nombres exactos pueden variar según el año; suelen
     comenzar con `H` para Hogares y `P` para Personas).
   - **Un único archivo CSV combinado** (`ECH_AAAA.csv` o una variante
     "implantación"): es la base combinada, con una fila por persona y
     los datos del hogar repetidos para cada integrante.
8. Copie esos archivos (los dos `.sav`, o el CSV combinado, según
   corresponda) a la subcarpeta del año dentro de `data/` — por ejemplo,
   `data/2024/`. Si la solicitud se realizó a través del agente, esa
   carpeta ya habrá sido creada y abierta en el Explorador antes de este
   paso. **No renombre el archivo**: el código ya reconoce las variantes
   de nombre reales.

Ante cualquier duda sobre la identificación de los archivos, puede
consultarse directamente al agente, indicando qué archivos se
extrajeron; el agente asistirá en identificarlos si es necesario (el
código detecta automáticamente, dentro de cada subcarpeta de año, los
archivos `H_*.sav`/`P_*.sav`, `ECH_AAAA.csv`, o las variantes
"implantación" — ver `config.hogares_csv_file`).

## Datos opcionales: seguridad alimentaria, empleo y seguridad/victimización

Además de Hogares y Personas, el catálogo de métricas del agente puede
incluir tres áreas adicionales, que corresponden a **descargas
independientes y no están disponibles para todos los años**:

- **Seguridad alimentaria (FIES)**: archivo `base_FIES_AAAA.csv`.
- **Empleo**: los 12 archivos mensuales `ECH_MM_AA.csv` (uno por mes) del
  módulo de seguimiento — se requieren los 12 en conjunto; con un
  subconjunto no es posible calcular el indicador anual.
- **Seguridad y victimización**: archivo `ECH_VICTIMIZACION_S2_AAAA.csv`.

Los tres se buscan y aceptan de la misma forma que la base principal
(pasos 1 a 4), dentro de la misma ficha del año en el catálogo del INE, y
se copian a la misma subcarpeta `data/AAAA/`. **No es necesario descargar
los archivos de pesos replicados** (`pesos_replicados_*`): pesan cientos
de megabytes por año y ninguna métrica del catálogo los utiliza. Si alguno no está
disponible (o el año elegido no lo incluye), no representa un problema:
el agente detecta automáticamente qué datos existen y solo ofrece las
categorías del catálogo que pueden construirse con la información
disponible.

## Carpeta `2019/`

Corresponde al año utilizado para construir y validar el análisis
original, y sirve como referencia para comparar la estructura de
cualquier año nuevo. **No debe eliminarse ni moverse**, independientemente
del año que se esté analizando.

## Cita requerida

Instituto Nacional de Estadística (INE) — Encuesta Continua de Hogares (ECH).
https://www4.ine.gub.uy/Anda5/index.php/catalog/Encuestas_a_hogares

> Los datos utilizados constituyen un extracto con fines de análisis
> personal, y no una muestra representativa completa ni un estudio
> oficial del INE.
