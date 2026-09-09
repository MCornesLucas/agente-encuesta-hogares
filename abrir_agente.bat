@echo off
cd /d "%~dp0"
title Agente - Encuesta de Hogares

where claude >nul 2>nul
if errorlevel 1 (
    echo No se encontro Claude Code en esta computadora.
    echo Corre primero instalar.bat, que esta en esta misma carpeta.
    pause
    exit /b 1
)

REM Minimiza esta terminal mientras se responde el formulario de arranque
REM (bienvenida con botones "Empezar" / "Salir"), para que lo primero que
REM se vea sea ese formulario en el navegador, no una consola vacia. Es
REM solo cosmetico: si falla, el arranque sigue igual.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0.claude\arranque\ventana.ps1" -Titulo "Agente - Encuesta de Hogares" -Accion Minimizar >nul 2>nul

set "ACCION="
for /f "delims=" %%A in ('run_python.bat arranque.py') do set "ACCION=%%A"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0.claude\arranque\ventana.ps1" -Titulo "Agente - Encuesta de Hogares" -Accion Restaurar >nul 2>nul

if /i not "%ACCION%"=="EMPEZAR" (
    exit /b 0
)

REM --- Cierre automatico de esta ventana al terminar el flujo ---
REM Una sesion interactiva de Claude Code no termina nunca por si sola
REM (confirmado contra la documentacion oficial de la CLI: no existe
REM ninguna forma nativa de que una sesion interactiva termine al final de
REM un turno). Como `claude` nunca retorna, sin esto las lineas de mas
REM abajo no se ejecutan jamas y la ventana queda viva de fondo
REM indefinidamente - tanto al terminar el informe como al apretar "Salir
REM sin terminar el informe". Se probo `claude -p` para resolverlo y se
REM revirtio porque rompia el flujo (ver el historial de este archivo).
REM
REM En cambio, ahora es el propio proyecto el que cierra la sesion de
REM Claude Code cuando el flujo termina de verdad
REM (src/encuesta_hogares/cierre.py, llamado desde los formularios). Estas
REM dos variables son las que le avisan que esta corriendo bajo esta
REM ventana y cual es la consola a cerrar. Se definen recien aca, despues
REM del formulario de arranque, para que arranque.py no pueda disparar un
REM cierre cuando todavia no hay ninguna sesion de Claude Code que cerrar.
REM
REM El PID de esta ventana se averigua preguntandole a powershell por su
REM propio proceso padre, con REDIRECCION a un archivo y no con
REM `for /f ('...')`: `for /f` corre el comando dentro de un cmd.exe
REM intermedio, asi que el padre de powershell terminaria siendo ese
REM proceso efimero (muerto un instante despues) en vez de esta consola, y
REM el cierre no encontraria nunca a quien cerrar. Verificado contra un
REM arbol de procesos real antes de dejarlo asi.
set "ENCUESTA_HOGARES_CONSOLA=1"
set "ARCHIVO_PID=%TEMP%\encuesta-hogares-pid-%RANDOM%.txt"
powershell -NoProfile -Command "$f = 'ProcessId=' + $PID; $p = Get-CimInstance Win32_Process -Filter $f; $p.ParentProcessId" > "%ARCHIVO_PID%"
set /p ENCUESTA_HOGARES_CONSOLA_PID=<"%ARCHIVO_PID%"
del "%ARCHIVO_PID%" >nul 2>nul

set "MARCA_CIERRE=%TEMP%\encuesta-hogares-cierre-%ENCUESTA_HOGARES_CONSOLA_PID%.marker"
if exist "%MARCA_CIERRE%" del "%MARCA_CIERRE%" >nul 2>nul

REM --model se fija a proposito: sin el, la sesion toma el modelo por
REM defecto de la cuenta, que puede cambiar sin que nadie toque el
REM proyecto. Es el unico lugar que fija el modelo de la corrida (no hay
REM subagente); .claude/instrucciones/encuesta-hogares.md lo declara con el
REM motivo largo y un test exige que los dos digan lo mismo.
claude --model claude-opus-5 "Quiero hacer la encuesta de hogares"

REM Terminar el proceso de Claude Code hace que `claude` salga con codigo
REM de error, asi que el codigo de salida por si solo no distingue "el
REM flujo termino bien y pedimos cerrar" de "Claude Code se rompio de
REM verdad" - esa diferencia la marca este archivo. Con marca: cierre
REM normal, la ventana se cierra sola. Sin marca y con error: se avisa y
REM se deja la ventana abierta para poder ver que paso.
if exist "%MARCA_CIERRE%" (
    del "%MARCA_CIERRE%" >nul 2>nul
    exit /b 0
)

if errorlevel 1 (
    echo.
    echo Hubo un problema y la sesion de Claude Code termino con error.
    pause
    exit /b 1
)

exit /b 0
