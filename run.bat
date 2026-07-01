@echo off
python meeting_transcription.py
if errorlevel 1 (
    echo.
    echo [ERRORE] L'applicazione si e' chiusa con un errore.
    echo Controlla i log nella cartella "logs\".
    pause
)
