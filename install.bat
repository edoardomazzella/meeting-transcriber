@echo off
setlocal

echo ============================================
echo  Meeting Transcriber - Installer
echo ============================================
echo.

:: Find the correct Python command (py = Python Launcher, python = fallback)
set PYTHON_CMD=
py --version >nul 2>&1
if not errorlevel 1 set PYTHON_CMD=py
if "%PYTHON_CMD%"=="" (
    python --version >nul 2>&1
    if not errorlevel 1 set PYTHON_CMD=python
)
if "%PYTHON_CMD%"=="" (
    echo [ERROR] Python not found.
    echo Download Python 3.10 or later from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo Python version detected:
%PYTHON_CMD% --version
echo.

:: Ask GPU or CPU
echo Do you have an NVIDIA GPU with CUDA?
echo.
echo   [1] Yes - install with GPU support (recommended if you have an NVIDIA GPU)
echo   [2] No  - install CPU-only
echo.
set /p CHOICE="Choose (1 or 2): "

if "%CHOICE%"=="1" (
    echo.
    echo Installing GPU dependencies...
    %PYTHON_CMD% -m pip install -r requirements-gpu.txt
) else if "%CHOICE%"=="2" (
    echo.
    echo Installing CPU dependencies...
    %PYTHON_CMD% -m pip install -r requirements-cpu.txt
) else (
    echo.
    echo Invalid choice. Please run install.bat again.
    pause
    exit /b 1
)

if errorlevel 1 (
    echo.
    echo [ERROR] Installation failed. Check your Internet connection and try again.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Installation complete.
echo  Launch the app with: run.bat
echo ============================================
echo.
pause
