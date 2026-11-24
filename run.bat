@echo off
rem WinIsland launcher - silent (no console window)
rem Uses the project venv so it never depends on the system Python.
setlocal
set "PY=%~dp0.venv\Scripts\pythonw.exe"

if not exist "%PY%" (
    echo [WinIsland] venv not found: %PY%
    echo Create it first:
    echo     python -m venv .venv
    echo     .venv\Scripts\python.exe -m pip install PySide6 comtypes psutil uiautomation
    pause
    exit /b 1
)

start "" "%PY%" "%~dp0app\main.py" %*
