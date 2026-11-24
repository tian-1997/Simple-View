@echo off
rem WinIsland build: logo -> icon -> single-file exe
rem Output: dist\WinIsland.exe (no Python required on the target machine)
setlocal
set "PY=%~dp0.venv\Scripts\python.exe"

if not exist "%PY%" (
    echo [WinIsland] venv not found: %PY%
    echo Create it first:
    echo     python -m venv .venv
    echo     .venv\Scripts\python.exe -m pip install PySide6 comtypes psutil uiautomation pyinstaller pillow
    exit /b 1
)

rem A running instance locks dist\WinIsland.exe; close it before overwriting
taskkill /IM WinIsland.exe /F >nul 2>&1

rem Build-only deps, installed on demand
"%PY%" -c "import PyInstaller" 2>nul || "%PY%" -m pip install --quiet pyinstaller
"%PY%" -c "import PIL" 2>nul || "%PY%" -m pip install --quiet pillow

echo [1/2] icon: assets\branding\app-icon.png + build\WinIsland.ico
"%PY%" "%~dp0tools\make_icon.py"
if errorlevel 1 exit /b 1

echo [2/2] pyinstaller
"%PY%" -m PyInstaller --noconfirm --clean ^
    --distpath "%~dp0dist" ^
    --workpath "%~dp0build\pyinstaller" ^
    "%~dp0WinIsland.spec"
if errorlevel 1 (
    echo [WinIsland] build failed, see the errors above
    exit /b 1
)

echo.
echo done: %~dp0dist\WinIsland.exe
for %%F in ("%~dp0dist\WinIsland.exe") do echo size: %%~zF bytes
endlocal
