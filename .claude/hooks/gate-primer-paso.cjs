// Hook PreToolUse: hace cumplir, a nivel de herramienta (no solo de texto
// de instrucciones), la regla innegociable de .claude/instrucciones/encuesta-hogares.md
// de que el formulario de bienvenida (formularios.plantilla_bienvenida) es
// siempre la primera accion de la conversacion. Antes de esa llamada por
// Bash, solo se permite leer los tres documentos que el propio archivo del
// agente indica "antes de hacer nada" (METODOLOGIA.md, FLUJO_DE_TRABAJO.md,
// CONVENCIONES_DE_GRAFICAS.md); cualquier otro Bash/Read/Glob/Grep se
// bloquea con un motivo que el modelo puede leer y corregir en el momento,
// en vez de depender de que respete la instruccion por su cuenta.
//
// Bug real encontrado en una corrida real (no en pruebas sinteticas): la
// primera version de este hook solo miraba el TEXTO CRUDO del comando Bash
// buscando la subcadena "plantilla_bienvenida". Pero el propio archivo del
// agente instruye escribir el codigo Python a un archivo temporal con la
// herramienta Write y correrlo con `run_python.bat archivo.py` (nunca un
// heredoc de Bash) - en ese patron, "plantilla_bienvenida" vive DENTRO del
// archivo .py, no en el texto del comando Bash, asi que la busqueda nunca
// coincidia. Resultado real: la llamada que de verdad mostraba el
// formulario de bienvenida quedaba denegada para siempre, en un bucle sin
// salida - el peor caso posible, porque bloqueaba el flujo entero desde el
// primer paso. Ahora, si el comando referencia un archivo .py, tambien se
// lee ese archivo y se busca ahi.
const fs = require("fs");
const os = require("os");
const path = require("path");
const { registrar } = require("./_lib_bitacora.cjs");

const DOCS_PERMITIDOS_ANTES_DEL_PASO_1 = ["metodologia.md", "flujo_de_trabajo.md", "convenciones_de_graficas.md"];

// El marcador de "ya se mostro la bienvenida" es uno por sesion y hasta
// ahora no se borraba nunca: quedaba un archivo suelto en la carpeta
// temporal por cada corrida, para siempre. Se limpian los de mas de un
// dia (una sesion no dura tanto, asi que ninguno de esos sigue en uso).
const UN_DIA_EN_MS = 24 * 60 * 60 * 1000;

function limpiarMarcadoresViejos() {
  try {
    const limite = Date.now() - UN_DIA_EN_MS;
    for (const nombre of fs.readdirSync(os.tmpdir())) {
      if (!nombre.startsWith("encuesta-hogares-bienvenida-") || !nombre.endsWith(".marker")) continue;
      const ruta = path.join(os.tmpdir(), nombre);
      try {
        if (fs.statSync(ruta).mtimeMs < limite) fs.unlinkSync(ruta);
      } catch {
        // Otro proceso lo borro primero, o no se puede leer - seguir.
      }
    }
  } catch {
    // Limpiar archivos temporales nunca puede impedir que el hook cumpla
    // su funcion real, que es dejar pasar o bloquear la herramienta.
  }
}

function comandoMuestraLaBienvenida(command) {
  if (command.includes("plantilla_bienvenida")) {
    return true;
  }
  const rutasPy = command.match(/[^\s"']+\.py\b/g) || [];
  for (const ruta of rutasPy) {
    try {
      if (fs.readFileSync(ruta, "utf-8").includes("plantilla_bienvenida")) {
        return true;
      }
    } catch {
      // Archivo temporal que ya no existe, o ruta no legible desde aca -
      // no es motivo para tirar el hook abajo, seguir con las demas rutas.
    }
  }
  return false;
}

let raw = "";
process.stdin.on("data", (chunk) => (raw += chunk));
process.stdin.on("end", () => {
  let input;
  try {
    input = JSON.parse(raw);
  } catch {
    process.exit(0);
  }

  const sessionId = input.session_id || "sin-sesion";
  const marker = path.join(os.tmpdir(), `encuesta-hogares-bienvenida-${sessionId}.marker`);

  if (fs.existsSync(marker)) {
    process.exit(0);
  }

  const toolName = input.tool_name;
  const toolInput = input.tool_input || {};

  if (toolName === "Bash" && typeof toolInput.command === "string" && comandoMuestraLaBienvenida(toolInput.command)) {
    limpiarMarcadoresViejos();
    fs.writeFileSync(marker, "");
    process.exit(0);
  }

  if (
    toolName === "Read" &&
    typeof toolInput.file_path === "string" &&
    DOCS_PERMITIDOS_ANTES_DEL_PASO_1.some((doc) => toolInput.file_path.toLowerCase().includes(doc))
  ) {
    process.exit(0);
  }

  registrar("hook_bloqueo", { hook: "primer-paso", ...{ herramienta: toolName } });
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason:
          "Regla innegociable del proyecto: antes de llamar por Bash a " +
          "formularios.plantilla_bienvenida(), no se puede usar ninguna otra " +
          "herramienta (las unicas excepciones son leer, con Read, " +
          "docs/METODOLOGIA.md, docs/FLUJO_DE_TRABAJO.md o " +
          "docs/CONVENCIONES_DE_GRAFICAS.md). Mostrá el formulario de " +
          "bienvenida primero.",
      },
    })
  );
  process.exit(0);
});
