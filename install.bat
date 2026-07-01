@echo off
setlocal

echo ============================================
echo  Meeting Transcriber - Installer
echo ============================================
echo.

:: Trova il comando Python corretto (py = Python Launcher, python = fallback)
set PYTHON_CMD=
py --version >nul 2>&1
if not errorlevel 1 set PYTHON_CMD=py
if "%PYTHON_CMD%"=="" (
    python --version >nul 2>&1
    if not errorlevel 1 set PYTHON_CMD=python
)
if "%PYTHON_CMD%"=="" (
    echo [ERRORE] Python non trovato.
    echo Scarica Python 3.10 o superiore da https://www.python.org/downloads/
    echo Assicurati di spuntare "Add Python to PATH" durante l'installazione.
    echo.
    pause
    exit /b 1
)

echo Versione Python rilevata:
%PYTHON_CMD% --version
echo.

:: Ask GPU or CPU
echo Hai una GPU NVIDIA con CUDA?
echo.
echo   [1] Si  - installa con supporto GPU (consigliato se hai una GPU NVIDIA)
echo   [2] No  - installa solo CPU
echo.
set /p SCELTA="Scegli (1 o 2): "

if "%SCELTA%"=="1" (
    echo.
    echo Installazione dipendenze GPU...
    %PYTHON_CMD% -m pip install -r requirements-gpu.txt
) else if "%SCELTA%"=="2" (
    echo.
    echo Installazione dipendenze CPU...
    %PYTHON_CMD% -m pip install -r requirements-cpu.txt
) else (
    echo.
    echo Scelta non valida. Esegui di nuovo install.bat.
    pause
    exit /b 1
)

if errorlevel 1 (
    echo.
    echo [ERRORE] Installazione fallita. Controlla la connessione Internet e riprova.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Installazione completata.
echo  Avvia l'app con: run.bat
echo ============================================
echo.
pause
