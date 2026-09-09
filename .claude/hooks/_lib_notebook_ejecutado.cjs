// Módulo compartido por los tres hooks que necesitan saber sobre qué
// notebook corre un `jupyter nbconvert --execute` disparado por la
// herramienta Bash (_lib_check_notebook_sin_duplicados.cjs,
// _lib_check_notebook_metrica_sin_grafica_o_cita.cjs,
// gate-notebook-graficas-faltantes.cjs).
//
// Bug real encontrado replicando el patrón exacto que documenta
// docs/FLUJO_DE_TRABAJO.md (pasos 5 y 8): nbconvert nunca se invoca suelto
// por Bash, siempre envuelto en un archivo .py con
// bitacora.medir_comando(...) y corrido con `run_python.bat archivo.py` -
// el mismo patrón "Write + run_python.bat" cuyo bug ya arregló
// gate-primer-paso.cjs (ver el comentario de ese archivo: "usá siempre
// Write, nunca un heredoc de Bash"). Los tres hooks de arriba buscaban
// "nbconvert"/"--execute" y la ruta del .ipynb solo en el texto CRUDO del
// comando Bash - con el patrón real, ese texto es apenas
// `run_python.bat archivo.py`, así que ninguno de los tres se disparaba
// nunca. Ahora, igual que gate-primer-paso.cjs, si el comando referencia
// un archivo .py también se lee ese archivo y se busca ahí.
const fs = require("fs");
const path = require("path");

function textoRelevante(command) {
  let texto = command;
  const rutasPy = command.match(/[^\s"']+\.py\b/g) || [];
  for (const ruta of rutasPy) {
    try {
      texto += "\n" + fs.readFileSync(ruta, "utf-8");
    } catch {
      // Archivo temporal que ya no existe, o ruta no legible desde aca -
      // no es motivo para tirar el hook abajo, seguir con las demas rutas.
    }
  }
  return texto;
}

// Devuelve { ruta, nb } si el comando (o algún .py que referencia) corre
// `nbconvert --execute` sobre un notebook que existe y se puede parsear
// como JSON; null si no aplica ninguna de esas condiciones.
function resolverNotebookEjecutado(command) {
  if (typeof command !== "string") return null;

  const texto = textoRelevante(command);
  if (!texto.includes("nbconvert") || !texto.includes("--execute")) {
    return null;
  }

  const match = texto.match(/["']?([^"'\s]+\.ipynb)["']?/);
  if (!match) return null;

  let rutaNotebook = match[1];
  if (!path.isAbsolute(rutaNotebook)) {
    rutaNotebook = path.join(process.cwd(), rutaNotebook);
  }
  if (!fs.existsSync(rutaNotebook)) return null;

  try {
    return { ruta: rutaNotebook, nb: JSON.parse(fs.readFileSync(rutaNotebook, "utf-8")) };
  } catch {
    return null;
  }
}

module.exports = { resolverNotebookEjecutado };
