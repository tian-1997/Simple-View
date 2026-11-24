@echo off
rem WinIsland launcher - with console (shows tracebacks and QML warnings)
setlocal
set "PY=%~dp0.venv\Scripts\python.exe"

if not exist "%PY%" (
    echo [WinIsland] venv not found: %PY%
    pause
    exit /b 1
)

"%PY%" "%~dp0app\main.py" %*
if errorlevel 1 pause
