@echo off
REM ============================================================
REM  Build eo-man.exe (Windows, no Python required to run)
REM
REM  Usage:
REM    build_exe.bat              -> GUI exe (kein Konsolenfenster)
REM    build_exe.bat --console    -> mit Konsole (fuer CLI-Befehle)
REM    build_exe.bat --onedir     -> Ordner-Build (schnellerer Start)
REM
REM  Voraussetzung: Virtualenv unter .venv mit installierten
REM  Projekt-Abhaengigkeiten (requirements.txt + Projekt selbst).
REM ============================================================
setlocal

REM ins Projektverzeichnis wechseln (Skript-Ordner)
pushd "%~dp0"

set "VENV_PY=.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo [ERROR] Virtualenv nicht gefunden: %CD%\.venv
    echo Bitte zuerst anlegen:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt
    echo   .venv\Scripts\pip install -e .
    popd
    exit /b 1
)

REM ---- Argumente parsen --------------------------------------
set "WINDOWED=--windowed"
set "MODE=--onefile"
:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--console" set "WINDOWED="
if /I "%~1"=="--onedir"  set "MODE=--onedir"
shift
goto parse_args
:args_done

REM ---- PyInstaller sicherstellen -----------------------------
"%VENV_PY%" -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installiere PyInstaller in .venv ...
    "%VENV_PY%" -m pip install pyinstaller
    if errorlevel 1 ( popd & exit /b 1 )
)

REM ---- Aufraeumen --------------------------------------------
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist
if exist eo-man.spec del /q eo-man.spec

REM ---- Build --------------------------------------------------
REM Hinweis: --collect-submodules eo_man ist noetig, weil eo_man\__main__.py
REM das Package zur Laufzeit dynamisch via __import__ / __package__ setzt,
REM was die statische Analyse von PyInstaller nicht erfasst. Ohne diesen
REM Schalter fehlen Submodule wie eo_man.data.app_info im Build.
REM pyproject.toml wird als Daten-Datei mitgepackt, da app_info.py sie zur
REM Laufzeit liest, um Versions- und Paketinfos anzuzeigen.
"%VENV_PY%" -m PyInstaller ^
    --noconfirm ^
    %MODE% ^
    %WINDOWED% ^
    --name eo-man ^
    --icon eo_man\icons\Faenza-system-search.ico ^
    --paths . ^
    --add-data "eo_man\icons;eo_man\icons" ^
    --add-data "eo_man\data\homeassistant;eo_man\data\homeassistant" ^
    --add-data "pyproject.toml;." ^
    --collect-submodules eo_man ^
    --collect-all enocean ^
    --collect-all eltakobus ^
    --collect-all esp2_gateway_adapter ^
    --collect-all tkinterhtml ^
    --collect-all tkScrolledFrame ^
    --collect-all aiocoap ^
    --collect-all zeroconf ^
    --hidden-import bs4 ^
    --hidden-import xmltodict ^
    eo_man\__main__.py

set "BUILD_RC=%ERRORLEVEL%"

if not "%BUILD_RC%"=="0" (
    echo.
    echo [ERROR] Build fehlgeschlagen.
    popd
    exit /b %BUILD_RC%
)

echo.
if /I "%MODE%"=="--onefile" (
    echo [OK] Fertig: %CD%\dist\eo-man.exe
) else (
    echo [OK] Fertig: %CD%\dist\eo-man\eo-man.exe
)

popd
endlocal
