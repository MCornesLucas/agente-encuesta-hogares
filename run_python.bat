@echo off
REM Envoltorio fijo: el agente siempre invoca "run_python.bat", nunca la
REM ruta real de Python (que cambia en cada computadora). Lee la ruta
REM detectada por instalar.bat en .claude\python_path.txt y le reenvia
REM todos los argumentos. Esto tambien permite que la regla de permisos
REM en .claude\settings.json sea la misma para cualquier usuario.
setlocal
set "AQUI=%~dp0"
set /p PYEXE=<"%AQUI%.claude\python_path.txt"
REM Salida siempre en UTF-8: la consola de Windows usa cp1252 y no puede
REM mostrar algunos caracteres de los datos del INE (nombres de columna con
REM acentos mal codificados); sin esto, un print los hace fallar con
REM UnicodeEncodeError en medio de una corrida (paso real, 2026-09-09).
set "PYTHONIOENCODING=utf-8"
"%PYEXE%" %*
