// Verificación: cada métrica del notebook (encabezado "### N. …") tiene que
// llevar una gráfica (viz.plot_...) y una cita que respalde el tipo de
// gráfica (docs/CONVENCIONES_DE_GRAFICAS.md). Hasta la v0.13.6 era el hook
// gate-notebook-metrica-sin-grafica-o-cita.cjs; ahora es un módulo que
// `gate-notebook.cjs` corre junto con las otras verificaciones leyendo el
// .ipynb una sola vez. Sigue pudiendo correrse solo, que es como lo
// ejercitan sus tests.
//
// Bug real que motivó su test contra el notebook generado de verdad: el
// hook buscaba un formato de encabezado que el generador ya no emitía y
// pasó en verde durante meses sin mirar ninguna métrica. Por eso el patrón
// acepta "### 7.", "### Métrica 7." y variantes con guion, y por eso hay un
// test que lo enfrenta a la salida real de notebook_builder.
const path = require("path");
const { resolverNotebookEjecutado } = require("./_lib_notebook_ejecutado.cjs");
const { registrar } = require("./_lib_bitacora.cjs");

const NOMBRE = "notebook-metrica-sin-grafica-o-cita";

const AUTORES_CONOCIDOS = [
  "Cleveland", "McGill", "Tufte", "Knaflic", "Few", "Ware", "Wilke", "Nightingale",
  "Data Visualization Society", "Hofmann", "Wickham", "Kafadar", "Weissgerber", "storytellingwithdata",
];

function tieneCitaConFundamento(texto) {
  if (AUTORES_CONOCIDOS.some((autor) => texto.includes(autor))) return true;
  const patronGenerico = /\([A-ZÀ-Ý][\wÀ-ÿ.]+(?:\s*(?:&|y|et al\.?)\s*[A-ZÀ-Ý][\wÀ-ÿ.]+)?,?\s*\d{4}\)/;
  return patronGenerico.test(texto);
}

function fuente(cell) {
  return Array.isArray(cell.source) ? cell.source.join("") : cell.source || "";
}

function verificar(nb) {
  const cells = nb.cells || [];
  const encabezadoMetrica = /^#{2,4}\s*(?:M[ée]trica\s+)?(\d{1,2})[.\s—-]/;
  const encabezadoDeSeccion = /^##\s+(?!\d)/;
  const metricas = [];
  let actual = null;
  cells.forEach((cell) => {
    if (cell.cell_type === "markdown") {
      const texto = fuente(cell);
      const primeraLinea = texto.split("\n").find((l) => l.trim().length > 0) || "";
      const nuevoEncabezado = primeraLinea.match(encabezadoMetrica);
      if (nuevoEncabezado) {
        if (actual) metricas.push(actual);
        actual = { numero: nuevoEncabezado[1], markdown: [texto], tieneGrafica: false };
        return;
      }
      if (encabezadoDeSeccion.test(primeraLinea)) {
        if (actual) metricas.push(actual);
        actual = null;
        return;
      }
      if (actual) actual.markdown.push(texto);
      return;
    }
    if (cell.cell_type === "code" && actual && /viz\.plot_\w+\(/.test(fuente(cell))) {
      actual.tieneGrafica = true;
    }
  });
  if (actual) metricas.push(actual);

  const violaciones = [];
  metricas.forEach((m) => {
    const problemas = [];
    if (!m.tieneGrafica) problemas.push("sin ninguna gráfica (viz.plot_...)");
    if (!tieneCitaConFundamento(m.markdown.join("\n"))) problemas.push("sin cita/fuente en la justificación");
    if (problemas.length > 0) violaciones.push(`Métrica ${m.numero}: ${problemas.join(" y ")}`);
  });
  return violaciones;
}

function motivo(rutaNotebook, violaciones) {
  return (
    `El notebook "${rutaNotebook}" tiene ${violaciones.length} métrica(s) que incumplen ` +
    `docs/CONVENCIONES_DE_GRAFICAS.md: ${violaciones.join("; ")}. Cada métrica necesita su gráfica (nunca solo un número ` +
    `o tabla de texto — para una diferencia entre dos grupos, usá visualization.plot_dumbbell) y su celda de ` +
    `markdown tiene que citar el principio o la fuente que respalda el tipo de gráfica elegido. Corregí esas ` +
    `celdas con nbformat antes de volver a ejecutar el notebook.`
  );
}

function evaluar(rutaNotebook, nb) {
  const violaciones = verificar(nb);
  if (violaciones.length === 0) return null;
  registrar("hook_bloqueo", { hook: NOMBRE, violaciones: violaciones.length, notebook: path.basename(rutaNotebook) });
  return motivo(rutaNotebook, violaciones);
}

module.exports = { NOMBRE, AUTORES_CONOCIDOS, tieneCitaConFundamento, verificar, motivo, evaluar };

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
