// Verificación: el "Resumen analítico final" no puede citar cifras que
// ningún output ejecutado del notebook contenga. Es el único lugar donde
// los números se transcriben a prosa. Hasta la v0.13.6 era el hook
// gate-resumen-cifras-inventadas.cjs; ahora es un módulo que
// `gate-notebook.cjs` corre junto con las otras verificaciones leyendo el
// .ipynb una sola vez. Sigue pudiendo correrse solo (sus tests lo hacen).
//
// Equilibrio buscado: atrapar un número inventado o mal transcripto SIN
// bloquear un redondeo legítimo ("cerca del 40%" cuando el dato es 40,13%).
// Un falso positivo acá dejaría el informe sin poder generarse.
const path = require("path");
const { resolverNotebookEjecutado } = require("./_lib_notebook_ejecutado.cjs");
const { registrar } = require("./_lib_bitacora.cjs");

const NOMBRE = "resumen-cifras-inventadas";
const ENCABEZADO_RESUMEN = /resumen anal[ií]tico/i;

function textoDeCelda(cell) {
  return Array.isArray(cell.source) ? cell.source.join("") : cell.source || "";
}

function textoDeOutputs(cell) {
  let texto = "";
  for (const out of cell.outputs || []) {
    if (out.text) texto += Array.isArray(out.text) ? out.text.join("") : out.text;
    const plano = out.data && out.data["text/plain"];
    if (plano) texto += Array.isArray(plano) ? plano.join("") : plano;
  }
  return texto;
}

/** Números "de estadística": con decimales, o enteros con % pegado. */
function cifrasDe(texto) {
  const encontradas = [];
  const patron = /(\d+(?:[.,]\d+)?)\s*%|(\d+[.,]\d+)/g;
  let m;
  while ((m = patron.exec(texto)) !== null) {
    const crudo = (m[1] !== undefined ? m[1] : m[2]).replace(",", ".");
    const valor = Number(crudo);
    if (!Number.isFinite(valor)) continue;
    if (Number.isInteger(valor) && valor >= 1900 && valor <= 2100) continue; // años
    const decimales = crudo.includes(".") ? crudo.split(".")[1].length : 0;
    encontradas.push({ texto: m[0].trim(), valor, decimales });
  }
  return encontradas;
}

function numerosDe(texto) {
  const valores = [];
  const patron = /\d+(?:[.,]\d+)?/g;
  let m;
  while ((m = patron.exec(texto)) !== null) {
    const valor = Number(m[0].replace(",", "."));
    if (Number.isFinite(valor)) valores.push(valor);
  }
  return valores;
}

function redondear(valor, decimales) {
  const factor = 10 ** decimales;
  return Math.round(valor * factor) / factor;
}

// Devuelve la lista (sin repetidos) de cifras del resumen sin respaldo;
// vacía si el notebook no está ejecutado todavía (no hay contra qué comparar).
function verificar(nb) {
  const celdas = nb.cells || [];
  const reales = [];
  for (const cell of celdas) {
    if (cell.cell_type === "code") reales.push(...numerosDe(textoDeOutputs(cell)));
  }
  if (reales.length === 0) return [];
  let dentroDelResumen = false;
  const sospechosas = [];
  for (const cell of celdas) {
    if (cell.cell_type !== "markdown") continue;
    const texto = textoDeCelda(cell);
    if (ENCABEZADO_RESUMEN.test(texto)) {
      dentroDelResumen = true;
      continue;
    }
    if (!dentroDelResumen) continue;
    for (const cifra of cifrasDe(texto)) {
      const existe = reales.some((real) => redondear(real, cifra.decimales) === cifra.valor);
      if (!existe) sospechosas.push(cifra.texto);
    }
  }
  return [...new Set(sospechosas)];
}

function motivo(rutaNotebook, sospechosas) {
  return (
    `El "Resumen analítico final" cita cifras que no aparecen en ningún resultado ` +
    `ejecutado del notebook: ${sospechosas.join(", ")}. Es el único lugar del informe donde los números ` +
    `se escriben a mano, así que un error de transcripción ahí no lo detecta nada más. ` +
    `Sacá cada número del resultado real (con Python, no de memoria) y volvé a escribir ` +
    `esa parte del resumen — si el número es correcto pero está redondeado a menos ` +
    `decimales de los que muestra el notebook, igual tiene que coincidir al redondear.`
  );
}

function evaluar(rutaNotebook, nb) {
  const sospechosas = verificar(nb);
  if (sospechosas.length === 0) return null;
  registrar("hook_bloqueo", { hook: NOMBRE, cifras: sospechosas, notebook: path.basename(rutaNotebook) });
  return motivo(rutaNotebook, sospechosas);
}

module.exports = { NOMBRE, cifrasDe, numerosDe, verificar, motivo, evaluar };

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
    const encontrado = resolverNotebookEjecutado(comando);
    if (!encontrado) process.exit(0);
    const razon = evaluar(encontrado.ruta, encontrado.nb);
    if (razon === null) process.exit(0);
    process.stdout.write(
      JSON.stringify({
        hookSpecificOutput: { hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: razon },
      })
    );
    process.exit(0);
  });
}
