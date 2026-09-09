// PreToolUse (Bash): las tres verificaciones del notebook en UN solo
// proceso — gráficas que se duplicarían, métricas sin gráfica o sin cita,
// cifras del resumen sin respaldo. Hasta la v0.13.6 eran tres hooks
// separados registrados en settings.json: cada llamada Bash lanzaba tres
// procesos de Node y, cuando el comando era el nbconvert, los tres leían y
// parseaban el mismo .ipynb (2 MB con outputs) por su cuenta. Ahora el
// notebook se resuelve y se parsea una vez, y cada verificación vive en su
// módulo `_lib_check_*.cjs` (con su propia prueba, que lo corre suelto).
//
// Solo actúa si el comando (o un .py que referencia) corre
// `jupyter nbconvert --execute` sobre un notebook existente — ver
// _lib_notebook_ejecutado.cjs. El pipeline `encuesta_hogares.generar_informe`
// no pasa por acá: hace las mismas verificaciones en Python antes de
// ejecutar (src/encuesta_hogares/verificacion_notebook.py).
const { resolverNotebookEjecutado } = require("./_lib_notebook_ejecutado.cjs");

const VERIFICACIONES = [
  require("./_lib_check_notebook_sin_duplicados.cjs"),
  require("./_lib_check_notebook_metrica_sin_grafica_o_cita.cjs"),
  require("./_lib_check_resumen_cifras_inventadas.cjs"),
];

let raw = "";
process.stdin.on("data", (chunk) => (raw += chunk));
process.stdin.on("end", () => {
  let input;
  try {
    input = JSON.parse(raw);
  } catch {
    process.exit(0);
  }
  const comando = (input.tool_input || {}).command;
  if (input.tool_name !== "Bash" || typeof comando !== "string") process.exit(0);

  const resultado = resolverNotebookEjecutado(comando);
  if (!resultado) process.exit(0);

  const razones = [];
  for (const verificacion of VERIFICACIONES) {
    const razon = verificacion.evaluar(resultado.ruta, resultado.nb);
    if (razon !== null) razones.push(razon);
  }
  if (razones.length === 0) process.exit(0);

  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: razones.join("\n\n"),
      },
    })
  );
  process.exit(0);
});
