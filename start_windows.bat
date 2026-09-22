@echo off
title Cita Auto - Consular Appointment Bot
cd /d "%~dp0"

echo ================================================================
echo           CITA AUTO - Consular Appointment Bot
echo ================================================================

if not exist config.json (
    echo [INFO] config.json not found. Copying from config.example.json...
    copy config.example.json config.json >nul
    echo [NOTICE] Created config.json. Please edit your credentials if needed.
)

if exist cita_auto.exe (
    cita_auto.exe
) else (
    echo [INFO] cita_auto.exe not found in directory.
    echo Running python cita_auto.py...
    python cita_auto.py
)

pause
