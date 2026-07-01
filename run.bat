@echo off
setlocal

:: Usa py (Python Launcher) per trovare il percorso di pythonw.exe
py --version >nul 2>&1
if errorlevel 1 (
    echo [ERRORE] Python non trovato.
    echo Scarica Python da https://www.python.org/downloads/
    echo Assicurati di spuntare "Add Python to PATH" durante l'installazione.
    pause
    exit /b 1
)

:: Ricava pythonw.exe dalla stessa cartella di python.exe
for /f "delims=" %%i in ('py -c "import sys; print(sys.executable)"') do set PYEXE=%%i
set PYWEXE=%PYEXE:python.exe=pythonw.exe%

if exist "%PYWEXE%" (
    start "" "%PYWEXE%" meeting_transcription.py
) else (
    start "" py meeting_transcription.py
)
)
