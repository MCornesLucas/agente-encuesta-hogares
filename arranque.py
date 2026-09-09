"""Pantalla de arranque que corre `abrir_agente.bat` antes de levantar
Claude Code: un formulario con dos botones (empezar / salir), para que el
primer mensaje que recibe el agente sea siempre el mismo texto fijo, sin
depender de que el usuario escriba algo (y sin la ambigüedad que eso
genera). Imprime "EMPEZAR" o "SALIR" por stdout como única salida, para
que `abrir_agente.bat` la capture.
"""

from encuesta_hogares import formularios

respuesta = formularios.mostrar_formulario(formularios.plantilla_arranque())
print("EMPEZAR" if respuesta.get("accion") == "empezar" else "SALIR")
