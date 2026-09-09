// Verificación: celdas que terminan con la variable sola después de
// asignarla con viz.plot_...(...) — con el renderer PNG de Plotly eso
// muestra la gráfica dos veces (ver .claude/instrucciones/encuesta-hogares.md,
// paso 5). Hasta la v0.13.6 era un hook propio (gate-notebook-sin-duplicados.cjs);
// ahora es un módulo que `gate-notebook.cjs` corre junto con las otras dos
// verificaciones del notebook, leyendo el .ipynb una sola vez. Sigue
// pudiendo correrse solo (`node _lib_check_notebook_sin_duplicados.cjs`),
// que es como lo ejercitan sus tests.
const path = require("path");
const { resolverNotebookEjecutado } = require("./_lib_notebook_ejecutado.cjs");
const { registrar } = require("./_lib_bitacora.cjs");

const NOMBRE = "notebook-sin-duplicados";

function verificar(nb) {
  const violaciones = [];
  (nb.cells || []).forEach((cell, i) => {
    if (cell.cell_type !== "code") return;
    const fuente = Array.isArray(cell.source) ? cell.source.join("") : cell.source || "";
    const lineas = fuente
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l.length > 0);
    if (lineas.length === 0) return;
    const ultima = lineas[lineas.length - 1];
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(ultima)) return;
    const patronAsignacion = new RegExp("^" + ultima.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\s*=\\s*viz\\.");
    if (lineas.some((l) => patronAsignacion.test(l))) {
      violaciones.push({ celda: i, variable: ultima });
    }
  });
  return violaciones;
}

function motivo(rutaNotebook, violaciones) {
  const detalle = violaciones.map((v) => `celda ${v.celda} (variable "${v.variable}")`).join(", ");
  return (
    `El notebook "${rutaNotebook}" tiene ${violaciones.length} celda(s) que van a duplicar su gráfica ` +
    `en el output: ${detalle}. Cada una termina con la variable sola después de asignarla con ` +
    `viz.plot_...(...) - eso duplica la imagen (ver .claude/instrucciones/encuesta-hogares.md, paso 5). ` +
    `Editá esas celdas con nbformat para que terminen en "<variable>.show()" (Plotly) o sin volver a ` +
    `nombrar la variable (matplotlib), y recién ahí volvé a ejecutar el notebook.`
  );
}

// Devuelve null si no hay nada que objetar; si no, el motivo ya registrado
// en la bitácora. Es lo que usa gate-notebook.cjs.
function evaluar(rutaNotebook, nb) {
  const violaciones = verificar(nb);
  if (violaciones.length === 0) return null;
  registrar("hook_bloqueo", { hook: NOMBRE, violaciones: violaciones.length, notebook: path.basename(rutaNotebook) });
  return motivo(rutaNotebook, violaciones);
}

module.exports = { NOMBRE, verificar, motivo, evaluar };

if (require.main === module) {
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
    const razon = evaluar(resultado.ruta, resultado.nb);
    if (razon === null) process.exit(0);
    process.stdout.write(
      JSON.stringify({
        hookSpecificOutput: { hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: razon },
      })
    );
    process.exit(0);
  });
}
