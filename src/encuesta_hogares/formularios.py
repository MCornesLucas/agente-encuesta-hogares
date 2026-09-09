"""Formularios locales en el navegador: la forma en que el agente le
"pregunta" cosas al usuario, en vez de hacerlo por chat.

Todo corre en la propia computadora del usuario — no hay ninguna cuenta de
por medio (ni Microsoft Forms ni nada externo), no sale a internet, no
depende de ningún servicio de terceros. `mostrar_formulario()` levanta un
servidor mínimo en localhost, abre el navegador con el HTML del paso que
corresponda, y bloquea hasta que el usuario lo completa — devuelve la
respuesta como un diccionario de Python.

El HTML de cada paso vive en `plantillas.py` (solo texto, sin servidor)
y se reexporta desde acá: `formularios.plantilla_*` es la cara pública
que usan el agente y los tests, antes y después de esa separación.
"""

from __future__ import annotations

import http.server
import json
import re
import subprocess
import threading
import traceback
from pathlib import Path

from . import bitacora, cierre, config
from .plantillas import (  # noqa: F401 — reexports: la cara pública es formularios.plantilla_*
    _CATEGORIA_EMPLEO,
    _CATEGORIA_FIES,
    _CATEGORIA_SEGURIDAD,
    _CATEGORIAS_METRICAS,
    plantilla_areas,
    plantilla_arranque,
    plantilla_bienvenida,
    plantilla_catalogo,
    plantilla_datos,
    plantilla_finalizacion,
    plantilla_revision,
)


def _origen_es_propio(handler) -> bool:
    """¿La respuesta que llega viene de la página que sirve este mismo
    servidor, o de otro sitio?

    El servidor escucha en 127.0.0.1 con un puerto al azar, pero eso solo
    no alcanza: cualquier página web abierta en el navegador de la persona
    puede probar puertos de localhost y mandar una respuesta al formulario
    en su nombre (elegir un año, marcar métricas, o directamente cerrarle
    el flujo). El rango de puertos efímeros es lo bastante chico como para
    barrerlo desde JavaScript en segundos.

    El navegador manda `Origin` en todo POST, así que alcanza con exigir
    que sea el nuestro. Si no viene `Origin` (un cliente que no es un
    navegador, ej. los tests), se acepta: el riesgo que se está cerrando
    es específicamente el de una página de otro sitio.
    """
    origen = handler.headers.get("Origin")
    if origen is None:
        return True
    puerto = handler.server.server_address[1]
    return origen in (f"http://127.0.0.1:{puerto}", f"http://localhost:{puerto}")


def _rechazar_origen_ajeno(handler) -> bool:
    """Corta la respuesta con 403 si vino de otro sitio. Devuelve True si
    ya se respondió y quien llama tiene que abandonar el pedido."""
    if _origen_es_propio(handler):
        return False
    bitacora.registrar("formulario_origen_rechazado", origen=handler.headers.get("Origin"))
    handler.send_response(403)
    handler.send_header("Content-Length", "0")
    handler.end_headers()
    return True


# Las respuestas de estos formularios son unos pocos cientos de bytes (un
# año, una lista de números de métrica). Un tope generoso evita que un
# `Content-Length` enorme —malformado o malicioso— haga que el proceso
# intente reservar esa memoria de una.
_MAXIMO_CUERPO_EN_BYTES = 1_000_000


def _leer_cuerpo(handler) -> bytes | None:
    """Lee el cuerpo del POST validando su tamaño. Devuelve None (y ya
    respondió) si el pedido no sirve: antes, un `Content-Length` que no
    fuera un número tiraba un ValueError sin manejar dentro del hilo del
    servidor."""
    crudo = handler.headers.get("Content-Length", "0")
    try:
        largo = int(crudo)
    except (TypeError, ValueError):
        largo = -1
    if largo < 0 or largo > _MAXIMO_CUERPO_EN_BYTES:
        handler.send_response(400)
        handler.send_header("Content-Length", "0")
        handler.end_headers()
        return None
    return handler.rfile.read(largo)


def _decodificar_respuesta(handler, cuerpo: bytes) -> dict | None:
    """Convierte el cuerpo del POST en el dict que espera el formulario.
    Devuelve None (y ya respondió 400) si no sirve.

    Sin esto, un cuerpo que no fuera JSON válido —o que fuera JSON pero no
    un objeto, ej. `[1,2]`— tiraba una excepción sin manejar dentro del
    hilo del servidor: la conexión moría con un traceback a stderr, el
    formulario seguía esperando como si nada, y la bitácora no registraba
    nada — justo la herramienta que existe para diagnosticar a distancia
    quedaba ciega en el único caso raro. Mismo criterio que `_leer_cuerpo`.
    """
    try:
        datos = json.loads(cuerpo)
    except (json.JSONDecodeError, UnicodeDecodeError):
        datos = None
    if not isinstance(datos, dict):
        bitacora.registrar("formulario_post_invalido", largo_cuerpo=len(cuerpo))
        handler.send_response(400)
        handler.send_header("Content-Length", "0")
        handler.end_headers()
        return None
    return datos


def _nombre_desde_html(html: str) -> str:
    """Extrae el texto del primer <h1> del HTML para identificar el
    formulario en la bitácora, sin depender de que cada llamada a
    mostrar_formulario() le pase un nombre a mano."""
    coincidencia = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL)
    if not coincidencia:
        return "formulario"
    texto = re.sub(r"<[^>]+>", "", coincidencia.group(1)).strip()
    return texto[:60] if texto else "formulario"


# ============================================================================
# Infraestructura compartida por los dos servidores (mostrar_formulario y
# mostrar_finalizacion). Vivía duplicada en cada función — ~80 líneas con
# las mismas decisiones sutiles en los dos lados — así que cada arreglo del
# servidor (la validación de Origin, el POST malformado) había que
# acordarse de hacerlo dos veces.
# ============================================================================


def _servir_html(handler, html_bytes: bytes) -> None:
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(html_bytes)))
    handler.end_headers()
    handler.wfile.write(html_bytes)


def _responder_post(handler, resultado: dict, evento: threading.Event) -> None:
    """El do_POST completo de cualquiera de los dos servidores: validación
    de origen, de tamaño y de formato — recién si todo eso pasa, la
    respuesta se guarda en `resultado` y se despierta a quien espera."""
    if _rechazar_origen_ajeno(handler):
        return
    cuerpo = _leer_cuerpo(handler)
    if cuerpo is None:
        return
    datos = _decodificar_respuesta(handler, cuerpo)
    if datos is None:
        return
    resultado.update(datos)
    respuesta = b'{"ok": true}'
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(respuesta)))
    handler.end_headers()
    handler.wfile.write(respuesta)
    evento.set()


def _servir_y_esperar(handler_cls, evento: threading.Event, timeout: float | None, evento_error: str, **detalle_error) -> bool:
    """Levanta el servidor en un puerto al azar de 127.0.0.1, abre el
    navegador, y bloquea hasta que llegue la respuesta o venza el timeout.
    Devuelve si hubo respuesta; si el servidor en sí falla, lo registra
    como `evento_error` y relanza."""
    try:
        # ThreadingHTTPServer: el navegador puede abrir mas de una conexion a
        # la vez. Un servidor de una sola conexion por vez se traba en ese
        # caso (visto en la practica con el formulario del catalogo de
        # metricas).
        with http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler_cls) as httpd:
            puerto = httpd.server_address[1]
            hilo = threading.Thread(target=httpd.serve_forever, daemon=True)
            hilo.start()
            url = f"http://127.0.0.1:{puerto}/"
            # os.startfile()/webbrowser.open() resultaron poco confiables en
            # algunos entornos; "cmd /c start" es lo mas robusto en Windows.
            subprocess.run(["cmd", "/c", "start", "", url], check=False)
            completado = evento.wait(timeout=timeout)
            httpd.shutdown()
    except Exception as e:
        bitacora.registrar(evento_error, mensaje=str(e), traceback=traceback.format_exc(), **detalle_error)
        raise
    return completado


def mostrar_formulario(html: str, timeout: float | None = config.TIMEOUT_FORMULARIO_SEGUNDOS) -> dict:
    """Sirve `html` en localhost, abre el navegador, y bloquea hasta que el
    usuario lo completa. Devuelve lo que haya mandado el formulario.
    """
    nombre = _nombre_desde_html(html)
    resultado: dict = {}
    evento = threading.Event()
    html_bytes = html.encode("utf-8")

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/favicon"):
                self.send_response(204)
                self.end_headers()
                return
            _servir_html(self, html_bytes)

        def do_POST(self):
            _responder_post(self, resultado, evento)

        def log_message(self, format, *args):
            pass

    bitacora.registrar("formulario_mostrado", nombre=nombre)
    completado = _servir_y_esperar(Handler, evento, timeout, "formulario_error", nombre=nombre)

    # Se guarda tambien lo que la persona respondio de verdad (no solo que
    # respondio) - antes, un desajuste entre lo que alguien creia haber
    # marcado y lo que terminaba en el informe (ej. tildar "Vivienda" y que
    # el informe final trajera otro bloque en su lugar) era indiagnosticable
    # despues del hecho: la bitacora solo decia "se respondio", nunca con
    # que contenido.
    if completado:
        bitacora.registrar("formulario_respondido", nombre=nombre, respuesta=resultado)
    else:
        bitacora.registrar("formulario_timeout", nombre=nombre)

    if not completado:
        # Nadie respondió dentro del timeout (la persona cerró la pestaña,
        # se fue, o lo que sea) - devolver {} tal cual hacía esto antes era
        # un riesgo real: el chequeo estándar que sigue a cualquier
        # mostrar_formulario() es `respuesta.get("salir_del_flujo")`, que
        # con un dict vacío da None (no True) y no dispara la salida
        # prolija - el siguiente acceso a un campo esperado (ej.
        # `respuesta["anio"]`) tiraba un KeyError sin manejar, exactamente
        # el tipo de falla cruda que este proyecto entero existe para
        # evitarle a alguien sin conocimientos técnicos. Devolver
        # salir_del_flujo=True hace que ese mismo chequeo, ya presente
        # después de cada formulario, también cubra este caso sin
        # necesitar ningún cambio en el resto del flujo.
        cierre.cerrar_consola(motivo="timeout_formulario")
        return {"salir_del_flujo": True, "motivo": "timeout"}

    # Salir sin terminar el informe: acá se termina la conversación (ver
    # .claude/instrucciones/encuesta-hogares.md), así que también se cierra la
    # consola. Se hace acá y no en las instrucciones del agente a
    # propósito: es el mismo criterio que los hooks del proyecto — una
    # regla que depende de que el modelo se acuerde de cumplirla en cada
    # corrida no se cumple siempre, y esta en particular es la que dejaba
    # una ventana abierta en la cara de alguien que ya se quiso ir.
    if resultado.get("salir_del_flujo"):
        cierre.cerrar_consola(motivo="salir_del_flujo")

    return resultado


def mostrar_finalizacion(pdf_path: str = "", html_path: str = "", timeout: float | None = config.TIMEOUT_FORMULARIO_SEGUNDOS) -> dict:
    """Último paso: pantalla de agradecimiento con links que abren el PDF
    y/o el HTML del informe. A diferencia de `start` desde la terminal (poco
    confiable — se vio en la práctica que podía fallar en silencio), estos
    links los sirve este mismo servidor local, así que abrirlos es un click
    normal del navegador. Bloquea hasta que el usuario elige una opción.

    El resultado trae `{"accion": "terminar"}` o `{"accion": "nuevo_informe"}`
    — este último significa que el agente tiene que reiniciar el flujo desde
    el paso 1 (ver .claude/instrucciones/encuesta-hogares.md), no terminar la
    conversación.
    """
    resultado: dict = {}
    evento = threading.Event()
    html = plantilla_finalizacion(pdf_disponible=bool(pdf_path), html_disponible=bool(html_path))
    html_bytes = html.encode("utf-8")

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/favicon"):
                self.send_response(204)
                self.end_headers()
                return
            if self.path == "/informe.pdf" and pdf_path:
                self._servir_archivo(pdf_path, "application/pdf")
                return
            if self.path == "/informe.html" and html_path:
                self._servir_archivo(html_path, "text/html; charset=utf-8")
                return
            _servir_html(self, html_bytes)

        def _servir_archivo(self, ruta: str, content_type: str):
            # El archivo puede haber desaparecido entre que se generó y que
            # la persona hizo click (movido a mano, borrado por un
            # antivirus). Sin esto, la excepción moría en el hilo del
            # servidor y el click no hacía nada, sin registro de por qué.
            try:
                datos = Path(ruta).read_bytes()
            except OSError as e:
                bitacora.registrar("finalizacion_archivo_ilegible", ruta=ruta, mensaje=str(e))
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(datos)))
            self.send_header("Content-Disposition", f'inline; filename="{Path(ruta).name}"')
            self.end_headers()
            self.wfile.write(datos)

        def do_POST(self):
            _responder_post(self, resultado, evento)

        def log_message(self, format, *args):
            pass

    bitacora.registrar("finalizacion_mostrada", pdf_disponible=bool(pdf_path), html_disponible=bool(html_path))
    completado = _servir_y_esperar(Handler, evento, timeout, "finalizacion_error")

    if completado:
        bitacora.registrar("finalizacion_respondida", respuesta=resultado)
    else:
        bitacora.registrar("finalizacion_timeout")

    if not completado:
        # Mismo riesgo que en mostrar_formulario(): devolver {} dejaba que
        # el siguiente `respuesta["accion"]` tirara un KeyError sin
        # manejar. Acá no existe "salir_del_flujo" (esta pantalla ya es el
        # final) - el equivalente seguro es tratarlo como si la persona
        # hubiera elegido terminar, que es exactamente lo que ya sabe
        # manejar el paso 8 del agente.
        cierre.cerrar_consola(motivo="timeout_finalizacion")
        return {"accion": "terminar", "motivo": "timeout"}

    # "terminar" es el final real del flujo — el usuario ya tiene su
    # informe y apretó "Listo, gracias". "nuevo_informe" NO cierra nada:
    # ahí el agente reinicia desde el paso 1 en la misma conversación, así
    # que la consola tiene que seguir viva.
    if resultado.get("accion") == "terminar":
        cierre.cerrar_consola(motivo="terminar")

    return resultado


