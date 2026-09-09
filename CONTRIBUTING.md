# Guía para contribuir

Este proyecto se distribuye bajo [PolyForm Noncommercial 1.0.0](LICENSE) —
uso, copia y modificación libres para fines no comerciales (ver la
licencia para el alcance exacto). Esta guía es para quien vaya a tocar el
código, ya sea una persona o una sesión de Claude Code.

## Antes de nada

1. Instalación y estructura del proyecto: ver [`README.md`](README.md).
2. **Leer [`docs/METODOLOGIA.md`](docs/METODOLOGIA.md),
   [`docs/FLUJO_DE_TRABAJO.md`](docs/FLUJO_DE_TRABAJO.md) y
   [`docs/CONVENCIONES_DE_GRAFICAS.md`](docs/CONVENCIONES_DE_GRAFICAS.md)
   enteros antes de tocar cualquier archivo permanente.** No es opcional
   — reúnen las reglas de rigor estadístico y claridad, los
   procedimientos paso a paso, y las convenciones de gráficas que existen
   porque en algún momento se encontró un problema real. Las reglas más
   importantes, resumidas:
   - **Toda estadística de Hogares/Personas se pondera** por el factor de
     expansión muestral del INE — nunca `.mean()`/`.median()` simple. Usar
     los helpers ya armados (`analysis.pct_ponderado`,
     `media_ponderada_por`, `proporcion_ponderada`, `mediana_ponderada`).
     Un test (`test_verificacion_ponderacion.py`) revisa automáticamente
     `analysis.py`/`preprocessing.py`/`visualization.py` buscando este
     descuido — si se agrega una función nueva que usa
     `.mean()`/`.median()`/`.value_counts()` sin pasar por esos helpers,
     el test va a fallar hasta que se pondere o se documente por qué no
     aplica (ver `encuesta_hogares.verificacion_ponderacion.ALLOWLIST`).
   - **Toda métrica lleva su gráfica**, sin excepción — ni un número
     suelto ni una tabla haciendo de gráfica.
   - **Toda justificación de gráfica cita la fuente** (principio de
     percepción visual o metodología estadística) — el público de este
     informe puede ser académico, profesional, técnico o no técnico, y la
     cita refuerza, no estorba. Las fuentes ya usadas están en
     [`docs/BIBLIOGRAFIA.md`](docs/BIBLIOGRAFIA.md).
   - **Nunca usar tenencia de tecnología como eje fijo** de un bloque que
     no es sobre tecnología — ya pasó dos veces en este proyecto y generó
     un rediseño grande cada vez. La tecnología vive en "Brecha Digital".

## Correr los tests y el linter

```bash
python -m pytest -q          # tests (dataframes sintéticos, no requieren datos reales)
python -m pytest --cov       # con reporte de cobertura
python -m ruff check src/ tests/ tools/
```

Antes de publicar un cambio que toque cómo se leen o combinan los datos
(`analysis.py`, `preprocessing.py`), ejecutar también, si hay datos
reales en `data/`:

```bash
python tools/validar_con_datos_reales.py
```

Ejercita el pipeline completo contra datos reales — atajó bugs que los
tests sintéticos no detectaban (columnas que cambian entre 2019 y 2024,
formato `.sav` vs. CSV combinado, base nacional vs. filtrada a Montevideo).

## Agregar una métrica al catálogo

Seguir el checklist de "Curación del catálogo" en
[`.claude/instrucciones/encuesta-hogares.md`](.claude/instrucciones/encuesta-hogares.md)
— cubre desde qué pregunta responde la métrica hasta la numeración del
catálogo (`_CATEGORIAS_METRICAS` en `plantillas.py`), que tiene que
quedar sin huecos ni duplicados (hay un test que lo verifica:
`test_catalogo_esta_numerado_del_1_a_N_sin_huecos_ni_duplicados`).

**Agregar también la entrada correspondiente en
`encuesta_hogares.verificacion_catalogo.MANIFEST`**, con la(s)
función(es) de `analysis.py`/`preprocessing.py` y la de
`visualization.py` que la implementan — un test
(`test_verificacion_catalogo.py`) falla si una métrica del catálogo no
tiene entrada, o si la entrada apunta a una función que no existe de
verdad. Nace de un caso real: tres métricas del catálogo activo (3, 9 y
11) no tenían ninguna función propia y quedaban libradas a que se
improvisara el cálculo en cada corrida, sin test.

## Antes de cerrar una sesión de trabajo

El agente `encuesta-hogares` no tiene permiso de usar git (ver
`.claude/settings.json`) — si escribe código nuevo y reutilizable durante
una corrida real (ej. una función para una métrica propuesta por el
usuario), queda en el disco pero sin commitear, y puede pasar
desapercibido. Antes de dar por cerrada una sesión, ejecutar:

```bash
python tools/verificar_sincronizacion.py
```

Si encuentra diferencias contra `origin/main`, revisarlas antes de
publicar — puede ser trabajo real sin commitear.

## Commits

- Mensajes en español, describiendo el *por qué* del cambio, no solo el
  *qué* — el código ya dice qué cambió.
- Un commit por cambio lógico, no una mezcla de varios sin relación.
- Si el cambio afecta los números que produce una métrica ya existente
  (ej. un fix de ponderación), documentarlo en
  [`CHANGELOG.md`](CHANGELOG.md) — alguien puede estar comparando un
  informe viejo con uno nuevo.
- Nunca `git push --force` a `main`, nunca `--no-verify`.
