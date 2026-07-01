@echo off
setlocal

:: Use py (Python Launcher) to locate pythonw.exe
py --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo Download Python from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: Derive pythonw.exe path from python.exe
for /f "delims=" %%i in ('py -c "import sys; print(sys.executable)"') do set PYEXE=%%i
set PYWEXE=%PYEXE:python.exe=pythonw.exe%

if exist "%PYWEXE%" (
    start "" "%PYWEXE%" meeting_transcription.py
) else (
    start "" py meeting_transcription.py
)
