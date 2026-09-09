"""Bitácora local de sesiones: un registro liviano de qué formularios se
mostraron, cuánto tardó cada uno, y si algo falló - todo en la propia
computadora del usuario, sin salir a internet.

Nace de un punto ciego real de este proyecto: cuando algo sale mal para
alguien sin conocimientos técnicos, hasta ahora la única forma de
enterarse era que esa persona describiera lo que vio (por chat, con una
captura de pantalla) - lento, impreciso, y depende de que la persona note
el problema y se tome el trabajo de reportarlo bien. Con esta bitácora,
el dueño del proyecto puede pedirle a la persona un solo archivo
(`logs/bitacora.jsonl`) en vez de una descripción de memoria, y ese
archivo alcanza para reconstruir qué pasó con datos objetivos: qué
formulario se mostró, cuándo, si hubo timeout o una excepción real.

No reemplaza el reporte de la persona - lo complementa. Nunca se sube a
git (ver .gitignore) y nunca sale de la computadora donde corre: nadie
más que el dueño del proyecto lo ve, y solo si la persona se lo manda.

**Regla de contenido, para quien agregue formularios o eventos:** este
archivo registra las respuestas completas de los formularios
(`formulario_respondido` guarda `respuesta` entera - necesario para
diagnosticar "marqué X y el informe trajo Y"). Eso es seguro HOY porque
ningún formulario pide datos personales: un año, números de métrica,
botones. Si algún día un formulario pidiera un nombre, un mail o
cualquier dato de la persona, esa respuesta viajaría en el archivo que
se le pide a la gente que mande - en ese momento, esta línea deja de
registrar `respuesta` entera y pasa a registrar solo los campos
inocuos, elegidos a mano.

`medir()` y `medir_comando()` agregan una segunda cosa a esta bitácora:
cuánto tarda de verdad cada paso pesado del flujo (cargar datos, ejecutar
el notebook completo, convertir a PDF) - para responder "¿dónde se va el
tiempo?" con números reales de una corrida, en vez de adivinar.
"""

from __future__ import annotations

import json
import subprocess
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone

from . import config

LOG_PATH = config.PROJECT_ROOT / "logs" / "bitacora.jsonl"

# La bitácora se escribe en cada formulario y en cada paso pesado, así que
# crece indefinidamente en una instalación que se use seguido. Al llegar a
# este tamaño se guarda como ".1" y se arranca de nuevo: se conserva una
# sola tanda anterior, que alcanza para diagnosticar (lo que importa es lo
# reciente) sin que el archivo crezca para siempre en la computadora de
# alguien que nunca lo va a mirar.
_TAMANIO_MAXIMO_EN_BYTES = 2_000_000


def _rotar_si_hace_falta() -> None:
    try:
        if LOG_PATH.exists() and LOG_PATH.stat().st_size >= _TAMANIO_MAXIMO_EN_BYTES:
            anterior = LOG_PATH.with_suffix(LOG_PATH.suffix + ".1")
            anterior.unlink(missing_ok=True)
            LOG_PATH.rename(anterior)
    except OSError:
        pass


def registrar(tipo: str, **detalle) -> None:
    """Agrega una línea al log. Nunca deja escapar una excepción: un fallo
    al escribir el log (disco lleno, carpeta sin permisos) no puede tirar
    abajo el flujo real de la persona que está usando el agente - la
    bitácora es de apoyo, nunca puede ser la causa de un problema nuevo."""
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _rotar_si_hace_falta()
        linea = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "tipo": tipo,
            **detalle,
        }
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(linea, ensure_ascii=False) + "\n")
    except Exception:
        pass


@contextmanager
def medir(nombre: str, **detalle):
    """Cronometra un bloque de código Python y lo registra. Envolvé con
    esto los pasos pesados que el agente ejecuta como código Python
    directo (ej. cargar los datos), no llamadas a otro programa - para eso
    está `medir_comando()`. Si el bloque lanza una excepción, igual se
    registra la duración hasta ese punto, junto con el error."""
    inicio = time.monotonic()
    try:
        yield
    except Exception as e:
        registrar(
            f"{nombre}_error",
            duracion_segundos=round(time.monotonic() - inicio, 1),
            mensaje=str(e),
            traceback=traceback.format_exc(),
        )
        raise
    else:
        registrar(f"{nombre}_fin", duracion_segundos=round(time.monotonic() - inicio, 1), **detalle)


def sugerir_catalogo(metrica: str, motivo: str) -> None:
    """Registra que una métrica a medida (paso 6 del flujo del agente)
    parece lo bastante reusable como para valer la pena incorporarla al
    catálogo permanente — para que el dueño del proyecto la vea después
    con `tools/resumen_sesiones.py`, revisando la bitácora cuando tenga
    tiempo.

    A propósito NO es una pregunta interactiva que el agente le haga al
    usuario y espere respuesta: la consola de Claude Code corre en
    segundo plano para la enorme mayoría de quien usa este agente (nunca
    la abren, ni deberían necesitar hacerlo — ver "Qué Python usar" en
    `.claude/instrucciones/encuesta-hogares.md`), así que una pregunta bloqueante
    ahí no la vería nadie, y el proceso puede cerrarse apenas la persona
    termina o sale del flujo. Quedar registrado en un archivo que
    sobrevive al cierre es la única forma confiable de que esto no se
    pierda.
    """
    registrar("sugerencia_catalogo", metrica=metrica, motivo=motivo)


def medir_comando(nombre: str, comando: list[str]) -> subprocess.CompletedProcess:
    """Corre un comando externo (ej. `jupyter nbconvert`) cronometrando
    cuánto tarda, y lo registra en la bitácora. Pensado para los pasos
    pesados que el agente invoca como subprocess en vez de código Python
    directo - la ejecución del notebook completo, la conversión a HTML."""
    inicio = time.monotonic()
    try:
        resultado = subprocess.run(comando, check=True)
    except Exception as e:
        registrar(f"{nombre}_error", duracion_segundos=round(time.monotonic() - inicio, 1), mensaje=str(e))
        raise
    registrar(f"{nombre}_fin", duracion_segundos=round(time.monotonic() - inicio, 1))
    return resultado


def leer_eventos() -> list[dict]:
    """Lee todos los eventos registrados. Ignora líneas corruptas en vez de
    fallar entera la lectura - un log que creció con el tiempo puede tener
    quedado a medio escribir si el proceso se cortó en el momento justo."""
    if not LOG_PATH.exists():
        return []
    eventos = []
    for linea in LOG_PATH.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea:
            continue
        try:
            eventos.append(json.loads(linea))
        except json.JSONDecodeError:
            continue
    return eventos


def agrupar_en_sesiones(eventos: list[dict], gap_horas: float = 2.0) -> list[list[dict]]:
    """Agrupa eventos consecutivos en "sesiones": una sesión termina cuando
    pasan más de `gap_horas` entre un evento y el siguiente. El log no
    tiene un ID de sesión explícito, así que el gap de tiempo es la mejor
    aproximación disponible sin agregar más infraestructura (ej. un
    identificador de proceso) para un caso de uso que no lo necesita."""
    if not eventos:
        return []
    eventos_ordenados = sorted(eventos, key=lambda e: e["timestamp"])
    sesiones = [[eventos_ordenados[0]]]
    for anterior, actual in zip(eventos_ordenados, eventos_ordenados[1:]):
        t_anterior = datetime.fromisoformat(anterior["timestamp"])
        t_actual = datetime.fromisoformat(actual["timestamp"])
        if (t_actual - t_anterior).total_seconds() > gap_horas * 3600:
            sesiones.append([])
        sesiones[-1].append(actual)
    return sesiones


@dataclass
class ResumenSesion:
    inicio: str
    fin: str
    formularios_mostrados: int
    timeouts: int
    errores: list[dict] = field(default_factory=list)
    pasos_medidos: list[dict] = field(default_factory=list)
    sugerencias_catalogo: list[dict] = field(default_factory=list)
    checkpoints_paso5: list[dict] = field(default_factory=list)
    # Cada re-ejecución del notebook con su motivo (evento
    # "reejecucion_notebook", ver paso 7 del agente). Sin esto, una corrida
    # con el notebook ejecutado dos veces mostraba ~4 minutos inexplicables.
    reejecuciones: list[dict] = field(default_factory=list)


def resumir_sesion(eventos: list[dict]) -> ResumenSesion:
    pasos_medidos = [
        {"nombre": e["tipo"].removesuffix("_fin"), "duracion_segundos": e["duracion_segundos"], "timestamp": e["timestamp"]}
        for e in eventos
        if e["tipo"].endswith("_fin") and "duracion_segundos" in e
    ]

    # A diferencia de pasos_medidos (que mide bloques de código Python que
    # corren de punta a punta), estos puntos de control marcan instantes
    # dentro del paso 5 en los que el modelo todavía no corrió nada -
    # arman, en su lugar, tramos por diferencia entre puntos consecutivos.
    # Nace de un hueco real de 9m41s entre el formulario del catálogo y el
    # arranque de la carga de datos que la bitácora, hasta ahora, no podía
    # explicar - ver paso 5 en .claude/instrucciones/encuesta-hogares.md.
    crudos = [e for e in eventos if e["tipo"] == "paso5_checkpoint"]
    checkpoints_paso5 = []
    anterior = None
    for e in crudos:
        entrada = {"etapa": e.get("etapa", "?"), "timestamp": e["timestamp"], "segundos_desde_el_anterior": None}
        if anterior is not None:
            t_anterior = datetime.fromisoformat(anterior["timestamp"])
            t_actual = datetime.fromisoformat(e["timestamp"])
            entrada["segundos_desde_el_anterior"] = round((t_actual - t_anterior).total_seconds(), 1)
        checkpoints_paso5.append(entrada)
        anterior = e

    return ResumenSesion(
        inicio=eventos[0]["timestamp"],
        fin=eventos[-1]["timestamp"],
        formularios_mostrados=sum(1 for e in eventos if e["tipo"] == "formulario_mostrado"),
        timeouts=sum(1 for e in eventos if e["tipo"] == "formulario_timeout"),
        errores=[e for e in eventos if e["tipo"].endswith("_error")],
        pasos_medidos=sorted(pasos_medidos, key=lambda p: -p["duracion_segundos"]),
        sugerencias_catalogo=[e for e in eventos if e["tipo"] == "sugerencia_catalogo"],
        checkpoints_paso5=checkpoints_paso5,
        reejecuciones=[e for e in eventos if e["tipo"] == "reejecucion_notebook"],
    )
